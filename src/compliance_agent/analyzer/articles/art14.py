"""Article 14 — Human oversight."""

from compliance_agent.analyzer.articles.base import (
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
    has_agents,
    is_high_risk,
)
from compliance_agent.models.findings import ScanResult, Severity


class Art14Analyzer(ArticleAnalyzer):
    article_number = 14
    article_title = "Human oversight"

    def applies(self, scan_result: ScanResult) -> bool:
        return has_agents(scan_result) or is_high_risk(scan_result)

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return "no autonomous agent patterns detected"

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        severity = Severity.HIGH if is_high_risk(scan_result) else Severity.WARNING
        return [
            Requirement(
                name="Human oversight mechanism required",
                status=evidence(
                    mechanism=probe.code_mentions(
                        "humanoversightcheckpoint",
                        "human_input_mode",
                        "require_approval",
                        "approval",
                    ),
                    mention=probe.docs_mention("human oversight"),
                ),
                severity=severity,
                details=(
                    "Agentic patterns (tool calls, multi-agent, autonomous "
                    "workflows) were detected without an oversight mechanism. "
                    "Autonomous actions require effective human oversight."
                ),
                suggestion=(
                    "Add approval checkpoints (templates/art14/human_oversight.py), "
                    "audit logs, and interruption controls"
                ),
            ),
        ]
