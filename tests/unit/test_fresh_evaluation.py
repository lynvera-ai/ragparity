import copy
import importlib.util
from hashlib import sha256
from pathlib import Path

import pytest


@pytest.fixture
def fresh(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("examples/second_pilot").resolve()))
    spec = importlib.util.spec_from_file_location(
        "fresh_offline", Path("examples/second_pilot/fresh_scoring.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_novelty_rejects_punctuation_or_accent_only_reuse(fresh):
    case = {"questions": {"es": "¿Qué regla aplica?", "en": "Which rule applies?"}}
    with pytest.raises(ValueError, match="reuses"):
        fresh.verify_novelty([case], ["que regla aplica"])
    assert fresh.verify_novelty([case], ["What time is it?"])["normalized_overlap"] == 0
    with pytest.raises(ValueError, match="duplicates"):
        fresh.verify_novelty([case, case], [])


def test_old_question_collection_does_not_treat_references_as_questions(fresh):
    data = {
        "cases": [
            {"question": "First?"},
            {"questions": {"es": "Segunda?", "en": "Second?"}, "rationale": "Not a question"},
        ]
    }
    assert fresh.collect_questions(data) == ["First?", "Segunda?", "Second?"]


@pytest.fixture
def answer():
    source = "A parser MAY accept extensions.\n\nA generator MUST conform."
    first = "A parser MAY accept extensions."
    second = "A generator MUST conform."
    rows = []
    for section, quote, start in [("9", first, 0), ("10", second, source.index(second))]:
        rows.append(
            {
                "document_id": "fixture",
                "section": section,
                "item": None,
                "start": start,
                "end": start + len(quote),
                "quote": quote,
                "source_sha256": sha256(source.encode()).hexdigest(),
                "chunk_ids": ["chunk"],
                "norms": ["MAY"] if section == "9" else ["MUST"],
            }
        )
    response = {
        "status": "ANSWERED",
        "answer": first,
        "answer_prose": "",
        "evidence": [rows[0]],
        "candidates": rows,
        "sources": [{"document_id": "fixture", "chunk_id": "chunk"}],
        "requested_language": "en",
        "answer_language": "en",
        "generation": {"finish_reason": "stop"},
    }
    case = {
        "id": "contrast",
        "category": "multiple-passages",
        "expected": "ANSWERED",
        "document": "fixture",
        "answer_patterns": ["parser"],
        "evidence_pattern": "parser",
        "checks": {"allowed_sections": ["9", "10"], "required_sections": ["9", "10"]},
    }
    return source, response, case, rows


def test_faithful_partial_answer_does_not_pass_complete_answer_check(fresh, answer):
    source, response, case, rows = answer
    result = fresh.score(case, "en", response, {"fixture": source})
    assert result["quotation_integrity"]
    assert result["status"] == "FAIL"
    assert result["reason"] == "INCOMPLETE_MULTI_PASSAGE"
    response["evidence"] = rows
    response["answer"] = "\n\n".join(row["quote"] for row in rows)
    assert fresh.score(case, "en", response, {"fixture": source})["status"] == "PASS"


def test_related_quote_is_not_an_answer_to_an_unsupported_question(fresh, answer):
    source, response, case, _ = answer
    case = copy.deepcopy(case)
    case.update(expected="ABSTAINED", document=None, checks={}, evidence_pattern=None)
    result = fresh.score(case, "en", response, {"fixture": source})
    assert result["quotation_integrity"]
    assert result["reason"] == "UNSUPPORTED_ANSWER"


def test_changed_source_quote_is_detected_independently_of_disposition(fresh, answer):
    source, response, case, _ = answer
    response["evidence"][0]["quote"] = "Invented text."
    result = fresh.score(case, "en", response, {"fixture": source})
    assert not result["quotation_integrity"]
    assert result["reason"] == "QUOTATION_INTEGRITY"
