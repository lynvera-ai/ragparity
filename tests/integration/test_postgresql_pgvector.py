import os

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError

from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.core import AdapterError, CheckPolicy, Status
from lynvera_ragparity.indexes import PgVectorIndex
from lynvera_ragparity.sources import PostgreSQLSource

pytestmark = pytest.mark.integration


@pytest.fixture
def engine():
    url = os.environ.get("RAGPARITY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RAGPARITY_TEST_DATABASE_URL to the initialized Compose reader URL")
    engine = create_engine(url, hide_parameters=True)
    yield engine
    engine.dispose()


def test_real_pgvector_metadata_scan(engine):
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        assert connection.scalar(text("SELECT embedding::text FROM indexed_documents LIMIT 1"))
    result = ConsistencyChecker(CheckPolicy(batch_size=2)).check(
        PostgreSQLSource(engine, "source_documents"), PgVectorIndex(engine, "indexed_documents")
    )
    assert result.status == Status.FAIL
    assert result.source_records == 5
    assert result.index_records == 6
    assert result.counts == {
        "DUPLICATE_ID": 1,
        "RECORD_SYNCED": 1,
        "VERSION_MISMATCH": 1,
        "HASH_MISMATCH": 1,
        "MISSING_INDEX": 1,
        "DELETED_PRESENT": 1,
        "ORPHAN_INDEX": 1,
    }


def test_postgresql_reader_is_read_only(engine):
    with engine.connect() as connection:
        assert connection.scalar(text("SHOW default_transaction_read_only")) == "on"
        with pytest.raises(DBAPIError):
            connection.execute(text("DELETE FROM source_documents WHERE false"))


def test_postgresql_stream_uses_read_only_repeatable_snapshot(engine):
    observed = []

    def inspect_transaction(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("SET TRANSACTION"):
            observed.append(
                (
                    connection.scalar(text("SHOW transaction_isolation")),
                    connection.scalar(text("SHOW transaction_read_only")),
                )
            )

    event.listen(engine, "after_cursor_execute", inspect_transaction)
    reader = PostgreSQLSource(engine, "source_documents")
    iterator = reader.iter_batches(2)
    try:
        assert len(next(iterator)) == 2
        assert observed == [("repeatable read", "on")]
        assert sum(len(batch) for batch in iterator) == 3
    finally:
        iterator.close()
        event.remove(engine, "after_cursor_execute", inspect_transaction)


def test_database_failure_is_sanitized(engine):
    with pytest.raises(AdapterError, match="Database metadata scan failed"):
        list(PgVectorIndex(engine, "table_that_does_not_exist").iter_batches(1))


def test_query_timeout_closes_connection_and_reports_error(engine):
    reader = PostgreSQLSource(engine, "slow_metadata", statement_timeout_ms=1)
    result = ConsistencyChecker().check(reader, PgVectorIndex(engine, "indexed_documents"))
    assert result.status == Status.ERROR
    assert result.counts == {"DATABASE_TIMEOUT": 1}
    assert result.comparisons == 0
    assert engine.pool.checkedout() == 0


def test_catalog_retrieval_chunk_audit_and_authoritative_price(engine):
    from lynvera_ragparity.claims import (
        EvidenceReference,
        NumericClaim,
        NumericEvidence,
        validate_claim,
    )
    from lynvera_ragparity.core import SnapshotEvidence
    from lynvera_ragparity.core.models import DATABASE_DEFAULT_FIELDS

    base = {name: name for name in DATABASE_DEFAULT_FIELDS}
    source = PostgreSQLSource(
        engine,
        "catalog_source",
        columns={
            **base,
            "updated_at": "updated_at",
            "snapshot_id": "snapshot_id",
            "expected_chunks": "expected_chunks",
        },
    )
    index = PgVectorIndex(
        engine,
        "catalog_index",
        columns={
            **base,
            "snapshot_id": "snapshot_id",
            "chunk_id": "chunk_id",
            "chunk_hash": "chunk_hash",
        },
    )
    manifest = SnapshotEvidence(
        snapshot_id="catalog-2026-01-01",
        scope="catalog:products",
        as_of="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:05:00Z",
        record_count=1,
    )
    report = ConsistencyChecker(CheckPolicy(identity_mode="chunk", require_snapshot=True)).check(
        source,
        index,
        source_snapshot=manifest,
        index_snapshot=manifest.model_copy(update={"record_count": 2}),
    )
    with engine.connect() as connection:
        expected_price = connection.scalar(
            text("SELECT price FROM catalog_source WHERE document_id=:id"), {"id": "P100"}
        )
        answer = (
            connection.execute(
                text(
                    "SELECT price, source_version, chunk_id FROM catalog_index "
                    "WHERE document_id=:id ORDER BY embedding <=> CAST(:query AS vector) LIMIT 1"
                ),
                {"id": "P100", "query": "[1,0,0]"},
            )
            .mappings()
            .one()
        )
    assert answer["chunk_id"] == "price"
    reference = EvidenceReference(
        reference_id="catalog:P100:price", revision="2", retrieved_at="2026-01-01T00:05:00Z"
    )
    expected = NumericEvidence(
        value=expected_price,
        unit="USD",
        period="2026-01-01",
        source_id="catalog",
        metric="P100.price",
        provenance=reference,
    )
    observed = expected.model_copy(
        update={
            "value": answer["price"],
            "provenance": reference.model_copy(update={"revision": answer["source_version"]}),
        }
    )
    report.add(
        validate_claim(
            NumericClaim(
                claim_id="P100-price", expected=expected, observed=observed, require_provenance=True
            )
        )
    )
    assert report.status == Status.PASS
    assert report.audit.snapshot_validated
    assert report.counts == {"CHUNKS_SYNCED": 1, "CLAIM_MATCH": 1}


def test_connection_loss_mid_scan_never_reports_missing_documents(engine):
    from lynvera_ragparity.indexes import MemoryIndex

    backend = []

    def capture_backend(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT source_documents."):
            backend.append(connection.scalar(text("SELECT pg_backend_pid()")))

    event.listen(engine, "after_cursor_execute", capture_backend)
    reader = PostgreSQLSource(engine, "source_documents")

    class InterruptedSource:
        def iter_batches(self, batch_size):
            iterator = reader.iter_batches(1)
            try:
                yield next(iterator)
                with engine.connect() as terminator:
                    assert terminator.scalar(
                        text("SELECT pg_terminate_backend(:pid)"), {"pid": backend[0]}
                    )
                yield from iterator
            finally:
                iterator.close()

    try:
        report = ConsistencyChecker(CheckPolicy(batch_size=1)).check(
            InterruptedSource(), MemoryIndex([])
        )
        assert report.status == Status.ERROR
        assert report.counts == {"DATABASE_CONNECTION_ERROR": 1}
        assert report.comparisons == 0
        assert engine.pool.checkedout() == 0
    finally:
        event.remove(engine, "after_cursor_execute", capture_backend)
