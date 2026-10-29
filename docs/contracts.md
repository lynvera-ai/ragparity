# Metadata and result contracts

## Records

`Record` accepts `source_id`, `document_id`, `source_version`, `content_hash`, `collection`,
`is_deleted`, and optional timezone-aware `indexed_at`. It additionally accepts `updated_at`,
`snapshot_id`, `chunk_id`, `chunk_hash` and `expected_chunks`. Unknown fields are rejected.
Identifiers, versions, and hashes must be strings; missing, null, or whitespace-only
strings represent absent evidence. `is_deleted` must be provided for a conclusive check.
An empty collection name is not an implicit default collection.

Source and default document-mode identity is `(source_id, document_id, collection)`.
Chunk-mode indexes add `chunk_id`. Duplicate identities are failures,
including duplicates in different batches. Ambiguous duplicate pairs are not compared.
Index orphans still fail when duplicate indexed rows have no authoritative identity.

Missing required metadata produces `MISSING_METADATA / INCONCLUSIVE`. When identity is
missing on either layer, absence checks against that entire layer are suppressed to avoid
misclassifying the unidentifiable records as missing or orphaned. Other verifiable
mismatches still fail. If a scan raises `AdapterError`, neither layer is compared.

## Deletion policy

| Policy | Source tombstone behavior |
| --- | --- |
| `remove` | Any indexed row for the deleted identity fails; absence passes |
| `tombstone` | Index row must exist, be deleted, and match version and hash |
| `ignore` | The source tombstone is accepted without comparing its index state |

These policies apply to source tombstones only. An index identity with no source row
is an orphan under every policy. A live source paired with an indexed tombstone fails.
Missing metadata remains inconclusive even when a deletion policy accepts the state.

## Stable result codes

| Code | Status | Meaning |
| --- | --- | --- |
| `RECORD_SYNCED` | PASS | All compared metadata agrees |
| `DELETION_CONFIRMED` | PASS | Deleted source absent from index under `remove` |
| `DELETION_IGNORED` | PASS | Source deletion accepted under `ignore` |
| `MISSING_INDEX` | FAIL | Live source has no indexed identity |
| `ORPHAN_INDEX` | FAIL | Indexed identity has no source identity |
| `VERSION_MISMATCH` | FAIL | Source and index version strings differ |
| `HASH_MISMATCH` | FAIL | Source and index hash strings differ |
| `DELETION_MISMATCH` | FAIL | Paired deletion flags differ |
| `DELETED_PRESENT` | FAIL | Removed source identity remains indexed |
| `MISSING_TOMBSTONE` | FAIL | Required index tombstone is absent |
| `DUPLICATE_ID` | FAIL | More than one record has the same identity in a layer |
| `MISSING_METADATA` | INCONCLUSIVE | Required metadata is unavailable |
| `NO_EVIDENCE` | INCONCLUSIVE | Both scans are empty |
| `ADAPTER_ERROR` | ERROR | A metadata scan did not complete |
| `STORAGE_ERROR` | ERROR | Temporary storage failed |
| `CLAIM_MATCH` | PASS | Comparable numeric claim falls within tolerance |
| `CLAIM_VALUE_MISMATCH` | FAIL | Comparable numeric claim exceeds tolerance |
| `CLAIM_NO_EVIDENCE` | INCONCLUSIVE | Expected or observed evidence is absent |
| `CLAIM_CONTEXT_MISMATCH` | INCONCLUSIVE | Source, metric, period, or unit differs |

Findings contain severity (`INFO`, `WARNING`, `ERROR`), layer, available identifiers,
structured evidence, and a recommendation. No original document body is accepted.
Reports emit schema version `2.0` (legacy `1.0` input is accepted), timestamp, input counts, comparison count,
counts by code, capped finding details, and `findings_truncated`. Comparison count is
the number of unique source identities evaluated after identity and duplicate safeguards;
it includes deletion checks. Counts by code count findings, not unique documents.

Overall precedence is `ERROR > FAIL > INCONCLUSIVE > PASS`. Details may be truncated;
counts and status are never calculated from only the retained details. Configuration
and file errors exit with code 2 and a sanitized message; they may prevent a report
from being written. Reports are evidence summaries, not signed attestations.

## Adapter configuration

`source` and `index` are required. Each accepts `kind = "memory" | "postgresql" | "pgvector"`.
Memory uses a `records` array. Database adapters require `url_env` and `table`, and accept
`schema_name` and `columns`. Mapping keys are `Record` fields, values are physical column
names. Identifiers are quoted by SQLAlchemy; arbitrary SQL strings are not accepted.
For example, a table without `indexed_at` and with an `id` column can use:

```toml
[source.columns]
source_id = "source_id"
document_id = "id"
source_version = "revision"
content_hash = "content_hash"
collection = "collection"
is_deleted = "is_deleted"
```

The database roles need schema usage and SELECT on the configured table or view.
Rows are streamed in one read-only repeatable-read transaction per adapter. The two
systems must expose equivalent audit scope. The toolkit does not infer deletion from
a filtered source or coordinate snapshots across different databases.


## Audit and operational codes added in 0.2

The `FindingCode` enum and [JSON schema](schemas/report.schema.json) enumerate all built-in
codes. Their meanings are documented in [audit semantics](audits.md):

- `SNAPSHOT_MISSING`, `SNAPSHOT_INCOMPLETE`, `SNAPSHOT_MISMATCH`,
  `SNAPSHOT_COUNT_MISMATCH`, `SNAPSHOT_RECORD_MISMATCH`: inconclusive audit evidence.
- `SYNC_PENDING`, `SYNC_EVIDENCE_MISSING`, `INVALID_TIMESTAMP`, `LAYOUT_MISMATCH`,
  `CHUNK_MANIFEST_MISSING`: inconclusive timing, layout or fragment evidence.
- `MISSING_CHUNK`, `UNEXPECTED_CHUNK`, `CHUNK_HASH_MISMATCH`, `MIXED_CHUNK_VERSIONS`:
  failures unless deferred by the explicit synchronization grace policy.
- `CHUNKS_SYNCED`: the complete declared fragment set and compared metadata agree.
- `DATABASE_TIMEOUT`, `DATABASE_CONNECTION_ERROR`, `CHECK_CANCELLED`,
  `TIME_LIMIT_EXCEEDED`: operational errors; the audit is incomplete.
- `CLAIM_PROVENANCE_MISSING`, `CLAIM_PROVENANCE_MISMATCH`: inconclusive numeric
  evidence when provenance is required.

Reports also retain audit policy, the captured reference time and optional manifests,
plus checker elapsed time and main-spool allocation. Redacted reports remove identifiers,
evidence and manifests. Counts and status still refer to the complete audit, including
findings omitted by the detail cap. See [release compatibility](releases.md).
