from datetime import datetime

from lynvera_ragparity.core import CheckReport, SnapshotEvidence


def snapshot_issues(
    source: SnapshotEvidence | None,
    index: SnapshotEvidence | None,
    report: CheckReport,
    reference_time: datetime,
    required: bool,
) -> list[tuple[str, str]]:
    """Validate declared completion evidence; this does not establish its provenance."""
    if source is None and index is None and not required:
        return []
    if source is None or index is None:
        return [("SNAPSHOT_MISSING", "Provide completion manifests for both scans.")]
    issues = []
    if any(
        item.completed_at is None or item.completed_at > reference_time for item in (source, index)
    ):
        issues.append(("SNAPSHOT_INCOMPLETE", "Wait for both immutable snapshots to complete."))
    if (source.snapshot_id, source.scope, source.as_of) != (
        index.snapshot_id,
        index.scope,
        index.as_of,
    ):
        issues.append(
            ("SNAPSHOT_MISMATCH", "Use the same snapshot, scope and cutoff in both layers.")
        )
    if (source.record_count, index.record_count) != (report.source_records, report.index_records):
        issues.append(
            ("SNAPSHOT_COUNT_MISMATCH", "Scan the complete scope declared by each manifest.")
        )
    return issues
