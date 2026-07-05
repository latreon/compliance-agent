"""Tests for RiskClassifier and Annex III mapping."""

from datetime import datetime
from pathlib import Path

from compliance_agent.classifier.annex3 import load_categories
from compliance_agent.classifier.risk import RiskClassifier
from compliance_agent.models.findings import Finding, RiskTier, ScanResult, Severity
from compliance_agent.scanner.engine import ScannerEngine


def _make_result(findings: list[Finding]) -> ScanResult:
    return ScanResult(
        project_path="/fake",
        findings=findings,
        scan_time=datetime.now(),
        files_scanned=len({f.file_path for f in findings}),
    )


def _finding(category: str, file_path: str = "app.py", description: str = "") -> Finding:
    return Finding(
        id=f"test:{category}:{file_path}",
        file_path=file_path,
        detector="test",
        severity=Severity.INFO,
        category=category,
        message=category,
        description=description,
    )


def test_loads_all_eight_annex3_categories() -> None:
    categories = load_categories()
    assert len(categories) == 8
    assert {c.id for c in categories} >= {"biometric", "employment", "law-enforcement"}


def test_classifies_empty_scan_as_minimal() -> None:
    # Arrange
    classifier = RiskClassifier()

    # Act
    assessment = classifier.classify(_make_result([]))

    # Assert
    assert assessment.tier == RiskTier.MINIMAL
    # Not 1.0: detection is signature-based, so "no AI" is never a guarantee.
    assert assessment.confidence == 0.5
    assert any("not a guarantee" in r for r in assessment.reasoning)


def _framework_finding(category: str, file_path: str = "agent.py") -> Finding:
    return Finding(
        id=f"fw:{category}:{file_path}",
        file_path=file_path,
        detector="frameworks:langchain",
        severity=Severity.INFO,
        category=category,
        message=category,
        description="",
    )


def test_prohibited_biometric_matches_snake_case_identifier() -> None:
    # Regression: the only hyphenated prohibited keyword ("real-time remote
    # biometric identification", Art. 5(1)(h)) must match the snake_case form
    # that actually appears in Python code. It previously required a literal
    # hyphen and silently missed the single most severe practice.
    classifier = RiskClassifier()
    result = _make_result([_finding("provider:openai")])
    assessment = classifier.classify(
        result,
        project_text="def real_time_remote_biometric_identification(camera_feed): ...",
    )
    assert assessment.tier == RiskTier.UNACCEPTABLE


def test_framework_only_app_with_interaction_is_limited_not_minimal() -> None:
    # Regression: a LangChain/CrewAI app with no raw provider SDK import must not
    # collapse to MINIMAL. has_ai (provider OR framework) drives the tier.
    classifier = RiskClassifier()
    result = _make_result(
        [
            _framework_finding("langchain_agent", "agent.py"),
            _finding("pattern:chat-interface", file_path="ui.py"),
        ]
    )
    assessment = classifier.classify(result)
    assert assessment.tier == RiskTier.LIMITED


def test_framework_only_app_is_recognized_as_ai() -> None:
    classifier = RiskClassifier()
    result = _make_result([_framework_finding("langchain_chain", "chain.py")])
    assessment = classifier.classify(result)
    # AI was detected (framework), so this is not the "no AI" branch.
    assert assessment.tier == RiskTier.MINIMAL
    assert assessment.confidence == 0.6
    assert any("provider or framework" in r for r in assessment.reasoning)


def test_ai_usage_only_in_tests_does_not_drive_risk() -> None:
    # Regression: a mocked `from openai import OpenAI` in tests/ is a standard
    # pattern and must not classify a no-AI project as an AI system.
    classifier = RiskClassifier()
    result = _make_result([_finding("provider:openai", file_path="tests/test_chat_mock.py")])
    assessment = classifier.classify(result)
    assert assessment.tier == RiskTier.MINIMAL
    assert assessment.confidence == 0.5  # the "no production AI" branch


def test_classifies_recruitment_project_as_high_risk(hiring_project: Path) -> None:
    # Arrange
    result = ScannerEngine(hiring_project).scan()
    classifier = RiskClassifier()

    # Act
    assessment = classifier.classify(result)

    # Assert
    assert assessment.tier == RiskTier.HIGH
    assert "employment" in assessment.matched_categories
    assert assessment.reasoning


def test_classifies_chat_app_as_limited_risk() -> None:
    # Arrange
    findings = [
        _finding("provider:openai"),
        _finding("pattern:chat-interface"),
    ]
    classifier = RiskClassifier()

    # Act
    assessment = classifier.classify(_make_result(findings))

    # Assert
    assert assessment.tier == RiskTier.LIMITED


def test_classifies_backend_ai_without_ui_as_minimal() -> None:
    # Arrange
    findings = [_finding("provider:openai")]
    classifier = RiskClassifier()

    # Act
    assessment = classifier.classify(_make_result(findings))

    # Assert
    assert assessment.tier == RiskTier.MINIMAL


def test_migrations_directory_does_not_trigger_high_risk() -> None:
    # Regression: "migration"/"migrations" in a path (Django/Alembic/etc.) must
    # not be misread as Annex III migration/border-control high-risk.
    findings = [
        _finding("provider:openai", file_path="data_migration/handler.py"),
        _finding("pattern:chat-interface", file_path="db/migrations/0001_init.py"),
    ]
    assessment = RiskClassifier().classify(_make_result(findings))
    assert assessment.tier != RiskTier.HIGH
    assert "migration" not in assessment.matched_categories


def test_risk_score_variable_does_not_trigger_high_risk() -> None:
    # Regression: a generic "risk_score" identifier must not imply essential
    # services / credit-scoring high-risk.
    findings = [
        _finding(
            "provider:openai",
            file_path="scoring/model.py",
            description="compute a risk_score for each request",
        )
    ]
    assessment = RiskClassifier().classify(_make_result(findings))
    assert assessment.tier != RiskTier.HIGH


def test_specific_credit_scoring_still_triggers_high_risk() -> None:
    # The specific multi-word phrase must still classify as high-risk.
    findings = [
        _finding(
            "provider:openai",
            file_path="credit_scoring/model.py",
            description="loan approval via creditworthiness assessment",
        )
    ]
    assessment = RiskClassifier().classify(_make_result(findings))
    assert assessment.tier == RiskTier.HIGH
    assert "essential-services" in assessment.matched_categories


def test_prohibited_practice_classified_unacceptable() -> None:
    # A likely Art. 5 prohibited practice outranks every other tier.
    findings = [
        _finding(
            "provider:openai",
            file_path="scoring/social_scoring.py",
            description="assign a social credit score to each citizen",
        )
    ]
    assessment = RiskClassifier().classify(_make_result(findings))
    assert assessment.tier == RiskTier.UNACCEPTABLE
    assert "social-scoring" in assessment.matched_categories
    assert assessment.confidence >= 0.5


def test_bare_biometric_categorisation_is_high_risk_not_prohibited() -> None:
    # Regression: Art. 5(1)(g) bans only categorisation that INFERS sensitive
    # attributes. Bare "biometric categorisation" is a high-risk practice
    # (Annex III(1)), not a prohibited one — classifying it UNACCEPTABLE wrongly
    # tells a lawful high-risk product it "cannot be deployed".
    findings = [
        _finding(
            "provider:openai",
            file_path="vision/model.py",
            description="biometric categorisation of faces into age groups",
        )
    ]
    assessment = RiskClassifier().classify(_make_result(findings))
    assert assessment.tier == RiskTier.HIGH
    assert "biometric" in assessment.matched_categories


def test_sensitive_attribute_inference_still_prohibited() -> None:
    # The genuinely banned variant — inferring a sensitive attribute — must stay
    # UNACCEPTABLE.
    findings = [
        _finding(
            "provider:openai",
            file_path="vision/model.py",
            description="biometric system to infer sexual orientation from photos",
        )
    ]
    assessment = RiskClassifier().classify(_make_result(findings))
    assert assessment.tier == RiskTier.UNACCEPTABLE


def test_bare_predictive_policing_is_high_risk_not_prohibited() -> None:
    # Regression: Art. 5(1)(d) bans only predicting a natural person's risk of
    # committing a crime SOLELY on profiling. Bare "predictive policing" (e.g.
    # place-based) is high-risk (Annex III(6)), not prohibited.
    findings = [
        _finding(
            "provider:openai",
            file_path="le/model.py",
            description="predictive policing hotspot map for patrol allocation",
        )
    ]
    assessment = RiskClassifier().classify(_make_result(findings))
    assert assessment.tier == RiskTier.HIGH
    assert "law-enforcement" in assessment.matched_categories


def test_profiling_crime_prediction_still_prohibited() -> None:
    findings = [
        _finding(
            "provider:openai",
            file_path="le/model.py",
            description="crime prediction profiling to predict criminal offence by a person",
        )
    ]
    assessment = RiskClassifier().classify(_make_result(findings))
    assert assessment.tier == RiskTier.UNACCEPTABLE


def test_generic_student_word_does_not_trigger_high_risk() -> None:
    # Regression: a bare "student" identifier must not imply Annex III education
    # high-risk (keywords are specific multi-word phrases now).
    findings = [
        _finding(
            "provider:openai",
            file_path="app.py",
            description="greet each student by name in the chat welcome message",
        )
    ]
    assessment = RiskClassifier().classify(_make_result(findings))
    assert assessment.tier != RiskTier.HIGH


def test_high_risk_confidence_never_below_floor() -> None:
    # A single Annex III hit must not report HIGH at an implausible 0.25.
    findings = [
        _finding(
            "provider:openai",
            file_path="app.py",
            description="loan approval decisioning",
        )
    ]
    assessment = RiskClassifier().classify(_make_result(findings))
    assert assessment.tier == RiskTier.HIGH
    assert assessment.confidence >= 0.5


def test_content_classification_catches_neutral_filename(tmp_path: Path) -> None:
    # The domain lives in the CODE, not the file name: an AI hiring tool in a
    # plainly-named app.py must still classify HIGH via content matching.
    (tmp_path / "app.py").write_text(
        "import openai\n\n"
        "def run(text: str) -> str:\n"
        "    # resume screening for recruitment: rank each job applicant\n"
        "    client = openai.OpenAI()\n"
        "    return client.chat.completions.create(model='gpt-4o', messages=[]).id\n"
    )
    engine = ScannerEngine(tmp_path)
    result = engine.scan()
    assessment = RiskClassifier().classify(result, project_text=engine.domain_corpus)
    assert assessment.tier == RiskTier.HIGH
    assert "employment" in assessment.matched_categories


def test_domain_keywords_without_ai_stay_minimal(tmp_path: Path) -> None:
    # A project that merely NAMES high-risk domains but uses no AI must not be
    # flagged — the AI Act governs AI systems. This also stops the scanner from
    # classifying its own rule files (which list these phrases) as high-risk.
    (tmp_path / "rules.py").write_text(
        "PROHIBITED = ['social scoring', 'predictive policing', 'resume screening']\n"
        "def check(text):\n    return any(p in text for p in PROHIBITED)\n"
    )
    engine = ScannerEngine(tmp_path)
    result = engine.scan()
    assessment = RiskClassifier().classify(result, project_text=engine.domain_corpus)
    assert assessment.tier == RiskTier.MINIMAL


def test_test_fixture_path_does_not_drive_high_risk(tmp_path: Path) -> None:
    # Regression: a descriptively-named test fixture (tests/recruitment.py) is
    # sample data, not the deployed system. It must not push the project to a
    # false HIGH tier via the classifier's finding-text corpus.
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "recruitment.py").write_text("import openai\n")
    (tmp_path / "app.py").write_text("import openai\n\nclient = openai.OpenAI()\n")
    engine = ScannerEngine(tmp_path)
    result = engine.scan()
    assessment = RiskClassifier().classify(result, project_text=engine.domain_corpus)
    assert assessment.tier != RiskTier.HIGH
    assert "employment" not in assessment.matched_categories


def test_limited_and_minimal_tiers_carry_domain_caveat() -> None:
    # A low tier must never read as "safe": every LIMITED/MINIMAL result carries
    # a caveat that keyword-based domain detection can miss high-risk uses.
    classifier = RiskClassifier()
    limited = classifier.classify(
        _make_result([_finding("provider:openai"), _finding("pattern:chat-interface")])
    )
    minimal = classifier.classify(_make_result([_finding("provider:openai")]))
    assert any("annex iii" in r.lower() for r in limited.reasoning)
    assert any("annex iii" in r.lower() for r in minimal.reasoning)


def test_high_risk_confidence_scales_with_keyword_hits() -> None:
    # Arrange
    findings = [
        _finding(
            "provider:openai",
            file_path="biometric/face_recognition.py",
            description="fingerprint and iris_scan matching for biometric identification",
        )
    ]
    classifier = RiskClassifier()

    # Act
    assessment = classifier.classify(_make_result(findings))

    # Assert
    assert assessment.tier == RiskTier.HIGH
    assert assessment.confidence > 0.25
