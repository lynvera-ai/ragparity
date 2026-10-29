# Auditing live ingestion

## Completed snapshots

Set `policy.require_snapshot = true` and provide `source.snapshot` and `index.snapshot`.
Each manifest contains `snapshot_id`, `scope`, `as_of`, `completed_at`, and `record_count`.
Both must refer to the same ID, scope and cutoff. Counts refer to physical rows and may
therefore differ between document sources and chunked indexes.

```toml
[policy]
require_snapshot = true

[source.snapshot]
snapshot_id = "catalog-2026-01-01"
scope = "catalog:products"
as_of = 2026-01-01T00:00:00Z
completed_at = 2026-01-01T00:05:00Z
record_count = 1

[index.snapshot]
snapshot_id = "catalog-2026-01-01"
scope = "catalog:products"
as_of = 2026-01-01T00:00:00Z
completed_at = 2026-01-01T00:05:00Z
record_count = 2
```

Every row must expose the matching `snapshot_id`. If `updated_at` is present, it must
not exceed the snapshot cutoff. Missing or incomplete manifests, unequal scopes or
cutoffs, wrong counts and rows from a different snapshot produce `INCONCLUSIVE` and
suppress all parity comparisons. Empty scans remain inconclusive even with manifests.

These are caller-supplied completion attestations. RAGParity validates their internal
consistency, not their authenticity. The application must publish immutable tables,
views or exports for the declared scope, keep them fixed for both scans, and resolve
manifests from an authoritative control plane. Copying a run ID onto mutable live tables
does not create a consistent distributed snapshot. `audit.snapshot_validated` means
these declared evidence checks passed; it is not a cryptographic provenance guarantee.

With no manifests and `require_snapshot = false` (the compatibility default), metadata
comparisons run without coordination, and `snapshot_validated` is false. Independent
repeatable-read transactions provide consistency within each scan only.

## Synchronization grace window

Set `sync_grace_seconds` to defer actionable ingestion mismatches while a source change
is recent. `updated_at` must be the authoritative source change or deletion timestamp.
`reference_time` optionally makes an audit replayable; otherwise one UTC time is captured
at its start. Within the window the result is `SYNC_PENDING / INCONCLUSIVE`, with the
original code recorded as `underlying_code`. At the exact boundary the original failure
applies. Missing change timestamps give `SYNC_EVIDENCE_MISSING`; future timestamps give
`INVALID_TIMESTAMP`, both inconclusive. A grace window never converts a mismatch to PASS.
The maximum supported window is one year.

Duplicates and orphans remain failures. Hard deletions without source tombstones cannot
supply an authoritative deletion time, so orphan removal is not deferred. Use tombstones
and completed snapshots when auditing deletion propagation.

## Document fragments

Set `identity_mode = "chunk"`. Sources still yield one row per document, with an explicit
`expected_chunks` mapping from fragment ID to hash. Index rows repeat the document's
`source_version` and document `content_hash`, and provide `chunk_id` and `chunk_hash`.
A PostgreSQL source can expose the mapping as JSONB through an explicit column mapping.

The checker detects missing, unexpected, duplicated and corrupted fragments, mixed
versions, and document metadata mismatches. Missing manifests or metadata are inconclusive.
An explicit empty mapping attests that zero fragments are expected. Manifests allow at
most 10,000 fragments per document; larger documents need a deliberate partitioning scheme.
Index rows are streamed; unexpected chunk IDs are not accumulated in an unbounded set.
Deletion `remove` requires every fragment to be absent. `tombstone` requires all expected
fragments to remain as matching tombstones. Chunk manifests and hashes must come from
an authoritative ingestion contract; they are never inferred from the index being audited.

## Execution and privacy

`max_duration_seconds` is a cooperative total limit, checked between scan batches and
comparisons and during SQLite operations. Blocking custom readers cannot be forcibly
interrupted; database reads additionally use connection and statement timeouts. Database
configuration defaults are `connect_timeout_seconds = 10` and `statement_timeout_ms = 30000`.
Timeouts and broken connections return ERROR. Whole audits must be rerun after failure;
there are no automatic retries against potentially different snapshots.

Library callers can pass `cancel=lambda: cancelled` to `check`. Cancellation closes active
generators, rolls back open database transactions and removes the private spool directory.
Programming errors propagate with cleanup. CLI Ctrl-C exits 130. A forcibly killed process
may leave temporary files; use a protected temporary filesystem and external cleanup.

`temporary_directory` chooses the spool parent. `max_spool_bytes` bounds the main SQLite
database, including its indexes; temporary sorting files and journal overhead are outside
that bound. `metrics.spool_bytes` measures main database allocation, not total peak disk.
`metrics.elapsed_seconds` covers the metadata check; additional numeric checks and rendering
are outside it. Detailed findings are capped while counts and status remain complete.

`check --redact`, `[report] redact = true`, and `report --redact` remove identifiers,
evidence, numeric values and snapshot manifests from saved outputs. The original result
in memory is unchanged. Reports are written atomically with private file permissions on
POSIX systems. Status, counts and policy context survive redaction. Protect unredacted
reports and any source-controlled configuration containing inline metadata.
