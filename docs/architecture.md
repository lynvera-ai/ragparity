# Architecture

RAGParity sits beside the ingestion and retrieval pipeline. It reads metadata and
explicit numeric evidence; it does not create embeddings, query a language model or
replace the application framework.

## Audit flow

| Stage | Behavior |
| --- | --- |
| Configure | Validate TOML or construct typed reader and policy objects. |
| Scan source | Read the complete authoritative metadata scope in batches. |
| Scan index | Read the complete indexed metadata scope in batches. |
| Stage | Store records in a private SQLite spool and detect duplicate identities across batches. |
| Validate evidence | Check required fields, layout, timestamps and supplied completion manifests. |
| Compare | Evaluate document or fragment identities, versions, hashes and deletion policy. |
| Validate claims | Compare supplied structured numeric values under explicit context and tolerances. |
| Report | Retain complete counts and overall status, cap detailed findings and optionally redact output. |

The CLI applies numeric claims to the metadata report. Library users can call the
numeric validator independently. Failed metadata scans prevent staged comparisons;
an empty scan does not become PASS because a numeric value matches.

The checker closes iterators and removes its spool on normal cleanup. Cancellation,
query timeouts and optional total-duration/spool limits produce incomplete audit
errors rather than a successful result. Abrupt process termination can leave temporary
files; protect the temporary filesystem as described in [SECURITY.md](../SECURITY.md).

## Package layout

| Module | Responsibility |
| --- | --- |
| `core` | Typed records, readers, policies, findings and report contracts. |
| `sources`, `indexes` | Complete batched metadata readers. |
| `checks` | Deterministic document, snapshot and fragment comparisons. |
| `claims` | Structured numeric evidence and Decimal tolerance checks. |
| `config`, `cli` | TOML validation, reader construction, commands and exit codes. |
| `reports` | Redaction, escaped HTML, versioned JSON and private atomic file writes. |
| `integrations` | Reserved namespace for future optional framework integrations. |

The optional pilots live under `examples`, outside the installed library wheel.
Their translation, retrieval and answer-selection behavior is not part of the
deterministic checker contract.

## Evidence boundaries

Each database reader uses its own read-only repeatable-read transaction. There is no
atomic transaction across independent source and index systems. Provide immutable
projections and matching completion manifests when coordinated evidence is required.
Caller-supplied attestations are checked for consistency, not authenticated.

Memory readers and inline TOML are appropriate for small fixtures; database readers
stream rows. Disk use grows with metadata volume even when memory use is bounded.
[Resource measurements](performance.md) record observed runs rather than a throughput
or capacity guarantee.

Hashes and versions are supplied strings. Equal metadata does not establish document
body or embedding correctness. Numeric provenance must be resolved by the caller.
Read [the contracts](contracts.md) and [audit semantics](audits.md) for exact decisions.

[Back to documentation](README.md).
