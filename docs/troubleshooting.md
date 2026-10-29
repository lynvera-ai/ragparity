# Troubleshooting and FAQ

Use the Python environment where you installed the package. Start with these checks:

```bash
python --version
python -m pip show lynvera-ragparity
python -m pip check
python -m lynvera_ragparity version
```

Expected package version: `0.2.0b1`. Python must be 3.12 or newer. `pip check` should
report no broken requirements. `pip show` can print local paths; remove private paths
and values before sharing output. PowerShell users can call
`.venv\Scripts\python.exe` instead of `python`.

## Installation and command problems

| Symptom | Next check |
| --- | --- |
| `ragparity` is not found | Activate the intended environment or use `python -m lynvera_ragparity`. On Windows, use that environment's executable path. |
| `No module named lynvera_ragparity` | Check `python -m pip show lynvera-ragparity`; install the reviewed source or wheel using the same Python. |
| Python version is rejected | Select Python 3.12+ before creating the environment. A newer pip does not change Python itself. |
| Dependency conflicts | Create a separate environment and install only the core package first; use `python -m pip check`. |
| `Cannot create configuration` | `init` does not overwrite files. Choose a new writable path with `ragparity init example.toml`. |
| `Invalid configuration` | Check the selected file, TOML syntax and the field names in the configuration contract. The CLI does not load `.env`. |
| Wheel or source hash differs | Keep the original file for investigation and obtain the intended reviewed artifact again. Do not install the changed download. |

See [installation choices](getting-started.md#choose-an-installation-method) and
[configuration contracts](contracts.md#adapter-configuration). The package is not
published to PyPI by this preparation; use the repository or reviewed artifact.

## Database and execution problems

| Symptom or finding | Next check |
| --- | --- |
| Database URL environment variable is missing | Set the variable named in `url_env` in the same process environment. Keep the credential out of TOML and Git. |
| Supported driver cannot be loaded | Install the optional `postgres` extra into the selected environment. Use `postgresql+psycopg://` URLs. |
| `DATABASE_CONNECTION_ERROR` | Verify the database is reachable and the SELECT-only account can access the intended schema and table/view. |
| `DATABASE_TIMEOUT` | Inspect query cost and the configured statement timeout. Do not convert an incomplete scan into PASS. |
| `STORAGE_ERROR` | Check writable temporary storage, available disk and `max_spool_bytes`. Preserve private logs before retrying a complete audit. |
| `TIME_LIMIT_EXCEEDED` or `CHECK_CANCELLED` | Run a new complete audit after adjusting the limit or cancellation condition. |
| Missing metadata or snapshot findings | Supply the fields and completed-snapshot evidence required by the chosen policy; read the exact finding code. |

The core has no local web server. A port conflict belongs to a database fixture or an
experimental chat service, not to the memory example. The disposable database example
documents its configurable port; keep its data separate from your application.

## Why does a check return 1?

Exit 1 means a deterministic inconsistency. For the guided version mismatch, it is the
expected result. Inspect the saved report's counts, identifiers and recommendations.
Do not reinstall the package to hide an observed data mismatch.

## Why does matching data still produce INCONCLUSIVE?

The audit can have matching pairs alongside missing metadata, unknown identities or
unverifiable completion evidence. An empty metadata scan is also inconclusive, even if
a numeric claim matches. Read overall status and all counts together; a capped finding
list is not the full set of observations.

## Why does rendering a FAIL report exit 0?

The report conversion completed successfully. Rendering does not rerun the audit or
change its status. Read the report's `status` to determine the audit result.

## Does PASS prove that a chat answer is correct?

PASS checks the supplied metadata or structured numeric contract. It does not certify a
complete free-form answer, authenticate supplied evidence or verify embeddings. The
experimental Haystack evaluation passed 22/46 and retained 24 failures. Chat relevance
and data consistency require separate evaluation.

## Does an update remove my reports?

The package installer owns the installed code. Your configuration, reports and optional
pilot runtime data have separate lifetimes. Follow [updates and removal](maintenance.md)
and retain the original private data when diagnosing an installation problem.

## Share a useful report

Record the installed version, platform, command, exit code, expected behavior and a small
sanitized reproduction. Use [the external feedback form](beta-feedback.md). Remove
credentials, connection URLs, document bodies and unredacted evidence. Security issues
use the private contact in [SECURITY.md](../SECURITY.md).

[Back to documentation](README.md).
