# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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

### Added

- **Art. 5 prohibited-practices detection.** Projects matching a prohibited
  practice are classified **UNACCEPTABLE** with a blocking Art. 5 gap.
- Word-boundary keyword matching and a confidence floor for HIGH-risk
  classification (no longer reported at 0.25 confidence).
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue/PR templates.

### Changed

- Annex III keywords narrowed to specific multi-word phrases to cut false HIGH
  classifications from generic words (`student`, `electricity`, `voting`, …).
- HIGH-risk classification now notes the Art. 6(3) narrow-purpose exemption.
- Recommender framework→article mappings regrouped to defensible categories
  (oversight / record-keeping / documentation).
- Single shared filesystem probe per analysis (removes duplicated file reads).
- `--version` short flag is now `-V` (was `-v`, which collided with `--verbose`).
- CI test matrix covers Python 3.12 and 3.13.

## [0.1.3]

- `-v`/`--version` flag, update notifier, boxed terminal sections, PDF branding.

## [0.1.0] – [0.1.2]

- Initial public releases: scanner engine, detectors, risk classifier, gap
  analyzer across EU AI Act articles, fix templates, PDF/Markdown/JSON reports,
  and the `scan` / `recommend` / `report` / `upgrade` commands.
