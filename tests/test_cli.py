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


def test_upgrade_rejects_invalid_version() -> None:
    result = runner.invoke(app, ["upgrade", "not-a-version"])
    assert result.exit_code == 2
    assert "invalid version" in result.output


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
