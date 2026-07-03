"""Markdown report rendering."""

from collections import Counter

from compliance_agent.models.findings import ScanResult, Severity

SEVERITY_ICONS = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.WARNING: "🟡",
    Severity.INFO: "🔵",
}


def render_markdown(scan_result: ScanResult) -> str:
    """Render the scan result as a Markdown report."""
    lines: list[str] = []
    lines.append("# EU AI Act Compliance Report")
    lines.append("")
    lines.append(f"- **Project:** `{scan_result.project_path}`")
    lines.append(f"- **Scanned:** {scan_result.scan_time.isoformat(timespec='seconds')}")
    lines.append(f"- **Files scanned:** {scan_result.files_scanned}")
    lines.append(f"- **Findings:** {len(scan_result.findings)}")
    if scan_result.risk_tier:
        lines.append(f"- **Risk tier:** **{scan_result.risk_tier.value.upper()}**")
    lines.append("")

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

    lines.append("## Findings")
    lines.append("")
    if not scan_result.findings:
        lines.append("No AI usage patterns detected.")
        lines.append("")
    else:
        counts = Counter(f.severity for f in scan_result.findings)
        summary = ", ".join(
            f"{counts[sev]} {sev.value}" for sev in Severity if counts.get(sev)
        )
        lines.append(f"Summary: {summary}")
        lines.append("")
        lines.append("| Severity | Category | File | Line | Message |")
        lines.append("|----------|----------|------|------|---------|")
        for finding in scan_result.findings:
            icon = SEVERITY_ICONS[finding.severity]
            line_no = str(finding.line_number) if finding.line_number else "—"
            lines.append(
                f"| {icon} {finding.severity.value} | {finding.category} "
                f"| `{finding.file_path}` | {line_no} | {finding.message} |"
            )
        lines.append("")

    return "\n".join(lines)
