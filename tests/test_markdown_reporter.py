"""Tests for the Markdown reporter's escaping and list rendering."""

from datetime import datetime
from pathlib import Path

from compliance_agent.analyzer.gaps import GapAnalyzer
from compliance_agent.classifier.risk import RiskClassifier
from compliance_agent.models.findings import Finding, RiskTier, ScanResult, Severity
from compliance_agent.recommender.engine import FixRecommender
from compliance_agent.reporter.markdown import render_markdown, render_recommendations
from compliance_agent.scanner.engine import ScannerEngine


def _full_result(project: Path) -> ScanResult:
    engine = ScannerEngine(project)
    result = engine.scan()
    assessment = RiskClassifier().classify(result, project_text=engine.domain_corpus)
    result = result.model_copy(update={"risk_tier": assessment.tier, "risk_assessment": assessment})
    analyzer = GapAnalyzer()
    result = result.model_copy(
        update={"gaps": analyzer.analyze(result), "coverage": analyzer.coverage(result)}
    )
    return result.model_copy(update={"recommendations": FixRecommender().recommend(result)})


def test_recommendation_steps_are_sequentially_numbered(agent_project: Path) -> None:
    # Regression: every step rendered as "1." (relied on Markdown auto-renumber),
    # which reads as "1. 1. 1." in any raw-text view.
    result = _full_result(agent_project)
    rec = next(r for r in result.recommendations if len(r.steps) >= 2)
    section = render_recommendations(result.model_copy(update={"recommendations": [rec]}))
    assert "1. " in section
    assert "2. " in section


def test_markdown_strips_control_chars_from_repo_paths() -> None:
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
    md = render_markdown(result)
    assert "\x1b" not in md
    assert "\x07" not in md
    assert "evil[31mred.py" in md
