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
    assert assessment.confidence == 1.0


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
