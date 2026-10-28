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
            '{"value":"63","unit":"bytes","source_document_id":"identifier-length"}',
            {"identifier-length": "abc"},
            Status.PASS,
            "CLAIM_MATCH",
        ),
        (
            '{"value":"64","unit":"bytes","source_document_id":"identifier-length"}',
            {"identifier-length": "abc"},
            Status.FAIL,
            "CLAIM_VALUE_MISMATCH",
        ),
        (
            '{"value":"63","unit":"bytes","source_document_id":"invented"}',
            {"identifier-length": "abc"},
            Status.INCONCLUSIVE,
            "CLAIM_NO_EVIDENCE",
        ),
        (
            '{"value":"63","unit":"bytes","source_document_id":"identifier-length"}',
            {"identifier-length": "old"},
            Status.INCONCLUSIVE,
            "CLAIM_CONTEXT_MISMATCH",
        ),
        (
            '{"value":"6,3","unit":"bytes","source_document_id":"identifier-length"}',
            {"identifier-length": "abc"},
            Status.INCONCLUSIVE,
            "CLAIM_NO_EVIDENCE",
        ),
        (
            '{"value":63,"unit":"bytes","source_document_id":"identifier-length"}',
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
            '{"value":null,"unit":null,"source_document_id":null}',
            {},
            Status.INCONCLUSIVE,
            "CLAIM_NO_EVIDENCE",
        ),
    ],
)
def test_public_pilot_requires_structured_values_and_retrieved_citations(
    pilot, raw, identities, status, code
):
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
