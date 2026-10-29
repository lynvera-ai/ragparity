"""Benchmark-independent retrieval, evidence selection and extraction runtime."""

import hashlib
import re
from dataclasses import asdict
from urllib.error import HTTPError

from grounded import NULL_ANSWER, eligible_facts, selected_answer, selection_payload
from language import normalize_question
from pydantic import ValidationError
from transport import APP_URL, request


def document_identity(metadata: dict) -> dict | None:
    name = metadata.get("name", "")
    for prefix, length, source in (("rpg", 40, "postgresql-docs"), ("rns", 64, "nasa-planetary")):
        match = re.fullmatch(rf"{prefix}-(.+)--([a-f0-9]{{{length}}})[.]txt", name)
        if match and (prefix == "rpg" or match[1].startswith("nasa-")):
            return {"document_id": match[1], "revision": match[2], "source_id": source}
    return None


def refresh_model_catalog(token: str, model: str, *, app_url=APP_URL, call=request) -> dict:
    """Refresh application state after a native model download, before generation."""
    catalog = call(app_url + "/api/models", token=token)
    if model not in {item["id"] for item in catalog.get("data", [])}:
        raise RuntimeError("The pinned local model is not visible to the application")
    return catalog


def answer_question(
    question_text: str,
    unit: str,
    token: str,
    uploads: dict,
    model: str,
    *,
    app_url=APP_URL,
    call=request,
) -> dict:
    language, normalized = normalize_question(question_text)
    retrieval = call(
        app_url + "/api/v1/retrieval/query/collection",
        {
            "collection_names": ["file-" + file_id for file_id in uploads.values()],
            "query": normalized,
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
        selection_payload(normalized, unit, facts, model) if abstention_reason is None else None
    )
    result = {
        "question_language": language,
        "normalized_question": normalized,
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
            response = call(app_url + "/api/chat/completions", payload, token=token, timeout=120)
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
