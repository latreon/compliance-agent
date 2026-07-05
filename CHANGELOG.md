# Changelog

All notable changes to ComplianceAgent are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.7] - 2026-07-05

### Fixed

- **PDF generation now works on macOS/Homebrew out of the box.** WeasyPrint's
  native libraries (pango, gobject, cairo) live in `/opt/homebrew/lib` (or
  `/usr/local/lib` on Intel), which macOS `dyld` does not search by default — so
  `scan --format pdf` failed with "cannot load library 'libgobject-2.0-0'" even
  after `brew install pango`. The reporter now primes
  `DYLD_FALLBACK_LIBRARY_PATH` with the Homebrew lib directory before importing
  WeasyPrint, so no manual environment export is needed. The failure message was
  also simplified accordingly.

## [0.1.6] - 2026-07-05

Correctness, security, and honesty fixes from a full pre-promotion review.

### Fixed

- **`--fail-on` now considers compliance gaps, not just findings.** Detectors
  only emit INFO/WARNING findings; the severe signals (CRITICAL Art. 5
  prohibited practice, HIGH oversight/robustness gaps) live in `gaps`. The CI
  gate previously inspected findings alone, so `--fail-on high`/`critical`
  silently passed builds on high-risk and UNACCEPTABLE-tier projects.
- **Test-fixture paths no longer inflate the risk tier.** A file such as
  `tests/recruitment.py` is sample data, not the deployed system. The scanner
  already excluded test paths from its domain corpus; the risk classifier's
  second corpus (finding paths/messages) did not, so descriptively named
  fixtures could push a project to a false HIGH/UNACCEPTABLE tier. Both corpora
  now apply the same exclusion.
- **A requirement can no longer be marked "met" from a code comment.** The
  documentation probe strips Python comments before matching, so a leftover
  `# TODO: add an AI disclosure` no longer counts as an implemented mechanism.
  Test directories are also excluded from the probe.
- **BOM-prefixed source files are parsed correctly.** A leading byte-order mark
  (common from Windows editors) previously made `ast.parse` fail the whole
  file, silently degrading provider detection to import-line-only regex and
  missing constructor/API-call evidence.

### Security

- **The scanner no longer follows symlinks.** Scanning an untrusted repository
  containing a symlink to a file outside the project (e.g. `utils.py ->
  ~/.ssh/id_rsa`) could read arbitrary local files, and a symlink to a device
  node (`/dev/zero`) bypassed the size cap and could hang the scan. File reads
  are additionally byte-capped independently of the reported size.

### Changed

- **Every LIMITED/MINIMAL result now carries a domain caveat** (terminal header
  and risk reasoning): keyword-based domain detection can miss high-risk uses
  expressed in ordinary wording, so a low tier is never presented as "safe".
- Broadened Annex III keyword coverage (hiring, credit/insurance, education,
  biometrics synonyms) to improve recall, and replaced the collision-prone bare
  `biometric` keyword with specific phrases.
- Single-sourced the severity ranking used for gap ordering and the `--fail-on`
  gate, so the two can no longer drift.

## [0.1.5] - 2026-07-05

Accuracy and honesty hardening so the tool neither under-warns high-risk
projects nor asserts false "compliant" verdicts.

### Changed

- **Risk classification now inspects code content, not just file names.** Annex
  III / Art. 5 domain keywords are matched against the scanned project's file
  paths **and actual file content**, so an AI hiring or credit-scoring system is
  classified HIGH even when its files are plainly named (e.g. `app.py`).
  Previously classification effectively keyed off file/directory names only.
- **Domain classification is gated on real AI usage.** A project is only
  escalated to HIGH/UNACCEPTABLE when an AI provider or framework is actually
  detected — the EU AI Act governs AI systems, and this prevents false high-risk
  flags on projects that merely mention these domains. Test fixtures and
  documentation/config prose no longer drive classification (they are
  false-positive prone).
- **Article requirements are no longer marked "met" from documentation prose.**
  A requirement is **Met** only with a verifiable signal — a real code mechanism
  or a concrete artifact file. An obligation merely *referenced* in prose is now
  reported as a new **Unverified** state ("referenced, but not confirmed — verify
  manually"), never as compliant. This removes false compliance assurance (e.g.
  a README saying "conformity assessment" no longer marks Art. 43 as met).

### Added

- **Legal disclaimer on every output surface.** The "not legal advice" disclaimer
  now appears in the terminal, Markdown, JSON (`disclaimer` field), and CI output
  — previously it was only in the PDF/HTML.
- Art. 5(1)(b) exploitation-of-vulnerabilities to the prohibited-practice rules.
- Static type checking (`mypy`) in CI and the dev dependencies.

### Fixed

- The terminal "no issues" message no longer claims the project "looks
  compliant"; it states that static analysis found no gaps and is not a
  compliance determination.
- Deduplicated the path/format validation shared by `scan`, `recommend`, and
  `report`.
- Repointed the dead "Discussions" issue-template link (Discussions is disabled)
  and added the Python 3.13 trove classifier.
- Regenerated `examples/EXPECTED_OUTPUT.md` against a real 0.1.5 run and
  relabelled the Markdown summary (the default `scan` renders the boxed terminal
  report; the Markdown form is produced by `--ci` / `report --format markdown`).

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
  findings, 10 gaps, `tool_version` 0.1.4, Art. 50 correctly flagged).
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

[Unreleased]: https://github.com/latreon/compliance-agent/compare/v0.1.7...HEAD
[0.1.7]: https://github.com/latreon/compliance-agent/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/latreon/compliance-agent/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/latreon/compliance-agent/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/latreon/compliance-agent/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.3
[0.1.2]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.2
[0.1.1]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.1
[0.1.0]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.0
