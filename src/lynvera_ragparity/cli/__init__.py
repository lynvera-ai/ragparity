from contextlib import ExitStack
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from lynvera_ragparity import __version__
from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.claims import validate_claim
from lynvera_ragparity.config import (
    DEFAULT_CONFIG,
    ConfigurationError,
    close_reader,
    create_reader,
    load_settings,
)
from lynvera_ragparity.core import AdapterError, CheckReport, Status
from lynvera_ragparity.reports import write_report

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="Verify metadata parity and structured numeric claims.",
)
EXIT_CODES = {Status.PASS: 0, Status.FAIL: 1, Status.ERROR: 2, Status.INCONCLUSIVE: 3}


class ReportFormat(StrEnum):
    json = "json"
    html = "html"


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def init(path: Annotated[Path, typer.Argument()] = Path("ragparity.toml")) -> None:
    """Create an annotated, runnable configuration without overwriting files."""
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(DEFAULT_CONFIG)
    except OSError:
        typer.echo("Cannot create configuration; check permissions or choose a new path.", err=True)
        raise typer.Exit(2) from None
    typer.echo(f"Created {path}")


@app.command()
def check(
    config: Annotated[Path, typer.Option("--config", "-c")] = Path("ragparity.toml"),
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Save a JSON report.")
    ] = None,
    redact: Annotated[
        bool, typer.Option("--redact", help="Remove identifiers and evidence from saved reports.")
    ] = False,
) -> None:
    """Run checks. Exit: 0 pass, 1 inconsistency, 2 error, 3 inconclusive."""
    try:
        with ExitStack() as resources:
            settings = load_settings(config)
            source = create_reader(settings.source)
            resources.callback(close_reader, source)
            index = create_reader(settings.index, index=True)
            resources.callback(close_reader, index)
            result = ConsistencyChecker(settings.policy).check(
                source,
                index,
                source_snapshot=settings.source.snapshot,
                index_snapshot=settings.index.snapshot,
            )
            for claim in settings.claims:
                result.add(validate_claim(claim), settings.policy.max_findings)
        if output is not None:
            write_report(result, output, "json", redact=redact or settings.report.redact)
    except ConfigurationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from None
    except KeyboardInterrupt:
        typer.echo("Check cancelled.", err=True)
        raise typer.Exit(130) from None
    except (AdapterError, OSError):
        typer.echo(
            "Check could not complete; verify configuration, database and output access.", err=True
        )
        raise typer.Exit(2) from None
    typer.echo(
        f"{result.status.value}: source={result.source_records} index={result.index_records} "
        f"comparisons={result.comparisons}"
    )
    for code, count in sorted(result.counts.items()):
        typer.echo(f"{code}: {count}")
    if result.findings_truncated:
        typer.echo("Detailed findings capped; counts include all findings.")
    raise typer.Exit(EXIT_CODES[result.status])


@app.command()
def report(
    input: Annotated[Path, typer.Option("--input", "-i", help="JSON report from check.")],
    output: Annotated[Path, typer.Option("--output", "-o")],
    format: Annotated[ReportFormat, typer.Option("--format", "-f")] = ReportFormat.html,
    redact: Annotated[bool, typer.Option("--redact")] = False,
) -> None:
    """Validate a saved JSON report and render JSON or self-contained HTML."""
    try:
        result = CheckReport.model_validate_json(input.read_text(encoding="utf-8"))
        write_report(result, output, format.value, redact=redact)
    except (OSError, ValueError, ValidationError):
        typer.echo("Cannot render report; check input JSON and output access.", err=True)
        raise typer.Exit(2) from None
    typer.echo(f"Created {output}")
