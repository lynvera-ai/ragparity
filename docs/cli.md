# CLI reference

Install `lynvera-ragparity` using [Getting started](getting-started.md). The executable
is `ragparity`; `python -m lynvera_ragparity` provides the same commands in the selected
environment. Use `--help` on the root or any command for installed option details.

## Commands

| Command | Purpose |
| --- | --- |
| `ragparity version` | Print the installed package version. |
| `ragparity init [PATH]` | Write an annotated memory example; default path is `ragparity.toml`. |
| `ragparity check` | Read configuration, perform checks and optionally save a JSON report. |
| `ragparity report` | Validate a saved report and write JSON or self-contained HTML. |

## Initialize and check

Run these in a new working directory with the installed environment active:

```bash
ragparity init
ragparity check --config ragparity.toml --output report.json
```

`init` refuses to overwrite an existing file. Choose another path with
`ragparity init example.toml`. Configuration paths and report paths are relative to
your current directory unless absolute paths are supplied.

`check` accepts `--config`/`-c`, `--output`/`-o` and `--redact`. Without `--config`,
it reads `ragparity.toml`. Without `--output`, it prints the status and counts without
saving a report. Use `--redact` or set `redact = true` in `[report]` to omit
identifiers, evidence and snapshot manifests from saved output.

Database credentials are read only from the environment variable named in each
adapter's `url_env`. The CLI does not load `.env`. Install the optional `postgres` driver
for database readers. See [configuration contracts](contracts.md#adapter-configuration).

## Exit codes

| Status | Code | Meaning |
| --- | ---: | --- |
| PASS | 0 | Supplied evidence agrees under the configured checks. |
| FAIL | 1 | At least one deterministic inconsistency was found. |
| ERROR | 2 | Invalid configuration, adapter, storage or execution failure. |
| INCONCLUSIVE | 3 | Evidence is missing, incomplete or unverifiable. |

Ctrl-C exits 130. Overall status uses ERROR, FAIL, INCONCLUSIVE, PASS precedence.
An empty metadata scan remains inconclusive even if a numeric claim matches.
An intentional mismatch in a fixture should return code 1; do not treat it as a
broken installation. Configuration failures can prevent a report from being written.

The result status codes above apply to `check`. Successful `init`, `version` and
`report` commands exit 0; file or input failures in `init` and `report` exit 2.

## Render a saved report

```bash
ragparity report --input report.json --output report.html
ragparity report --input report.json --output redacted.json --format json --redact
```

`report` requires `--input`/`-i` and `--output`/`-o`. `--format`/`-f` accepts `json` or
`html`; the default is HTML, regardless of the output filename. Rendering a saved FAIL
report successfully exits 0 because the conversion completed; read the report's status
to determine the audit result.

HTML escapes metadata and uses no external scripts or assets. Redaction preserves
counts and status; reports can still reveal aggregate information. Output writes use
a private temporary file and atomic replacement. Choose a destination with adequate
permissions and space. Readers accept schema 1.0 and 2.0; writers emit 2.0.

[Back to documentation](README.md).
