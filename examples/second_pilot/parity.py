"""Project stored fragment metadata and compare it with an independent source inventory."""

import re
from collections import Counter

from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.core import CheckPolicy, Record
from lynvera_ragparity.indexes import MemoryIndex
from lynvera_ragparity.sources import MemorySource


def word_windows(text: str) -> dict[str, str]:
    """Preserve RFC whitespace while defining 180 space-delimited units with 30 overlap."""
    from hashlib import sha256

    words = text.split(" ")
    expected = {}
    for start in range(0, len(words), 150):
        chunk = " ".join(words[start : start + 180])
        if start + 180 < len(words):
            chunk += " "
        if not chunk:
            continue
        expected[str(start)] = "sha256:" + sha256(chunk.encode()).hexdigest()
        if start + 180 >= len(words):
            break
    return expected


def metadata(documents) -> list[dict]:
    from hashlib import sha256

    return [
        {
            "source_id": "rfc-editor",
            "document_id": d.meta["document_id"],
            "source_version": d.meta["source_version"],
            "collection": "public-standards",
            "content_hash": d.meta["content_hash"],
            "is_deleted": d.meta["is_deleted"],
            "chunk_id": d.meta["chunk_id"],
            "chunk_hash": "sha256:" + sha256(d.content.encode()).hexdigest(),
        }
        for d in documents
    ]


def compare(manifest: dict, actual: list[dict]):
    source = [
        Record(
            source_id="rfc-editor",
            document_id=d["document_id"],
            source_version=d["source_version"],
            collection="public-standards",
            content_hash=d["content_hash"],
            is_deleted=d["is_deleted"],
            expected_chunks=d["expected_chunks"],
        )
        for d in manifest["documents"]
    ]
    index = [Record(**row) for row in actual]
    return ConsistencyChecker(CheckPolicy(identity_mode="chunk")).check(
        MemorySource(source), MemoryIndex(index)
    )


def accepted_translation(original: str, translated: str) -> bool:
    """Reject empty, oversized or numerically altered search queries."""
    return (
        bool(translated.strip())
        and len(translated) <= 1500
        and Counter(re.findall(r"\d+", original)) == Counter(re.findall(r"\d+", translated))
    )
