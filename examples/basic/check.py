"""Run a framework-independent metadata check with no external services."""

from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.core import Record
from lynvera_ragparity.indexes import MemoryIndex
from lynvera_ragparity.sources import MemorySource

source_record = Record(
    source_id="catalog",
    document_id="product-1",
    source_version="2",
    content_hash="sha256:synthetic-v2",
    collection="products",
    is_deleted=False,
)
indexed_record = source_record.model_copy(update={"source_version": "1"})
result = ConsistencyChecker().check(MemorySource([source_record]), MemoryIndex([indexed_record]))
print(result.model_dump_json(indent=2))
