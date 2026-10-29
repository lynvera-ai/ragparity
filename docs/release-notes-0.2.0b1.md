# Lynvera RAGParity 0.2.0b1

Final candidate notes for maintainer review. Publication is pending. Links below
target the intended `v0.2.0b1` tag and become available when it is published.

RAGParity checks consistency between authoritative source metadata and RAG index
metadata, and validates explicit structured numeric claims. It runs locally without
a model subscription or hosted service.

## Included

- Missing, orphaned, duplicate, deleted, stale and inconsistent metadata detection.
- Document and fragment contracts, completion manifests and bounded scanning.
- Structured numeric checks with explicit context and Decimal tolerances.
- Command-line tool, Python library, memory readers and optional PostgreSQL/pgvector readers.
- Versioned JSON reports, local HTML reports, redaction and execution limits.
- Installation choices, platform evidence, CLI and Python references, troubleshooting,
  update/removal instructions and a Spanish first-use guide.
- Local verification of wheel and source installation, source rebuild and user-file
  preservation during uninstall.

Python 3.12 or newer is required. Install a reviewed downloaded wheel into a virtual
environment, then run `ragparity init` and `ragparity check --output report.json`.
See [Getting started](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/docs/getting-started.md) for full instructions and source installation.
The package is not published to PyPI as part of this release preparation.

## Prepared files

```text
lynvera_ragparity-0.2.0b1-py3-none-any.whl
lynvera_ragparity-0.2.0b1.tar.gz
RELEASE_NOTES.md
BUILD_INFO.json
SHA256SUMS
```

The build record identifies the exact source commit and tested platform. Check all four
listed file hashes against `SHA256SUMS` before installation or publication. Neither the
checksum file nor the build record is an independent signature. Private logs, environments,
documents and chat responses are excluded from the bundle.

## Validation and limitations

This preparation validates installation on macOS ARM64 with Python 3.12. Platform
checks not actually run are not claimed. The repository documents prior Linux CI
coverage separately. Independent beta acceptance remains pending.

Local core validation includes 303 unit tests with 95.79% core coverage and seven
PostgreSQL integration tests. The database results are retained from the unchanged
core's earlier local validation. Final preparation repeats unit and distribution checks,
including clean wheel/source installs, metadata validation, report generation, source
rebuild and uninstall preserving user files. The installer is updated before the final
dependency audit. Actual final-bundle results are recorded with the build evidence. See the
[validation record](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/docs/beta-validation.md).

The core checks supplied metadata and numeric evidence. Matching metadata does not
prove that document bodies, embeddings or complete model answers are correct.
Cross-system atomic snapshots are not inferred. Read [the contracts](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/docs/contracts.md),
[release policy](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/docs/releases.md) and [security policy](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/SECURITY.md) before integration.

Open WebUI and Haystack are optional experimental examples with separate setup needs.
The latest varied Haystack evaluation passed 22 of 46 questions: 10/23 in Spanish
and 12/23 in English. All 24 failures remain documented in the
[evaluation report](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/examples/second_pilot/FRESH_REVIEW.md). They include false
abstentions, irrelevant or incomplete passages and unsupported answers. General chat
answer quality is outside the supported beta contract.

## Upgrade and feedback

Report writers emit schema 2.0; readers accept legacy schema 1.0. Review the
[migration notes](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/docs/releases.md#migrating-from-01) when upgrading from 0.1. Beta contracts
may change with documented migration steps before 1.0.

Try the [external review procedure](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/docs/beta-feedback.md) and share a sanitized reproduction.
The [Spanish guide](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/docs/es/getting-started.md)
provides the initial installation and check in Spanish; reference documentation remains
in English. [Troubleshooting](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/docs/troubleshooting.md)
and [maintenance](https://github.com/lynvera-ai/ragparity/blob/v0.2.0b1/docs/maintenance.md)
cover later installation problems and updates.
Security reports use the private contact in `SECURITY.md`. Version 1.0 requires
independent application acceptance, resolution of material findings, stable public
contracts and a defined maintenance scope.
