# PostgreSQL and pgvector example

The disposable fixture uses PostgreSQL 17 with pgvector, synthetic vectors, and
reproducible metadata inconsistencies. It requires Docker Compose and the `postgres`
extra. It binds the database only to `127.0.0.1:55432` by default.

From the repository root, in a shell with the package installed:

```bash
export RAGPARITY_DB_PASSWORD="$(python -c 'import secrets; print(secrets.token_hex(24))')"
docker compose up -d --wait
export RAGPARITY_DATABASE_URL="postgresql+psycopg://ragparity_reader:${RAGPARITY_DB_PASSWORD}@127.0.0.1:55432/ragparity"
ragparity check --config examples/postgresql_pgvector/ragparity.toml --output report.json
```

The check intentionally exits 1. It reports one synchronized record, a stale version
and hash, a missing record, a deleted record still indexed, a duplicate identity, and
an orphan. The vector column exists but is not selected or compared.

```bash
export RAGPARITY_TEST_DATABASE_URL="$RAGPARITY_DATABASE_URL"
pytest -m integration
ragparity report --input report.json --output report.html
docker compose down --volumes
```

The fixture owner initializes the extension and tables. Checks and integration tests
use `ragparity_reader`, which has SELECT privileges and read-only transactions. The
local reader shares the randomly supplied owner password to keep bootstrap reproducible;
use separate credentials and provision roles independently in a real deployment.
Passwords never appear in SQL fixture files. The service has no persistent named volume;
removing its container discards fixture data. Set `RAGPARITY_DB_PORT` and adjust URLs if
55432 is occupied. Always set the test URL to this disposable fixture.
