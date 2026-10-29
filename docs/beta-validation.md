# Beta preparation validation

Observed on October 29, 2026. These are maintainer checks, not independent acceptance.
The core checker and the experimental chat runtimes were not changed.

| Check | Observed result |
| --- | --- |
| Host | macOS 27.0.1, ARM64, CPython 3.12.9 |
| Unit tests | 303 passed; core coverage 95.79% |
| Lint, formatting and core static types | Passed |
| PostgreSQL integration | 7 passed, PostgreSQL 17 with pgvector 0.8.7 in an isolated local container |
| Integration cleanup | Temporary container and network removed; existing pilot services retained |
| Distribution metadata | Wheel and source package accepted by Twine |
| Clean installation | New environment outside checkout; imported the installed wheel |
| User journey | CLI/module entry points, PASS, FAIL, ERROR, INCONCLUSIVE, overwrite refusal and JSON/HTML output passed |
| Numeric contract | Matching, mismatched and missing structured values behaved as expected |
| Optional database driver | Wheel's `postgres` extra installed and imported successfully |
| Source package | Rebuilt wheel was byte-identical within the same build environment |
| Dependency audit | 16 installed third-party packages, including installer and optional driver; no known vulnerabilities found after installer update |
| Independent acceptance | Pending |

The first empty environment inherited pip 25.0 from Python. Its advisory scan found
known installer vulnerabilities. Updating to pip 26.2.2 removed those findings. The
documented installation and verification script now require `pip>=26.2,<27` before
installing the wheel. The initial failure and subsequent audit remain in private logs;
the scan is an observation at this date, not a security certification.

The PostgreSQL test reused the existing local image
`pgvector/pgvector:0.8.7-pg17` at
`sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d`.
Its port was assigned dynamically on loopback. Tests used a SELECT-only account and
synthetic fixture data. No image/model download, paid service or hosted job was needed.
The first attempt used an unavailable Compose CLI plugin; the successful run used the
standalone Compose executable installed on this host.

The private distribution work directory contains `verification.json`, actual dependency
versions, archive inventories and per-command logs. Final artifacts and SHA-256 sums
are under `dist/beta-0.2.0b1`. Logs, environments and synthetic execution reports are
excluded from release attachments and Git. See [the build guide](beta-release.md).

The source archive includes an explicit project-file allowlist. Wheel notices match
the repository's Apache-2.0 license and NOTICE. Archive checks reject private runtime
files; a separate scan checked project text against known local private values.
No decorative separators, unwanted attribution or new personal absolute paths were
introduced.

Windows and Linux clean-install checks remain pending for this preparation. Prior
Linux CI results are historical and are not presented as new local runs. The current
push deliberately skips hosted workflows; maintainers must review any required checks
before merging. No release, tag or package-index upload is performed here.

The Haystack evidence remains 22 passes and 24 failures from 46 fresh questions.
Source and runtime fingerprints and the frozen evaluation seal were preserved.
See [the full evaluation](../examples/second_pilot/FRESH_REVIEW.md). A consistent index
and a faithful quotation do not establish complete answer relevance.
