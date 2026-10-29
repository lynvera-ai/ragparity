# Second local RAG pilot

Experimental example outside the supported library and CLI beta scope. Its latest
varied evaluation passed 22/46 and preserves 24 failures in [FRESH_REVIEW.md](FRESH_REVIEW.md).
Independent acceptance is pending. Start with [the core installation guide](../../docs/getting-started.md)
if you only need metadata or numeric checks.

This application uses Haystack 3.4.1 with its Ollama integration. It is separate from
Open WebUI and runs at http://127.0.0.1:3189. It uses the first pilot's existing local
model service. No paid account or remote inference is required.

The corpus contains the complete RFC 8259 (JSON), RFC 4180 (CSV), and RFC 9309
(robots.txt). Original bytes, attribution and copyright notices remain intact in
private runtime storage. These documents describe different topics and contain
rules across multiple sections. `versions.json` pins every source URL and SHA-256.
RFC 4180 is informational; the corpus does not claim all three documents have the
same standards status. Downloads retain the notices in each RFC. No extracted
code is redistributed by this example.

The index contains 116 fragments. The splitter uses 180 space-delimited units per
fragment with 30 units of overlap, including the RFCs' original whitespace. Those
units are not equivalent to 180 natural-language words in formatted RFC text.
An independent source implementation computes all expected boundaries and hashes
before the Haystack splitter or embedding model runs. RAGParity compares that
inventory with hashes calculated from the stored fragments.

The Haystack pipeline translates Spanish search queries locally, embeds the query,
and retrieves four fragments. English queries remain unchanged. Source bytes,
fragment offsets and revisions are verified before building complete supporting
passages. Lists and their following constraints remain together.

Selection is extractive. A document-local lexical score ranks complete source
passages using the translated query together with the original question. Keeping
the original terms helps retain technical identifiers and units. A passage needs
three distinct content-term matches, or all query terms when fewer than three
remain after normalization. Insufficient overlap produces an explicit abstention.
Basic inflections and analysis/parsing search vocabulary are normalized.

The response quotes the selected passage exactly, with its actual section and
numbered item. Spanish and English questions receive localized headers, citations
and normative labels; the quoted evidence remains in its original English.
SHOULD NOT is identified as a recommendation against an action, not an absolute
prohibition. The answer contains no model-authored explanations or section numbers.

The existing `nomic-embed-text:v1.5` model performs query embedding. The existing
`qwen3:1.7b` model is used only for Spanish search-query translation, with temperature
0, seed 42, a 2048-token context, a 160-token cap and thinking disabled. English
queries do not require generation. The receipt's legacy `generation` field sets
`skipped` to true for answers and explains that extraction was used; translation
metadata is recorded separately.

The pipeline supports questions answerable by one source passage. It does not
synthesize several rules, convert units or provide unverified source translations.
The overlap threshold is a bounded retrieval heuristic, not proof of semantic
relevance for every future query. Source hashes, quotation fidelity, lifecycle
metadata and citation boundaries are checked explicitly. Search translation still
needs broader independent acceptance for unfamiliar wording and domains.

## Run

This setup was exercised on Apple Silicon macOS. It assumes the first pilot's local
Ollama service is already prepared and has the two pinned models. A fresh core install
does not provide that service. The chat uses port 3189 and the model service uses 11445;
check availability before starting, and keep these services restricted to loopback.
Other platforms and a standalone portable chat installer remain unverified.
The `RAGPARITY_SECOND_HOME` override chooses a private runtime folder outside Git.

Start the first pilot's managed model service, then install the optional packages:

```bash
.venv/bin/pip install -r examples/second_pilot/requirements.txt
.venv/bin/python examples/second_pilot/manage.py prepare
.venv/bin/python examples/second_pilot/manage.py start
.venv/bin/python examples/second_pilot/manage.py evaluate
.venv/bin/python examples/second_pilot/manage.py audit
```

Run the persisted-copy checks with:

```bash
.venv/bin/python examples/second_pilot/probe.py
```

Run `prepare` only for a new installation. It refuses to replace an existing
index. `start` reuses it. To stop only this application:

```bash
.venv/bin/python examples/second_pilot/manage.py stop
```

Runtime files live in `~/Library/Application Support/Lynvera/RAGParity/second-pilot`,
outside the repository. `RAGPARITY_SECOND_HOME` can select another private local
folder. Keep the model service at `127.0.0.1:11445`. The chat binds to loopback and
blocks external connections while serving. Telemetry is disabled. The browser
loads local assets. Clicking an original-source link opens the public RFC site.

The JSON index contains text and embeddings. Its parent directory is private and
its file is readable only by the current user. The audit projection exports only
identities, lifecycle fields and hashes. This small application has no separate
database reader role. It is intended for one local user, not a shared deployment.
No immutable snapshot attestation is claimed for a live index audit.

## Evaluation

`questions.json` contains nine new cases in English and Spanish. Seven require
source-backed answers and two require abstention. The evaluator freezes its
questions, runtime hashes, model records and source manifest before sending any
request. Only question text goes to `/ask`; expected answers stay in the offline
scorer. References are checked against the original pinned RFCs.

Each private evaluation directory contains complete responses, retrieved fragments,
selected source spans, citation metadata, decisions and timings. The strengthened
offline scorer verifies the actual displayed quotation against pinned source bytes,
its hash, the expected citation and normative wording. It also detects extra text
outside the quoted evidence and localized explanation.

The corrected run passed all 18 original questions, nine per language, including
four abstentions. All five previous findings are closed in the engineering review.

These checks and the engineering review are regressions, not independent human
acceptance or a proof of universal answer relevance. The previous failing replies
remain preserved. Read `REVIEW.md` for the before-and-after results and remaining
limitations. The independent human-review form remains blank.

### Fresh questions

`fresh_questions.json` adds 23 paired cases with new topics and more varied tasks.
The unchanged service passed 22/46: 10/23 in Spanish and 12/23 in English.
Read [FRESH_REVIEW.md](FRESH_REVIEW.md) for the frozen method, all 24 failures and
follow-up priorities. `fresh_review.csv` preserves the per-question engineering
assessment and response hashes. These results are separate from the original
18-case regression.

To evaluate another unseen set against the already running service:

```bash
.venv/bin/python examples/second_pilot/evaluate_fresh.py --questions /path/to/new_questions.json
```

Use the same schema with new cases and authoritative source references. The
evaluator validates references, rejects normalized duplicates and earlier question
text, then freezes the questions, models, source manifest, index and code before
sending requests. It refuses to run on `main`. It exits with status 1 when a reply
fails, preserving every observation. The included set has already been executed;
the novelty guard rejects using it again as an unseen evaluation. Replay its
saved replies with the snapshotted scorer for offline analysis. Semantic novelty
also needs topic review; text normalization alone cannot reject all paraphrases.

AnythingLLM was considered first, but its image download failed when the host ran
out of space. The incomplete download was discarded, the isolated VM was
restarted, and the original Open WebUI data was retained. The smaller unused
`qwen3:0.6b` pilot model was removed. The two models used by both pilots remain.
This Haystack application completes the second pilot without another large image.
