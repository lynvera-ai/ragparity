"""Build attributed text excerpts from the pinned official PostgreSQL limits table."""

import hashlib
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
ROOT = (
    Path(
        os.environ.get(
            "RAGPARITY_PILOT_HOME",
            str(Path.home() / "Library/Application Support/Lynvera/RAGParity/public-pilot"),
        )
    )
    .expanduser()
    .resolve()
)


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def verified_download(path: Path, url: str, checksum: str) -> bytes:
    """Reuse only verified bytes; upstream changes require an explicit reference update."""
    data = path.read_bytes() if path.exists() else None
    if data is None or hashlib.sha256(data).hexdigest() != checksum:
        with urlopen(url, timeout=30) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != checksum:
        raise ValueError("Pinned public source checksum mismatch")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def reference_document(body: str, question: dict, filename: str, revision: str) -> dict:
    if len(body) >= 4096:
        raise ValueError("Public pilot excerpts must each fit in one configured fragment")
    return {
        **question,
        "filename": filename,
        "source_version": revision,
        "content_hash": digest(body.encode()),
        "chunk_hash": digest(body.strip().encode()),
    }


class LimitsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: dict[str, list[str]] = {}
        self.cells: list[str] | None = None
        self.text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "row":
            self.cells = []
        elif tag == "entry" and self.cells is not None:
            self.text = []

    def handle_data(self, data: str) -> None:
        if self.text is not None:
            self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "entry" and self.text is not None and self.cells is not None:
            self.cells.append(" ".join("".join(self.text).split()))
            self.text = None
        elif tag == "row" and self.cells:
            self.rows[self.cells[0]] = self.cells
            self.cells = None


def render_excerpt(question: dict, row: list[str], license_text: str, revision: str) -> str:
    url = f"https://github.com/postgres/postgres/blob/{revision}/doc/src/sgml/limits.sgml"
    return (
        f"PostgreSQL 17.6 official documentation: {question['item']}\n"
        f"Document ID: {question['id']}\n"
        f"Source revision: {revision}\nSource: {url}\n\n"
        f"Item: {row[0]}\nUpper limit: {row[1]}\n"
        f"Conditions: {row[2] or 'No additional condition in this table row.'}\n"
        "Practical limits may be lower than these documented hard limits.\n\n"
        "Redistribution notice for the source documentation:\n" + license_text.strip() + "\n"
    )


def prepare() -> dict:
    versions = json.loads((HERE / "versions.json").read_text())
    revision = versions["corpus_revision"]
    destination = ROOT / "corpus"
    destination.mkdir(parents=True, exist_ok=True)
    downloads = {}
    for name, remote in {
        "limits.sgml": "doc/src/sgml/limits.sgml",
        "COPYRIGHT": "COPYRIGHT",
    }.items():
        url = f"https://raw.githubusercontent.com/postgres/postgres/{revision}/{remote}"
        data = verified_download(destination / name, url, versions["corpus_file_sha256"][name])
        downloads[name] = {"url": url, "content_hash": digest(data)}
    parser = LimitsParser()
    parser.feed((destination / "limits.sgml").read_text())
    license_text = (destination / "COPYRIGHT").read_text()
    documents = []
    for question in json.loads((HERE / "questions.json").read_text()):
        row = parser.rows[question["item"]]
        numeric = re.match(r"[\d,]+", row[1])
        if numeric is None or numeric.group().replace(",", "") != question["value"]:
            raise ValueError("Pinned documentation does not match the reviewed reference values")
        body = render_excerpt(question, row, license_text, revision)
        filename = f"rpg-{question['id']}--{revision}.txt"
        (destination / filename).write_text(body, encoding="utf-8")
        documents.append(
            reference_document(
                body,
                {**question, "source_id": "postgresql-docs", "collection": "postgresql-17.6"},
                filename,
                revision,
            )
        )
    # Imported lazily so the standalone PostgreSQL parser remains independently usable.
    from planets import prepare_planets

    if "nasa" in versions:
        documents.extend(prepare_planets(destination, versions["nasa"]))
    manifest = {
        "release": versions["corpus_release"],
        "revision": revision,
        "upstream": downloads,
        "documents": documents,
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    result = prepare()
    print(f"Prepared {len(result['documents'])} attributed public documentation excerpts.")
