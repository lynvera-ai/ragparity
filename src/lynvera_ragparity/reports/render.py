import os
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from lynvera_ragparity.core import CheckReport
from lynvera_ragparity.reports.privacy import redact_report


def render_html(report: CheckReport) -> str:
    rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{escape(str(value))}</td>"
            for value in (
                finding.status.value,
                finding.code,
                finding.source,
                finding.source_id or "",
                finding.document_id or "",
                finding.collection or "",
                finding.chunk_id or "",
                finding.model_dump_json(include={"evidence"}),
                finding.recommendation,
            )
        )
        + "</tr>"
        for finding in report.findings
    )
    counts = escape(str({code.value: count for code, count in report.counts.items()}))
    context = escape(
        report.audit.model_dump_json() if report.audit else "No audit context (legacy report)"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        "<title>Lynvera RAGParity report</title><style>"
        "body{font:16px system-ui;margin:2rem;color:#172536}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #bcc6d0;"
        "padding:.5rem;text-align:left;overflow-wrap:anywhere}</style></head><body>"
        f"<h1>Lynvera RAGParity</h1><p>Status: <strong>{report.status.value}</strong></p>"
        f"<p>Generated: {escape(report.generated_at.isoformat())}</p>"
        f"<p>Source records: {report.source_records}; index records: {report.index_records}; "
        f"comparisons: {report.comparisons}</p><p>Counts: {counts}</p>"
        f"<p>Findings truncated: {str(report.findings_truncated).lower()}</p>"
        f"<p>Redacted: {str(report.redacted).lower()}</p>"
        f"<details><summary>Audit context</summary><pre>{context}</pre></details>"
        "<table><thead><tr><th>Status</th><th>Code</th><th>Layer</th><th>Source</th>"
        "<th>Document</th><th>Collection</th><th>Chunk</th><th>Evidence</th><th>Recommendation</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></body></html>"
    )


def write_report(
    report: CheckReport,
    path: Path,
    format: Literal["json", "html"],
    *,
    redact: bool = False,
) -> None:
    if format not in ("json", "html"):
        raise ValueError("Unsupported report format")
    result = redact_report(report) if redact else report.model_copy(deep=True)
    result.schema_version = "2.0"
    content = result.model_dump_json(indent=2) if format == "json" else render_html(result)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".ragparity-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
