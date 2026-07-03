"""Article 6 — Classification rules for high-risk AI systems."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art6Analyzer(ArticleAnalyzer):
    article_number = 6
    article_title = "High-risk AI systems"

    def applies(self, scan_result: ScanResult) -> bool:
        return is_high_risk(scan_result)

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        has_purpose = probe.docs_mention("intended purpose") or probe.any_file(
            "docs/intended-purpose.md"
        )
        has_annex3 = bool(
            scan_result.risk_assessment and scan_result.risk_assessment.matched_categories
        ) or probe.docs_mention("annex iii")
        return [
            Requirement(
                name="Intended purpose must be documented",
                met=has_purpose,
                severity=Severity.CRITICAL,
                details=(
                    "High-risk AI systems require a documented intended purpose "
                    "per Art. 6(1) — classification depends on it."
                ),
                suggestion=(
                    "Document the intended purpose in the project README or "
                    "docs/intended-purpose.md"
                ),
            ),
            Requirement(
                name="Annex III category must be identified",
                met=has_annex3,
                severity=Severity.HIGH,
                details="The applicable Annex III category must be specified.",
                suggestion="Add the Annex III category classification to your documentation",
            ),
        ]
