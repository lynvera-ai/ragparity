"""Bounded English/Spanish routing and an offline prose-language screen."""

import re


def request_language(question: str) -> str:
    spanish = re.search(
        r"[¿ñáéíóúü]|\b(?:segun|cual|cuales|que|como|cuanto|cuantas|"
        r"estos|estas|documentos|archivos|contraseña)\b",
        question.casefold(),
    )
    return "es" if spanish else "en"


def language_instruction(language: str) -> str:
    if language == "es":
        return (
            "Responde únicamente en español. Usa solo los fragmentos proporcionados. "
            "Explica la regla y sus excepciones de forma breve. Cita el identificador RFC. "
            "Si falta evidencia, indica que los documentos no contienen evidencia suficiente. "
            "No inventes ni calcules datos que falten. Usa texto plano, "
            "sin Markdown, viñetas ni separadores decorativos."
        )
    return (
        "Answer only in English. Use only the provided passages. "
        "Explain the rule and its exceptions briefly. Cite the RFC identifier. "
        "If evidence is missing, say the documents contain insufficient evidence. "
        "Do not invent or calculate missing facts. Use plain text "
        "without Markdown, bullets or decorative separators."
    )


def prose_language(text: str) -> str:
    """Screen obvious language mismatches; short technical labels can be neutral."""
    words = re.findall(r"[a-záéíóúñü]+", text.casefold())
    spanish = {
        "según",
        "debe",
        "deben",
        "el",
        "la",
        "los",
        "las",
        "en",
        "de",
        "se",
        "un",
        "una",
        "que",
        "por",
        "para",
        "no",
        "evidencia",
        "documentos",
        "insuficiente",
    }
    english = {
        "according",
        "the",
        "must",
        "should",
        "and",
        "of",
        "to",
        "be",
        "is",
        "are",
        "in",
        "a",
        "an",
        "that",
        "for",
        "not",
        "evidence",
        "documents",
        "insufficient",
    }
    es_count = sum(word in spanish for word in words)
    en_count = sum(word in english for word in words)
    if es_count == en_count == 0:
        return "neutral"
    return "es" if es_count > en_count else "en"
