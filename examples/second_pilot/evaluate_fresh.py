"""Freeze and run new bilingual cases against the unchanged local Haystack service."""

import argparse
import hashlib
import json
import re
import subprocess
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app import HERE, MODEL_URL, ROOT, digest, fingerprints, private_write, request, save
from fresh_scoring import collect_questions, score, verify_novelty
from scoring import source_texts

URL = "http://127.0.0.1:3189"


def prepare_cases(path: Path, originals: dict) -> tuple[dict, dict]:
    specification = json.loads(path.read_text())
    cases = specification["cases"]
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)) or any(re.fullmatch(r"[a-z0-9-]+", i) is None for i in ids):
        raise ValueError("Case identifiers must be unique and safe filenames")
    for case in cases:
        if set(case["questions"]) != {"es", "en"}:
            raise ValueError("Every case needs English and Spanish questions")
        if case["expected"] not in ("ANSWERED", "ABSTAINED"):
            raise ValueError("Unknown expected disposition")
        for pattern in case["answer_patterns"]:
            re.compile(pattern)
        if case["document"]:
            if not re.search(case["evidence_pattern"], originals[case["document"]], re.I | re.S):
                raise ValueError("A new reference is absent from its pinned source: " + case["id"])
        elif case["expected"] != "ABSTAINED":
            raise ValueError("A supported question needs an authoritative source")
    previous = []
    for old in [
        HERE / "questions.json",
        *(HERE.parent / "public_pilot").glob("*.json"),
        *(ROOT / "receipts").glob("*.json"),
        *(ROOT.parent / "public-pilot/ui-receipts").glob("*.json"),
    ]:
        previous.extend(collect_questions(json.loads(old.read_text())))
    novelty = verify_novelty(cases, previous)
    return specification, novelty


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=HERE / "fresh_questions.json")
    args = parser.parse_args()
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=HERE, text=True
    ).strip()
    if not branch or branch == "main":
        raise RuntimeError("Run the evaluation on a working branch outside main")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip()
    versions = json.loads((HERE / "versions.json").read_text())
    originals = source_texts(ROOT, versions)
    specification, novelty = prepare_cases(args.questions, originals)
    models = request(MODEL_URL + "/api/tags")
    pinned = json.loads((HERE.parent / "public_pilot/versions.json").read_text())["model_digests"]
    actual = {m["name"]: m["digest"] for m in models["models"]}
    if any(actual.get(name) != checksum for name, checksum in pinned.items()):
        raise RuntimeError("The local model digests differ from their pins")
    if not request(URL + "/health", timeout=5).get("ready"):
        raise RuntimeError("The existing local service is not ready")
    code = fingerprints()
    index_hash = digest((ROOT / "index.json").read_text())
    run = (
        ROOT
        / "fresh-evaluations"
        / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    )
    run.mkdir(parents=True, exist_ok=False)
    run.chmod(0o700)
    freeze = {
        "created_at": datetime.now(UTC).isoformat(),
        "specification": specification,
        "novelty": novelty,
        "code_sha256": code,
        "versions": versions,
        "models": models,
        "index_sha256": index_hash,
        "source_manifest": json.loads((ROOT / "source-manifest.json").read_text()),
        "git_branch": branch,
        "git_head": head,
        "independent_human_acceptance": False,
        "question_specification_sha256": digest(args.questions.read_text()),
        "evaluation_code_sha256": {
            name: digest((HERE / name).read_text())
            for name in ("evaluate_fresh.py", "fresh_scoring.py", "scoring.py")
        },
    }
    save(run / "frozen.json", freeze)
    private_write(
        run / "frozen.sha256", hashlib.sha256((run / "frozen.json").read_bytes()).hexdigest() + "\n"
    )
    for name in (*code, "evaluate_fresh.py", "fresh_scoring.py", "scoring.py"):
        private_write(run / "code" / name, (HERE / name).read_text())
    private_write(run / "code/fresh_questions.json", args.questions.read_text())
    results = []
    print("Fresh evaluation: " + run.name, flush=True)
    for case in specification["cases"]:
        for language, question in case["questions"].items():
            if fingerprints() != code or digest((ROOT / "index.json").read_text()) != index_hash:
                raise RuntimeError("Runtime or index changed after the evaluation was frozen")
            before = time.monotonic()
            try:
                # Only question text is passed; references and expected answers stay offline.
                response = request(URL + "/ask", {"question": question}, timeout=300)
            except Exception as exc:
                response = {"error_type": type(exc).__name__}
            name = case["id"] + "-" + language
            save(run / (name + ".json"), response)
            if not response.get("error_type"):
                if (
                    response["code_sha256"] != code
                    or response["index_sha256"] != index_hash
                    or response["versions"] != versions
                ):
                    raise RuntimeError("The serving deployment differs from its frozen fingerprint")
                served = {m["name"]: m["digest"] for m in response["models"]["models"]}
                if any(served.get(n) != d for n, d in pinned.items()):
                    raise RuntimeError("The serving model record differs from its pin")
            result = score(case, language, response, originals)
            result["seconds"] = round(time.monotonic() - before, 2)
            results.append(result)
            save(run / "results.json", results)
            print(name + ": " + result["status"] + " " + result["reason"], flush=True)
    summary = {
        "run_id": run.name,
        "total": len(results),
        "counts": dict(Counter(r["status"] for r in results)),
        "by_language": {
            lang: dict(Counter(r["status"] for r in results if r["language"] == lang))
            for lang in ("es", "en")
        },
        "by_category": {
            cat: dict(Counter(r["status"] for r in results if r["category"] == cat))
            for cat in sorted({r["category"] for r in results})
        },
        "expected_answers": sum(r["expected"] == "ANSWERED" for r in results),
        "expected_abstentions": sum(r["expected"] == "ABSTAINED" for r in results),
        "quotation_integrity_pass": sum(r.get("quotation_integrity", False) for r in results),
        "runtime_unchanged": fingerprints() == code,
        "index_unchanged": digest((ROOT / "index.json").read_text()) == index_hash,
    }
    save(run / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    print("Evidence: " + str(run), flush=True)
    if summary["counts"].get("PASS", 0) != summary["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
