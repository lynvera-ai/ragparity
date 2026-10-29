"""Bounded English/Spanish routing and an offline prose-language screen."""

import re


def request_language(question: str) -> str:
    spanish = re.search(
        r"[¿ñáéíóúü]|\b(?:segun|cual|cuales|que|como|cuanto|cuantas|"
        r"estos|estas|documentos|archivos|contraseña)\b",
        question.casefold(),
    )
    return "es" if spanish else "en"


def prose_language(text: str) -> str:
    """Screen obvious language mismatches; short technical labels can be neutral."""
    words = re.findall(r"[a-záéíóúñü]+", text.casefold())
    spanish = {
        "obligación",
        "fuente",
        "sección",
        "recomendación",
        "documento",
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
        "requirement",
        "source",
        "section",
        "recommendation",
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
