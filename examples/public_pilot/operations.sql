-- Disposable public copies only; the original pilot source/index projections are untouched.
CREATE TABLE IF NOT EXISTS pilot_operation_sources (
    source_id text NOT NULL,
    document_id text PRIMARY KEY,
    source_version text NOT NULL,
    content_hash text NOT NULL,
    collection text NOT NULL,
    is_deleted boolean NOT NULL DEFAULT false,
    expected_chunks jsonb NOT NULL
);
CREATE OR REPLACE VIEW pilot_operation_index AS
SELECT
    'public-document-operations'::text AS source_id,
    substring(vmetadata->>'name' FROM '^rpo-operations-([a-f0-9]{12})[.]txt$') AS document_id,
    vmetadata->>'hash' AS source_version,
    'sha256:' || (vmetadata->>'hash') AS content_hash,
    'operations-test'::text AS collection,
    false AS is_deleted,
    vmetadata->>'start_index' AS chunk_id,
    'sha256:' || encode(digest(text, 'sha256'), 'hex') AS chunk_hash
FROM document_chunk
WHERE vmetadata->>'name' ~ '^rpo-operations-[a-f0-9]{12}[.]txt$'
  AND collection_name = 'file-' || (vmetadata->>'file_id');
GRANT SELECT ON pilot_operation_sources, pilot_operation_index TO pilot_reader;
