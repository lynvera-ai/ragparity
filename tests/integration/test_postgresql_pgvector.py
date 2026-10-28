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
