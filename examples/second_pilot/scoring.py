"""Offline source, citation and answer checks. Never imported by the application."""

import hashlib
import re
from pathlib import Path


def validate_evidence(
    response: dict, originals: dict[str, str], expected: dict, case: dict
) -> bool:
    selected = response.get("evidence", [])
    candidates = response.get("candidates", [])
    if not case["document"]:
        return response.get("status") == "ABSTAINED" and selected == []
    if response.get("status") != "ANSWERED" or not selected:
        return False
    checked = []
    for row in selected:
        source = originals.get(row["document_id"])
        if source is None or not 0 <= row["start"] < row["end"] <= len(source):
            return False
        if source[row["start"] : row["end"]] != row["quote"]:
            return False
        if hashlib.sha256(source.encode()).hexdigest() != row["source_sha256"]:
            return False
        if row not in candidates or not row["chunk_ids"]:
            return False
        if row["quote"] not in response["answer"]:
            return False
        checked.append(row)
    without_quotes = response["answer"]
    for row in checked:
        without_quotes = without_quotes.replace(row["quote"], "", 1)
    remaining = "\n\n".join(part for part in without_quotes.split("\n\n") if part)
    if remaining != response.get("answer_prose"):
        return False
    # Check the cited, displayed evidence rather than merely any retrieved context.
    relevant = [row for row in checked if row["document_id"] == case["document"]]
    joined = "\n".join(row["quote"] for row in relevant)
    if not re.search(case["evidence_pattern"], joined, re.I | re.S):
        return False
    for row in relevant:
        if row["section"] not in expected.get("allowed_sections", [expected.get("section")]):
            return False
        if expected.get("item") and row["item"] != expected["item"]:
            return False
    return not expected.get("norm") or any(expected["norm"] in row["norms"] for row in relevant)


def source_texts(root: Path, versions: dict) -> dict[str, str]:
    result = {}
    for doc in versions["documents"]:
        raw = (root / "corpus" / (doc["id"] + ".txt")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != doc["sha256"]:
            raise ValueError("Original evaluation source differs from its pinned hash")
        result[doc["id"]] = raw.decode("utf-8")
    return result
