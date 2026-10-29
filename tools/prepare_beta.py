"""Build and exercise a beta distribution locally without publishing anything."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from datetime import UTC, datetime
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_archives(wheel: Path, source: Path, version: str) -> dict:
    """Reject accidental runtime/build files and verify the distributable contract."""
    info = f"lynvera_ragparity-{version}.dist-info/"
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if any(not n.startswith(("lynvera_ragparity/", info)) for n in names):
            raise ValueError("Unexpected wheel content")
        required = {
            "lynvera_ragparity/py.typed",
            info + "licenses/LICENSE",
            info + "licenses/NOTICE",
            info + "entry_points.txt",
        }
        if not required.issubset(names):
            raise ValueError("Wheel is missing license, notice, typing or CLI metadata")
        for name in ("LICENSE", "NOTICE"):
            if archive.read(info + "licenses/" + name) != (ROOT / name).read_bytes():
                raise ValueError("Wheel legal notices differ from project files")
        metadata = BytesParser().parsebytes(archive.read(info + "METADATA"))
        if (
            metadata["Name"] != "lynvera-ragparity"
            or metadata["Version"] != version
            or metadata["Requires-Python"] != ">=3.12"
            or metadata["License-Expression"] != "Apache-2.0"
        ):
            raise ValueError("Unexpected wheel metadata")
        if b"ragparity = lynvera_ragparity.cli:app" not in archive.read(info + "entry_points.txt"):
            raise ValueError("Missing CLI entry point")
        wheel_names = names
    allowed_roots = {
        "src",
        "docs",
        "examples",
        "tests",
        "benchmarks",
        "tools",
        "constraints",
        "pyproject.toml",
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        "NOTICE",
        "PKG-INFO",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "compose.yaml",
        ".env.example",
        ".gitignore",
    }
    forbidden = {".git", ".venv", "__pycache__", "receipts", "fresh-evaluations", "dist"}
    prefix = f"lynvera_ragparity-{version}"
    with tarfile.open(source) as archive:
        source_names = []
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or len(path.parts) < 2
                or path.parts[0] != prefix
                or path.parts[1] not in allowed_roots
                or any(p in forbidden for p in path.parts)
                or any(p in {".env", "secrets.json", "login.txt", "index.json"} for p in path.parts)
                or not member.isfile()
            ):
                raise ValueError("Unexpected source archive content: " + member.name)
            source_names.append(str(PurePosixPath(*path.parts[1:])))
        if not {"LICENSE", "NOTICE", "README.md", "pyproject.toml"}.issubset(source_names):
            raise ValueError("Source archive is missing required project files")
    return {"wheel_files": wheel_names, "source_files": source_names}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/beta-0.2.0b1")
    parser.add_argument(
        "--work-dir", type=Path, help="New private directory for logs and environments"
    )
    args = parser.parse_args()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    version = project["project"]["version"]
    if (
        version != "0.2.0b1"
        or f'__version__ = "{version}"'
        not in (ROOT / "src/lynvera_ragparity/__init__.py").read_text()
        or f"## {version}" not in (ROOT / "CHANGELOG.md").read_text()
    ):
        raise ValueError("Project version and changelog must agree on 0.2.0b1")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    work = (
        args.work_dir.resolve()
        if args.work_dir
        else Path(tempfile.mkdtemp(prefix="ragparity-beta-"))
    )
    if args.work_dir:
        work.mkdir(parents=True, exist_ok=False)
    work.chmod(0o700)
    if work == ROOT or ROOT in work.parents:
        raise ValueError("Choose a work directory outside the checkout")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "PIP_"))}
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_INDEX_URL"] = "https://pypi.org/simple"
    epoch = subprocess.check_output(["git", "show", "-s", "--format=%ct", "HEAD"], cwd=ROOT)
    env["SOURCE_DATE_EPOCH"] = epoch.decode().strip()
    records = []

    def run(label, command, *, cwd=work, expected=0):
        result = subprocess.run(
            [str(arg) for arg in command], cwd=cwd, env=env, capture_output=True, text=True
        )
        log = work / (label + ".log")
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        log.chmod(0o600)
        records.append({"check": label, "exit_code": result.returncode, "expected": expected})
        if result.returncode != expected:
            raise RuntimeError("Distribution check failed: " + label + "; inspect " + str(log))
        return result.stdout

    run("build", [sys.executable, "-m", "build", "--outdir", output], cwd=ROOT)
    (wheel,) = output.glob("*.whl")
    (source,) = output.glob("*.tar.gz")
    inventory = inspect_archives(wheel, source, version)
    run("metadata", [sys.executable, "-m", "twine", "check", wheel, source])
    environment = work / "environment"
    run("environment", [sys.executable, "-m", "venv", environment])
    binaries = environment / ("Scripts" if os.name == "nt" else "bin")
    python = binaries / ("python.exe" if os.name == "nt" else "python")
    cli = binaries / ("ragparity.exe" if os.name == "nt" else "ragparity")
    run("installer", [python, "-m", "pip", "install", "--upgrade", "pip>=26.2,<27"])
    run("install", [python, "-m", "pip", "install", wheel])
    run("dependencies", [python, "-m", "pip", "check"])
    installed = json.loads(run("installed", [python, "-m", "pip", "list", "--format=json"]))
    excluded = {"haystack-ai", "ollama-haystack", "psycopg", "torch", "transformers"}
    if excluded.intersection(d["name"].casefold() for d in installed):
        raise ValueError("Core installation unexpectedly includes optional pilot packages")
    origin = run(
        "origin",
        [
            python,
            "-I",
            "-c",
            (
                "from pathlib import Path; import lynvera_ragparity as p; "
                "from importlib.metadata import version; "
                f"assert p.__version__ == version('lynvera-ragparity') == {version!r}; "
                "print(Path(p.__file__).resolve())"
            ),
        ],
    ).strip()
    if not Path(origin).is_relative_to(environment):
        raise ValueError("The smoke check imported the checkout instead of the installed wheel")
    run("help", [cli, "--help"])
    if run("version", [cli, "version"]).strip() != version:
        raise ValueError("Installed CLI version differs")
    if run("module", [python, "-I", "-m", "lynvera_ragparity", "version"]).strip() != version:
        raise ValueError("Installed module entry point differs")
    run(
        "numeric-contract",
        [
            python,
            "-I",
            "-c",
            (
                "from lynvera_ragparity.claims import "
                "NumericClaim, NumericEvidence, validate_claim; "
                "expected = NumericEvidence(value='10.00', unit='USD', period='2026-10', "
                "source_id='fixture', metric='price'); "
                "match = NumericClaim(claim_id='match', expected=expected, observed=expected); "
                "assert validate_claim(match).status.value == 'PASS'; "
                "wrong = match.model_copy(update={'observed': "
                "expected.model_copy(update={'value': expected.value + 1})}); "
                "assert validate_claim(wrong).status.value == 'FAIL'; "
                "missing = match.model_copy(update={'observed': None}); "
                "assert validate_claim(missing).status.value == 'INCONCLUSIVE'; "
                "print('Structured numeric contracts passed')"
            ),
        ],
    )
    run("init", [cli, "init"])
    original = (work / "ragparity.toml").read_text()
    run("init-no-overwrite", [cli, "init"], expected=2)
    if (work / "ragparity.toml").read_text() != original:
        raise ValueError("init changed an existing configuration")
    run("pass", [cli, "check", "--output", "pass.json"])
    report = json.loads((work / "pass.json").read_text())
    if report["status"] != "PASS":
        raise ValueError("Initial example did not pass")
    run("html", [cli, "report", "--input", "pass.json", "--output", "report.html"])
    if "<html" not in (work / "report.html").read_text().lower():
        raise ValueError("HTML report missing")
    run(
        "json", [cli, "report", "--input", "pass.json", "--output", "copy.json", "--format", "json"]
    )
    if json.loads((work / "copy.json").read_text()) != report:
        raise ValueError("JSON report conversion changed the report")
    source_part, index_part = original.split("[index]", 1)
    (work / "stale.toml").write_text(
        source_part
        + "[index]"
        + index_part.replace('source_version = "1"', 'source_version = "2"'),
        encoding="utf-8",
    )
    run("fail", [cli, "check", "--config", "stale.toml", "--output", "fail.json"], expected=1)
    failed = json.loads((work / "fail.json").read_text())
    if failed["status"] != "FAIL" or failed["counts"].get("VERSION_MISMATCH") != 1:
        raise ValueError("Deliberate mismatch was not detected")
    (work / "empty.toml").write_text('[source]\nkind="memory"\n[index]\nkind="memory"\n')
    run(
        "inconclusive",
        [cli, "check", "--config", "empty.toml", "--output", "empty.json"],
        expected=3,
    )
    if json.loads((work / "empty.json").read_text())["status"] != "INCONCLUSIVE":
        raise ValueError("Empty scan was not inconclusive")
    run("error", [cli, "check", "--config", "absent.toml"], expected=2)
    run("redacted", [cli, "check", "--redact", "--output", "redacted.json"])
    if "product-1" in (work / "redacted.json").read_text():
        raise ValueError("Shared report contains a fixture identifier")
    rebuilt = work / "rebuilt"
    run(
        "source-install",
        [python, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", rebuilt, source],
    )
    (rebuilt_wheel,) = rebuilt.glob("*.whl")
    if checksum(rebuilt_wheel) != checksum(wheel):
        raise ValueError("Rebuilding the source archive produced a different wheel")
    run("postgres-extra", [python, "-m", "pip", "install", str(wheel) + "[postgres]"])
    run("postgres-dependencies", [python, "-m", "pip", "check"])
    driver = run(
        "postgres-driver",
        [
            python,
            "-I",
            "-c",
            (
                "import psycopg; from lynvera_ragparity.indexes import PgVectorIndex; "
                "print(psycopg.__version__)"
            ),
        ],
    ).strip()
    sums = "".join(f"{checksum(p)}  {p.name}\n" for p in (wheel, source))
    (output / "SHA256SUMS").write_text(sums, encoding="ascii")
    evidence = {
        "version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "installed_dependencies": installed,
        "optional_postgres_driver": driver,
        "checks": records,
        "inventory": inventory,
        "artifacts": {p.name: checksum(p) for p in (wheel, source)},
        "source_rebuild_identical": True,
        "independent_acceptance": "PENDING",
        "publishing_performed": False,
    }
    path = work / "verification.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    print("Beta artifacts: " + str(output))
    print("Private verification: " + str(path))
    print("PASS: clean wheel install, CLI checks and identical source rebuild. Nothing published.")


if __name__ == "__main__":
    main()
