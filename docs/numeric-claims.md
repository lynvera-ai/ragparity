# Structured numeric claims

A numeric comparison needs two `NumericEvidence` objects: authoritative `expected`
evidence and the application's `observed` claim. Each contains `value`, `unit`, `period`,
`source_id`, and `metric`. The caller must supply evidence from a trusted source and
bind the observed structured result to the application answer it intends to audit.
Matching values alone cannot establish this provenance. Omitted or null evidence fields
produce `INCONCLUSIVE`; invalid types or malformed numbers are configuration errors.

```python
from decimal import Decimal
from lynvera_ragparity.claims import NumericClaim, NumericEvidence, validate_claim

expected = NumericEvidence(
    value=Decimal("1250.10"), unit="USD", period="2026-10",
    source_id="ledger", metric="revenue",
)
observed = expected.model_copy(update={"value": Decimal("1250.11")})
finding = validate_claim(NumericClaim(
    claim_id="october-revenue", expected=expected, observed=observed,
    absolute_tolerance=Decimal("0.01"),
))
assert finding.code == "CLAIM_MATCH"
```

Use decimal strings or `Decimal` values to avoid introducing binary floating-point
rounding before validation. Values allow up to 50 decimal digits and 20 fractional
digits. NaN, infinity, negative tolerances, and blank context labels are rejected.

The source, metric, unit, and period must match exactly. No unit or currency conversion
is attempted. A context mismatch or absent evidence is `INCONCLUSIVE`, even when the
numeric values happen to match. The acceptance rule is inclusive:

```text
abs(expected - observed) <= max(absolute_tolerance, abs(expected) * relative_tolerance)
```

Relative tolerance is a fraction (`0.01` means 1%). For an expected zero, only absolute
tolerance can allow a nonzero difference. The calculation uses a local decimal context
so caller rounding settings do not reduce comparison precision.

The CLI accepts `[[claims]]` with `[claims.expected]` and `[claims.observed]` in the
same TOML configuration. See [claims.toml](../examples/basic/claims.toml). Metadata
and claim statuses are combined conservatively. Call `validate_claim` directly for
standalone numeric checks; there is no heuristic extraction from free-form text.
