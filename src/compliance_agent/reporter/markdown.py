"""Markdown report rendering: summary first, findings grouped by file."""

from collections import Counter
from itertools import groupby

from compliance_agent.models.findings import ScanResult, Severity

SEVERITY_ICONS = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.WARNING: "🟡",
    Severity.INFO: "🔵",
}

PROVIDER_LABELS = {
    "provider:openai": "OpenAI",
    "provider:anthropic": "Anthropic",
    "provider:google": "Google Generative AI",
    "provider:mistral": "Mistral AI",
    "provider:local": "Local model stack",
}


def detected_providers(scan_result: ScanResult) -> list[str]:
    """Human-readable labels of AI providers found in the scan."""
    categories = {f.category for f in scan_result.findings}
    return [label for cat, label in PROVIDER_LABELS.items() if cat in categories]


def render_summary(scan_result: ScanResult) -> str:
    """Render just the high-level scan summary."""
    counts = Counter(f.severity for f in scan_result.findings)
    severity_summary = (
        ", ".join(
            f"{counts[sev]} {sev.value}"
            for sev in (Severity.CRITICAL, Severity.HIGH, Severity.WARNING, Severity.INFO)
            if counts.get(sev)
        )
        or "none"
    )
    providers = detected_providers(scan_result)
    providers_text = f"{len(providers)} ({', '.join(providers)})" if providers else "none"
    tier_text = scan_result.risk_tier.value.upper() if scan_result.risk_tier else "n/a"

    lines = [
        "## Scan Summary",
        "",
        f"- **Files scanned:** {scan_result.files_scanned}",
        f"- **AI providers detected:** {providers_text}",
        f"- **Risk tier:** **{tier_text}**",
        f"- **Findings:** {severity_summary}",
        "",
    ]
    return "\n".join(lines)


def render_recommendations(scan_result: ScanResult) -> str:
    """Render the fix recommendations section."""
    if not scan_result.recommendations:
        return ""
    lines = ["## Recommendations", ""]
    for idx, rec in enumerate(scan_result.recommendations, start=1):
        lines.append(f"### {idx}. {rec.title} ({rec.article})")
        lines.append("")
        lines.append(rec.description)
        lines.append("")
        lines.append(f"**Template:** `templates/{rec.template_path}`")
        if rec.extra_templates:
            extras = ", ".join(f"`templates/{path}`" for path in rec.extra_templates)
            lines.append(f"**Also relevant:** {extras}")
        lines.append("")
        lines.append("**Steps:**")
        for step in rec.steps:
            lines.append(f"1. {step}")
        lines.append("")
    return "\n".join(lines)


def render_markdown(scan_result: ScanResult) -> str:
    """Render the full scan result as a Markdown report."""
    lines: list[str] = []
    lines.append("# EU AI Act Compliance Report")
    lines.append("")
    lines.append(f"- **Project:** `{scan_result.project_path}`")
    lines.append(f"- **Scanned:** {scan_result.scan_time.isoformat(timespec='seconds')}")
    lines.append("")
    lines.append(render_summary(scan_result))

    if scan_result.risk_assessment:
        lines.append("## Risk Assessment")
        lines.append("")
        lines.append(f"Confidence: {scan_result.risk_assessment.confidence:.0%}")
        lines.append("")
        for reason in scan_result.risk_assessment.reasoning:
            lines.append(f"- {reason}")
        lines.append("")

    if scan_result.gaps:
        lines.append("## Compliance Gaps")
        lines.append("")
        for gap in scan_result.gaps:
            icon = SEVERITY_ICONS[gap.severity]
            lines.append(f"### {icon} {gap.title} ({gap.article})")
            lines.append("")
            lines.append(gap.description)
            lines.append("")
            lines.append(f"**Recommendation:** {gap.recommendation}")
            lines.append("")

    recommendations_section = render_recommendations(scan_result)

    lines.append("## Findings")
    lines.append("")
    if not scan_result.findings:
        lines.append("No AI usage patterns detected.")
        lines.append("")
        if recommendations_section:
            lines.append(recommendations_section)
        return "\n".join(lines)

    ordered = sorted(scan_result.findings, key=lambda f: (f.file_path, f.line_number or 0))
    for file_path, file_findings in groupby(ordered, key=lambda f: f.file_path):
        lines.append(f"### `{file_path}`")
        lines.append("")
        for finding in file_findings:
            icon = SEVERITY_ICONS[finding.severity]
            location = f"line {finding.line_number}" if finding.line_number else "file-level"
            repeat = f", ×{finding.occurrences}" if finding.occurrences > 1 else ""
            lines.append(
                f"- {icon} **{finding.severity.value}** `{finding.category}` "
                f"({location}{repeat}): {finding.message}"
            )
        lines.append("")

    if recommendations_section:
        lines.append(recommendations_section)

    return "\n".join(lines)
