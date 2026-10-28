import pytest

from lynvera_ragparity.core import Record


@pytest.fixture
def synchronized_record() -> Record:
    return Record(
        source_id="catalog",
        document_id="item-1",
        collection="products",
        source_version="2",
        content_hash="sha256:fixture-v2",
        is_deleted=False,
    )
