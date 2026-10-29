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
    CASE WHEN vmetadata->>'name' LIKE 'rpg-%' THEN 'postgresql-docs'
         ELSE 'nasa-planetary' END AS source_id,
    substring(vmetadata->>'name' FROM '^r(?:pg|ns)-(.+)--(?:[a-f0-9]{40}|[a-f0-9]{64})[.]txt$') AS document_id,
    substring(vmetadata->>'name' FROM '--([a-f0-9]+)[.]txt$') AS source_version,
    'sha256:' || (vmetadata->>'hash') AS content_hash,
    CASE WHEN vmetadata->>'name' LIKE 'rpg-%' THEN 'postgresql-17.6'
         ELSE 'nasa-planets-2025-03-18' END AS collection,
    false AS is_deleted,
    (vmetadata->>'start_index') AS chunk_id,
    'sha256:' || encode(digest(text, 'sha256'), 'hex') AS chunk_hash
FROM document_chunk
WHERE (vmetadata->>'name' ~ '^rpg-.+--[a-f0-9]{40}[.]txt$'
    OR vmetadata->>'name' ~ '^rns-nasa-.+--[a-f0-9]{64}[.]txt$')
  AND collection_name = 'file-' || (vmetadata->>'file_id');
GRANT CONNECT ON DATABASE pilot TO pilot_reader;
GRANT USAGE ON SCHEMA public TO pilot_reader;
GRANT SELECT ON pilot_sources, pilot_index_metadata TO pilot_reader;
ALTER ROLE pilot_reader SET default_transaction_read_only = on;
