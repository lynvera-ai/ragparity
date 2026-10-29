# Fresh bilingual Haystack evaluation

The unchanged application passed 22 of 46 new questions (47.8%). Engineering
review of every reply agrees with the frozen automatic result. The broader sample
exposes answer-relevance and abstention gaps despite faithful source quotations.
This application is not ready for general answer-quality acceptance.

| Result | Spanish | English | Total |
| --- | ---: | ---: | ---: |
| Passed | 10/23 | 12/23 | 22/46 |
| Failed | 13/23 | 11/23 | 24/46 |
| Request errors | 0 | 0 | 0 |

| Topic | Passed | Total |
| --- | ---: | ---: |
| JSON rules and parser/generator comparison | 0 | 14 |
| CSV format, optional behavior and field preservation | 7 | 10 |
| robots.txt matching, redirects, status and file location | 9 | 14 |
| Questions requiring abstention | 6 | 8 |

Of 38 answerable questions, 16 passed. Of eight questions requiring abstention,
six passed. Both language variants passed for nine paired cases; four pairs had
different outcomes between languages. The sample is deliberately varied, not a
statistical estimate for all users or domains.

## Method and evidence

Run: `20261029T151907Z-f699f8f8`, started 2026-10-29 at 15:19 UTC.
Serving Git revision: `439fbb967dbbebd160991c9f34405623600d9060` on
`feat/second-local-rag-pilot`. No serving code, dependencies, models, source files
or index were changed during this evaluation.

`fresh_questions.json` defines 23 new cases, each in Spanish and English. New
topics include duplicate member names, array types, numeric syntax, required
escaping, CSV record boundaries, case-sensitive paths, rule specificity and
redirects. Four cases test missing numeric values, unknown local configuration or
current information unavailable in static documents. The comparison case requires
two source sections and intentionally measures a limit beyond the current
single-passage contract.

References and expected dispositions were validated against the original pinned
RFC files and frozen before the first request. Normalized comparison against 128
distinct earlier questions found zero overlaps. Manual topic review also excluded
previous encoding, MIME, quote-escaping, cache, parsing-size and HTTP 5xx cases.
Only question text was sent to the local `/ask` endpoint. References, expected
answers and scoring rules remained offline. There were no retries to improve a
score, runtime adjustments or revised scoring expectations after seeing replies.

The original three RFCs and all 116 indexed fragments remain unchanged. Haystack
3.4.1 uses the existing local `nomic-embed-text:v1.5` and `qwen3:1.7b` models. No
paid account, cloud inference, new model or document download was used. The question
about a live origin did not trigger an external network request.

Private evidence directory:
`~/Library/Application Support/Lynvera/RAGParity/second-pilot/fresh-evaluations/20261029T151907Z-f699f8f8`.
It contains the frozen specification, exact runtime and evaluator snapshots,
model records, source manifest, 46 complete replies, timings and results. The
frozen file seal is
`4c100d5aad5d6dceff54bebe3f428aaf492b9a90c0db2619f9442e03099f1a2f`.
The unchanged index fingerprint is
`sha256:522e523da65e65b84cc6ebd8601d3460d09a6225eda9643b84013ab95814bbfc`.

`fresh_review.csv` records each automatic result, engineering assessment, reference
availability among candidates and raw response SHA-256. Review used the original
RFC text and displayed answers. No result was promoted from fail to pass. This is
an engineering review by the implementer, not independent human acceptance.
Earlier 18-case regression results and failure evidence remain separate.

## Findings

| Failure | Count | Evidence |
| --- | ---: | --- |
| False abstention | 9 | Unique object names, Infinity/NaN and path case sensitivity in both languages; CSV header and file location in Spanish; consistent CSV field counts in English. |
| Wrong or incomplete passage | 11 | Duplicate-name fragments omit the main rule; mixed arrays cite JSON text syntax; leading-zero questions cite precision limits; escaping questions cite Unicode interoperability. Spanish CSV counts and path specificity, and English Sitemaps boundaries also select the wrong passage. |
| Incomplete comparison | 2 | Parser section 9 is quoted, but generator section 10 is absent. |
| Unsupported answer | 2 | A question about today's origin status receives the RFC's general HTTP 4xx definition instead of abstention. No actual live status is established. |

Quotation integrity checks passed for all 46 operations: every displayed quotation
matched its pinned source slice, hash and retrieved-fragment linkage; abstentions
contained no evidence. This does not mean 46 correct answers. There were 31
answered replies and 15 abstentions, including the nine false abstentions. Related
but irrelevant quotations remain failures.

Several failures occur after usable evidence has been found. The English CSV
field-count question and path case-sensitivity question have correct reference
candidates but fail the lexical threshold with two distinct terms against three.
The English Sitemaps question selects the permissive paragraph even though the
group-boundary prohibition is present among candidates. Simply increasing retrieval
count would not resolve these examples.

The Spanish specificity and file-location questions were accepted as translated
even though their recorded search queries remained Spanish. Other false
abstentions also occur with English or successfully translated queries. Translation
validation, candidate ranking and abstention need separate checks; the language
gap cannot be attributed solely to translation.

The duplicate-name quotation starts at a page continuation and omits the main
explanation. Source-byte fidelity alone therefore does not establish a complete
semantic passage. The parser/generator comparison also confirms the declared
single-passage limitation.

## Follow-up priorities

1. Validate actual translation into the retrieval language while preserving
   identifiers. Add new holdout questions after making any changes.
2. Evaluate passage relevance and completeness beyond lexical overlap, including
   page continuations, short queries and competing adjacent rules.
3. Detect requests for current or user-specific facts that static sources cannot
   establish, even when related general rules are retrieved.
4. Support complete multi-passage answers or explicitly decline that scope.
5. Retain this run as regression evidence and obtain independent bilingual review.

These are observed application limits, not a benchmark of all Haystack systems.
The fresh question set has now been observed and is no longer an unseen holdout.

## Verification

Runtime, index and pinned model hashes matched the pre-run records for all 46
requests. The independent 116-fragment audit passed. All 296 unit tests passed
with 95.79% core coverage; lint, formatting and static type checks passed. The
evaluator's nonzero exit reflects the 24 recorded answer failures, with no request
errors. No application fix is included in this evaluation change.
