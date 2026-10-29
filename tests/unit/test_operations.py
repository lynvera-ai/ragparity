import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.cli import app
from lynvera_ragparity.config import DEFAULT_CONFIG
from lynvera_ragparity.core import CheckPolicy, CheckReport, Status
from lynvera_ragparity.indexes import MemoryIndex
from lynvera_ragparity.reports import redact_report, write_report
from lynvera_ragparity.sources import MemorySource


def test_cancellation_closes_active_scan_and_cleans_spool(tmp_path, synchronized_record):
    closed = []
    cancelled = [False]

    class Source:
        def iter_batches(self, batch_size):
            try:
                yield [synchronized_record]
                cancelled[0] = True
                yield [synchronized_record]
            finally:
                closed.append(True)

    result = ConsistencyChecker(CheckPolicy(temporary_directory=tmp_path)).check(
        Source(),
        MemoryIndex([]),
        cancel=lambda: cancelled[0],
    )
    assert result.status == Status.ERROR
    assert result.counts == {"CHECK_CANCELLED": 1}
    assert result.comparisons == 0
    assert closed == [True]
    assert list(tmp_path.iterdir()) == []


def test_time_limit_does_not_compare_partial_data(monkeypatch, synchronized_record):
    ticks = iter([0, 0, 2, 3])
    monkeypatch.setattr("lynvera_ragparity.checks.engine.monotonic", lambda: next(ticks))
    result = ConsistencyChecker(CheckPolicy(max_duration_seconds=1)).check(
        MemorySource([synchronized_record]),
        MemoryIndex([]),
    )
    assert result.status == Status.ERROR
    assert result.counts == {"TIME_LIMIT_EXCEEDED": 1}
    assert result.comparisons == 0


def test_spool_limit_and_cleanup(tmp_path, synchronized_record):
    records = (synchronized_record.model_copy(update={"document_id": str(i)}) for i in range(1000))
    result = ConsistencyChecker(
        CheckPolicy(max_spool_bytes=65_536, temporary_directory=tmp_path)
    ).check(
        MemorySource(records),
        MemoryIndex([]),
    )
    assert result.status == Status.ERROR
    assert "STORAGE_ERROR" in result.counts
    assert list(tmp_path.iterdir()) == []


def test_programming_error_propagates_but_cleans_storage(tmp_path):
    class Bug:
        def iter_batches(self, batch_size):
            raise RuntimeError("adapter bug")
            yield []

    with pytest.raises(RuntimeError, match="adapter bug"):
        ConsistencyChecker(CheckPolicy(temporary_directory=tmp_path)).check(Bug(), MemoryIndex([]))
    assert list(tmp_path.iterdir()) == []


def test_atomic_private_report_and_redaction(tmp_path, synchronized_record):
    result = ConsistencyChecker().check(MemorySource([synchronized_record]), MemoryIndex([]))
    safe = redact_report(result)
    assert safe.status == result.status
    assert safe.counts == result.counts
    assert safe.redacted
    assert safe.findings[0].document_id is None
    assert result.findings[0].document_id is not None
    path = tmp_path / "report.json"
    write_report(result, path, "json", redact=True)
    assert "item-1" not in path.read_text()
    assert CheckReport.model_validate_json(path.read_text()).redacted
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_atomic_failure_keeps_existing_report(tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    path.write_text("original")

    def denied(*args):
        raise OSError("replacement denied")

    monkeypatch.setattr("lynvera_ragparity.reports.render.os.replace", denied)
    with pytest.raises(OSError):
        write_report(CheckReport(), path, "json")
    assert path.read_text() == "original"
    assert list(tmp_path.iterdir()) == [path]


def test_unknown_report_contract_is_rejected():
    with pytest.raises(ValidationError):
        CheckReport.model_validate({"schema_version": "9.0"})
    with pytest.raises(ValidationError):
        CheckReport.model_validate({"source_records": -1})
    with pytest.raises(ValidationError):
        CheckReport.model_validate({"counts": {"INVENTED": 1}})


def test_legacy_reports_are_read_and_upgraded(tmp_path):
    report = CheckReport.model_validate(
        {"schema_version": "1.0", "status": "PASS", "counts": {"RECORD_SYNCED": 1}}
    )
    path = tmp_path / "report.json"
    write_report(report, path, "json")
    assert json.loads(path.read_text())["schema_version"] == "2.0"
    assert report.schema_version == "1.0"


def test_schema_matches_exported_contract():
    schema = Path("docs/schemas/report.schema.json")
    assert json.loads(schema.read_text()) == CheckReport.model_json_schema()


def test_cli_diagnostics_are_actionable_and_sanitized(tmp_path):
    config = tmp_path / "invalid.toml"
    config.write_text(DEFAULT_CONFIG.replace("batch_size = 1000", 'batch_size = "secret-value"'))
    result = CliRunner().invoke(app, ["check", "-c", str(config)])
    assert result.exit_code == 2
    assert "policy.batch_size" in result.output
    assert "secret-value" not in result.output


def test_cli_redacts_json_and_html(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(DEFAULT_CONFIG)
    saved, html = tmp_path / "result.json", tmp_path / "result.html"
    runner = CliRunner()
    assert (
        runner.invoke(app, ["check", "-c", str(config), "-o", str(saved), "--redact"]).exit_code
        == 0
    )
    assert "product-1" not in saved.read_text()
    assert (
        runner.invoke(app, ["report", "-i", str(saved), "-o", str(html), "--redact"]).exit_code == 0
    )
    assert "product-1" not in html.read_text()


def test_sqlite_work_can_be_cancelled_without_storage_misclassification(
    tmp_path, synchronized_record, monkeypatch
):
    import sqlite3

    original = sqlite3.connect
    cancelled = [False]

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs)

        def trace(statement):
            if statement.startswith("CREATE INDEX identity_lookup"):
                cancelled[0] = True

        connection.set_trace_callback(trace)
        return connection

    monkeypatch.setattr("lynvera_ragparity.checks.engine.sqlite3.connect", connect)
    records = [synchronized_record.model_copy(update={"document_id": str(i)}) for i in range(2000)]
    result = ConsistencyChecker(CheckPolicy(temporary_directory=tmp_path)).check(
        MemorySource(records),
        MemoryIndex(records),
        cancel=lambda: cancelled[0],
    )
    assert result.status == Status.ERROR
    assert result.counts == {"CHECK_CANCELLED": 1}
    assert result.comparisons == 0
    assert list(tmp_path.iterdir()) == []


def test_cli_keyboard_interrupt_exits_130(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text(DEFAULT_CONFIG)

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("lynvera_ragparity.cli.create_reader", interrupted)
    assert CliRunner().invoke(app, ["check", "-c", str(config)]).exit_code == 130


def test_redaction_removes_custom_layer_labels(synchronized_record):
    result = ConsistencyChecker().check(MemorySource([synchronized_record]), MemoryIndex([]))
    result.findings[0].source = "private-customer-database"
    safe = redact_report(result)
    assert safe.findings[0].source == "redacted"
    assert "private-customer-database" not in safe.model_dump_json()
    assert result.findings[0].source == "private-customer-database"
