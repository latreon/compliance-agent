"""Tests for article-specific gap analyzers and the coverage table."""

import io
from datetime import datetime
from pathlib import Path

from compliance_agent.analyzer.articles import (
    ALL_ARTICLE_ANALYZERS,
    Art5Analyzer,
    Art6Analyzer,
    Art9Analyzer,
    Art13Analyzer,
    Art14Analyzer,
    Art15Analyzer,
    Art16Analyzer,
    Art24Analyzer,
    Art43Analyzer,
    Art50Analyzer,
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


def test_art5_applies_only_when_unacceptable() -> None:
    assert Art5Analyzer().analyze(_result(risk_tier=RiskTier.LIMITED)) == []
    assert Art5Analyzer().analyze(_result(risk_tier=RiskTier.HIGH)) == []


def test_art5_unacceptable_emits_critical_blocking_gap() -> None:
    gaps = Art5Analyzer().analyze(_result(risk_tier=RiskTier.UNACCEPTABLE))
    assert len(gaps) == 1
    assert gaps[0].article == "Art. 5"
    assert gaps[0].severity == Severity.CRITICAL


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


def test_art15_error_handling_unverified_not_met(tmp_path: Path) -> None:
    # A project-wide try/except (or a `validate` helper) cannot be tied to the
    # AI call site by static keyword matching, so it must NOT confirm the
    # requirement as MET. It downgrades the gap to UNVERIFIED ("verify manually"),
    # never removes it — otherwise an unrelated try/except elsewhere would clear a
    # HIGH obligation on a project with an unguarded model call.
    (tmp_path / "app.py").write_text(
        "import openai\ntry:\n    x = validate(input)\nexcept ValueError:\n    pass\n"
    )
    result = _result(findings=[_finding("provider:openai")], project_path=str(tmp_path))
    gaps = Art15Analyzer().analyze(result)
    by_title = {g.title: g for g in gaps}
    assert by_title["Error handling mechanisms required"].status == "unverified"
    assert by_title["Cybersecurity measures required"].status == "unverified"


def test_art43_prose_mention_is_unverified_not_met(tmp_path: Path) -> None:
    # A README that merely names "conformity assessment" must NOT mark the
    # CRITICAL Art. 43 obligation as met — it becomes an unverified gap.
    (tmp_path / "README.md").write_text("We perform a conformity assessment before release.\n")
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art43Analyzer().analyze(result)
    conformity = next(g for g in gaps if g.title.startswith("Conformity assessment"))
    assert conformity.status == "unverified"


def test_art43_met_only_with_real_artifact(tmp_path: Path) -> None:
    # An actual conformity-assessment document is verifiable evidence -> met (no gap).
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "conformity-assessment.md").write_text("Assessment recorded.\n")
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art43Analyzer().analyze(result)
    assert not any(g.title.startswith("Conformity assessment") for g in gaps)


def test_art50_comment_does_not_satisfy_disclosure(tmp_path: Path) -> None:
    # Regression: a disclosure phrase in a COMMENT is not an implemented
    # mechanism — comments are stripped before matching, so the requirement
    # stays unmet.
    (tmp_path / "app.py").write_text(
        "import openai\n"
        '# TODO: tell users "you are interacting with an ai" before shipping\n'
        "client = openai.OpenAI()\n"
    )
    result = _result(
        findings=[_finding("provider:openai"), _finding("pattern:chat-interface")],
        project_path=str(tmp_path),
    )
    gaps = Art50Analyzer().analyze(result)
    assert any(g.title == "AI interaction disclosure required" for g in gaps)


def test_art50_disclosure_phrase_literal_is_unverified_not_met(tmp_path: Path) -> None:
    # A bare disclosure PHRASE in an arbitrary string literal (could be marketing
    # copy that is never shown to a user) is weak evidence: it downgrades the gap
    # to UNVERIFIED, but must NOT mark the requirement MET.
    (tmp_path / "app.py").write_text(
        "import openai\n"
        'AI_NOTICE = "You are interacting with an AI system."\n'
        "client = openai.OpenAI()\n"
    )
    result = _result(
        findings=[_finding("provider:openai"), _finding("pattern:chat-interface")],
        project_path=str(tmp_path),
    )
    gaps = Art50Analyzer().analyze(result)
    disclosure = next(g for g in gaps if g.title == "AI interaction disclosure required")
    assert disclosure.status == "unverified"


def test_art50_structured_disclosure_identifier_is_met(tmp_path: Path) -> None:
    # A deliberate disclosure construct (a named field/header) is verifiable
    # evidence of an implemented control -> MET (no gap).
    (tmp_path / "app.py").write_text(
        "import openai\nai_disclosure = True\nclient = openai.OpenAI()\n"
    )
    result = _result(
        findings=[_finding("provider:openai"), _finding("pattern:chat-interface")],
        project_path=str(tmp_path),
    )
    gaps = Art50Analyzer().analyze(result)
    assert not any(g.title == "AI interaction disclosure required" for g in gaps)


def test_art16_high_risk_comprehensive() -> None:
    gaps = Art16Analyzer().analyze(_result(risk_tier=RiskTier.HIGH))
    assert len(gaps) >= 4
    assert all(g.article == "Art. 16" for g in gaps)


def test_art16_not_applicable_below_high_tier() -> None:
    assert Art16Analyzer().analyze(_result(risk_tier=RiskTier.LIMITED)) == []


def test_art24_applies_only_with_deployment_artifacts(tmp_path: Path) -> None:
    result = _result(project_path=str(tmp_path))
    assert Art24Analyzer().analyze(result) == []

    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
    gaps = Art24Analyzer().analyze(result)
    assert gaps
    assert all(g.article == "Art. 24" for g in gaps)


# --- gap analyzer orchestration -------------------------------------------------------


def test_all_articles_loaded() -> None:
    analyzer = GapAnalyzer()
    assert len(analyzer.analyzers) == len(ALL_ARTICLE_ANALYZERS) == 13
    numbers = {a.article_number for a in analyzer.analyzers}
    assert numbers == {5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 24, 43, 50}


def test_gaps_sorted_most_severe_first() -> None:
    gaps = GapAnalyzer().analyze(_result(risk_tier=RiskTier.HIGH))
    ranks = ["critical", "high", "warning", "info"]
    positions = [ranks.index(g.severity.value) for g in gaps]
    assert positions == sorted(positions)


def test_coverage_covers_every_article() -> None:
    coverage = GapAnalyzer().coverage(_result(risk_tier=RiskTier.LIMITED))
    assert len(coverage) == 13
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
    assert statuses <= {"met", "partial", "unverified", "missing", "not_applicable"}


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


# ---------- regression tests for pre-release honesty/correctness fixes --------


def test_art9_empty_risk_register_does_not_satisfy_control(tmp_path: Path) -> None:
    # Regression: an empty placeholder file (e.g. `touch risk_register.json`)
    # must NOT flip the CRITICAL Art. 9 requirement to met.
    (tmp_path / "risk_register.json").write_text("")
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art9Analyzer().analyze(result)
    assert any(g.title == "Risk management system required" for g in gaps)


def test_art9_risk_register_with_content_is_met(tmp_path: Path) -> None:
    (tmp_path / "risk_register.json").write_text(
        '{"risks": [{"id": 1, "description": "model bias in candidate scoring"}]}'
    )
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art9Analyzer().analyze(result)
    assert not any(g.title == "Risk management system required" for g in gaps)


def test_art14_bare_approval_identifier_does_not_clear_oversight(tmp_path: Path) -> None:
    # Regression: an ordinary business identifier like `process_loan_approval`
    # must NOT satisfy the human-oversight mechanism on an autonomous high-risk
    # agent. The gap must remain.
    (tmp_path / "app.py").write_text(
        "def process_loan_approval(application):\n    return application\n"
    )
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art14Analyzer().analyze(result)
    assert any(g.title == "Human oversight mechanism required" for g in gaps)


def test_art14_explicit_approval_gate_is_met(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def gate(action):\n    require_approval(action)\n    return action\n"
    )
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art14Analyzer().analyze(result)
    assert not any(g.title == "Human oversight mechanism required" for g in gaps)


def test_capitalized_tests_dir_is_treated_as_test_code() -> None:
    # Regression: a capitalized `Tests/` directory must be recognised as test
    # code so fixtures don't leak into the domain corpus / article probes.
    from compliance_agent.scanner.engine import _is_test_path

    assert _is_test_path(Path("Tests/fixtures/biometric_sample.py")) is True
    assert _is_test_path(Path("TESTS/data.py")) is True
    assert _is_test_path(Path("src/app.py")) is False


def test_terminal_findings_render_survives_markup_in_file_path() -> None:
    # Regression: a scanned repo containing a file/dir named like Rich markup
    # (e.g. "[/bold]") must not crash the default scan report.
    from rich.console import Console

    from compliance_agent.reporter.terminal import build_findings

    finding = Finding(
        id="t:evil",
        file_path="[/bold]evil/model.py",
        detector="providers",
        severity=Severity.INFO,
        category="provider:openai",
        message="uses [red]openai[/red]",
        description="",
    )
    result = _result(findings=[finding])
    # Wide enough that the path is not column-folded across lines.
    console = Console(file=io.StringIO(), record=True, width=400)
    console.print(build_findings(result))  # must not raise MarkupError
    output = console.export_text()
    # The markup-looking path renders literally (not consumed as a style tag).
    assert "[/bold]evil/model.py" in output


def test_scan_errors_surface_in_markdown(tmp_path: Path) -> None:
    result = _result(project_path=str(tmp_path))
    result = result.model_copy(update={"scan_errors": ["providers failed on x.py: boom"]})
    md = render_markdown(result)
    assert "Incomplete scan" in md
