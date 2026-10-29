import copy
import importlib.util
from hashlib import sha256
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "second_scoring", Path("examples/second_pilot/scoring.py")
)
assert spec and spec.loader
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)


@pytest.fixture
def payload():
    source = "Clients SHOULD NOT cache results beyond 39 hours unless unavailable."
    row = {
        "document_id": "rfc7777",
        "section": "2.4",
        "item": None,
        "start": 0,
        "end": len(source),
        "quote": source,
        "source_sha256": sha256(source.encode()).hexdigest(),
        "chunk_ids": ["chunk"],
        "norms": ["SHOULD NOT"],
    }
    prose = "Document evidence. Original quotation in English:\n\nSource: RFC 7777, section 2.4."
    response = {
        "status": "ANSWERED",
        "answer": prose.replace("\n\n", "\n\n" + source + "\n\n"),
        "answer_prose": prose,
        "evidence": [row],
        "candidates": [copy.deepcopy(row)],
    }
    return (
        source,
        response,
        {"section": "2.4", "norm": "SHOULD NOT"},
        {"document": "rfc7777", "evidence_pattern": r"SHOULD NOT cache"},
    )


def test_scoring_checks_the_actual_quoted_evidence(payload):
    source, response, contract, case = payload
    assert scoring.validate_evidence(response, {"rfc7777": source}, contract, case)


@pytest.mark.parametrize(
    "fault",
    [
        "extra_prose",
        "invented_section",
        "changed_quote",
        "missing_quote",
        "different_hash",
        "no_support",
    ],
)
def test_old_failure_modes_cannot_pass_the_stronger_screen(payload, fault):
    source, response, contract, case = payload
    if fault == "extra_prose":
        response["answer"] += "\n\nAn unrelated rule is an exception."
    elif fault == "invented_section":
        response["evidence"][0]["section"] = "6.1"
        response["candidates"][0]["section"] = "6.1"
    elif fault == "changed_quote":
        response["evidence"][0]["quote"] = source.replace("SHOULD NOT", "MUST NOT")
    elif fault == "missing_quote":
        response["answer"] = response["answer_prose"]
    elif fault == "different_hash":
        response["evidence"][0]["source_sha256"] = "different"
    else:
        response["evidence"] = []
    assert not scoring.validate_evidence(response, {"rfc7777": source}, contract, case)
