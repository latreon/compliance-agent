"""Compliance gap analyzer: derives missing obligations from scan + risk tier."""

from compliance_agent.models.findings import (
    ComplianceGap,
    RiskAssessment,
    RiskTier,
    ScanResult,
    Severity,
)


class GapAnalyzer:
    """Identifies compliance gaps based on findings and the assigned risk tier."""

    def analyze(self, scan_result: ScanResult, assessment: RiskAssessment) -> list[ComplianceGap]:
        """Return gaps ordered by severity (most severe first)."""
        gaps: list[ComplianceGap] = []
        findings = scan_result.findings

        has_provider = any(f.category.startswith("provider:") for f in findings)
        has_agents = any(f.category.startswith("agent:") for f in findings)
        has_missing_logging = any(f.category == "pattern:missing-logging" for f in findings)
        has_user_interaction = any(
            f.category in ("pattern:user-input", "pattern:chat-interface") for f in findings
        )

        if not has_provider:
            return gaps

        if has_missing_logging:
            gaps.append(
                ComplianceGap(
                    id="gap:record-keeping",
                    title="Missing record-keeping for AI calls",
                    article="Art. 12",
                    severity=Severity.HIGH
                    if assessment.tier == RiskTier.HIGH
                    else Severity.WARNING,
                    description=(
                        "AI provider calls found without logging. The EU AI Act requires "
                        "automatic recording of events for high-risk systems."
                    ),
                    recommendation="Add structured logging around all model invocations.",
                )
            )

        if has_user_interaction:
            gaps.append(
                ComplianceGap(
                    id="gap:transparency",
                    title="AI interaction transparency not verified",
                    article="Art. 50",
                    severity=Severity.WARNING,
                    description=(
                        "Users appear to interact with AI output. They must be informed "
                        "they are interacting with an AI system."
                    ),
                    recommendation=("Add a clear AI disclosure notice in the user interface."),
                )
            )

        if has_agents:
            gaps.append(
                ComplianceGap(
                    id="gap:human-oversight",
                    title="Human oversight for autonomous agents not verified",
                    article="Art. 14",
                    severity=Severity.HIGH
                    if assessment.tier == RiskTier.HIGH
                    else Severity.WARNING,
                    description=(
                        "Agentic patterns (tool calls, MCP, multi-agent) detected. "
                        "Autonomous actions require effective human oversight."
                    ),
                    recommendation=(
                        "Implement approval gates, audit logs, and interruption controls "
                        "for agent tool execution."
                    ),
                )
            )

        if assessment.tier == RiskTier.HIGH:
            gaps.append(
                ComplianceGap(
                    id="gap:risk-management",
                    title="Risk management system required",
                    article="Art. 9",
                    severity=Severity.CRITICAL,
                    description=(
                        "The project matches Annex III high-risk categories: "
                        f"{', '.join(assessment.matched_categories) or 'unspecified'}. "
                        "A documented risk management system is mandatory."
                    ),
                    recommendation=(
                        "Establish a risk management process, technical documentation "
                        "(Art. 11), and conformity assessment before deployment."
                    ),
                )
            )

        severity_rank = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.WARNING: 2,
            Severity.INFO: 3,
        }
        return sorted(gaps, key=lambda g: severity_rank[g.severity])
