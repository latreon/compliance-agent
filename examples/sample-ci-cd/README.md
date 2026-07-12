# `sample-ci-cd/` — gating a PR on EU AI Act compliance

The root [README](../../README.md#cicd-integration) shows a two-line CI
snippet. This directory is the runnable version: a real (if tiny) AI feature
plus a real `.github/workflows/compliance-gate.yml` you can copy wholesale
into your own repository.

## What the workflow does

`.github/workflows/compliance-gate.yml`:

1. Checks out the repo and installs `compliance-agent` from PyPI.
2. Runs `compliance-agent scan . --ci --fail-on high` — `--ci` keeps the log
   plain (no color/spinners); `--fail-on high` fails the job on statutory
   gaps and above. `critical` is reserved for high-risk-tier/prohibited-
   practice obligations, so a LIMITED-tier project like this one (a plain
   AI feature, no Annex III domain) would never hit that gate at all — see
   below.
3. Always (even on failure) generates a PDF report and uploads it as a build
   artifact, so a reviewer has something to open regardless of outcome.

## Adopting this in your own repo

1. Copy `.github/workflows/compliance-gate.yml` into your repo's
   `.github/workflows/`.
2. Change `compliance-agent scan .` to point at the subfolder that holds your
   AI code, if it is not the repo root.
3. Pick a `--fail-on` threshold:

   | Threshold | Blocks the build on |
   |-----------|----------------------|
   | `critical` | Only blocking obligations (e.g. a prohibited practice, a missing QMS for a high-risk system) — **only reachable for a HIGH/UNACCEPTABLE-tier project**; see [`sample-hiring-tool`](../sample-hiring-tool) for one |
   | `high` | The above, plus statutory-but-not-blocking gaps (e.g. missing event logging) — reachable at any risk tier |
   | `warning` | The above, plus recommended-practice gaps |
   | `info` | Everything, including informational findings |

   `high` is the safer default: for a LIMITED-tier project (most chatbots
   and internal tools), `critical` never fires, so a gate set to `critical`
   silently does nothing. Use `critical` deliberately, only once you have
   confirmed your project is HIGH-risk and want to allow known non-blocking
   gaps to merge.
4. Exit codes: `0` success, `1` the `--fail-on` threshold was met, `2` a usage
   error (bad path, bad flag) — the workflow fails the job the same way either
   of the last two happen, so treat a red check as "go read the log."

## Try it locally

```bash
pip install -r requirements.txt
compliance-agent scan . --ci --fail-on critical   # exits 0: this project is LIMITED-tier, not high-risk
compliance-agent scan . --ci --fail-on high       # exits 1: this app.py is non-compliant on purpose
compliance-agent recommend . --output ./fixes     # generates the fix templates that close the gate
```

## Alternative: pre-commit hook

For a faster local-only gate (before code even reaches CI), see the
pre-commit example in the [root README](../../README.md#cicd-integration).
