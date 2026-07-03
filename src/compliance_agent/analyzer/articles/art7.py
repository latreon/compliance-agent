"""Article 7 (with Art. 43/49) — Conformity assessment and EU database registration."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art7Analyzer(ArticleAnalyzer):
    article_number = 7
    article_title = "Conformity assessment"

    def applies(self, scan_result: ScanResult) -> bool:
        return is_high_risk(scan_result)

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        has_assessment = probe.any_file("docs/conformity*", "CONFORMITY*") or probe.docs_mention(
            "conformity assessment"
        )
        has_registration = probe.docs_mention("eu database")
        return [
            Requirement(
                name="Conformity assessment required for high-risk systems",
                met=has_assessment,
                severity=Severity.CRITICAL,
                details=(
                    "High-risk AI systems must undergo conformity assessment "
                    "before market placement."
                ),
                suggestion=(
                    "Conduct a conformity assessment before deployment and record "
                    "it in docs/conformity-assessment.md"
                ),
            ),
            Requirement(
                name="EU database registration required",
                met=has_registration,
                severity=Severity.HIGH,
                details="High-risk systems must be registered in the EU database (Art. 49).",
                suggestion="Register the AI system in the EU database after conformity assessment",
            ),
        ]
