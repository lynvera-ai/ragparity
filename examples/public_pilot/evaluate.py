"""Evaluate real local retrieval and generation; preserve each run and its evidence."""

import argparse
import hashlib
import json
import re
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated
from urllib.error import HTTPError

from corpus import HERE, ROOT
from grounded import NULL_ANSWER, eligible_facts, selected_answer, selection_payload
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


def document_identity(metadata: dict) -> dict | None:
    name = metadata.get("name", "")
    for prefix, length, source in (("rpg", 40, "postgresql-docs"), ("rns", 64, "nasa-planetary")):
        match = re.fullmatch(rf"{prefix}-(.+)--([a-f0-9]{{{length}}})[.]txt", name)
        if match and (prefix == "rpg" or match[1].startswith("nasa-")):
            return {"document_id": match[1], "revision": match[2], "source_id": source}
    return None


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
    """Refresh application state after a native model download, before generation."""
    catalog = request(APP_URL + "/api/models", token=token)
    if model not in {item["id"] for item in catalog.get("data", [])}:
        raise RuntimeError("The pinned local model is not visible to the application")
    return catalog


def answer_question(question_text: str, unit: str, token: str, uploads: dict, model: str) -> dict:
    retrieval = request(
        APP_URL + "/api/v1/retrieval/query/collection",
        {
            "collection_names": ["file-" + file_id for file_id in uploads.values()],
            "query": question_text,
            "k": 3,
            "hybrid": False,
        },
        token=token,
        timeout=180,
    )
    contexts, identities, evidence = [], {}, []
    texts = (retrieval.get("documents") or [[]])[0]
    metadata = (retrieval.get("metadatas") or [[]])[0]
    for content, meta in zip(texts, metadata, strict=True):
        identity = document_identity(meta)
        if identity is not None:
            document_id = identity["document_id"]
            identities[document_id] = identity
            passage = content.split("Redistribution notice for the source documentation:")[0]
            if identity["source_id"] == "postgresql-docs":
                # Actual retrieved filename, never the expected answer or reference ID.
                passage += f"\nMetric ID: {document_id}\n"
            contexts.append({"document_id": document_id, "text": passage})
            evidence.append(
                {
                    **identity,
                    "text": content,
                    "text_sha256": hashlib.sha256(content.encode()).hexdigest(),
                }
            )
    facts, abstention_reason = eligible_facts(question_text, unit, contexts)
    payload = (
        selection_payload(question_text, unit, facts, model) if abstention_reason is None else None
    )
    result = {
        "retrieved_documents": identities,
        "retrieved_evidence": evidence,
        "generation_request": payload,
        "answer_mode": "evidence_selection",
        "eligible_evidence_rows": [asdict(fact) for fact in facts],
        "raw_selection": None,
    }
    if payload is None:
        answer = dict(NULL_ANSWER)
        result.update(answer_origin="policy_abstention", abstention_reason=abstention_reason)
    else:
        try:
            response = request(APP_URL + "/api/chat/completions", payload, token=token, timeout=120)
            choice = response["choices"][0]
            raw = choice["message"]["content"]
        except (HTTPError, TimeoutError, ConnectionError) as exc:
            result.update(status="ERROR", error_type=type(exc).__name__, error_stage="generation")
            if isinstance(exc, HTTPError):
                result["http_status"] = exc.code
            return result
        result.update(
            raw_selection=raw,
            finish_reason=choice.get("finish_reason"),
            usage=response.get("usage"),
        )
        try:
            if choice.get("finish_reason") == "length":
                raise ValueError("Selection exhausted its generation budget")
            answer, index = selected_answer(raw, facts)
            result.update(
                selection_index=index,
                answer_origin=("model_abstention" if index == -1 else "evidence_extraction"),
            )
        except (ValidationError, ValueError, TypeError):
            answer = dict(NULL_ANSWER)
            result.update(answer_origin="invalid_selection", abstention_reason="INVALID_SELECTION")
    result["structured_answer"] = answer
    result["status"] = (
        "ANSWERED"
        if result["answer_origin"] == "evidence_extraction"
        else "INCONCLUSIVE"
        if result["answer_origin"] == "invalid_selection"
        else "ABSTAINED"
    )
    return result


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
            for name in ("evaluate.py", "grounded.py", "corpus.py", "planets.py", "manage.py")
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
