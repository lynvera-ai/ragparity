from decimal import Context, Decimal, localcontext
from typing import Annotated

from pydantic import Field

from lynvera_ragparity.core import Finding, Severity, Status
from lynvera_ragparity.core.models import Contract

Number = Annotated[Decimal, Field(max_digits=50, decimal_places=20, allow_inf_nan=False)]
Tolerance = Annotated[Number, Field(ge=0)]
Label = Annotated[str, Field(min_length=1, pattern=r"\S")]


class NumericEvidence(Contract):
    value: Number | None = None
    unit: Label | None = None
    period: Label | None = None
    source_id: Label | None = None
    metric: Label | None = None


class NumericClaim(Contract):
    claim_id: Label
    expected: NumericEvidence | None = None
    observed: NumericEvidence | None = None
    absolute_tolerance: Tolerance = Decimal("0")
    relative_tolerance: Tolerance = Decimal("0")


def validate_claim(claim: NumericClaim) -> Finding:
    expected, observed = claim.expected, claim.observed
    evidence: dict[str, object] = {"claim_id": claim.claim_id}
    code, status = "CLAIM_NO_EVIDENCE", Status.INCONCLUSIVE
    recommendation = "Provide authoritative evidence and an observed structured claim."
    if expected is not None and observed is not None:
        missing = [
            f"{side}.{field}"
            for side, item in (("expected", expected), ("observed", observed))
            for field in NumericEvidence.model_fields
            if getattr(item, field) is None
        ]
        mismatched = [
            field
            for field in ("source_id", "metric", "unit", "period")
            if getattr(expected, field) != getattr(observed, field)
        ]
        if missing:
            evidence["fields"] = missing
        elif mismatched:
            code = "CLAIM_CONTEXT_MISMATCH"
            evidence["fields"] = mismatched
            recommendation = "Match source, metric, unit and period; no implicit conversions occur."
        else:
            assert expected.value is not None and observed.value is not None
            with localcontext(Context(prec=120)):
                difference = abs(expected.value - observed.value)
                tolerance = max(
                    claim.absolute_tolerance,
                    abs(expected.value) * claim.relative_tolerance,
                )
            status = Status.PASS if difference <= tolerance else Status.FAIL
            code = "CLAIM_MATCH" if status == Status.PASS else "CLAIM_VALUE_MISMATCH"
            evidence.update(
                expected=str(expected.value),
                observed=str(observed.value),
                difference=str(difference),
                tolerance=str(tolerance),
                unit=expected.unit,
                period=expected.period,
                metric=expected.metric,
            )
            recommendation = (
                "No action required."
                if status == Status.PASS
                else "Correct the claim using the authoritative value."
            )
    return Finding(
        code=code,
        status=status,
        severity=Severity.INFO
        if status == Status.PASS
        else (Severity.ERROR if status == Status.FAIL else Severity.WARNING),
        source="claim",
        source_id=expected.source_id if expected else None,
        evidence=evidence,
        recommendation=recommendation,
    )
