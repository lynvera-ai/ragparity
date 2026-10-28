"""Bounded-memory comparisons using a private, temporary SQLite metadata spool."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from lynvera_ragparity.core import (
    AdapterError,
    CheckPolicy,
    CheckReport,
    Finding,
    Record,
    RecordReader,
    Severity,
    Status,
)


class ConsistencyChecker:
    def __init__(self, policy: CheckPolicy | None = None) -> None:
        self.policy = policy or CheckPolicy()

    def _add(
        self,
        report: CheckReport,
        code: str,
        status: Status,
        side: str,
        recommendation: str,
        record: Record | None = None,
        **evidence: object,
    ) -> None:
        report.add(
            Finding(
                code=code,
                status=status,
                severity=(
                    Severity.ERROR
                    if status in (Status.FAIL, Status.ERROR)
                    else Severity.WARNING
                    if status == Status.INCONCLUSIVE
                    else Severity.INFO
                ),
                source=side,
                source_id=record.source_id if record else None,
                document_id=record.document_id if record else None,
                collection=record.collection if record else None,
                evidence=evidence,
                recommendation=recommendation,
            ),
            self.policy.max_findings,
        )

    def _stage(
        self, connection: sqlite3.Connection, reader: RecordReader, side: str, report: CheckReport
    ) -> bool:
        unknown_identity = False
        for batch in reader.iter_batches(self.policy.batch_size):
            for record in batch:
                if side == "source":
                    report.source_records += 1
                else:
                    report.index_records += 1
                missing = [
                    key
                    for key in Record.model_fields
                    if key != "indexed_at" and getattr(record, key) is None
                ]
                if missing:
                    self._add(
                        report,
                        "MISSING_METADATA",
                        Status.INCONCLUSIVE,
                        side,
                        "Populate required metadata before asserting parity.",
                        record,
                        fields=missing,
                    )
                if record.identity is None:
                    unknown_identity = True
                    continue
                connection.execute(
                    "INSERT INTO records(side, identity, payload) VALUES (?, ?, ?)",
                    (side, json.dumps(record.identity), record.model_dump_json()),
                )
            connection.commit()
        return unknown_identity

    def _compare(self, source: Record, index: Record | None, report: CheckReport) -> None:
        report.comparisons += 1
        if source.is_deleted is None:
            return
        if source.is_deleted:
            policy = self.policy.deletion_policy
            if policy == "ignore":
                self._add(
                    report,
                    "DELETION_IGNORED",
                    Status.PASS,
                    "both",
                    "No action required under the ignore policy.",
                    source,
                    policy=policy,
                )
                return
            if policy == "remove":
                self._add(
                    report,
                    "DELETED_PRESENT" if index else "DELETION_CONFIRMED",
                    Status.FAIL if index else Status.PASS,
                    "both",
                    "Remove the indexed record." if index else "No action required.",
                    source,
                    policy=policy,
                )
                return
            if index is None:
                self._add(
                    report,
                    "MISSING_TOMBSTONE",
                    Status.FAIL,
                    "index",
                    "Write the required indexed tombstone.",
                    source,
                )
                return
        elif index is None:
            self._add(
                report,
                "MISSING_INDEX",
                Status.FAIL,
                "index",
                "Index the current source record.",
                source,
            )
            return
        assert index is not None
        incomplete = False
        mismatch = False
        for field, code in (
            ("is_deleted", "DELETION_MISMATCH"),
            ("source_version", "VERSION_MISMATCH"),
            ("content_hash", "HASH_MISMATCH"),
        ):
            expected, actual = getattr(source, field), getattr(index, field)
            if expected is None or actual is None:
                incomplete = True
                continue
            if expected != actual:
                mismatch = True
                self._add(
                    report,
                    code,
                    Status.FAIL,
                    "both",
                    "Reindex from the current authoritative source.",
                    source,
                    expected=expected,
                    actual=actual,
                )
        if not incomplete and not mismatch:
            self._add(
                report,
                "RECORD_SYNCED",
                Status.PASS,
                "both",
                "No action required; compared metadata agrees.",
                source,
            )

    def check(self, source: RecordReader, index: RecordReader) -> CheckReport:
        report = CheckReport(status=Status.PASS)
        side = "source"
        try:
            with (
                TemporaryDirectory(prefix="ragparity-") as directory,
                closing(sqlite3.connect(Path(directory) / "metadata.sqlite")) as connection,
            ):
                connection.execute("CREATE TABLE records (side TEXT, identity TEXT, payload TEXT)")
                source_unknown = self._stage(connection, source, "source", report)
                side = "index"
                index_unknown = self._stage(connection, index, "index", report)
                connection.execute("CREATE INDEX identity_lookup ON records(side, identity)")
                connection.execute(
                    "CREATE TABLE grouped AS SELECT side, identity, MIN(payload) AS payload, "
                    "COUNT(*) AS n FROM records GROUP BY side, identity"
                )
                connection.execute("CREATE UNIQUE INDEX grouped_lookup ON grouped(side, identity)")
                for duplicate_side, payload, count in connection.execute(
                    "SELECT side, payload, n FROM grouped WHERE n > 1 ORDER BY side, identity"
                ):
                    self._add(
                        report,
                        "DUPLICATE_ID",
                        Status.FAIL,
                        duplicate_side,
                        "Provide one metadata record per document identity.",
                        Record.model_validate_json(payload),
                        count=count,
                    )
                for payload, other, count, other_count in connection.execute(
                    "SELECT s.payload, i.payload, s.n, i.n FROM grouped s LEFT JOIN grouped i "
                    "ON i.side='index' AND i.identity=s.identity "
                    "WHERE s.side='source' ORDER BY s.identity"
                ):
                    if count > 1 or (other_count is not None and other_count > 1):
                        continue
                    if other is None and index_unknown:
                        continue
                    self._compare(
                        Record.model_validate_json(payload),
                        Record.model_validate_json(other) if other else None,
                        report,
                    )
                if not source_unknown:
                    for (payload,) in connection.execute(
                        "SELECT i.payload FROM grouped i LEFT JOIN grouped s "
                        "ON s.side='source' AND s.identity=i.identity "
                        "WHERE i.side='index' AND s.identity IS NULL ORDER BY i.identity"
                    ):
                        self._add(
                            report,
                            "ORPHAN_INDEX",
                            Status.FAIL,
                            "index",
                            "Remove the orphan or restore its authoritative source.",
                            Record.model_validate_json(payload),
                        )
        except AdapterError:
            self._add(
                report,
                "ADAPTER_ERROR",
                Status.ERROR,
                side,
                "Check adapter connectivity, permissions and metadata mapping.",
            )
        except (OSError, sqlite3.Error):
            self._add(
                report,
                "STORAGE_ERROR",
                Status.ERROR,
                "checker",
                "Check available temporary disk space and filesystem permissions.",
            )
        if (
            report.source_records == 0
            and report.index_records == 0
            and report.status != Status.ERROR
        ):
            self._add(
                report,
                "NO_EVIDENCE",
                Status.INCONCLUSIVE,
                "both",
                "Provide source and index records before asserting parity.",
            )
        return report
