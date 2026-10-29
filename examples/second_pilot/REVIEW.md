# Second pilot review

This is an engineering evaluation of a separate, locally built Haystack application.
It is not independent human acceptance, a production deployment or a 1.0 release.
The same developer prepared the application and its evaluation cases. No cloud
inference, paid model service or new model download was used.

## Corpus and index

| Complete public document | Source bytes | Natural-language words | Fragments |
| --- | ---: | ---: | ---: |
| RFC 8259, JSON | 28,360 | 3,998 | 52 |
| RFC 4180, CSV | 12,931 | 1,690 | 19 |
| RFC 9309, Robots Exclusion Protocol | 25,265 | 2,965 | 45 |
| Total | 66,556 | 8,653 | 116 |

The index uses overlapping windows from the full original text, not repeated
single-fact fixtures. The original RFC formatting is retained. Space-delimited
splitter units include indentation; they are not natural-language word counts.
Source hashes and expected fragment hashes were frozen before Haystack splitting
or embedding. The independently computed boundaries matched the installed splitter.
The saved index audit passed for all three documents and 116 fragments.

The checker receives metadata only. Fragment hashes are calculated from the actual
stored content by the example adapter. Embeddings are generated and retrieved by
Haystack but their numerical correctness is outside the checker's contract. There
is no separate filesystem reader role or immutable live-snapshot attestation here.

## Evaluation design

Nine source-derived cases are asked in Spanish and English: JSON encoding and
literal names, CSV MIME type and quoting, robots.txt caching, parsing limits and
server-error behavior, plus two questions absent from the corpus. Only question
text is sent to the application. Reference patterns remain in the offline scorer.
The evaluator verifies reference passages against the pinned original RFCs and
retains runtime fingerprints, model records, the source manifest and full replies.

Passing the automatic screen requires expected answer content, a corresponding
retrieved passage, a normal generation finish and the requested language. The
language screen uses a small vocabulary and accepts short neutral technical labels.
It does not prove semantic equivalence or complete factuality. The complete replies
must still be reviewed. `human_review.csv` intentionally has blank acceptance fields.

## Earlier observations

The first complete run, `20261029T042929Z`, passed 12 of 18 automatic content/source
checks. Five Spanish questions retrieved unsuitable fragments. The English CSV
quoting case returned a relevant example without explaining the rule and failed
the wording check. These original replies and scores remain intact.

A second diagnostic added local query translation. It improved retrieval, but some
Spanish questions received English prose. That diagnostic was stopped after the
language defect was confirmed; it is not counted as a completed acceptance run.
Its partial results and stop reason are retained in private runtime storage.

The final flow translates Spanish queries with the existing local model, retains
English questions unchanged, and gives explicit language instructions to the answer
generator. Empty, oversized or numerically altered translations fall back to the
original query. This check does not establish that all translated names, units and
negations are preserved. Original questions, translated queries and generation
metadata are retained for review. The runtime has no answer table or reference-case
routing. Supported and unsupported answers still come from the retrieved passages
and local model, rather than a deterministic answer-copying policy.

## Persistence and controlled faults

Four checks used separate persisted copies of the native index. Reloading the
unaltered copy passed. Removing one fragment produced `MISSING_CHUNK`; changing
stored text produced `CHUNK_HASH_MISMATCH`; changing one version produced
`VERSION_MISMATCH` and `MIXED_CHUNK_VERSIONS`. All four checks behaved as expected.
The original index's byte hash was unchanged throughout.

## Display cleanup

Project files use ordinary punctuation in place of decorative separators. Open
WebUI now registers `RAGParity - Public documents`. Its six saved pilot chat titles
and stored model display names were updated after an online SQLite backup. The
application catalog and saved titles were read back to verify the change. Historical
answer bodies, screenshots and original evaluation receipts remain intact outside
Git. The original source/index audit still passes for 19 documents and fragments.

## Final completed run

Run `20261029T044507Z` executed all 18 questions against flow version 3. Automatic
checks passed 17 of 18 cases: 8 of 9 Spanish cases and all 9 English cases. The
Spanish server-error answer failed. Both unsupported questions abstained in both
languages. All 18 generations finished normally, without hitting the token cap.
No operational request errors or middle dots occurred in the final answers.

Reading every complete reply against the original RFCs found defects beyond the
screen's one failure. `engineering_review.csv` records 13 PASS, 4 FAIL and 1 REVIEW:

| Case | Finding | Required interpretation |
| --- | --- | --- |
| JSON encoding, Spanish | Older specifications are described as an exception to the current rule. | RFC 8259 section 8.1 requires UTF-8 outside a closed ecosystem. Historical behavior is not that rule's exception. |
| CSV quoting, English | The escaping rule is correct, but the answer cites section 6.1 of RFC 4180. | The applicable rule is section 2, item 7. |
| robots.txt parsing limit, Spanish | The 500 KiB minimum is correct, but undefined or unreachable files are added as exceptions to that limit. | RFC 9309 section 2.5 states the minimum without those exceptions. |
| robots.txt server errors, Spanish | The response says the file is defined and its rules should be followed. | Section 2.3.1.4 requires complete disallow while the file is unreachable, with separate longer-term options. |
| robots.txt caching, Spanish | The value and unreachable exception are correct, but obligation wording is stronger than the source's SHOULD NOT. | An independent reviewer should assess the Spanish wording against section 2.4. |

These findings are preserved rather than hidden by the automatic result. All
questions are now engineering regressions, not unseen held-out acceptance cases.
The checker correctly establishes fragment consistency, but that result does not
certify a generator's paraphrases, normative qualifiers or section citations.

The browser exercised one Spanish JSON question and one English CSV question.
Both displayed the requested language and a relevant source; opening a source
showed the actual retrieved RFC passage and its original URL. Private screenshots
and visible-text captures are stored under `ui-final`. The Spanish response also
contained an unnecessary sentence about exceptions, so UI success is not treated
as full factual acceptance.

The local suite passes 276 unit tests with 95.79% core coverage. Lint, formatting
and static typing pass. The original Open WebUI corpus still passes its independent
19-fragment audit. Project-file scans and the native model catalog/saved chat-title
checks found no remaining middle dots or decorative separators in authored text.
Historical raw evidence remains preserved outside the repository.

Before 1.0 acceptance, correct the four substantive response defects, resolve the
normative-language review, and obtain independent review using new questions. Add
larger corpora and sustained update/recovery runs. This pilot is complete as an
observed evaluation; it is not a claim that the generated chat is ready for 1.0.

The application was stopped and started again after the completed evaluation. Its
process identifier changed, the index byte hash remained identical, and the full
fragment audit still passed. Repeating the English CSV MIME question after restart
produced exactly the same answer, with a new native receipt. The private
`restart-evidence.json` records these checks. This is a process restart check,
not a claim of long-term recovery under every failure mode.
