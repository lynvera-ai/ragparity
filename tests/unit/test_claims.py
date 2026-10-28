from decimal import Decimal, getcontext

import pytest
from pydantic import ValidationError

from lynvera_ragparity.claims import NumericClaim, NumericEvidence, validate_claim
from lynvera_ragparity.core import Status


def evidence(value="0.3", **changes):
    return NumericEvidence.model_validate(
        {
            "value": value,
            "unit": "USD",
            "period": "2026-10",
            "source_id": "ledger",
            "metric": "revenue",
            **changes,
        }
    )


@pytest.mark.parametrize(
    ("value", "absolute", "relative", "status"),
    [
        ("0.3", "0", "0", Status.PASS),
        ("0.31", "0.01", "0", Status.PASS),
        ("0.31000000000000000001", "0.01", "0", Status.FAIL),
        ("0.33", "0", "0.1", Status.PASS),
        ("0.34", "0", "0.1", Status.FAIL),
    ],
)
def test_decimal_tolerances(value, absolute, relative, status):
    result = validate_claim(
        NumericClaim(
            claim_id="revenue",
            expected=evidence(),
            observed=evidence(value),
            absolute_tolerance=Decimal(absolute),
            relative_tolerance=Decimal(relative),
        )
    )
    assert result.status == status
    assert result.evidence["expected"] == "0.3"


@pytest.mark.parametrize("field", ["source_id", "unit", "period", "metric"])
def test_unverifiable_context(field):
    result = validate_claim(
        NumericClaim(
            claim_id="revenue",
            expected=evidence(),
            observed=evidence(**{field: "different"}),
        )
    )
    assert result.status == Status.INCONCLUSIVE
    assert result.code == "CLAIM_CONTEXT_MISMATCH"
    assert result.evidence["fields"] == [field]


@pytest.mark.parametrize(
    ("expected", "observed"),
    [
        (None, None),
        (None, evidence()),
        (evidence(), None),
    ],
)
def test_missing_evidence(expected, observed):
    result = validate_claim(NumericClaim(claim_id="revenue", expected=expected, observed=observed))
    assert result.status == Status.INCONCLUSIVE
    assert result.code == "CLAIM_NO_EVIDENCE"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e100", "1e-21"])
def test_invalid_numbers(value):
    with pytest.raises(ValidationError):
        evidence(value)


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_context(value):
    with pytest.raises(ValidationError):
        evidence(unit=value)


def test_negative_tolerance_rejected():
    with pytest.raises(ValidationError):
        NumericClaim(claim_id="bad", absolute_tolerance=Decimal("-1"))


def test_zero_expected_does_not_gain_relative_allowance():
    result = validate_claim(
        NumericClaim(
            claim_id="zero",
            expected=evidence("0"),
            observed=evidence("0.01"),
            relative_tolerance=Decimal("0.5"),
        )
    )
    assert result.status == Status.FAIL
    assert result.evidence["tolerance"] == "0"


def test_precision_does_not_depend_on_callers_context():
    previous = getcontext().prec
    previous_emax = getcontext().Emax
    try:
        getcontext().prec = 3
        getcontext().Emax = 5
        result = validate_claim(
            NumericClaim(
                claim_id="precise",
                expected=evidence("123456789012345678901234567890.12345678901234567890"),
                observed=evidence("123456789012345678901234567890.12345678901234567891"),
            )
        )
        assert result.status == Status.FAIL
        assert Decimal(result.evidence["difference"]) == Decimal("1e-20")
    finally:
        getcontext().prec = previous
        getcontext().Emax = previous_emax


@pytest.mark.parametrize("side", ["expected", "observed"])
@pytest.mark.parametrize("field", ["value", "unit", "period", "source_id", "metric"])
def test_partial_numeric_evidence_is_inconclusive(side, field):
    incomplete = evidence().model_dump(exclude={field})
    claim = NumericClaim.model_validate(
        {
            "claim_id": "partial",
            "expected": evidence(),
            "observed": evidence(),
            side: incomplete,
        }
    )
    result = validate_claim(claim)
    assert result.status == Status.INCONCLUSIVE
    assert result.code == "CLAIM_NO_EVIDENCE"
    assert result.evidence["fields"] == [f"{side}.{field}"]
