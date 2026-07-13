"""Tests for article-specific gap analyzers and the coverage table."""

import io
from datetime import datetime
from pathlib import Path

from compliance_agent.analyzer.articles import (
    ALL_ARTICLE_ANALYZERS,
    Art5Analyzer,
    Art6Analyzer,
    Art9Analyzer,
    Art10Analyzer,
    Art11Analyzer,
    Art12Analyzer,
    Art13Analyzer,
    Art14Analyzer,
    Art15Analyzer,
    Art16Analyzer,
    Art17Analyzer,
    Art24Analyzer,
    Art26Analyzer,
    Art27Analyzer,
    Art43Analyzer,
    Art50Analyzer,
    Art53_55Analyzer,
)
from compliance_agent.analyzer.articles.base import ProjectProbe
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


def test_probe_skips_symlinked_source(tmp_path: Path) -> None:
    # A symlinked .py must never be read by the probe: it can point outside the
    # project or at a device node (/dev/zero) that hangs the read. Here the link
    # escapes the project root — its content must be excluded, while a real file
    # in the project is still read.
    import tempfile

    from compliance_agent.analyzer.articles.base import ProjectProbe

    (tmp_path / "real.py").write_text("MARKER_IN_PROJECT = 'oversight_checkpoint'\n")
    external = Path(tempfile.mkdtemp()) / "outside.py"
    external.write_text("MARKER_VIA_SYMLINK = 'do_not_read'\n")
    (tmp_path / "link.py").symlink_to(external)

    code = ProjectProbe(tmp_path).code_text
    assert "oversight_checkpoint" in code  # real project file is read
    assert "do_not_read" not in code  # symlink escaping the project is skipped


def test_art13_applies_to_high_risk_system(tmp_path: Path) -> None:
    # Art. 13 (instructions for use to deployers) is a high-risk-only obligation.
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art13Analyzer().analyze(result)
    assert len(gaps) == 3  # instructions, interpretation, input info
    assert all(g.article == "Art. 13" for g in gaps)


def test_art13_not_applicable_below_high_risk() -> None:
    # A limited-risk chatbot with user interaction is NOT subject to Art. 13 —
    # it applied at HIGH severity to any user-facing AI before, overstating the
    # obligation.
    result = _result(findings=[_finding("pattern:user-input")], risk_tier=RiskTier.LIMITED)
    assert Art13Analyzer().analyze(result) == []


def test_art15_missing_error_handling(tmp_path: Path) -> None:
    # Art. 15 (accuracy/robustness/cybersecurity) is a high-risk-only obligation.
    (tmp_path / "app.py").write_text("import openai\nclient = openai.OpenAI()\n")
    result = _result(
        findings=[_finding("provider:openai")],
        risk_tier=RiskTier.HIGH,
        project_path=str(tmp_path),
    )
    gaps = Art15Analyzer().analyze(result)
    assert any(g.title == "Error handling mechanisms required" for g in gaps)


def test_art15_not_applicable_below_high_risk() -> None:
    # A limited-risk chatbot is NOT subject to Art. 15's high-risk robustness and
    # cybersecurity obligations; it must not receive HIGH-severity Art. 15 gaps.
    result = _result(findings=[_finding("provider:openai")], risk_tier=RiskTier.LIMITED)
    assert Art15Analyzer().analyze(result) == []


def test_art15_error_handling_unverified_not_met(tmp_path: Path) -> None:
    # A project-wide try/except (or a `validate` helper) cannot be tied to the
    # AI call site by static keyword matching, so it must NOT confirm the
    # requirement as MET. It downgrades the gap to UNVERIFIED ("verify manually"),
    # never removes it — otherwise an unrelated try/except elsewhere would clear a
    # HIGH obligation on a project with an unguarded model call.
    (tmp_path / "app.py").write_text(
        "import openai\ntry:\n    x = validate(input)\nexcept ValueError:\n    pass\n"
    )
    result = _result(
        findings=[_finding("provider:openai")],
        risk_tier=RiskTier.HIGH,
        project_path=str(tmp_path),
    )
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
    # A substantive conformity-assessment document is verifiable evidence -> met
    # (no gap). The content must clear the min_content_chars gate that stops an
    # empty/placeholder file from satisfying a CRITICAL obligation.
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "conformity-assessment.md").write_text(
        "# Conformity assessment\n\n"
        "Internal control procedure completed per Annex VI on 2026-01-15; "
        "results recorded and signed off by the responsible person.\n"
    )
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art43Analyzer().analyze(result)
    assert not any(g.title.startswith("Conformity assessment") for g in gaps)


def test_art43_empty_placeholder_does_not_satisfy(tmp_path: Path) -> None:
    # Regression: `touch CONFORMITY.md` must NOT flip the CRITICAL conformity
    # obligation to met — an empty placeholder is not evidence of an assessment.
    (tmp_path / "CONFORMITY.md").write_text("")
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art43Analyzer().analyze(result)
    assert any(g.title.startswith("Conformity assessment") for g in gaps)


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


# --- Art. 17 (Quality management system) -----------------------------------------


def test_art17_not_applicable_below_high_risk() -> None:
    assert Art17Analyzer().analyze(_result(risk_tier=RiskTier.LIMITED)) == []


def test_art17_empty_qms_doc_does_not_satisfy(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "quality-management.md").write_text("")
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art17Analyzer().analyze(result)
    assert any(g.title.startswith("Quality management system") for g in gaps)


def test_art17_substantive_qms_doc_satisfies(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "quality-management.md").write_text(
        "# Quality management system\n\n"
        "Regulatory compliance strategy, design QA techniques, and data "
        "management procedures are documented here per Art. 17(1).\n"
    )
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art17Analyzer().analyze(result)
    assert not any(g.title.startswith("Quality management system") for g in gaps)


def test_art17_testing_and_accountability_are_separate_requirements(tmp_path: Path) -> None:
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art17Analyzer().analyze(result)
    titles = {g.title for g in gaps}
    assert "QMS testing and validation procedures required" in titles
    assert "QMS accountability framework required" in titles


# --- Art. 26 (Deployer obligations) -----------------------------------------------


def test_art26_not_applicable_below_high_risk() -> None:
    assert Art26Analyzer().analyze(_result(risk_tier=RiskTier.LIMITED)) == []


def test_art26_high_risk_emits_five_deployer_requirements(tmp_path: Path) -> None:
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art26Analyzer().analyze(result)
    assert len(gaps) == 5
    assert all(g.article == "Art. 26" for g in gaps)


def test_art26_log_retention_mechanism_satisfies_requirement(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "from art12 import AILogger\nlogger = AILogger()\nlogger.cleanup_expired()\n"
    )
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art26Analyzer().analyze(result)
    assert not any(g.title.startswith("Deployer log retention") for g in gaps)


def test_art26_decision_notice_mechanism_satisfies_requirement(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def notify_subject(notice):\n    return notice\n")
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art26Analyzer().analyze(result)
    assert not any(g.title.startswith("Individuals subject to") for g in gaps)


# --- Art. 27 (Fundamental rights impact assessment) -------------------------------


def test_art27_not_applicable_below_high_risk() -> None:
    assert Art27Analyzer().analyze(_result(risk_tier=RiskTier.LIMITED)) == []


def test_art27_empty_fria_placeholder_does_not_satisfy(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "fria.md").write_text("")
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art27Analyzer().analyze(result)
    assert any(g.title.startswith("Fundamental rights impact assessment") for g in gaps)


def test_art27_substantive_fria_satisfies(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "fria.md").write_text(
        "# Fundamental rights impact assessment\n\n"
        "Categories of affected persons, specific risks, and mitigation "
        "measures with a complaint mechanism are documented per Art. 27(1).\n"
    )
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art27Analyzer().analyze(result)
    assert not any(g.title.startswith("Fundamental rights impact assessment") for g in gaps)


# --- Art. 14 override/reverse capability (Art. 14(4)(d)-(e)) ---------------------


def test_art14_override_requirement_missing_by_default(tmp_path: Path) -> None:
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art14Analyzer().analyze(result)
    assert any(g.title == "Ability to override or reverse AI system output required" for g in gaps)


def test_art14_kill_switch_satisfies_override_requirement(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def kill_switch():\n    stop_agent()\n")
    result = _result(risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art14Analyzer().analyze(result)
    assert not any(
        g.title == "Ability to override or reverse AI system output required" for g in gaps
    )


# --- Art. 50 expanded sub-obligations (content marking, deepfake, biometric) -----


def test_art50_plain_chatbot_gets_only_base_disclosure_requirement(tmp_path: Path) -> None:
    # No synthetic-media/deepfake/biometric signal: only the core Art. 50(1)
    # disclosure requirement should apply — the other three would be false
    # obligations on a plain text chatbot.
    result = _result(
        findings=[_finding("provider:openai"), _finding("pattern:chat-interface")],
        project_path=str(tmp_path),
    )
    reqs = Art50Analyzer().requirements(result, ProjectProbe(str(tmp_path)))
    assert len(reqs) == 1
    assert reqs[0].name == "AI interaction disclosure required"


def test_art50_content_marking_gated_on_synthetic_media_signal(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def generate_image(prompt):\n    return call_dalle(prompt)\n")
    result = _result(
        findings=[_finding("provider:openai"), _finding("pattern:chat-interface")],
        project_path=str(tmp_path),
    )
    gaps = Art50Analyzer().analyze(result)
    assert any(g.title == "AI-generated content must be marked as such" for g in gaps)


def test_art50_deepfake_disclosure_gated_on_deepfake_signal(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def face_swap(image, target):\n    return run(image, target)\n"
    )
    result = _result(
        findings=[_finding("provider:openai"), _finding("pattern:chat-interface")],
        project_path=str(tmp_path),
    )
    gaps = Art50Analyzer().analyze(result)
    assert any(g.title == "Deepfake content must be disclosed" for g in gaps)


def test_art50_emotion_recognition_disclosure_gated_on_signal(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def emotion_recognition(audio):\n    return classify(audio)\n"
    )
    result = _result(
        findings=[_finding("provider:openai"), _finding("pattern:chat-interface")],
        project_path=str(tmp_path),
    )
    gaps = Art50Analyzer().analyze(result)
    assert any(
        g.title == "Emotion recognition / biometric categorisation disclosure required"
        for g in gaps
    )


def test_art50_content_marking_mechanism_satisfies_requirement(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def generate_image(prompt):\n"
        "    marker = AIContentMarker(generator='dalle-3', provider='openai')\n"
        "    return call_dalle(prompt), marker\n"
    )
    result = _result(
        findings=[_finding("provider:openai"), _finding("pattern:chat-interface")],
        project_path=str(tmp_path),
    )
    gaps = Art50Analyzer().analyze(result)
    assert not any(g.title == "AI-generated content must be marked as such" for g in gaps)


def test_art53_55_not_applicable_for_ordinary_api_consumer(tmp_path: Path) -> None:
    # Calling a hosted provider's API makes a project a *deployer*, not a GPAI
    # model *provider* — Art. 53-55 must not fire just because openai is imported.
    (tmp_path / "app.py").write_text("import openai\nclient = openai.OpenAI()\n")
    result = _result(
        findings=[_finding("provider:openai")],
        risk_tier=RiskTier.LIMITED,
        project_path=str(tmp_path),
    )
    assert Art53_55Analyzer().analyze(result) == []


def test_art53_55_applies_on_training_signal(tmp_path: Path) -> None:
    (tmp_path / "train.py").write_text(
        "from transformers import Trainer, TrainingArguments\n"
        "trainer = Trainer(model=model, args=TrainingArguments(output_dir='out'))\n"
        "trainer.train()\n"
    )
    result = _result(
        findings=[_finding("provider:local")],
        risk_tier=RiskTier.LIMITED,
        project_path=str(tmp_path),
    )
    gaps = Art53_55Analyzer().analyze(result)
    titles = {g.title for g in gaps}
    assert "Technical documentation of the model required" in titles
    assert "Downstream integrator documentation required" in titles
    # Systemic-risk requirement only appears when the project's own docs claim it.
    assert "Systemic-risk model evaluation and incident tracking required" not in titles


def test_art53_55_applies_on_self_declared_gpai_provider(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("We are a general-purpose AI model provider.\n")
    result = _result(
        findings=[],
        risk_tier=RiskTier.LIMITED,
        project_path=str(tmp_path),
    )
    assert Art53_55Analyzer().analyze(result) != []


def test_art53_55_systemic_risk_requirement_gated_on_self_declaration(tmp_path: Path) -> None:
    (tmp_path / "train.py").write_text("trainer = Trainer(model=model)\ntrainer.train()\n")
    (tmp_path / "README.md").write_text(
        "This model has been classified as carrying systemic risk under Art. 51.\n"
    )
    result = _result(findings=[], risk_tier=RiskTier.LIMITED, project_path=str(tmp_path))
    gaps = Art53_55Analyzer().analyze(result)
    assert any(
        g.title == "Systemic-risk model evaluation and incident tracking required" for g in gaps
    )


def test_art53_55_met_with_real_artifacts(tmp_path: Path) -> None:
    (tmp_path / "train.py").write_text("from transformers import Trainer\n")
    (tmp_path / "MODEL_CARD.md").write_text(
        "# Model Card\n\nIntended use, limitations, and training data sources "
        "are documented here in detail for downstream integrators.\n"
    )
    result = _result(findings=[], risk_tier=RiskTier.LIMITED, project_path=str(tmp_path))
    gaps = Art53_55Analyzer().analyze(result)
    titles = {g.title for g in gaps}
    assert "Downstream integrator documentation required" not in titles


# --- gap analyzer orchestration -------------------------------------------------------


def test_all_articles_loaded() -> None:
    analyzer = GapAnalyzer()
    assert len(analyzer.analyzers) == len(ALL_ARTICLE_ANALYZERS) == 17
    numbers = {a.article_number for a in analyzer.analyzers}
    assert numbers == {5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 24, 26, 27, 43, 50, 53}


def test_gaps_sorted_most_severe_first() -> None:
    gaps = GapAnalyzer().analyze(_result(risk_tier=RiskTier.HIGH))
    ranks = ["critical", "high", "warning", "info"]
    positions = [ranks.index(g.severity.value) for g in gaps]
    assert positions == sorted(positions)


def test_coverage_covers_every_article() -> None:
    coverage = GapAnalyzer().coverage(_result(risk_tier=RiskTier.LIMITED))
    assert len(coverage) == 17
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
    assert "Not assessed" in report  # e.g. Art. 6 at non-high tier (heuristic gate)


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


# --- false-MET regression guards (empty artifacts / inferred logging) --------

_AI = [_finding("provider:openai", detector="providers")]


def test_art11_empty_technical_doc_does_not_satisfy(tmp_path: Path) -> None:
    # `touch TECHNICAL_DOC.md` must NOT mark the (CRITICAL at high-risk)
    # technical-documentation obligation met.
    (tmp_path / "TECHNICAL_DOC.md").write_text("")
    result = _result(findings=_AI, risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art11Analyzer().analyze(result)
    assert any(g.title.startswith("Technical documentation") for g in gaps)


def test_art11_substantive_technical_doc_satisfies(tmp_path: Path) -> None:
    (tmp_path / "TECHNICAL_DOC.md").write_text(
        "# Technical documentation\n\n"
        "Intended purpose, model architecture, training data, and known "
        "limitations are described here per Annex IV of the EU AI Act.\n"
    )
    result = _result(findings=_AI, risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art11Analyzer().analyze(result)
    assert not any(g.title.startswith("Technical documentation") for g in gaps)


def test_art16_empty_files_and_stray_logger_do_not_satisfy(tmp_path: Path) -> None:
    # The exact reported failure: a high-risk provider must not clear provider
    # obligations by creating empty files. With no missing-logging signal AND
    # empty docs, NO Art. 16 requirement may be met and coverage must not read "met".
    for name in ("docs/quality.md", "docs/technical.md", "docs/post-market.md", "docs/incident.md"):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
    result = _result(findings=_AI, risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    analyzer = Art16Analyzer()
    reqs = analyzer.requirements(result, ProjectProbe(str(tmp_path)))
    assert all(not r.met for r in reqs)
    assert analyzer.coverage(result).status != "met"


def test_art12_logging_never_confirmed_met(tmp_path: Path) -> None:
    # "No missing-logging signal" is the absence of a negative, not proof of an
    # event log. Art. 12 must never be reported met on that basis — at best it is
    # UNVERIFIED (a gap the user must verify), and MISSING when logging is absent.
    with_logging = _result(findings=_AI, risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art12Analyzer().analyze(with_logging)
    logging_gaps = [g for g in gaps if g.title.startswith("Automated logging")]
    assert logging_gaps and logging_gaps[0].status == "unverified"

    missing = _result(
        findings=[*_AI, _finding("pattern:missing-logging", detector="patterns")],
        risk_tier=RiskTier.HIGH,
        project_path=str(tmp_path),
    )
    missing_gaps = [g for g in Art12Analyzer().analyze(missing) if g.title.startswith("Automated")]
    assert missing_gaps and missing_gaps[0].status == "missing"


def test_art10_empty_data_docs_do_not_satisfy(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "data.md").write_text("")
    result = _result(findings=_AI, risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art10Analyzer().analyze(result)
    assert any(g.title.startswith("Dataset governance") for g in gaps)


def test_art10_substantive_data_governance_satisfies(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "data-governance.md").write_text(
        "# Data governance\n\n"
        "Dataset provenance, collection method, and bias examination are "
        "documented for the training, validation, and testing datasets.\n"
    )
    result = _result(findings=_AI, risk_tier=RiskTier.HIGH, project_path=str(tmp_path))
    gaps = Art10Analyzer().analyze(result)
    assert not any(g.title.startswith("Dataset governance") for g in gaps)
