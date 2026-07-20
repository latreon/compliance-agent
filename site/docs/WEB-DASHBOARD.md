# Web Dashboard — Full Reference

`compliance-agent serve` runs a local, single-project web dashboard for
interactively browsing scan results, comparing scans over time, and
exporting reports. This doc covers usage and mechanics. For the dashboard's
threat model (why it has no authentication, what defends it anyway), see
[SECURITY.md](../SECURITY.md) — that write-up isn't duplicated here.

## Starting it

```bash
compliance-agent serve                  # serves "." on 127.0.0.1:8420
compliance-agent serve ./my-project     # serve a specific project
compliance-agent serve --port 9000      # different port
compliance-agent serve --no-browser     # don't auto-open a browser tab
compliance-agent serve --verbose        # uvicorn access logs
```

| Flag | Default | Notes |
|---|---|---|
| `path` (positional) | `.` | Project directory to serve — bound once at startup; there's no way to switch projects without restarting. |
| `--host` | `127.0.0.1` | Keep the localhost default — the dashboard has **no authentication**. Widening this exposes an unauthenticated compliance-scan endpoint to the network. |
| `--port` / `-p` | `8420` | Before serving, the CLI proactively tries to bind this host:port with a throwaway socket, so "port already in use" surfaces as a clear error instead of a late uvicorn crash after "Serving..." has already printed. |
| `--no-browser` | off | By default, if stdout is a TTY, a browser tab opens automatically ~0.8s after the server starts. |
| `--verbose` / `-v` | off | Raises uvicorn's log level from `warning` to `info`. |

## What it serves

| Method & path | Purpose |
|---|---|
| `GET /` | The dashboard UI (static HTML/CSS/JS shell). |
| `GET /api/meta` | Tool name/version, bound project path, disclaimer text. |
| `POST /api/scan` | Runs a fresh scan of the bound project and saves it to history. Requires an `X-Compliance-Dashboard: 1` header (see [CSRF guard](#csrf-guard) below). |
| `GET /api/history` | Lists stored scans for this project, newest first (summaries only). |
| `GET /api/history/{entry_id}` | Loads one full stored scan. |
| `GET /api/diff?base=...&target=...` | Compares two stored scans — see [Comparing scans](#comparing-scans). |
| `GET /api/export/html` | Downloads a scan as a standalone HTML report (`?entry=` to pick one; defaults to latest). |
| `GET /api/export/pdf` | Downloads a scan as a PDF report (same `?entry=` param; `501` if WeasyPrint's native libraries aren't installed). |
| `GET /docs`, `/redoc`, `/openapi.json` | FastAPI's interactive API docs — enabled (see [why below](#why-openapi-docs-stay-enabled)). |

## Scan history

Each scan you run through the dashboard is saved automatically:

- **Location**: `$XDG_DATA_HOME/compliance-agent/history/<project-key>/<entry-id>.json`
  (falls back to `~/.local/share` if `XDG_DATA_HOME` isn't set).
- **Project key**: the first 16 hex characters of a SHA-256 hash of the
  project's resolved absolute path — so re-scanning the same directory
  always lands in the same history folder, regardless of how the path was
  typed (relative, `~`, symlink, etc.).
- **Entry id**: a timestamp (`YYYYMMDDThhmmssffffff`, truncated). Two scans
  finishing in the same millisecond don't collide — the id is claimed
  atomically, and a collision just bumps the timestamp by 1ms and retries.
- **Format**: one plain JSON file per scan (the same envelope shape
  `scan_project(format="json")` produces), written with restrictive `0o600`
  file permissions — not a database.
- **Retention**: the most recent **50** scans per project are kept; older
  ones are pruned automatically after each new scan.
- Saving history is best-effort: a read-only home directory or similar
  filesystem issue logs a warning but never fails the scan itself.

There's no way to browse history across *different* projects from one
dashboard instance — it's scoped to whatever directory you launched
`serve` against.

## Comparing scans

`GET /api/diff` compares two stored scans by id. If you omit `base` and/or
`target`, it defaults to comparing the two most recent scans — "previous
scan" specifically means the second-most-recent entry in this project's
history, compared against the most recent one. You need at least two saved
scans for the default comparison to work; with fewer, the endpoint returns
an error asking you to run another scan first.

The actual diff (risk-tier movement, gaps resolved/new/changed, findings
added/removed) is computed by the same `diff_scan_results` logic the CLI's
`compliance-agent diff` command and the `diff_scans` MCP tool use — the
dashboard's compare view, the CLI, and MCP all produce the same comparison,
just through different entry points.

## CSRF guard

`POST /api/scan` requires a custom `X-Compliance-Dashboard: 1` header on
every request. There's no CORS policy configured, so an ordinary
cross-origin `<form>` submit or `fetch()` from another site open in your
browser can't trigger a scan — it has no way to attach that header. This
also applies to requests made through the `/docs` Swagger UI's "Try it out"
button; you still have to supply the header there.

## Security headers (brief)

The dashboard sets `X-Content-Type-Options: nosniff`, `X-Frame-Options:
DENY`, `Referrer-Policy: no-referrer`, and a restrictive
`Content-Security-Policy` on every response, plus `TrustedHostMiddleware` to
reject requests with a spoofed `Host` header (DNS-rebinding defense). Full
threat-model rationale lives in [SECURITY.md](../SECURITY.md).

## Why OpenAPI docs stay enabled

`/docs`, `/redoc`, and `/openapi.json` are left on rather than disabled, for
two reasons specific to this dashboard: the API is read-only except for
`POST /api/scan`, which still enforces the CSRF header guard above even when
triggered from Swagger UI — and no endpoint accepts an arbitrary filesystem
path (the server is permanently bound to the one project directory it was
launched with), so exposing the schema can't be used to make the server
touch a different path. Because Swagger UI/ReDoc load their JS/CSS from
`cdn.jsdelivr.net`, those two routes (and only those two) get a relaxed CSP
scoped specifically to that CDN; every other route keeps the restrictive
default policy.
