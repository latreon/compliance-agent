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
                        # Specific oversight constructs only. The bare token
                        # "approval" matched ordinary business identifiers like
                        # ``process_loan_approval`` and silently cleared human
                        # oversight on fully autonomous high-risk agents.
                        "humanoversightcheckpoint",
                        "human_input_mode",
                        "human_in_the_loop",
                        "require_approval",
                        "requires_approval",
                        "approval_required",
                        "await_approval",
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
            Requirement(
                # Art. 14(4)(e) is broader than a pre-action approval gate: the
                # overseer must also be able to disregard, override, or reverse
                # an output the system has already produced, or stop the system
                # with a "stop" button or similar procedure — a distinct,
                # after-the-fact capability that an approval checkpoint alone
                # does not give.
                name="Ability to override or reverse AI system output required",
                status=evidence(
                    mechanism=probe.code_mentions(
                        "override_decision",
                        "reverse_decision",
                        "disregard_output",
                        "manual_override",
                        "kill_switch",
                        "emergency_stop",
                        "human_override",
                    ),
                    mention=probe.docs_mention(
                        "override the output",
                        "reverse the output",
                        "disregard the output",
                        "stop button",
                    ),
                ),
                severity=severity,
                details=(
                    "The human overseer must be able to decide not to use the "
                    "system, or to disregard, override, or reverse its output, "
                    "and to intervene or stop the system via a 'stop' button or "
                    "similar procedure (Art. 14(4)(d)-(e))."
                ),
                suggestion=(
                    "Add an override/reverse action and a stop mechanism "
                    "alongside your approval checkpoints"
                ),
            ),
        ]
