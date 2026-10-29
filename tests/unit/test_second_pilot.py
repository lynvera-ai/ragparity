import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

path = Path("examples/second_pilot/parity.py")
spec = importlib.util.spec_from_file_location("second_parity", path)
assert spec and spec.loader
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


def hashed(text):
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def test_word_windows_preserve_source_bytes_and_overlap():
    text = " ".join(str(i) for i in range(331))
    expected = {
        "0": hashed(" ".join(str(i) for i in range(180)) + " "),
        "150": hashed(" ".join(str(i) for i in range(150, 330)) + " "),
        "300": hashed(" ".join(str(i) for i in range(300, 331))),
    }
    assert parity.word_windows(text) == expected
    assert parity.word_windows("first\n\nsecond  third\f") == {
        "0": hashed("first\n\nsecond  third\f")
    }


@pytest.fixture
def inventory():
    doc = {
        "document_id": "public-rfc",
        "source_version": "source-revision",
        "content_hash": hashed("first second"),
        "is_deleted": False,
    }
    manifest = {
        "documents": [{**doc, "expected_chunks": {"0": hashed("first"), "1": hashed("second")}}]
    }
    rows = parity.metadata(
        [
            SimpleNamespace(content=text, meta={**doc, "chunk_id": str(i)})
            for i, text in enumerate(("first", "second"))
        ]
    )
    return manifest, rows


def test_native_metadata_projection_matches_frozen_inventory(inventory):
    manifest, rows = inventory
    assert parity.compare(manifest, rows).status.value == "PASS"
    assert all("text" not in row and "embedding" not in row for row in rows)


@pytest.mark.parametrize("fault", ["missing", "hash", "version", "unexpected", "duplicate"])
def test_index_faults_cannot_pass(inventory, fault):
    manifest, rows = inventory
    if fault == "missing":
        rows.pop()
    elif fault == "hash":
        rows[0]["chunk_hash"] = hashed("corrupted")
    elif fault == "version":
        rows[0]["source_version"] = "older-revision"
    elif fault == "unexpected":
        rows.append({**rows[0], "chunk_id": "unexpected"})
    elif fault == "duplicate":
        rows.append(dict(rows[0]))
    assert parity.compare(manifest, rows).status.value != "PASS"


def test_missing_metadata_is_inconclusive(inventory):
    manifest, rows = inventory
    rows[0]["is_deleted"] = None
    assert parity.compare(manifest, rows).status.value == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "original,translated,accepted",
    [
        ("RFC 9309, ¿límite de 500 KiB?", "RFC 9309, limit of 500 KiB?", True),
        ("RFC 9309 limit 500", "RFC 9309 limit 512", False),
        ("RFC 9309 limit 500", "", False),
        ("How to quote CSV?", "How to quote CSV?", True),
        ("What is JSON?", "x" * 1501, False),
    ],
)
def test_local_translation_preserves_numbers_and_bounds(original, translated, accepted):
    assert parity.accepted_translation(original, translated) is accepted
