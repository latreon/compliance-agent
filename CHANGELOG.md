# Changelog

All notable changes to ComplianceAgent are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.4] - 2026-07-04

### Fixed

- **Correct EU AI Act article numbers in reports.** Conformity assessment is now
  reported as **Art. 43** (was Art. 7), provider obligations as **Art. 16** (was
  Art. 26), and distributor obligations as **Art. 24** (was Art. 28).
- **Requirement checks no longer pass on incidental substrings.** Doc/code
  keyword probes now match on word boundaries, so `auth` no longer satisfies the
  Art. 15 cybersecurity check via `__author__`, and a README that merely mentions
  "AI disclosure" (or says it is missing) no longer marks Art. 50 as met.
- **Art. 50 disclosure is judged from code, not prose** — "met" now requires an
  actual disclosure mechanism, and the gap is rated HIGH (was WARNING).
- **`recommend` no longer prints "nothing to recommend" when gaps exist** without
  a fix template; it now lists the affected articles.
- Corrected the README "What You'll See" and worked examples to match the actual
  boxed terminal report and the real risk behavior (HIGH comes only from an
  Annex III domain match; tool access alone does not raise the tier).
- De-contaminated `examples/sample-chatbot` (now only `app.py` +
  `requirements.txt`) so the scanner no longer ingests the sample's own docs,
  and regenerated `examples/EXPECTED_OUTPUT.md` against a real run (1 file, 4
  findings, 10 gaps, `tool_version` 0.1.3, Art. 50 correctly flagged).
- Marked `compliance_config.yaml` as a documentation-only artifact (the scanner
  does not read it yet).
- Fixed a per-detector line-split cache that could return a previous file's
  lines when a reused detector instance processed a later same-length file
  (CPython address reuse), misattributing findings; added a multi-file
  regression test.

### Added

- **Art. 5 prohibited-practices detection.** Projects matching a prohibited
  practice are classified **UNACCEPTABLE** with a blocking Art. 5 gap (previously
  the tier existed but was never assessed).
- Word-boundary keyword matching and a confidence floor for HIGH-risk
  classification (no longer reported at 0.25 confidence).
- `CHANGELOG.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `docs/ARCHITECTURE.md`,
  and GitHub issue/PR templates.
- PyPI `classifiers` and `[project.urls]` metadata; release process in
  `CONTRIBUTING.md`.
- Documented previously hidden flags: `scan --include`, `--no-color`,
  `--quiet`, `--verbose`, `--no-update-check`, and `recommend --format json`;
  documented the `NO_UPDATE_NOTIFIER` env var, scannable file types, and the
  1 MB file cap. Troubleshooting entries for Python 3.12+ install and for
  wrong-tier / false-negative detection.

### Changed

- Annex III keywords narrowed to specific multi-word phrases to cut false HIGH
  classifications from generic words (`student`, `electricity`, `voting`, …).
- HIGH-risk classification now notes the Art. 6(3) narrow-purpose exemption.
- Recommender framework→article mappings regrouped to defensible categories
  (oversight / record-keeping / documentation).
- Single shared filesystem probe per analysis (removes duplicated file reads);
  library warnings/errors now route through Rich and respect `--verbose`.
- `--version` short flag is now `-V` (was `-v`, which collided with `--verbose`).
- CI test matrix covers Python 3.12 and 3.13.

## [0.1.3] - 2026-07

### Added

- `--version` / `-v` top-level flag; version shown on bare invocation.

### Changed

- Uniform boxed terminal sections, consistent spacing, and a boxed "Next Steps"
  panel.

## [0.1.2]

### Added

- Update notifier: after a scan, reports when a newer version is on PyPI
  (cached daily, skipped in CI/JSON, opt-out via env var).
- `upgrade` command that auto-detects the install method (uv / pipx / pip).

### Fixed

- Installation and versioning hardening (single-source version via Hatch,
  bundled `templates/` and `rules/` in the wheel).

## [0.1.1]

### Changed

- Boxed Scan Summary and consistent section spacing in terminal output.

## [0.1.0]

### Added

- Initial release: AST-based scanner for AI providers (OpenAI, Anthropic,
  Mistral, Google, local runtimes), agent patterns, and framework detectors
  (LangChain, CrewAI, AutoGen, LangGraph).
- EU AI Act risk classification (Annex III) and per-article coverage/gap
  analysis.
- Fix recommender with copy-pasteable templates; terminal, Markdown, JSON, and
  PDF reports.

[Unreleased]: https://github.com/latreon/compliance-agent/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/latreon/compliance-agent/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.3
[0.1.2]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.2
[0.1.1]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.1
[0.1.0]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.0
