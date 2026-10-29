from collections.abc import Iterator

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Engine,
    MetaData,
    String,
    Table,
    select,
    text,
)
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from lynvera_ragparity.core import AdapterError, FindingCode, Record
from lynvera_ragparity.core.models import DATABASE_DEFAULT_FIELDS


class PostgreSQLSource:
    """Read mapped metadata columns using a streamed, read-only transaction."""

    def __init__(
        self,
        engine: Engine,
        table: str,
        *,
        schema: str | None = None,
        columns: dict[str, str] | None = None,
        statement_timeout_ms: int = 30_000,
    ) -> None:
        if statement_timeout_ms < 1:
            raise ValueError("statement_timeout_ms must be positive")
        self.statement_timeout_ms = statement_timeout_ms
        self.engine = engine
        self.table = table
        self.schema = schema
        self.columns = (
            columns if columns is not None else {key: key for key in DATABASE_DEFAULT_FIELDS}
        )
        if not self.columns or set(self.columns) - Record.model_fields.keys():
            raise ValueError("Column mappings must use Record field names")

    def iter_batches(self, batch_size: int) -> Iterator[list[Record]]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        try:
            with self.engine.connect() as connection, connection.begin():
                if connection.dialect.name == "postgresql":
                    connection.exec_driver_sql(
                        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                    )
                    connection.execute(
                        text("SELECT set_config('statement_timeout', :timeout, true)"),
                        {"timeout": str(self.statement_timeout_ms)},
                    )
                metadata_columns = {
                    column: Column(
                        column,
                        Boolean()
                        if field == "is_deleted"
                        else DateTime(timezone=True)
                        if field in ("indexed_at", "updated_at")
                        else JSON()
                        if field == "expected_chunks"
                        else String(),
                    )
                    for field, column in self.columns.items()
                }
                table = Table(
                    self.table, MetaData(), *metadata_columns.values(), schema=self.schema
                )
                statement = select(
                    *(table.c[column].label(field) for field, column in self.columns.items())
                )
                result = connection.execution_options(yield_per=batch_size).execute(statement)
                with result:
                    for rows in result.mappings().partitions(batch_size):
                        yield [Record.model_validate(dict(row)) for row in rows]
        except (SQLAlchemyError, KeyError, ValueError) as exc:
            # Driver messages can contain credentials, SQL parameters or record content.
            code = FindingCode.ADAPTER_ERROR
            if getattr(getattr(exc, "orig", None), "sqlstate", None) == "57014":
                code = FindingCode.DATABASE_TIMEOUT
            elif isinstance(exc, OperationalError):
                code = FindingCode.DATABASE_CONNECTION_ERROR
            raise AdapterError(
                "Database metadata scan failed; check connection and mapping.",
                code=code,
            ) from exc
