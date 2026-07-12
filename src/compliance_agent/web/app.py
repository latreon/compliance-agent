"""FastAPI app for the local compliance dashboard (`compliance-agent serve`).

Design constraints:
- The server is bound to ONE project directory, chosen when the CLI launches
  it. The API deliberately accepts no path parameters, so browser-reachable
  code can never scan or read arbitrary directories.
- FastAPI/uvicorn are optional (`pip install 'compliance-agent[web]'`); this
  module must only be imported behind that check.
- Intended for localhost use; nothing is authenticated and nothing should be
  exposed to a network.

Security hardening (beyond localhost-only binding):
- ``TrustedHostMiddleware`` rejects requests whose ``Host`` header doesn't
  match the bound interface, so a DNS-rebinding attack (a remote page whose
  hostname is rebound to 127.0.0.1) can't pass itself off as same-origin and
  read responses that a normal cross-origin request could never see.
- ``POST /api/scan`` requires a custom ``X-Compliance-Dashboard`` header. A
  plain cross-origin ``<form>`` POST can't set custom headers, and a
  cross-origin ``fetch`` with a custom header forces a CORS preflight; since
  no ``CORSMiddleware`` is registered, that preflight fails and the browser
  never sends the real request. This blocks any other tab/website from
  silently triggering scans (blind CSRF / drive-by resource exhaustion).
- Baseline security headers (``X-Content-Type-Options``, ``X-Frame-Options``,
  ``Referrer-Policy``, a restrictive default CSP) are applied to every
  response; the HTML shell additionally gets a nonce-scoped script-src CSP
  for its one inline bootstrap script.

API documentation:
- The read-only REST API is documented via OpenAPI. ``/openapi.json`` is the
  machine-readable spec (for generating clients / integrating other tools) and
  ``/docs`` (Swagger UI) / ``/redoc`` render it for humans. Those two HTML
  explorers load their JS/CSS from a CDN, so they run under a relaxed,
  docs-only CSP; every other route keeps the restrictive baseline. This surface
  is read-only — ``POST /api/scan`` still requires the custom dashboard header,
  which "Try it out" callers must add themselves.
"""

import logging
import re
import secrets
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from compliance_agent import DISCLAIMER, __version__
from compliance_agent.config import ConfigError, load_config
from compliance_agent.models.findings import ScanResult
from compliance_agent.pipeline import run_pipeline
from compliance_agent.reporter.json_report import build_envelope
from compliance_agent.web import history

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"

_STYLES_MARK = "<!--%STYLES%-->"
_SCRIPTS_MARK = "<!--%SCRIPTS%-->"
_DATA_MARK = "<!--%DATA%-->"

# Restrictive-by-default CSP applied to every response; the index route
# overrides it with a same-origin policy that also allows its own assets.
_BASE_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

# Swagger UI / ReDoc load their bundle from jsdelivr and run an inline init
# script, so the docs pages need a looser CSP than the rest of the app. Scoped
# to the docs routes only — every other response keeps _BASE_CSP.
_DOCS_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})
_DOCS_CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "worker-src blob:; "
    "child-src blob:; "
    "frame-ancestors 'none'; "
    "base-uri 'none'"
)

_API_DESCRIPTION = (
    "Read-only REST API behind the ComplianceAgent dashboard. The server is "
    "bound to a single project directory chosen at launch, so no endpoint takes "
    "a filesystem path. `POST /api/scan` additionally requires the "
    "`X-Compliance-Dashboard: 1` header. Download the machine-readable spec at "
    "`/openapi.json` to integrate other tools."
)

# Static assets change on every `compliance-agent` release; force revalidation
# so a browser tab left open across an upgrade can't keep serving a stale
# dashboard.js against a newer server (ETag/Last-Modified still allow a cheap
# 304 instead of a full re-download).
_NO_CACHE = {"Cache-Control": "no-cache"}


def _index_html(nonce: str) -> str:
    """Dashboard shell wired for server mode (assets and data via HTTP).

    The one inline bootstrap script is nonce-scoped so the page can ship a
    strict ``script-src`` CSP without an `'unsafe-inline'` escape hatch.
    """
    template = (_STATIC_DIR / "dashboard.html").read_text(encoding="utf-8")
    return (
        template.replace(_STYLES_MARK, '<link rel="stylesheet" href="/static/dashboard.css">')
        .replace(_DATA_MARK, f'<script nonce="{nonce}">window.__SERVER_MODE__ = true;</script>')
        .replace(
            _SCRIPTS_MARK, f'<script src="/static/dashboard.js" nonce="{nonce}" defer></script>'
        )
    )


def create_app(project_path: Path, *, host: str = "127.0.0.1") -> FastAPI:
    """Build the dashboard app bound to a single project directory.

    ``host`` is the interface the CLI is about to bind uvicorn to; it seeds
    the ``TrustedHostMiddleware`` allow-list so requests arriving with a
    spoofed/rebound ``Host`` header are rejected rather than treated as
    same-origin.
    """
    project = Path(project_path).resolve()
    app = FastAPI(
        title="ComplianceAgent dashboard API",
        version=__version__,
        description=_API_DESCRIPTION,
        # OpenAPI docs are enabled so the dashboard's REST API can be explored
        # (/docs, /redoc) and integrated with other tools (/openapi.json). The
        # server stays localhost-only and the mutating endpoint keeps its
        # custom-header guard, so exposing a read-only explorer is safe.
        openapi_tags=[
            {"name": "meta", "description": "Tool and project metadata."},
            {"name": "scan", "description": "Run a compliance scan of the bound project."},
            {"name": "history", "description": "Browse and compare stored scans."},
            {"name": "export", "description": "Download a scan as an HTML or PDF report."},
        ],
    )

    # Defends against DNS rebinding: without this, a page whose hostname has
    # been rebound to 127.0.0.1 is treated by the browser as same-origin and
    # can read responses a normal cross-origin request could not.
    allowed_hosts = sorted({host, "127.0.0.1", "localhost", "::1"})
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts, www_redirect=False)

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # Swagger UI / ReDoc need CDN assets + an inline init script; every
        # other route keeps the restrictive default.
        csp = _DOCS_CSP if request.url.path in _DOCS_PATHS else _BASE_CSP
        response.headers.setdefault("Content-Security-Policy", csp)
        return response

    @app.get("/", response_class=HTMLResponse)
    def index() -> Response:
        nonce = secrets.token_urlsafe(16)
        response = HTMLResponse(_index_html(nonce))
        # Overrides the default-deny CSP above with one that allows this
        # page's own same-origin script/style/image needs.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "object-src 'none'; "
            "base-uri 'none'; "
            "form-action 'none'; "
            "frame-ancestors 'none'"
        )
        return response

    @app.get("/static/dashboard.css")
    def stylesheet() -> FileResponse:
        # no-cache (not no-store): the browser must revalidate every time
        # rather than reuse a stale copy across a `compliance-agent` upgrade,
        # but a 304 round-trip still avoids re-downloading on every load.
        return FileResponse(_STATIC_DIR / "dashboard.css", media_type="text/css", headers=_NO_CACHE)

    @app.get("/static/dashboard.js")
    def script() -> FileResponse:
        return FileResponse(
            _STATIC_DIR / "dashboard.js", media_type="text/javascript", headers=_NO_CACHE
        )

    @app.get("/api/meta", tags=["meta"], summary="Tool and project metadata")
    def meta() -> dict:
        return {
            "tool_name": "ComplianceAgent",
            "tool_version": __version__,
            "project_path": str(project),
            "disclaimer": DISCLAIMER,
        }

    @app.post("/api/scan", tags=["scan"], summary="Scan the bound project")
    def scan(
        x_compliance_dashboard: str | None = Header(default=None, alias="X-Compliance-Dashboard"),
    ) -> dict:
        # Cross-origin forms can't set custom headers, and a cross-origin
        # fetch that tries to would trigger a CORS preflight this app never
        # grants — so a request lacking this header never legitimately came
        # from the dashboard's own same-origin JS.
        if x_compliance_dashboard != "1":
            raise HTTPException(
                status_code=403,
                detail="This endpoint only accepts requests from the dashboard UI.",
            )
        if not project.is_dir():
            raise HTTPException(status_code=409, detail="Project directory no longer exists.")
        try:
            # The project's compliance.yaml applies to dashboard scans too, so
            # the CLI and the dashboard produce identical results.
            config = load_config(project)
        except ConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            result = run_pipeline(
                project,
                exclude=config.scan.exclude if config else (),
                include=config.scan.include if config else (),
                declared_tier=config.posture.risk_tier if config else None,
                with_recommendations=True,
            )
        except OSError as exc:
            # TOCTOU guard: the directory can vanish/change between the
            # is_dir() check above and the scan itself. Fail with a clean,
            # generic 409 instead of an unhandled 500.
            logger.warning("Scan of %s failed: %s", project, exc)
            raise HTTPException(
                status_code=409,
                detail="Project directory changed or became unreadable during the scan.",
            ) from exc
        envelope = build_envelope(result)
        entry_id = history.save(project, envelope)
        logger.info("Dashboard scan of %s: %d finding(s)", project, len(result.findings))
        # history_id lets the client mark the fresh scan as selected.
        return {**envelope, "history_id": entry_id}

    @app.get("/api/history", tags=["history"], summary="List stored scans (newest first)")
    def list_history() -> dict:
        return {"entries": history.list_entries(project)}

    @app.get("/api/history/{entry_id}", tags=["history"], summary="Load one stored scan")
    def get_history(entry_id: str) -> dict:
        envelope = history.load(project, entry_id)
        if envelope is None:
            raise HTTPException(status_code=404, detail="No such scan in history.")
        return envelope

    def _result_from_entry(entry_id: str) -> ScanResult:
        """Rebuild a ScanResult from a specific history entry (404/409 on error)."""
        envelope = history.load(project, entry_id)
        if envelope is None:
            raise HTTPException(status_code=404, detail="No such scan in history.")
        try:
            return ScanResult.model_validate(envelope["scan_result"])
        except (KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=409,
                detail="This scan was saved by an incompatible version — re-run the scan.",
            ) from exc

    @app.get("/api/diff", tags=["history"], summary="Compare two scans")
    def diff(base: str | None = None, target: str | None = None) -> dict:
        """Compare two scans. Defaults to the latest scan vs the one before it."""
        from compliance_agent.diff import diff_scan_results

        if base is None or target is None:
            entries = history.list_entries(project)
            if len(entries) < 2:
                raise HTTPException(
                    status_code=409,
                    detail="Need at least two scans to compare — run another scan first.",
                )
            # Entries are newest-first: newest is the target, the one before it
            # is the baseline.
            target = target or entries[0]["id"]
            base = base or entries[1]["id"]
        base_result = _result_from_entry(base)
        target_result = _result_from_entry(target)
        result = diff_scan_results(base_result, target_result)
        return {"base_id": base, "target_id": target, **result.model_dump(mode="json")}

    def _load_result_for_export(entry: str | None) -> ScanResult:
        """Rebuild a ScanResult from a history envelope (specific or latest)."""
        if entry is not None:
            envelope = history.load(project, entry)
            if envelope is None:
                raise HTTPException(status_code=404, detail="No such scan in history.")
        else:
            entries = history.list_entries(project)
            if not entries:
                raise HTTPException(
                    status_code=404, detail="No scan to export yet — run a scan first."
                )
            envelope = history.load(project, entries[0]["id"])
            if envelope is None:
                raise HTTPException(status_code=404, detail="No scan to export yet.")
        try:
            return ScanResult.model_validate(envelope["scan_result"])
        except (KeyError, ValueError) as exc:
            # A history file from an incompatible (older/newer) release.
            raise HTTPException(
                status_code=409,
                detail="This scan was saved by an incompatible version — re-run the scan.",
            ) from exc

    def _export_filename(extension: str) -> str:
        # Header values must stay ASCII and quote-free; the project directory
        # name is user-controlled, so sanitize rather than trust it.
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", project.name) or "project"
        prefix = "compliance-dashboard" if extension == "html" else "compliance-report"
        return f"{prefix}-{stem}.{extension}"

    @app.get("/api/export/html", tags=["export"], summary="Export a scan as an HTML report")
    def export_html(entry: str | None = None) -> Response:
        from compliance_agent.reporter.html_report import render_html

        result = _load_result_for_export(entry)
        return Response(
            content=render_html(result),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{_export_filename("html")}"'},
        )

    @app.get("/api/export/pdf", tags=["export"], summary="Export a scan as a PDF report")
    def export_pdf(entry: str | None = None) -> Response:
        from compliance_agent.reporter.pdf_report import PDFReporter

        result = _load_result_for_export(entry)
        try:
            pdf = PDFReporter().render_pdf_bytes(result)
        except RuntimeError as exc:
            # WeasyPrint's native libraries are missing; the message explains
            # exactly what to install.
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{_export_filename("pdf")}"'},
        )

    return app
