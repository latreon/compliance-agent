"""Tests for the SARIF 2.1.0 reporter (GitHub code scanning integration)."""

import json
from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from compliance_agent import __version__
from compliance_agent.cli import app
from compliance_agent.models.findings import (
    ComplianceGap,
    Finding,
    ScanResult,
    Severity,
)
from compliance_agent.pipeline import run_pipeline
from compliance_agent.reporter.sarif_report import build_sarif, render_sarif

runner = CliRunner()


def _finding(**overrides) -> Finding:
    base = dict(
        id="providers:provider:openai:app.py:3",
        file_path="app.py",
        line_number=3,
        detector="providers",
        severity=Severity.INFO,
        category="provider:openai",
        message="OpenAI API usage detected",
        description="The project calls the OpenAI API.",
        article="Art. 50",
        suggestion="Disclose AI interaction to users.",
    )
    base.update(overrides)
    return Finding(**base)


def _gap(**overrides) -> ComplianceGap:
    base = dict(
        id="gap:art50:ai-disclosure",
        title="No AI disclosure",
        article="Art. 50",
        article_title="Transparency obligations",
        severity=Severity.HIGH,
        description="Users are not told they interact with an AI system.",
        recommendation="Add a visible AI notice.",
    )
    base.update(overrides)
    return ComplianceGap(**base)


def _result(tmp_path: Path, **overrides) -> ScanResult:
    base = dict(
        project_path=str(tmp_path),
        findings=[_finding()],
        gaps=[_gap()],
        scan_time=datetime(2026, 7, 12, 12, 0, 0),
        files_scanned=1,
    )
    base.update(overrides)
    return ScanResult(**base)


def test_sarif_envelope_shape(tmp_path: Path) -> None:
    log = build_sarif(_result(tmp_path))
    assert log["version"] == "2.1.0"
    assert log["$schema"].endswith("sarif-2.1.0.json")
    driver = log["runs"][0]["tool"]["driver"]
    assert driver["name"] == "ComplianceAgent"
    assert driver["version"] == __version__
    assert "not legal advice" in log["runs"][0]["properties"]["disclaimer"].lower()


def test_finding_becomes_result_with_location(tmp_path: Path) -> None:
    log = build_sarif(_result(tmp_path, gaps=[]))
    (result,) = log["runs"][0]["results"]
    assert result["level"] == "note"  # info -> note
    location = result["locations"][0]["physicalLocation"]
    assert location["artifactLocation"]["uri"] == "app.py"
    assert location["region"]["startLine"] == 3
    assert result["partialFingerprints"]["complianceAgentId"]


def test_rule_ids_are_per_class_not_per_file(tmp_path: Path) -> None:
    # Two findings of the same category in different files share ONE rule.
    findings = [
        _finding(file_path="a.py", id="providers:provider:openai:a.py:1"),
        _finding(file_path="b.py", id="providers:provider:openai:b.py:9", line_number=9),
    ]
    log = build_sarif(_result(tmp_path, findings=findings, gaps=[]))
    run = log["runs"][0]
    assert len(run["tool"]["driver"]["rules"]) == 1
    assert len(run["results"]) == 2
    assert {r["ruleId"] for r in run["results"]} == {"finding.providers.provider.openai"}


def test_severity_levels_and_security_severity(tmp_path: Path) -> None:
    result = _result(
        tmp_path,
        findings=[_finding(severity=Severity.WARNING)],
        gaps=[_gap(severity=Severity.CRITICAL)],
    )
    log = build_sarif(result)
    run = log["runs"][0]
    levels = {r["ruleId"]: r["level"] for r in run["results"]}
    assert levels["finding.providers.provider.openai"] == "warning"
    assert levels["gap.art50.ai-disclosure"] == "error"  # critical -> error
    scores = {
        rule["id"]: rule["properties"]["security-severity"]
        for rule in run["tool"]["driver"]["rules"]
    }
    assert scores["gap.art50.ai-disclosure"] == "9.5"
    assert scores["finding.providers.provider.openai"] == "5.0"


def test_gap_is_anchored_to_a_root_file(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    log = build_sarif(_result(tmp_path, findings=[]))
    (result,) = log["runs"][0]["results"]
    uri = result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri == "pyproject.toml"
    assert "Fix:" in result["message"]["text"]


def test_gap_without_anchor_file_falls_back_to_a_finding_path(tmp_path: Path) -> None:
    log = build_sarif(_result(tmp_path))  # no root manifest in tmp_path
    gap_result = log["runs"][0]["results"][1]
    uri = gap_result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri == "app.py"


def test_scan_errors_flip_execution_successful(tmp_path: Path) -> None:
    log = build_sarif(_result(tmp_path, scan_errors=["bad.py: boom"]))
    invocation = log["runs"][0]["invocations"][0]
    assert invocation["executionSuccessful"] is False
    assert "bad.py" in invocation["toolExecutionNotifications"][0]["message"]["text"]

    clean = build_sarif(_result(tmp_path))
    assert clean["runs"][0]["invocations"][0]["executionSuccessful"] is True


def test_render_sarif_is_valid_json(tmp_path: Path) -> None:
    parsed = json.loads(render_sarif(_result(tmp_path)))
    assert parsed["runs"][0]["results"]


def test_real_pipeline_produces_sarif_results(openai_project: Path) -> None:
    result = run_pipeline(openai_project)
    log = build_sarif(result)
    run = log["runs"][0]
    assert run["results"], "the sample project must yield SARIF results"
    # Every result must reference a rule that exists at the given index.
    rules = run["tool"]["driver"]["rules"]
    for res in run["results"]:
        assert rules[res["ruleIndex"]]["id"] == res["ruleId"]


def test_cli_scan_format_sarif_stdout(openai_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(openai_project), "--format", "sarif"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["version"] == "2.1.0"


def test_cli_scan_format_sarif_to_file(openai_project: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "out" / "results.sarif"
    result = runner.invoke(
        app, ["scan", str(openai_project), "--format", "sarif", "--output", str(out_file)]
    )
    assert result.exit_code == 0
    parsed = json.loads(out_file.read_text(encoding="utf-8"))
    assert parsed["runs"][0]["tool"]["driver"]["name"] == "ComplianceAgent"


def test_cli_scan_format_json_to_file(openai_project: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "report.json"
    result = runner.invoke(
        app, ["scan", str(openai_project), "--format", "json", "--output", str(out_file)]
    )
    assert result.exit_code == 0
    parsed = json.loads(out_file.read_text(encoding="utf-8"))
    assert parsed["schema_version"] == "1.0"
