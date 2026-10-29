# Lynvera RAGParity

**Verify source and index consistency in your RAG pipeline.**

RAGParity compares authoritative metadata with indexed metadata and validates structured
numeric claims. Run it as a command-line tool or a Python library alongside your existing
pipeline. The core example needs no model, database, subscription or hosted service.

[Get started](docs/getting-started.md)
[Documentation](docs/README.md)
[Python API](docs/python-api.md)
[Release notes](docs/release-notes-0.2.0b1.md)

**Beta 0.2.0b1.** Python 3.12 or newer. Apache License 2.0.
The supported beta scope is the library and CLI. Chat examples remain experimental;
independent user acceptance is pending.

## What you can verify

| Check | Detects |
| --- | --- |
| Document consistency | Missing, orphaned, duplicate, stale and deleted indexed records. |
| Fragment consistency | Missing or unexpected chunks, hash mismatches and mixed versions against a source manifest. |
| Completion evidence | Missing, incomplete or inconsistent snapshot declarations and scan counts. |
| Structured numeric claims | Value mismatches against explicit source, metric, unit, period and tolerance contracts. |

Comparisons use supplied metadata and evidence. Matching metadata does not prove that
document bodies, embeddings or complete generated answers are correct.

## Quick start

Install the beta from the GitHub source. On macOS or Linux, with Python 3.12+:

```bash
git clone --branch main --single-branch https://github.com/lynvera-ai/ragparity.git
cd ragparity
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade 'pip>=26.2,<27'
python -m pip install .
ragparity init
ragparity check --output report.json
ragparity report --input report.json --output report.html
```

The included synthetic metadata agrees, so the first check returns:

```text
PASS: source=1 index=1 comparisons=1
RECORD_SYNCED: 1
```

Open `report.html` locally. It contains the audit summary and findings and loads no
external assets. To see a failure, change only the index's `source_version` to `"2"`
in `ragparity.toml` and rerun the check. It reports `VERSION_MISMATCH: 1` and exits 1.

The [installation guide](docs/getting-started.md) covers Windows, downloaded wheels,
configuration and troubleshooting. `init [PATH]` refuses to overwrite existing files.
The distribution is `lynvera-ragparity`; the import package is `lynvera_ragparity`.

## Read the result

| Status | Exit code | Meaning |
| --- | ---: | --- |
| PASS | 0 | Supplied evidence agrees under the configured rules. |
| FAIL | 1 | At least one deterministic inconsistency was found. |
| ERROR | 2 | Configuration, adapter, storage or execution prevented completion. |
| INCONCLUSIVE | 3 | Evidence is missing or unverifiable; an empty scan is inconclusive. |

Overall precedence is ERROR, FAIL, INCONCLUSIVE, PASS. Counts include all findings even
when detailed output is capped. Numeric matches cannot turn an empty metadata scan into
PASS. See the [CLI reference](docs/cli.md) and [result contracts](docs/contracts.md).

## Connect your pipeline

Use the memory readers for small fixtures, the optional PostgreSQL/pgvector readers for
metadata tables or views, or implement the documented reader contract for your system.
Database URLs come from named environment variables; credentials do not belong in TOML.
Use SELECT-only accounts. Built-in index reads do not select embeddings or document bodies.

```bash
# Run from the cloned source directory in the same environment.
python -m pip install '.[postgres]'
```

[Database integration](examples/postgresql_pgvector/README.md) provides a disposable local
fixture. [Python integration](docs/python-api.md) shows a complete version-mismatch check.
[Fragment audits](docs/audits.md) describe authoritative manifests and snapshot evidence.
[Numeric contracts](docs/numeric-claims.md) define value, context and provenance checks.

## Examples and validation

| Example | Purpose | Status |
| --- | --- | --- |
| [Basic check](examples/basic/check.py) | Compare two metadata records without external services. | Deterministic example. |
| [Product catalog](examples/catalog/README.md) | Exercise ingestion, fragment and numeric-contract scenarios. | Synthetic demonstration. |
| [PostgreSQL/pgvector](examples/postgresql_pgvector/README.md) | Audit database metadata with a SELECT-only role. | Disposable integration fixture. |
| [Open WebUI](examples/public_pilot/README.md) | Exercise local retrieval and document update/recovery flows. | Experimental, platform-specific setup. |
| [Haystack](examples/second_pilot/README.md) | Retrieve from complete public RFCs with multiple fragments. | Experimental; fresh evaluation passed 22/46. |

Local beta preparation passed 303 unit tests with 95.79% core coverage and seven database
integration tests. Wheel and source installation were checked in clean macOS ARM64
Python 3.12 environments. Other clean-install platforms and independent acceptance remain
pending. Read the [validation record](docs/beta-validation.md) for conditions and limits.
The [Haystack report](examples/second_pilot/FRESH_REVIEW.md) preserves all 24 failures.

## Scope and limitations

Versions and hashes are compared as exact strings; the core does not recompute document
hashes. Fragment checks require an authoritative manifest. Independent database scans do
not establish an atomic snapshot across systems. Caller-supplied evidence is checked for
consistency, not authenticated. Arbitrary framework schemas are not inferred.

Numeric evidence must be supplied by the caller. There is no free-text fact extraction,
unit/currency conversion or live metric query. Temporary disk use grows with metadata
volume; consult [measured resource use](docs/performance.md) before large scans.
Custom readers must raise `AdapterError` on incomplete scans.

## Development and releases

[Contributing](CONTRIBUTING.md) describes local development. The
[documentation index](docs/README.md) links public contracts, architecture and examples.
Maintainers can [prepare distribution files locally](docs/beta-release.md) and review
[compatibility and migration policy](docs/releases.md). Report writers emit schema 2.0;
readers also accept schema 1.0.

No release, tag or package-index upload is performed by the local build script.
[External beta review](docs/beta-feedback.md) remains pending until other people provide
actual installation and application results.

## Security and license

Reports may contain sensitive identifiers and evidence. Keep them private or use
`--redact` before sharing. Read [SECURITY.md](SECURITY.md),
[the code of conduct](CODE_OF_CONDUCT.md), [LICENSE](LICENSE) and [NOTICE](NOTICE).

Created and maintained by **Dr. Felipe Castillo Rendón**, Lynvera.
[lynvera.ai](https://lynvera.ai)
felipe.castillo@lynvera.ai
