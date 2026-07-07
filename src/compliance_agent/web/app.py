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
"""

import logging
import secrets
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from compliance_agent import DISCLAIMER, __version__
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
        title="ComplianceAgent dashboard",
        version=__version__,
        # The dashboard is the only intended client — no API explorer surface.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
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
        response.headers.setdefault("Content-Security-Policy", _BASE_CSP)
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

    @app.get("/api/meta")
    def meta() -> dict:
        return {
            "tool_name": "ComplianceAgent",
            "tool_version": __version__,
            "project_path": str(project),
            "disclaimer": DISCLAIMER,
        }

    @app.post("/api/scan")
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
            result = run_pipeline(project, with_recommendations=True)
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

    @app.get("/api/history")
    def list_history() -> dict:
        return {"entries": history.list_entries(project)}

    @app.get("/api/history/{entry_id}")
    def get_history(entry_id: str) -> dict:
        envelope = history.load(project, entry_id)
        if envelope is None:
            raise HTTPException(status_code=404, detail="No such scan in history.")
        return envelope

    return app
