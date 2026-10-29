"""Prepare, run and audit the second local RAG pilot."""

import argparse
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from urllib.request import urlopen

from app import HERE, ROOT, digest, fingerprints, save

sys.path.insert(0, str(HERE.parent / "public_pilot"))
from haystack import Document
from haystack.components.preprocessors import DocumentSplitter
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from parity import compare, metadata, word_windows
from transport import MODEL_URL, request

URL = "http://127.0.0.1:3189"


def source_documents() -> list[Document]:
    versions = json.loads((HERE / "versions.json").read_text())
    documents = []
    for source in versions["documents"]:
        path = ROOT / "corpus" / (source["id"] + ".txt")
        if not path.exists():
            with urlopen(source["url"], timeout=60) as response:
                raw = response.read()
            from hashlib import sha256

            if sha256(raw).hexdigest() != source["sha256"]:
                raise ValueError("Downloaded RFC checksum mismatch")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o600)
        text = path.read_text()
        if digest(text) != "sha256:" + source["sha256"]:
            raise ValueError("Cached RFC checksum mismatch")
        documents.append(
            Document(
                id=source["id"],
                content=text,
                meta={
                    "document_id": source["id"],
                    "url": source["url"],
                    "source_version": source["sha256"],
                    "content_hash": digest(text),
                    "is_deleted": False,
                },
            )
        )
    return documents


def prepare() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    ROOT.chmod(0o700)
    versions = json.loads((HERE / "versions.json").read_text())
    for package, key in (
        ("haystack-ai", "haystack_version"),
        ("ollama-haystack", "integration_version"),
    ):
        if importlib.metadata.version(package) != versions[key]:
            raise ValueError("The installed application version differs from its pin")
    if (ROOT / "index.json").exists():
        raise RuntimeError("An index already exists; use audit or a separate pilot directory")
    originals = source_documents()
    # Independent word windows, computed before calling the application's splitter or embedder.
    manifest = []
    for doc in originals:
        expected = word_windows(doc.content)
        manifest.append(
            {
                **doc.meta,
                "expected_chunks": expected,
                "words": len(doc.content.split()),
                "characters": len(doc.content),
            }
        )
    save(ROOT / "source-manifest.json", {"versions": versions, "documents": manifest})
    splitter = DocumentSplitter(
        split_by="word",
        split_length=180,
        split_overlap=30,
        split_threshold=0,
        respect_sentence_boundary=False,
    )
    splitter.warm_up()
    chunks = splitter.run(documents=originals)["documents"]
    for chunk in chunks:
        chunk.meta["chunk_id"] = str(chunk.meta["split_id"] * 150)
    # Verify the independently built boundaries before writing any embedding.
    projected = metadata(chunks)
    report = compare(json.loads((ROOT / "source-manifest.json").read_text()), projected)
    if report.status.value != "PASS":
        save(ROOT / "splitter-mismatch.json", report.model_dump(mode="json"))
        raise ValueError("Independent word windows differ from the installed splitter")
    model_versions = json.loads((HERE.parent / "public_pilot/versions.json").read_text())
    tags = request(MODEL_URL + "/api/tags")
    actual = {m["name"]: m["digest"] for m in tags["models"]}
    for name, checksum in model_versions["model_digests"].items():
        if actual.get(name) != checksum:
            raise ValueError("A local model differs from its reviewed digest")
    save(ROOT / "models.json", {"tags": tags, "runtime": request(MODEL_URL + "/api/version")})
    embedder = OllamaDocumentEmbedder(
        model="nomic-embed-text:v1.5", url=MODEL_URL, progress_bar=False, batch_size=1
    )
    embedded = embedder.run(documents=chunks)["documents"]
    store = InMemoryDocumentStore(embedding_similarity_function="cosine")
    store.write_documents(embedded)
    store.save_to_disk(str(ROOT / "index.json"))
    (ROOT / "index.json").chmod(0o600)
    print(f"Indexed {len(originals)} complete documents as {len(chunks)} fragments.", flush=True)
    audit()


def audit() -> None:
    store = InMemoryDocumentStore.load_from_disk(str(ROOT / "index.json"))
    rows = metadata(store.filter_documents())
    manifest = json.loads((ROOT / "source-manifest.json").read_text())
    report = compare(manifest, rows)
    save(ROOT / "index-metadata.json", rows)
    save(ROOT / "audit.json", report.model_dump(mode="json"))
    print("Fragment audit: " + report.status.value, flush=True)
    if report.status.value != "PASS":
        raise RuntimeError("The stored index differs from the source manifest")


def start() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    try:
        if request(URL + "/health", timeout=2).get("ready"):
            print("Second application already ready: " + URL)
            return
    except (OSError, ValueError):
        pass
    with (ROOT / "service.log").open("ab") as stream:
        process = subprocess.Popen(
            [sys.executable, str(HERE / "app.py")],
            cwd=HERE,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    save(ROOT / "service.json", {"pid": process.pid, "script": str(HERE / "app.py")})
    for _ in range(60):
        if process.poll() is not None:
            raise RuntimeError("See the private service log")
        try:
            if request(URL + "/health", timeout=2).get("ready"):
                print("Second application ready: " + URL, flush=True)
                return
        except (OSError, ValueError):
            pass
        time.sleep(1)
    raise RuntimeError("The application did not become ready")


def stop() -> None:
    import signal

    state = json.loads((ROOT / "service.json").read_text())
    command = subprocess.run(
        ["ps", "-p", str(state["pid"]), "-o", "args="], capture_output=True, text=True
    ).stdout
    if state["script"] not in command:
        raise RuntimeError("The recorded process no longer belongs to this application")
    os.kill(state["pid"], signal.SIGTERM)


def evaluate() -> None:
    cases = json.loads((HERE / "questions.json").read_text())
    run = ROOT / "evaluations" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run.mkdir(parents=True, exist_ok=False)
    run.chmod(0o700)
    code = fingerprints()
    save(
        run / "frozen.json",
        {
            "cases": cases,
            "code_sha256": code,
            "evaluator_sha256": digest((HERE / "manage.py").read_text()),
            "questions_sha256": digest((HERE / "questions.json").read_text()),
            "manifest": json.loads((ROOT / "source-manifest.json").read_text()),
            "models": json.loads((ROOT / "models.json").read_text()),
            "index_sha256": digest((ROOT / "index.json").read_text()),
        },
    )
    for name in (*code, "manage.py", "questions.json"):
        save_path = run / "code" / name
        from app import private_write

        private_write(save_path, (HERE / name).read_text())
    # Verify golden evidence against pinned source files, never against the index.
    for case in cases:
        if case["document"]:
            source = (ROOT / "corpus" / (case["document"] + ".txt")).read_text()
            if not re.search(case["evidence_pattern"], source, re.I | re.S):
                raise ValueError("A question reference is absent from its pinned RFC")
    results = []
    for case in cases:
        for lang, question in case["questions"].items():
            before = time.monotonic()
            try:
                response = request(URL + "/ask", {"question": question}, timeout=300)
            except Exception as exc:
                save(run / (case["id"] + "-" + lang + ".json"), {"error_type": type(exc).__name__})
                results.append(
                    {
                        "id": case["id"] + "-" + lang,
                        "status": "ERROR",
                        "seconds": round(time.monotonic() - before, 2),
                    }
                )
                save(run / "results.json", results)
                print(results[-1]["id"] + ": ERROR", flush=True)
                continue
            save(run / (case["id"] + "-" + lang + ".json"), response)
            if response["code_sha256"] != code:
                raise RuntimeError("Deployment changed during evaluation")
            answer = response["answer"]
            answer_ok = all(
                re.search(pattern, answer, re.I | re.S) for pattern in case["answer_patterns"]
            )
            source_ok = case.get("document") is None or any(
                s["document_id"] == case["document"]
                and re.search(case["evidence_pattern"], s["text"], re.I | re.S)
                for s in response["sources"]
            )
            generation_ok = response["generation"].get("finish_reason") == "stop"
            language_ok = response["requested_language"] == lang and response[
                "answer_language"
            ] in (lang, "neutral")
            passed = bool(answer) and answer_ok and source_ok and generation_ok and language_ok
            results.append(
                {
                    "id": case["id"] + "-" + lang,
                    "status": "PASS" if passed else "FAIL",
                    "answer_check": bool(answer_ok),
                    "generation_check": generation_ok,
                    "language_check": language_ok,
                    "source_check": source_ok,
                    "receipt": response["id"],
                    "seconds": round(time.monotonic() - before, 2),
                }
            )
            save(run / "results.json", results)
            print(results[-1]["id"] + ": " + results[-1]["status"], flush=True)
    save(
        run / "summary.json",
        {"passed": sum(r["status"] == "PASS" for r in results), "total": len(results)},
    )
    print("Evidence: " + str(run), flush=True)
    if any(row["status"] != "PASS" for row in results):
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "audit", "start", "stop", "evaluate"))
    globals()[parser.parse_args().action]()


if __name__ == "__main__":
    main()
