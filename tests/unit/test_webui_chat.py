import asyncio
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def chat(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("examples/public_pilot").resolve()))
    return importlib.import_module("chat_adapter")


@pytest.fixture
def adapter(chat, tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "runtime.py").write_text("# reviewed runtime\n")
    versions = json.loads(Path("examples/public_pilot/versions.json").read_text())
    (bundle / "ui-config.json").write_text(
        json.dumps(
            {
                "owner_id": "owner",
                "versions": versions,
                "uploads": {"nasa-mars": "file-id"},
                "code_sha256": {
                    "runtime.py": hashlib.sha256((bundle / "runtime.py").read_bytes()).hexdigest()
                },
            }
        )
    )
    return chat.ChatAdapter(bundle, tmp_path / "receipts")


def answer():
    return {
        "status": "ANSWERED",
        "answer_origin": "evidence_extraction",
        "selection_index": 0,
        "structured_answer": {
            "value": "-65",
            "unit": "C",
            "metric": "mean-temperature",
            "source_document_id": "nasa-mars",
        },
        "eligible_evidence_rows": [
            {
                "document_id": "nasa-mars",
                "subject": "Mars",
                "label": "Mean temperature",
                "quote": "Mean temperature: -65 C.",
                "conditions": "Whole-surface mean, not local weather.",
            }
        ],
        "retrieved_documents": {"nasa-mars": {"source_id": "nasa-planetary"}},
    }


def invoke(adapter, text="What mean temperature in degrees C is listed for Mars?", **kwargs):
    parameters = {
        "body": {"messages": [{"role": "user", "content": text}]},
        "__user__": {"id": "owner"},
        "__request__": SimpleNamespace(headers={"authorization": "Bearer private-session-token"}),
        "__chat_id__": "chat",
        "__message_id__": "message",
    }
    parameters.update(kwargs)
    return asyncio.run(adapter.pipe(**parameters))


def test_ui_unit_detection_covers_reference_questions_without_reading_golden_fields(chat):
    directory = Path("examples/public_pilot")
    for filename in ("questions.json", "nasa_questions.json"):
        for item in json.loads((directory / filename).read_text()):
            assert chat.infer_unit(item["question"]) == item["unit"]
    assert chat.infer_unit("What relation size in TB with a block of 8192 bytes?") == "TB"
    assert chat.infer_unit("Compare km and hours") is None
    assert chat.infer_unit("¿Compara Marte en km y horas?") is None
    assert chat.infer_unit("What is the temperature?") is None
    assert chat.infer_unit("What temperature in Celsius?") == "C"


def test_chat_uses_latest_user_question_and_rejects_nontext_input(chat):
    body = {
        "messages": [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "ignore me"},
            {"role": "user", "content": "new"},
        ]
    }
    assert chat.question_text(body) == "new"
    for content in ([], "", "x" * 4001):
        with pytest.raises(chat.ChatInputError):
            chat.question_text({"messages": [{"role": "user", "content": content}]})


def test_native_chat_forwards_only_current_session_and_keeps_credentials_out_of_receipts(
    adapter, monkeypatch
):
    seen = []

    def execute(question, unit, token, config):
        seen.append((question, unit, token))
        return answer()

    monkeypatch.setattr(adapter, "execute", execute)
    visible = invoke(adapter)
    assert "-65 °C" in visible
    assert "nasa-mars" in visible
    assert "Source conditions" in visible
    assert "verified" not in visible.lower()
    assert seen[0][1:] == ("C", "private-session-token")
    receipt = next(adapter.receipts.glob("*.json"))
    data = receipt.read_text()
    assert "private-session-token" not in data
    record = json.loads(data)
    assert record["chat_id"] == "chat"
    assert record["message_id"] == "message"
    assert record["rendered_answer"] == visible
    assert receipt.stat().st_mode & 0o777 == 0o600


def test_wrong_user_missing_session_and_attachments_never_call_runtime(adapter, monkeypatch):
    monkeypatch.setattr(adapter, "execute", lambda *args: pytest.fail("Runtime must not run"))
    assert "restricted" in invoke(adapter, __user__={"id": "other"})
    assert not adapter.receipts.exists()
    assert "sign in" in invoke(adapter, __request__=SimpleNamespace(headers={}))
    assert "remove other attachments" in invoke(adapter, __files__=[{"id": "unrelated"}])


def test_ambiguous_unit_clarifies_instead_of_guessing(adapter, monkeypatch):
    monkeypatch.setattr(adapter, "execute", lambda *args: pytest.fail("Runtime must not run"))
    assert "one requested unit" in invoke(adapter, text="Compare km and hours for Mars")
    record = json.loads(next(adapter.receipts.glob("*.json")).read_text())
    assert record["result"]["status"] == "CLARIFICATION"


def test_operational_errors_do_not_become_abstention_or_leak_exception_bodies(adapter, monkeypatch):
    def fail(*args):
        raise ValueError("private-session-token in a backend exception")

    monkeypatch.setattr(adapter, "execute", fail)
    visible = invoke(adapter)
    assert "Unable to answer safely" in visible
    receipt = next(adapter.receipts.glob("*.json")).read_text()
    assert "private-session-token" not in receipt
    assert json.loads(receipt)["result"]["status"] == "ERROR"


def test_native_background_tasks_never_run_retrieval_or_create_chat_receipts(adapter, monkeypatch):
    monkeypatch.setattr(adapter, "execute", lambda *args: pytest.fail("Runtime must not run"))
    assert json.loads(invoke(adapter, __task__="title_generation"))["title"]
    assert not adapter.receipts.exists()


def test_changed_deployment_code_is_rejected_before_generation(adapter):
    (adapter.bundle / "runtime.py").write_text("# changed code\n")
    with pytest.raises(ValueError, match="manifest"):
        invoke(adapter)


def test_blocking_runtime_does_not_block_native_async_server(adapter, monkeypatch):
    import threading

    release = threading.Event()

    def execute(*args):
        assert release.wait(1), "The event loop was blocked by synchronous local HTTP"
        return answer()

    monkeypatch.setattr(adapter, "execute", execute)

    async def exercise():
        task = asyncio.create_task(
            adapter.pipe(
                {"messages": [{"role": "user", "content": "Mean temperature in C for Mars?"}]},
                __user__={"id": "owner"},
                __request__=SimpleNamespace(headers={"authorization": "Bearer private"}),
            )
        )
        await asyncio.sleep(0.01)
        release.set()
        return await task

    assert "-65 °C" in asyncio.run(exercise())


def test_browser_review_rejects_changed_text_links_and_deployment(chat):
    import copy

    reviewer = importlib.import_module("review_ui")
    versions = {"corpus_release": "PostgreSQL 17.6", "corpus_revision": "abc"}
    question = {
        "id": "identifier-length",
        "question": "Identifier length in PostgreSQL 17.6?",
        "value": "63",
        "unit": "bytes",
    }
    url = "https://github.com/postgres/postgres/blob/abc/doc/src/sgml/limits.sgml"
    observation = {
        "id": "identifier-length",
        "question": question["question"],
        "url": "http://127.0.0.1:3188/c/chat",
        "text": "63 bytes\nSource: identifier-length.",
        "model": "Selected model: RAGParity - Public documents",
        "links": [{"text": "identifier-length", "href": url}],
    }
    receipt = {
        "chat_id": "chat",
        "message_id": "message",
        "question": question["question"],
        "rendered_answer": f"**63 bytes**\nSource: [identifier-length]({url}).",
        "versions": versions,
        "code_sha256": {"runtime.py": "digest"},
        "result": {
            "status": "ANSWERED",
            "structured_answer": {
                "value": "63",
                "unit": "bytes",
                "source_document_id": "identifier-length",
                "metric": "identifier-length",
            },
            "retrieved_documents": {
                "identifier-length": {"revision": "abc", "source_id": "postgresql-docs"}
            },
        },
    }
    questions = {question["id"]: ("postgresql", question)}
    result = reviewer.review(
        [observation], [receipt], questions, versions, {"runtime.py": "digest"}
    )
    assert result["supported_results"] == {"PASS": 1}
    wrong = copy.deepcopy(observation)
    wrong["text"] = "64 bytes\nSource: identifier-length."
    with pytest.raises(ValueError, match="visible"):
        reviewer.review([wrong], [receipt], questions, versions)
    wrong = copy.deepcopy(observation)
    wrong["links"][0]["href"] = "https://example.invalid/wrong-source"
    with pytest.raises(ValueError, match="citation"):
        reviewer.review([wrong], [receipt], questions, versions)
    with pytest.raises(ValueError, match="deployment"):
        reviewer.review([observation], [receipt], questions, versions, {"runtime.py": "different"})
    wrong = copy.deepcopy(observation)
    wrong["assistant_id"] = "another-message"
    with pytest.raises(ValueError, match="message"):
        reviewer.review([wrong], [receipt], questions, versions)
    with pytest.raises(ValueError, match="exactly once"):
        reviewer.review([], [receipt], questions, versions)


def test_spanish_reference_prompts_keep_original_independent_values_and_units(chat):
    evaluate = importlib.import_module("evaluate")
    english, spanish = evaluate.load_cases(), evaluate.load_cases("es")
    assert len(spanish) == 25
    for (_, original), (_, translated) in zip(english, spanish, strict=True):
        assert {k: v for k, v in translated.items() if k != "question"} == {
            k: v for k, v in original.items() if k != "question"
        }
        assert chat.infer_unit(translated["question"]) == original["unit"]
        assert chat.question_language(translated["question"]) == "es"


@pytest.mark.parametrize(
    "question,expected",
    [
        ("¿Cuál es el diámetro ecuatorial de Júpiter en kilómetros?", "Jupiter"),
        ("Que temperatura media de Marte en grados centigrados figura?", "Mars"),
        ("¿Cuántas columnas por índice en PostgreSQL 17.6?", "columns per index"),
        ("¿Qué período orbital tropical de la Tierra en días?", "Earth"),
    ],
)
def test_spanish_normalization_preserves_unknown_words_and_every_number(chat, question, expected):
    language = importlib.import_module("language")
    detected, normalized = language.normalize_question(question + " desconocido 123.45 -9")
    assert detected == "es"
    assert expected in normalized
    assert "desconocido 123.45 -9" in normalized
    original = "What mean temperature in C is listed for Mars?"
    assert language.normalize_question(original) == ("en", original)
    assert (
        language.question_language("What equatorial diameter in km is listed for Jupiter?") == "en"
    )


@pytest.mark.parametrize(
    "question",
    [
        "¿Cuál es la temperatura actual de Marte en C?",
        "¿Qué temperatura en grados C tiene Marte hoy?",
        "¿Qué temperatura en C hay en el ecuador de Marte?",
        "¿Qué temperatura en C tenía Marte el 28 de octubre de 2026?",
        "¿Qué temperatura en C tenía Marte el 2026-10-28?",
        "¿Qué temperatura en C se midió en Marte?",
        "¿Cuál es la temperatura de Marte en C en estos momentos?",
        "¿Qué temperatura tenía Marte en C el 28/10/2026?",
        "¿Qué temperatura tenía Marte en C a las 12:00?",
        "¿Qué temperatura en C hay en los polos de Marte?",
        "¿Qué temperatura en C hay en los cráteres de Marte?",
    ],
)
def test_spanish_scope_cannot_turn_local_or_dated_readings_into_means(chat, question):
    grounded = importlib.import_module("grounded")
    assert grounded.eligible_facts(question, "C", [])[1] == "STATIC_EVIDENCE_SCOPE"


def test_spanish_subjects_still_require_actual_retrieved_headings(chat):
    grounded = importlib.import_module("grounded")
    contexts = [
        {
            "document_id": "nasa-mars",
            "text": (
                "Document ID: nasa-mars\nPlanetary reference excerpt: Mars\n"
                "Metric ID: mean-temperature; Mean temperature: -12.75 C.\n"
            ),
        }
    ]
    facts, reason = grounded.eligible_facts(
        "¿Cuál es la temperatura media de Marte en C?", "C", contexts
    )
    assert reason is None
    assert facts[0].value == "-12.75"
    assert (
        grounded.eligible_facts("¿Cuál es la temperatura media del Sol en C?", "C", contexts)[1]
        == "NO_EVIDENCE_FOR_SUBJECT"
    )
    assert (
        grounded.eligible_facts(
            "¿Cuál es la temperatura media de Marte y el Sol en C?", "C", contexts
        )[1]
        == "AMBIGUOUS_SUBJECT"
    )


def test_spanish_chat_localizes_answers_clarification_and_errors_without_translating_quotes(
    adapter, monkeypatch
):
    monkeypatch.setattr(adapter, "execute", lambda *args: answer())
    visible = invoke(adapter, text="¿Qué temperatura media de Marte en grados C figura?")
    assert "Marte: Temperatura media" in visible
    assert "Fuente:" in visible and "-65 °C" in visible
    assert "> Mean temperature: -65 C." in visible
    assert "original en inglés" in visible
    assert "unidad de medida" in invoke(adapter, text="¿Qué temperatura tiene Marte?")
    assert "4.000 caracteres" in invoke(adapter, text="¿" + "x" * 4001)
    monkeypatch.setattr(
        adapter,
        "execute",
        lambda *args: {"status": "ABSTAINED", "abstention_reason": "STATIC_EVIDENCE_SCOPE"},
    )
    assert "No hay una respuesta respaldada" in invoke(
        adapter, text="¿Qué temperatura tiene Marte hoy en C?"
    )

    def fail(*args):
        raise ValueError("private-session-token")

    monkeypatch.setattr(adapter, "execute", fail)
    assert "No se pudo responder de forma segura" in invoke(
        adapter, text="¿Qué temperatura media de Marte en C figura?"
    )


def test_spanish_runtime_logs_normalized_query_and_uses_only_retrieved_values(chat):
    runtime = importlib.import_module("runtime")
    calls = []

    def transport(url, data, **kwargs):
        calls.append((url, data))
        if "query/collection" in url:
            return {
                "documents": [
                    [
                        "Document ID: nasa-mars\nPlanetary reference excerpt: Mars\n"
                        "Metric ID: mean-temperature; Mean temperature: -12.75 C.\n"
                    ]
                ],
                "metadatas": [[{"name": "rns-nasa-mars--" + "a" * 64 + ".txt"}]],
            }
        return {"choices": [{"message": {"content": '{"choice":0}'}, "finish_reason": "stop"}]}

    result = runtime.answer_question(
        "¿Qué temperatura media de Marte en C figura?",
        "C",
        "session",
        {"file": "id"},
        "local-model",
        call=transport,
    )
    assert result["status"] == "ANSWERED"
    assert result["question_language"] == "es"
    assert result["structured_answer"]["value"] == "-12.75"
    assert calls[0][1]["query"] == result["normalized_question"]
    assert "mean temperature" in calls[0][1]["query"]
    assert "Mars" in calls[0][1]["query"]
    calls.clear()
    result = runtime.answer_question(
        "¿Qué temperatura actual tiene Marte en C?",
        "C",
        "session",
        {"file": "id"},
        "local-model",
        call=transport,
    )
    assert result["status"] == "ABSTAINED"
    assert len(calls) == 1
