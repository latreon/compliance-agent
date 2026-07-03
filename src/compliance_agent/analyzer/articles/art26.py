"""Article 26 (with Art. 16/17/72/73) — Provider obligations for high-risk systems."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    has_missing_logging,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art26Analyzer(ArticleAnalyzer):
    article_number = 26
    article_title = "Obligations of providers of high-risk AI systems"

    def applies(self, scan_result: ScanResult) -> bool:
        return is_high_risk(scan_result)

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        return [
            Requirement(
                name="Quality management system required",
                met=probe.any_file("docs/quality*") or probe.docs_mention("quality management"),
                severity=Severity.CRITICAL,
                details="Providers must implement a quality management system (Art. 17).",
                suggestion=(
                    "Establish quality management processes documented in "
                    "docs/quality-management.md"
                ),
            ),
            Requirement(
                name="Technical documentation required",
                met=probe.any_file("TECHNICAL_DOC.md", "docs/technical*")
                or probe.docs_mention("technical documentation"),
                severity=Severity.CRITICAL,
                details="Providers must draw up technical documentation (Art. 11).",
                suggestion=(
                    "Generate documentation with templates/art11/technical_documentation.py"
                ),
            ),
            Requirement(
                name="Automated logging system required",
                met=not has_missing_logging(scan_result),
                severity=Severity.CRITICAL,
                details="Providers must enable automatic recording of events (Art. 12).",
                suggestion="Implement event logging (templates/art12/event_logging.py)",
            ),
            Requirement(
                name="Post-market monitoring plan required",
                met=probe.any_file("docs/post-market*") or probe.docs_mention("post-market"),
                severity=Severity.HIGH,
                details="Providers must establish post-market monitoring (Art. 72).",
                suggestion="Create a post-market monitoring plan and procedures",
            ),
            Requirement(
                name="Incident reporting procedure required",
                met=probe.any_file("docs/incident*") or probe.docs_mention("incident report"),
                severity=Severity.HIGH,
                details=(
                    "Serious incidents must be reported to market surveillance "
                    "authorities (Art. 73)."
                ),
                suggestion="Establish incident reporting procedures and contacts",
            ),
        ]
