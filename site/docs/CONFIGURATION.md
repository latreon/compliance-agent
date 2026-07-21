# Configuration — Full Reference

The root README's
[Project config file section](../README.md#project-config-file-complianceyaml)
covers the everyday case: declare your posture and scan defaults once in
`compliance.yaml`. This doc is the precise mechanics — file discovery order,
exactly which command uses which field, and how config merges with CLI
flags field-by-field.

## File discovery

On every run, ComplianceAgent looks for one of these in the project root, in
this order, and uses the **first one found**:

1. `compliance.yaml`
2. `compliance.yml`
3. `.compliance.yaml`
4. `.compliance.yml`

No project config at all is a valid, common state — every field simply
falls back to its CLI default. A config file larger than 256 KB is rejected
outright (`"...is larger than 256 kB — that is not a compliance config
file"`) — this file is meant to hold a handful of scan defaults and a
posture declaration, not grow into a general project manifest.

## Schema

```yaml
version: 1                # required; only 1 is currently supported

posture:
  risk_tier: high          # unacceptable | high | limited | minimal
  intended_purpose: "CV screening assistant for the recruiting team"

scan:
  exclude: ["docs/*", "notebooks/*"]
  include: []
  fail_on: high             # info | warning | high | critical
  severity: warning         # info | warning | high | critical
  format: markdown          # markdown | json | pdf | html | sarif
  output: null
```

Every field is optional — an empty file (or a file with just `version: 1`)
is a fully valid "all defaults" config. The schema rejects **unknown keys**
outright (`extra="forbid"` on every section) — a typo like `risk_teir` is a
hard config error, not a silently-ignored field.

| Section | Field | Type | Maps to |
|---|---|---|---|
| `posture` | `risk_tier` | `unacceptable`\|`high`\|`limited`\|`minimal` | See [tier precedence](#risk-tier-declaration) below. |
| `posture` | `intended_purpose` | string | Recorded in the report; not otherwise validated. |
| `scan` | `exclude` | list of glob strings | Merged additively with `--exclude`. |
| `scan` | `include` | list of glob strings | Merged additively with `--include`. |
| `scan` | `fail_on` | severity | Default for `--fail-on` (scan command only). |
| `scan` | `severity` | severity | Default for `--severity` (scan command only). |
| `scan` | `format` | one of `markdown`/`json`/`pdf`/`html`/`sarif` | Default for `--format` (scan command only). |
| `scan` | `output` | string path or `null` | Default for `--output` (scan command only). |

A malformed config (bad YAML, wrong types, an invalid enum value, an unknown
key, `version` not equal to `1`) is a **hard error, exit code 2**, on every
command that reads it — never silently treated as "no config." The error
names the exact field and problem, e.g. `fail_on: hihg` fails validation
with a message naming `scan.fail_on` and the bad value, rather than quietly
disabling your CI gate.

## Precedence rules

**Explicit CLI flags always win.** A config field only fills in a flag you
didn't pass — it never overrides one you did.

**List fields merge additively, scalar fields don't.** `exclude`/`include`
from the CLI and from `compliance.yaml` are combined (deduplicated, config
values appended after CLI-supplied ones) — someone who has `exclude:
["docs/*"]` in config and passes one extra `--exclude tests/*` on the
command line gets both applied, not one silently dropping the other. Every
other field (`fail_on`, `severity`, `format`, `output`) is a plain
CLI-flag-wins-or-config-fills-in — there's no equivalent merge for a scalar.

### Risk tier declaration

`posture.risk_tier` can only **raise** the tier the scanner detects, never
lower it — this is deliberate, so a config file can't be used to manufacture
false assurance about a project's actual risk. Concretely:

- Declaring `high` on a project the heuristics classified `limited` raises
  it to `high` (the report records the reason: "declared in
  compliance.yaml").
- Declaring `minimal` on a project the heuristics classified `high` changes
  **nothing** except a note that the higher, detected tier still applies.
- Declaring `unacceptable` always wins, since nothing outranks it anyway.

## Which command uses which fields

Not every field applies to every command — `scan.fail_on`/`severity`/
`format`/`output` are **`scan`-command-only** defaults (they mirror CLI flags
that only `scan` has). `posture.risk_tier` and `scan.exclude`/`include`,
however, are used everywhere the project gets analyzed, so `recommend` and
`report` see the same effective project (same exclusions, same declared
tier) that `scan` would:

| Command | Uses `scan.exclude`/`include` | Uses `posture.risk_tier` | Uses `scan.fail_on`/`severity`/`format`/`output` |
|---|---|---|---|
| `scan` | ✅ | ✅ | ✅ |
| `recommend` | ✅ | ✅ | — (no such flags exist on `recommend`) |
| `report` | ✅ | ✅ | — (`report` has its own `--format`/`--output`, not fed from `scan.*`) |
| `serve` | — | — (see below) | — |
| MCP tools (`scan_project`, `get_summary`, etc.) | ✅ | ✅ | n/a (MCP tools don't have a fail-on gate) |

`serve` validates the config file at startup (so a broken `compliance.yaml`
surfaces as a clear error immediately, rather than a confusing failure the
first time someone clicks "Scan" in the dashboard), but the dashboard's own
`POST /api/scan` endpoint re-loads and applies the config the same way the
CLI does for each scan it runs — it isn't skipped, it's just loaded per
request rather than once at `serve` startup.

## See also

- [README's Project config file section](../README.md#project-config-file-complianceyaml) — the everyday quick-start.
- [GLOSSARY.md](GLOSSARY.md#risk-tier) — what each risk tier means.
- [CI-CD.md](CI-CD.md#complianceyaml-in-ci) — how this interacts with a CI gate.
