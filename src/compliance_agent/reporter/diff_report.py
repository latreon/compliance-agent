"""Render a scan-to-scan diff as human-readable Markdown."""

from compliance_agent.diff import IMPROVED, MIXED, REGRESSED, ScanDiff

_VERDICT_LABEL = {
    IMPROVED: "Compliance improved",
    REGRESSED: "Compliance regressed",
    MIXED: "Mixed — some gains, some regressions",
    "unchanged": "No change",
}
_VERDICT_MARK = {IMPROVED: "▲", REGRESSED: "▼", MIXED: "◆", "unchanged": "="}


def _tier(value: object) -> str:
    return str(value).upper() if value else "n/a"


def render_diff_markdown(diff: ScanDiff, base_label: str, target_label: str) -> str:
    """Return a Markdown comparison report between two scans."""
    mark = _VERDICT_MARK.get(diff.verdict, "=")
    lines = [
        "# Scan comparison",
        "",
        f"**{mark} {_VERDICT_LABEL.get(diff.verdict, diff.verdict)}**",
        "",
        f"- Base: `{base_label}`",
        f"- Target: `{target_label}`",
        "",
        "## Risk tier",
        "",
        f"- {_tier(diff.base_tier)} → {_tier(diff.target_tier)} ({diff.tier_direction})",
        "",
        "## Compliance gaps",
        "",
        f"- Resolved: {len(diff.gaps_resolved)}",
        f"- New: {len(diff.gaps_new)}",
        f"- Unchanged: {diff.gaps_unchanged}",
    ]
    if diff.gaps_resolved:
        lines.append("")
        lines.append("### Resolved")
        for gap in diff.gaps_resolved:
            lines.append(f"- ✓ {gap.article} — {gap.title}")
    if diff.gaps_new:
        lines.append("")
        lines.append("### New")
        for gap in diff.gaps_new:
            lines.append(f"- ✗ {gap.article} — {gap.title}")

    lines += [
        "",
        "## Requirements met",
        "",
        f"- {diff.requirements_met_base} / {diff.requirements_total_base} → "
        f"{diff.requirements_met_target} / {diff.requirements_total_target}",
        "",
        "## Findings",
        "",
        f"- Added: {len(diff.findings_added)}",
        f"- Removed: {len(diff.findings_removed)}",
        f"- Unchanged: {diff.findings_unchanged}",
        "",
    ]
    return "\n".join(lines)
