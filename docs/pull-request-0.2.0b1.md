# Original beta review notes

This description was prepared for the initial beta integration from
`feat/second-local-rag-pilot` into `main`, when the base contained only the initial
repository files. The maintainer merged [PR #1](https://github.com/lynvera-ai/ragparity/pull/1)
on October 29, 2026. The draft below is retained as review context for that original
scope. Subsequent changes must be reviewed against the updated `main`.

## Proposed title

Add RAGParity 0.2.0b1 metadata and numeric validation toolkit

## Proposed description

RAG indexes can retain outdated or deleted records, omit documents or contain
inconsistent fragments. This adds a local library and command-line tool that compare
authoritative metadata with index metadata and report explicit evidence. Structured
numeric checks compare values only when their source, metric, unit and period agree.

The beta includes memory and optional PostgreSQL/pgvector readers, completion and
fragment manifests, bounded scans, execution limits, redaction, and versioned JSON
and local HTML reports. Source packages, installation instructions, release notes
and a clean-install verification tool are included. No model or hosted service is
needed for the core example.

Open WebUI and Haystack examples are experimental and have separate setup requirements.
The varied Haystack evaluation remains 22/46, including 24 preserved failures.
This release does not certify complete model answers or production readiness.

### Validation

- Local macOS ARM64, Python 3.12.9: 303 unit tests, 95.79% core coverage.
- Seven PostgreSQL 17/pgvector integration tests passed with a SELECT-only account
  in a disposable local container; temporary resources were removed.
- Lint, formatting and core static types passed.
- Wheel and source installation passed in separate clean environments outside the
  checkout. CLI status codes, numeric contracts and JSON/HTML output were exercised.
- Source rebuild produced an identical wheel within the same build environment.
- The final beta candidate dependency audit found no known vulnerabilities after
  updating the clean environment's installer. Details are in `docs/beta-validation.md`.

Remote workflows are skipped for the local-only preparation commits. Historical CI
does not constitute a run on the current commit. Windows/Linux clean installation
and independent user acceptance remain pending. Rebuild and verify distribution
files from the final approved commit before publishing.

### Compatibility and scope

The package version is 0.2.0b1. Report writers emit schema 2.0; readers also accept
schema 1.0. Public beta contracts can change with documented migration steps.
No tag, GitHub Release or package-index upload is included in this pull request.

## Suggested review order

1. `docs/contracts.md`, `docs/audits.md`, core models and checker semantics.
2. Database readers, execution limits, redaction and report rendering.
3. Unit/integration tests, dependency bounds and existing workflow changes.
4. Packaging allowlist, `tools/prepare_beta.py`, installation and validation records.
5. Experimental example setup, retained evaluation failures and scope limitations.

The pre-merge cleanup normalizes line endings in two blank review forms without
changing their parsed rows. Existing workflow checks now include the distribution
tool, and wheel smoke installation uses the same installer floor as the beta guide.
Workflow triggers and permissions are unchanged; no hosted job was started.

The maintainer still owns PR creation, review, merging and publication. After merging,
follow `docs/beta-release.md` on the intended commit and obtain independent feedback
using `docs/beta-feedback.md`.
