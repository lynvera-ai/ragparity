import importlib
import json
from pathlib import Path

import pytest

from lynvera_ragparity.core import Status


@pytest.fixture
def pilot(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("examples/public_pilot").resolve()))
    return importlib.import_module("evaluate")


@pytest.mark.parametrize(
    "raw,identities,status,code",
    [
        (
            '{"value":"63","unit":"bytes","source_document_id":"identifier-length","metric":"identifier-length"}',
            {"identifier-length": "abc"},
            Status.PASS,
            "CLAIM_MATCH",
        ),
        (
            '{"value":"64","unit":"bytes","source_document_id":"identifier-length","metric":"identifier-length"}',
            {"identifier-length": "abc"},
            Status.FAIL,
            "CLAIM_VALUE_MISMATCH",
        ),
        (
            '{"value":"63","unit":"bytes","source_document_id":"invented","metric":"identifier-length"}',
            {"identifier-length": "abc"},
            Status.INCONCLUSIVE,
            "CLAIM_NO_EVIDENCE",
        ),
        (
            '{"value":"63","unit":"bytes","source_document_id":"identifier-length","metric":"identifier-length"}',
            {"identifier-length": "old"},
            Status.INCONCLUSIVE,
            "CLAIM_CONTEXT_MISMATCH",
        ),
        (
            '{"value":"6,3","unit":"bytes","source_document_id":"identifier-length","metric":"identifier-length"}',
            {"identifier-length": "abc"},
            Status.INCONCLUSIVE,
            "CLAIM_NO_EVIDENCE",
        ),
        (
            '{"value":63,"unit":"bytes","source_document_id":"identifier-length","metric":"identifier-length"}',
            {"identifier-length": "abc"},
            Status.INCONCLUSIVE,
            "CLAIM_NO_EVIDENCE",
        ),
        (
            "The maximum is 63 bytes.",
            {"identifier-length": "abc"},
            Status.INCONCLUSIVE,
            "CLAIM_NO_EVIDENCE",
        ),
        (
            '{"value":null,"unit":null,"source_document_id":null,"metric":null}',
            {},
            Status.INCONCLUSIVE,
            "CLAIM_NO_EVIDENCE",
        ),
    ],
)
def test_public_pilot_requires_structured_values_and_retrieved_citations(
    pilot, raw, identities, status, code
):
    identities = {
        key: {"revision": value, "source_id": "postgresql-docs"}
        for key, value in identities.items()
    }
    question = {"id": "identifier-length", "value": "63", "unit": "bytes"}
    result = pilot.validate_answer(question, raw, identities, "PostgreSQL 17.6", "abc")
    assert result.status == status
    assert result.code == code


def test_public_source_table_parser_handles_markup_and_conditions(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("examples/public_pilot").resolve()))
    corpus = importlib.import_module("corpus")
    parser = corpus.LimitsParser()
    parser.feed("""<table><row><entry>relation size</entry><entry>32 TB</entry>
    <entry>with the default <symbol>BLCKSZ</symbol> of 8192 bytes</entry></row></table>""")
    assert parser.rows["relation size"] == [
        "relation size",
        "32 TB",
        "with the default BLCKSZ of 8192 bytes",
    ]
    rendered = corpus.render_excerpt(
        {"id": "relation-size", "item": "relation size"},
        parser.rows["relation size"],
        "Source redistribution terms",
        "a" * 40,
    )
    assert "Source redistribution terms" in rendered
    assert "8192 bytes" in rendered
    assert "PostgreSQL 17.6" in rendered


def test_downloaded_source_is_verified_before_becoming_a_reference(tmp_path, monkeypatch):
    import io

    monkeypatch.syspath_prepend(str(Path("examples/public_pilot").resolve()))
    corpus = importlib.import_module("corpus")
    config = tmp_path / "config"
    config.mkdir()
    (config / "versions.json").write_text(
        json.dumps(
            {
                "corpus_revision": "a" * 40,
                "corpus_file_sha256": {"limits.sgml": "0" * 64},
            }
        )
    )
    monkeypatch.setattr(corpus, "HERE", config)
    monkeypatch.setattr(corpus, "ROOT", tmp_path / "runtime")
    monkeypatch.setattr(corpus, "urlopen", lambda *args, **kwargs: io.BytesIO(b"tampered source"))
    with pytest.raises(ValueError, match="checksum"):
        corpus.prepare()
    assert not (tmp_path / "runtime/corpus/manifest.json").exists()


def test_installation_state_is_private_and_runtime_is_ignored(tmp_path, monkeypatch):
    import os
    import subprocess

    monkeypatch.syspath_prepend(str(Path("examples/public_pilot").resolve()))
    manager = importlib.import_module("manage")
    monkeypatch.setattr(manager, "ROOT", tmp_path)
    credentials = manager.settings()
    assert len(credentials["reader_password"]) >= 32
    if os.name == "posix":
        assert (tmp_path / "secrets.json").stat().st_mode & 0o777 == 0o600
    ignored = subprocess.run(
        ["git", "check-ignore", ".local-pilot/secrets.json"], capture_output=True
    )
    assert ignored.returncode == 0


def test_reference_set_is_unique_and_pinned():
    directory = Path("examples/public_pilot")
    versions = json.loads((directory / "versions.json").read_text())
    questions = json.loads((directory / "questions.json").read_text())
    assert len(questions) == len({item["id"] for item in questions}) == 11
    assert len(versions["corpus_revision"]) == 40
    assert "@sha256:" in versions["webui_image"]
    assert "@sha256:" in versions["postgres_image"]
    assert set(versions["model_digests"]) == {
        versions["generation_model"],
        versions["embedding_model"],
    }


def test_stop_cleans_owned_processes_when_container_daemon_is_unavailable(tmp_path, monkeypatch):
    import signal
    import subprocess
    from types import SimpleNamespace

    monkeypatch.syspath_prepend(str(Path("examples/public_pilot").resolve()))
    manager = importlib.import_module("manage")
    monkeypatch.setattr(manager, "ROOT", tmp_path)
    for name, pid in (("tunnel", 1001), ("ollama", 1002)):
        (tmp_path / f"{name}.pid").write_text(str(pid))

    def unavailable(*args):
        raise subprocess.CalledProcessError(1, ["compose", "stop"])

    monkeypatch.setattr(manager, "compose", unavailable)
    monkeypatch.setattr(
        manager.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(tmp_path), returncode=0),
    )
    signals = []
    monkeypatch.setattr(manager.os, "kill", lambda pid, sig: signals.append((pid, sig)))
    manager.stop()
    assert signals == [(1001, signal.SIGTERM), (1002, signal.SIGTERM)]
    assert not list(tmp_path.glob("*.pid"))


@pytest.mark.parametrize(
    "case,value,unit,cited,metric,field",
    [
        (
            "relation-count",
            "1.431650303",
            "1,431,650,303",
            "relation-count",
            "relation-count",
            "unit",
        ),
        ("index-columns", "1664", "columns", "result-columns", "result-columns", "metric"),
    ],
)
def test_original_inconclusive_answers_are_never_upgraded_to_verified(
    pilot, case, value, unit, cited, metric, field
):
    questions = json.loads(Path("examples/public_pilot/questions.json").read_text())
    question = next(item for item in questions if item["id"] == case)
    raw = json.dumps({"value": value, "unit": unit, "source_document_id": cited, "metric": metric})
    identities = {cited: {"source_id": "postgresql-docs", "revision": "abc"}}
    finding = pilot.validate_answer(question, raw, identities, "PostgreSQL 17.6", "abc")
    assert finding.status == Status.INCONCLUSIVE
    assert field in finding.evidence["fields"]


def test_same_planet_wrong_measurement_or_foreign_source_is_not_verified(pilot):
    question = {
        "id": "venus-rotation",
        "document_id": "nasa-venus",
        "metric": "rotation-period",
        "value": "-5832.5",
        "unit": "hours",
    }
    raw = json.dumps(
        {
            "value": "2802",
            "unit": "hours",
            "source_document_id": "nasa-venus",
            "metric": "length-of-day",
        }
    )
    retrieved = {"nasa-venus": {"revision": "abc", "source_id": "nasa-planetary"}}
    finding = pilot.validate_answer(question, raw, retrieved, "edition", "abc", "nasa-planetary")
    assert finding.status == Status.INCONCLUSIVE
    assert "metric" in finding.evidence["fields"]
    raw = json.dumps(
        {
            "value": "-5832.5",
            "unit": "hours",
            "source_document_id": "nasa-venus",
            "metric": "rotation-period",
        }
    )
    retrieved["nasa-venus"]["source_id"] = "other-source"
    finding = pilot.validate_answer(question, raw, retrieved, "edition", "abc", "nasa-planetary")
    assert finding.status == Status.INCONCLUSIVE
    assert "source_id" in finding.evidence["fields"]


def test_same_number_in_another_document_is_not_sufficient_provenance(pilot):
    question = {
        "id": "q",
        "document_id": "nasa-earth",
        "metric": "diameter",
        "value": "12756",
        "unit": "km",
    }
    raw = json.dumps(
        {"value": "12756", "unit": "km", "source_document_id": "nasa-mars", "metric": "diameter"}
    )
    finding = pilot.validate_answer(
        question,
        raw,
        {"nasa-mars": {"revision": "abc", "source_id": "nasa-planetary"}},
        "edition",
        "abc",
        "nasa-planetary",
    )
    assert finding.code == "CLAIM_PROVENANCE_MISMATCH"


def test_request_uses_retrieval_and_unit_contract_without_golden_answer_leakage(pilot):
    from grounded import eligible_facts, selection_payload

    question = {
        "id": "hidden-question-id",
        "document_id": "hidden-golden-doc",
        "metric": "hidden-metric",
        "question": "What is the diameter of Probe?",
        "unit": "km",
        "value": "987654321",
    }
    contexts = [
        {
            "document_id": name,
            "text": f"Planetary reference excerpt: Probe\nDocument ID: {name}\n"
            "Metric ID: diameter; Equatorial diameter: 4879 km.\n"
            "Metric ID: rotation-period; Rotation: 24 hours.\n",
        }
        for name in ("nasa-retrieved", "nasa-distractor")
    ]
    facts, reason = eligible_facts(question["question"], question["unit"], contexts)
    assert reason is None
    payload = selection_payload(question["question"], question["unit"], facts, "local-model")
    serialized = json.dumps(payload)
    for hidden in ("987654321", "hidden-golden-doc", "hidden-metric", "hidden-question-id"):
        assert hidden not in serialized
    assert payload["params"]["format"]["properties"]["choice"]["enum"] == [-1, 0, 1]
    assert payload["params"]["num_predict"] == 24
    assert all(fact.unit == "km" for fact in facts)


def test_only_complete_null_answer_is_a_correct_abstention(pilot):
    assert pilot.abstained('{"value":null,"unit":null,"source_document_id":null,"metric":null}')
    assert not pilot.abstained('{"value":null,"unit":"km","source_document_id":null,"metric":null}')
    assert not pilot.abstained("No evidence")


def test_planet_parser_uses_header_positions_and_preserves_negative_decimals(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("examples/public_pilot").resolve()))
    planets = importlib.import_module("planets")
    header = [
        "",
        "MERCURY",
        "VENUS",
        "EARTH",
        "MOON",
        "MARS",
        "JUPITER",
        "SATURN",
        "URANUS",
        "NEPTUNE",
    ]
    parser = planets.PlanetTable()
    parser.feed(
        "<table><tr>"
        + "".join(f"<th>{item}</th>" for item in header)
        + "</tr>"
        + "".join(
            "<tr><td>"
            + label
            + "</td>"
            + "".join(
                f"<td>{item}</td>"
                for item in ["1,000", "-5832.5", "3", "999", "5", "6", "7", "-17.2", "9"]
            )
            + "</tr>"
            for label, _, _ in planets.METRICS.values()
        )
        + "</table>"
    )
    values = parser.values()
    assert values["diameter"]["mercury"] == "1000"
    assert values["rotation-period"]["venus"] == "-5832.5"
    assert values["rotation-period"]["uranus"] == "-17.2"
    assert values["diameter"]["mars"] == "5"  # Do not shift Mars into the Moon's column.
    parser.rows[1].pop()
    with pytest.raises(ValueError, match="dimensions"):
        parser.values()


def test_nasa_revision_and_question_units_are_independent_and_pinned():
    import hashlib

    directory = Path("examples/public_pilot")
    config = json.loads((directory / "versions.json").read_text())["nasa"]
    assert (
        config["revision"]
        == hashlib.sha256(json.dumps(config["files"], sort_keys=True).encode()).hexdigest()
    )
    questions = json.loads((directory / "nasa_questions.json").read_text())
    assert len({item["id"] for item in questions}) == 14
    assert len({item["document_id"] for item in questions if item.get("supported", True)}) == 8
    assert sum(not item.get("supported", True) for item in questions) == 2


def test_evaluation_archives_errors_without_secrets_and_continues(pilot, monkeypatch, tmp_path):
    import sys

    versions = json.loads((pilot.HERE / "versions.json").read_text())
    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    (tmp_path / "uploads.json").write_text("{}")
    monkeypatch.setattr(pilot, "authenticate", lambda: "private-token")
    monkeypatch.setattr(
        pilot,
        "request",
        lambda url, **kwargs: (
            {
                "models": [
                    {"name": name, "digest": digest}
                    for name, digest in versions["model_digests"].items()
                ]
            }
            if url.endswith("/api/tags")
            else {"data": [{"id": versions["generation_model"]}]}
            if url.endswith("/api/models")
            else {"version": "local"}
        ),
    )
    evaluated = []

    def evaluate(question, *args):
        evaluated.append(question["id"])
        if question["id"] == "relation-count":
            raise RuntimeError("sensitive-password-in-exception")
        return {"question_id": question["id"], "status": "PASS", "supported": True}

    monkeypatch.setattr(pilot, "evaluate_case", evaluate)
    monkeypatch.setattr(
        sys, "argv", ["evaluate.py", "--case", "relation-count", "--case", "index-columns"]
    )
    for _ in range(2):
        with pytest.raises(SystemExit) as result:
            pilot.main()
        assert result.value.code == 2
    assert evaluated == ["relation-count", "index-columns"] * 2
    runs = list((tmp_path / "runs").iterdir())
    assert len(runs) == 2
    for run in runs:
        summary = json.loads((run / "summary.json").read_text())
        assert summary["errors"] == 1
        assert summary["supported_cases"]["PASS"] == 1
        data = (run / "answers.json").read_text()
        assert "RuntimeError" in data
        assert "sensitive-password-in-exception" not in data
        assert "private-token" not in (run / "provenance.json").read_text()


def test_cached_public_source_requires_the_same_verified_bytes(monkeypatch, tmp_path):
    import hashlib
    import io

    monkeypatch.syspath_prepend(str(Path("examples/public_pilot").resolve()))
    corpus = importlib.import_module("corpus")
    path = tmp_path / "facts.html"
    path.write_bytes(b"reviewed source")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()

    def unexpected_network(*args, **kwargs):
        pytest.fail("Verified local source must not be replaced by an upstream response")

    monkeypatch.setattr(corpus, "urlopen", unexpected_network)
    assert corpus.verified_download(path, "https://example.invalid", checksum) == b"reviewed source"
    path.write_bytes(b"corrupt cache")
    monkeypatch.setattr(corpus, "urlopen", lambda *args, **kwargs: io.BytesIO(b"changed upstream"))
    with pytest.raises(ValueError, match="checksum"):
        corpus.verified_download(path, "https://example.invalid", checksum)


def test_generation_http_error_preserves_evidence_without_response_secrets(pilot, monkeypatch):
    import io
    from urllib.error import HTTPError

    def request(url, *args, **kwargs):
        if url.endswith("/api/v1/retrieval/query/collection"):
            return {
                "documents": [
                    [
                        "Planetary reference excerpt: Mercury\nDocument ID: nasa-mercury\n"
                        "Metric ID: diameter; Equatorial diameter: 4879 km."
                    ]
                ],
                "metadatas": [[{"name": "rns-nasa-mercury--" + "a" * 64 + ".txt"}]],
            }
        raise HTTPError(
            url,
            503,
            "private-body",
            {"Authorization": "private-token"},
            io.BytesIO(b"sensitive-remote-error"),
        )

    monkeypatch.setattr(pilot, "request", request)
    question = {"id": "q", "question": "Diameter of Mercury?", "unit": "km", "value": "4879"}
    result = pilot.evaluate_case(
        question,
        "private-token",
        {"nasa-mercury": "file-id"},
        {"generation_model": "local"},
        "nasa",
    )
    assert result["status"] == "ERROR"
    assert result["http_status"] == 503
    assert result["retrieved_evidence"][0]["document_id"] == "nasa-mercury"
    assert result["generation_request"]["params"]["format"]
    serialized = json.dumps(result)
    for secret in ("private-token", "private-body", "sensitive-remote-error"):
        assert secret not in serialized
