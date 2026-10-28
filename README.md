# Lynvera RAGParity

Open-source toolkit for validating data consistency across source systems, RAG indexes,
and AI-generated answers expressed as structured numeric claims.

**Trust your AI data. Verify every layer.**

Version 0.2.0b1 is a beta candidate with completed-snapshot checks, native fragment
validation, execution controls and a reproducible catalog pilot. Independent application
pilots remain outstanding. It checks explicit metadata and numeric contracts; it does
not certify free-form answers or provide semantic fact-checking.

## Why RAGParity

A retrieval index can retain deleted records, omit documents, or serve outdated versions.
RAGParity compares authoritative metadata with indexed metadata and reports the evidence
behind each result. It fits alongside an existing RAG framework without replacing it.

## Implemented features

- Missing and orphaned indexed documents, duplicate identities, version and hash mismatches.
- Required metadata checks, configurable deletion policies, and synchronization grace windows.
- Completion manifests checked against scope, cutoff, row counts and snapshot IDs.
- Native chunk identity, expected fragment hashes and mixed-version detection.
- Framework-independent readers, memory adapters, SQLAlchemy PostgreSQL reader, and a
  pgvector metadata reader that never selects embeddings.
- Batched scans with a private SQLite disk spool and capped finding details.
- Structured numeric comparisons with `Decimal`, explicit source, metric, unit, period,
  and absolute or relative tolerances.
- TOML configuration with sanitized field diagnostics, CLI exit codes, versioned JSON
  results, atomic private report writes, redaction, and self-contained HTML reports.
- Query and connection timeouts, cooperative cancellation, total duration and spool limits.
- Unit tests, PostgreSQL/pgvector integration fixtures, CI, and dependency audits.

No model API, embedding generation, subscription, or paid service is required.

## Installation

Python 3.12 or newer is required. Install from this repository; this version is not
published to PyPI.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
# For PostgreSQL and pgvector:
python -m pip install '.[postgres]'
```

The distribution is `lynvera-ragparity`; the import package is `lynvera_ragparity` and
its executable is `ragparity`.

## Quick start

```bash
ragparity --help
ragparity version
ragparity init
ragparity check --config ragparity.toml --output report.json
ragparity report --input report.json --output report.html
```

`init [PATH]` writes an annotated, synchronized memory example and refuses to overwrite
an existing file. The example returns `PASS`. Change an index version to see a mismatch.
`check --output` writes JSON; `report --format json|html` converts a saved JSON report.

| Result | Exit code | Meaning |
| --- | --- | --- |
| PASS | 0 | Evidence agrees for the configured checks |
| FAIL | 1 | At least one deterministic inconsistency |
| ERROR | 2 | Invalid configuration, adapter, storage, or output error |
| INCONCLUSIVE | 3 | Insufficient or unverifiable evidence |

Overall precedence is `ERROR`, `FAIL`, `INCONCLUSIVE`, `PASS`. An empty scan is
`INCONCLUSIVE`. Matching numeric claims do not turn an empty metadata scan into `PASS`.

## Library usage

```python
from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.core import Record
from lynvera_ragparity.indexes import MemoryIndex
from lynvera_ragparity.sources import MemorySource

record = Record(
    source_id="catalog",
    document_id="product-1",
    source_version="2",
    content_hash="sha256:synthetic-v2",
    collection="products",
    is_deleted=False,
)
stale = record.model_copy(update={"source_version": "1"})
report = ConsistencyChecker().check(MemorySource([record]), MemoryIndex([stale]))
assert report.counts["VERSION_MISMATCH"] == 1
```

See [the basic example](examples/basic/check.py) and
[numeric contracts](docs/numeric-claims.md). Applications can call `validate_claim`
independently when only numeric validation is needed.

## Configuration

Configuration uses TOML. Database URLs are read only from named environment variables.
The CLI does not load `.env`; Docker Compose does. Do not place credentials in TOML.

```toml
[policy]
batch_size = 1000
max_findings = 1000
deletion_policy = "remove"

[source]
kind = "postgresql"
url_env = "SOURCE_DATABASE_URL"
table = "source_metadata"
schema_name = "public"

[index]
kind = "pgvector"
url_env = "INDEX_DATABASE_URL"
table = "index_metadata"
schema_name = "public"
```

Use `postgresql+psycopg://` URLs and SELECT-only roles. Defaults are a 10-second
connection timeout and a 30-second database statement timeout. By default the database table
must expose the original seven metadata columns with matching names. An explicit
`[source.columns]` or `[index.columns]` mapping can map a subset of contract field names
to physical column names; omitted fields become missing evidence. `indexed_at` is
optional. See [configuration and result semantics](docs/contracts.md) and the
[PostgreSQL/pgvector example](examples/postgresql_pgvector/README.md).

New checks are opt-in for existing configurations. See [live ingestion and fragment audits](docs/audits.md).
Use `ragparity check --redact --output report.json` to omit identifiers and evidence from
saved output. Numeric evidence can require a matching source reference and revision.

The [synthetic catalog pilot](examples/catalog/README.md) demonstrates six ingestion and
answer scenarios without model APIs. [Scale measurements](docs/performance.md) document
measured resources and their limits. Report consumers should review the
[migration notes](docs/releases.md#migrating-from-01) before upgrading from 0.1.

## Architecture

The `src/lynvera_ragparity` package separates:

| Component | Responsibility |
| --- | --- |
| `core` | Typed record, reader, policy, finding, and report contracts |
| `sources`, `indexes` | Complete batched metadata scans |
| `checks` | Deterministic identity and metadata comparisons |
| `claims` | Explicit numeric evidence and tolerances |
| `config`, `cli` | Validated TOML and automation commands |
| `reports` | JSON and escaped HTML rendering |
| `integrations` | Namespace for future optional framework integrations |

Readers implement `iter_batches(batch_size)` and raise `AdapterError` on incomplete
scans. The checker stages both complete scans before comparing. SQLite indexes detect
duplicates across batches without holding all records in Python memory. Memory adapter
inputs and inline TOML records are appropriate for small datasets; database adapters
stream rows. Findings are capped, but counts and overall status include all findings.

## Development and tests

```bash
python -m pip install -e '.[dev,postgres]'
ruff check src tests examples
ruff format --check src tests examples
mypy src
pytest -m 'not integration' --cov=lynvera_ragparity --cov-report=term-missing --cov-fail-under=90
python -m build
```

Integration tests skip unless `RAGPARITY_TEST_DATABASE_URL` is set. Use the initialized
Compose fixture and reader account as described in the database example, then run
`pytest -m integration`. No Docker is needed for unit tests.

CI runs Python 3.12, 3.13, and 3.14, quality checks, coverage, package build and wheel
installation, CLI smoke tests, minimum dependency compatibility, and Compose integration jobs for PostgreSQL 16, 17 and 18. A free dependency
audit, Dependabot configuration and a manual release preparation workflow are included.
There is no PyPI publishing workflow. See [release policy](docs/releases.md).

## Compatibility and limitations

- PostgreSQL and pgvector are supported through relational metadata columns or views.
  JSON metadata must be exposed through a view; arbitrary framework schemas are not inferred.
- Sources use `(source_id, document_id, collection)`. Document mode expects one index
  row per document; chunk mode adds `chunk_id` and requires an authoritative fragment manifest.
- Versions and hashes are opaque, exact strings. Hashes are compared, not recomputed.
  Equal metadata does not prove document body or embedding correctness.
- `indexed_at` is retained when supplied and must include a timezone. Grace windows use
  the authoritative source `updated_at`; indexed timestamps alone do not prove freshness.
- Each database scan uses its own read-only repeatable-read snapshot. There is no atomic
  snapshot across systems; provide immutable projections and matching completion manifests
  for coordinated audits. Caller-supplied attestations do not establish authenticity.
- Temporary disk space scales with metadata size. Metadata is temporarily written to disk
  and deleted on normal cleanup; use an appropriately protected temporary filesystem.
- Numeric evidence is supplied by the caller, who is responsible for its provenance.
  There is no free-text extraction, currency conversion, unit conversion, or live metric query.
- Library adapter exceptions must follow the `AdapterError` protocol. Programming errors
  from custom adapters propagate rather than masquerading as successful scans.

## Contributing and security

Read [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
and [SECURITY.md](SECURITY.md). Reports include identifiers, versions, hashes, and numeric
evidence; handle them as potentially sensitive metadata. Document bodies and database
credentials are not included by the built-in adapters.

## License and maintainer

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Created and maintained by **Dr. Felipe Castillo Rendón**

**Lynvera** · [lynvera.ai](https://lynvera.ai) · felipe.castillo@lynvera.ai
