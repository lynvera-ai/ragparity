import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "second_ranking", Path("examples/second_pilot/ranking.py")
)
assert spec and spec.loader
ranking = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ranking)


def test_query_inflections_match_the_source():
    assert ranking.tokens("escape") == ranking.tokens("escaped")
    assert ranking.tokens("analysis") == ranking.tokens("parsing")
    assert ranking.tokens("cache") == ranking.tokens("cached")


def test_specific_rule_beats_neighboring_rules_and_original_units_survive():
    rows = [
        SimpleNamespace(quote="Files may be quoted inside fields."),
        SimpleNamespace(quote="An embedded quote must be escaped in the field."),
    ]
    picked, _ = ranking.choose(rows, "How is an embedded quote escaped inside a field?")
    assert picked == [rows[1]]
    rows = [SimpleNamespace(quote="The parsing limit is measured in mebibytes.")]
    picked, _ = ranking.choose(
        rows, "analysis limit in kilibytes? ¿Límite de análisis en mebibytes?"
    )
    assert picked == rows


def test_short_queries_require_all_terms_and_unrelated_questions_abstain():
    rows = [SimpleNamespace(quote="The workshop opens after an inspection.")]
    assert ranking.choose(rows, "workshop opens")[0] == rows
    assert ranking.choose(rows, "library opens")[0] == []
    assert ranking.choose(rows, "maximum lunar temperature")[0] == []
    assert ranking.choose([], "workshop opens")[0] == []
