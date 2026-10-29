# Getting started with 0.2.0b1

RAGParity compares source metadata with index metadata and validates structured numeric
claims. Start with the local memory example below. It needs Python 3.12 or newer and
internet access to install free dependencies. It needs no model, database, container,
subscription or account. Once installed, this example runs offline.

The package and command-line tool are in beta. A passing result means that the supplied
evidence agrees under the selected rules. It does not certify a complete generated answer.

## Choose an installation method

| Method | Use when | Requirements |
| --- | --- | --- |
| Source checkout | You want the code, documentation and examples from GitHub. | Git, Python 3.12+ and free build/runtime dependencies. |
| Wheel | You have a reviewed `.whl` file and want the packaged CLI/library. | Python 3.12+ and free runtime dependencies; no Git checkout needed. |
| Source archive | You have a reviewed `.tar.gz` file and want to build locally. | Python 3.12+ and free build/runtime dependencies. |
| PostgreSQL extra | Your source/index metadata live in PostgreSQL or pgvector. | Add `postgres` to the chosen installation; use SELECT-only accounts. |

Initial dependency installation needs network access unless you supply a complete local
wheelhouse. Once installed, the memory example runs offline. The core installation does
not download models, start services, create accounts or open a listening port.

| Environment | Evidence for this beta preparation |
| --- | --- |
| macOS ARM64, Python 3.12.9 | Clean installation and local CLI/library verification. |
| Linux | Prior CI covers the documented Python/database matrix; a new clean host installation remains pending. |
| Windows | Instructions are provided; clean installation remains pending. |

Code is installed in the selected Python environment. Configuration and reports live
at the paths you choose. The core creates no fixed application data directory or
background service. Temporary audit data uses the system temporary directory unless
`policy.temporary_directory` is configured; protect it as described in the security policy.

## Install from GitHub

The beta code is available on `main`. For installation from source:

```bash
git clone --branch main --single-branch https://github.com/lynvera-ai/ragparity.git
cd ragparity
python3 -m venv .venv
```

On macOS or Linux:

```bash
source .venv/bin/activate
python -m pip install --upgrade 'pip>=26.2,<27'
python -m pip install .
```

On Windows PowerShell, create the environment with `py -3.12 -m venv .venv` if `python3`
is unavailable, then run the environment's executables directly:

```powershell
.venv\Scripts\python.exe -m pip install --upgrade 'pip>=26.2,<27'
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\ragparity.exe version
```

The examples below use `ragparity` from the activated environment. PowerShell users can
save the executable's full path with `$ragparity = (Resolve-Path .venv\Scripts\ragparity.exe).Path`
before changing directories, then substitute `& $ragparity` in subsequent commands.
Windows and Linux installation instructions
are provided for testing; this preparation's clean-install check was run on macOS ARM64
with Python 3.12. Other platforms need external confirmation. Historical Linux CI is
listed separately in the release policy.

For a reviewed release wheel downloaded from GitHub, install the actual local filename:

```bash
python -m pip install --upgrade 'pip>=26.2,<27'
python -m pip install ./lynvera_ragparity-0.2.0b1-py3-none-any.whl
```

Compare the file's SHA-256 with the release's `SHA256SUMS` before installing. These
checksums detect a changed download; they are not a signature or independent attestation.
No PyPI publication or currently available GitHub Release is implied by these instructions.

For the source archive, use the same environment and run
`python -m pip install ./lynvera_ragparity-0.2.0b1.tar.gz`. Choose one package format;
both install the same CLI and library. Use the supplied `SHA256SUMS` to check the actual
download before installation. A wheel contains the library; the source archive also
includes documentation and examples.

## Run the first check

Choose a new working directory outside the checkout, activate the installed environment,
then run:

```bash
ragparity version
ragparity init
ragparity check --config ragparity.toml --output report.json
ragparity report --input report.json --output report.html
```

Expected version: `0.2.0b1`. Expected result: `PASS: source=1 index=1 comparisons=1`.
Open `report.html` in a browser. It is self-contained and requires no server or external
assets. The configuration and reports are written to the directory you chose.
`init` refuses to overwrite an existing file; `ragparity init another.toml` chooses a
different name.

In `ragparity.toml`, change only the `source_version` under `[[index.records]]` from
`"1"` to `"2"`, leaving the source unchanged. Run the check again. It should return
`FAIL` with `VERSION_MISMATCH: 1` and exit code 1. Recreate the HTML report to see it.
An exit code of 1 is an observed mismatch, not an installation failure.

| Status | Exit code | Action |
| --- | ---: | --- |
| PASS | 0 | Supplied evidence agrees under the configured rules. |
| FAIL | 1 | Inspect the reported differences and the ingestion pipeline. |
| ERROR | 2 | Correct configuration, access or execution problems before retrying. |
| INCONCLUSIVE | 3 | Supply the missing or verifiable evidence; an empty scan is inconclusive. |

Ctrl-C exits 130. Numeric checks require explicit values, units, metrics, periods and
source references. See [numeric contracts](numeric-claims.md) and the source-tree
`examples/basic/claims.toml`; its intentionally empty metadata scans remain inconclusive.

## Connect your source and index

For PostgreSQL and pgvector, install the optional driver into the same environment:

```bash
python -m pip install '.[postgres]'
```

Run this from the cloned source directory. For a downloaded wheel, install
`'./lynvera_ragparity-0.2.0b1-py3-none-any.whl[postgres]'` instead.

Use SELECT-only accounts and expose metadata tables or views with the documented
identity, version, hash and deletion columns. Match `source_id`, `document_id` and
`collection` between layers. Do not point the disposable integration tests at your data.

```toml
[source]
kind = "postgresql"
url_env = "SOURCE_DATABASE_URL"
table = "source_metadata"
schema_name = "public"

[index]
kind = "pgvector"
url_env = "INDEX_DATABASE_URL"
table = "index_metadata"
schema_name = "public"
```

Save the configuration in a separate file. Set both named environment variables to your
database URLs using the `postgresql+psycopg://` driver. Keep credentials out of TOML,
Git and shared reports. The CLI does not automatically read `.env` files. Existing
databases can be local; RAGParity does not create or require a hosted service.
Use `ragparity check --config your-file.toml --redact --output report.json`.

The [database example](../examples/postgresql_pgvector/README.md) provides a separate
disposable local fixture and configurable port. The [contract guide](contracts.md)
describes column mappings, missing evidence and snapshot semantics. Chunk audits also
need authoritative fragment manifests; see [audit configuration](audits.md).

For other applications, implement the documented `RecordReader.iter_batches` contract
and supply metadata through the library. Automatic discovery of arbitrary framework
schemas is outside the beta scope.

## Requirements and troubleshooting

- The core does not listen on a network port. Existing chat ports do not affect it.
  Configuration paths and output paths are explicit; no personal directory is required.
- Memory and temporary disk use grow with input size. The tiny example is not a capacity
  estimate. See [measured resource use](performance.md) before running large scans.
- If the command is missing, activate the environment or use its full executable path.
- If installation rejects Python, check `python --version` and use Python 3.12 or newer.
- Update pip in the environment before installation. Python may bundle an older
  installer even when the selected package dependencies are current.
- If a database URL is missing, set the environment variable named in `url_env`.
  If a driver is missing, install the `postgres` extra in the same environment.
- If configuration is invalid, check TOML syntax, required fields and column mappings.
  If evidence is incomplete, investigate it rather than treating the result as PASS.
- Reports can contain sensitive identifiers and evidence. Keep them local or use
  `--redact` before sharing. Share sanitized symptoms using [the beta feedback form](beta-feedback.md).

## Optional experimental pilots

Neither chat is installed or started by the core package. Their requirements are separate:

| Example | Additional requirements | Scope |
| --- | --- | --- |
| Synthetic catalog | Core package and cloned example files | Free deterministic demonstration; no model or database. |
| PostgreSQL fixture | `postgres` extra, Docker Compose, free local image and a free port | Disposable synthetic metadata integration. |
| Open WebUI pilot | Apple Silicon macOS, Colima, Docker tools, SSH, local models and at least 8 GiB initial free disk | Experimental platform-specific installer; not a portable core requirement. |
| Haystack pilot | Optional pinned Haystack packages and separately prepared local Ollama service/models | Experimental single-passage retrieval; setup depends on the documented first pilot. |

Use the pilot READMEs before installing anything. They involve substantial optional
downloads and additional memory/storage. They are not a one-command portable chat
product. The Haystack fresh evaluation passed 22/46 and retained all 24 failures.
Independent user acceptance remains pending.

For a failed step, see [diagnostics and common questions](troubleshooting.md).
For a later upgrade or removal, follow [installation maintenance](maintenance.md).
