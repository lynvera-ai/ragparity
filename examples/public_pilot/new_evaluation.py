"""Freeze and execute new bilingual cases through the unchanged native local chat API.

This is an engineering evaluation authored alongside the implementation, not independent
human acceptance. Golden fields are used only by offline scoring, never sent to the chat.
"""

import hashlib
import json
import re
import uuid
from collections import Counter
from datetime import UTC, datetime

from corpus import LimitsParser
from evaluate import validate_answer
from manage import APP_URL, HERE, MODEL_URL, ROOT, authenticate, private_write, request
from planets import METRICS, PlanetTable
from webui_install import collect

RUNTIME_FILES = ("runtime.py", "grounded.py", "language.py", "transport.py", "chat_adapter.py")


def hashes() -> dict:
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in RUNTIME_FILES}


def reference_cases(specifications: list[dict], versions: dict, corpus) -> list[dict]:
    # Verify authoritative cached source bytes, independently of the application index.
    for path, expected in [
        (corpus / "limits.sgml", versions["corpus_file_sha256"]["limits.sgml"]),
        *[
            (corpus / "nasa" / name, info["sha256"])
            for name, info in versions["nasa"]["files"].items()
        ],
    ]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("A cached authoritative source differs from its pinned digest")
    nasa = PlanetTable()
    nasa.feed((corpus / "nasa/facts.html").read_text())
    values = nasa.values()
    postgres = LimitsParser()
    postgres.feed((corpus / "limits.sgml").read_text())
    cases = []
    for spec in specifications:
        reference = spec.get("reference")
        expected = None
        if reference:
            if "planet" in reference:
                metric, planet = reference["metric"], reference["planet"]
                expected = {
                    "value": values[metric][planet],
                    "unit": METRICS[metric][2],
                    "metric": metric,
                    "document_id": "nasa-" + planet,
                    "source": "nasa",
                }
            else:
                raw = postgres.rows[reference["item"]][1]
                expected = {
                    "value": re.match(r"[\d,]+", raw)[0].replace(",", ""),
                    "unit": reference["unit"],
                    "metric": reference["document_id"],
                    "document_id": reference["document_id"],
                    "source": "postgresql",
                }
        for language, question in spec["questions"].items():
            cases.append(
                {
                    "id": spec["id"] + "-" + language,
                    "question": question,
                    "language": language,
                    "expected": spec["expected"],
                    "reference": expected,
                }
            )
    return cases


def score(case: dict, receipt: dict | None, response: dict, versions: dict, code: dict) -> dict:
    result = {"id": case["id"], "language": case["language"], "expected": case["expected"]}
    if receipt is None or response.get("error_type"):
        return {**result, "status": "ERROR", "reason": "NATIVE_REQUEST_OR_RECEIPT_MISSING"}
    if receipt["code_sha256"] != code or receipt["versions"] != versions:
        raise ValueError("The evaluated deployment changed after the evaluation was frozen")
    if receipt["language"] != case["language"]:
        return {**result, "status": "FAIL", "reason": "RESPONSE_LANGUAGE"}
    if (
        response.get("choices", [{}])[0].get("message", {}).get("content")
        != receipt["rendered_answer"]
    ):
        return {**result, "status": "ERROR", "reason": "API_RECEIPT_DIFFER"}
    actual = receipt["result"]
    if actual["status"] == "ERROR":
        return {**result, "status": "ERROR", "reason": "RUNTIME_ERROR"}
    passed = actual["status"] == case["expected"]
    result["observed"] = actual["status"]
    if case["expected"] == "ANSWERED":
        ref = case["reference"]
        config = versions["nasa"] if ref["source"] == "nasa" else versions
        finding = validate_answer(
            {**ref, "id": case["id"]},
            json.dumps(actual.get("structured_answer", {})),
            actual.get("retrieved_documents", {}),
            config["release"] if ref["source"] == "nasa" else config["corpus_release"],
            config["revision"] if ref["source"] == "nasa" else config["corpus_revision"],
            "nasa-planetary" if ref["source"] == "nasa" else "postgresql-docs",
        )
        passed = passed and finding.status.value == "PASS"
        result["finding"] = finding.model_dump(mode="json")
    elif case["expected"] == "ABSTAINED":
        passed = passed and actual.get("answer_origin") in ("policy_abstention", "model_abstention")
        passed = passed and actual.get("structured_answer") == {
            "value": None,
            "unit": None,
            "source_document_id": None,
            "metric": None,
        }
    result.update(status="PASS" if passed else "FAIL", reason=actual.get("abstention_reason"))
    return result


def main() -> None:
    versions = json.loads((HERE / "versions.json").read_text())
    code = hashes()
    if code != json.loads((ROOT / "ui-install.json").read_text())["code_sha256"]:
        raise ValueError("Deploy the reviewed runtime before evaluating")
    actual = {m["name"]: m["digest"] for m in request(MODEL_URL + "/api/tags")["models"]}
    if any(actual.get(k) != v for k, v in versions["model_digests"].items()):
        raise ValueError("Installed model digest mismatch")
    specs = json.loads((HERE / "new_questions.json").read_text())
    cases = reference_cases(specs, versions, ROOT / "corpus")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = ROOT / "evaluations" / run_id
    directory.mkdir(parents=True, mode=0o700)
    frozen = {
        "created_at": datetime.now(UTC).isoformat(),
        "runtime_sha256": code,
        "versions": versions,
        "cases": cases,
        "channel": "native Open WebUI HTTP API",
        "independent_human_review": False,
        "specification_sha256": hashlib.sha256(
            (HERE / "new_questions.json").read_bytes()
        ).hexdigest(),
    }
    private_write(directory / "frozen.json", json.dumps(frozen, indent=2))
    seal = hashlib.sha256((directory / "frozen.json").read_bytes()).hexdigest()
    private_write(directory / "frozen.sha256", seal + "\n")
    for name in (*RUNTIME_FILES, "new_evaluation.py", "new_questions.json"):
        private_write(directory / "code" / name, (HERE / name).read_text())
    token = authenticate()
    responses = []
    print(f"Evaluation: {run_id} (frozen before the first question)", flush=True)
    for case in cases:
        if hashes() != code:
            raise ValueError("Runtime source changed during evaluation")
        message_id = str(uuid.uuid4())
        # This is the entire generation input: no unit, references, expected state or IDs.
        payload = {
            "model": "ragparity_grounded",
            "stream": False,
            "id": message_id,
            "chat_id": "local:" + run_id,
            "messages": [{"role": "user", "content": case["question"]}],
        }
        try:
            response = request(APP_URL + "/api/chat/completions", payload, token=token, timeout=240)
        except Exception as exc:
            response = {"error_type": type(exc).__name__}
        responses.append(
            {
                "case_id": case["id"],
                "message_id": message_id,
                "request": payload,
                "response": response,
            }
        )
        private_write(directory / "responses.json", json.dumps(responses, indent=2))
        print(f"{case['id']}: request completed", flush=True)
    collect()
    receipts = [json.loads(p.read_text()) for p in (ROOT / "ui-receipts").glob("*.json")]
    selected = []
    results = []
    for case, response in zip(cases, responses, strict=True):
        matches = [
            r
            for r in receipts
            if r["message_id"] == response["message_id"]
            and r["question"] == case["question"]
            and r["chat_id"] == "local:" + run_id
        ]
        receipt = matches[0] if len(matches) == 1 else None
        if receipt:
            selected.append(receipt)
        results.append(score(case, receipt, response["response"], versions, code))
    private_write(directory / "receipts.json", json.dumps(selected, indent=2))
    summary = {
        "run_id": run_id,
        "frozen_sha256": seal,
        "channel": frozen["channel"],
        "counts": dict(Counter(r["status"] for r in results)),
        "by_language": {
            language: dict(Counter(r["status"] for r in results if r["language"] == language))
            for language in ("en", "es")
        },
        "independent_human_review": False,
        "cases": results,
    }
    private_write(directory / "report.json", json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}))
    raise SystemExit(
        2 if summary["counts"].get("ERROR") else 1 if summary["counts"].get("FAIL") else 0
    )


if __name__ == "__main__":
    main()
