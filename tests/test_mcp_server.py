"""Tests for the MCP server tool functions.

Every tool is called directly as a plain Python function (FastMCP's
``@mcp.tool()`` decorator leaves the underlying callable invocable without a
running server), so these tests exercise the exact same code path an MCP
client would trigger — just without the transport layer.
"""

import json
from pathlib import Path

import pytest

from compliance_agent.mcp_server import (
    diff_scans,
    get_article_info,
    get_summary,
    list_templates,
    recommend_fixes,
    scan_project,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


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
    assert "## Scan Comparison" in result
    assert "Tier direction" in result
    assert "Findings:" in result


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
