"""Article 9 — Risk management system."""

from compliance_agent.analyzer.articles.base import (
    MIN_ARTIFACT_CHARS,
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art9Analyzer(ArticleAnalyzer):
    article_number = 9
    article_title = "Risk management system"

    def applies(self, scan_result: ScanResult) -> bool:
        return is_high_risk(scan_result)

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        return [
            Requirement(
                name="Risk management system required",
                status=evidence(
                    # Require real content: an empty placeholder (e.g. a touched
                    # risk_register.json) must not satisfy a mandatory control.
                    mechanism=probe.any_file(
                        "risk_register.json", "docs/risk*", min_content_chars=MIN_ARTIFACT_CHARS
                    ),
                    mention=probe.docs_mention("risk management"),
                ),
                severity=Severity.CRITICAL,
                details=(
                    "The project matches high-risk criteria. A documented, "
                    "continuously maintained risk management system is mandatory."
                ),
                suggestion=(
                    "Establish a risk register (templates/art9/risk_management.py) "
                    "and review it every release"
                ),
            ),
        ]
