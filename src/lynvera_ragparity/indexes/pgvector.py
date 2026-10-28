from lynvera_ragparity.sources.postgresql import PostgreSQLSource


class PgVectorIndex(PostgreSQLSource):
    """Scan one metadata row per document in a pgvector table or projection view.

    Embedding values are neither selected nor compared. Chunked indexes should expose
    a document-level view with explicit aggregation semantics before using this adapter.
    """
