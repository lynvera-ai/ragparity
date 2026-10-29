import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def grounded(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("examples/public_pilot").resolve()))
    return importlib.import_module("grounded")


def planetary_context(value="-71", subject="Probe"):
    return {
        "document_id": "nasa-probe",
        "text": f"Planetary reference excerpt: {subject}\nDocument ID: nasa-probe\n"
        "Metric ID: diameter; Equatorial diameter: 9010 km.\n"
        f"Metric ID: mean-temperature; Mean temperature: {value} C.\n"
        "Metric ID: rotation-period; Sidereal rotation period: -18.5 hours.\n"
        "Metric ID: length-of-day; Solar length of day: 18.5 hours.\n\n"
        "Diameter is measured at the equator.\n"
        "Mean temperature is a whole-surface average.\n\n",
    }


def test_temperature_is_one_atomic_source_fact_and_keeps_its_quote(grounded):
    context = planetary_context()
    facts, reason = grounded.eligible_facts(
        "What mean temperature is listed for Probe?", "C", [context]
    )
    assert reason is None
    assert len(facts) == 1
    fact = facts[0]
    assert fact.subject == "Probe"
    assert fact.value == "-71"
    assert fact.metric == "mean-temperature"
    assert context["text"][fact.start : fact.end] == fact.quote
    answer, index = grounded.selected_answer('{"choice":0}', facts)
    assert index == 0
    assert answer == {
        "value": "-71",
        "unit": "C",
        "source_document_id": "nasa-probe",
        "metric": "mean-temperature",
    }
    # Changing only retrieved evidence changes the extracted answer, without any golden reference.
    changed, _ = grounded.eligible_facts(
        "Mean temperature of Probe?", "C", [planetary_context("-82.25")]
    )
    assert grounded.selected_answer('{"choice":0}', changed)[0]["value"] == "-82.25"


def test_same_unit_measurements_stay_distinct_and_selector_can_abstain(grounded):
    facts, _ = grounded.eligible_facts(
        "Sidereal rotation period of Probe?", "hours", [planetary_context()]
    )
    assert {fact.metric for fact in facts} == {"rotation-period"}
    with pytest.raises(ValueError):
        grounded.selected_answer('{"choice":1}', facts)
    assert grounded.selected_answer('{"choice":0}', facts)[0]["value"] == "-18.5"
    answer, index = grounded.selected_answer('{"choice":-1}', facts)
    assert index == -1
    assert all(value is None for value in answer.values())


@pytest.mark.parametrize(
    "raw",
    [
        '{"choice":2}',
        '{"choice":-2}',
        '{"choice":true}',
        '{"choice":"0"}',
        '{"choice":0,"value":"999"}',
        "not JSON",
    ],
)
def test_invalid_selection_never_becomes_a_successful_answer_or_abstention(grounded, raw):
    facts, _ = grounded.eligible_facts("Mean temperature of Probe?", "C", [planetary_context()])
    with pytest.raises(ValueError):
        grounded.selected_answer(raw, facts)


@pytest.mark.parametrize(
    "question",
    [
        "What temperature is recorded at the station?",
        "What is the temperature today?",
        "What is the temperature at 08:45?",
        "What was the temperature on 2031-02-06?",
        "What is the temperature at the south pole?",
    ],
)
def test_static_summary_cannot_answer_unseen_local_or_time_specific_questions(grounded, question):
    facts, reason = grounded.eligible_facts(question, "C", [planetary_context()])
    assert not facts
    assert reason == "STATIC_EVIDENCE_SCOPE"


def test_missing_unit_and_malformed_evidence_do_not_use_prior_knowledge(grounded):
    facts, reason = grounded.eligible_facts(
        "What revenue is listed for Probe?", "USD", [planetary_context()]
    )
    assert not facts
    assert reason == "NO_EVIDENCE_FOR_UNIT"
    # A fragment attributed to a different document is not acceptable evidence.
    context = planetary_context()
    context["document_id"] = "nasa-different"
    assert grounded.extract_facts([context]) == []
    assert grounded.extract_facts([planetary_context("1,2")])  # Other valid rows remain.
    assert not grounded.eligible_facts(
        "Mean temperature of Probe?", "C", [planetary_context("1,2")]
    )[0]


@pytest.mark.parametrize(
    "label,value,unit",
    [
        ("number of widgets", "1,234", "widgets"),
        ("columns in a result set", "1664", "columns"),
        ("relations per database", "100", "relations"),
        ("query parameters", "321", "parameters"),
        ("field size", "1 GB", "GB"),
    ],
)
def test_count_units_are_parsed_from_source_labels_not_the_requested_unit(
    grounded, label, value, unit
):
    context = {
        "document_id": "probe",
        "text": "Document ID: probe\n"
        f"Item: {label}\nUpper limit: {value}\nConditions: fixed build\n",
    }
    fact = grounded.extract_facts([context])[0]
    assert fact.unit == unit
    assert fact.conditions == "fixed build"
    assert grounded.eligible_facts("What limit?", "wrong-unit", [context])[0] == []


def test_runtime_answer_does_not_read_supported_flag_or_golden_value(grounded, monkeypatch):
    evaluator = importlib.import_module("evaluate")
    calls = []

    def request(url, payload, **kwargs):
        calls.append(payload)
        if url.endswith("/query/collection"):
            return {
                "documents": [[planetary_context()["text"]]],
                "metadatas": [[{"name": "rns-nasa-probe--" + "a" * 64 + ".txt"}]],
            }
        return {"choices": [{"message": {"content": '{"choice":0}'}, "finish_reason": "stop"}]}

    monkeypatch.setattr(evaluator, "request", request)
    versions = {"generation_model": "local", "nasa": {"release": "edition", "revision": "a" * 64}}
    question = {
        "id": "arbitrary",
        "question": "What mean temperature is listed for Probe?",
        "unit": "C",
        "value": "999",
        "document_id": "nasa-probe",
        "metric": "mean-temperature",
    }
    first = evaluator.evaluate_case(question, "private", {"probe": "file"}, versions, "nasa")
    second = evaluator.evaluate_case(
        {**question, "supported": False, "value": "111"},
        "private",
        {"probe": "file"},
        versions,
        "nasa",
    )
    assert first["status"] == "FAIL"  # Independent golden comparison still catches the difference.
    assert first["structured_answer"] == second["structured_answer"]
    assert second["structured_answer"]["value"] == "-71"
    assert not second["abstained"]  # Negative benchmark labels cannot force abstention.
    assert calls[1] == calls[3]
    assert "999" not in json.dumps(calls[1])


def test_invalid_model_selection_is_not_counted_as_correct_abstention(grounded, monkeypatch):
    evaluator = importlib.import_module("evaluate")

    def request(url, payload, **kwargs):
        if url.endswith("/query/collection"):
            return {
                "documents": [[planetary_context()["text"]]],
                "metadatas": [[{"name": "rns-nasa-probe--" + "a" * 64 + ".txt"}]],
            }
        return {"choices": [{"message": {"content": '{"choice":99}'}, "finish_reason": "stop"}]}

    monkeypatch.setattr(evaluator, "request", request)
    result = evaluator.evaluate_case(
        {"id": "q", "question": "Mean temperature of Probe?", "unit": "C", "supported": False},
        "private",
        {"probe": "file"},
        {"generation_model": "local"},
        "nasa",
    )
    assert result["answer_origin"] == "invalid_selection"
    assert result["status"] == "INCONCLUSIVE"
    assert not result["abstained"]


def test_application_model_catalog_is_refreshed_and_missing_model_stops_early(
    grounded, monkeypatch
):
    evaluator = importlib.import_module("evaluate")
    called = []

    def request(url, **kwargs):
        called.append(url)
        return {"data": [{"id": "new-local-model"}]}

    monkeypatch.setattr(evaluator, "request", request)
    evaluator.refresh_model_catalog("private-token", "new-local-model")
    assert called == [evaluator.APP_URL + "/api/models"]
    with pytest.raises(RuntimeError, match="not visible"):
        evaluator.refresh_model_catalog("private-token", "missing-model")


def test_budget_exhaustion_is_inconclusive_instead_of_a_valid_abstention(grounded, monkeypatch):
    evaluator = importlib.import_module("evaluate")

    def request(url, payload, **kwargs):
        if url.endswith("/query/collection"):
            return {
                "documents": [[planetary_context()["text"]]],
                "metadatas": [[{"name": "rns-nasa-probe--" + "a" * 64 + ".txt"}]],
            }
        return {"choices": [{"message": {"content": '{"choice":-1}'}, "finish_reason": "length"}]}

    monkeypatch.setattr(evaluator, "request", request)
    result = evaluator.answer_question(
        "Mean temperature of Probe?", "C", "private", {"probe": "file"}, "local"
    )
    assert result["status"] == "INCONCLUSIVE"
    assert result["answer_origin"] == "invalid_selection"


def test_absent_or_ambiguous_subject_cannot_borrow_a_matching_measurement(grounded):
    contexts = [planetary_context(subject="Probe")]
    facts, reason = grounded.eligible_facts(
        "What mean temperature is listed for Another?", "C", contexts
    )
    assert not facts
    assert reason == "NO_EVIDENCE_FOR_SUBJECT"
    assert not grounded.eligible_facts("What mean temperature?", "C", contexts)[0]
    second = planetary_context(subject="Another")
    second["document_id"] = "nasa-another"
    second["text"] = second["text"].replace("Document ID: nasa-probe", "Document ID: nasa-another")
    facts, reason = grounded.eligible_facts(
        "Compare mean temperatures for Probe and Another.", "C", [*contexts, second]
    )
    assert not facts
    assert reason == "AMBIGUOUS_SUBJECT"
    facts, reason = grounded.eligible_facts(
        "What mean temperature is listed for Another?", "C", [*contexts, second]
    )
    assert reason is None
    assert {fact.document_id for fact in facts} == {"nasa-another"}


@pytest.mark.parametrize(
    "question",
    [
        "How long is Probe's solar day, expressed in hours?",
        "What is the length of day in hours for Probe?",
        "Give the day length of Probe in hours.",
        "¿Cuántas horas dura el día solar de Probe?",
        "¿Cuál es la duración del día solar de Probe en horas?",
        "Que duracion solar del dia figura para Probe en horas?",
    ],
)
def test_measurement_filter_selects_solar_day_from_source_label_not_metric_id(grounded, question):
    context = planetary_context()
    context["text"] = context["text"].replace(
        "Metric ID: length-of-day; Solar length of day: 18.5 hours.",
        "Metric ID: different-identifier; Solar length of day: 237.125 hours.",
    )
    facts, reason = grounded.eligible_facts(question, "hours", [context])
    assert reason is None and len(facts) == 1
    assert facts[0].metric == "different-identifier"
    assert facts[0].value == "237.125"
    assert grounded.selected_answer('{"choice":0}', facts)[0]["value"] == "237.125"


@pytest.mark.parametrize(
    "question",
    [
        "What is the equatorial radius of Probe in km?",
        "¿Qué radio ecuatorial de Probe en km se indica?",
        "What maximum temperature in C is listed for Probe?",
        "¿Cuál es la temperatura máxima de Probe en C?",
        "Give the minimum temperature of Probe in C.",
        "¿Qué temperatura mínima tiene Probe en C?",
        "What median temperature in C is documented for Probe?",
        "What circumference in km is listed for Probe?",
    ],
)
def test_missing_quantity_or_statistic_cannot_borrow_same_unit_fact(grounded, question):
    unit = "km" if "km" in question else "C"
    facts, reason = grounded.eligible_facts(question, unit, [planetary_context()])
    assert facts == [] and reason == "NO_EVIDENCE_FOR_MEASUREMENT"


@pytest.mark.parametrize(
    "question,unit,metric,value",
    [
        ("What equatorial radius in km is listed for Probe?", "km", "radial-span", "4512.125"),
        ("¿Qué radio ecuatorial de Probe en km consta?", "km", "radial-span", "4512.125"),
        ("What maximum temperature in C is listed for Probe?", "C", "upper-temperature", "43.25"),
        ("¿Qué temperatura máxima de Probe en C figura?", "C", "upper-temperature", "43.25"),
    ],
)
def test_radius_and_maximum_are_accepted_when_that_actual_evidence_exists(
    grounded, question, unit, metric, value
):
    context = planetary_context()
    context["text"] += "\nMetric ID: radial-span; Equatorial radius: 4512.125 km.\n"
    context["text"] += "Metric ID: upper-temperature; Maximum temperature: 43.25 C.\n"
    facts, reason = grounded.eligible_facts(question, unit, [context])
    assert reason is None and len(facts) == 1
    assert grounded.selected_answer('{"choice":0}', facts)[0]["metric"] == metric
    assert facts[0].value == value


@pytest.mark.parametrize(
    "question",
    [
        (
            "What signed sidereal rotation period in hours is listed for Probe, "
            "rather than its solar length of day?"
        ),
        (
            "¿Qué período de rotación sideral de Probe en horas figura, "
            "en lugar de su duración solar del día?"
        ),
        "Give the sidereal day of Probe in hours, not its solar day.",
    ],
)
def test_excluded_comparison_clause_does_not_change_requested_measurement(grounded, question):
    facts, reason = grounded.eligible_facts(question, "hours", [planetary_context()])
    assert reason is None and [f.metric for f in facts] == ["rotation-period"]
    assert grounded.measurement_request(question)["excluded_clause"]


@pytest.mark.parametrize(
    "question,reason",
    [
        ("Compare the solar day and sidereal rotation of Probe in hours.", "AMBIGUOUS_MEASUREMENT"),
        ("Compara el día solar y la rotación sideral de Probe en horas.", "AMBIGUOUS_MEASUREMENT"),
        ("What period in hours is listed for Probe?", "MEASUREMENT_UNSPECIFIED"),
        ("What is half the equatorial diameter of Probe in km?", "DERIVED_MEASUREMENT_UNSUPPORTED"),
        (
            "¿Cuál es la mitad del diámetro ecuatorial de Probe en km?",
            "DERIVED_MEASUREMENT_UNSUPPORTED",
        ),
    ],
)
def test_ambiguous_and_derived_quantities_fail_closed(grounded, question, reason):
    unit = "km" if "km" in question else "hours"
    assert grounded.eligible_facts(question, unit, [planetary_context()]) == ([], reason)


@pytest.mark.parametrize(
    "question,unit",
    [
        ("What equatorial radius of Probe in km is documented?", "km"),
        ("¿Qué radio ecuatorial de Probe en km consta?", "km"),
        ("What maximum temperature of Probe in C is documented?", "C"),
        ("¿Qué temperatura máxima de Probe en C consta?", "C"),
    ],
)
def test_unsupported_measurements_abstain_before_generation(grounded, question, unit):
    runtime = importlib.import_module("runtime")
    calls = []

    def transport(url, payload, **kwargs):
        calls.append(payload)
        assert len(calls) == 1, "Unsupported measurements must not invoke generation"
        return {
            "documents": [[planetary_context()["text"]]],
            "metadatas": [[{"name": "rns-nasa-probe--" + "a" * 64 + ".txt"}]],
        }

    result = runtime.answer_question(
        question, unit, "session", {"probe": "file"}, "local", call=transport
    )
    assert result["status"] == "ABSTAINED"
    assert result["answer_origin"] == "policy_abstention"
    assert result["abstention_reason"] == "NO_EVIDENCE_FOR_MEASUREMENT"
    assert result["generation_request"] is None and len(calls) == 1
    assert result["measurement_request"]["kinds"]
    assert result["structured_answer"] == grounded.NULL_ANSWER


def test_unqualified_measurement_with_multiple_source_statistics_requires_clarification(grounded):
    context = planetary_context()
    context["text"] += "\nMetric ID: high; Maximum temperature: 44 C.\n"
    facts, reason = grounded.eligible_facts(
        "What temperature of Probe in C is documented?", "C", [context]
    )
    assert not facts and reason == "AMBIGUOUS_MEASUREMENT"
