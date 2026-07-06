"""Tests for the Rich terminal reporter.

The CLI renders raw Markdown when piped (non-TTY), so these exercise the
terminal report surface directly with a recording Console.
"""

import io
from datetime import datetime
from pathlib import Path

from rich.console import Console

from compliance_agent.analyzer.gaps import GapAnalyzer
from compliance_agent.classifier.risk import RiskClassifier
from compliance_agent.models.findings import Finding, RiskTier, ScanResult, Severity
from compliance_agent.recommender.engine import FixRecommender
from compliance_agent.reporter import terminal
from compliance_agent.scanner.engine import ScannerEngine


def _rich_result(project: Path) -> ScanResult:
    engine = ScannerEngine(project)
    result = engine.scan()
    assessment = RiskClassifier().classify(result, project_text=engine.domain_corpus)
    result = result.model_copy(update={"risk_tier": assessment.tier, "risk_assessment": assessment})
    analyzer = GapAnalyzer()
    result = result.model_copy(
        update={"gaps": analyzer.analyze(result), "coverage": analyzer.coverage(result)}
    )
    return result.model_copy(update={"recommendations": FixRecommender().recommend(result)})


def _render(renderable) -> str:
    console = Console(file=io.StringIO(), record=True, width=200)
    console.print(renderable)
    return console.export_text()


def _report(result: ScanResult) -> str:
    console = Console(file=io.StringIO(), record=True, width=200)
    terminal.render_report(console, result)
    return console.export_text()


def test_full_terminal_report_renders_all_sections(hiring_project: Path) -> None:
    out = _report(_rich_result(hiring_project))
    for section in (
        "Scan Summary",
        "Compliance Coverage",
        "Risk Assessment",
        "Findings",
        "Compliance Gaps",
        "Recommendations",
    ):
        assert section in out, section
    assert "not legal advice" in out.lower()


def test_terminal_frameworks_section(tmp_path: Path) -> None:
    (tmp_path / "crew.py").write_text("from crewai import Agent, Crew\ncrew = Crew(agents=[])\n")
    out = _report(_rich_result(tmp_path))
    assert "Frameworks Detected" in out
    assert "crewai" in out


def test_terminal_next_steps_with_gaps(hiring_project: Path) -> None:
    out = _render(terminal.build_next_steps(_rich_result(hiring_project), str(hiring_project)))
    assert "recommend" in out


def test_terminal_next_steps_clean(clean_project: Path) -> None:
    out = _render(terminal.build_next_steps(_rich_result(clean_project), "."))
    assert "No gaps detected" in out


def test_terminal_quiet_summary(hiring_project: Path) -> None:
    result = _rich_result(hiring_project)
    console = Console(file=io.StringIO(), record=True, width=200)
    terminal.print_summary(console, result)
    out = console.export_text()
    assert "Scan Summary" in out
    assert "Compliance Gaps" not in out  # detail sections omitted in quiet mode


def test_terminal_scan_errors_section() -> None:
    result = ScanResult(
        project_path="/x",
        findings=[],
        scan_time=datetime.now(),
        files_scanned=1,
        scan_errors=["providers failed on app.py: boom"],
    )
    out = _render(terminal.build_scan_errors(result))
    assert "could not be fully analyzed" in out
    assert "boom" in out


def test_findings_empty_message_distinguishes_no_ai_from_filtered() -> None:
    with_findings = ScanResult(
        project_path="/x",
        findings=[
            Finding(
                id="t:1",
                file_path="app.py",
                detector="providers",
                severity=Severity.INFO,
                category="provider:openai",
                message="OpenAI usage",
                description="",
            )
        ],
        scan_time=datetime.now(),
        files_scanned=1,
    )
    empty = with_findings.model_copy(update={"findings": []})

    # No AI at all -> reassuring message.
    assert "No AI usage patterns detected" in _render(terminal.build_findings(empty))
    # AI detected but filtered out by --severity -> honest, non-reassuring message.
    filtered = _render(terminal.build_findings(empty, summary_source=with_findings))
    assert "No findings at or above" in filtered
    assert "No AI usage patterns detected" not in filtered


def test_terminal_strips_control_chars_from_repo_paths() -> None:
    # A hostile filename carrying a raw ESC byte must not leak the control
    # sequence into the rendered terminal report.
    finding = Finding(
        id="t:evil",
        file_path="evil\x1b[31mred.py",
        detector="providers",
        severity=Severity.INFO,
        category="provider:openai",
        message="uses \x1b]0;pwned\x07openai",
        description="",
    )
    result = ScanResult(
        project_path="proj\x1b[2J",
        findings=[finding],
        scan_time=datetime.now(),
        files_scanned=1,
        risk_tier=RiskTier.MINIMAL,
    )
    out = _report(result)
    # The ESC byte that *starts* an ANSI/OSC sequence is gone, so the leftover
    # "[31m" is inert literal text a terminal will not interpret.
    assert "\x1b" not in out
    assert "\x07" not in out
    assert "evil[31mred.py" in out  # path text preserved, control byte stripped
