"""Tests for the local web dashboard (FastAPI app + scan history)."""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi", reason="web extra not installed")

from fastapi.testclient import TestClient  # noqa: E402

from compliance_agent import __version__  # noqa: E402
from compliance_agent.web import history  # noqa: E402
from compliance_agent.web.app import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep scan history out of the real user data dir."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))


# The dashboard's own fetch calls attach this header; it's required on
# POST /api/scan specifically so a cross-origin page (another open tab)
# can never trigger a scan blindly — see app.py's module docstring.
_DASHBOARD_HEADERS = {"X-Compliance-Dashboard": "1"}


@pytest.fixture
def client(openai_project: Path) -> TestClient:
    # TestClient's default base_url ("http://testserver") would otherwise be
    # rejected by TrustedHostMiddleware, same as any other untrusted Host.
    return TestClient(create_app(openai_project), base_url="http://127.0.0.1")


def test_index_serves_dashboard(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "window.__SERVER_MODE__ = true" in resp.text
    assert "window.__SCAN_DATA__" not in resp.text  # data comes from the API


def test_static_assets_served(client: TestClient) -> None:
    css = client.get("/static/dashboard.css")
    js = client.get("/static/dashboard.js")
    assert css.status_code == 200 and "text/css" in css.headers["content-type"]
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    # Force revalidation so a tab left open across a version upgrade can't
    # keep serving stale JS/CSS against a newer server.
    assert css.headers["cache-control"] == "no-cache"
    assert js.headers["cache-control"] == "no-cache"


def test_api_docs_disabled(client: TestClient) -> None:
    # Localhost-only tool: no API explorer surface.
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_meta_endpoint(client: TestClient, openai_project: Path) -> None:
    meta = client.get("/api/meta").json()
    assert meta["tool_version"] == __version__
    assert meta["project_path"] == str(openai_project.resolve())
    assert "legal advice" in meta["disclaimer"]


def test_security_headers_present_on_every_response(client: TestClient) -> None:
    # Baseline hardening headers must be on API, HTML, and static responses.
    for resp in (client.get("/api/meta"), client.get("/"), client.get("/static/dashboard.css")):
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert resp.headers["referrer-policy"] == "no-referrer"
        assert "Content-Security-Policy" in resp.headers


def test_index_csp_is_nonce_scoped_and_same_origin(client: TestClient) -> None:
    resp = client.get("/")
    csp = resp.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "'nonce-" in csp
    assert "frame-ancestors 'none'" in csp
    # The nonce advertised in the CSP must match what's on the inline script.
    nonce = csp.split("'nonce-", 1)[1].split("'", 1)[0]
    assert f'nonce="{nonce}"' in resp.text


def test_untrusted_host_header_rejected(client: TestClient) -> None:
    # Defends against DNS rebinding: a request whose Host doesn't match the
    # bound interface must never be treated as same-origin.
    resp = client.get("/api/meta", headers={"host": "evil.example.com"})
    assert resp.status_code == 400


def test_scan_endpoint_rejects_requests_without_dashboard_header(client: TestClient) -> None:
    # Blocks blind cross-origin/CSRF triggering of a scan from another tab.
    assert client.post("/api/scan").status_code == 403
    assert client.post("/api/scan", headers={"X-Compliance-Dashboard": "0"}).status_code == 403


def test_scan_endpoint_returns_envelope_and_saves_history(client: TestClient) -> None:
    payload = client.post("/api/scan", headers=_DASHBOARD_HEADERS).json()
    assert payload["schema_version"] == "1.0"
    assert payload["scan_result"]["findings"]
    assert payload["history_id"]

    entries = client.get("/api/history").json()["entries"]
    assert len(entries) == 1
    assert entries[0]["id"] == payload["history_id"]
    assert entries[0]["risk_tier"] == payload["scan_result"]["risk_tier"]


def test_history_entry_roundtrip(client: TestClient) -> None:
    created = client.post("/api/scan", headers=_DASHBOARD_HEADERS).json()
    fetched = client.get(f"/api/history/{created['history_id']}").json()
    assert fetched["scan_result"]["files_scanned"] == created["scan_result"]["files_scanned"]


def test_history_rejects_bad_ids(client: TestClient) -> None:
    # Traversal-shaped and malformed ids must 404, never touch the filesystem.
    assert client.get("/api/history/nope").status_code == 404
    assert client.get("/api/history/..%2f..%2fetc%2fpasswd").status_code == 404


def test_history_prunes_to_cap(openai_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(history, "MAX_ENTRIES", 3)
    for _ in range(5):
        history.save(openai_project, {"scan_result": {"findings": [], "gaps": []}})
    assert len(history.list_entries(openai_project)) <= 3


def test_history_save_survives_readonly_dir(
    openai_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A failing data dir must never break the scan itself.
    monkeypatch.setattr(history, "_data_dir", lambda: Path("/dev/null/nope"))
    assert history.save(openai_project, {"scan_result": {}}) is None


def test_history_save_never_collides_or_corrupts_under_race(openai_project: Path) -> None:
    # Two saves landing in the same millisecond must not overwrite/interleave
    # each other's file — each gets a distinct, fully-formed entry.
    ids = [
        history.save(openai_project, {"scan_result": {"findings": [], "gaps": [], "n": i}})
        for i in range(20)
    ]
    assert None not in ids
    assert len(set(ids)) == len(ids)  # every id unique, no silent overwrite
    for entry_id in ids:
        envelope = history.load(openai_project, entry_id)
        assert envelope is not None  # never partially-written/corrupted


def test_history_save_refuses_symlinked_project_dir(openai_project: Path, tmp_path: Path) -> None:
    # A symlink planted at the exact project-key path must never be followed.
    target_dir = history._project_dir(openai_project)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    escape_target = tmp_path / "outside"
    escape_target.mkdir()
    target_dir.symlink_to(escape_target)

    assert history.save(openai_project, {"scan_result": {}}) is None
    assert list(escape_target.iterdir()) == []


# ---------- export endpoints ---------------------------------------------


def test_export_with_no_history_is_404(client: TestClient) -> None:
    resp = client.get("/api/export/html")
    assert resp.status_code == 404
    assert "run a scan first" in resp.json()["detail"].lower()


def test_export_html_latest_scan(client: TestClient) -> None:
    client.post("/api/scan", headers=_DASHBOARD_HEADERS)
    resp = client.get("/api/export/html")
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("attachment;")
    assert ".html" in resp.headers["content-disposition"]
    # The export is the self-contained dashboard with the data inlined.
    assert "window.__SCAN_DATA__" in resp.text
    assert "window.__SERVER_MODE__ = true" not in resp.text


def test_export_html_specific_entry(client: TestClient) -> None:
    created = client.post("/api/scan", headers=_DASHBOARD_HEADERS).json()
    resp = client.get(f"/api/export/html?entry={created['history_id']}")
    assert resp.status_code == 200
    assert str(created["scan_result"]["files_scanned"]) in resp.text


def test_export_rejects_unknown_entry(client: TestClient) -> None:
    client.post("/api/scan", headers=_DASHBOARD_HEADERS)
    assert client.get("/api/export/html?entry=nope").status_code == 404
    assert client.get("/api/export/html?entry=..%2f..%2fetc").status_code == 404


def test_export_pdf_latest_scan(client: TestClient) -> None:
    client.post("/api/scan", headers=_DASHBOARD_HEADERS)
    resp = client.get("/api/export/pdf")
    if resp.status_code == 501:
        pytest.skip("WeasyPrint native libraries not installed")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    assert ".pdf" in resp.headers["content-disposition"]


def test_export_ui_present_in_dashboard_shell(client: TestClient) -> None:
    page = client.get("/").text
    assert 'id="btn-export-html"' in page
    assert 'id="btn-export-pdf"' in page


def test_scan_endpoint_surfaces_broken_config(openai_project: Path) -> None:
    (openai_project / "compliance.yaml").write_text("scan: [unclosed")
    broken_client = TestClient(create_app(openai_project), base_url="http://127.0.0.1")
    resp = broken_client.post("/api/scan", headers=_DASHBOARD_HEADERS)
    assert resp.status_code == 422
    assert "yaml" in resp.json()["detail"].lower()


def test_scan_endpoint_applies_config_declared_tier(openai_project: Path) -> None:
    (openai_project / "compliance.yaml").write_text("posture:\n  risk_tier: high\n")
    config_client = TestClient(create_app(openai_project), base_url="http://127.0.0.1")
    payload = config_client.post("/api/scan", headers=_DASHBOARD_HEADERS).json()
    assert payload["scan_result"]["risk_tier"] == "high"
