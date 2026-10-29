"""Independently score browser observations against native chat receipts and references.

This tool never sends chat messages. Browser evidence must already have been collected
through the interface and receipts exported with webui_install.py collect.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from evaluate import load_cases, validate_answer
from manage import HERE, ROOT, private_write


def visible_text(markdown: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)
    text = re.sub(r"(?m)^>\s?", "", text).replace("**", "")
    return " ".join(text.split())


def review(
    observations: list[dict],
    receipts: list[dict],
    questions: dict,
    versions: dict,
    expected_hashes=None,
    expected_language=None,
) -> dict:
    if len(observations) != len(questions) or {item["id"] for item in observations} != set(
        questions
    ):
        raise ValueError(
            "The browser observations must contain every reference question exactly once"
        )
    if len({item["id"] for item in observations}) != len(observations):
        raise ValueError("Duplicate browser observations are not valid evidence")
    results = []
    for observation in observations:
        dataset, question = questions[observation["id"]]
        chat_id = observation["url"].rsplit("/", 1)[-1]
        candidates = [
            item
            for item in receipts
            if item.get("chat_id") == chat_id and item.get("question") == observation["question"]
        ]
        if observation["question"] != question["question"] or len(candidates) != 1:
            raise ValueError("A browser question must match one native receipt in the same chat")
        receipt = candidates[0]
        if expected_language is not None and receipt.get("language", "en") != expected_language:
            raise ValueError("The native response does not use the expected question language")
        if observation.get("assistant_id") not in (None, receipt["message_id"]):
            raise ValueError("The browser message does not match the native receipt")
        if receipt.get("versions") != versions:
            raise ValueError("The receipt does not match the pinned model and corpus configuration")
        if expected_hashes is not None and receipt.get("code_sha256") != expected_hashes:
            raise ValueError("The receipt does not match the reviewed deployment code")
        if observation["model"] != "Selected model: RAGParity - Public documents":
            raise ValueError("The browser did not use the grounded document mode")
        if visible_text(receipt["rendered_answer"]) != " ".join(observation["text"].split()):
            raise ValueError("The visible browser answer differs from the native receipt")
        result = receipt["result"]
        row = {
            "id": question["id"],
            "chat_id": chat_id,
            "message_id": receipt["message_id"],
            "ui_matches_receipt": True,
            "supported": question.get("supported", True),
        }
        if result["status"] == "ERROR":
            row["status"] = "ERROR"
        elif not row["supported"]:
            row.update(
                status="INCONCLUSIVE",
                correct_abstention=(
                    result["status"] == "ABSTAINED"
                    and result.get("answer_origin") in ("policy_abstention", "model_abstention")
                    and all(
                        value is None
                        for value in result.get("structured_answer", {"missing": 1}).values()
                    )
                    and (
                        "No hay una respuesta respaldada."
                        if receipt.get("language") == "es"
                        else "No supported answer."
                    )
                    in observation["text"]
                ),
            )
        else:
            config = versions if dataset == "postgresql" else versions["nasa"]
            finding = validate_answer(
                question,
                json.dumps(result.get("structured_answer", {})),
                result.get("retrieved_documents", {}),
                config["corpus_release"] if dataset == "postgresql" else config["release"],
                config["corpus_revision"] if dataset == "postgresql" else config["revision"],
                "postgresql-docs" if dataset == "postgresql" else "nasa-planetary",
            )
            row.update(status=finding.status.value, finding=finding.model_dump(mode="json"))
            if finding.status.value == "PASS":
                cited = result["structured_answer"]["source_document_id"]
                expected_url = (
                    versions["nasa"]["files"]["facts.html"]["url"]
                    if dataset == "nasa"
                    else "https://github.com/postgres/postgres/blob/"
                    + versions["corpus_revision"]
                    + "/doc/src/sgml/limits.sgml"
                )
                if {"text": cited, "href": expected_url} not in observation["links"]:
                    raise ValueError("The verified answer has no matching visible citation")
        results.append(row)
    counts = Counter(item["status"] for item in results if item["supported"])
    negatives = [item for item in results if not item["supported"]]
    return {
        "channel": "Open WebUI browser interface",
        "cases": results,
        "supported_results": dict(counts),
        "unsupported_cases": len(negatives),
        "correct_abstentions": sum(item.get("correct_abstention", False) for item in negatives),
        "errors": sum(item["status"] == "ERROR" for item in results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, default=ROOT / "ui-evidence/observations.json")
    parser.add_argument("--language", choices=("en", "es"), default="en")
    args = parser.parse_args()
    questions = {item["id"]: (dataset, item) for dataset, item in load_cases(args.language)}
    report = review(
        json.loads(args.observations.read_text()),
        [json.loads(path.read_text()) for path in (ROOT / "ui-receipts").glob("*.json")],
        questions,
        json.loads((HERE / "versions.json").read_text()),
        json.loads((ROOT / "ui-install.json").read_text())["code_sha256"],
        args.language,
    )
    report["question_language"] = args.language
    report_file = "ui-report-es.json" if args.language == "es" else "ui-report.json"
    private_write(ROOT / report_file, json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}))
    if report["errors"]:
        raise SystemExit(2)
    if report["supported_results"] != {"PASS": 23} or report["correct_abstentions"] != 2:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
