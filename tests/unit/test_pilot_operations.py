import copy
import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def operations(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("examples/public_pilot").resolve()))
    return importlib.import_module("operations")


def configuration():
    return {
        "name": "ragparity-public",
        "services": {
            "webui": {
                "environment": {"HOST": "127.0.0.1", "PORT": "8080"},
                "volumes": [
                    {"type": "volume", "source": "webui-data", "target": "/app/backend/data"}
                ],
            },
            "postgres": {
                "environment": {},
                "volumes": [
                    {
                        "type": "volume",
                        "source": "postgres-data",
                        "target": "/var/lib/postgresql/data",
                    }
                ],
            },
        },
        "volumes": {
            "webui-data": {"name": "primary-webui"},
            "postgres-data": {"name": "primary-postgres"},
        },
    }


def test_recovery_configuration_never_reuses_primary_volumes(operations):
    original = configuration()
    project = "ragparity-recovery-" + "a" * 12
    clone = operations.clone_configuration(original, project)
    assert original == configuration()
    assert clone["volumes"]["webui-data"]["name"] != original["volumes"]["webui-data"]["name"]
    for bad in ("ragparity-public", "ragparity-recovery-../primary", ""):
        with pytest.raises(ValueError):
            operations.clone_configuration(original, bad)
    bad = copy.deepcopy(clone)
    bad["volumes"]["postgres-data"] = original["volumes"]["postgres-data"]
    with pytest.raises(ValueError, match="primary"):
        operations.validate_isolation(bad, project)
    bad = copy.deepcopy(clone)
    bad["services"]["webui"]["volumes"][0] = {
        "type": "bind",
        "source": "/primary",
        "target": "/app/backend/data",
    }
    with pytest.raises(ValueError, match="dedicated"):
        operations.validate_isolation(bad, project)
    bad = copy.deepcopy(clone)
    bad["services"]["webui"]["environment"]["HOST"] = "0.0.0.0"
    with pytest.raises(ValueError, match="loopback"):
        operations.validate_isolation(bad, project)


def test_operational_fragment_manifest_precedes_and_does_not_read_index(operations):
    first, manifest = operations.fixture("Public documentation excerpt. " * 50, "A")
    second, changed = operations.fixture("Public documentation excerpt. " * 50, "B")
    assert 4096 < len(first) < 8192
    assert len(manifest) == 2 and len(changed) == 2
    assert set(manifest.values()).isdisjoint(changed.values())
    assert set(manifest) == set(changed)
    for start, checksum in manifest.items():
        block = first[int(start) :].split("\n\n")[0].strip()
        assert checksum == "sha256:" + operations.digest(block.encode())
    assert first != second


def test_original_file_ids_cannot_be_mutated(operations):
    runner = object.__new__(operations.Operations)
    runner.created_ids = {"disposable"}
    with pytest.raises(ValueError, match="created"):
        runner.own_file("original")


def test_new_evaluation_rejects_numeric_answers_for_unsupported_measurements(operations):
    evaluate = importlib.import_module("new_evaluation")
    case = {"id": "radius-en", "language": "en", "expected": "ABSTAINED"}
    content = "**100 km**"
    receipt = {
        "language": "en",
        "code_sha256": {},
        "versions": {},
        "rendered_answer": content,
        "result": {
            "status": "ANSWERED",
            "answer_origin": "evidence_extraction",
            "structured_answer": {
                "value": "100",
                "unit": "km",
                "source_document_id": "body",
                "metric": "diameter",
            },
        },
    }
    response = {"choices": [{"message": {"content": content}}]}
    assert evaluate.score(case, receipt, response, {}, {})["status"] == "FAIL"
    assert evaluate.score(case, None, response, {}, {})["status"] == "ERROR"
    receipt["result"] = {
        "status": "ABSTAINED",
        "answer_origin": "invalid_selection",
        "structured_answer": {"value": None},
    }
    assert evaluate.score(case, receipt, response, {}, {})["status"] == "FAIL"
    receipt["result"]["answer_origin"] = "policy_abstention"
    assert evaluate.score(case, receipt, response, {}, {})["status"] == "FAIL"
    receipt["result"]["structured_answer"] = {
        "value": None,
        "unit": None,
        "source_document_id": None,
        "metric": None,
    }
    assert evaluate.score(case, receipt, response, {}, {})["status"] == "PASS"
    receipt["code_sha256"] = {"runtime.py": "changed"}
    with pytest.raises(ValueError, match="changed"):
        evaluate.score(case, receipt, response, {}, {})


def test_new_question_prompts_do_not_repeat_prior_reference_questions():
    directory = Path("examples/public_pilot")
    previous = {
        q["question"]
        for name in ("questions.json", "nasa_questions.json", "questions_es.json")
        for q in json.loads((directory / name).read_text())
    }
    prompts = [
        q
        for spec in json.loads((directory / "new_questions.json").read_text())
        for q in spec["questions"].values()
    ]
    assert len(prompts) == len(set(prompts)) == 32
    assert previous.isdisjoint(prompts)
