# Changelog

All notable changes to ComplianceAgent are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed / Documentation

- Corrected the README "What You'll See" and worked examples to match the
  actual boxed terminal report and the real risk-classification behavior
  (HIGH comes only from an Annex III domain match).
- Clarified that the `UNACCEPTABLE` (Art. 5) tier is **not** auto-detected and
  must be self-assessed; removed the implication that the tool outputs it.
- Regenerated `examples/EXPECTED_OUTPUT.md` against real output (3 files, 6
  findings, 9 gaps) and fixed the stale `tool_version` (0.1.0 → 0.1.3).
- Documented previously hidden flags: `scan --include`, `--no-color`,
  `--quiet`, `--verbose`, and `recommend --format json`; documented the
  `NO_UPDATE_NOTIFIER` env var, the scannable file types, and the 1 MB file cap.
- Marked `compliance_config.yaml` as a documentation-only artifact (the scanner
  does not read it yet).

### Added

- `CHANGELOG.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `docs/ARCHITECTURE.md`,
  and GitHub issue/PR templates.
- PyPI `classifiers` and `[project.urls]` metadata; release process in
  `CONTRIBUTING.md`.
- Troubleshooting entries for Python 3.12+ install failures and for
  wrong-tier / false-negative detection.

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
  analysis for 12 articles.
- Fix recommender with copy-pasteable templates; terminal, Markdown, JSON, and
  PDF reports.

[Unreleased]: https://github.com/latreon/compliance-agent/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.3
[0.1.2]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.2
[0.1.1]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.1
[0.1.0]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.0
