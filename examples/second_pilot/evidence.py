"""Select exact retrieved source paragraphs and derive citations without model prose."""

import bisect
import hashlib
import re
from dataclasses import asdict, dataclass

HEADING = re.compile(
    r"^(?:(\d+(?:\.\d+)*)\. {2,}\S.*|Appendix ([A-Z])\. {2,}\S.*|"
    r"Author(?:s'|'s) Address(?:es)?)$",
    re.M,
)
ITEM = re.compile(r"^(\d+)\. {2,}")
NORMS = re.compile(
    r"\b(?:MUST NOT|SHALL NOT|SHOULD NOT|NOT RECOMMENDED|MUST|SHALL|"
    r"SHOULD|RECOMMENDED|MAY|OPTIONAL)\b"
)


@dataclass(frozen=True)
class Passage:
    document_id: str
    section: str | None
    item: str | None
    start: int
    end: int
    quote: str
    source_sha256: str
    url: str
    chunk_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {**asdict(self), "norms": NORMS.findall(self.quote)}


def paragraphs(document_id: str, text: str, url: str) -> list[Passage]:
    headings = list(HEADING.finditer(text))
    offsets = [heading.start() for heading in headings]
    checksum = hashlib.sha256(text.encode()).hexdigest()
    result = []
    for match in re.finditer(r"\S[^\n]*(?:\n(?![ \t]*\n)[^\n]*)*", text):
        raw = match.group().rstrip()
        start, end = match.start(), match.start() + len(raw)
        position = bisect.bisect_right(offsets, start) - 1
        if position < 0 or HEADING.fullmatch(raw):
            continue
        if re.search(r"\[Page \d+\]", raw) or re.match(r"RFC \d+\s", raw):
            continue
        item = ITEM.match(raw)
        result.append(
            Passage(
                document_id,
                headings[position].group(1) or headings[position].group(2),
                item.group(1) if item else None,
                start,
                end,
                raw,
                checksum,
                url,
            )
        )
    grouped = []
    position = 0
    while position < len(result):
        paragraph = result[position]
        count = 1
        if paragraph.quote.rstrip().endswith(":") and position + 1 < len(result):
            following = result[position + 1]
            line_start = text.rfind("\n", 0, following.start) + 1
            indented = following.start - line_start >= 6
            if indented and following.section == paragraph.section and following.item is None:
                end = following.end
                count = 2
                if position + 2 < len(result):
                    qualifier = result[position + 2]
                    if (
                        qualifier.section == paragraph.section
                        and qualifier.item is None
                        and NORMS.search(qualifier.quote)
                    ):
                        end = qualifier.end
                        count = 3
                if end - paragraph.start <= 1800:
                    paragraph = Passage(
                        **{**asdict(paragraph), "end": end, "quote": text[paragraph.start : end]}
                    )
                else:
                    count = 1
        grouped.append(paragraph)
        position += count
    return grouped


def candidates(documents, catalog: dict, texts: dict, question: str) -> list[Passage]:
    named = {"rfc" + n for n in re.findall(r"\bRFC\s*(\d{3,5})\b", question, re.I)}
    matches = {}
    for document in documents:
        ident = document.meta["document_id"]
        if named and ident.casefold() not in named:
            continue
        text = texts[ident]
        start = document.meta["split_idx_start"]
        end = start + len(document.content)
        if text[start:end] != document.content:
            raise ValueError("Retrieved fragment differs from its pinned source span")
        checksum = hashlib.sha256(text.encode()).hexdigest()
        if document.meta["source_version"] != checksum or document.meta["is_deleted"] is not False:
            raise ValueError("Retrieved fragment has invalid version or lifecycle metadata")
        if document.meta["content_hash"] != "sha256:" + checksum:
            raise ValueError("Retrieved fragment belongs to another source revision")
        for passage in catalog[ident]:
            if passage.start < end and passage.end > start and len(passage.quote) <= 1800:
                key = ident, passage.start
                if key not in matches:
                    matches[key] = [passage, set()]
                matches[key][1].add(document.meta["chunk_id"])
    # Keep retrieval ranking when limiting candidates, then order selected evidence by source.
    result = []
    for passage, chunk_ids in list(matches.values())[:24]:
        result.append(Passage(**{**asdict(passage), "chunk_ids": tuple(sorted(chunk_ids))}))
    return result


NORM_LABELS = {
    "es": {
        "MUST": "obligación",
        "SHALL": "obligación",
        "MUST NOT": "prohibición",
        "SHALL NOT": "prohibición",
        "SHOULD": "recomendación",
        "RECOMMENDED": "recomendación",
        "SHOULD NOT": "recomendación de no hacerlo; no es una prohibición absoluta",
        "NOT RECOMMENDED": "no recomendado",
        "MAY": "opción permitida",
        "OPTIONAL": "opcional",
    },
    "en": {
        "MUST": "requirement",
        "SHALL": "requirement",
        "MUST NOT": "prohibition",
        "SHALL NOT": "prohibition",
        "SHOULD": "recommendation",
        "RECOMMENDED": "recommendation",
        "SHOULD NOT": "recommendation against; not an absolute prohibition",
        "NOT RECOMMENDED": "not recommended",
        "MAY": "permitted option",
        "OPTIONAL": "optional",
    },
}


def render(passages: list[Passage], language: str) -> dict:
    if not passages:
        prose = (
            "Los documentos recuperados no contienen evidencia suficiente para responder."
            if language == "es"
            else "The retrieved documents contain insufficient evidence to answer."
        )
        return {"status": "ABSTAINED", "answer": prose, "answer_prose": prose, "evidence": []}
    header = (
        "Evidencia del documento. Cita original en inglés:"
        if language == "es"
        else "Document evidence. Original quotation in English:"
    )
    sections, prose = [header], [header]
    for passage in passages:
        ident = re.sub(r"^rfc", "RFC ", passage.document_id, flags=re.I)
        reference = ident
        if passage.section:
            kind = (
                (", apéndice " if language == "es" else ", appendix ")
                if passage.section.isalpha()
                else (", sección " if language == "es" else ", section ")
            )
            reference += kind + passage.section
        if passage.item:
            reference += (", punto " if language == "es" else ", item ") + passage.item
        citation = ("Fuente: " if language == "es" else "Source: ") + reference + "."
        labels = [
            term + ": " + NORM_LABELS[language][term] + "."
            for term in dict.fromkeys(NORMS.findall(passage.quote))
        ]
        sections.extend([passage.quote, *labels, citation])
        prose.extend([*labels, citation])
    return {
        "status": "ANSWERED",
        "answer": "\n\n".join(sections),
        "answer_prose": "\n\n".join(prose),
        "evidence": [p.as_dict() for p in passages],
    }
