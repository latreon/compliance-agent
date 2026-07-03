"""Tests for article-specific gap analyzers and the coverage table."""

from datetime import datetime
from pathlib import Path

from compliance_agent.analyzer.articles import (
    ALL_ARTICLE_ANALYZERS,
    Art6Analyzer,
    Art13Analyzer,
    Art15Analyzer,
    Art26Analyzer,
    Art28Analyzer,
)
from compliance_agent.analyzer.gaps import GapAnalyzer
from compliance_agent.classifier.risk import RiskClassifier
from compliance_agent.models.findings import (
    Finding,
    RiskTier,
    ScanResult,
    Severity,
)
from compliance_agent.reporter.markdown import render_coverage, render_markdown
from compliance_agent.reporter.pdf_report import PDFReporter
from compliance_agent.scanner.engine import ScannerEngine


def _result(
    findings: list[Finding] | None = None,
    risk_tier: RiskTier | None = None,
    project_path: str = "/nonexistent-test-project",
) -> ScanResult:
    return ScanResult(
        project_path=project_path,
        findings=findings or [],
        scan_time=datetime.now(),
        files_scanned=1,
        risk_tier=risk_tier,
    )


def _finding(category: str, detector: str = "test") -> Finding:
    return Finding(
        id=f"t:{category}",
        file_path="app.py",
        detector=detector,
        severity=Severity.INFO,
        category=category,
        message=category,
        description=category,
    )


# --- individual articles ---------------------------------------------------------


def test_art6_high_risk_analysis() -> None:
    gaps = Art6Analyzer().analyze(_result(risk_tier=RiskTier.HIGH))
    assert len(gaps) >= 1
    assert gaps[0].article == "Art. 6"
    assert gaps[0].severity == Severity.CRITICAL


def test_art6_limited_risk_no_gaps() -> None:
    gaps = Art6Analyzer().analyze(_result(risk_tier=RiskTier.LIMITED))
    assert gaps == []


def test_art13_user_interaction_gaps(tmp_path: Path) -> None:
    result = _result(findings=[_finding("pattern:user-input")], project_path=str(tmp_path))
    gaps = Art13Analyzer().analyze(result)
    assert len(gaps) == 3  # instructions, interpretation, input info
    assert all(g.article == "Art. 13" for g in gaps)


def test_art13_not_applicable_without_user_interaction() -> None:
    gaps = Art13Analyzer().analyze(_result(findings=[_finding("provider:openai")]))
    assert gaps == []


def test_art15_missing_error_handling(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("import openai\nclient = openai.OpenAI()\n")
    result = _result(findings=[_finding("provider:openai")], project_path=str(tmp_path))
    gaps = Art15Analyzer().analyze(result)
    assert any(g.title == "Error handling mechanisms required" for g in gaps)


def test_art15_met_when_error_handling_present(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "import openai\ntry:\n    x = validate(input)\nexcept ValueError:\n    pass\n"
    )
    result = _result(findings=[_finding("provider:openai")], project_path=str(tmp_path))
    gaps = Art15Analyzer().analyze(result)
    titles = {g.title for g in gaps}
    assert "Error handling mechanisms required" not in titles
    assert "Cybersecurity measures required" not in titles


def test_art26_high_risk_comprehensive() -> None:
    gaps = Art26Analyzer().analyze(_result(risk_tier=RiskTier.HIGH))
    assert len(gaps) >= 4
    assert all(g.article == "Art. 26" for g in gaps)


def test_art26_not_applicable_below_high_tier() -> None:
    assert Art26Analyzer().analyze(_result(risk_tier=RiskTier.LIMITED)) == []


def test_art28_applies_only_with_deployment_artifacts(tmp_path: Path) -> None:
    result = _result(project_path=str(tmp_path))
    assert Art28Analyzer().analyze(result) == []

    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
    gaps = Art28Analyzer().analyze(result)
    assert gaps
    assert all(g.article == "Art. 28" for g in gaps)


# --- gap analyzer orchestration -------------------------------------------------------


def test_all_articles_loaded() -> None:
    analyzer = GapAnalyzer()
    assert len(analyzer.analyzers) == len(ALL_ARTICLE_ANALYZERS) == 12
    numbers = {a.article_number for a in analyzer.analyzers}
    assert numbers == {6, 7, 9, 10, 11, 12, 13, 14, 15, 26, 28, 50}


def test_gaps_sorted_most_severe_first() -> None:
    gaps = GapAnalyzer().analyze(_result(risk_tier=RiskTier.HIGH))
    ranks = ["critical", "high", "warning", "info"]
    positions = [ranks.index(g.severity.value) for g in gaps]
    assert positions == sorted(positions)


def test_coverage_covers_every_article() -> None:
    coverage = GapAnalyzer().coverage(_result(risk_tier=RiskTier.LIMITED))
    assert len(coverage) == 12
    art6 = next(c for c in coverage if c.article == "Art. 6")
    assert art6.status == "not_applicable"
    assert "limited" in art6.reason


def test_coverage_statuses_for_real_project(agent_project: Path) -> None:
    result = ScannerEngine(agent_project).scan()
    assessment = RiskClassifier().classify(result)
    result = result.model_copy(update={"risk_tier": assessment.tier, "risk_assessment": assessment})
    coverage = GapAnalyzer().coverage(result)

    art12 = next(c for c in coverage if c.article == "Art. 12")
    assert art12.status == "missing"  # anthropic usage without logging
    statuses = {c.status for c in coverage}
    assert statuses <= {"met", "partial", "missing", "not_applicable"}


# --- reporting -------------------------------------------------------------------------


def _full_result(project: Path) -> ScanResult:
    result = ScannerEngine(project).scan()
    assessment = RiskClassifier().classify(result)
    result = result.model_copy(update={"risk_tier": assessment.tier, "risk_assessment": assessment})
    analyzer = GapAnalyzer()
    return result.model_copy(
        update={"gaps": analyzer.analyze(result), "coverage": analyzer.coverage(result)}
    )


def test_markdown_includes_coverage_table(agent_project: Path) -> None:
    report = render_markdown(_full_result(agent_project))
    assert "## Compliance Coverage" in report
    assert "Art. 12" in report
    assert "Not applicable" in report  # e.g. Art. 6 at non-high tier


def test_render_coverage_empty_without_data() -> None:
    assert render_coverage(_result()) == ""


def test_pdf_html_includes_coverage(agent_project: Path) -> None:
    html = PDFReporter()._render_html(_full_result(agent_project))
    assert "Compliance coverage" in html
    assert "Art. 12" in html


def test_gap_ids_map_to_article_recommendations(agent_project: Path) -> None:
    from compliance_agent.recommender.engine import FixRecommender

    result = _full_result(agent_project)
    recs = FixRecommender().recommend(result)
    art12 = next(r for r in recs if r.rule_key == "art12")
    assert any(t.startswith("gap:art12:") for t in art12.triggered_by)
