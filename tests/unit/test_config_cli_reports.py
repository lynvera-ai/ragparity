import json

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from lynvera_ragparity import __version__
from lynvera_ragparity.cli import app
from lynvera_ragparity.config import (
    DEFAULT_CONFIG,
    AdapterConfig,
    ConfigurationError,
    create_reader,
    load_settings,
)
from lynvera_ragparity.core import CheckReport, Finding, Severity, Status
from lynvera_ragparity.reports import render_html, write_report

runner = CliRunner()


def test_help_version_init_check_report(tmp_path):
    config, saved, html = (
        tmp_path / name for name in ("config.toml", "result.json", "result.html")
    )
    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert runner.invoke(app, ["version"]).stdout.strip() == __version__
    assert runner.invoke(app, ["init", str(config)]).exit_code == 0
    assert config.read_text() == DEFAULT_CONFIG
    assert runner.invoke(app, ["init", str(config)]).exit_code == 2
    checked = runner.invoke(app, ["check", "-c", str(config), "-o", str(saved)])
    assert checked.exit_code == 0, checked.output
    assert "PASS" in checked.stdout
    assert CheckReport.model_validate_json(saved.read_text()).status == Status.PASS
    assert runner.invoke(app, ["report", "-i", str(saved), "-o", str(html)]).exit_code == 0
    assert "<!doctype html>" in html.read_text()
    copied = tmp_path / "copy.json"
    assert (
        runner.invoke(app, ["report", "-i", str(saved), "-o", str(copied), "-f", "json"]).exit_code
        == 0
    )
    assert json.loads(copied.read_text()) == json.loads(saved.read_text())


@pytest.mark.parametrize(
    ("replacement", "exit_code", "code"),
    [
        ('source_version = "old"', 1, "VERSION_MISMATCH"),
        ("# source_version omitted", 3, "MISSING_METADATA"),
    ],
)
def test_cli_failure_exit_codes(tmp_path, replacement, exit_code, code):
    config = tmp_path / "config.toml"
    config.write_text(DEFAULT_CONFIG.replace('source_version = "1"', replacement, 1))
    result = runner.invoke(app, ["check", "-c", str(config)])
    assert result.exit_code == exit_code, result.output
    assert code in result.stdout


@pytest.mark.parametrize(
    "contents",
    [
        "not-toml",
        "[source]\nkind='unknown'\n[index]\nkind='memory'",
        "[source]\nkind='postgresql'\n[index]\nkind='memory'",
        DEFAULT_CONFIG.replace("batch_size = 1000", "batch_size = 0"),
        DEFAULT_CONFIG + "\nunexpected_field = 'secret-value'\n",
    ],
)
def test_invalid_configuration(tmp_path, contents):
    config = tmp_path / "config.toml"
    config.write_text(contents)
    with pytest.raises(ConfigurationError):
        load_settings(config)
    result = runner.invoke(app, ["check", "-c", str(config)])
    assert result.exit_code == 2
    assert "secret-value" not in result.output


def test_missing_files_and_invalid_reports(tmp_path):
    missing = str(tmp_path / "missing")
    assert runner.invoke(app, ["check", "-c", missing]).exit_code == 2
    assert runner.invoke(app, ["report", "-i", missing, "-o", missing]).exit_code == 2
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    assert runner.invoke(app, ["report", "-i", str(bad), "-o", missing]).exit_code == 2
    config = tmp_path / "config.toml"
    config.write_text(DEFAULT_CONFIG)
    assert runner.invoke(app, ["check", "-c", str(config), "-o", str(tmp_path)]).exit_code == 2
    assert runner.invoke(app, ["init", str(tmp_path / "missing" / "config")]).exit_code == 2


def test_database_url_never_echoed(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text("""[source]
kind = "postgresql"
url_env = "RAGPARITY_TEST_INVALID_URL"
table = "documents"
[index]
kind = "memory"
""")
    monkeypatch.setenv("RAGPARITY_TEST_INVALID_URL", "invalid://user:secret-value@host/db")
    result = runner.invoke(app, ["check", "-c", str(config)])
    assert result.exit_code == 2
    assert "secret-value" not in result.output
    monkeypatch.delenv("RAGPARITY_TEST_INVALID_URL")
    assert runner.invoke(app, ["check", "-c", str(config)]).exit_code == 2


def test_cli_connection_error(tmp_path, monkeypatch):
    from lynvera_ragparity.core import AdapterError

    class Broken:
        def iter_batches(self, batch_size):
            raise AdapterError("secret-value")
            yield []

    config = tmp_path / "config.toml"
    config.write_text(DEFAULT_CONFIG)
    monkeypatch.setattr("lynvera_ragparity.cli.create_reader", lambda *args, **kwargs: Broken())
    result = runner.invoke(app, ["check", "-c", str(config)])
    assert result.exit_code == 2
    assert "ADAPTER_ERROR" in result.stdout
    assert "secret-value" not in result.output


def test_configuration_column_validation():
    for columns in ({}, {"body": "content"}, {"document_id": ""}):
        with pytest.raises(ValidationError):
            AdapterConfig(columns=columns, kind="postgresql", url_env="DB", table="documents")
    with pytest.raises(ValidationError):
        AdapterConfig(kind="memory", url_env="DB")


def test_non_postgres_url_rejected(monkeypatch):
    monkeypatch.setenv("RAGPARITY_TEST_URL", "sqlite://")
    with pytest.raises(ConfigurationError):
        create_reader(AdapterConfig(kind="postgresql", url_env="RAGPARITY_TEST_URL", table="docs"))


def test_html_escapes_untrusted_metadata_and_json_roundtrip(tmp_path):
    payload = '<script>alert("x")</script>'
    result = CheckReport(
        status=Status.FAIL,
        findings=[
            Finding(
                code="HASH_MISMATCH",
                status=Status.FAIL,
                severity=Severity.ERROR,
                source="index",
                source_id=payload,
                document_id=payload,
                collection=payload,
                evidence={"value": payload},
                recommendation=payload,
            )
        ],
    )
    html = render_html(result)
    assert payload not in html
    assert "&lt;script&gt;" in html
    path = tmp_path / "report.json"
    write_report(result, path, "json")
    assert CheckReport.model_validate_json(path.read_text()) == result


def test_numeric_claim_cli(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        DEFAULT_CONFIG
        + """
[[claims]]
claim_id = "revenue"
[claims.expected]
value = "1.00"
unit = "USD"
period = "2026-10"
source_id = "ledger"
metric = "revenue"
[claims.observed]
value = "2.00"
unit = "USD"
period = "2026-10"
source_id = "ledger"
metric = "revenue"
"""
    )
    result = runner.invoke(app, ["check", "-c", str(config)])
    assert result.exit_code == 1
    assert "CLAIM_VALUE_MISMATCH" in result.stdout


def test_cli_truncation_keeps_all_failure_counts(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        DEFAULT_CONFIG.replace("max_findings = 1000", "max_findings = 1")
        .replace('source_version = "1"', 'source_version = "old"', 1)
        .replace('content_hash = "sha256:synthetic-example"', 'content_hash = "old"', 1)
    )
    result = runner.invoke(app, ["check", "-c", str(config)])
    assert result.exit_code == 1
    assert "Detailed findings capped" in result.stdout
    assert "VERSION_MISMATCH: 1" in result.stdout
    assert "HASH_MISMATCH: 1" in result.stdout


def test_configuration_requires_utf8(tmp_path):
    config = tmp_path / "config.toml"
    config.write_bytes(b"\xff\xfe")
    with pytest.raises(ConfigurationError):
        load_settings(config)
    assert runner.invoke(app, ["check", "-c", str(config)]).exit_code == 2
