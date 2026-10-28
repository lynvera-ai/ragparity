"""Evaluate real local retrieval and generation; preserve each run and its evidence."""

import argparse
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

import runtime as chat_runtime
from corpus import HERE, ROOT
from manage import APP_URL, MODEL_URL, authenticate, private_write, request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lynvera_ragparity.claims import (
    EvidenceReference,
    NumericClaim,
    NumericEvidence,
    validate_claim,
)


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: Annotated[str, Field(pattern=r"^-?[0-9]+(?:\.[0-9]+)?$")] | None
    unit: str | None
    source_document_id: str | None
    metric: str | None


def validate_answer(
    question: dict,
    raw: str,
    retrieved: dict[str, dict],
    release: str,
    revision: str,
    source_id: str = "postgresql-docs",
):
    now = datetime.now(UTC)
    expected = NumericEvidence(
        value=question["value"],
        unit=question["unit"],
        period=release,
        source_id=source_id,
        metric=question.get("metric", question["id"]),
        provenance=EvidenceReference(
            reference_id=question.get("document_id", question["id"]),
            revision=revision,
            retrieved_at=now,
        ),
    )
    observed = None
    try:
        answer = Answer.model_validate_json(raw)
        cited = answer.source_document_id
        if cited in retrieved:
            identity = retrieved[cited]
            observed_revision = identity["revision"]
            observed = NumericEvidence(
                value=answer.value,
                unit=answer.unit,
                period=release if observed_revision == revision else observed_revision,
                source_id=identity["source_id"],
                metric=answer.metric,
                provenance=EvidenceReference(
                    reference_id=cited, revision=observed_revision, retrieved_at=now
                ),
            )
    except (ValidationError, ValueError, TypeError):
        pass
    return validate_claim(
        NumericClaim(
            claim_id=question["id"], expected=expected, observed=observed, require_provenance=True
        )
    )


def abstained(raw: str) -> bool:
    try:
        answer = Answer.model_validate_json(raw)
        return all(value is None for value in answer.model_dump().values())
    except (ValidationError, ValueError, TypeError):
        return False


def refresh_model_catalog(token: str, model: str) -> dict:
    return chat_runtime.refresh_model_catalog(token, model, call=request)


def answer_question(question_text: str, unit: str, token: str, uploads: dict, model: str) -> dict:
    return chat_runtime.answer_question(question_text, unit, token, uploads, model, call=request)


def evaluate_case(question: dict, token: str, uploads: dict, versions: dict, dataset: str) -> dict:
    result = answer_question(
        question["question"], question["unit"], token, uploads, versions["generation_model"]
    )
    result.update(
        question_id=question["id"], dataset=dataset, supported=question.get("supported", True)
    )
    if result["status"] == "ERROR":
        return result
    identities = result["retrieved_documents"]
    encoded_answer = json.dumps(result["structured_answer"])
    if not result["supported"]:
        result.update(
            status="INCONCLUSIVE",
            expected_abstention=True,
            abstained=result["answer_origin"] in ("policy_abstention", "model_abstention")
            and abstained(encoded_answer),
        )
    else:
        config = versions if dataset == "postgresql" else versions["nasa"]
        finding = validate_answer(
            question,
            encoded_answer,
            identities,
            config["corpus_release"] if dataset == "postgresql" else config["release"],
            config["corpus_revision"] if dataset == "postgresql" else config["revision"],
            "postgresql-docs" if dataset == "postgresql" else "nasa-planetary",
        )
        result.update(
            expected_document_retrieved=question.get("document_id", question["id"]) in identities,
            status=finding.status.value,
            finding=finding.model_dump(mode="json"),
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("all", "postgresql", "nasa"), default="all")
    parser.add_argument(
        "--case", action="append", default=[], help="Select question IDs; repeatable"
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cases = []
    for dataset, filename in (("postgresql", "questions.json"), ("nasa", "nasa_questions.json")):
        if args.dataset in ("all", dataset):
            cases.extend((dataset, item) for item in json.loads((HERE / filename).read_text()))
    if args.case:
        unknown = set(args.case) - {item["id"] for _, item in cases}
        if unknown:
            parser.error("Unknown case IDs: " + ", ".join(sorted(unknown)))
        cases = [(dataset, item) for dataset, item in cases if item["id"] in args.case]
    if args.limit is not None:
        if args.limit < 1 or args.limit > len(cases):
            parser.error("--limit must be between 1 and the selected case count")
        cases = cases[: args.limit]
    token = authenticate()
    uploads = json.loads((ROOT / "uploads.json").read_text())
    versions = json.loads((HERE / "versions.json").read_text())
    models = request(MODEL_URL + "/api/tags")
    actual_digests = {item["name"]: item["digest"] for item in models["models"]}
    if any(actual_digests.get(key) != value for key, value in versions["model_digests"].items()):
        parser.error("Installed model digests differ from the pinned pilot configuration")
    refresh_model_catalog(token, versions["generation_model"])
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = ROOT / "runs" / run_id
    outcomes = []
    provenance = {
        "harness_version": 5,
        "answer_mode": "evidence_selection",
        "started_at": datetime.now(UTC).isoformat(),
        "versions": versions,
        "observed_runtime": {
            "models": models,
            "model_server": request(MODEL_URL + "/api/version"),
            "application": request(APP_URL + "/api/version"),
        },
        "selected_cases": cases,
        "code_sha256": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in (
                "evaluate.py",
                "runtime.py",
                "transport.py",
                "grounded.py",
                "corpus.py",
                "planets.py",
                "manage.py",
            )
        },
    }
    private_write(directory / "provenance.json", json.dumps(provenance, indent=2))
    for name in provenance["code_sha256"]:
        private_write(directory / "code" / name, (HERE / name).read_text())
    print(f"Run: {run_id}", flush=True)
    for dataset, question in cases:
        try:
            result = evaluate_case(question, token, uploads, versions, dataset)
        except Exception as exc:
            # HTTP headers, connection strings and exception bodies can contain secrets.
            result = {
                "question_id": question["id"],
                "dataset": dataset,
                "status": "ERROR",
                "supported": question.get("supported", True),
                "error_type": type(exc).__name__,
            }
        outcomes.append(result)
        encoded = json.dumps(outcomes, indent=2) + "\n"
        private_write(directory / "answers.json", encoded)
        private_write(ROOT / "answers.json", encoded)
        print(f"{question['id']}: {result['status']}", flush=True)
    counts = {
        status: sum(item["status"] == status for item in outcomes if item["supported"])
        for status in ("PASS", "FAIL", "INCONCLUSIVE", "ERROR")
    }
    negatives = [item for item in outcomes if not item["supported"]]
    summary = {
        "run_id": run_id,
        "supported_cases": counts,
        "unsupported_cases": len(negatives),
        "correct_abstentions": sum(item.get("abstained", False) for item in negatives),
        "errors": sum(item["status"] == "ERROR" for item in outcomes),
        "policy_abstentions": sum(
            item.get("answer_origin") == "policy_abstention" for item in outcomes
        ),
        "model_abstentions": sum(
            item.get("answer_origin") == "model_abstention" for item in outcomes
        ),
        "invalid_selections": sum(
            item.get("answer_origin") == "invalid_selection" for item in outcomes
        ),
    }
    private_write(directory / "summary.json", json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    print("Integration observations; independent human pilot review remains required.")
    raise SystemExit(
        2
        if summary["errors"]
        else 1
        if counts["FAIL"]
        else 3
        if counts["INCONCLUSIVE"] or any(not item.get("abstained") for item in negatives)
        else 0
    )


if __name__ == "__main__":
    main()
