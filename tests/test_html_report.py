"""Tests for the self-contained HTML dashboard export."""

import json
from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from compliance_agent import __version__
from compliance_agent.cli import app
from compliance_agent.models.findings import Finding, RiskTier, ScanResult, Severity
from compliance_agent.pipeline import run_pipeline
from compliance_agent.reporter.html_report import render_html, write_html

runner = CliRunner()


def test_render_html_is_self_contained(openai_project: Path) -> None:
    html = render_html(run_pipeline(openai_project, with_recommendations=True))
    assert html.startswith("<!doctype html>")
    assert "window.__SCAN_DATA__" in html
    assert "<style>" in html and "<script>" in html  # assets inlined
    for marker in ("%STYLES%", "%SCRIPTS%", "%DATA%"):
        assert marker not in html
    # no external resources — the file must work offline
    assert "http://" not in html.split("</style>")[0] or "xmlns" in html
    assert "not legal advice" in html


def test_render_html_embeds_valid_envelope(openai_project: Path) -> None:
    html = render_html(run_pipeline(openai_project))
    payload = html.split("window.__SCAN_DATA__ = ", 1)[1].split(";</script>", 1)[0]
    envelope = json.loads(payload)
    assert envelope["schema_version"] == "1.1"
    assert envelope["tool_version"] == __version__
    assert envelope["scan_result"]["findings"]


def test_render_html_neutralizes_script_breakout() -> None:
    # A scanned file named to close the data <script> block must not be able to
    # inject markup into its own compliance report.
    finding = Finding(
        id="t:evil",
        file_path="</script><script>alert(1)</script>.py",
        detector="providers",
        severity=Severity.INFO,
        category="provider:openai",
        message="x",
        description="",
    )
    result = ScanResult(
        project_path="/x",
        findings=[finding],
        scan_time=datetime.now(),
        files_scanned=1,
        risk_tier=RiskTier.MINIMAL,
    )
    html = render_html(result)
    data_block = html.split("window.__SCAN_DATA__ = ", 1)[1]
    assert "</script><script>" not in data_block.split(";</script>", 1)[0]


def test_write_html_default_filename(openai_project: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = write_html(run_pipeline(openai_project))
    assert out.name == f"compliance-dashboard-{openai_project.name}.html"
    assert out.is_file()


def test_scan_html_format_writes_dashboard(openai_project: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "dash.html"
    result = runner.invoke(
        app, ["scan", str(openai_project), "--format", "html", "--output", str(out_file)]
    )
    assert result.exit_code == 0
    assert "Dashboard saved to" in result.output
    assert "window.__SCAN_DATA__" in out_file.read_text(encoding="utf-8")


def test_scan_html_unwritable_output_exits_helpfully(openai_project: Path) -> None:
    result = runner.invoke(
        app,
        ["scan", str(openai_project), "--format", "html", "--output", "/dev/null/nope/dash.html"],
    )
    assert result.exit_code == 2
    assert "Cannot write the dashboard" in result.output


def test_report_html_format(openai_project: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "report.html"
    result = runner.invoke(
        app, ["report", str(openai_project), "--format", "html", "--output", str(out_file)]
    )
    assert result.exit_code == 0
    assert out_file.is_file()
