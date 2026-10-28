# Changelog

## 0.2.0b1

- Ground public-pilot answers in atomic retrieved facts, with explicit scope abstention,
  bounded evidence selection, raw-decision logs and a benchmark-independent question client.
- Pin the local evidence selector to `qwen3:1.7b` and refresh the application model catalog
  after downloads. Preserve earlier diagnostic failures and qualify repeated pilot results.

- Expand the public-document pilot with eight planetary excerpts, twelve supported
  questions, two abstention cases, explicit metric citations and preserved run evidence.
- Record the source review of the two original inconclusive answers without upgrading
  them to verified claims or rewriting the generated values.

- Add an isolated local pilot with pinned public PostgreSQL documentation, Open WebUI,
  local inference, independent source metadata, read-only projections and a human review form.

- Add completion manifests with scope, cutoff, row count and per-row snapshot checks.
- Add native fragment manifests, missing and unexpected fragment checks, per-fragment
  hashes, duplicate fragment detection and mixed-version findings.
- Add synchronization grace windows using authoritative change timestamps.
- Add cooperative cancellation, runtime and spool limits, database connection and query
  timeouts, and sanitized configuration field diagnostics.
- Add numeric evidence references, report redaction and atomic private report writes.
- Version the result contract as 2.0 and enumerate stable finding codes; accept legacy
  1.0 input and document migration and compatibility policies.
- Add a synthetic catalog pipeline, PostgreSQL retrieval tests, scale tooling and measured
  resource results, minimum-dependency CI and PostgreSQL 16/17/18 integration jobs.
- Add manual artifact preparation and validation without package-index publication.

Independent real-application pilots remain outstanding. This is a beta candidate.

## 0.1.0

Initial experimental MVP:

- Metadata parity checks, deletion policies, duplicate detection, and evidence-aware results.
- Batched memory, PostgreSQL, and pgvector metadata readers.
- Structured decimal numeric comparisons with explicit context and tolerances.
- TOML configuration, CLI, JSON and HTML reporting.
- Unit and PostgreSQL/pgvector integration tests, packaging, and GitHub Actions workflows.
