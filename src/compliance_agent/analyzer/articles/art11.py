"""Article 11 — Technical documentation."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
    has_ai,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art11Analyzer(ArticleAnalyzer):
    article_number = 11
    article_title = "Technical documentation"

    def applies(self, scan_result: ScanResult) -> bool:
        return has_ai(scan_result)

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return "no AI usage detected"

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        severity = Severity.CRITICAL if is_high_risk(scan_result) else Severity.WARNING
        return [
            Requirement(
                name="Technical documentation required",
                status=evidence(
                    mechanism=probe.any_file("TECHNICAL_DOC.md", "docs/technical*"),
                    mention=probe.docs_mention("technical documentation"),
                ),
                severity=severity,
                details=(
                    "The AI system's purpose, architecture, models, and limitations "
                    "must be described in technical documentation (Annex IV)."
                ),
                suggestion=(
                    "Generate TECHNICAL_DOC.md with templates/art11/technical_documentation.py"
                ),
            ),
        ]
