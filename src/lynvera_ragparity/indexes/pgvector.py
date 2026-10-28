from lynvera_ragparity.sources.postgresql import PostgreSQLSource


class PgVectorIndex(PostgreSQLSource):
    """Read mapped document or fragment metadata from a pgvector table or view.

    Embedding values are neither selected nor compared. The checker policy selects
    document or chunk identity; fragment contracts remain explicit caller evidence.
    """
