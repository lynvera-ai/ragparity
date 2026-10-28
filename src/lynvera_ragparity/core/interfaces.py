from collections.abc import Iterator
from typing import Protocol

from lynvera_ragparity.core.models import Record


class AdapterError(Exception):
    """An adapter cannot provide a complete metadata scan."""


class RecordReader(Protocol):
    def iter_batches(self, batch_size: int) -> Iterator[list[Record]]:
        """Yield a complete scan, or raise AdapterError; never silently skip records."""
        ...
