# Beta finalization pull request

Suggested title:

```text
Finalize 0.2.0b1 documentation and local distribution checks
```

Copy the description below for the maintainer's PR from
`feat/second-local-rag-pilot` into `main`. It describes the changes after
[the initial beta integration](https://github.com/lynvera-ai/ragparity/pull/1).
PR creation, merging and publication remain with the maintainer.

## Description

Make the 0.2.0b1 beta easier to install, understand and verify before publication.
The project now has a focused overview, a documentation entry point and guides for
CLI use, Python integration, architecture, diagnostics and installation maintenance.
A Spanish quick start complements the English reference documentation.

Distribution preparation now requires a clean fixed commit. It verifies wheel and
source installation separately and produces a reviewable bundle containing both
packages, release notes, build information and SHA-256 checksums. The core checker,
public runtime contracts and experimental chat behavior are unchanged.

### Changes

- Explain installation choices, tested/pending platforms, first-use results and
  troubleshooting; document updates, rollback and package removal without deleting user data.
- Add CLI, Python and architecture references, navigation and a Spanish first-use guide.
- Verify clean wheel/source installs, an identical source rebuild, the optional database
  driver and uninstall preserving synthetic configuration and reports.
- Reject uncommitted source changes and record the source commit in `BUILD_INFO.json`.
  Copy the reviewed notes and hash all four bundle files in `SHA256SUMS`.
- Keep beta limitations explicit, including the 24 failures in the experimental
  Haystack evaluation and pending independent user acceptance.

### Validation

The existing local candidate was built from `a20f2f1e2e91aa2a8515b919364ac90cc729cbbf`.
These results describe that candidate, not a future merge commit:

- 303 unit tests passed with 95.79% core coverage; the suite also passed against
  the installed final wheel and its freshly resolved dependencies.
- All 37 distribution checks passed on macOS ARM64 with Python 3.12.9.
- Wheel/source metadata, documentation examples, archive contents and all four
  bundle hashes were checked. The copied notes match the source notes exactly.
- The audit of 16 runtime dependencies found no known vulnerabilities.
- Earlier seven PostgreSQL/pgvector integration checks remain evidence for the
  unchanged core; they were not rerun for these documentation changes.

Private environments, raw reports and execution logs are excluded from the public
bundle and Git. Hosted workflows are skipped for the preparation commits; no remote
CI result is claimed for this head. No paid service or new hosted automation is used.

### Scope and follow-up

The supported beta scope is deterministic metadata and structured numeric validation.
The Haystack fresh evaluation remains 22/46; chat examples are experimental. Windows
and Linux clean-install checks and independent application acceptance remain pending.
These limits must remain visible; broader acceptance and the 1.0 gates are separate work.

### Publication handoff

- [ ] Review the effective branch rules and any required checks, then review and merge
  this PR through the maintainer's process.
- [ ] Select the approved release commit, review final note wording/versioned links,
  and rebuild the five-file bundle from that clean commit into a new output directory.
- [ ] Verify version 0.2.0b1, license/notices, `BUILD_INFO.json` source identity and all
  checksums. Do not label the existing a20f2f1 bundle as built from a later commit.
- [ ] When publication is separately authorized, create `v0.2.0b1` and a GitHub prerelease,
  attach the verified bundle, then test installation from the actual download.

No PR, merge, tag, GitHub Release or PyPI upload is performed by this preparation.
