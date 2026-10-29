"""Haystack evidence-selection component with source-derived answer rendering."""

import hashlib
import json

from evidence import candidates, paragraphs, render
from haystack import Document, component
from language_tools import request_language
from ranking import choose, rank


@component
class EvidenceResponder:
    def __init__(self, root, versions: dict):
        self.texts, self.catalog = {}, {}
        for source in versions["documents"]:
            raw = (root / "corpus" / (source["id"] + ".txt")).read_bytes()
            if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                raise ValueError("Pinned source checksum mismatch")
            text = raw.decode("utf-8")
            self.texts[source["id"]] = text
            self.catalog[source["id"]] = paragraphs(source["id"], text, source["url"])

    @component.output_types(result=dict)
    def run(self, documents: list[Document], query: str, question: str) -> dict:
        pool = candidates(documents, self.catalog, self.texts, question)
        search = query + " " + question
        eligible = rank(pool, search)
        chosen, decision = choose(pool, search)
        raw = json.dumps(decision)
        generation = {
            "finish_reason": "stop",
            "skipped": True,
            "reason": "extractive_response_without_answer_generation",
        }
        answer = render(chosen, request_language(question))
        return {
            "result": {
                **answer,
                "generation": generation,
                "selection_raw": raw,
                "candidates": [p.as_dict() for p in eligible],
                "candidate_pool_count": len(pool),
            }
        }
