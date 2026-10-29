# Synthetic product catalog pilot

This reproducible harness models ingestion into fragments, retrieval of a price fragment,
a structured answer fixture, and an audit against authoritative product metadata. It
uses invented product P100 and actual SHA-256 digests of fixed UTF-8 fixture strings.
It does not call a language model, perform semantic retrieval, or represent an independent
customer pilot. The deterministic answer fixture uses the contract a RAG application's
model output would supply.

```bash
python examples/catalog/pipeline.py --scenario synchronized
python examples/catalog/pipeline.py --scenario stale
python examples/catalog/pipeline.py --scenario missing-chunk
python examples/catalog/pipeline.py --scenario deleted
python examples/catalog/pipeline.py --scenario wrong-answer
python examples/catalog/pipeline.py --scenario partial
```

The first command exits 0; stale, missing-chunk, deleted and wrong-answer exit 1;
partial exits 3. JSON output explains each result. Source and index attest the same
completed snapshot except in the deliberate partial scenario. All scenarios are tested.

For actual PostgreSQL/pgvector retrieval, initialize the Compose fixture and run
`pytest -m integration`. The catalog integration test uses the SELECT-only account,
compares document and fragment metadata, retrieves the nearest synthetic vector through
a parameterized query, and compares its numeric price with the authoritative source.
These synthetic vectors demonstrate mechanics, not semantic retrieval quality.

To connect an application, replace the fixture readers with its immutable metadata
projections and completion manifests. Supply expected chunk hashes from its ingestion
contract and resolve numeric evidence from its authoritative source. Bind the observed
structured values and evidence references to the actual generated answer. Preserve the
snapshot and scope identifiers throughout the pipeline. Apply appropriate privacy
controls before sharing any reports.
