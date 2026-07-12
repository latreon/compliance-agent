"""The full analysis pipeline: scan -> classify -> gaps + coverage (+ fixes).

Shared by the CLI commands and the web dashboard so every surface produces
identical results for the same project.
"""

from collections.abc import Sequence
from pathlib import Path

from compliance_agent.analyzer.gaps import GapAnalyzer
from compliance_agent.classifier.risk import RiskClassifier
from compliance_agent.models.findings import TIER_ORDER, RiskAssessment, RiskTier, ScanResult
from compliance_agent.recommender.engine import FixRecommender
from compliance_agent.scanner.engine import ScannerEngine


def apply_declared_tier(assessment: RiskAssessment, declared: RiskTier) -> RiskAssessment:
    """Fold a tier declared in compliance.yaml into the heuristic assessment.

    A declaration can only RAISE the tier. Lowering is refused by design: if a
    config file could talk the scanner down from HIGH to MINIMAL, the file
    itself would become a false-assurance mechanism — the exact failure mode
    this tool exists to prevent. Either way the reasoning records what the
    config said, so the report stays auditable.
    """
    if TIER_ORDER[declared] > TIER_ORDER[assessment.tier]:
        return assessment.model_copy(
            update={
                "tier": declared,
                # The tier now comes from an explicit declaration, not a
                # keyword heuristic — full confidence in its origin.
                "confidence": 1.0,
                "reasoning": [
                    *assessment.reasoning,
                    f"Risk tier raised from {assessment.tier.value.upper()} to "
                    f"{declared.value.upper()}: declared in compliance.yaml "
                    "(posture.risk_tier).",
                ],
            }
        )
    if declared != assessment.tier:
        return assessment.model_copy(
            update={
                "reasoning": [
                    *assessment.reasoning,
                    f"compliance.yaml declares {declared.value.upper()}, but detection "
                    f"found {assessment.tier.value.upper()} — the higher tier applies "
                    "(a declaration can never lower the detected tier).",
                ]
            }
        )
    return assessment


def run_pipeline(
    project_path: Path,
    *,
    exclude: Sequence[str] = (),
    include: Sequence[str] = (),
    with_recommendations: bool = False,
    declared_tier: RiskTier | None = None,
) -> ScanResult:
    """Run the complete pipeline on a project directory."""
    engine = ScannerEngine(project_path, exclude=list(exclude), include=list(include))
    result = engine.scan()
    assessment = RiskClassifier().classify(result, project_text=engine.domain_corpus)
    if declared_tier is not None:
        assessment = apply_declared_tier(assessment, declared_tier)
    result = result.model_copy(update={"risk_tier": assessment.tier, "risk_assessment": assessment})
    analyzer = GapAnalyzer()
    result = result.model_copy(
        update={"gaps": analyzer.analyze(result), "coverage": analyzer.coverage(result)}
    )
    if with_recommendations:
        result = result.model_copy(update={"recommendations": FixRecommender().recommend(result)})
    return result
