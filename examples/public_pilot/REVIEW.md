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

The full run (harness 3, `20261028T194017Z-5c19a1f2`) produced:

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
failures blocked a 1.0 acceptance decision for that application configuration; they did not
invalidate the recorded metadata-parity result.

This is still a small English-language integration pilot in one application, with two
public source domains. Harness versions differ in schema, instructions and retrieval
scope, so their counts are not a controlled accuracy experiment. Independent review,
repeated sampling and a representative second application remain necessary before 1.0.


## Corrected evidence-selection runtime

Version 4 separates answerability, evidence selection, extraction and independent scoring.
The runtime receives only question text, an explicit unit, the actual retrieved passages
and a pinned local model. It cannot read the benchmark's expected number, document,
metric or support flag. The benchmark calls this same runtime and scores its answer later.
`ask.py` provides ordinary questions through the runtime without a benchmark reference.

Atomic facts bind subject, metric, value, unit, conditions and an exact quote span. The
model selects one row through a single-integer schema capped at 24 output tokens. The
structured answer then copies the complete fact, preventing a diameter from acquiring a
temperature unit. This is source extraction, not a claim that the model generated a correct
number. Original free generations remain preserved and are not rewritten.

Scope policy abstains before generation for absent units and local/time-specific readings
unsupported by the static source adapters. These are counted as **policy abstentions**,
separately from a model selecting `-1`. Invalid, truncated or out-of-range model outputs
never count as a correct abstention. Generation errors remain ERROR, with no automatic
retry or reference-value fallback. The former population token loop is avoided by never
asking the model to manufacture an answer without eligible evidence rows.

The smaller `qwen3:0.6b` selector correctly handled the two unsupported questions but
introduced over-abstention: run `20261028T212345Z-38d22109` verified 19 of 23 supported
questions and abstained on four valid PostgreSQL limits. Prompting alone did not reliably
resolve this regression. Those diagnostics and the preceding targeted trials remain saved.

The selector is now the local Apache-2.0 model
[`qwen3:1.7b`](https://ollama.com/library/qwen3:1.7b), pinned to its reviewed digest. It
requires an additional approximately 1.4 GB download; cloud inference and paid APIs remain
disabled. The initial switch exposed a stale application model catalog (HTTP 400, model
not found). Both entry points now refresh and validate the catalog before generation.
Run `20261028T213018Z-1ba883ec` retains that setup failure. Once corrected, the seven-case
regression run `20261028T213150Z-d6b51a19` verified all five supported questions and
produced both required policy abstentions without operational errors.

The documents, reference numbers and embedding model were unchanged. The answer protocol,
selector model and scope enforcement changed together, so before/after results cannot be
attributed solely to a model improvement or treated as a controlled accuracy benchmark.

### Repeated version 4 pilot

Both complete version 4 runs used the same frozen nineteen documents, twenty-three
reference questions, two negative questions and pinned models on the 8 GiB Apple M2.

| Run | Supported PASS / total | Correct negative abstentions | Errors | Selection calls |
| --- | --- | --- | --- | --- |
| `20261028T213259Z-15582b04` | 23 / 23 | 2 / 2 policy | 0 | 23 |
| `20261028T213710Z-be97dc11` | 23 / 23 | 2 / 2 policy | 0 | 23 |

Both runs extracted **-65 C**, metric `mean-temperature`, from the retrieved Mars document.
The population and time-specific Mars queries made no generation request: their explicit
policy abstentions are not evidence that the model independently learned to abstain.
All 46 actual model-selection calls completed without HTTP errors, invalid selections or
token-repeat aborts. The largest reported completion was six tokens, below the 24-token
budget. The two complete runs exited successfully. Both retained code snapshots match
their recorded SHA-256 digests. The post-run metadata audit still passed for 19 fragments.

These are deterministic regression repetitions at temperature zero, not independent users,
random sampling or proof of general accuracy. The runtime remains restricted to the two
static English document formats; its conservative scope rules can over-abstain. Ordinary
UI chats require their own integration and acceptance testing before sharing these guarantees.

### Subject applicability and ordinary-query probes

Four additional `ask.py` queries exercised the runtime outside the reference question files.
Version 4 extracted the correct Neptune mean temperature and Venus solar length of day,
but substituted Mercury for the Sun and Saturn for Titan. The failed queries remain at
`PILOT_HOME/queries/20261028T214140Z-1e7fb7fd/` and
`PILOT_HOME/queries/20261028T214147Z-8b81369f/`. Matching a unit and measurement alone
was not sufficient evidence that the requested subject was present.

Version 5 now requires exactly one subject explicitly named in the question and present
in the eligible retrieved facts. The names and software versions come from source headings,
not a planet allowlist or benchmark identifiers. Absent or ambiguous subjects cause a
policy abstention before generation. This stateless scope rule can reject pronouns and
indirect references; it does not claim general entity resolution.

The same four ordinary queries then produced:

| Question scope | Version 5 result | Private query ID |
| --- | --- | --- |
| Neptune mean temperature at one-bar pressure | `-200 C`, `mean-temperature`, `nasa-neptune` | `20261028T215513Z-3148ac0d` |
| Venus solar length of day | `2802.0 hours`, `length-of-day`, `nasa-venus` | `20261028T214440Z-15a09458` |
| Sun equatorial diameter | Policy abstention, `NO_EVIDENCE_FOR_SUBJECT` | `20261028T214443Z-46e51b9c` |
| Titan tropical orbital period | Policy abstention, `NO_EVIDENCE_FOR_SUBJECT` | `20261028T214444Z-f97dad4d` |

The Neptune probe was clarified to specify the source's one-bar condition for gas giants.
Earlier Neptune queries used imprecise "whole-surface" wording; those records remain
archived but are not acceptance evidence for that spatial condition. The final positive
values and applicable conditions were source-checked against the pinned table. These are engineering
probes, not independent human acceptance. The two additional abstentions are policy
decisions, not evidence of voluntary model abstention. Query records include exact
requests, retrieved passages, candidate facts, extracted answers and code snapshots.

### Final version 5 repetitions

| Run | Supported PASS / total | Correct negative abstentions | Errors | Selection calls |
| --- | --- | --- | --- | --- |
| `20261028T214445Z-fd555c5c` | 23 / 23 | 2 / 2 policy | 0 | 23 |
| `20261028T214840Z-6808116c` | 23 / 23 | 2 / 2 policy | 0 | 23 |

Both final runs used the subject-applicability policy and completed successfully. Mars
mean temperature remained **-65 C** with the correct metric and source. The former
unsupported questions abstained before generation. None of the 46 model selections
produced an HTTP error, invalid response or token-repeat abort. The largest reported
completion was six tokens, below the 24-token cap. Every selected quote span matched
the full actual retrieved text; retained harness source copies matched their recorded code hashes.

The final automated suite contains 190 passing unit tests, including reference/runtime
separation, altered retrieved values, absent and ambiguous subjects, source-label units,
invalid indices/types, token-budget exhaustion and safe operational-error recording.
The source/index audit remains PASS for nineteen documents and nineteen fragments.

Before 1.0, independently review normal usage, conditions and conservative rejection
rules, exercise another representative application and run longer operational trials.
This small repeated English-language pilot does not establish universal question-answering
accuracy, voluntary model abstention, multilingual coverage or guarantees for ordinary UI chats.
