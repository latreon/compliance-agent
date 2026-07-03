"""Article 10 — Data and data governance."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    has_data_processing,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art10Analyzer(ArticleAnalyzer):
    article_number = 10
    article_title = "Data and data governance"

    def applies(self, scan_result: ScanResult) -> bool:
        return has_data_processing(scan_result) or is_high_risk(scan_result)

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return "no data processing detected"

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        has_cards = probe.any_file("dataset_cards/*", "docs/data*") or probe.docs_mention(
            "dataset card", "data governance"
        )
        severity = Severity.HIGH if is_high_risk(scan_result) else Severity.WARNING
        return [
            Requirement(
                name="Dataset governance must be documented",
                met=has_cards,
                severity=severity,
                details=(
                    "Data pipelines feed the AI system. Training, validation, and "
                    "testing data need documented provenance and bias examination."
                ),
                suggestion=(
                    "Create dataset cards (templates/art10/data_governance.py) for each dataset"
                ),
            ),
        ]
