"""Bounded-memory document and chunk comparisons with conservative audit gates."""

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, suppress
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from lynvera_ragparity.checks.audit import snapshot_issues
from lynvera_ragparity.core import (
    AdapterError,
    AuditContext,
    CheckPolicy,
    CheckReport,
    ExecutionMetrics,
    Finding,
    FindingCode,
    Record,
    RecordReader,
    Severity,
    SnapshotEvidence,
    Status,
)
from lynvera_ragparity.core.models import BASE_RECORD_FIELDS

LAG_CODES = {
    "MISSING_INDEX",
    "VERSION_MISMATCH",
    "HASH_MISMATCH",
    "DELETION_MISMATCH",
    "DELETED_PRESENT",
    "MISSING_TOMBSTONE",
    "MISSING_CHUNK",
    "UNEXPECTED_CHUNK",
    "CHUNK_HASH_MISMATCH",
    "MIXED_CHUNK_VERSIONS",
}


class _Interrupted(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


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
        *,
        chunk_id: str | None = None,
        **evidence: object,
    ) -> None:
        if status == Status.FAIL and code in LAG_CODES and self.policy.sync_grace_seconds:
            assert record is not None and report.audit is not None
            evidence["underlying_code"] = code
            if record.updated_at is None:
                code, status = "SYNC_EVIDENCE_MISSING", Status.INCONCLUSIVE
                recommendation = "Supply the source change timestamp to evaluate the grace window."
            else:
                age = (report.audit.reference_time - record.updated_at).total_seconds()
                if record.updated_at > report.audit.reference_time:
                    code, status = "INVALID_TIMESTAMP", Status.INCONCLUSIVE
                    recommendation = "Correct the authoritative timestamp or audit reference time."
                elif age < self.policy.sync_grace_seconds:
                    code, status = "SYNC_PENDING", Status.INCONCLUSIVE
                    recommendation = "Repeat the audit after the declared synchronization window."
                    evidence["remaining_seconds"] = self.policy.sync_grace_seconds - age
        report.add(
            Finding(
                code=FindingCode(code),
                status=status,
                severity=Severity.ERROR
                if status in (Status.FAIL, Status.ERROR)
                else (Severity.WARNING if status == Status.INCONCLUSIVE else Severity.INFO),
                source=side,
                source_id=record.source_id if record else None,
                document_id=record.document_id if record else None,
                collection=record.collection if record else None,
                chunk_id=chunk_id or (record.chunk_id if record else None),
                evidence=evidence,
                recommendation=recommendation,
            ),
            self.policy.max_findings,
        )

    def _stage(
        self,
        connection: sqlite3.Connection,
        reader: RecordReader,
        side: str,
        report: CheckReport,
        snapshot: SnapshotEvidence | None,
        guard: Callable[[], None],
    ) -> bool:
        unknown_identity = False
        batches = reader.iter_batches(self.policy.batch_size)
        try:
            for batch in batches:
                guard()
                rows = []
                for record in batch:
                    if side == "source":
                        report.source_records += 1
                    else:
                        report.index_records += 1
                    missing = [key for key in BASE_RECORD_FIELDS if getattr(record, key) is None]
                    chunked_index = self.policy.identity_mode == "chunk" and side == "index"
                    if chunked_index:
                        missing.extend(
                            key
                            for key in ("chunk_id", "chunk_hash")
                            if getattr(record, key) is None
                        )
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
                    if snapshot is not None and (
                        record.snapshot_id != snapshot.snapshot_id
                        or (record.updated_at is not None and record.updated_at > snapshot.as_of)
                    ):
                        self._add(
                            report,
                            "SNAPSHOT_RECORD_MISMATCH",
                            Status.INCONCLUSIVE,
                            side,
                            "Read immutable rows belonging to the declared snapshot.",
                            record,
                        )
                    if (
                        record.updated_at is not None
                        and report.audit is not None
                        and (record.updated_at > report.audit.reference_time)
                    ):
                        self._add(
                            report,
                            "INVALID_TIMESTAMP",
                            Status.INCONCLUSIVE,
                            side,
                            "Use a change timestamp at or before the audit reference time.",
                            record,
                        )
                    wrong_layout = record.chunk_id is not None and (
                        self.policy.identity_mode == "document" or side == "source"
                    )
                    if wrong_layout:
                        self._add(
                            report,
                            "LAYOUT_MISMATCH",
                            Status.INCONCLUSIVE,
                            side,
                            "Use document source rows and the configured index identity mode.",
                            record,
                        )
                    if (
                        record.identity is None
                        or wrong_layout
                        or (chunked_index and record.chunk_id is None)
                    ):
                        unknown_identity = True
                        continue
                    identity = json.dumps(record.identity)
                    item = (
                        json.dumps((*record.identity, record.chunk_id))
                        if chunked_index
                        else identity
                    )
                    rows.append((side, identity, item, record.model_dump_json()))
                connection.executemany(
                    "INSERT INTO records(side, identity, item, payload) VALUES (?, ?, ?, ?)", rows
                )
                connection.commit()
        finally:
            close = getattr(batches, "close", None)
            if callable(close):
                close()
        guard()
        return unknown_identity

    def _deletion(self, source: Record, present: bool, report: CheckReport) -> bool:
        if source.is_deleted is None:
            return True
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
                return True
            if policy == "remove":
                self._add(
                    report,
                    "DELETED_PRESENT" if present else "DELETION_CONFIRMED",
                    Status.FAIL if present else Status.PASS,
                    "both",
                    "Remove all indexed rows." if present else "No action required.",
                    source,
                    policy=policy,
                )
                return True
            if not present:
                self._add(
                    report,
                    "MISSING_TOMBSTONE",
                    Status.FAIL,
                    "index",
                    "Write the required indexed tombstone.",
                    source,
                )
                return True
        return False

    def _metadata(self, source: Record, index: Record, report: CheckReport) -> bool:
        synced = True
        for field, code in (
            ("is_deleted", "DELETION_MISMATCH"),
            ("source_version", "VERSION_MISMATCH"),
            ("content_hash", "HASH_MISMATCH"),
        ):
            expected, actual = getattr(source, field), getattr(index, field)
            if expected is None or actual is None:
                synced = False
            elif expected != actual:
                synced = False
                self._add(
                    report,
                    code,
                    Status.FAIL,
                    "both",
                    "Reindex from the current authoritative source.",
                    source,
                    chunk_id=index.chunk_id,
                    expected=expected,
                    actual=actual,
                )
        return synced

    def _compare(self, source: Record, index: Record | None, report: CheckReport) -> None:
        report.comparisons += 1
        if self._deletion(source, index is not None, report):
            return
        if index is None:
            self._add(
                report,
                "MISSING_INDEX",
                Status.FAIL,
                "index",
                "Index the current source record.",
                source,
            )
        elif self._metadata(source, index, report):
            self._add(
                report,
                "RECORD_SYNCED",
                Status.PASS,
                "both",
                "No action required; compared metadata agrees.",
                source,
            )

    def _chunks(
        self,
        source: Record,
        rows: Iterator[tuple[str, int]],
        present: bool,
        report: CheckReport,
        guard: Callable[[], None],
    ) -> None:
        report.comparisons += 1
        if self._deletion(source, present, report):
            return
        manifest = source.expected_chunks
        if manifest is None:
            self._add(
                report,
                "CHUNK_MANIFEST_MISSING",
                Status.INCONCLUSIVE,
                "source",
                "Provide the complete expected chunk ID to hash mapping.",
                source,
            )
            return
        remaining = set(manifest)
        synced = True
        first_version = None
        mixed = False
        for payload, count in rows:
            guard()
            chunk = Record.model_validate_json(payload)
            assert chunk.chunk_id is not None
            remaining.discard(chunk.chunk_id)
            if count > 1:
                synced = False
                continue
            if chunk.source_version is not None:
                if (
                    first_version is not None
                    and chunk.source_version != first_version
                    and not mixed
                ):
                    mixed = True
                    self._add(
                        report,
                        "MIXED_CHUNK_VERSIONS",
                        Status.FAIL,
                        "index",
                        "Replace the document chunks as one complete version.",
                        source,
                    )
                first_version = chunk.source_version
            if chunk.chunk_id not in manifest:
                synced = False
                self._add(
                    report,
                    "UNEXPECTED_CHUNK",
                    Status.FAIL,
                    "index",
                    "Remove chunks absent from the authoritative manifest.",
                    source,
                    chunk_id=chunk.chunk_id,
                )
            elif chunk.chunk_hash is None:
                synced = False
            elif chunk.chunk_hash != manifest[chunk.chunk_id]:
                synced = False
                self._add(
                    report,
                    "CHUNK_HASH_MISMATCH",
                    Status.FAIL,
                    "both",
                    "Rebuild the fragment using the authoritative chunk manifest.",
                    source,
                    chunk_id=chunk.chunk_id,
                    expected=manifest[chunk.chunk_id],
                    actual=chunk.chunk_hash,
                )
            synced = self._metadata(source, chunk, report) and synced
        for chunk_id in sorted(remaining):
            self._add(
                report,
                "MISSING_CHUNK",
                Status.FAIL,
                "index",
                "Index the missing authoritative fragment.",
                source,
                chunk_id=chunk_id,
            )
        if synced and not remaining:
            self._add(
                report,
                "CHUNKS_SYNCED",
                Status.PASS,
                "both",
                "All expected chunks and metadata agree.",
                source,
                chunk_count=len(manifest),
            )

    def _compare_staged(
        self,
        connection: sqlite3.Connection,
        report: CheckReport,
        source_unknown: bool,
        index_unknown: bool,
        guard: Callable[[], None],
    ) -> None:
        connection.execute("CREATE INDEX identity_lookup ON records(side, item)")
        guard()
        connection.execute(
            "CREATE TABLE grouped AS SELECT side, identity, item, MIN(payload) AS payload, "
            "COUNT(*) AS n FROM records GROUP BY side, identity, item"
        )
        connection.execute("CREATE UNIQUE INDEX grouped_item ON grouped(side, item)")
        connection.execute("CREATE INDEX grouped_document ON grouped(side, identity)")
        for side, payload, count in connection.execute(
            "SELECT side, payload, n FROM grouped WHERE n > 1 ORDER BY side, item"
        ):
            guard()
            self._add(
                report,
                "DUPLICATE_ID",
                Status.FAIL,
                side,
                "Provide one row per configured identity in each layer.",
                Record.model_validate_json(payload),
                count=count,
            )
        if self.policy.identity_mode == "document":
            for payload, other, count, other_count in connection.execute(
                "SELECT s.payload, i.payload, s.n, i.n FROM grouped s LEFT JOIN grouped i "
                "ON i.side='index' AND i.identity=s.identity "
                "WHERE s.side='source' ORDER BY s.identity"
            ):
                guard()
                if count > 1 or (other_count is not None and other_count > 1):
                    continue
                if other is None and index_unknown:
                    continue
                self._compare(
                    Record.model_validate_json(payload),
                    Record.model_validate_json(other) if other else None,
                    report,
                )
        elif not index_unknown:
            for identity, payload, count in connection.execute(
                "SELECT identity, payload, n FROM grouped WHERE side='source' ORDER BY identity"
            ):
                guard()
                if count > 1:
                    continue
                source = Record.model_validate_json(payload)
                present = (
                    connection.execute(
                        "SELECT 1 FROM grouped WHERE side='index' AND identity=? LIMIT 1",
                        (identity,),
                    ).fetchone()
                    is not None
                )
                rows = connection.execute(
                    "SELECT payload, n FROM grouped "
                    "WHERE side='index' AND identity=? ORDER BY item",
                    (identity,),
                )
                self._chunks(source, iter(rows), present, report, guard)
        if not source_unknown:
            for (payload,) in connection.execute(
                "SELECT i.payload FROM grouped i LEFT JOIN grouped s "
                "ON s.side='source' AND s.identity=i.identity "
                "WHERE i.side='index' AND s.identity IS NULL ORDER BY i.item"
            ):
                guard()
                self._add(
                    report,
                    "ORPHAN_INDEX",
                    Status.FAIL,
                    "index",
                    "Remove the orphan or restore its authoritative source.",
                    Record.model_validate_json(payload),
                )

    def check(
        self,
        source: RecordReader,
        index: RecordReader,
        *,
        source_snapshot: SnapshotEvidence | None = None,
        index_snapshot: SnapshotEvidence | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> CheckReport:
        started = monotonic()
        reference = self.policy.reference_time or datetime.now(UTC)
        report = CheckReport(
            status=Status.PASS,
            metrics=ExecutionMetrics(),
            audit=AuditContext(
                reference_time=reference,
                identity_mode=self.policy.identity_mode,
                deletion_policy=self.policy.deletion_policy,
                sync_grace_seconds=self.policy.sync_grace_seconds,
                source_snapshot=source_snapshot,
                index_snapshot=index_snapshot,
            ),
        )
        deadline = (
            started + self.policy.max_duration_seconds if self.policy.max_duration_seconds else None
        )

        def guard() -> None:
            if cancel is not None and cancel():
                raise _Interrupted("CHECK_CANCELLED")
            if deadline is not None and monotonic() >= deadline:
                raise _Interrupted("TIME_LIMIT_EXCEEDED")

        interrupted: str | None = None

        def sqlite_progress() -> int:
            nonlocal interrupted
            try:
                guard()
            except _Interrupted as exc:
                interrupted = exc.code
                return 1
            return 0

        side = "source"
        try:
            guard()
            with (
                TemporaryDirectory(
                    prefix="ragparity-", dir=self.policy.temporary_directory
                ) as directory,
                closing(sqlite3.connect(Path(directory) / "metadata.sqlite")) as connection,
            ):
                connection.set_progress_handler(sqlite_progress, 10_000)
                connection.execute("PRAGMA cache_size=-8192")
                connection.execute("PRAGMA temp_store=FILE")
                if self.policy.max_spool_bytes is not None:
                    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
                    pages = self.policy.max_spool_bytes // page_size
                    connection.execute(f"PRAGMA max_page_count={pages:d}")
                try:
                    connection.execute(
                        "CREATE TABLE records (side TEXT, identity TEXT, item TEXT, payload TEXT)"
                    )
                    source_unknown = self._stage(
                        connection, source, "source", report, source_snapshot, guard
                    )
                    side = "index"
                    index_unknown = self._stage(
                        connection, index, "index", report, index_snapshot, guard
                    )
                    issues = snapshot_issues(
                        source_snapshot,
                        index_snapshot,
                        report,
                        reference,
                        self.policy.require_snapshot,
                    )
                    for code, recommendation in issues:
                        self._add(report, code, Status.INCONCLUSIVE, "audit", recommendation)
                    if not issues and "SNAPSHOT_RECORD_MISMATCH" not in report.counts:
                        assert report.audit is not None
                        report.audit.snapshot_validated = (
                            source_snapshot is not None and index_snapshot is not None
                        )
                        self._compare_staged(
                            connection, report, source_unknown, index_unknown, guard
                        )
                finally:
                    with suppress(sqlite3.Error):
                        assert report.metrics is not None
                        report.metrics.spool_bytes = (
                            connection.execute("PRAGMA page_count").fetchone()[0]
                            * connection.execute("PRAGMA page_size").fetchone()[0]
                        )
        except AdapterError as exc:
            self._add(
                report,
                exc.code,
                Status.ERROR,
                side,
                "Check adapter connectivity, permissions, mapping and timeout settings.",
            )
        except _Interrupted as exc:
            self._add(
                report,
                exc.code,
                Status.ERROR,
                "checker",
                "Repeat the complete audit after cancellation or adjust the time limit.",
            )
        except (OSError, sqlite3.Error):
            self._add(
                report,
                interrupted or "STORAGE_ERROR",
                Status.ERROR,
                "checker",
                "Repeat the audit after cancellation or adjust the time limit."
                if interrupted
                else "Check temporary disk space, configured spool limit and filesystem access.",
            )
        finally:
            assert report.metrics is not None
            report.metrics.elapsed_seconds = monotonic() - started
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
