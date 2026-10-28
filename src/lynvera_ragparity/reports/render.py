from html import escape
from pathlib import Path
from typing import Literal

from lynvera_ragparity.core import CheckReport


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
                finding.model_dump_json(include={"evidence"}),
                finding.recommendation,
            )
        )
        + "</tr>"
        for finding in report.findings
    )
    counts = escape(str(report.counts))
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
        "<table><thead><tr><th>Status</th><th>Code</th><th>Layer</th><th>Source</th>"
        "<th>Document</th><th>Collection</th><th>Evidence</th><th>Recommendation</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></body></html>"
    )


def write_report(report: CheckReport, path: Path, format: Literal["json", "html"]) -> None:
    content = report.model_dump_json(indent=2) if format == "json" else render_html(report)
    path.write_text(content + "\n", encoding="utf-8")
