# MCP Server — Full Reference

[MCP](https://modelcontextprotocol.io) (Model Context Protocol) lets an AI
assistant call ComplianceAgent's `scan -> classify -> gaps -> coverage ->
recommendations` pipeline directly as **tools**, instead of shelling out to
the CLI and parsing text output. This doc is the complete reference — tool
signatures, path resolution, security model, and troubleshooting. For a
5-minute quick start (install, run, client config), see the
[README's MCP Server section](../README.md#mcp-server).

Implementation: `src/compliance_agent/mcp_server.py`. Built on
[FastMCP](https://github.com/jlowin/fastmcp).

## Install

```bash
pip install 'compliance-agent[mcp]'
```

## Transports

```bash
compliance-agent-mcp          # stdio — for Claude Desktop, Cursor, etc.
compliance-agent-mcp --http   # HTTP — for remote/shared access
```

**stdio** (the default) needs no configuration. The trust boundary is
"whoever can launch a process on this machine" — identical to running the
CLI directly. This is the right mode for a local assistant driving your own
projects.

**`--http`** changes the trust boundary to "whoever can reach this port," so
it refuses to start without a bearer token and adds three more controls (see
[Security](#security) below). Binds to `127.0.0.1` by default; only widen
`--host` once auth and the allowlist are both configured.

## Path resolution

Every tool that takes a `path` argument resolves it the same way
(`_resolve_project_path` in `mcp_server.py`):

1. **Absolute or relative path** — resolved directly. A relative path
   resolves against **the MCP server process's working directory**, not
   whatever directory the calling assistant or editor has open — always
   prefer an absolute path to avoid surprises.
2. **Bare name, no path separator** (e.g. `"perch"` instead of
   `/Users/me/Developer/perch`) — if it doesn't exist as a literal path,
   the server searches common dev-folder locations, two levels deep:
   `~/projects`, `~/Projects`, `~/Developer`, `~/dev`, `~/code`, `~/work`,
   `~/workspace`, `~/Documents`, `~/src`, `~/repos`, `~/git`, `~/Desktop`
   (and each of *their* immediate subdirectories — so
   `~/Desktop/Playground/perch` is found via the `~/Desktop` root).
   - **Exactly one match** → used transparently.
   - **Multiple matches** → returns an error listing every candidate; pass
     the exact absolute path instead.
   - **No match** → returns an error naming the locations searched.
3. Every resolved path is then checked against
   `COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS` if set (see [Security](#security)) —
   this applies to *all* paths a tool touches (`path`, `output`,
   `output_dir`, `base_path`, `target_path`), not just the project root.

This means you can hand an assistant a project's name and it will usually
find it without you supplying a path — but ambiguous or unusual locations
still need an explicit absolute path.

## Available tools

All tools return a **string** (Markdown or JSON text) and never raise — every
failure mode (bad path, bad severity, unwritable output, oversized project,
timeout, malformed config) is converted to a plain `Error: ...` string
response instead of an exception, so a calling assistant always gets
something it can read and act on.

### `scan_project`

Full compliance scan, from scratch — the most expensive tool. Runs
scan → classify → gaps → coverage → recommendations every time; no cached
state.

| Arg | Type | Default | Notes |
|---|---|---|---|
| `path` | str | — | Project root. See [Path resolution](#path-resolution). |
| `severity` | str | `"info"` | `info` \| `warning` \| `high` \| `critical`. Display filter only — the underlying scan is unaffected. |
| `exclude` | list[str] \| None | `None` | Glob patterns, e.g. `["tests/*", "*.md"]`. Combined with `compliance.yaml`'s excludes, not replaced. |
| `include` | list[str] \| None | `None` | If set, only these globs are scanned. Combined with `compliance.yaml`'s includes. |
| `format` | str | `"markdown"` | `markdown` \| `json` \| `pdf` \| `html`. |
| `output` | str \| None | `None` | Absolute file path. **Required** for `pdf`/`html` (binary/too large to return as text). Optional for `markdown`/`json` — omit to get the report back inline. |

Returns the report text inline, or (when `output` is given, or format is
`pdf`/`html`) a confirmation string naming the absolute path written.
`format="json"` produces the same versioned envelope the CLI's
`--format json` does — feed it into `diff_scans` later.

`compliance.yaml` defaults (declared risk tier, excludes) are loaded and
merged automatically if the project has one. Generating `pdf` needs
WeasyPrint's native libraries (pango/gobject); the error message names what
to install if they're missing.

### `get_summary`

Lightweight scan+classify only — skips recommendation generation, so it's
faster than `scan_project`. Use for a quick "how does this look" check.

| Arg | Type | Notes |
|---|---|---|
| `path` | str | Project root. |

Returns a short Markdown summary: files scanned, detected providers, risk
tier, finding counts by severity. No gaps, coverage, or recommendations — use
`scan_project` or `recommend_fixes` for those.

### `recommend_fixes`

Full pipeline with recommendations enabled; returns just the fix
recommendations section — article, template, numbered steps per gap.

| Arg | Type | Default | Notes |
|---|---|---|---|
| `path` | str | — | Project root. |
| `output_dir` | str \| None | `None` | Absolute directory path. If given, copies the actual template files (preserving `templates/...` structure) plus a `RECOMMENDATIONS.md` into it — the same files `compliance-agent recommend . --output ./fixes` writes. Without it, only recommendation *text* is returned. |

If the project has gaps but no fix template covers them yet, says so
explicitly and names the uncovered articles (never silently empty). Only
covers gaps that map to an existing template — cross-check with
`list_templates` / `get_article_info`.

### `diff_scans`

Compares two **JSON** scan reports (must be `scan_project(format="json")` or
`compliance-agent scan --format json` output — not arbitrary JSON).

| Arg | Type | Default | Notes |
|---|---|---|---|
| `base_path` | str | — | Earlier baseline JSON report file. |
| `target_path` | str | — | Later JSON report file. |
| `format` | str | `"markdown"` | `markdown` (human-readable) or `json` (structured diff). |
| `output` | str \| None | `None` | Absolute path to write the diff to instead of returning it inline. |

Returns risk-tier movement, gaps resolved/new/changed, findings
added/removed/unchanged, requirements-met ratio. A missing file, plain text,
unrelated JSON, or a report from an incompatible schema version all return a
clear error string rather than raising.

**There is no built-in baseline store** — this tool only diffs two files you
already have. To track compliance over time, save each scan's JSON output
somewhere stable (e.g. commit `compliance-report.json` per release, or keep
one in CI artifacts) and pass the previous one as `base_path`.

### `export_sarif`

Scan and render as [SARIF 2.1.0](https://sarifweb.azurewebsites.net/) — the
format `github/codeql-action/upload-sarif` (and most other code-scanning
consumers) expect. Same pipeline as `scan_project` minus recommendation
generation (SARIF has no field for those — use `recommend_fixes` alongside
it if you want fixes too).

| Arg | Type | Default | Notes |
|---|---|---|---|
| `path` | str | — | Project root. |
| `severity` | str | `"info"` | Same semantics as `scan_project`. |
| `exclude` | list[str] \| None | `None` | Same semantics as `scan_project`. |
| `include` | list[str] \| None | `None` | Same semantics as `scan_project`. |
| `output` | str \| None | `None` | Absolute path to write the SARIF file to. Omit to get the SARIF JSON back inline. |

A project with zero findings/gaps still returns valid SARIF (empty `results`
array), never an empty string. See the
[README's CI/CD Integration section](../README.md#cicd-integration) for the
GitHub Action that wires this into the Security tab.

### `get_article_info`

Look up what ComplianceAgent's *own rules and templates* cover for one EU AI
Act article — not the full legal text.

| Arg | Type | Notes |
|---|---|---|
| `article_number` | int | e.g. `5`, `6`, `50`. |

Art. 5 and 6 return the actual rules-file excerpt (prohibited practices /
Annex III), truncated to 2000 chars at a line boundary. Any article with a
template directory returns the list of template files. An uncovered article
number returns a message naming it as such plus the full list of covered
articles — never a bare error.

### `list_templates`

No arguments. Lists every fix template ComplianceAgent ships, grouped by
article directory (e.g. `art50`). Empty/`__pycache__`-only directories are
omitted. Returns `"No templates found."` if the templates directory is
missing or empty — never an empty string. Useful for cross-checking
`recommend_fixes` output against the full catalog before running a scan.

### `get_version`

No arguments. Returns `"ComplianceAgent v{version}"` — a local, offline
lookup (unlike the CLI's `version` command, this does **not** check PyPI for
updates).

## Security

`stdio` needs none of this — same trust boundary as running the CLI
yourself. Everything below applies only to `--http`.

| Environment variable | Purpose | Default |
|---|---|---|
| `COMPLIANCE_AGENT_MCP_TOKEN` | **Required** for `--http`; server refuses to start without it. Bearer token every request must present via `Authorization: Bearer <token>`. Compared with `secrets.compare_digest` (constant-time). Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. | — |
| `COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS` | Comma-separated absolute directories every path a tool touches (`path`, `output`, `output_dir`, `base_path`, `target_path`) must resolve inside — symlinks and `..` resolved before comparison, so a symlink planted inside an allowed root can't point back out. Without it, an authenticated caller can point any tool at any path the server process can read/write. | unset (unrestricted) |
| `COMPLIANCE_AGENT_MCP_MAX_FILES` | Pre-flight file-count guard — rejects a project outright, before reading any content, if it has more scannable files than this. Cheap protection against a whole home directory or filesystem root pointed at by mistake (or maliciously, over `--http`). | `20000` |
| `COMPLIANCE_AGENT_MCP_TIMEOUT_SECONDS` | Wall-clock bound per scan. A scan that exceeds it returns a timeout error to the *caller* — Python can't forcibly cancel a running thread, so the underlying scan keeps using CPU/memory in the background. Bounds one slow request from hanging a client; a genuinely hostile input needs process-level isolation (out of scope here). | `120` |
| `COMPLIANCE_AGENT_MCP_LOG_LEVEL` | Log level for stderr output, including the audit log. | `INFO` |

`--host` (default `127.0.0.1`, loopback-only) and `--port` (default `8000`)
control what `--http` binds to. The server logs a warning at startup if
`COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS` is unset — it will still start (unlike a
missing token, which is fatal), because stdio-equivalent unrestricted access
is a legitimate choice for a single-operator deployment.

**Audit log**: every tool call and every allowlist rejection emits one
structured line to stderr (tool name, resolved path) — never stdout, which
is reserved for the JSON-RPC stream on stdio transport. There is currently
one shared identity per token (no per-user attribution) — appropriate for a
single-tenant, ops-managed deployment; per-user tokens are out of scope until
an actual multi-tenant use case needs them.

Production example:

```bash
export COMPLIANCE_AGENT_MCP_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS="/srv/projects,/home/ci/repos"
compliance-agent-mcp --http --host 0.0.0.0 --port 8000
```

## Workflows

**Track compliance drift over time** — no baseline store exists, so persist
JSON reports yourself:

```text
scan_project(path="/repo", format="json", output="/history/2026-07-01.json")
# ... later, after changes ...
scan_project(path="/repo", format="json", output="/history/2026-07-19.json")
diff_scans(base_path="/history/2026-07-01.json", target_path="/history/2026-07-19.json")
```

**CI code-scanning integration** — pair `export_sarif` with GitHub's
upload-sarif action (see the
[GitHub Action example](../README.md#cicd-integration) for the equivalent
non-MCP CI step):

```text
export_sarif(path="/repo", output="/repo/compliance-results.sarif")
```

**Fast triage before a full scan** — call `get_summary` first; only reach for
`scan_project` or `recommend_fixes` once you know the project actually has
findings worth digging into.

## Troubleshooting

**"Error: `--http` requires `COMPLIANCE_AGENT_MCP_TOKEN`..."** — the server
refuses to start in HTTP mode without a token; set the env var before
launching (see [Security](#security)).

**"Error: '<path>' is outside the allowed roots..."** — `--http` is running
with `COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS` set and the path you passed doesn't
resolve inside any configured root. Either use a path inside the allowlist,
or have an operator add the location.

**"Error: '<project>' has more than N scannable files..."** — the
`COMPLIANCE_AGENT_MCP_MAX_FILES` guard tripped. Narrow the scan with
`include`/`exclude`, or raise the limit if the project is legitimately that
large.

**"Error: scan of '<path>' did not finish within Ns..."** — the
`COMPLIANCE_AGENT_MCP_TIMEOUT_SECONDS` guard tripped. Narrow the scan or
raise the limit. Note the underlying scan keeps running server-side until it
finishes naturally (see the env var table above).

**Ambiguous / not-found bare project name** — pass the exact absolute path
instead of relying on the common-locations search (see
[Path resolution](#path-resolution)).

**A relative `path` resolves somewhere unexpected** — relative paths resolve
against the MCP *server process's* working directory, never the calling
assistant's or editor's. Always prefer an absolute path.

For install/PATH/Python-version issues unrelated to MCP specifically, see
[docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md).
