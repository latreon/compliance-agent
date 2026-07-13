"""Tests for the Typer CLI."""

import json
from pathlib import Path

from typer.testing import CliRunner

from compliance_agent import __version__
from compliance_agent.cli import app

runner = CliRunner()


def test_version_command_shows_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_flag_shows_version() -> None:
    for flag in ("--version", "-V"):
        result = runner.invoke(app, [flag])
        assert result.exit_code == 0, flag
        assert __version__ in result.output


def test_bare_invocation_shows_version_and_commands() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert __version__ in result.output
    # the command list should be shown
    assert "scan" in result.output
    assert "upgrade" in result.output


def test_scan_nonexistent_path_exits_with_error() -> None:
    result = runner.invoke(app, ["scan", "/does/not/exist"])
    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_scan_invalid_format_exits_with_error(clean_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(clean_project), "--format", "xml"])
    assert result.exit_code == 2
    assert "invalid format" in result.output


def test_scan_clean_project_succeeds(clean_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(clean_project)])
    assert result.exit_code == 0
    assert "Compliance Report" in result.output


def test_scan_json_output_is_valid_json(openai_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(openai_project), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "1.0"
    assert payload["tool_version"] == __version__
    scan = payload["scan_result"]
    assert scan["files_scanned"] == 2
    assert scan["risk_tier"] is not None
    assert isinstance(scan["findings"], list)
    # The "not legal advice" disclaimer must ride every output surface.
    assert "legal advice" in payload["disclaimer"]


def test_scan_json_envelope_locks_the_contract(openai_project: Path) -> None:
    # CI consumers parse this envelope. Lock the top-level and nested key sets so
    # a rename/drop can't ship silently while schema_version stays "1.0".
    result = runner.invoke(app, ["scan", str(openai_project), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload) == {
        "schema_version",
        "tool_name",
        "tool_version",
        "disclaimer",
        "scan_result",
    }
    scan = payload["scan_result"]
    assert set(scan) == {
        "project_path",
        "findings",
        "scan_time",
        "files_scanned",
        "risk_tier",
        "risk_assessment",
        "gaps",
        "recommendations",
        "frameworks_detected",
        "coverage",
        "scan_errors",
    }
    assert scan["findings"], "expected at least one finding for the sample project"
    assert set(scan["findings"][0]) == {
        "id",
        "file_path",
        "line_number",
        "detector",
        "severity",
        "category",
        "message",
        "description",
        "article",
        "suggestion",
        "occurrences",
    }
    assert set(scan["risk_assessment"]) == {
        "tier",
        "confidence",
        "reasoning",
        "matched_categories",
    }


def test_scan_fail_on_high_triggers_on_gap_without_high_findings(agent_project: Path) -> None:
    # Regression: detectors only emit INFO/WARNING findings, so a HIGH gap
    # (e.g. Art. 15 missing error handling) must still trip --fail-on high.
    # Previously the gate inspected findings only and exited 0 here.
    json_result = runner.invoke(app, ["scan", str(agent_project), "--format", "json"])
    scan = json.loads(json_result.output)["scan_result"]
    assert not any(f["severity"] in ("high", "critical") for f in scan["findings"])
    assert any(g["severity"] in ("high", "critical") for g in scan["gaps"])

    result = runner.invoke(app, ["scan", str(agent_project), "--fail-on", "high"])
    assert result.exit_code == 1


def test_scan_terminal_output_includes_disclaimer(clean_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(clean_project)])
    assert result.exit_code == 0
    assert "not legal advice" in result.output.lower()


def test_scan_ci_output_includes_disclaimer(openai_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(openai_project), "--ci"])
    assert result.exit_code == 0
    assert "not legal advice" in result.output.lower()


def test_scan_fail_on_threshold_triggers_exit_code_1(agent_project: Path) -> None:
    # agent_project has WARNING findings (tool calls, missing logging)
    result = runner.invoke(app, ["scan", str(agent_project), "--fail-on", "warning"])
    assert result.exit_code == 1


def test_scan_fail_on_not_triggered_below_threshold(clean_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(clean_project), "--fail-on", "critical"])
    assert result.exit_code == 0


def test_should_fail_when_scan_incomplete() -> None:
    # A detector crash (scan_errors non-empty) means coverage is unknown, so the
    # CI gate must fail regardless of threshold — a green build would otherwise
    # falsely assert a clean scan of the whole project.
    from datetime import datetime

    from compliance_agent.cli import _should_fail
    from compliance_agent.models.findings import ScanResult, Severity

    incomplete = ScanResult(
        project_path="/fake",
        findings=[],
        scan_time=datetime.now(),
        files_scanned=1,
        scan_errors=["providers failed on app.py: boom"],
    )
    assert _should_fail(incomplete, Severity.CRITICAL) is True
    assert (
        _should_fail(incomplete.model_copy(update={"scan_errors": []}), Severity.CRITICAL) is False
    )


def test_scan_fail_on_scan_error_explains_why_in_output(monkeypatch, clean_project: Path) -> None:
    # An exit code 1 caused by an incomplete scan (a detector crash) looks
    # identical to a severity-threshold failure from the exit code alone — the
    # user must be told WHY, not just left with a red build.
    from datetime import datetime

    import compliance_agent.cli as cli_module
    from compliance_agent.models.findings import RiskTier, ScanResult

    def fake_run_pipeline(*_args, **_kwargs):
        return ScanResult(
            project_path=str(clean_project),
            findings=[],
            scan_time=datetime.now(),
            files_scanned=1,
            risk_tier=RiskTier.MINIMAL,
            scan_errors=["providers failed on app.py: boom"],
        )

    monkeypatch.setattr(cli_module, "run_pipeline", fake_run_pipeline)
    result = runner.invoke(app, ["scan", str(clean_project), "--fail-on", "critical", "--quiet"])
    assert result.exit_code == 1
    assert "could not be fully analyzed" in result.output
    assert "regardless of the severity" in result.output


def test_scan_fail_on_invalid_severity_exits_with_error(clean_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(clean_project), "--fail-on", "banana"])
    assert result.exit_code == 2
    assert "invalid severity" in result.output


def test_scan_exclude_flag_skips_directory(tmp_path: Path) -> None:
    vendored = tmp_path / "vendored"
    vendored.mkdir()
    (vendored / "lib.py").write_text("import openai\n")
    (tmp_path / "app.py").write_text("import openai\n")

    result = runner.invoke(
        app, ["scan", str(tmp_path), "--exclude", "vendored/*", "--format", "json"]
    )
    assert result.exit_code == 0
    scan = json.loads(result.output)["scan_result"]
    assert scan["files_scanned"] == 1
    assert all("vendored" not in f["file_path"] for f in scan["findings"])


def test_scan_severity_filter_hides_lower_findings(agent_project: Path) -> None:
    result = runner.invoke(
        app, ["scan", str(agent_project), "--severity", "warning", "--format", "json"]
    )
    assert result.exit_code == 0
    scan = json.loads(result.output)["scan_result"]
    assert scan["findings"], "expected warning-or-above findings"
    assert all(f["severity"] in ("warning", "high", "critical") for f in scan["findings"])


def test_scan_quiet_outputs_summary_only(openai_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(openai_project), "--quiet"])
    assert result.exit_code == 0
    assert "Scan Summary" in result.output
    assert "## Findings" not in result.output


def test_scan_no_color_flag_runs(clean_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(clean_project), "--no-color"])
    assert result.exit_code == 0


def test_scan_file_path_errors_instead_of_reporting_compliant(clean_project: Path) -> None:
    # Regression: pointing at a file (not a folder) must error, not silently
    # report "compliant".
    file_path = clean_project / "utils.py"
    result = runner.invoke(app, ["scan", str(file_path)])
    assert result.exit_code == 2
    assert "is a file" in result.output


def test_scan_markdown_format_emits_raw_markdown_when_piped(openai_project: Path) -> None:
    # Regression: `--format markdown` piped to a file used to emit the Rich
    # terminal report (box-drawing art). It must now be real Markdown.
    result = runner.invoke(app, ["scan", str(openai_project), "--format", "markdown"])
    assert result.exit_code == 0
    assert result.output.startswith("# EU AI Act Compliance Report")
    assert "## Findings" in result.output
    assert "╭" not in result.output  # no ╭ box-drawing character


def test_scan_markdown_format_honors_output_flag(openai_project: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "report.md"
    result = runner.invoke(
        app, ["scan", str(openai_project), "--format", "markdown", "--output", str(out_file)]
    )
    assert result.exit_code == 0
    assert out_file.read_text(encoding="utf-8").startswith("# EU AI Act Compliance Report")
    assert "Report saved to" in result.output


def test_scan_markdown_severity_filter_message_not_misleading(agent_project: Path) -> None:
    # With --severity above every finding, the (piped) Markdown must not claim
    # "No AI usage patterns detected" when AI *was* detected.
    result = runner.invoke(
        app, ["scan", str(agent_project), "--format", "markdown", "--severity", "critical"]
    )
    assert result.exit_code == 0
    assert "No findings at or above the selected severity." in result.output
    assert "No AI usage patterns detected." not in result.output


def test_scan_verbose_logs_scan_summary(openai_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(openai_project), "--verbose"])
    assert result.exit_code == 0


def test_report_markdown_writes_file(openai_project: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "compliance.md"
    result = runner.invoke(
        app, ["report", str(openai_project), "--format", "markdown", "--output", str(out_file)]
    )
    assert result.exit_code == 0
    assert "# EU AI Act Compliance Report" in out_file.read_text(encoding="utf-8")
    assert "Report saved to" in result.output


def test_report_rejects_json_format(openai_project: Path) -> None:
    result = runner.invoke(app, ["report", str(openai_project), "--format", "json"])
    assert result.exit_code == 2
    assert "invalid format" in result.output


def test_report_nonexistent_path_exits_with_error() -> None:
    result = runner.invoke(app, ["report", "/does/not/exist"])
    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_recommend_on_ai_project_lists_recommendations(agent_project: Path) -> None:
    result = runner.invoke(app, ["recommend", str(agent_project)])
    assert result.exit_code == 0
    assert "Recommendations" in result.output


def test_recommend_clean_project_reports_nothing(clean_project: Path) -> None:
    result = runner.invoke(app, ["recommend", str(clean_project)])
    assert result.exit_code == 0
    assert "No compliance gaps" in result.output


def test_recommend_output_dir_writes_templates(agent_project: Path, tmp_path: Path) -> None:
    fixes = tmp_path / "fixes"
    result = runner.invoke(app, ["recommend", str(agent_project), "--output", str(fixes)])
    assert result.exit_code == 0
    assert (fixes / "RECOMMENDATIONS.md").is_file()


def test_serve_launches_uvicorn_on_localhost(monkeypatch, openai_project: Path) -> None:
    import sys
    import types

    calls: dict = {}
    fake_uvicorn = types.SimpleNamespace(run=lambda asgi_app, **kw: calls.update(kw, app=asgi_app))
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    result = runner.invoke(app, ["serve", str(openai_project), "--no-browser", "--port", "9137"])
    assert result.exit_code == 0
    assert calls["host"] == "127.0.0.1"  # localhost by default — no auth on this server
    assert calls["port"] == 9137
    assert calls["app"] is not None


def test_serve_without_web_extra_exits_helpfully(monkeypatch, openai_project: Path) -> None:
    import sys

    # Simulate `pip install compliance-agent` without the [web] extra.
    monkeypatch.setitem(sys.modules, "uvicorn", None)
    result = runner.invoke(app, ["serve", str(openai_project)])
    assert result.exit_code == 2
    assert "web" in result.output


def test_serve_nonexistent_path_exits_with_error() -> None:
    result = runner.invoke(app, ["serve", "/does/not/exist"])
    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_upgrade_rejects_invalid_version() -> None:
    result = runner.invoke(app, ["upgrade", "not-a-version"])
    assert result.exit_code == 2
    assert "invalid version" in result.output


def test_upgrade_reports_failure_exit_code(monkeypatch) -> None:
    from compliance_agent import updates

    monkeypatch.setattr(updates, "build_upgrade_command", lambda v: ["echo", "x"])
    monkeypatch.setattr(updates, "run_upgrade", lambda version="latest": 3)
    result = runner.invoke(app, ["upgrade"])
    assert result.exit_code == 3
    assert "Upgrade failed" in result.output


def test_notify_update_prints_when_newer(monkeypatch, capsys) -> None:
    from rich.console import Console

    from compliance_agent import cli, updates

    monkeypatch.setattr(updates, "check_for_update", lambda: "99.0.0")
    cli._notify_update(Console())
    assert "Update available" in capsys.readouterr().out


def test_upgrade_runs_detected_command(monkeypatch) -> None:
    from compliance_agent import updates

    calls = {}
    monkeypatch.setattr(updates, "build_upgrade_command", lambda v: ["echo", "upgrade", v])

    def fake_run(version: str = "latest") -> int:
        calls["version"] = version
        return 0

    monkeypatch.setattr(updates, "run_upgrade", fake_run)
    result = runner.invoke(app, ["upgrade"])
    assert result.exit_code == 0
    assert calls["version"] == "latest"
    assert "Done" in result.output


# --- diff command ---------------------------------------------------------


def _write_report(path: Path, *, tier: str, gaps: list[dict]) -> None:
    """Write a minimal scan-envelope JSON file (as `scan --format json` emits)."""
    envelope = {
        "schema_version": "1.0",
        "tool_name": "ComplianceAgent",
        "tool_version": __version__,
        "disclaimer": "x",
        "scan_result": {
            "project_path": "/proj",
            "findings": [],
            "scan_time": "2026-01-01T12:00:00",
            "files_scanned": 3,
            "risk_tier": tier,
            "gaps": gaps,
            "coverage": [],
        },
    }
    path.write_text(json.dumps(envelope), encoding="utf-8")


def _gap_dict(gap_id: str) -> dict:
    return {
        "id": gap_id,
        "title": f"gap {gap_id}",
        "article": "Art. 9",
        "severity": "high",
        "description": "d",
        "recommendation": "fix",
    }


def test_diff_reports_resolved_gap(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    target = tmp_path / "target.json"
    _write_report(base, tier="limited", gaps=[_gap_dict("g1"), _gap_dict("g2")])
    _write_report(target, tier="limited", gaps=[_gap_dict("g1")])

    result = runner.invoke(app, ["diff", str(base), str(target)])

    assert result.exit_code == 0
    assert "improved" in result.output.lower()


def test_diff_json_output_is_machine_readable(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    target = tmp_path / "target.json"
    _write_report(base, tier="high", gaps=[])
    _write_report(target, tier="limited", gaps=[])

    result = runner.invoke(app, ["diff", str(base), str(target), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["verdict"] == "improved"
    assert payload["tier_direction"] == "improved"


def test_diff_fail_on_regression_exits_nonzero(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    target = tmp_path / "target.json"
    _write_report(base, tier="limited", gaps=[])
    _write_report(target, tier="high", gaps=[_gap_dict("g9")])

    result = runner.invoke(app, ["diff", str(base), str(target), "--fail-on-regression"])

    assert result.exit_code == 1


def test_diff_fail_on_regression_passes_when_improved(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    target = tmp_path / "target.json"
    _write_report(base, tier="limited", gaps=[_gap_dict("g1")])
    _write_report(target, tier="limited", gaps=[])

    result = runner.invoke(app, ["diff", str(base), str(target), "--fail-on-regression"])

    assert result.exit_code == 0


def test_diff_missing_file_exits_with_error(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    _write_report(base, tier="limited", gaps=[])

    result = runner.invoke(app, ["diff", str(base), str(tmp_path / "nope.json")])

    assert result.exit_code == 2


def test_diff_malformed_file_exits_with_error(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    target = tmp_path / "target.json"
    _write_report(base, tier="limited", gaps=[])
    target.write_text("{ not valid json", encoding="utf-8")

    result = runner.invoke(app, ["diff", str(base), str(target)])

    assert result.exit_code == 2


def test_diff_non_object_json_exits_with_error(tmp_path: Path) -> None:
    # Valid JSON but the wrong shape (a bare array) — a plausible "wrong file"
    # mistake must give the friendly exit-2 error, not an unhandled traceback.
    base = tmp_path / "base.json"
    target = tmp_path / "target.json"
    _write_report(base, tier="limited", gaps=[])
    target.write_text("[1, 2, 3]", encoding="utf-8")

    result = runner.invoke(app, ["diff", str(base), str(target)])

    assert result.exit_code == 2
