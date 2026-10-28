CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE source_documents (
    source_id text NOT NULL,
    document_id text NOT NULL,
    source_version text NOT NULL,
    content_hash text NOT NULL,
    collection text NOT NULL,
    is_deleted boolean NOT NULL,
    indexed_at timestamptz,
    PRIMARY KEY (source_id, document_id, collection)
);

CREATE TABLE indexed_documents (
    source_id text,
    document_id text,
    source_version text,
    content_hash text,
    collection text,
    is_deleted boolean,
    indexed_at timestamptz,
    embedding vector(3)
);

INSERT INTO source_documents VALUES
    ('catalog', 'synced', '2', 'sha256:synthetic-v2', 'products', false, NULL),
    ('catalog', 'stale', '2', 'sha256:synthetic-v2', 'products', false, NULL),
    ('catalog', 'missing', '1', 'sha256:synthetic-v1', 'products', false, NULL),
    ('catalog', 'deleted', '3', 'sha256:synthetic-v3', 'products', true, NULL),
    ('catalog', 'duplicate', '1', 'sha256:synthetic-v1', 'products', false, NULL);

INSERT INTO indexed_documents VALUES
    ('catalog', 'synced', '2', 'sha256:synthetic-v2', 'products', false,
     '2026-01-01 00:00:00+00', '[1,0,0]'),
    ('catalog', 'stale', '1', 'sha256:synthetic-v1', 'products', false,
     '2026-01-01 00:00:00+00', '[0,1,0]'),
    ('catalog', 'deleted', '2', 'sha256:synthetic-v2', 'products', false,
     '2026-01-01 00:00:00+00', '[0,0,1]'),
    ('catalog', 'duplicate', '1', 'sha256:synthetic-v1', 'products', false,
     '2026-01-01 00:00:00+00', '[1,1,0]'),
    ('catalog', 'duplicate', '1', 'sha256:synthetic-v1', 'products', false,
     '2026-01-01 00:00:00+00', '[1,1,0]'),
    ('catalog', 'orphan', '1', 'sha256:synthetic-v1', 'products', false,
     '2026-01-01 00:00:00+00', '[1,0,1]');

-- Local fixture role inherits the password supplied to the disposable owner account.
-- Production deployments must provision a separate, least-privilege credential.
DO $$
DECLARE owner_password text;
BEGIN
    SELECT rolpassword INTO owner_password FROM pg_authid WHERE rolname = current_user;
    EXECUTE format('CREATE ROLE ragparity_reader LOGIN PASSWORD %L', owner_password);
END
$$;
ALTER ROLE ragparity_reader SET default_transaction_read_only = on;
GRANT CONNECT ON DATABASE ragparity TO ragparity_reader;
GRANT USAGE ON SCHEMA public TO ragparity_reader;
GRANT SELECT ON source_documents, indexed_documents TO ragparity_reader;

CREATE TABLE catalog_source (
    source_id text NOT NULL,
    document_id text NOT NULL,
    source_version text NOT NULL,
    content_hash text NOT NULL,
    collection text NOT NULL,
    is_deleted boolean NOT NULL,
    indexed_at timestamptz,
    updated_at timestamptz NOT NULL,
    snapshot_id text NOT NULL,
    expected_chunks jsonb NOT NULL,
    price numeric(12, 2) NOT NULL
);
CREATE TABLE catalog_index (
    source_id text NOT NULL,
    document_id text NOT NULL,
    source_version text NOT NULL,
    content_hash text NOT NULL,
    collection text NOT NULL,
    is_deleted boolean NOT NULL,
    indexed_at timestamptz NOT NULL,
    snapshot_id text NOT NULL,
    chunk_id text NOT NULL,
    chunk_hash text NOT NULL,
    price numeric(12, 2) NOT NULL,
    embedding vector(3) NOT NULL
);
INSERT INTO catalog_source VALUES (
    'catalog', 'P100', '2', 'sha256:synthetic-document-v2', 'products', false, NULL,
    '2026-01-01 00:00:00+00', 'catalog-2026-01-01',
    '{"overview": "sha256:synthetic-overview", "price": "sha256:synthetic-price"}', 49.90
);
INSERT INTO catalog_index VALUES
    ('catalog', 'P100', '2', 'sha256:synthetic-document-v2', 'products', false,
     '2026-01-01 00:05:00+00', 'catalog-2026-01-01', 'overview', 'sha256:synthetic-overview',
     49.90, '[0,1,0]'),
    ('catalog', 'P100', '2', 'sha256:synthetic-document-v2', 'products', false,
     '2026-01-01 00:05:00+00', 'catalog-2026-01-01', 'price', 'sha256:synthetic-price',
     49.90, '[1,0,0]');
-- A volatile predicate keeps the delay when only metadata columns are selected.
CREATE VIEW slow_metadata AS SELECT source_documents.* FROM source_documents
    WHERE pg_sleep(0.02) IS NULL;
GRANT SELECT ON catalog_source, catalog_index, slow_metadata TO ragparity_reader;
