"""The full analysis pipeline: scan -> classify -> gaps + coverage (+ fixes).

Shared by the CLI commands and the web dashboard so every surface produces
identical results for the same project.
"""

from collections.abc import Sequence
from pathlib import Path

from compliance_agent.analyzer.gaps import GapAnalyzer
from compliance_agent.classifier.risk import RiskClassifier
from compliance_agent.models.findings import ScanResult
from compliance_agent.recommender.engine import FixRecommender
from compliance_agent.scanner.engine import ScannerEngine


def run_pipeline(
    project_path: Path,
    *,
    exclude: Sequence[str] = (),
    include: Sequence[str] = (),
    with_recommendations: bool = False,
) -> ScanResult:
    """Run the complete pipeline on a project directory."""
    engine = ScannerEngine(project_path, exclude=list(exclude), include=list(include))
    result = engine.scan()
    assessment = RiskClassifier().classify(result, project_text=engine.domain_corpus)
    result = result.model_copy(update={"risk_tier": assessment.tier, "risk_assessment": assessment})
    analyzer = GapAnalyzer()
    result = result.model_copy(
        update={"gaps": analyzer.analyze(result), "coverage": analyzer.coverage(result)}
    )
    if with_recommendations:
        result = result.model_copy(update={"recommendations": FixRecommender().recommend(result)})
    return result
