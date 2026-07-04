"""Article 5 — Prohibited AI practices.

Applies only when the risk classifier flagged the project as UNACCEPTABLE
(a prohibited-practice keyword matched). Prohibited practices cannot be
deployed at all, so this is always a critical, blocking gap.
"""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
)
from compliance_agent.models.findings import (
    RequirementStatus,
    RiskTier,
    ScanResult,
    Severity,
)


class Art5Analyzer(ArticleAnalyzer):
    article_number = 5
    article_title = "Prohibited AI practices"

    def applies(self, scan_result: ScanResult) -> bool:
        return scan_result.risk_tier == RiskTier.UNACCEPTABLE

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return "no prohibited AI practices detected"

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        matched = ", ".join(
            scan_result.risk_assessment.matched_categories if scan_result.risk_assessment else []
        )
        detail = (
            "The scan matched indicators of a practice prohibited under "
            "Article 5 of the EU AI Act"
            + (f" ({matched})" if matched else "")
            + ". Prohibited AI systems cannot be placed on the EU market or put "
            "into service under any conditions."
        )
        return [
            Requirement(
                # This obligation is never automatically "met" — a prohibited
                # practice must be removed, not documented around.
                name="Prohibited AI practice must be removed",
                status=RequirementStatus.MISSING,
                severity=Severity.CRITICAL,
                details=detail,
                suggestion=(
                    "Do not deploy this system. Remove the prohibited functionality "
                    "or obtain qualified legal review before proceeding."
                ),
            ),
        ]
