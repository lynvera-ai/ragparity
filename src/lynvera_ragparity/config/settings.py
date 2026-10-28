import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from lynvera_ragparity.claims import NumericClaim
from lynvera_ragparity.core import AdapterError, CheckPolicy, Record, RecordReader
from lynvera_ragparity.core.models import Contract
from lynvera_ragparity.indexes import MemoryIndex, PgVectorIndex
from lynvera_ragparity.sources import MemorySource, PostgreSQLSource


class ConfigurationError(Exception):
    """Invalid or inaccessible configuration; messages must not include input secrets."""


class AdapterConfig(Contract):
    kind: Literal["memory", "postgresql", "pgvector"] = "memory"
    records: list[Record] = Field(default_factory=list)
    url_env: str | None = None
    table: str | None = None
    schema_name: str | None = None
    columns: dict[str, str] | None = None

    @model_validator(mode="after")
    def database_fields(self) -> "AdapterConfig":
        if self.kind != "memory":
            if not self.url_env or not self.table or not self.table.strip():
                raise ValueError("Database adapters require url_env and table")
            if self.records:
                raise ValueError("Database adapters cannot contain inline records")
        elif any(
            value is not None
            for value in (self.url_env, self.table, self.schema_name, self.columns)
        ):
            raise ValueError("Memory adapters do not accept database settings")
        if self.columns is not None and (
            not self.columns
            or set(self.columns) - Record.model_fields.keys()
            or any(not column for column in self.columns.values())
        ):
            raise ValueError("Invalid metadata column mapping")
        return self


class Settings(Contract):
    source: AdapterConfig
    index: AdapterConfig
    policy: CheckPolicy = Field(default_factory=CheckPolicy)
    claims: list[NumericClaim] = Field(default_factory=list)


DEFAULT_CONFIG = """# Lynvera RAGParity: metadata only; no document content or credentials.
# Identity is (source_id, document_id, collection).
[policy]
batch_size = 1000
max_findings = 1000
deletion_policy = "remove" # remove, tombstone, or ignore

[source]
kind = "memory"
[[source.records]]
source_id = "catalog"
document_id = "product-1"
source_version = "1"
content_hash = "sha256:synthetic-example"
collection = "products"
is_deleted = false

[index]
kind = "memory"
[[index.records]]
source_id = "catalog"
document_id = "product-1"
source_version = "1"
content_hash = "sha256:synthetic-example"
collection = "products"
is_deleted = false
# indexed_at is optional and must include a timezone if supplied.
"""


def load_settings(path: Path) -> Settings:
    try:
        with path.open("rb") as stream:
            return Settings.model_validate(tomllib.load(stream))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValidationError) as exc:
        raise ConfigurationError(
            "Invalid configuration; check TOML syntax and documented fields."
        ) from exc


def create_reader(config: AdapterConfig, *, index: bool = False) -> RecordReader:
    if config.kind == "memory":
        return MemoryIndex(config.records) if index else MemorySource(config.records)
    url = os.environ.get(config.url_env or "")
    if not url:
        raise ConfigurationError("A database URL environment variable is missing.")
    engine = None
    try:
        parsed = make_url(url)
        if parsed.get_backend_name() != "postgresql":
            raise ValueError("PostgreSQL URL required")
        engine = create_engine(parsed, hide_parameters=True)
        adapter = PgVectorIndex if config.kind == "pgvector" else PostgreSQLSource
        return adapter(
            engine, config.table or "", schema=config.schema_name, columns=config.columns
        )
    except (ValueError, ImportError, SQLAlchemyError) as exc:
        if engine is not None:
            engine.dispose()
        raise ConfigurationError("Invalid PostgreSQL URL or missing PostgreSQL driver.") from exc


def close_reader(reader: RecordReader) -> None:
    if isinstance(reader, PostgreSQLSource):
        try:
            reader.engine.dispose()
        except Exception as exc:
            raise AdapterError("Could not close database resources.") from exc
