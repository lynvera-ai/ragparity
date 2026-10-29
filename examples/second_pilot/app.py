"""A separate local Haystack RAG application with a persistent chunk index."""

# Telemetry must be disabled before importing the application framework.
# ruff: noqa: E402

import hashlib
import json
import os
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ["HAYSTACK_TELEMETRY_ENABLED"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1"
HERE = Path(__file__).resolve().parent
ROOT = Path(
    os.environ.get(
        "RAGPARITY_SECOND_HOME",
        str(Path.home() / "Library/Application Support/Lynvera/RAGParity/second-pilot"),
    )
).resolve()
sys.path.insert(0, str(HERE.parent / "public_pilot"))
from answer import EvidenceResponder
from bilingual import LocalQueryTranslator
from haystack import Pipeline
from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from language_tools import prose_language, request_language
from manage import MODEL_URL, private_write, request


def digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def fingerprints() -> dict:
    return {
        name: digest((HERE / name).read_text())
        for name in (
            "app.py",
            "answer.py",
            "evidence.py",
            "ranking.py",
            "parity.py",
            "bilingual.py",
            "language_tools.py",
            "versions.json",
            "index.html",
        )
    }


def save(path: Path, value) -> None:
    private_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class Application:
    def __init__(self):
        versions = json.loads((HERE / "versions.json").read_text())
        self.store = InMemoryDocumentStore.load_from_disk(str(ROOT / "index.json"))
        self.pipeline = Pipeline()
        self.pipeline.add_component("translation", LocalQueryTranslator(MODEL_URL))
        self.pipeline.add_component(
            "embedder",
            OllamaTextEmbedder(model="nomic-embed-text:v1.5", url=MODEL_URL, keep_alive=0),
        )
        self.pipeline.add_component(
            "retriever",
            InMemoryEmbeddingRetriever(document_store=self.store, top_k=versions["top_k"]),
        )
        self.pipeline.add_component("responder", EvidenceResponder(ROOT, versions))
        self.pipeline.connect("translation.query", "embedder.text")
        self.pipeline.connect("translation.query", "responder.query")
        self.pipeline.connect("embedder.embedding", "retriever.query_embedding")
        self.pipeline.connect("retriever.documents", "responder.documents")
        self.lock = threading.Lock()
        self.versions = versions
        self.models = request(MODEL_URL + "/api/tags")
        self.code = fingerprints()
        self.index_hash = digest((ROOT / "index.json").read_text())

    def ask(self, question: str) -> dict:
        with self.lock:
            if fingerprints() != self.code:
                raise RuntimeError("Restart the application after changing runtime files")
            result = self.pipeline.run(
                {
                    "translation": {"question": question},
                    "responder": {"question": question},
                },
                include_outputs_from={"translation", "retriever"},
            )
            sources = [
                {
                    "document_id": d.meta["document_id"],
                    "chunk_id": d.meta["chunk_id"],
                    "url": d.meta["url"],
                    "text": d.content,
                    "score": d.score,
                }
                for d in result["retriever"]["documents"]
            ]
            answer = result["responder"]["result"]
            reply = answer["answer"]
            response = {
                "id": uuid.uuid4().hex,
                "answer": reply,
                "requested_language": request_language(question),
                "answer_language": prose_language(answer["answer_prose"]),
                "language_scope": "localized explanation; English source quotations",
                "answer_mode": "source_excerpt",
                "status": answer["status"],
                "answer_prose": answer["answer_prose"],
                "evidence": answer["evidence"],
                "selection_raw": answer["selection_raw"],
                "candidates": answer["candidates"],
                "sources": sources,
                "generation": answer["generation"],
                "query_translation": result["translation"]["translation"],
                "retrieval_query": result["translation"]["query"],
                "versions": self.versions,
                "code_sha256": self.code,
                "index_sha256": self.index_hash,
                "models": self.models,
            }
            save(ROOT / "receipts" / (response["id"] + ".json"), {"question": question, **response})
            return response


class Handler(BaseHTTPRequestHandler):
    application: Application

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/health":
            self.respond({"ready": True})
        elif self.path == "/":
            content = (HERE / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header(
                "Content-Security-Policy",
                (
                    "default-src 'self'; script-src 'unsafe-inline'; "
                    "style-src 'unsafe-inline'; connect-src 'self'"
                ),
            )
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)

    def respond(self, value, status=200):
        content = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if self.path != "/ask":
            return self.send_error(404)
        if self.headers.get("Origin") not in (None, "http://127.0.0.1:3189"):
            return self.send_error(403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                return self.send_error(413)
            question = json.loads(self.rfile.read(length))["question"]
            if not isinstance(question, str) or not question.strip() or len(question) > 1000:
                return self.send_error(400)
            response = self.application.ask(question)
            self.respond(response)
        except (KeyError, ValueError, TypeError):
            self.send_error(400)
        except Exception:
            self.respond({"error": "The local request failed. See the private service log."}, 503)
            import traceback

            traceback.print_exc()


def serve() -> None:
    # Block external connections, including accidental telemetry, during service operation.
    def local_only(event, args):
        if event == "socket.connect":
            address = args[1]
            if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1"):
                raise PermissionError("Only loopback connections are allowed")
        if event == "socket.getaddrinfo" and args[0] not in ("127.0.0.1", "::1", "localhost"):
            raise PermissionError("Only local address resolution is allowed")

    sys.addaudithook(local_only)
    Handler.application = Application()
    ThreadingHTTPServer(("127.0.0.1", 3189), Handler).serve_forever()


if __name__ == "__main__":
    serve()
