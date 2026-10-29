# RAGParity documentation

RAGParity validates consistency between source and index metadata and checks structured
numeric evidence. Version 0.2.0b1 is a beta for the CLI and library. Start with the local
example, then connect the metadata projection for your application.

## Start here

| Goal | Guide |
| --- | --- |
| Install and run your first check | [Getting started](getting-started.md) |
| Start in Spanish | [Guía rápida](es/getting-started.md) |
| Fix an installation or audit problem | [Troubleshooting and FAQ](troubleshooting.md) |
| Update, roll back or remove the package | [Installation maintenance](maintenance.md) |
| Understand commands and exit codes | [CLI reference](cli.md) |
| Call the checker from Python | [Python API](python-api.md) |
| Connect PostgreSQL or pgvector | [Database example](../examples/postgresql_pgvector/README.md) |
| Audit complete document fragments | [Fragment and snapshot audits](audits.md) |
| Validate a numeric claim | [Numeric contracts](numeric-claims.md) |

## Contracts and operation

For a first session, install the core package, run the initial PASS, introduce the
documented version mismatch and open the HTML report. Then choose either the Python
reader contract or the database example for a small controlled application scope.
The optional chats are a separate path with additional requirements.

[Metadata and result contracts](contracts.md) define identities, required fields,
deletion behavior, configuration and findings. The
[machine-readable report schema](schemas/report.schema.json) describes accepted report
data. [Architecture](architecture.md) explains the scan, comparison and reporting flow.
[Resource measurements](performance.md) record observed scale and their practical limits.

Use [security guidance](../SECURITY.md) for database access, temporary storage and reports.
[Compatibility and migration](releases.md) describes supported interfaces and schema changes.

## Examples

The [basic check](../examples/basic/check.py) runs with no external services. The
[synthetic catalog](../examples/catalog/README.md) demonstrates controlled ingestion and
numeric failures. The [database fixture](../examples/postgresql_pgvector/README.md) uses
local disposable PostgreSQL/pgvector data.

The [Open WebUI pilot](../examples/public_pilot/README.md) and
[Haystack pilot](../examples/second_pilot/README.md) have separate dependencies and are
experimental. Haystack's [fresh evaluation](../examples/second_pilot/FRESH_REVIEW.md)
passed 22/46 and retains 24 failures. Those chat results are separate from metadata
consistency and do not establish independent acceptance.

## Beta review and maintenance

[Beta validation](beta-validation.md) records the local environment and observed results.
Windows/Linux clean installation and independent user acceptance remain pending for
that preparation. The [feedback guide](beta-feedback.md) provides a short review form.

Maintainers can use [local distribution preparation](beta-release.md),
[proposed release notes](release-notes-0.2.0b1.md) and the
[original beta review notes](pull-request-0.2.0b1.md). These are preparation
documents; they do not imply that a release has been published.

[Contributing](../CONTRIBUTING.md) describes development checks.
[Return to the project overview](../README.md).
