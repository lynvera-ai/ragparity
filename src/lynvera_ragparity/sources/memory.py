from collections.abc import Iterable, Iterator
from itertools import islice

from lynvera_ragparity.core import Record


class MemorySource:
    def __init__(self, records: Iterable[Record]) -> None:
        self.records = records

    def iter_batches(self, batch_size: int) -> Iterator[list[Record]]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        iterator = iter(self.records)
        while batch := list(islice(iterator, batch_size)):
            yield batch
