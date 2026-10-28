from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from sqlalchemy import Boolean, Column, MetaData, String, Table, create_engine

from lynvera_ragparity.core import AdapterError, Record
from lynvera_ragparity.sources import MemorySource, PostgreSQLSource


def test_memory_accepts_generator_and_batches(synchronized_record):
    adapter = MemorySource(synchronized_record for _ in range(5))
    assert [len(batch) for batch in adapter.iter_batches(2)] == [2, 2, 1]
    with pytest.raises(ValueError):
        list(adapter.iter_batches(0))


def test_mapped_sql_scan_selects_only_metadata(synchronized_record):
    engine = create_engine("sqlite://")
    metadata = MetaData()
    table = Table(
        "documents",
        metadata,
        Column("external_id", String),
        Column("source_id", String),
        Column("collection", String),
        Column("source_version", String),
        Column("content_hash", String),
        Column("is_deleted", Boolean),
        Column("sensitive_content", String),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        row = synchronized_record.model_dump(exclude={"document_id", "indexed_at"})
        connection.execute(
            table.insert(),
            [
                {**row, "external_id": str(i), "sensitive_content": "must-not-be-selected"}
                for i in range(5)
            ],
        )
    columns = {key: key for key in row}
    columns["document_id"] = "external_id"
    adapter = PostgreSQLSource(engine, "documents", columns=columns)
    batches = list(adapter.iter_batches(2))
    assert [len(batch) for batch in batches] == [2, 2, 1]
    assert "sensitive" not in batches[0][0].model_dump_json()
    with pytest.raises(ValueError):
        list(adapter.iter_batches(0))
    with pytest.raises(AdapterError, match="Database metadata scan failed"):
        list(PostgreSQLSource(engine, "documents; DROP TABLE documents").iter_batches(1))
    with pytest.raises(AdapterError):
        list(
            PostgreSQLSource(engine, "documents", columns={"source_id": "missing"}).iter_batches(1)
        )
    engine.dispose()


def test_invalid_mapping():
    with pytest.raises(ValueError):
        PostgreSQLSource(Mock(), "records", columns={"document_body": "body"})
    with pytest.raises(ValueError):
        PostgreSQLSource(Mock(), "records", columns={})


def test_invalid_record_types_and_blank_metadata():
    assert Record(document_id=" ").document_id is None
    with pytest.raises(ValidationError):
        Record.model_validate({"document_id": 123})
    with pytest.raises(ValidationError):
        Record(indexed_at="2026-10-28T10:00:00")
    assert Record(indexed_at="2026-10-28T10:00:00Z").indexed_at is not None


@pytest.mark.parametrize("value", [0, 1, "false", "true", "yes"])
def test_deletion_flag_requires_explicit_boolean(value):
    with pytest.raises(ValidationError):
        Record.model_validate({"is_deleted": value})
