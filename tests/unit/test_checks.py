from collections.abc import Iterator

import pytest

from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.core import AdapterError, CheckPolicy, Record, Status
from lynvera_ragparity.indexes import MemoryIndex
from lynvera_ragparity.sources import MemorySource


def run(source: list[Record], index: list[Record], **policy: object):
    return ConsistencyChecker(CheckPolicy.model_validate(policy)).check(
        MemorySource(source), MemoryIndex(index)
    )


def test_synchronized(synchronized_record):
    result = run([synchronized_record], [synchronized_record])
    assert result.status == Status.PASS
    assert result.counts == {"RECORD_SYNCED": 1}
    assert result.comparisons == 1


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("source_version", "1", "VERSION_MISMATCH"),
        ("content_hash", "other", "HASH_MISMATCH"),
        ("is_deleted", True, "DELETION_MISMATCH"),
    ],
)
def test_mismatched_metadata(synchronized_record, field, value, code):
    result = run([synchronized_record], [synchronized_record.model_copy(update={field: value})])
    assert result.status == Status.FAIL
    assert result.counts == {code: 1}
    assert result.findings[0].evidence["actual"] == value


def test_missing_and_orphan(synchronized_record):
    assert run([synchronized_record], []).counts == {"MISSING_INDEX": 1}
    assert run([], [synchronized_record]).counts == {"ORPHAN_INDEX": 1}


@pytest.mark.parametrize(
    ("policy", "present", "deleted", "code", "status"),
    [
        ("remove", True, True, "DELETED_PRESENT", Status.FAIL),
        ("remove", False, True, "DELETION_CONFIRMED", Status.PASS),
        ("tombstone", False, True, "MISSING_TOMBSTONE", Status.FAIL),
        ("tombstone", True, True, "RECORD_SYNCED", Status.PASS),
        ("tombstone", True, False, "DELETION_MISMATCH", Status.FAIL),
        ("ignore", True, False, "DELETION_IGNORED", Status.PASS),
        ("ignore", False, False, "DELETION_IGNORED", Status.PASS),
    ],
)
def test_deletion_policies(synchronized_record, policy, present, deleted, code, status):
    source = synchronized_record.model_copy(update={"is_deleted": True})
    index = source.model_copy(update={"is_deleted": deleted})
    result = run([source], [index] if present else [], deletion_policy=policy)
    assert result.status == status
    assert result.counts == {code: 1}


@pytest.mark.parametrize("side", ["source", "index"])
def test_duplicates_across_batches(synchronized_record, side):
    records = [synchronized_record, synchronized_record]
    result = run(
        records if side == "source" else [synchronized_record],
        records if side == "index" else [synchronized_record],
        batch_size=1,
    )
    assert result.status == Status.FAIL
    assert result.counts == {"DUPLICATE_ID": 1}
    assert result.comparisons == 0
    assert result.findings[0].source == side
    assert result.findings[0].evidence == {"count": 2}


@pytest.mark.parametrize("field", ["source_version", "content_hash", "is_deleted"])
def test_incomplete_metadata_is_not_pass(synchronized_record, field):
    incomplete = synchronized_record.model_copy(update={field: None})
    result = run([incomplete], [incomplete])
    assert result.status == Status.INCONCLUSIVE
    assert result.counts == {"MISSING_METADATA": 2}


@pytest.mark.parametrize("side", ["source", "index"])
def test_unknown_identity_prevents_false_absence(synchronized_record, side):
    incomplete = synchronized_record.model_copy(update={"document_id": None})
    result = run(
        [incomplete] if side == "source" else [synchronized_record],
        [incomplete] if side == "index" else [synchronized_record],
    )
    assert result.status == Status.INCONCLUSIVE
    assert result.counts == {"MISSING_METADATA": 1}


def test_identity_is_scoped_by_source_and_collection(synchronized_record):
    records = [
        synchronized_record,
        synchronized_record.model_copy(update={"source_id": "other"}),
        synchronized_record.model_copy(update={"collection": "other"}),
    ]
    result = run(records, records)
    assert result.status == Status.PASS
    assert result.counts == {"RECORD_SYNCED": 3}


def test_empty_scan_is_inconclusive():
    assert run([], []).status == Status.INCONCLUSIVE
    assert run([], []).counts == {"NO_EVIDENCE": 1}


class BrokenReader:
    def iter_batches(self, batch_size: int) -> Iterator[list[Record]]:
        raise AdapterError("password=not-for-reports")
        yield []


@pytest.mark.parametrize("side", ["source", "index"])
def test_connection_error_never_implies_missing_records(synchronized_record, side):
    reader = MemorySource([synchronized_record])
    result = ConsistencyChecker().check(
        BrokenReader() if side == "source" else reader,
        BrokenReader() if side == "index" else reader,
    )
    assert result.status == Status.ERROR
    assert result.counts == {"ADAPTER_ERROR": 1}
    assert result.findings[0].source == side
    assert "password" not in result.model_dump_json()


def test_batching_and_bounded_findings(synchronized_record):
    class Batches:
        def __init__(self):
            self.requested = []

        def iter_batches(self, batch_size):
            self.requested.append(batch_size)
            for start in range(0, 1001, batch_size):
                yield [
                    synchronized_record.model_copy(update={"document_id": str(i)})
                    for i in range(start, min(start + batch_size, 1001))
                ]

    source, index = Batches(), Batches()
    result = ConsistencyChecker(CheckPolicy(batch_size=37, max_findings=3)).check(source, index)
    assert source.requested == index.requested == [37]
    assert result.source_records == result.index_records == result.comparisons == 1001
    assert result.counts == {"RECORD_SYNCED": 1001}
    assert len(result.findings) == 3
    assert result.findings_truncated
    assert result.status == Status.PASS


def test_partial_scan_does_not_compare(synchronized_record):
    class PartialReader:
        def iter_batches(self, batch_size):
            yield [synchronized_record]
            raise AdapterError("Interrupted scan")

    result = ConsistencyChecker().check(MemorySource([synchronized_record]), PartialReader())
    assert result.status == Status.ERROR
    assert result.comparisons == 0
    assert "MISSING_INDEX" not in result.counts


def test_spool_error_is_an_error(monkeypatch):
    def denied(**kwargs):
        raise OSError("No disk space")

    monkeypatch.setattr("lynvera_ragparity.checks.engine.TemporaryDirectory", denied)
    result = run([], [])
    assert result.status == Status.ERROR
    assert result.counts == {"STORAGE_ERROR": 1}


def test_truncated_details_preserve_failure(synchronized_record):
    stale = synchronized_record.model_copy(update={"source_version": "old", "content_hash": "old"})
    result = run([synchronized_record], [stale], max_findings=1)
    assert result.status == Status.FAIL
    assert result.counts == {"VERSION_MISMATCH": 1, "HASH_MISMATCH": 1}
    assert result.findings_truncated
