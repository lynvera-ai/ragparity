# Engineering review of the public-document pilot

## Original inconclusive answers

The original version 1 run is retained privately at `PILOT_HOME/reviews/initial-run.json`.
The authoritative reference is the PostgreSQL 17.6 limits table, commit
`7885b94dd81b98bbab9ed878680d156df7bf857f`, verified against its pinned bytes before
ingestion. This is an engineering source review, not independent user acceptance.

| Case | Source value | Original generated answer | Diagnosis |
| --- | --- | --- | --- |
| Relations per database | 1,431,650,303 relations | Value `1.431650303`, unit `1,431,650,303`, citation `relation-count` | Correct source retrieved and cited; numeric scale and unit are both wrong. |
| Columns per index | 32 columns under the default build; changing the limit requires recompilation | Value `1664`, unit `columns`, citation `result-columns` | Correct index passage was retrieved first; generation substituted a different measurement from a retrieved distractor. |

Both original findings remain `CLAIM_CONTEXT_MISMATCH` / INCONCLUSIVE. The checker
checks context before comparing numbers. Therefore the first finding exposes the unit
problem without establishing numeric correctness; the engineering review also identifies
the scale error. In the second case, 1664 is a real result-set limit, but it does not answer
the index question. Neither answer is useful as a verified response to the requested fact.

The expected reference documents were present among the three retrieved passages in both
cases. These observations identify generation/selection mistakes, not missing retrieval
of the correct source. They do not establish that retrieval is reliable for other questions.

## Changes exercised by the expanded pilot

- Keep the same small local generation and embedding models; no paid API or model upgrade.
- Keep three retrieved passages, now searched across both public document sets.
- Require an explicit metric ID alongside the cited document, preserving distinctions
  within a multi-measurement planetary excerpt.
- Clarify exact subject selection, signed decimal copying, no unit conversions and
  abstention when the requested fact is absent. These instructions are generic.
- Constrain generation to the requested unit contract and actual retrieved citation IDs.
  Do not provide the golden value, expected document ID or expected metric ID to generation.
- Version 3 also constrains metric IDs to every ID parsed from the actual retrieved
  passages, including distractors. This addresses formatting without choosing an answer.
- Retain raw answers, retrieved text and exact requests per run. Never rewrite model
  values or replace an inconclusive historical result with a later pass.

Regression tests retain the two original failure patterns, wrong-metric selection within
one document, wrong-source metadata and matching numbers with mismatched provenance.

## Expanded execution observations

Results are recorded after the real local execution completes. The expanded suite has
nineteen documents, twenty-three supported numeric questions and two unsupported questions.
The latter measure abstention separately and never add verified numeric claims.

The first expanded diagnostic run (harness 2, `20261028T193421Z-a22e4ff1`) produced
12 PASS and 11 INCONCLUSIVE supported answers. Eleven planetary numeric values and
document citations matched their references; the remaining temperature case was also
incorrect. Ten inconclusive metric IDs included their human labels (for example
`diameter; Equatorial diameter`). The checker correctly refused to equate these free-form
strings to canonical IDs. The unsupported population question
encountered an HTTP error; the time-specific Mars question incorrectly substituted a
diameter as a temperature. Neither negative case demonstrated correct abstention.
The diagnostic answers, requests and code snapshots are retained in that run directory.

The final full run (harness 3, `20261028T194017Z-5c19a1f2`) produced:

| Scope | Verified | Inconclusive | Operational errors |
| --- | --- | --- | --- |
| PostgreSQL supported questions | 11 | 0 | 0 |
| Planetary supported questions | 11 | 1 | 0 |
| Unsupported questions | Not applicable | 1 unsafe attempted answer | 1 generation failure |

Both original PostgreSQL cases now passed in the full expanded run: `1431650303 relations`
from `relation-count`, and `32 columns` from `index-columns`. Their historical answers
remain unverified. The new schema and instructions are part of this result; a later pass
does not reinterpret the old output.

For the planetary mean-temperature case, the source says **-65 C** for Mars, but the model
returned **6792 C**, citing the Mars document and metric `diameter`. It copied a true
diameter into the wrong measurement. The checker returned `CLAIM_CONTEXT_MISMATCH`, not
PASS. This remains a material generation defect despite the metric-format improvement.

Neither unsupported case demonstrated correct abstention. The time-specific Mars question
also returned `6792 C` / `diameter`; the harness retained it as an unsafe attempted answer
and never constructed a verified numeric claim. The Earth-population question returned
HTTP 500 with the diagnostic message `prediction aborted, token repeat limit reached`.
A single isolated diagnostic retry reproduced that failure. Its sanitized response is
retained at `PILOT_HOME/reviews/population-http-diagnostic.json`. It is an operational
generation failure, not an abstention or a verified answer. No automatic retries or
golden-value fallback hide either outcome.

The source/index audit passed for all nineteen documents and fragments. The application,
model server and metadata audit remain local. The remaining model-selection and abstention
failures block a 1.0 acceptance decision for this application configuration; they do not
invalidate the recorded metadata-parity result.

This is still a small English-language integration pilot in one application, with two
public source domains. Harness versions differ in schema, instructions and retrieval
scope, so their counts are not a controlled accuracy experiment. Independent review,
repeated sampling and a representative second application remain necessary before 1.0.
