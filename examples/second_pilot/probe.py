"""Check persisted-index faults and reload without modifying the application's index."""

import copy
import json
from dataclasses import replace
from datetime import UTC, datetime

from app import ROOT, digest, save
from haystack import Document
from haystack.document_stores.in_memory import InMemoryDocumentStore
from parity import compare, metadata


def main() -> None:
    destination = ROOT / "probes" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination.mkdir(parents=True, exist_ok=False)
    destination.chmod(0o700)
    original_hash = digest((ROOT / "index.json").read_text())
    manifest = json.loads((ROOT / "source-manifest.json").read_text())
    original = InMemoryDocumentStore.load_from_disk(str(ROOT / "index.json"))
    documents = original.filter_documents()
    results = []
    for fault in ("none", "missing", "hash", "version"):
        copies = [Document.from_dict(copy.deepcopy(d.to_dict())) for d in documents]
        if fault == "missing":
            copies.pop()
        elif fault == "hash":
            copies[0] = replace(copies[0], content=copies[0].content + " Controlled corruption.")
        elif fault == "version":
            copies[0].meta["source_version"] = "controlled-older-version"
        clone = InMemoryDocumentStore(embedding_similarity_function="cosine")
        clone.write_documents(copies)
        path = destination / (fault + ".json")
        clone.save_to_disk(str(path))
        path.chmod(0o600)
        loaded = InMemoryDocumentStore.load_from_disk(str(path))
        report = compare(manifest, metadata(loaded.filter_documents()))
        save(destination / (fault + "-audit.json"), report.model_dump(mode="json"))
        expected = "PASS" if fault == "none" else "FAIL"
        results.append(
            {
                "case": fault,
                "observed": report.status.value,
                "passed": report.status.value == expected,
                "counts": report.counts,
            }
        )
    unchanged = digest((ROOT / "index.json").read_text()) == original_hash
    save(destination / "summary.json", {"results": results, "original_unchanged": unchanged})
    print(json.dumps({"results": results, "original_unchanged": unchanged}, indent=2))
    if not unchanged or not all(row["passed"] for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
