"""Synthetic ingestion, retrieval and structured answer audit; no language model is used."""

import argparse
import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.claims import (
    EvidenceReference,
    NumericClaim,
    NumericEvidence,
    validate_claim,
)
from lynvera_ragparity.core import CheckPolicy, CheckReport, Record, SnapshotEvidence
from lynvera_ragparity.indexes import MemoryIndex
from lynvera_ragparity.sources import MemorySource

CUTOFF = datetime(2026, 1, 1, tzinfo=UTC)
COMPLETED = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
REFERENCE = datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
SCENARIOS = ("synchronized", "stale", "missing-chunk", "deleted", "wrong-answer", "partial")


def digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(scenario: str = "synchronized") -> CheckReport:
    if scenario not in SCENARIOS:
        raise ValueError("Unknown catalog scenario")
    bodies = {"overview": "Product P100: desk lamp", "price": "P100 price: 49.90 USD"}
    source = Record(
        source_id="catalog",
        document_id="P100",
        source_version="2",
        collection="products",
        content_hash=digest("\n".join(bodies.values())),
        is_deleted=scenario == "deleted",
        snapshot_id="catalog-2026-01-01",
        updated_at=CUTOFF,
        expected_chunks={name: digest(body) for name, body in bodies.items()},
    )
    index = [
        Record(
            source_id=source.source_id,
            document_id=source.document_id,
            source_version="1" if scenario == "stale" else "2",
            content_hash=source.content_hash,
            collection=source.collection,
            is_deleted=False,
            snapshot_id=source.snapshot_id,
            chunk_id=name,
            chunk_hash=digest(body),
            indexed_at=COMPLETED,
        )
        for name, body in bodies.items()
    ]
    if scenario == "missing-chunk":
        index = index[:1]
    source_manifest = SnapshotEvidence(
        snapshot_id=source.snapshot_id,
        scope="catalog:products",
        as_of=CUTOFF,
        completed_at=COMPLETED,
        record_count=1,
    )
    index_manifest = source_manifest.model_copy(
        update={
            "record_count": len(index),
            "completed_at": None if scenario == "partial" else COMPLETED,
        }
    )
    report = ConsistencyChecker(
        CheckPolicy(
            identity_mode="chunk",
            require_snapshot=True,
            reference_time=REFERENCE,
            batch_size=1,
        )
    ).check(
        MemorySource([source]),
        MemoryIndex(index),
        source_snapshot=source_manifest,
        index_snapshot=index_manifest,
    )

    # This deterministic answer fixture exposes the same structured contract as a model output.
    retrieved_price = next((item for item in index if item.chunk_id == "price"), None)
    provenance = EvidenceReference(
        reference_id="catalog:P100:price", revision="2", retrieved_at=COMPLETED
    )
    authoritative = NumericEvidence(
        value=Decimal("49.90"),
        unit="USD",
        period="2026-01-01",
        source_id="catalog",
        metric="P100.price",
        provenance=provenance,
    )
    observed = None
    if retrieved_price is not None and not source.is_deleted:
        observed = authoritative.model_copy(
            update={
                "value": Decimal("39.90")
                if scenario in ("stale", "wrong-answer")
                else Decimal("49.90"),
                "provenance": provenance.model_copy(
                    update={"revision": retrieved_price.source_version}
                ),
            }
        )
    report.add(
        validate_claim(
            NumericClaim(
                claim_id="P100-price",
                expected=authoritative,
                observed=observed,
                require_provenance=True,
            )
        )
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="synchronized")
    args = parser.parse_args()
    result = run(args.scenario)
    print(result.model_dump_json(indent=2))
    raise SystemExit({"PASS": 0, "FAIL": 1, "ERROR": 2, "INCONCLUSIVE": 3}[result.status.value])


if __name__ == "__main__":
    main()
