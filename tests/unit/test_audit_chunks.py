from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.core import CheckPolicy, SnapshotEvidence, Status
from lynvera_ragparity.indexes import MemoryIndex
from lynvera_ragparity.sources import MemorySource

REFERENCE = datetime(2026, 1, 2, tzinfo=UTC)


def snapshot(count=1, **changes):
    return SnapshotEvidence.model_validate(
        {
            "snapshot_id": "run-1",
            "scope": "catalog:public",
            "as_of": REFERENCE - timedelta(hours=1),
            "completed_at": REFERENCE - timedelta(minutes=30),
            "record_count": count,
            **changes,
        }
    )


def audit(source, index, *, source_snapshot=None, index_snapshot=None, **policy):
    return ConsistencyChecker(CheckPolicy(reference_time=REFERENCE, **policy)).check(
        MemorySource(source),
        MemoryIndex(index),
        source_snapshot=source_snapshot,
        index_snapshot=index_snapshot,
    )


def test_coordinated_audit(synchronized_record):
    record = synchronized_record.model_copy(update={"snapshot_id": "run-1"})
    result = audit(
        [record],
        [record],
        source_snapshot=snapshot(),
        index_snapshot=snapshot(),
        require_snapshot=True,
    )
    assert result.status == Status.PASS
    assert result.audit.snapshot_validated


@pytest.mark.parametrize(
    "change,code",
    [
        ({"snapshot_id": "other"}, "SNAPSHOT_MISMATCH"),
        ({"scope": "other-tenant"}, "SNAPSHOT_MISMATCH"),
        ({"as_of": REFERENCE - timedelta(hours=2)}, "SNAPSHOT_MISMATCH"),
        ({"completed_at": None}, "SNAPSHOT_INCOMPLETE"),
        ({"completed_at": REFERENCE + timedelta(seconds=1)}, "SNAPSHOT_INCOMPLETE"),
        ({"record_count": 2}, "SNAPSHOT_COUNT_MISMATCH"),
    ],
)
def test_unverifiable_snapshots_never_compare(synchronized_record, change, code):
    record = synchronized_record.model_copy(update={"snapshot_id": "run-1"})
    result = audit(
        [record], [record], source_snapshot=snapshot(), index_snapshot=snapshot(**change)
    )
    assert result.status == Status.INCONCLUSIVE
    assert code in result.counts
    assert result.comparisons == 0
    assert not result.audit.snapshot_validated


@pytest.mark.parametrize("side", ["source", "index"])
def test_wrong_snapshot_row_is_not_comparable(synchronized_record, side):
    good = synchronized_record.model_copy(update={"snapshot_id": "run-1"})
    bad = good.model_copy(update={"snapshot_id": "other"})
    result = audit(
        [bad if side == "source" else good],
        [bad if side == "index" else good],
        source_snapshot=snapshot(),
        index_snapshot=snapshot(),
    )
    assert result.status == Status.INCONCLUSIVE
    assert result.counts == {"SNAPSHOT_RECORD_MISMATCH": 1}
    assert result.comparisons == 0


def test_required_and_half_supplied_manifests(synchronized_record):
    assert audit([synchronized_record], [], require_snapshot=True).counts == {"SNAPSHOT_MISSING": 1}
    record = synchronized_record.model_copy(update={"snapshot_id": "run-1"})
    assert audit([record], [], source_snapshot=snapshot()).counts == {"SNAPSHOT_MISSING": 1}


def test_snapshot_contract_rejects_invalid_completion():
    with pytest.raises(ValidationError):
        snapshot(completed_at=REFERENCE - timedelta(days=2))
    with pytest.raises(ValidationError):
        snapshot(count=-1)


@pytest.mark.parametrize(
    "age,status,code",
    [
        (0, Status.INCONCLUSIVE, "SYNC_PENDING"),
        (59, Status.INCONCLUSIVE, "SYNC_PENDING"),
        (60, Status.FAIL, "MISSING_INDEX"),
        (61, Status.FAIL, "MISSING_INDEX"),
        (-1, Status.INCONCLUSIVE, "INVALID_TIMESTAMP"),
    ],
)
def test_grace_boundaries(synchronized_record, age, status, code):
    source = synchronized_record.model_copy(
        update={"updated_at": REFERENCE - timedelta(seconds=age)}
    )
    result = audit([source], [], sync_grace_seconds=60)
    assert result.status == status
    assert code in result.counts
    assert "RECORD_SYNCED" not in result.counts


def test_grace_needs_authoritative_timestamp(synchronized_record):
    result = audit([synchronized_record], [], sync_grace_seconds=60)
    assert result.status == Status.INCONCLUSIVE
    assert result.counts == {"SYNC_EVIDENCE_MISSING": 1}
    assert result.findings[0].evidence["underlying_code"] == "MISSING_INDEX"


def test_grace_preserves_unrelated_failure(synchronized_record):
    source = synchronized_record.model_copy(update={"updated_at": REFERENCE})
    orphan = source.model_copy(update={"document_id": "orphan"})
    result = audit([source], [orphan], sync_grace_seconds=60)
    assert result.status == Status.FAIL
    assert result.counts == {"SYNC_PENDING": 1, "ORPHAN_INDEX": 1}


def chunks(record):
    source = record.model_copy(update={"expected_chunks": {"a": "hash-a", "b": "hash-b"}})
    return source, [
        record.model_copy(update={"chunk_id": name, "chunk_hash": value})
        for name, value in source.expected_chunks.items()
    ]


def test_chunked_index_does_not_treat_fragments_as_duplicate_documents(synchronized_record):
    source, index = chunks(synchronized_record)
    result = audit([source], index, identity_mode="chunk", batch_size=1)
    assert result.status == Status.PASS
    assert result.counts == {"CHUNKS_SYNCED": 1}
    assert result.comparisons == 1


@pytest.mark.parametrize(
    "change,code",
    [
        ({"chunk_hash": "wrong"}, "CHUNK_HASH_MISMATCH"),
        ({"source_version": "old"}, "VERSION_MISMATCH"),
        ({"content_hash": "wrong"}, "HASH_MISMATCH"),
        ({"is_deleted": True}, "DELETION_MISMATCH"),
        ({"chunk_id": "unexpected"}, "UNEXPECTED_CHUNK"),
    ],
)
def test_chunk_corruption(synchronized_record, change, code):
    source, index = chunks(synchronized_record)
    index[0] = index[0].model_copy(update=change)
    result = audit([source], index, identity_mode="chunk")
    assert result.status == Status.FAIL
    assert code in result.counts
    assert "CHUNKS_SYNCED" not in result.counts
    if code == "VERSION_MISMATCH":
        assert "MIXED_CHUNK_VERSIONS" in result.counts


def test_missing_and_duplicate_chunks(synchronized_record):
    source, index = chunks(synchronized_record)
    missing = audit([source], index[:1], identity_mode="chunk")
    assert missing.counts == {"MISSING_CHUNK": 1}
    assert missing.findings[0].chunk_id == "b"
    duplicate = audit([source], [*index, index[0]], identity_mode="chunk", batch_size=1)
    assert duplicate.status == Status.FAIL
    assert duplicate.counts == {"DUPLICATE_ID": 1}
    assert duplicate.findings[0].chunk_id == "a"


@pytest.mark.parametrize("field", ["chunk_id", "chunk_hash"])
def test_missing_chunk_evidence(synchronized_record, field):
    source, index = chunks(synchronized_record)
    index[0] = index[0].model_copy(update={field: None})
    result = audit([source], index, identity_mode="chunk")
    assert result.status == Status.INCONCLUSIVE
    assert "MISSING_METADATA" in result.counts
    assert "CHUNKS_SYNCED" not in result.counts
    assert "MISSING_CHUNK" not in result.counts


def test_chunk_manifest_is_required(synchronized_record):
    _, index = chunks(synchronized_record)
    result = audit([synchronized_record], index, identity_mode="chunk")
    assert result.counts == {"CHUNK_MANIFEST_MISSING": 1}


def test_explicit_empty_chunk_manifest(synchronized_record):
    source = synchronized_record.model_copy(update={"expected_chunks": {}})
    assert audit([source], [], identity_mode="chunk").counts == {"CHUNKS_SYNCED": 1}


@pytest.mark.parametrize("side", ["source", "index"])
def test_wrong_layout_is_not_passed(synchronized_record, side):
    _, index = chunks(synchronized_record)
    result = audit(
        index if side == "source" else [synchronized_record],
        index if side == "index" else [synchronized_record],
    )
    assert result.status == Status.INCONCLUSIVE
    assert "LAYOUT_MISMATCH" in result.counts


def test_deleted_document_removes_every_chunk(synchronized_record):
    source, index = chunks(synchronized_record)
    source = source.model_copy(update={"is_deleted": True})
    assert audit([source], index, identity_mode="chunk").counts == {"DELETED_PRESENT": 1}
    assert audit([source], [], identity_mode="chunk").counts == {"DELETION_CONFIRMED": 1}
    tombstones = [item.model_copy(update={"is_deleted": True}) for item in index]
    assert audit(
        [source], tombstones, identity_mode="chunk", deletion_policy="tombstone"
    ).counts == {"CHUNKS_SYNCED": 1}


def test_rows_after_cutoff_cannot_be_attested_by_copying_snapshot_id(synchronized_record):
    record = synchronized_record.model_copy(
        update={"snapshot_id": "run-1", "updated_at": REFERENCE - timedelta(minutes=10)}
    )
    result = audit([record], [record], source_snapshot=snapshot(), index_snapshot=snapshot())
    assert result.status == Status.INCONCLUSIVE
    assert result.counts == {"SNAPSHOT_RECORD_MISMATCH": 2}
    assert result.comparisons == 0


def test_batch_size_and_input_order_preserve_findings(synchronized_record):
    source, index = chunks(synchronized_record)
    index = [index[1].model_copy(update={"source_version": "old"}), index[0], index[0]]
    baseline = audit([source], index, identity_mode="chunk", batch_size=1)
    for batch_size in (2, 7, 1000):
        result = audit(
            [source], list(reversed(index)), identity_mode="chunk", batch_size=batch_size
        )
        assert result.status == baseline.status == Status.FAIL
        assert result.counts == baseline.counts
        assert [(item.code, item.chunk_id) for item in result.findings] == [
            (item.code, item.chunk_id) for item in baseline.findings
        ]
