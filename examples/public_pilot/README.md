# Local public-document pilot

This pilot runs Open WebUI, native Ollama and PostgreSQL/pgvector on an Apple Silicon
Mac. It uses actual local embeddings, retrieval and language-model generation. No model
subscription, paid API, cloud model or hosted database is configured. Open WebUI retains
its original branding. Downloads need internet access; the models run locally afterward.

## Corpus and scope

The first corpus contains eleven attributed excerpts from the official PostgreSQL 17.6 limits
table, fixed to commit `7885b94dd81b98bbab9ed878680d156df7bf857f`:

[Original source](https://github.com/postgres/postgres/blob/7885b94dd81b98bbab9ed878680d156df7bf857f/doc/src/sgml/limits.sgml)

Topics cover database and relation counts, relation and field sizes, table and result-set
columns, index columns, partition keys, identifier length, function arguments and query
parameters. These are documentation limits under the stated build conditions, not
measurements or recommendations for the machine running the pilot.

`corpus.py` downloads the pinned source and its redistribution notice, verifies their
SHA-256 digests, checks the reviewed numeric references against the source table, and
prepares UTF-8 excerpts. Every uploaded excerpt includes the complete source notice.
The PostgreSQL documentation retains its own license; the surrounding toolkit code
remains Apache-2.0. Downloaded documents are kept outside version control.

`questions.json` holds eleven reference questions and explicit values and units.
This is a small, English-language integration corpus from one authoritative source.
It does not establish performance on unrelated documents, languages or customer workloads.

The second corpus contains eight multi-measurement planetary excerpts, one per planet,
from the [NASA/NSSDCA metric fact sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/)
and its [definitions](https://nssdc.gsfc.nasa.gov/planetary/factsheet/planetfact_notes.html).
The source editions are dated March 18, 2025 and December 20, 2021 respectively.
`nasa_questions.json` defines twelve supported questions and two intentionally unsupported
questions. Diameter, signed sidereal rotation, solar length of day, tropical orbital
period and mean temperature provide similar labels, decimals and negative values.
Moon and Pluto columns are parsed but are outside the uploaded eight-planet scope.

NASA source bytes are fixed by SHA-256, with a combined revision derived from both source
URLs and hashes. These upstream URLs are mutable: verified cached bytes are reused;
a changed fresh download fails rather than silently replacing the reference. The excerpts
credit the source and preserve relevant definitions. They contain factual numerical data
and paraphrased definitions, without logos or images. Generated responses belong to this
pilot and have not been reviewed or endorsed by NASA; see its
[usage guidance](https://www.nasa.gov/nasa-brand-center/images-and-media/).

## Components and resources

`versions.json` fixes application versions, container digests, the verified runtime
archive and model digests. The selected models are `qwen3:1.7b` for evidence selection and
`nomic-embed-text:v1.5` for embeddings. They are small local models; no inference-quality
guarantee is made.

The installer targets macOS on ARM64. Python 3.12+, Colima, Docker CLI, Docker Compose
and SSH must already be installed. The Python environment needs the package's `postgres`
extra. The setup uses an isolated `ragparity-public` Colima profile with two CPUs and
1.5 GiB RAM. It does not change the active Docker context or other profiles. Ollama
runs natively and loads at most one model at a time with a 4,096-token context.
The initial fresh download requires at least 8 GiB of available disk space. More space
may be needed for container caches, updates and later datasets.

Runtime files live outside the repository at
`~/Library/Application Support/Lynvera/RAGParity/public-pilot/`, including models, source
documents, private credentials and generated reports. This path is called `PILOT_HOME`
below; it is a documentation shorthand. Set `RAGPARITY_PILOT_HOME` to override it.
Container volumes are retained in this pilot's VM; Colima and Ollama may also keep their
normal per-user management metadata outside this directory. Nothing is installed globally by the pilot script and no
login/startup service is registered with macOS.

## Install and start

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[postgres]'
.venv/bin/python examples/public_pilot/manage.py install
.venv/bin/python examples/public_pilot/manage.py ingest
.venv/bin/python examples/public_pilot/manage.py audit
.venv/bin/python examples/public_pilot/webui_install.py install
```

The installer verifies the native runtime before extraction, starts the services, checks
model digests and prepares the corpus. Ingestion creates one local application account
and uploads documents through Open WebUI's real processing API. It then provisions a
separate SELECT-only audit role. Repeated completed uploads are reused rather than
silently duplicated. An incomplete upload requires inspection before retrying.

Open **http://127.0.0.1:3188**. The account details are in `PILOT_HOME/login.txt`, which
is private to the local user. Do not commit or share this file. Additional account signup
is disabled. New chats select **RAGParity - Public documents** after the integration is
installed. Ask in English or Spanish, name one subject and include the requested unit,
for example: "¿Qué temperatura media de toda la superficie en grados C figura para Marte?"
The response follows the question language. Source excerpts and conditions remain in
their original English, explicitly labeled in Spanish responses. The mode uses the
nineteen loaded documents automatically; do not attach additional files. It shows the
extracted value, citation, excerpt and applicable source conditions, or a clear abstention.
Missing or ambiguous units ask for clarification. It uses the same stateless subject,
scope and evidence-selection rules as the CLI client.

The planetary uploads start with `rns-`. Both the chat mode and automatic harness retrieve
their top three passages
from **all nineteen uploaded documents**, even when selecting only one question set.
`--dataset` selects questions, not a narrower or oracle-selected retrieval scope.

Connections use explicit SSH tunnels: the web UI is on `127.0.0.1:3188`, database on
`127.0.0.1:55433`, and model server on `127.0.0.1:11445`. Container services bind only
inside the VM's loopback interface. No pilot service is exposed to the LAN. Ollama's
cloud features are disabled. The application has no configured paid-provider credentials.

```bash
.venv/bin/python examples/public_pilot/manage.py status
.venv/bin/python examples/public_pilot/manage.py start
.venv/bin/python examples/public_pilot/manage.py stop
```

`stop` retains models, documents, chats and database volumes. `start` restores the local
services and tunnels. It does not delete existing data. The private runtime logs help
troubleshoot startup failures. If the selected ports are occupied by other services,
resolve the conflict before starting; the script does not stop those services.

## Metadata audit

The source manifest and expected fragment hashes are computed from the pinned documents
before upload. They are not copied from the index being checked. The small excerpts
fit one 4,096-character fragment each; the expected fragment start offset is zero.
The audit compares the application's actual stored document hash, version-bearing
filename, fragment start offset and SHA-256 of its stored fragment text.

A projection view computes these values in PostgreSQL. The audit role can read the
source metadata and projection, but cannot read base document text or embeddings and
has no write privileges. It runs through the existing PostgreSQL and pgvector readers.
The audit scope is the pilot's `rpg-` and `rns-` files in their per-file collections. Other uploads
and any additional knowledge-collection copies are outside this scope.

The application tables are live. The pilot does not manufacture completed snapshot
attestations for them: `audit.snapshot_validated` remains false. Run the audit while
ingestion is idle. A coordinated production audit still needs authoritative immutable
projections and completion evidence as described in `docs/audits.md`.

Generated files are `PILOT_HOME/metadata-report.json` and `metadata-report.html`.

## Automatic structured answer observations

```bash
.venv/bin/python examples/public_pilot/evaluate.py
.venv/bin/python examples/public_pilot/evaluate.py --dataset nasa
.venv/bin/python examples/public_pilot/evaluate.py --case relation-count --case index-columns
```

Harness version 7 adds a planetary measurement contract to the bilingual retrieval,
evidence selection and extraction flow. It retrieves three
real indexed excerpts across both corpora. `grounded.py` parses atomic facts from the
pilot's two fixed document formats, retaining subject, label, unit, conditions and exact
quote offsets. It filters by the caller's explicit unit contract. The local model selects
one evidence row or `-1`; it does not generate a number, unit, metric or citation. A selected
answer copies all four fields from the **same retrieved fact**. No golden reference value,
expected document ID, expected metric or benchmark support flag enters this runtime path.
The benchmark independently checks the resulting structured answer afterward.

Before model selection, the planetary adapter compares the requested measurement
with labels in the actual retrieved facts. Its bounded vocabulary separates solar day,
sidereal rotation, orbital period, diameter, radius and temperature statistics. Requested
qualifiers must be present in the source label. Explicit exclusions such as "rather than"
are excluded only from this contract, while the full question is retained for retrieval,
generation and evidence. Multiple measures, unrecognized measures and requested derived
values cause policy abstention. PostgreSQL upper-limit rows keep their existing path.

The runtime records `measurement_request` with the requested kinds, qualifiers, excluded
clause flag and derivation flag. It contains no reference values or expected source IDs.
The selector only sees compatible facts and its returned index is checked against that
filtered list. If a source actually documents a radius or maximum, that row remains
eligible; there is no blanket ban on those quantities. The gate is a source-adapter rule,
not learned model abstention or general natural-language understanding.

The selection schema contains one integer and allows at most 24 generated tokens. There
are no automatic retries or fallbacks to reference values. Errors, malformed selections,
out-of-range indices and token-budget exhaustion never count as a successful answer or
abstention. Qualifying default-build and size conditions remain attached to each fact.

These adapters support **English static-document facts**, queried in English or Spanish. They conservatively abstain
before generation when no fact has the requested unit or explicitly named subject,
when multiple source subjects are requested in one scalar answer, or when a query requests a local
or time-specific observation, current data or a recorded reading absent from these static
summaries. This scope policy is not a general natural-language understanding system. Its
rules can reject valid paraphrases or pronouns and require a different adapter for timestamped data.
Subjects and software versions are matched against actual retrieved headings after
query normalization. The bilingual term dictionary translates entity names but does not
assert corpus membership or consult expected document identifiers.
`policy_abstentions` and model-selected `-1` decisions are counted separately. The two
negative benchmark questions never count as verified numeric claims.

Every execution gets its own `PILOT_HOME/runs/<run-id>/` directory with full retrieved
passages/hashes, eligible facts and quote offsets, exact requests, raw selections, extracted
answers, observed runtime/model versions, code copies and a summary. The latest answers
also appear in `PILOT_HOME/answers.json`. Earlier raw generations and diagnostic failures
remain in their original run directories. Exit codes are 0 for verified supported answers
plus correct abstentions, 1 for numeric mismatches, 2 for operational errors and 3 for
inconclusive supported cases, invalid selections or failure to abstain.

For an ordinary question outside the benchmark, use the same corrected runtime:

```bash
.venv/bin/python examples/public_pilot/ask.py --unit C \
  "What whole-surface mean temperature in degrees C is listed for Mars?"
.venv/bin/python examples/public_pilot/ask.py --unit people \
  "What human population count for Earth is given in the supplied planetary excerpts?"
```

`ask.py` accepts only question text and a source unit. It reads no benchmark question files
and has no golden-answer arguments. It reports `ANSWERED`, `ABSTAINED`, `INCONCLUSIVE` or
`ERROR`, saving private evidence/code copies in `PILOT_HOME/queries/`. `ANSWERED` means
extracted from retrieved evidence; it does not assert independent golden verification.

The same `runtime.py`, `grounded.py`, `language.py` and HTTP transport run in the native Open WebUI
Pipe function as well as the host clients. The read-only deployment bundle contains no
benchmark questions or golden answers, database passwords or saved account tokens. The
function forwards the current signed-in user's session to loopback retrieval and selection
requests and is restricted to the existing local pilot account. Blocking HTTP runs in a
worker thread so calls back into the same application do not block its event loop. No
additional server, listening port, model or Python package is installed for this integration.

Only **RAGParity - Public documents** uses these rules. Other model choices retain the
application's ordinary chat behavior. The native function uses the pinned image's existing
Python/Pydantic environment; it does not install or change the toolkit's dependency contract.
The adapter's shared runtime does not import the toolkit's benchmark/scoring code.

To update the installed code, rerun `webui_install.py install`. It rebuilds the private,
hashed bundle and recreates only this pilot's WebUI container, retaining chats and volumes.
Separately edited function code is rejected rather than overwritten. Installation is
idempotent; signup and loopback network restrictions remain in force.

`language.py` uses a bounded bilingual domain vocabulary for query normalization and
presentation. It handles accents, Spanish source-subject names and measurement units,
while preserving unknown words and numbers. It is not a general translator: unfamiliar
wording, pronouns and ambiguous subjects can still require clarification or abstention.
Local/time-specific scope checks apply to Spanish dates and locations as well as English.
No translation service, extra model call, paid API or new dependency is used. Receipts
retain the original question, detected language and normalized query. Model selection
remains capped at 24 output tokens and copies a complete retrieved fact.

`questions_es.json` contains only translated test prompts and IDs. The scorer joins them
with the unchanged independent references; this file is never deployed to the chat runtime.
Repeat the Spanish harness and review separately captured Spanish browser evidence with:

```bash
.venv/bin/python examples/public_pilot/evaluate.py --language es
.venv/bin/python examples/public_pilot/review_ui.py --language es \
  --observations /path/to/spanish-observations.json
```

The Spanish browser report is `PILOT_HOME/ui-report-es.json`, leaving the original
English report in place. Language selection affects question text and presentation;
source documents, reference values, model digests and retrieval scope remain unchanged.

Each completed UI turn writes a private receipt inside the application's existing data
volume, linked to the chat and assistant message. To export and score UI observations:

```bash
.venv/bin/python examples/public_pilot/webui_install.py collect
.venv/bin/python examples/public_pilot/review_ui.py --observations /path/to/observations.json
```

Browser observations must record each reference question once, the visible response,
selected mode, chat URL and visible citation links. `review_ui.py` sends no messages: it
checks these observations against native receipts, deployed code hashes, pinned source
links and independent reference values. An API-only run is not browser evidence. Receipts,
observations, screenshots and `ui-report.json` stay in the private runtime directory.

The initial version 1 run on October 28, 2026 on an 8 GiB Apple M2 produced:

- Metadata parity: 11 source documents, 11 indexed fragments, 11 `CHUNKS_SYNCED`, PASS.
- Eleven structured questions: 9 PASS, 2 INCONCLUSIVE, 0 FAIL, 0 ERROR.
- Inconclusive cases: relation count returned an invalid unit; index columns cited the
  result-set columns document. Both require review and are not verified answers.

An initial three-question smoke run had rejected comma-formatted numeric strings. That
version 1 harness constrained generation to canonical decimal strings instead of heuristically
rewriting answers. The observed results are integration observations, not an accuracy
benchmark or a 1.0 acceptance decision. Repeated execution results are recorded in
[REVIEW.md](REVIEW.md). Independent human review and multi-day application use remain outstanding.

The original eleven answers are retained at `PILOT_HOME/reviews/initial-run.json`.
The engineering review of the two inconclusive answers is in [REVIEW.md](REVIEW.md),
including the subsequent expanded-run observations. A changed schema and a larger
retrieval scope prevent treating before/after counts as a controlled accuracy comparison.

## New bilingual evaluation and recovery exercises

`new_questions.json` defines sixteen new question pairs, thirty-two prompts in total.
They cover previously untested planet/measurement combinations, new PostgreSQL phrasing,
unsupported measurements and clarification. `new_evaluation.py` fixes the questions,
independent references, runtime hashes and pinned versions before the first request.
References are read from verified authoritative source bytes, never from the index.
Only question text and ordinary transport identifiers enter the native chat HTTP API.
The offline scorer checks the native response against its private receipt and reference.
This is API acceptance evidence, not another browser run or independent human review.

```bash
.venv/bin/python examples/public_pilot/new_evaluation.py
.venv/bin/python examples/public_pilot/new_evaluation.py \
  --questions examples/public_pilot/measurement_probes.json
.venv/bin/python examples/public_pilot/operations.py
```

Evaluation runs stay at `PILOT_HOME/evaluations/<run-id>/`, including the sealed protocol,
code copies, exact requests, responses, receipts and report. Exit status 1 means an answer
acceptance failure and 2 an operational error. The initial new-question result was **26/32**: it exposed confusion between Mercury's
solar day and sidereal rotation, Jupiter's radius and diameter, and Mars's maximum and mean
temperature, in both languages. Version 7 adds the measurement contract and the repeat passed **32/32**. Sixteen
additional bilingual variants also passed. The original failed report is retained. See
[REVIEW.md](REVIEW.md) for the recorded cases. Use the blank [new_review.csv](new_review.csv)
for independent human review; no reviewer decisions have been filled automatically.

The operational runner creates its own public copy with two independently specified
paragraph fragments. Its files use `rpo-operations-` names and never enter the nineteen-file
chat allowlist or the original metadata-audit scope. Source expectations precede ingestion.
It checks stale content, updated text, reindexing, an explicitly removed test fragment,
delete propagation and recovery by re-upload. Indexed-text edits use the application's
content-update endpoint; that endpoint does not replace the originally uploaded bytes.

The runner then pauses this pilot's WebUI to copy its complete data directory, including
SQLite transaction files, and dumps PostgreSQL while application writes are quiesced.
The backup includes the private runtime configuration, authentication material, allowlist
and deployed code. It restores into a generated recovery project with **new named volumes**,
validates a different PostgreSQL cluster identity, and checks the original corpus, files,
chats and function. It writes a new canary file, abruptly stops only the verified recovery
containers, restarts them and checks committed data, fragment hashes and native answers.
The original containers and volumes are retained and restarted in `finally`; disposable
original-stack test files are deleted by their run-created IDs only. Recovery containers
and volumes remain stopped for inspection. No volume-removal command is issued.

This exercise temporarily interrupts the local UI and uses its existing loopback ports.
Do not run it alongside other evaluations or interactive edits. One operational runner
is allowed at a time. It uses the cached pinned images and existing native model server;
no new service provider, public port or paid dependency is configured. Model weights are
not copied into the backup: restoration requires the existing pinned runtime/model cache
or their verified reinstallation. Backups and clone configuration contain credentials
and chat data; keep them private outside Git. Reports, source/code copies, checksums and
journals stay at `PILOT_HOME/operations/<run-id>/`.

If the runner itself is forcibly interrupted, use its private `recovery-compose.json`
and generated project name from `provenance.json` to stop only that recovery project,
with `manage.docker_environment()` selecting the isolated `ragparity-public` engine.
Then run `manage.py start` to bring back the retained original volumes. Do not copy a
backup over the original volumes. These controlled tests do not replace sustained use,
independent review or a production disaster-recovery procedure.

## Human review before 1.0

Use `review.csv` and `nasa_review.csv` as review forms. The two original PostgreSQL failures
have engineering source-review notes; the remaining fields await human review.
Check the full question, build conditions,
retrieved passage, cited document, value and unit. Also try questions outside this corpus
and confirm that unsupported answers are not treated as verified. Recheck metadata
after controlled reindexing or deletion of pilot copies. Keep source documents immutable;
changes to a test copy must be recorded as deliberate pilot interventions.

Have an independent reviewer evaluate ordinary UI use and the two inconclusive cases.
Record reproducible problems without uploading credentials or private application data.
Resolve material findings and repeat the evaluation on another representative application
scope before declaring 1.0 stability. The stable-release decision remains with the maintainer.
