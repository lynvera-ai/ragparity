import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from lynvera_ragparity.claims import NumericClaim
from lynvera_ragparity.core import AdapterError, CheckPolicy, Record, RecordReader, SnapshotEvidence
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
    snapshot: SnapshotEvidence | None = None
    connect_timeout_seconds: int = Field(default=10, ge=1, le=300)
    statement_timeout_ms: int = Field(default=30_000, ge=1, le=3_600_000)

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


class ReportSettings(Contract):
    redact: bool = Field(default=False, strict=True)


class Settings(Contract):
    source: AdapterConfig
    index: AdapterConfig
    policy: CheckPolicy = Field(default_factory=CheckPolicy)
    report: ReportSettings = Field(default_factory=ReportSettings)
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
    except ValidationError as exc:
        known = (
            set(AdapterConfig.model_fields) | set(Settings.model_fields) | set(Record.model_fields)
        )
        known |= set(CheckPolicy.model_fields) | set(SnapshotEvidence.model_fields)
        known |= {"expected", "observed", "claim_id", "value", "unit", "period", "metric", "redact"}
        issues = []
        for error in exc.errors(include_input=False, include_context=False, include_url=False)[:8]:
            location = ".".join(
                str(part) if isinstance(part, int) or part in known else "<field>"
                for part in error["loc"]
            )
            issues.append(f"{location or 'config'} ({error['type']})")
        raise ConfigurationError("Invalid configuration: " + "; ".join(issues)) from exc
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
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
        if parsed.drivername == "postgresql":
            parsed = parsed.set(drivername="postgresql+psycopg")
        if parsed.drivername != "postgresql+psycopg":
            raise ValueError("Use the supported psycopg driver")
        engine = create_engine(
            parsed,
            hide_parameters=True,
            connect_args={"connect_timeout": config.connect_timeout_seconds},
        )
        adapter = PgVectorIndex if config.kind == "pgvector" else PostgreSQLSource
        return adapter(
            engine,
            config.table or "",
            schema=config.schema_name,
            columns=config.columns,
            statement_timeout_ms=config.statement_timeout_ms,
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
