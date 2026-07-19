# CI/CD — Full Reference

The root [README](../README.md#cicd-integration) and
[`examples/sample-ci-cd`](../examples/sample-ci-cd) cover the two-minute
setup: the GitHub Action, or the CLI installed by hand, gated with
`--fail-on`. This doc is the underlying mechanics — what "fail on X" actually
checks, exact exit codes, the GitHub Action's full input/output surface, and
how to wire this into a CI system other than GitHub Actions.

## `--fail-on` mechanics

Severities are strictly ordered: `info < warning < high < critical`
(`Severity` in `models/findings.py`).

"Fail on X" means: **any finding or gap at severity X or above exists.**
Concretely, the gate checks two things — not just one:

```text
threshold met  ⟺  any(finding.severity >= X for finding in result.findings)
              or  any(gap.severity      >= X for gap      in result.gaps)
```

This matters because **detectors only ever emit `info`/`warning` findings**
— the severe `high`/`critical` signals live entirely in **gaps** (a missing
mandatory control at HIGH risk tier, or an Art. 5 prohibited-practice
match). A gate that only inspected `findings` would silently pass on an
`UNACCEPTABLE`-tier project — checking both is what makes `--fail-on
critical`/`--fail-on high` meaningful at all.

**A scan that couldn't fully analyze every file always fails the gate**,
regardless of your threshold — if any file triggered a scan error (a
detector crashed on it), the gate fails because coverage is unknown and an
incomplete scan can't be trusted to have found everything. When this is what
tripped the gate, a separate message is printed to stderr explaining it's a
scan-error-forced failure — from the exit code alone, "gate threshold met"
and "scan was incomplete" look identical (both exit `1`), so **read the CI
log, not just the exit code**, when a job goes red.

**The gate evaluates the full, unfiltered scan result** — not whatever
`--severity` chose to display. `--severity high --fail-on warning` can still
exit 1 from a warning-level item that `--severity` hid from the printed
report. `--severity` only controls what's shown; `--fail-on` always sees
everything.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Scan ran; gate not triggered (or no `--fail-on` given at all). |
| `1` | Gate triggered — threshold met, or the scan had errors (see above). |
| `2` | Usage/setup error — bad project path, invalid `--format`, invalid `--severity`/`--fail-on` value, or a malformed `compliance.yaml`. Same code for the `recommend`/`report`/`diff` commands' equivalent errors. |

## Gating on risk tier vs. severity

`--fail-on` is **severity-only** — there is no flag to gate directly on risk
tier (`UNACCEPTABLE`/`HIGH`/`LIMITED`/`MINIMAL`; see
[GLOSSARY.md](GLOSSARY.md#risk-tier)). The gap analyzer only ever emits
`critical`-severity gaps when the project is already classified HIGH or
UNACCEPTABLE tier, so `--fail-on critical` acts as a de facto tier gate in
practice — but it's an indirect consequence, not a guarantee. There's no way
to say "fail if tier is HIGH or above" independent of whether that tier
happens to have produced a critical-severity gap yet.

## `compliance.yaml` in CI

If the scanned project has a `compliance.yaml` (see
[CONFIGURATION.md](CONFIGURATION.md)), its `scan.fail_on`/`scan.severity`/
`scan.format` become the defaults for a CI run too — an explicit `--fail-on`
CLI flag (or Action input) always overrides the file, but if you omit it,
the project's own committed config decides the gate. `exclude`/`include`
glob lists are combined additively between the config file and CLI/Action
args, never replaced by one or the other.

## GitHub Action (`action.yml`)

| Input | Description | Default |
|---|---|---|
| `path` | Directory to scan, relative to the workspace | `.` |
| `format` | `sarif` (default), `json`, or `markdown` | `sarif` |
| `output` | File to write the report to | `compliance-results.sarif` |
| `fail-on` | Fail the build at this severity or above: `info`/`warning`/`high`/`critical`. Empty = never fails | `""` |
| `args` | Extra arguments passed verbatim to `compliance-agent scan` | `""` |
| `python-version` | Python version used to run the scanner (needs ≥ 3.12) | `3.12` |

**Output:** `report` — path to the generated report file.

**What it actually runs** (composite action): sets up the requested Python
version, installs the CLI **from the Action's own pinned checkout** (not
from PyPI) so the scanner version always matches the Action's tag exactly,
then runs `compliance-agent scan "$path" --ci --no-update-check --format
"$format" --output "$output"` (plus `--fail-on` and `args` if set). Inputs
are passed through environment variables rather than interpolated directly
into the shell script, specifically so a crafted input value can't inject
shell syntax.

## SARIF from the CLI directly

SARIF isn't Action-only or MCP-only — it's a first-class CLI format:

```bash
compliance-agent scan . --format sarif --output results.sarif
```

The GitHub Action is just this same command with `format` defaulting to
`sarif`. This means you can produce a SARIF file in **any** CI system, then
upload it however that system's code-scanning integration expects.

## Non-GitHub CI systems

There's no bundled Action/plugin for these — wire up the CLI directly, same
shape as `examples/sample-ci-cd`'s "Option B":

**GitLab CI** (`.gitlab-ci.yml`):

```yaml
compliance-scan:
  image: python:3.12
  script:
    - pip install compliance-agent
    - compliance-agent scan . --ci --fail-on high --format json --output compliance-report.json
  artifacts:
    when: always
    paths:
      - compliance-report.json
```

**CircleCI** (`.circleci/config.yml`):

```yaml
jobs:
  compliance-scan:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run: pip install compliance-agent
      - run: compliance-agent scan . --ci --fail-on high --format json --output compliance-report.json
      - store_artifacts:
          path: compliance-report.json
```

**Generic / self-hosted runner or Jenkins** — same three steps as above:
install from PyPI (`pip install compliance-agent`), run `scan --ci --fail-on
<threshold>`, and archive whichever `--format` output your platform's
artifact/reporting step expects. There's no network dependency beyond the
PyPI install and (unless `--no-update-check`/`COMPLIANCE_AGENT_NO_UPDATE_CHECK`
is set) an optional version check — no license server, no phone-home, so an
air-gapped or private-registry setup only needs to make the PyPI package (or
a mirrored copy of it) available to `pip install`.

## Local pre-commit gate

For a faster feedback loop than waiting on CI, see the pre-commit hook
example in the [root README](../README.md#cicd-integration) — same
`--fail-on` semantics, running before code is even pushed.
