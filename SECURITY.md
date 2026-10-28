# Security policy

Version 0.2 is in beta. Security fixes target the latest available beta; users of 0.1
should upgrade and review the report-schema migration. No
production-readiness, compliance, or accuracy certification is implied.

Report suspected vulnerabilities privately to felipe.castillo@lynvera.ai. Include
affected versions, reproduction steps, impact, and sanitized examples. Do not send
credentials, customer documents, or database dumps. Do not publish sensitive details
in a public issue before coordinated disclosure. No response-time guarantee is offered.

Use SELECT-only database accounts, narrowly scoped tables or views, and trusted
configuration. Database connections inherit SQLAlchemy driver behavior; configure TLS appropriate to your deployment. Connection and query timeouts are
configurable and finite by default; total audit cancellation is cooperative. Do not enable SQLAlchemy SQL logging for
sensitive workloads. Built-in errors omit driver messages and connection URLs.

Document bodies are not read, but identifiers, hashes, versions, and numeric evidence
can be sensitive. Protect reports and temporary storage. Use `--redact` for shared reports; unredacted
identifiers, hashes, numeric values and evidence references remain potentially sensitive. The checker uses a private
temporary directory for its SQLite spool and removes it on normal cleanup; abrupt process
termination may leave files. Secure the temporary filesystem and apply your own retention
policy. HTML output escapes metadata and uses no external scripts or network resources.

A PASS means the supplied evidence agrees under configured rules. It does not establish
the authority of caller-provided evidence, the correctness of document content, model
behavior, embeddings, or an entire free-form answer. Missing evidence remains inconclusive.

Completion manifests and numeric evidence references are caller-supplied attestations.
They are checked for internal consistency, not authenticated or fetched. Publish immutable
audit projections from a trusted pipeline and resolve evidence through an authorized
source. Arbitrary URLs in references are never fetched by the toolkit.
