"""Article 43 (with Art. 49) — Conformity assessment and EU database registration.

Note: conformity assessment for high-risk AI systems is governed by Article 43
(not Article 7, which concerns amendments to Annex III). EU database
registration is Article 49.
"""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art43Analyzer(ArticleAnalyzer):
    article_number = 43
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
                    "before market placement (Art. 43)."
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
