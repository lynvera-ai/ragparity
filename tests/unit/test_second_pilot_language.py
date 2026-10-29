import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "second_language", Path("examples/second_pilot/language_tools.py")
)
assert spec and spec.loader
language = importlib.util.module_from_spec(spec)
spec.loader.exec_module(language)


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Según RFC 8259, ¿qué codificación debe usar JSON?", "es"),
        ("Como se escapa una comilla en CSV?", "es"),
        ("According to RFC 9309, what is the parsing limit?", "en"),
    ],
)
def test_request_language(question, expected):
    assert language.request_language(question) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("According to RFC 8259, the encoding must be UTF-8.", "en"),
        ("Según RFC 8259, la codificación debe ser UTF-8.", "es"),
        ("UTF-8", "neutral"),
        ("The documents contain insufficient evidence.", "en"),
        ("Los documentos no contienen evidencia suficiente.", "es"),
    ],
)
def test_language_screen_catches_obvious_mismatches(text, expected):
    assert language.prose_language(text) == expected
