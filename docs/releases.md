# Compatibility and release policy

Version 0.2.0b1 is a beta candidate. Field validation, snapshot, chunk, failure and synthetic
pipeline tests support this status. Independent application pilots remain outstanding;
no production-readiness or general answer-verification claim is made.

## Public contracts

The supported interfaces are the documented exports of `core`, `checks`, `claims`,
`sources`, `indexes`, `config`, and `reports`, plus the five CLI commands. Private
underscore-prefixed helpers and storage layout are implementation details.

- Existing finding code meanings and CLI exit codes are retained. Ctrl-C exits 130.
- `FindingCode` enumerates supported built-in codes. Arbitrary codes are rejected.
- Writers emit report schema `2.0`. Readers also accept legacy `1.0` reports. Unknown
  schema versions, negative counts and unknown finding codes are rejected.
- The machine-readable accepted report contract is [report.schema.json](schemas/report.schema.json).
  A test checks that it matches the Python model.
- A minor beta release may change public contracts with documented migration steps.
  After 1.0, incompatible API or result-schema changes require a major release; additive
  functionality requires a minor release, and compatible fixes use patch releases.

## Compatibility matrix

CI checks Python 3.12, 3.13 and 3.14. It also tests the minimum supported runtime
versions listed in `constraints/minimum.txt`; other jobs resolve the latest versions
within declared upper bounds. PostgreSQL/pgvector integration jobs cover PostgreSQL
16, 17 and 18 with pgvector 0.8.7 and psycopg 3. Unsupported drivers are rejected.
The package is operating-system independent; database integration CI uses Linux.

The minimum runtime versions are deliberately limited to versions exercised by this
release. Audits check the resolved dependencies; an audit is not a security certification.

## Preparing a release

1. Review the source diff and dependency changes, update the changelog and keep
   `pyproject.toml` and `__version__` consistent.
2. Require green CI, minimum-dependency tests, all database jobs and dependency audit.
3. Run the catalog scenarios and repeat scale measurements when the checker changes.
4. Run the manual **Prepare release** workflow with the exact version. It validates
   metadata using Twine, builds the wheel and sdist, and retains artifacts and SHA-256
   checksums for review. It neither creates a release nor uploads to a package index.
5. Review and approve the artifacts, install the wheel outside the checkout, and create
   a signed tag or a reviewed release from the intended commit using maintainer credentials.
6. Publishing to PyPI requires a separate maintainer decision, account access and a
   reviewed publishing setup. No publishing credentials or index-upload workflow is included.

## Gates for 1.0

Before declaring stability, complete independent pilots on real application pipelines,
record the evaluated dataset sizes and ingestion conditions without disclosing private
data, and resolve material false positives or usability problems. Verify the documented
resource envelope on the intended deployment hardware. Freeze the supported contracts
and define the maintenance scope and response process. A passing synthetic example or
high coverage alone does not satisfy these gates.

## Migrating from 0.1

Old memory configurations and seven-column document metadata projections still work.
New optional columns are read only through explicit mappings. Existing document identity
is unchanged. Opt into `identity_mode = "chunk"` to use a chunked index. Report writers
emit `2.0`, including audit context, metrics and optional chunk IDs; update consumers
before upgrading. Hash and version comparison remains exact; no document bodies are read.
