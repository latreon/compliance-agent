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
    assert payload["files_scanned"] == 2
    assert payload["risk_tier"] is not None
    assert isinstance(payload["findings"], list)


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
