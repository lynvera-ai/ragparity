import importlib.util
import sys
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "second_evidence", Path("examples/second_pilot/evidence.py")
)
assert spec and spec.loader
evidence = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evidence
spec.loader.exec_module(evidence)


@pytest.fixture
def source():
    text = (
        "   1.  Table of contents\n\n"
        "1.  Introduction\n\n   This is a public fixture.\n\n"
        "2.  Rules\n\n   4.  Clients SHOULD NOT reuse the result for more than 39 hours,\n"
        "       unless the service is unreachable. See section 6.1 of RFC 9999.\n\n"
        "2.1.  Limits\n\n   The limit MUST be at least 909 units.\n"
    )
    return text


def test_citations_follow_real_headings_and_list_items_not_cross_references(source):
    rows = evidence.paragraphs("rfc7777", source, "https://example.invalid/rfc7777")
    rule = next(row for row in rows if "SHOULD NOT" in row.quote)
    assert (rule.section, rule.item) == ("2", "4")
    assert source[rule.start : rule.end] == rule.quote
    result = evidence.render([rule], "es")
    assert "sección 2, punto 4" in result["answer_prose"]
    assert "recomendación de no hacerlo; no es una prohibición absoluta" in result["answer_prose"]
    assert "6.1" not in result["answer_prose"]
    assert "MUST" not in result["answer_prose"]
    assert rule.as_dict()["norms"] == ["SHOULD NOT"]


def test_render_preserves_changed_values_and_source_conditions(source):
    changed = source.replace("909", "1729")
    rule = evidence.paragraphs("rfc7777", changed, "https://example.invalid")[-1]
    result = evidence.render([rule], "en")
    assert "1729 units" in result["answer"]
    assert "909" not in result["answer"]
    assert result["evidence"][0]["quote"] == rule.quote
    assert "requirement" in result["answer_prose"]
    assert "exception" not in result["answer_prose"]
    assert result["status"] == "ANSWERED"


def test_retrieval_must_match_source_bytes_and_named_document(source):
    rows = evidence.paragraphs("rfc7777", source, "https://example.invalid")
    paragraph = rows[-1]
    metadata = {
        "document_id": "rfc7777",
        "split_idx_start": paragraph.start,
        "chunk_id": "actual-fragment",
        "source_version": sha256(source.encode()).hexdigest(),
        "is_deleted": False,
        "content_hash": "sha256:" + sha256(source.encode()).hexdigest(),
    }
    document = SimpleNamespace(content=paragraph.quote, meta=metadata)
    found = evidence.candidates(
        [document], {"rfc7777": rows}, {"rfc7777": source}, "RFC 7777 limit?"
    )
    assert len(found) == 1
    assert found[0].chunk_ids == ("actual-fragment",)
    assert (
        evidence.candidates([document], {"rfc7777": rows}, {"rfc7777": source}, "RFC 8888 limit?")
        == []
    )
    document.content += " altered"
    with pytest.raises(ValueError, match="differs"):
        evidence.candidates([document], {"rfc7777": rows}, {"rfc7777": source}, "limit?")


def test_lowercase_modals_do_not_gain_formal_normative_status():
    row = evidence.Passage(
        "fixture", None, None, 0, 18, "One must quote it.", "hash", "https://example.invalid"
    )
    assert row.as_dict()["norms"] == []
    assert "obligación" not in evidence.render([row], "es")["answer_prose"]


def test_lists_keep_their_following_constraints_and_appendix_citations():
    text = (
        "1.  Values\n\n   The following names are allowed:\n\n"
        "      alpha\n      beta\n\n   The names MUST be lowercase.\n\n"
        "Appendix A.  Notes\n\n   Historical context.\n\n"
        "Author's Address\n\n   A public author.\n"
    )
    rows = evidence.paragraphs("rfc7777", text, "https://example.invalid")
    assert len(rows) == 3
    assert "alpha" in rows[0].quote and "MUST be lowercase" in rows[0].quote
    assert rows[1].section == "A"
    assert "appendix A" in evidence.render([rows[1]], "en")["answer_prose"]
    assert rows[2].section is None
