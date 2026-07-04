"""Article 16 (with Art. 17/11/12/72/73) — Obligations of providers of high-risk systems.

Note: provider obligations for high-risk AI systems are set out in Article 16
(quality management is Art. 17, technical documentation Art. 11, record-keeping
Art. 12, post-market monitoring Art. 72, incident reporting Art. 73). Article 26
concerns *deployer* obligations, which are distinct.
"""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
    has_missing_logging,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art16Analyzer(ArticleAnalyzer):
    article_number = 16
    article_title = "Obligations of providers of high-risk AI systems"

    def applies(self, scan_result: ScanResult) -> bool:
        return is_high_risk(scan_result)

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        return [
            Requirement(
                name="Quality management system required",
                status=evidence(
                    mechanism=probe.any_file("docs/quality*"),
                    mention=probe.docs_mention("quality management"),
                ),
                severity=Severity.CRITICAL,
                details="Providers must implement a quality management system (Art. 17).",
                suggestion=(
                    "Establish quality management processes documented in "
                    "docs/quality-management.md"
                ),
            ),
            Requirement(
                name="Technical documentation required",
                status=evidence(
                    mechanism=probe.any_file("TECHNICAL_DOC.md", "docs/technical*"),
                    mention=probe.docs_mention("technical documentation"),
                ),
                severity=Severity.CRITICAL,
                details="Providers must draw up technical documentation (Art. 11).",
                suggestion=(
                    "Generate documentation with templates/art11/technical_documentation.py"
                ),
            ),
            Requirement(
                name="Automated logging system required",
                status=evidence(mechanism=not has_missing_logging(scan_result)),
                severity=Severity.CRITICAL,
                details="Providers must enable automatic recording of events (Art. 12).",
                suggestion="Implement event logging (templates/art12/event_logging.py)",
            ),
            Requirement(
                name="Post-market monitoring plan required",
                status=evidence(
                    mechanism=probe.any_file("docs/post-market*"),
                    mention=probe.docs_mention("post-market"),
                ),
                severity=Severity.HIGH,
                details="Providers must establish post-market monitoring (Art. 72).",
                suggestion="Create a post-market monitoring plan and procedures",
            ),
            Requirement(
                name="Incident reporting procedure required",
                status=evidence(
                    mechanism=probe.any_file("docs/incident*"),
                    mention=probe.docs_mention("incident report"),
                ),
                severity=Severity.HIGH,
                details=(
                    "Serious incidents must be reported to market surveillance "
                    "authorities (Art. 73)."
                ),
                suggestion="Establish incident reporting procedures and contacts",
            ),
        ]
