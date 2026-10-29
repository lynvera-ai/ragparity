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

### Native Open WebUI chat integration

The corrected runtime is now installed as the native **RAGParity · Public documents**
Pipe function in the existing local Open WebUI instance. New chats select this mode by
default. It retrieves across the same nineteen public documents, forwards the current
pilot user's session to loopback endpoints and applies the version 5 subject, unit,
scope and bounded-selection rules. The interface shows the extracted value, source
link, exact fact excerpt and source conditions, or a clear abstention. Missing or
ambiguous units request clarification. Questions remain stateless and English-only.

`runtime.py` and `transport.py` are shared by the native function and host clients.
The read-only deployment bundle contains no benchmark question files, reference answers
or private account credentials. The native function uses the pinned image's
existing Python/Pydantic environment; it does not change the SDK dependency requirements.
Blocking HTTP runs off the application event loop, avoiding deadlock when retrieval
and selection call back into the same server. The function is restricted to the existing
pilot account. No additional server, listening port, model or package was installed.

Each completed turn writes a private receipt tied to its native chat and assistant
message identifiers, including retrieved evidence, selection request/response, rendered
answer, pinned versions and deployed code hashes. `review_ui.py` compares independently
recorded browser-visible text and citation links with those receipts and the reference
questions. It sends no chat requests and cannot create browser acceptance evidence by itself.

All twenty-five reference questions were entered through the actual browser chat on
October 28, 2026, in chat `508baaa0-d508-47f3-b482-af7c5f9034d5`. The final review found:

| Browser observation | Result |
| --- | --- |
| Supported PostgreSQL questions | 11 / 11 PASS |
| Supported planetary questions | 12 / 12 PASS |
| Unsupported population and time-specific temperature questions | 2 / 2 policy abstentions |
| Operational errors or invalid selections | 0 |
| Actual model-selection calls | 23 |
| Largest reported completion / configured cap | 6 / 24 tokens |
| Visible answer, native receipt, pinned deployment and citation agreement | 25 / 25 |

Mars mean temperature displayed **-65 °C**, with `mean-temperature` and `nasa-mars`;
the separate Mars diameter answer displayed **6792 km**. The two unsupported questions
made no model-selection request, so their abstentions are policy enforcement, not learned
model behavior. No token-repeat abort or generation error occurred. Reloading the chat
preserved both abstentions and the selected document mode. Metadata parity remained
PASS for nineteen documents and nineteen fragments after integration.

The private evidence is retained as `PILOT_HOME/ui-evidence/observations.json`, screenshots
in the same directory, `PILOT_HOME/ui-receipts/*.json`, `PILOT_HOME/ui-install.json` and
`PILOT_HOME/ui-report.json`. Exploratory chats and diagnostic captures remain separate
from the final twenty-five-question acceptance observations. Runtime files and credentials
are not committed. These engineering interface checks repeat a small frozen question set;
they are not independent human acceptance or a general accuracy benchmark.

The expanded automated suite passes **200 unit tests**, including same-server asynchronous
execution, session/role boundaries, input clarification, credential-free receipts,
deployment integrity and rejection of changed UI text, citations or message identifiers.
Core package coverage is 95.79%. Formatting, lint and static typing checks pass.

The integration applies only to **RAGParity · Public documents**. Other model selections
retain their ordinary chat behavior. Independent human acceptance, broader document and
application coverage, and longer operational trials remain necessary before 1.0.

### Spanish query and response support

Harness version 6 adds a bounded Spanish/English vocabulary to the shared runtime.
Spanish source names and measurement terms normalize to English retrieval terms, while
unknown words and all numbers remain present. Original questions, detected language and
normalized queries are retained in private evidence. The vocabulary contains no reference
answers, test IDs or assertions that an entity belongs to the corpus. Applicable subjects
still come from retrieved headings. English and Spanish coordinate-subject questions are
conservatively rejected when one scalar answer would omit another requested subject.

The native chat localizes answer labels, display units, status messages, clarification,
abstention and operational-error messages. Source quotes and conditions retain the original
English and are explicitly labeled. Structured evidence units and numeric strings remain
unchanged. Spanish dates, temporal terms and local geographic terms participate in the
same scope checks; a current or local reading must not become a static mean temperature.
The change adds no model, translation service, generated translation call or dependency.

`questions_es.json` provides twenty-five translated prompts and IDs only. Offline scoring
joins these prompts to the original independent reference values and support flags.
Neither this file nor the original reference files are deployed to the chat. The same
nineteen documents, full retrieval scope and pinned model digests remain in use.

The five-case Spanish smoke run `20261028T230836Z-9fe26055` passed all three supported
regressions and both policy abstentions. Diagnostic English run
`20261028T231007Z-4d2d3c93` overlapped an installation restart: sixteen supported cases
passed before nine connection/availability errors affected the remaining requests. It
exited with an operational-error status and is retained as a diagnostic, not acceptance
evidence. The complete English repetition was restarted after installation finished.

The preceding native-chat deployment and manifest are retained under
`PILOT_HOME/ui-deployments/4e6927157c9bec2c/`; earlier English browser evidence remains in
`PILOT_HOME/ui-evidence/` and `ui-report.json`. Spanish observations and their report are
kept separately. These are bounded engineering regressions; independent bilingual human
review and broader paraphrase/application coverage remain required before 1.0.

The stable English repetition `20261028T231356Z-d61aa464` passed 23/23 supported cases
and 2/2 policy abstentions with zero errors. After the final numeric-date, plural-location
and coordinated-unit checks were added, run `20261028T231936Z-20632a9b` repeated the same
23/23 and 2/2 result with zero errors or invalid selections. This final run shared the
local model service with the Spanish browser checks; no service restart occurred during
either acceptance run. These counts do not measure latency or independent model accuracy.

The final automated suite passes **219 unit tests**, with 95.79% core coverage. New cases
cover Spanish prompts, accent-free wording, source-subject aliases, unit ambiguity,
calendar and numeric dates, clock times, plural locations, Spanish presentation and
normalization provenance. Altered retrieved values still determine the answer, and
unsupported Spanish readings make no model-selection call. The original reference
values and source documents remain unchanged.

#### Final Spanish browser acceptance

All twenty-five Spanish reference prompts were submitted through the native chat in
`e0b47aba-65fd-4f4b-885d-5184363f8652`, using the final deployed code. Independent review
matched every visible response, native assistant-message receipt, selected mode, pinned
version, deployment hash and applicable official citation.

| Final check | Result |
| --- | --- |
| Supported Spanish PostgreSQL questions | 11 / 11 PASS |
| Supported Spanish planetary questions | 12 / 12 PASS |
| Spanish unsupported reference questions | 2 / 2 policy abstentions |
| Reference-question operational errors or invalid selections | 0 |
| Additional ordinary browser probes | 8 / 8 PASS |
| Model selections across all 33 browser turns | 25 |
| Largest reported completion / configured cap | 6 / 24 tokens |

The additional probes covered a missing unit, absent Sun, coordinated Mars/Sun subjects,
a slash-form date, polar temperature, two requested units, accent-free Spanish and a
switch back to English within the same chat. The first six produced the required
clarification or policy abstention without a model-selection call. Accent-free Spanish
returned the sourced Mars mean temperature of **-65 C**; the English turn returned the
sourced Jupiter diameter of **142984 km** with English presentation. Spanish reference
answers preserved negative rotation signs and the distinction between mean temperature
and diameter. No token-repeat abort or generation error occurred.

Browser observation briefly paused twice when its access checks timed out. Permitted
retries resumed observing the same pending messages; questions were not resubmitted and
each final browser observation matched exactly one native receipt. These tooling pauses
are separate from the recorded application results.

Private evidence is at `PILOT_HOME/ui-evidence-es/observations.json`, `probes.json`,
`probe-report.json` and screenshots in that directory, plus `PILOT_HOME/ui-report-es.json`
and the native receipts. The final read-only deployment and manifest are retained under
`PILOT_HOME/ui-deployments/47d8cf02a2215337/`. Earlier English evidence and reports remain
preserved. The source/index audit still passes for nineteen documents and fragments.
This establishes acceptance for the bounded pilot vocabulary and tested questions;
it does not establish arbitrary Spanish understanding or 1.0 readiness.

### New-question evaluation and update/recovery exercises

On October 28, 2026 local time (October 29 UTC), evaluation
`20261029T002903Z-32dfcb04` submitted **32 new prompts**, sixteen in each language, through
the installed native Open WebUI HTTP chat API. This was an engineering evaluation
created alongside the implementation; it was not independent human acceptance or a
new browser-interface run. The sixteen semantic cases are paired translations, not
thirty-two independent samples.

Before the first request, the driver wrote and sealed the questions, expected dispositions,
source-derived numeric references, pinned versions and unchanged runtime hashes. The
frozen protocol SHA-256 is
`ffa393baf2079815bf1d92cb480f4ba8295067c5c48f909a295538f9ff534f6b`.
Reference values came from independently verified cached PostgreSQL SGML and NASA HTML,
not retrieved index text. Requests contained only the ordinary native mode/transport
identifiers and user question. No expected unit, value, metric, source ID or support flag
was sent to the chat. Code and model selection were not tuned during the evaluation.

| Category | Correct / total |
| --- | --- |
| Supported extraction questions | 18 / 20 |
| Required abstentions | 6 / 10 |
| Required clarification | 2 / 2 |
| English overall | 13 / 16 |
| Spanish overall | 13 / 16 |
| Combined | **26 / 32** |
| Operational request errors | 0 |

Three measurement-selection defects occurred in both languages:

| Requested measurement | Observed response | Required behavior |
| --- | --- | --- |
| Mercury solar day | `1407.6 hours`, `rotation-period` | `4222.6 hours`, `length-of-day` |
| Explicitly listed Jupiter equatorial radius | `142984 km`, `diameter` | Abstain: no radius fact in these excerpts |
| Mars maximum temperature | `-65 C`, `mean-temperature` | Abstain: no maximum-temperature fact in these excerpts |

The model selected valid retrieved facts that did not answer the requested measurement.
A citation and matching source unit did not prevent these semantic errors. These remain
open beta defects; the earlier repeated reference-set success must not be generalized
into an accuracy claim. The six FAIL observations are preserved. An offline review
strengthened complete-null-field validation for abstentions and confirmed that all 32
verdicts remained unchanged without sending additional generation requests.

Private evaluation evidence is retained at `PILOT_HOME/evaluations/20261029T002903Z-32dfcb04/`,
including `frozen.json`, its checksum, executed code snapshots, requests, responses,
native receipts, `report.json` and the offline review. `new_review.csv` provides 32 blank
review rows; no independent reviewer verdict has been supplied. These questions become
regression cases after this run; future independent evaluation needs additional cases.

#### Operational scope and outcomes

Final operational run **`20261029T004802Z-0b77ab8f932e` passed all 29 checks**.
Operations used disposable attributed public copies with two paragraph fragments whose
expected offsets and hashes were computed before ingestion. Original source documents
and the chat's nineteen-file allowlist were not changed. Operational filenames and
projections occupy a separate scope; the auditor retained SELECT-only metadata access.

| Exercise | Observed acceptance |
| --- | --- |
| Initial two-fragment upload | PASS |
| Authoritative source changes before reindex | Expected FAIL detected: version/content/fragment mismatch |
| Content update and reindex | PASS |
| One deliberately removed test fragment | Expected FAIL detected: `MISSING_CHUNK` |
| Rebuild through the content-update API | PASS |
| Source deletion before index removal | Expected FAIL detected: `DELETED_PRESENT` |
| File deletion and re-upload recovery | PASS; the missing-fragment interval was detected |
| Coordinated application and database backup | PASS; hashes retained for 133 backup files |
| Restore into a new application volume and PostgreSQL cluster | PASS; original volumes were not mounted |
| Original nineteen-fragment audit after restore | PASS |
| Restored files, five saved chats and native function | PASS |
| New confirmed file written in the restored stack | PASS |
| Abrupt termination of both disposable services | Recovery PASS; PostgreSQL logs contain automatic crash recovery |
| Original corpus and new fragment hash after abrupt restart | PASS |
| Native retrieval/generation after restore and restart | PASS; sourced Mars mean temperature |
| Return to original services and delete only test copies | PASS; original nineteen-fragment audit and native answer passed |

WebUI was stopped before copying its complete data directory, including SQLite transaction
files. PostgreSQL was dumped while application writes were quiesced. The backup also
retained private authentication/configuration, allowlist and deployed code. Restoration
used a generated project, new named volumes and a different PostgreSQL system identifier;
container labels and mounts were checked before abrupt termination. Images, model cache,
loopback ports and network restrictions were retained. Native code was mounted read-only
from the backup. Model weights were not copied, so this is recovery using the existing
pinned model/runtime installation, not proof of offline recovery on a fresh machine.

The first diagnostic run `20261029T003657Z-e31f9c673310` restored the application successfully
but its canary check compared preliminary upload-response metadata and stopped. Reading
the stopped clone's complete SQLite database and transaction files confirmed the correct
committed file. The revised check reads the confirmed file record. Run
`20261029T004057Z-ab2f7d232b32` then passed 26 controls; the final run added full original-corpus
audits and verification of the canary's actual stored fragment hash. Diagnostic runs,
backups and stopped clones remain preserved; no earlier failure was overwritten.

Final private evidence is at `PILOT_HOME/operations/20261029T004802Z-0b77ab8f932e/`, including
source manifests, per-stage audit reports, journal, code/provenance copies, backup manifest,
recovery logs and report. Backups contain credentials and chat data and are not committed.
All live audit reports keep `snapshot_validated=false`; the exercise does not manufacture
immutable production audit attestations. It tests controlled sequencing and recovery,
not multi-day reliability or arbitrary concurrent writers.

The toolkit suite passes **224 unit tests**, including safeguards against mounting primary
volumes, mutating uncreated file IDs and accepting invalid abstentions. Core coverage is
95.79%; lint, formatting and static typing checks pass. Production readiness still needs
the three measurement defects resolved, independent acceptance and sustained operational
validation. No 1.0 tag or release was created.
