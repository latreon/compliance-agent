"""Tests for the MCP server tool functions.

Every tool is called directly as a plain Python function (FastMCP's
``@mcp.tool()`` decorator leaves the underlying callable invocable without a
running server), so these tests exercise the exact same code path an MCP
client would trigger — just without the transport layer.
"""

import json
from pathlib import Path

import pytest

import compliance_agent.mcp_server as mcp_server
from compliance_agent import __version__
from compliance_agent.mcp_server import (
    diff_scans,
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
    assert data["schema_version"] == "1.0"
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
