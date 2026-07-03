"""Article 12 — Record-keeping (automatic event logging)."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    has_ai,
    has_missing_logging,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art12Analyzer(ArticleAnalyzer):
    article_number = 12
    article_title = "Record-keeping"

    def applies(self, scan_result: ScanResult) -> bool:
        return has_ai(scan_result)

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return "no AI usage detected"

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        logging_ok = not has_missing_logging(scan_result)
        severity = Severity.HIGH if is_high_risk(scan_result) else Severity.WARNING
        return [
            Requirement(
                name="Automated logging of AI events required",
                met=logging_ok,
                severity=severity,
                details=(
                    "AI provider calls were found without logging. The EU AI Act "
                    "requires automatic recording of events for traceability."
                ),
                suggestion=(
                    "Wrap model calls with the Art. 12 logger "
                    "(templates/art12/event_logging.py); keep logs 6+ months"
                ),
            ),
        ]
