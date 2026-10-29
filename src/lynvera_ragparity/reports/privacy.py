from lynvera_ragparity.core import CheckReport


def redact_report(report: CheckReport) -> CheckReport:
    """Remove identifiers and all evidence without changing counts or status."""
    safe = report.model_copy(deep=True)
    safe.redacted = True
    for finding in safe.findings:
        if finding.source not in {"source", "index", "both", "audit", "checker", "claim"}:
            finding.source = "redacted"
        finding.source_id = finding.document_id = finding.collection = finding.chunk_id = None
        finding.evidence = {"redacted": True}
        finding.recommendation = "Inspect the private audit output for remediation details."
    if safe.audit is not None:
        safe.audit.source_snapshot = safe.audit.index_snapshot = None
    return safe
