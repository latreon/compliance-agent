"""Tests for the MCP server tool functions.

Every tool is called directly as a plain Python function (FastMCP's
``@mcp.tool()`` decorator leaves the underlying callable invocable without a
running server), so these tests exercise the exact same code path an MCP
client would trigger — just without the transport layer.
"""

import asyncio
import json
import logging
import sys
import threading
import time
from pathlib import Path

import pytest

import compliance_agent.mcp_server as mcp_server
from compliance_agent import __version__
from compliance_agent.mcp_server import (
    diff_scans,
    export_sarif,
    get_article_info,
    get_summary,
    get_version,
    list_templates,
    recommend_fixes,
    scan_project,
)
from compliance_agent.reporter import pdf_report

REPO_ROOT = Path(__file__).resolve().parents[1]


def _weasyprint_available() -> bool:
    pdf_report._prime_macos_library_path()  # find Homebrew libs on macOS
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


needs_weasyprint = pytest.mark.skipif(
    not _weasyprint_available(),
    reason="weasyprint native libraries (pango/gobject) not available",
)


# ---------- scan_project ---------------------------------------------------


def test_scan_project_real_project_markdown() -> None:
    result = scan_project(str(REPO_ROOT))
    assert "EU AI Act Compliance Report" in result
    assert "Scan Summary" in result


def test_scan_project_json_is_valid_and_diffable() -> None:
    result = scan_project(str(REPO_ROOT), format="json")
    data = json.loads(result)
    assert data["schema_version"] == "1.1"
    assert data["tool_name"] == "ComplianceAgent"
    assert "scan_result" in data
    assert "findings" in data["scan_result"]


def test_scan_project_nonexistent_path() -> None:
    result = scan_project("/no/such/path/anywhere")
    assert result.startswith("Error:")
    assert "does not exist" in result


def test_scan_project_bare_name_resolves_via_common_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_project: Path
) -> None:
    # Simulate ~/Developer containing the "perch" project.
    root = tmp_path / "fake-home-root"
    root.mkdir()
    project = root / "perch"
    project.mkdir()
    (project / "app.py").write_text((clean_project / "utils.py").read_text(encoding="utf-8"))
    monkeypatch.setattr(mcp_server, "_COMMON_PROJECT_ROOTS", (str(root),))

    result = scan_project("perch")
    assert "EU AI Act Compliance Report" in result
    assert str(project.resolve()) in result


def test_scan_project_bare_name_resolves_via_nested_common_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_project: Path
) -> None:
    # Simulate ~/Desktop/Playground/perch — one level deeper than the root.
    root = tmp_path / "fake-home-root"
    nested_parent = root / "Playground"
    nested_parent.mkdir(parents=True)
    project = nested_parent / "perch"
    project.mkdir()
    (project / "app.py").write_text((clean_project / "utils.py").read_text(encoding="utf-8"))
    monkeypatch.setattr(mcp_server, "_COMMON_PROJECT_ROOTS", (str(root),))

    result = scan_project("perch")
    assert "EU AI Act Compliance Report" in result


def test_scan_project_bare_name_ambiguous(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    (root_a / "perch").mkdir(parents=True)
    (root_b / "perch").mkdir(parents=True)
    monkeypatch.setattr(mcp_server, "_COMMON_PROJECT_ROOTS", (str(root_a), str(root_b)))

    result = scan_project("perch")
    assert result.startswith("Error:")
    assert "ambiguous" in result
    assert str((root_a / "perch").resolve()) in result
    assert str((root_b / "perch").resolve()) in result


def test_scan_project_bare_name_ambiguous_filters_matches_outside_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Security regression: an ambiguous bare-name search must not disclose
    # folder names outside COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS in its error
    # message — _search_common_locations probes the whole home-folder tree
    # regardless of the allowlist. Three candidates, only two allowed, so the
    # result stays ambiguous (proving filtering doesn't just resolve down to
    # a single silent match) while the disallowed one must not leak.
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    root_c = tmp_path / "root-c"
    (root_a / "perch").mkdir(parents=True)
    (root_b / "perch").mkdir(parents=True)
    (root_c / "perch").mkdir(parents=True)
    monkeypatch.setattr(
        mcp_server, "_COMMON_PROJECT_ROOTS", (str(root_a), str(root_b), str(root_c))
    )
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, f"{root_a},{root_c}")

    result = scan_project("perch")

    assert result.startswith("Error:")
    assert "ambiguous" in result
    assert str((root_a / "perch").resolve()) in result
    assert str((root_c / "perch").resolve()) in result
    assert str((root_b / "perch").resolve()) not in result


def test_scan_project_bare_name_not_found_anywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "empty-root"
    root.mkdir()
    monkeypatch.setattr(mcp_server, "_COMMON_PROJECT_ROOTS", (str(root),))

    result = scan_project("nonexistent-project-name")
    assert result.startswith("Error:")
    assert "common project locations" in result
    assert "exact absolute path" in result


def test_scan_project_path_is_file_not_directory() -> None:
    result = scan_project(str(REPO_ROOT / "README.md"))
    assert result.startswith("Error:")
    assert "is a file, not a folder" in result


def test_scan_project_invalid_severity() -> None:
    result = scan_project(str(REPO_ROOT), severity="not-a-severity")
    assert result.startswith("Error:")
    assert "invalid severity" in result
    assert "info" in result and "critical" in result


def test_scan_project_clean_project_reports_no_findings(clean_project: Path) -> None:
    result = scan_project(str(clean_project))
    assert "EU AI Act Compliance Report" in result
    assert "Findings:** none" in result


def test_scan_project_invalid_format() -> None:
    result = scan_project(str(REPO_ROOT), format="yaml")
    assert result.startswith("Error:")
    assert "invalid format" in result
    assert "pdf" in result and "html" in result


def test_scan_project_pdf_without_output_is_an_error() -> None:
    result = scan_project(str(REPO_ROOT), format="pdf")
    assert result.startswith("Error:")
    assert "output" in result


def test_scan_project_html_without_output_is_an_error() -> None:
    result = scan_project(str(REPO_ROOT), format="html")
    assert result.startswith("Error:")
    assert "output" in result


def test_scan_project_markdown_with_output_writes_file(clean_project: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "report.md"
    result = scan_project(str(clean_project), output=str(out_file))
    assert result.startswith("Report written to")
    assert out_file.is_file()
    assert "EU AI Act Compliance Report" in out_file.read_text(encoding="utf-8")


def test_scan_project_json_with_output_writes_valid_json(
    clean_project: Path, tmp_path: Path
) -> None:
    out_file = tmp_path / "report.json"
    result = scan_project(str(clean_project), format="json", output=str(out_file))
    assert result.startswith("Report written to")
    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "scan_result" in data


def test_scan_project_html_with_output_writes_dashboard(
    clean_project: Path, tmp_path: Path
) -> None:
    out_file = tmp_path / "dashboard.html"
    result = scan_project(str(clean_project), format="html", output=str(out_file))
    assert result.startswith("HTML dashboard written to")
    assert out_file.is_file()
    assert "<html" in out_file.read_text(encoding="utf-8").lower()


@needs_weasyprint
def test_scan_project_pdf_with_output_writes_pdf(clean_project: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "report.pdf"
    result = scan_project(str(clean_project), format="pdf", output=str(out_file))
    assert result.startswith("PDF report written to")
    assert out_file.is_file()
    assert out_file.read_bytes().startswith(b"%PDF")


def test_scan_project_output_bad_directory_is_an_error(clean_project: Path) -> None:
    # A path whose parent is actually a file (not a directory) can't be created.
    blocker = Path(str(REPO_ROOT / "README.md"))
    result = scan_project(str(clean_project), output=str(blocker / "report.md"))
    assert result.startswith("Error:")


def test_scan_project_exclude_param_actually_excludes(clean_project: Path) -> None:
    (clean_project / "ai_stuff.py").write_text("import openai\nclient = openai.OpenAI()\n")

    full_result = scan_project(str(clean_project))
    assert "Findings:** none" not in full_result

    excluded_result = scan_project(str(clean_project), exclude=["ai_stuff.py"])
    assert "Findings:** none" in excluded_result


def test_scan_project_include_param_restricts_scan(clean_project: Path) -> None:
    (clean_project / "ai_stuff.py").write_text("import openai\nclient = openai.OpenAI()\n")

    full_result = scan_project(str(clean_project))
    assert "Findings:** none" not in full_result

    restricted_result = scan_project(str(clean_project), include=["utils.py"])
    assert "Findings:** none" in restricted_result


def test_scan_project_malformed_compliance_yaml(clean_project: Path) -> None:
    (clean_project / "compliance.yaml").write_text('scan:\n  exclude: ["unterminated\n')
    result = scan_project(str(clean_project))
    assert result.startswith("Error:")
    assert "compliance.yaml" in result


def test_scan_project_run_pipeline_exception_returns_clean_error(
    monkeypatch: pytest.MonkeyPatch, clean_project: Path
) -> None:
    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated pipeline crash")

    monkeypatch.setattr(mcp_server, "run_pipeline", _boom)
    result = scan_project(str(clean_project))
    assert result.startswith("Error:")
    assert "simulated pipeline crash" in result
    assert "Traceback" not in result


# ---------- get_summary ------------------------------------------------------


def test_get_summary_real_project() -> None:
    result = get_summary(str(REPO_ROOT))
    assert "Scan Summary" in result
    assert "Files scanned" in result


def test_get_summary_nonexistent_path() -> None:
    result = get_summary("/no/such/path/anywhere")
    assert result.startswith("Error:")


def test_get_summary_path_is_file() -> None:
    result = get_summary(str(REPO_ROOT / "README.md"))
    assert result.startswith("Error:")
    assert "is a file" in result


def test_get_summary_clean_project_is_meaningful(clean_project: Path) -> None:
    result = get_summary(str(clean_project))
    assert result
    assert "Findings:** none" in result


# ---------- recommend_fixes --------------------------------------------------


def test_recommend_fixes_no_gaps(clean_project: Path) -> None:
    result = recommend_fixes(str(clean_project))
    assert result == "No compliance gaps found — nothing to recommend."


def test_recommend_fixes_with_gaps(agent_project: Path) -> None:
    result = recommend_fixes(str(agent_project))
    assert "## Fix Recommendations" in result
    assert "**Steps:**" in result


def test_recommend_fixes_nonexistent_path() -> None:
    result = recommend_fixes("/no/such/path/anywhere")
    assert result.startswith("Error:")


def test_recommend_fixes_path_is_file() -> None:
    result = recommend_fixes(str(REPO_ROOT / "README.md"))
    assert result.startswith("Error:")


def test_recommend_fixes_output_dir_writes_template_files(
    agent_project: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "fixes"
    result = recommend_fixes(str(agent_project), output_dir=str(out_dir))
    assert "## Fix Recommendations" in result
    assert "Wrote" in result and "file(s) to" in result
    assert (out_dir / "RECOMMENDATIONS.md").is_file()
    written_files = list(out_dir.rglob("*.py"))
    assert written_files, "expected at least one copied template .py file"


def test_recommend_fixes_honors_compliance_yaml_excludes(agent_project: Path) -> None:
    # Regression test: recommend_fixes previously ignored compliance.yaml's
    # exclude list even though scan_project honored it — excluding the only
    # AI-usage file should leave nothing to recommend fixes for.
    ai_file = next(agent_project.glob("*.py"))
    (agent_project / "compliance.yaml").write_text(
        f'version: 1\nscan:\n  exclude: ["{ai_file.name}"]\n'
    )
    result = recommend_fixes(str(agent_project))
    assert result == "No compliance gaps found — nothing to recommend."


def test_article_label_sort_key_orders_numerically() -> None:
    # Regression test: a plain string sort on "Art. N" labels puts
    # "Art. 11"/"Art. 53" before "Art. 5"/"Art. 6" — same bug class already
    # fixed for template-directory names ("artN"), just on gap.article labels.
    labels = ["Art. 11", "Art. 5", "Art. 53", "Art. 6", "Art. 9"]
    assert sorted(labels, key=mcp_server._article_label_sort_key) == [
        "Art. 5",
        "Art. 6",
        "Art. 9",
        "Art. 11",
        "Art. 53",
    ]


def test_get_summary_honors_compliance_yaml_excludes(agent_project: Path) -> None:
    ai_file = next(agent_project.glob("*.py"))
    (agent_project / "compliance.yaml").write_text(
        f'version: 1\nscan:\n  exclude: ["{ai_file.name}"]\n'
    )
    result = get_summary(str(agent_project))
    assert "Findings:** none" in result


# ---------- diff_scans --------------------------------------------------


def test_diff_scans_between_clean_and_agent_project(
    clean_project: Path, agent_project: Path, tmp_path: Path
) -> None:
    base_json = scan_project(str(clean_project), format="json")
    target_json = scan_project(str(agent_project), format="json")

    base_file = tmp_path / "base.json"
    target_file = tmp_path / "target.json"
    base_file.write_text(base_json, encoding="utf-8")
    target_file.write_text(target_json, encoding="utf-8")

    result = diff_scans(str(base_file), str(target_file))
    assert "# Scan comparison" in result
    assert "## Risk tier" in result
    assert "## Findings" in result


def test_diff_scans_json_format_is_valid(
    clean_project: Path, agent_project: Path, tmp_path: Path
) -> None:
    base_json = scan_project(str(clean_project), format="json")
    target_json = scan_project(str(agent_project), format="json")

    base_file = tmp_path / "base.json"
    target_file = tmp_path / "target.json"
    base_file.write_text(base_json, encoding="utf-8")
    target_file.write_text(target_json, encoding="utf-8")

    result = diff_scans(str(base_file), str(target_file), format="json")
    data = json.loads(result)
    assert "tier_direction" in data
    assert "findings_added" in data


def test_diff_scans_invalid_format(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    target = tmp_path / "target.json"
    base.write_text(json.dumps({"scan_result": {}}), encoding="utf-8")
    target.write_text(json.dumps({"scan_result": {}}), encoding="utf-8")
    result = diff_scans(str(base), str(target), format="yaml")
    assert result.startswith("Error:")
    assert "invalid format" in result


def test_diff_scans_with_output_writes_file(
    clean_project: Path, agent_project: Path, tmp_path: Path
) -> None:
    base_json = scan_project(str(clean_project), format="json")
    target_json = scan_project(str(agent_project), format="json")
    base_file = tmp_path / "base.json"
    target_file = tmp_path / "target.json"
    base_file.write_text(base_json, encoding="utf-8")
    target_file.write_text(target_json, encoding="utf-8")

    out_file = tmp_path / "diff.md"
    result = diff_scans(str(base_file), str(target_file), output=str(out_file))
    assert result.startswith("Diff report written to")
    assert out_file.is_file()
    assert "# Scan comparison" in out_file.read_text(encoding="utf-8")


def test_diff_scans_nonexistent_base_file(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    result = diff_scans(str(tmp_path / "missing.json"), str(target))
    assert result.startswith("Error:")
    assert "does not exist" in result


def test_diff_scans_path_is_directory(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    result = diff_scans(str(tmp_path), str(target))
    assert result.startswith("Error:")
    assert "directory" in result


def test_diff_scans_invalid_json(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    target = tmp_path / "target.json"
    base.write_text("not valid json {{{", encoding="utf-8")
    target.write_text("{}", encoding="utf-8")
    result = diff_scans(str(base), str(target))
    assert result.startswith("Error:")


def test_diff_scans_missing_scan_result_key(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    target = tmp_path / "target.json"
    base.write_text(json.dumps({"not_a_report": True}), encoding="utf-8")
    target.write_text(json.dumps({"not_a_report": True}), encoding="utf-8")
    result = diff_scans(str(base), str(target))
    assert result.startswith("Error:")
    assert "scan_result" in result


def test_diff_scans_malformed_scan_result_schema(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    target = tmp_path / "target.json"
    base.write_text(json.dumps({"scan_result": {"totally": "wrong"}}), encoding="utf-8")
    target.write_text(json.dumps({"scan_result": {"totally": "wrong"}}), encoding="utf-8")
    result = diff_scans(str(base), str(target))
    assert result.startswith("Error:")


# ---------- export_sarif -----------------------------------------------------


def test_export_sarif_clean_project_is_valid_empty_sarif(clean_project: Path) -> None:
    result = export_sarif(str(clean_project))

    data = json.loads(result)
    assert data["version"] == "2.1.0"
    assert data["runs"][0]["results"] == []


def test_export_sarif_hiring_project_has_results_and_rules(hiring_project: Path) -> None:
    result = export_sarif(str(hiring_project))

    data = json.loads(result)
    run = data["runs"][0]
    assert run["results"], "hiring_project has Annex III gaps/findings — expected results"
    assert run["tool"]["driver"]["rules"], "expected at least one rule for the results above"


def test_export_sarif_nonexistent_path() -> None:
    result = export_sarif("/no/such/path/anywhere")

    assert result.startswith("Error:")
    assert "does not exist" in result


def test_export_sarif_invalid_severity(clean_project: Path) -> None:
    result = export_sarif(str(clean_project), severity="not-a-severity")

    assert result.startswith("Error:")
    assert "invalid severity" in result


def test_export_sarif_severity_filter_reduces_results(hiring_project: Path) -> None:
    everything = json.loads(export_sarif(str(hiring_project), severity="info"))
    critical_only = json.loads(export_sarif(str(hiring_project), severity="critical"))

    assert len(critical_only["runs"][0]["results"]) <= len(everything["runs"][0]["results"])


def test_export_sarif_with_output_writes_file(clean_project: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "results.sarif"

    result = export_sarif(str(clean_project), output=str(out_file))

    assert result.startswith("SARIF report written to")
    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["version"] == "2.1.0"


def test_export_sarif_output_blocked_by_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
    clean_project: Path,
) -> None:
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(clean_project))
    outside_root = tmp_path_factory.mktemp("sarif-outside-allowlist")
    outside_output = outside_root / "results.sarif"

    result = export_sarif(str(clean_project), output=str(outside_output))

    assert result.startswith("Error:")
    assert "outside the allowed roots" in result
    assert not outside_output.exists()


def test_export_sarif_emits_audit_log(
    caplog: pytest.LogCaptureFixture, clean_project: Path
) -> None:
    with caplog.at_level(logging.INFO, logger=mcp_server._audit_logger.name):
        export_sarif(str(clean_project))

    assert any(
        "event=export_sarif" in record.message and str(clean_project) in record.message
        for record in caplog.records
    )


# ---------- get_article_info --------------------------------------------------


@pytest.mark.parametrize("article", [5, 6, 9, 12, 50])
def test_get_article_info_covered_articles(article: int) -> None:
    result = get_article_info(article)
    assert f"Article {article}" in result
    assert "not currently covered" not in result


def test_get_article_info_uncovered_article() -> None:
    result = get_article_info(999)
    assert "is not currently covered" in result
    assert "Covered articles" in result


@pytest.mark.parametrize("article", [5, 6])
def test_get_article_info_truncates_at_line_boundary(article: int) -> None:
    # rules/prohibited.yaml and rules/annex3.yaml both exceed the 2000-char
    # truncation limit, so this exercises the real truncation path, not just
    # the helper in isolation.
    result = get_article_info(article)
    assert "more line(s) truncated) ..." in result


def test_truncate_at_line_boundary_never_cuts_mid_line() -> None:
    content = "\n".join(f"line {i}: {'x' * 20}" for i in range(200))
    truncated = mcp_server._truncate_at_line_boundary(content, 100)
    body = truncated.split("\n\n... (")[0]
    assert body in content  # every truncated line is a complete original line
    assert "more line(s) truncated" in truncated


def test_truncate_at_line_boundary_returns_unchanged_when_under_limit() -> None:
    content = "short content"
    assert mcp_server._truncate_at_line_boundary(content, 2000) == content


# ---------- list_templates --------------------------------------------------


def test_list_templates_lists_articles() -> None:
    result = list_templates()
    assert "## Available Fix Templates" in result
    assert "art50" in result


def test_list_templates_excludes_pycache() -> None:
    result = list_templates()
    assert "__pycache__" not in result


# ---------- get_version --------------------------------------------------


def test_get_version_matches_package_version() -> None:
    result = get_version()
    assert result == f"ComplianceAgent v{__version__}"


# ---------- StaticBearerAuthProvider (gap 1: no auth on --http) -------------


def test_static_bearer_auth_accepts_matching_token() -> None:
    provider = mcp_server.StaticBearerAuthProvider("s3cret")

    access = asyncio.run(provider.verify_token("s3cret"))

    assert access is not None
    assert access.token == "s3cret"


def test_static_bearer_auth_rejects_wrong_token() -> None:
    provider = mcp_server.StaticBearerAuthProvider("s3cret")

    access = asyncio.run(provider.verify_token("wrong"))

    assert access is None


def test_static_bearer_auth_rejects_empty_token() -> None:
    provider = mcp_server.StaticBearerAuthProvider("s3cret")

    access = asyncio.run(provider.verify_token(""))

    assert access is None


def test_main_refuses_http_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(mcp_server.ENV_AUTH_TOKEN, raising=False)
    monkeypatch.setattr(sys, "argv", ["compliance-agent-mcp", "--http"])

    def _fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("mcp.run must not be reached without an auth token")

    monkeypatch.setattr(mcp_server.mcp, "run", _fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        mcp_server.main()

    assert exc_info.value.code == 1


def test_main_starts_http_with_token_and_wires_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(mcp_server.ENV_AUTH_TOKEN, "s3cret")
    monkeypatch.delenv(mcp_server.ENV_ALLOWED_ROOTS, raising=False)
    monkeypatch.setattr(sys, "argv", ["compliance-agent-mcp", "--http", "--port", "9001"])

    calls: list[dict] = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    mcp_server.main()

    assert calls == [{"transport": "http", "host": "127.0.0.1", "port": 9001}]
    assert isinstance(mcp_server.mcp.auth, mcp_server.StaticBearerAuthProvider)


def test_main_warns_when_http_has_no_allowed_roots(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(mcp_server.ENV_AUTH_TOKEN, "s3cret")
    monkeypatch.delenv(mcp_server.ENV_ALLOWED_ROOTS, raising=False)
    monkeypatch.setattr(sys, "argv", ["compliance-agent-mcp", "--http"])
    monkeypatch.setattr(mcp_server.mcp, "run", lambda **_kwargs: None)

    with caplog.at_level(logging.WARNING, logger=mcp_server.logger.name):
        mcp_server.main()

    assert mcp_server.ENV_ALLOWED_ROOTS in caplog.text


def test_main_refuses_non_loopback_host_without_allowed_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Security regression: a bearer token alone is not enough once the
    # server is actually reachable off-box. Widening --host past loopback
    # without an allowlist must be a hard failure, not just a log warning
    # that's easy to miss in --http deployments.
    monkeypatch.setenv(mcp_server.ENV_AUTH_TOKEN, "s3cret")
    monkeypatch.delenv(mcp_server.ENV_ALLOWED_ROOTS, raising=False)
    monkeypatch.setattr(sys, "argv", ["compliance-agent-mcp", "--http", "--host", "0.0.0.0"])

    def _fail_if_called(**_kwargs: object) -> None:
        raise AssertionError("mcp.run must not be reached without an allowlist")

    monkeypatch.setattr(mcp_server.mcp, "run", _fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        mcp_server.main()

    assert exc_info.value.code == 1


def test_main_allows_non_loopback_host_with_allowed_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(mcp_server.ENV_AUTH_TOKEN, "s3cret")
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["compliance-agent-mcp", "--http", "--host", "0.0.0.0"])
    calls: list[dict] = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    mcp_server.main()

    assert calls == [{"transport": "http", "host": "0.0.0.0", "port": 8000}]


def test_main_defaults_to_stdio_without_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["compliance-agent-mcp"])
    calls: list[str] = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda: calls.append("stdio"))

    mcp_server.main()

    assert calls == ["stdio"]


# ---------- path allowlist (gap 2: no sandboxing) ---------------------------


def test_check_path_allowed_permits_everything_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(mcp_server.ENV_ALLOWED_ROOTS, raising=False)

    assert mcp_server._check_path_allowed(tmp_path) is None


def test_check_path_allowed_blocks_path_outside_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(allowed))

    error = mcp_server._check_path_allowed(outside)

    assert error is not None
    assert "outside the allowed roots" in error
    assert mcp_server.ENV_ALLOWED_ROOTS in error


def test_check_path_allowed_permits_path_inside_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = tmp_path / "allowed"
    nested = allowed / "project"
    nested.mkdir(parents=True)
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(allowed))

    assert mcp_server._check_path_allowed(nested) is None
    assert mcp_server._check_path_allowed(allowed) is None  # the root itself


def test_check_path_allowed_supports_multiple_comma_separated_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, f"{first}, {second}")

    assert mcp_server._check_path_allowed(first) is None
    assert mcp_server._check_path_allowed(second) is None


def test_scan_project_blocked_by_allowlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clean_project: Path
) -> None:
    other_root = tmp_path / "elsewhere"
    other_root.mkdir()
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(other_root))

    result = scan_project(str(clean_project))

    assert result.startswith("Error:")
    assert "outside the allowed roots" in result


def test_scan_project_allowed_when_inside_allowlist(
    monkeypatch: pytest.MonkeyPatch, clean_project: Path
) -> None:
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(clean_project.parent))

    result = scan_project(str(clean_project))

    assert "EU AI Act Compliance Report" in result


def test_scan_project_output_path_blocked_by_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
    clean_project: Path,
) -> None:
    # clean_project *is* the test's tmp_path (see conftest), so the
    # "elsewhere" output must live under a disjoint root minted via
    # tmp_path_factory — nesting it under tmp_path would land inside
    # clean_project itself and defeat the test.
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(clean_project))
    outside_root = tmp_path_factory.mktemp("output-outside-allowlist")
    outside_output = outside_root / "report.json"

    result = scan_project(str(clean_project), format="json", output=str(outside_output))

    assert result.startswith("Error:")
    assert "outside the allowed roots" in result
    assert not outside_output.exists()


def test_recommend_fixes_output_dir_blocked_by_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
    hiring_project: Path,
) -> None:
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(hiring_project))
    outside_root = tmp_path_factory.mktemp("fixes-outside-allowlist")
    outside_dir = outside_root / "fixes"

    result = recommend_fixes(str(hiring_project), output_dir=str(outside_dir))

    assert result.startswith("Error:")
    assert "outside the allowed roots" in result
    assert not outside_dir.exists()


def test_diff_scans_blocked_by_allowlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clean_project: Path
) -> None:
    base = clean_project / "base.json"
    base.write_text(scan_project(str(clean_project), format="json"), encoding="utf-8")
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(tmp_path / "somewhere-else"))

    result = diff_scans(str(base), str(base))

    assert result.startswith("Error:")
    assert "outside the allowed roots" in result


# ---------- resource limits (gap 3: no size/time bound) ---------------------


def test_project_exceeds_file_limit_true_when_over(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"file_{i}.py").write_text("x = 1\n", encoding="utf-8")

    assert mcp_server._project_exceeds_file_limit(tmp_path, limit=3) is True


def test_project_exceeds_file_limit_false_when_under(tmp_path: Path) -> None:
    for i in range(3):
        (tmp_path / f"file_{i}.py").write_text("x = 1\n", encoding="utf-8")

    assert mcp_server._project_exceeds_file_limit(tmp_path, limit=10) is False


def test_project_exceeds_file_limit_ignores_hard_skip_dirs(tmp_path: Path) -> None:
    skip_dir = tmp_path / "node_modules"
    skip_dir.mkdir()
    for i in range(20):
        (skip_dir / f"vendored_{i}.js").write_text("//\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")

    assert mcp_server._project_exceeds_file_limit(tmp_path, limit=10) is False


def test_scan_project_rejects_when_over_max_files(
    monkeypatch: pytest.MonkeyPatch, clean_project: Path
) -> None:
    monkeypatch.setenv(mcp_server.ENV_MAX_FILES, "0")

    result = scan_project(str(clean_project))

    assert result.startswith("Error:")
    assert "scannable files" in result
    assert mcp_server.ENV_MAX_FILES in result


def test_get_summary_respects_custom_max_files_limit(
    monkeypatch: pytest.MonkeyPatch, clean_project: Path
) -> None:
    monkeypatch.setenv(mcp_server.ENV_MAX_FILES, "1000")

    result = get_summary(str(clean_project))

    assert not result.startswith("Error:")


def test_run_pipeline_safely_times_out_and_returns_promptly(
    monkeypatch: pytest.MonkeyPatch, clean_project: Path
) -> None:
    def _slow_pipeline(*_args: object, **_kwargs: object) -> None:
        time.sleep(5)

    monkeypatch.setattr(mcp_server, "run_pipeline", _slow_pipeline)
    monkeypatch.setenv(mcp_server.ENV_TIMEOUT_SECONDS, "0.2")

    start = time.monotonic()
    result, error = mcp_server._run_pipeline_safely(clean_project)
    elapsed = time.monotonic() - start

    assert result is None
    assert error is not None
    assert "did not finish within" in error
    assert mcp_server.ENV_TIMEOUT_SECONDS in error
    assert elapsed < 4  # bounded by the timeout, not by the 5s sleep


def test_run_pipeline_safely_bounds_total_concurrent_scans(
    monkeypatch: pytest.MonkeyPatch, clean_project: Path
) -> None:
    # Reliability regression: a per-call timeout alone only bounds the
    # *caller's* wait, not the abandoned background thread it leaves running
    # — repeatedly timing out could otherwise accumulate unbounded stuck
    # threads. A shared, bounded slot pool must reject a new scan once every
    # slot is held by a still-running (even if already timed-out-on) thread.
    release_event = threading.Event()

    def _blocked_pipeline(*_args: object, **_kwargs: object) -> None:
        release_event.wait()  # released explicitly at the end of the test

    monkeypatch.setattr(mcp_server, "run_pipeline", _blocked_pipeline)
    monkeypatch.setattr(mcp_server, "_SCAN_SLOTS", threading.BoundedSemaphore(1))
    # Short so acquiring the (already-held) slot below fails fast rather than
    # actually waiting for the first call's still-running thread to finish.
    monkeypatch.setenv(mcp_server.ENV_TIMEOUT_SECONDS, "0.3")

    first_thread = threading.Thread(target=mcp_server._run_pipeline_safely, args=(clean_project,))
    first_thread.start()
    time.sleep(0.2)  # let the first call acquire the only slot

    try:
        _, error = mcp_server._run_pipeline_safely(clean_project)
        assert error is not None
        assert "maximum number of concurrent scans" in error
        assert mcp_server.ENV_MAX_CONCURRENT_SCANS in error
    finally:
        release_event.set()
        first_thread.join(timeout=5)


def test_run_pipeline_safely_succeeds_within_timeout(clean_project: Path) -> None:
    result, error = mcp_server._run_pipeline_safely(clean_project)

    assert error is None
    assert result is not None


# ---------- audit logging (gap 4: no invocation trail) ----------------------


def test_scan_project_emits_audit_log(
    caplog: pytest.LogCaptureFixture, clean_project: Path
) -> None:
    with caplog.at_level(logging.INFO, logger=mcp_server._audit_logger.name):
        scan_project(str(clean_project))

    assert any(
        "event=scan_project" in record.message and str(clean_project) in record.message
        for record in caplog.records
    )


def test_blocked_path_emits_audit_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clean_project: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(tmp_path / "somewhere-else"))

    with caplog.at_level(logging.INFO, logger=mcp_server._audit_logger.name):
        scan_project(str(clean_project))

    assert any("event=path_blocked" in record.message for record in caplog.records)


def test_diff_scans_emits_audit_log(caplog: pytest.LogCaptureFixture, clean_project: Path) -> None:
    base = clean_project / "base.json"
    base.write_text(scan_project(str(clean_project), format="json"), encoding="utf-8")

    with caplog.at_level(logging.INFO, logger=mcp_server._audit_logger.name):
        diff_scans(str(base), str(base))

    assert any("event=diff_scans" in record.message for record in caplog.records)


# ---------- host binding (gap 5: --host not configurable) ------------------


def test_host_flag_defaults_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mcp_server.ENV_AUTH_TOKEN, "s3cret")
    monkeypatch.setattr(sys, "argv", ["compliance-agent-mcp", "--http"])
    calls: list[dict] = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    mcp_server.main()

    assert calls[0]["host"] == "127.0.0.1"


def test_host_flag_can_be_overridden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(mcp_server.ENV_AUTH_TOKEN, "s3cret")
    # A non-loopback --host also requires an allowlist (see
    # test_main_refuses_non_loopback_host_without_allowed_roots) — set one so
    # this test isolates "does --host get passed through" from that check.
    monkeypatch.setenv(mcp_server.ENV_ALLOWED_ROOTS, str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["compliance-agent-mcp", "--http", "--host", "0.0.0.0"])
    calls: list[dict] = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    mcp_server.main()

    assert calls[0]["host"] == "0.0.0.0"
