# Second local RAG pilot

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

The application runs a Haystack pipeline: local query embedding, cosine retrieval
of four fragments, a prompt containing those fragments, and local generation.
Before retrieval, the same local generation model translates Spanish questions
into English. English queries are retained unchanged. The original question controls the response language. Empty, oversized
or numerically altered translations fall back to the original query. Translation
text and model metadata are retained in each receipt. This guard does not prove
that every name, unit or negation was translated correctly.

It uses `nomic-embed-text:v1.5` and `qwen3:1.7b`, with the digests pinned by the first
pilot. Generation uses temperature 0, seed 42, a 4096-token context and a maximum
of 256 output tokens. Thinking is disabled. These settings limit resource use;
model output is still evaluated rather than presumed correct.

## Run

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

Each private evaluation directory contains the full responses, retrieved text,
source identifiers, timings and scoring results. Automatic checks look for
answer content and a matching retrieved passage. They are an engineering screen,
not independent human acceptance or a proof that all generated claims are true.
The final run passed 17 of 18 automatic checks. Reading the complete replies
identified four factual or citation defects and one wording item needing review.
These are recorded in `engineering_review.csv`; the independent review form
remains blank.
Read `REVIEW.md` for observed results and remaining limitations.

AnythingLLM was considered first, but its image download failed when the host ran
out of space. The incomplete download was discarded, the isolated VM was
restarted, and the original Open WebUI data was retained. The smaller unused
`qwen3:0.6b` pilot model was removed. The two models used by both pilots remain.
This Haystack application completes the second pilot without another large image.
