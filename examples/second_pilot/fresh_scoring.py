"""Offline checks for novel cases; this module is never loaded by the serving app."""

import hashlib
import re
import unicodedata

from scoring import validate_evidence


def question_key(text: str) -> str:
    folded = "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )
    return " ".join(re.findall(r"\w+", folded))


def collect_questions(value) -> list[str]:
    result = []
    if isinstance(value, list):
        for item in value:
            result.extend(collect_questions(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key == "question" and isinstance(item, str):
                result.append(item)
            elif key == "questions" and isinstance(item, dict):
                result.extend(text for text in item.values() if isinstance(text, str))
            else:
                result.extend(collect_questions(item))
    return result


def verify_novelty(cases: list[dict], previous: list[str]) -> dict:
    old = {question_key(q) for q in previous}
    current = [question_key(q) for c in cases for q in c["questions"].values()]
    if len(current) != len(set(current)):
        raise ValueError("Fresh questions contain duplicates")
    if old.intersection(current):
        raise ValueError("Fresh evaluation reuses an earlier question")
    return {
        "previous_question_count": len(old),
        "new_question_count": len(current),
        "normalized_overlap": 0,
        "prior_set_sha256": hashlib.sha256("\n".join(sorted(old)).encode()).hexdigest(),
    }


def quotation_integrity(response: dict, originals: dict) -> bool:
    selected = response.get("evidence", [])
    if response.get("status") == "ABSTAINED":
        return selected == [] and response.get("answer") == response.get("answer_prose")
    if response.get("status") != "ANSWERED" or not selected:
        return False
    remaining = response.get("answer", "")
    for row in selected:
        source = originals.get(row.get("document_id"))
        if source is None or not 0 <= row["start"] < row["end"] <= len(source):
            return False
        if source[row["start"] : row["end"]] != row["quote"]:
            return False
        if hashlib.sha256(source.encode()).hexdigest() != row["source_sha256"]:
            return False
        if row not in response.get("candidates", []) or row["quote"] not in remaining:
            return False
        if not any(
            s["document_id"] == row["document_id"] and s["chunk_id"] in row["chunk_ids"]
            for s in response.get("sources", [])
        ):
            return False
        remaining = remaining.replace(row["quote"], "", 1)
    return "\n\n".join(p for p in remaining.split("\n\n") if p) == response.get("answer_prose")


def score(case: dict, language: str, response: dict, originals: dict) -> dict:
    result = {
        "id": case["id"] + "-" + language,
        "category": case["category"],
        "language": language,
        "expected": case["expected"],
        "observed": response.get("status"),
    }
    if response.get("error_type"):
        return {**result, "status": "ERROR", "reason": "REQUEST_FAILED"}
    checks = case["checks"]
    answer_ok = all(
        re.search(p, response.get("answer", ""), re.I | re.S) is not None
        for p in case["answer_patterns"]
    )
    scope_ok = set(checks.get("required_sections", [])).issubset(
        {
            row["section"]
            for row in response.get("evidence", [])
            if row["document_id"] == case["document"]
        }
    )
    evidence_ok = validate_evidence(response, originals, checks, case)
    fidelity = quotation_integrity(response, originals)
    language_ok = response.get("requested_language") == language and response.get(
        "answer_language"
    ) in (language, "neutral")
    completion_ok = response.get("generation", {}).get("finish_reason") == "stop"
    disposition_ok = response.get("status") == case["expected"]
    passed = all(
        (answer_ok, scope_ok, evidence_ok, fidelity, language_ok, completion_ok, disposition_ok)
    )
    if passed:
        reason = "ALL_CHECKS_PASSED"
    elif not fidelity:
        reason = "QUOTATION_INTEGRITY"
    elif not disposition_ok:
        reason = (
            "FALSE_ABSTENTION" if response.get("status") == "ABSTAINED" else "UNSUPPORTED_ANSWER"
        )
    elif not language_ok:
        reason = "LANGUAGE_FRAME"
    elif not scope_ok:
        reason = "INCOMPLETE_MULTI_PASSAGE"
    elif not answer_ok:
        reason = "WRONG_OR_INCOMPLETE_PASSAGE"
    elif not evidence_ok:
        reason = "REFERENCE_OR_EVIDENCE_SCOPE"
    else:
        reason = "INCOMPLETE_OPERATION"
    return {
        **result,
        "status": "PASS" if passed else "FAIL",
        "reason": reason,
        "answer_check": answer_ok,
        "required_scope_check": scope_ok,
        "reference_check": evidence_ok,
        "quotation_integrity": fidelity,
        "language_check": language_ok,
        "completion_check": completion_ok,
        "receipt": response.get("id"),
    }
