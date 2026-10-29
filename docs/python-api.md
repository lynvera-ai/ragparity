# Python API

Install the package using [Getting started](getting-started.md). Import from
`lynvera_ragparity`. The examples below use invented metadata and require no external
service, model or database.

## Compare metadata

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
result = ConsistencyChecker().check(MemorySource([record]), MemoryIndex([stale]))
assert result.status.value == "FAIL"
assert result.counts["VERSION_MISMATCH"] == 1
```

Document identity is `(source_id, document_id, collection)`. Versions and hashes are
opaque strings compared exactly. A hash string in an example does not attest to real
document content. Missing evidence produces INCONCLUSIVE rather than PASS.

For numeric evidence, use `NumericClaim`, `NumericEvidence` and `validate_claim` from
`lynvera_ragparity.claims`. The [numeric guide](numeric-claims.md) provides a complete
example with Decimal values, context, tolerances and optional provenance requirements.

## Configure the checker

Pass a `CheckPolicy` to `ConsistencyChecker` to set batch size, finding limits, deletion
policy, snapshot requirements, chunk identity or execution limits. Supply matching
`SnapshotEvidence` objects through `source_snapshot` and `index_snapshot` when checking
declared completed snapshots. Use the [audit guide](audits.md) for complete examples;
the checker does not coordinate snapshots across separate systems.

Finding details can be capped while counts and status retain all observed results.
Inspect `findings_truncated`, `counts` and the overall status together.

## Connect a custom reader

A reader implements `RecordReader.iter_batches(batch_size)` and yields lists of
`Record` values for a complete scope. Use the same identity and scope on both sides.
Raise `AdapterError` if the scan cannot complete; never silently omit failed rows.
The core consumes both scans before comparing staged records.

```python
from collections.abc import Iterator

from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.core import AdapterError, Record
from lynvera_ragparity.indexes import MemoryIndex

class InterruptedSource:
    def iter_batches(self, batch_size: int) -> Iterator[list[Record]]:
        yield []
        raise AdapterError("Source scan did not complete")

result = ConsistencyChecker().check(InterruptedSource(), MemoryIndex([]))
assert result.status.value == "ERROR"
assert result.counts["ADAPTER_ERROR"] == 1
assert result.comparisons == 0
```

The example deliberately fails to show the adapter contract. Real readers should
sanitize their messages and clean up resources when an iterator closes. Programming
errors that do not follow the `AdapterError` contract propagate to the caller.
The package does not infer arbitrary framework schemas.

## Reports and database readers

Use `write_report` from `lynvera_ragparity.reports` to write JSON or HTML and optionally
redact identifiers and evidence. See [report contracts](contracts.md) and
[security guidance](../SECURITY.md) before sharing output.

`PostgreSQLSource` and `PgVectorIndex` accept a SQLAlchemy engine, table and optional
metadata mapping. They stream metadata only with read-only repeatable-read transactions.
Close engines owned by your application. The [database example](../examples/postgresql_pgvector/README.md)
provides a disposable fixture; the CLI can construct readers from TOML instead.

The [public compatibility policy](releases.md#public-contracts) defines supported exports.
[Back to documentation](README.md).
