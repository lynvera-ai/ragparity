"""Ask a static-document question through the same local grounded flow as the pilot."""

import argparse
import hashlib
import json
import uuid
from datetime import UTC, datetime

from evaluate import answer_question, refresh_model_catalog
from manage import HERE, MODEL_URL, ROOT, authenticate, private_write, request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "question", help="English or Spanish question about the indexed static documents"
    )
    parser.add_argument("--unit", required=True, help="Explicit source unit, e.g. C, km or columns")
    args = parser.parse_args()
    if not args.question.strip() or not args.unit.strip():
        parser.error("Question and unit must not be blank")
    versions = json.loads((HERE / "versions.json").read_text())
    installed = request(MODEL_URL + "/api/tags")
    digests = {item["name"]: item["digest"] for item in installed["models"]}
    if any(digests.get(key) != value for key, value in versions["model_digests"].items()):
        parser.error("Installed model digests differ from the pinned pilot configuration")
    token = authenticate()
    refresh_model_catalog(token, versions["generation_model"])
    result = answer_question(
        args.question,
        args.unit,
        token,
        json.loads((ROOT / "uploads.json").read_text()),
        versions["generation_model"],
    )
    query_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    record = {
        "question": args.question,
        "unit": args.unit,
        "harness_version": 7,
        "versions": versions,
        "result": result,
        "code_sha256": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in (
                "ask.py",
                "evaluate.py",
                "runtime.py",
                "transport.py",
                "grounded.py",
                "language.py",
            )
        },
    }
    path = ROOT / "queries" / query_id / "answer.json"
    private_write(path, json.dumps(record, indent=2) + "\n")
    for name in record["code_sha256"]:
        private_write(path.parent / "code" / name, (HERE / name).read_text())
    print(
        json.dumps(
            {
                "status": result["status"],
                "answer": result.get("structured_answer"),
                "reason": result.get("abstention_reason"),
                "evidence": str(path),
            },
            indent=2,
        )
    )
    # An extracted answer is grounded in a passage; only benchmark scoring calls it verified.
    raise SystemExit(
        2 if result["status"] == "ERROR" else 3 if result["status"] == "INCONCLUSIVE" else 0
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Local query failed ({type(exc).__name__}); inspect the private runtime logs.")
        raise SystemExit(2) from None
