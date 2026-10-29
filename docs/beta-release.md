# Prepare the 0.2.0b1 beta locally

This guide prepares distribution files for review. It does not publish a GitHub
Release, create a tag, merge a branch, upload to PyPI or start remote automation.
Package downloads use free public dependencies; model APIs and paid infrastructure
are not part of this process.

## Release scope

The beta supports the documented metadata and structured numeric contracts through
the library and CLI. Memory readers, PostgreSQL/pgvector metadata readers, chunk
manifests, bounded scans and JSON/HTML reports are included. Application chats are
experimental examples, not a supported general-purpose answer-verification service.
The Haystack fresh evaluation remains 22/46 with all 24 failures preserved.

Independent acceptance is pending. Installation on another person's machine and
application evidence are required before claiming that gate is satisfied. See
[the feedback procedure](beta-feedback.md) and [the 1.0 gates](releases.md#gates-for-10).

## Build and verify

Use a checkout on a working branch and a Python 3.12+ environment. Install development
tools only in that environment:

```bash
python -m pip install -e '.[dev,postgres]' 'twine>=6,<7'
python -m ruff check src tests examples benchmarks tools
python -m ruff format --check src tests examples benchmarks tools
python -m mypy src
python -m pytest tests/unit --cov=lynvera_ragparity --cov-fail-under=95
python tools/prepare_beta.py
```

Commit the intended changes before running the script. It refuses a dirty checkout
and checks that the source commit stays fixed through the preparation.
The script creates a new `dist/beta-0.2.0b1-final` directory. It refuses to replace an
existing directory; use `--output-dir /path/to/new-directory` for another run.
`--work-dir /path/to/new-private-directory` chooses where logs and environments live.
That directory must be outside the checkout. It is retained for inspection with
private permissions and must not be committed or attached to a public issue.

Checks include:

- Version agreement, metadata validation and intended archive contents.
- Apache-2.0 license and maintainer notice included in both packages.
- A clean wheel installation in a new environment outside the checkout.
- A current installer (`pip>=26.2,<27`) instead of the older copy bundled with Python.
- Import origin, dependency consistency and absence of optional pilot/model packages.
- CLI and module entry points, initial PASS, deliberate FAIL, configuration ERROR,
  empty-scan INCONCLUSIVE, numeric contracts and overwrite refusal.
- JSON/HTML generation and redacted output using synthetic metadata.
- A byte-identical wheel rebuilt from the source package with the same build timestamp.
- Direct source-archive installation in a second clean environment, followed by the
  initial check, HTML report and uninstall preserving the synthetic user files.
- Installation and import of the optional PostgreSQL driver after the core-only checks.

The source package uses an explicit content allowlist. The wheel contains the library
and distribution metadata, not the optional pilots. The source package includes docs,
examples and tests but excludes local runtime data and automation configuration.
Review the inventory and perform a private-value scan before publishing; an allowlist
does not detect a secret accidentally written into a permitted source file.

The script stores `verification.json`, dependency versions and individual logs in its
private work directory. It records the Git revision and whether the checkout was dirty.
For final release artifacts, use a clean reviewed commit. The timestamp comes from that
commit. Rebuild identity was checked within the same environment; this is not a claim
of independent reproducibility across different backend versions or platforms.

## Artifacts for review

The output directory contains:

```text
lynvera_ragparity-0.2.0b1-py3-none-any.whl
lynvera_ragparity-0.2.0b1.tar.gz
RELEASE_NOTES.md
BUILD_INFO.json
SHA256SUMS
```

Only those five files are candidates for release attachments. Keep environments,
credentials, reports, source documents, chat receipts and raw execution logs private.
Read [the proposed release notes](release-notes-0.2.0b1.md) and update them if the
reviewed scope changes. The `dist` directory is ignored by Git.

`RELEASE_NOTES.md` is an exact copy of the reviewed notes in `docs`. `BUILD_INFO.json`
records the source commit, build timestamp, package/notes hashes and the platform actually
checked. It contains no private work paths or logs. `SHA256SUMS` covers the four other
bundle files. This record is not an independent attestation or cryptographic signature.

After obtaining all five files from the intended source, verify the bundle with Python
from its directory:

```python
import hashlib
from pathlib import Path

for line in Path("SHA256SUMS").read_text().splitlines():
    expected, name = line.split("  ", 1)
    actual = hashlib.sha256(Path(name).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit("Checksum mismatch: " + name)
print("All bundle checksums match")
```

## Maintainer publication steps, still pending

The [beta finalization PR description](pull-request-0.2.0b1.md) covers documentation
and local distribution changes after the maintainer merged PR #1. The current local
bundle records `a20f2f1` as its source; a different approved release commit requires
its own rebuilt and verified bundle. Preparation notes do not substitute for that check.

1. Review and integrate any remaining changes into `main` through the maintainer's PR.
2. Recheck version, changelog, license, notices and the exact intended commit.
3. Run the local checks above on that commit and review package inventories and hashes.
4. Confirm the account's permissions and any external automation billing settings before
   running hosted jobs. This preparation uses local checks and does not require them.
5. Create the reviewed version tag and a GitHub prerelease using maintainer credentials.
   Attach the verified five-file bundle and copy the proposed notes. Those actions
   require a separate publication instruction and are not performed by the script.
6. Verify installation from the actual release download and invite external beta review.

PyPI publication is outside this preparation. No publishing credentials are needed.

## Local verification record

Read [the observed validation record](beta-validation.md) for results, the installer
finding and resolution, and pending platform checks.

The preparation is checked on macOS ARM64 with Python 3.12. It covers a new environment
without access to the checkout's installed development package. Windows and Linux clean
installation are pending external confirmation in this preparation. Prior Linux CI
covers Python and PostgreSQL versions listed in [the compatibility policy](releases.md).
Do not describe those historical jobs as newly executed local platform checks.

The core checker was not changed by this preparation, so the existing resource
measurements remain historical observations rather than newly repeated benchmarks.
The optional pilot services and raw evaluation evidence remain separate and unchanged.

For this local-only preparation, the push commit uses `[skip ci]` so the existing push
workflows do not start. GitHub documents this behavior in
[Skipping workflow runs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs).
Required remote checks may remain pending until a maintainer deliberately runs them
before merging. Existing scheduled jobs are not disabled or modified by this preparation.
