CREATE TABLE IF NOT EXISTS pilot_sources (
    source_id text NOT NULL,
    document_id text PRIMARY KEY,
    source_version text NOT NULL,
    content_hash text NOT NULL,
    collection text NOT NULL,
    is_deleted boolean NOT NULL DEFAULT false,
    expected_chunks jsonb NOT NULL
);
CREATE OR REPLACE VIEW pilot_index_metadata AS
SELECT
    'postgresql-docs'::text AS source_id,
    substring(vmetadata->>'name' FROM '^rpg-(.+)--[a-f0-9]{40}[.]txt$') AS document_id,
    substring(vmetadata->>'name' FROM '--([a-f0-9]{40})[.]txt$') AS source_version,
    'sha256:' || (vmetadata->>'hash') AS content_hash,
    'postgresql-17.6'::text AS collection,
    false AS is_deleted,
    (vmetadata->>'start_index') AS chunk_id,
    'sha256:' || encode(digest(text, 'sha256'), 'hex') AS chunk_hash
FROM document_chunk
WHERE vmetadata->>'name' LIKE 'rpg-%'
  AND collection_name = 'file-' || (vmetadata->>'file_id');
GRANT CONNECT ON DATABASE pilot TO pilot_reader;
GRANT USAGE ON SCHEMA public TO pilot_reader;
GRANT SELECT ON pilot_sources, pilot_index_metadata TO pilot_reader;
ALTER ROLE pilot_reader SET default_transaction_read_only = on;
