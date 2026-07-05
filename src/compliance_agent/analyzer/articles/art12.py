"""Article 12 — Record-keeping (automatic event logging)."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
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
        # "No missing-logging signal" is the *absence of a negative*, not proof
        # the AI events are recorded: a stray ``logger`` elsewhere in the module,
        # or a framework whose calls the pattern detector cannot AST-match,
        # suppresses the negative signal without any real event log. So it can
        # only downgrade to UNVERIFIED (verify manually), never confirm MET.
        logging_seen = not has_missing_logging(scan_result)
        severity = Severity.HIGH if is_high_risk(scan_result) else Severity.WARNING
        return [
            Requirement(
                name="Automated logging of AI events required",
                status=evidence(mechanism=False, mention=logging_seen),
                severity=severity,
                details=(
                    "Automatic logging of AI events (Art. 12) could not be "
                    "verified at the model call site. It is a statutory obligation "
                    "for high-risk systems and strongly recommended for all others."
                ),
                suggestion=(
                    "Wrap model calls with the Art. 12 logger "
                    "(templates/art12/event_logging.py); retain logs per Art. 19 "
                    "(providers) / Art. 26(6) (deployers) — at least 6 months"
                ),
            ),
        ]
