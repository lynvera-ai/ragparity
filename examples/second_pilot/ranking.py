"""Reduce retrieved context with document-local lexical ranking, without reference answers."""

import math
import re
from collections import Counter

STOP = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "according",
    "be",
    "been",
    "by",
    "can",
    "do",
    "does",
    "for",
    "from",
    "has",
    "have",
    "how",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "these",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
}


def tokens(text: str) -> list[str]:
    text = re.sub(r"\brfc\s*\d+\b", "", text, flags=re.I)
    result = []
    for word in re.findall(r"\b[a-z0-9]+\b", text.casefold()):
        if word in STOP:
            continue
        if len(word) > 5 and word.endswith(("ing", "ed")):
            word = re.sub(r"(?:ing|ed)$", "", word)
        elif len(word) > 4 and word.endswith("s"):
            word = word[:-1]
        if len(word) > 4 and word.endswith("e"):
            word = word[:-1]
        # Technical searches use analysis and parsing for the same processing activity.
        if word == "analysi":
            word = "pars"
        result.append(word)
    return result


def rank(passages, query: str):
    query_words = set(tokens(query))
    counts = [Counter(tokens(p.quote)) for p in passages]

    def score(index):
        matched = sum(
            (math.log((len(passages) + 1) / (1 + sum(term in c for c in counts))) + 1)
            * min(counts[index][term], 2)
            for term in query_words
            if counts[index][term]
        )
        return matched / (1 + len(tokens(passages[index].quote)) / 200)

    return [passages[i] for i in sorted(range(len(passages)), key=lambda i: (-score(i), i))[:6]]


def choose(passages, query: str):
    ordered = rank(passages, query)
    content = set(tokens(query))
    required = min(3, len(content))
    matches = len(content.intersection(tokens(ordered[0].quote))) if ordered else 0
    supported = bool(ordered) and required > 0 and matches >= required
    return (ordered[:1] if supported else []), {
        "method": "lexical_overlap",
        "distinct_terms": matches,
        "required_terms": required,
        "reason": "supported_passage" if supported else "insufficient_query_overlap",
    }
