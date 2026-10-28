from collections.abc import Iterator

from sqlalchemy import Boolean, Column, DateTime, Engine, MetaData, String, Table, select
from sqlalchemy.exc import SQLAlchemyError

from lynvera_ragparity.core import AdapterError, Record


class PostgreSQLSource:
    """Read mapped metadata columns using a streamed, read-only transaction."""

    def __init__(
        self,
        engine: Engine,
        table: str,
        *,
        schema: str | None = None,
        columns: dict[str, str] | None = None,
    ) -> None:
        self.engine = engine
        self.table = table
        self.schema = schema
        self.columns = columns if columns is not None else {key: key for key in Record.model_fields}
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
                metadata_columns = {
                    column: Column(
                        column,
                        Boolean()
                        if field == "is_deleted"
                        else DateTime(timezone=True)
                        if field == "indexed_at"
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
            raise AdapterError(
                "Database metadata scan failed; check connection and mapping."
            ) from exc
