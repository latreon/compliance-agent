"""Markdown report rendering: summary first, findings grouped by file."""

import re
from collections import Counter
from itertools import groupby

from compliance_agent import DISCLAIMER
from compliance_agent.models.findings import ArticleCoverage, ScanResult, Severity

# C0 control characters (except tab/newline) carried in from a scanned repo.
# A raw ESC in a file path or message survives into the rendered Markdown and,
# when the report is later viewed in a terminal or converted, can inject ANSI
# control sequences. Strip them from every repo-derived value.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _plain(text: str) -> str:
    """Strip terminal control characters from repo-derived free text."""
    return _CONTROL_CHARS_RE.sub("", text)


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


def _md_code(text: str) -> str:
    """Neutralize a value for safe embedding in a Markdown inline code span.

    A backtick in a scanned-repo file path would close the span and leave the
    remainder as live Markdown/HTML — a stored-injection vector when the report
    is later rendered to HTML. Backticks are replaced and line breaks/pipes
    stripped so the value cannot break out of the span or a table cell.
    """
    neutralized = text.replace("`", "'").replace("\r", " ").replace("\n", " ").replace("|", r"\|")
    return _CONTROL_CHARS_RE.sub("", neutralized)


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
    ]
    if scan_result.frameworks_detected:
        names = ", ".join(fw.name for fw in scan_result.frameworks_detected)
        lines.append(f"- **Frameworks:** {names}")
    if scan_result.scan_errors:
        lines.append(
            f"- **⚠️ Incomplete scan:** {len(scan_result.scan_errors)} file(s) "
            "could not be fully analyzed; results may be missing findings."
        )
    lines.append("")
    lines.append(f"> _{DISCLAIMER}_")
    lines.append("")
    return "\n".join(lines)


def _coverage_status_text(entry: ArticleCoverage) -> str:
    if entry.status == "not_applicable":
        # "Not assessed", not "Not applicable": these articles were gated out by
        # heuristic detection, which is not a determination that the obligation
        # does not apply. See STATUS_LABELS in reporter/terminal.py.
        return f"Not assessed ({entry.reason})" if entry.reason else "Not assessed"
    label = {
        "met": "Met",
        "partial": "Partial",
        "unverified": "Unverified",
        "missing": "Missing",
    }[entry.status]
    return f"{label} — {entry.requirements_met}/{entry.requirements_total} requirements met"


def render_coverage(scan_result: ScanResult) -> str:
    """Render the per-article compliance coverage table."""
    if not scan_result.coverage:
        return ""
    lines = [
        "## Compliance Coverage",
        "",
        "| Article | Title | Status |",
        "|---------|-------|--------|",
    ]
    for entry in scan_result.coverage:
        lines.append(f"| {entry.article} | {entry.title} | {_coverage_status_text(entry)} |")
    lines.append("")
    return "\n".join(lines)


def render_frameworks(scan_result: ScanResult) -> str:
    """Render the frameworks-detected section."""
    if not scan_result.frameworks_detected:
        return ""
    lines = ["## Frameworks Detected", ""]
    for framework in scan_result.frameworks_detected:
        patterns = ", ".join(framework.patterns)
        lines.append(f"### {framework.name} ({patterns})")
        lines.append("")
        for note in framework.risk_notes:
            lines.append(f"- → {note}")
        lines.append("")
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
        for i, step in enumerate(rec.steps, start=1):
            lines.append(f"{i}. {_plain(step)}")
        lines.append("")
    return "\n".join(lines)


def render_markdown(scan_result: ScanResult, summary_source: ScanResult | None = None) -> str:
    """Render the full scan result as a Markdown report.

    ``summary_source`` supplies the true totals for the summary and the
    empty-findings message when ``scan_result`` is a ``--severity``-filtered
    view — so the summary never understates and an "everything filtered out"
    result is not reported as "No AI usage patterns detected".
    """
    src = summary_source or scan_result
    lines: list[str] = []
    lines.append("# EU AI Act Compliance Report")
    lines.append("")
    lines.append(f"- **Project:** `{_md_code(scan_result.project_path)}`")
    lines.append(f"- **Scanned:** {scan_result.scan_time.isoformat(timespec='seconds')}")
    lines.append("")
    lines.append(render_summary(src))

    coverage_section = render_coverage(scan_result)
    if coverage_section:
        lines.append(coverage_section)

    frameworks_section = render_frameworks(scan_result)
    if frameworks_section:
        lines.append(frameworks_section)

    if scan_result.risk_assessment:
        lines.append("## Risk Assessment")
        lines.append("")
        lines.append(
            f"Confidence: {scan_result.risk_assessment.confidence:.0%} "
            "(heuristic estimate, not a calibrated probability)"
        )
        lines.append("")
        for reason in scan_result.risk_assessment.reasoning:
            lines.append(f"- {reason}")
        lines.append("")

    if scan_result.gaps:
        lines.append("## Compliance Gaps")
        lines.append("")
        for gap in scan_result.gaps:
            icon = "⚠️" if gap.status == "unverified" else SEVERITY_ICONS[gap.severity]
            tag = " _(unverified)_" if gap.status == "unverified" else ""
            lines.append(f"### {icon} {_plain(gap.title)} ({gap.article}){tag}")
            lines.append("")
            lines.append(_plain(gap.description))
            lines.append("")
            lines.append(f"**Recommendation:** {_plain(gap.recommendation)}")
            lines.append("")

    recommendations_section = render_recommendations(scan_result)

    lines.append("## Findings")
    lines.append("")
    if not scan_result.findings:
        if src.findings:
            lines.append("No findings at or above the selected severity.")
        else:
            lines.append("No AI usage patterns detected.")
        lines.append("")
        if recommendations_section:
            lines.append(recommendations_section)
        return "\n".join(lines)

    ordered = sorted(scan_result.findings, key=lambda f: (f.file_path, f.line_number or 0))
    for file_path, file_findings in groupby(ordered, key=lambda f: f.file_path):
        lines.append(f"### `{_md_code(file_path)}`")
        lines.append("")
        for finding in file_findings:
            icon = SEVERITY_ICONS[finding.severity]
            location = f"line {finding.line_number}" if finding.line_number else "file-level"
            repeat = f", ×{finding.occurrences}" if finding.occurrences > 1 else ""
            lines.append(
                f"- {icon} **{finding.severity.value}** `{_md_code(finding.category)}` "
                f"({location}{repeat}): {_plain(finding.message)}"
            )
        lines.append("")

    if recommendations_section:
        lines.append(recommendations_section)

    return "\n".join(lines)
