"""Rich terminal rendering for scan results.

Produces a clean, professional console report — header panel, summary metrics,
compliance coverage, findings table, gaps, and recommendations — instead of
dumping raw Markdown to the terminal.
"""

import re

from rich.box import ROUNDED, SIMPLE_HEAVY
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from compliance_agent.models.findings import RiskTier, ScanResult, Severity

# ---------- palette ----------------------------------------------------------

TIER_STYLES = {
    RiskTier.MINIMAL: "green",
    RiskTier.LIMITED: "yellow",
    RiskTier.HIGH: "dark_orange",
    RiskTier.UNACCEPTABLE: "red",
}

SEVERITY_STYLES = {
    Severity.CRITICAL: "red",
    Severity.HIGH: "dark_orange",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}

SEVERITY_ICONS = {
    Severity.CRITICAL: "✗",
    Severity.HIGH: "✗",
    Severity.WARNING: "⚠",
    Severity.INFO: "ℹ",
}

STATUS_STYLES = {
    "met": "green",
    "partial": "dark_orange",
    "missing": "red",
    "not_applicable": "dim",
}

STATUS_LABELS = {
    "met": "MET",
    "partial": "PARTIAL",
    "missing": "MISSING",
    "not_applicable": "N/A",
}

HEADER_STYLE = "bold white on blue"
TITLE_STYLE = "bold blue"

TIER_SCALE = [RiskTier.MINIMAL, RiskTier.LIMITED, RiskTier.HIGH, RiskTier.UNACCEPTABLE]


# ---------- sections ---------------------------------------------------------


def _providers(result: ScanResult) -> list[str]:
    return sorted(
        {f.category.split(":", 1)[1] for f in result.findings if f.category.startswith("provider:")}
    )


def build_header(result: ScanResult) -> Panel:
    """Title panel with project metadata."""
    tier = result.risk_tier or RiskTier.MINIMAL
    grid = Table.grid(padding=(0, 2))
    grid.add_column(justify="right", style="dim")
    grid.add_column()
    grid.add_row("Project", Text(result.project_path, style="bold"))
    grid.add_row("Scan date", result.scan_time.strftime("%Y-%m-%d %H:%M"))
    grid.add_row("Files scanned", str(result.files_scanned))
    grid.add_row("Risk tier", Text(tier.value.upper(), style=f"bold {TIER_STYLES[tier]}"))
    return Panel(
        grid,
        title="EU AI Act Compliance Report",
        title_align="left",
        subtitle="ComplianceAgent",
        subtitle_align="right",
        border_style="blue",
        box=ROUNDED,
        padding=(1, 2),
    )


def _short_article(article: str | None) -> str:
    """Strip parenthetical descriptions so the findings column stays narrow.

    "Art. 3 (definitions), Art. 6 (classification)" -> "Art. 3, Art. 6"
    """
    if not article:
        return "—"
    return re.sub(r"\s*\([^)]*\)", "", article)


def _metric(value: str, label: str) -> Panel:
    inner = Table.grid(expand=True)
    inner.add_column(justify="center")
    inner.add_row(Text(value, style=TITLE_STYLE))
    inner.add_row(Text(label.upper(), style="dim"))
    return Panel(inner, box=ROUNDED, border_style="grey37", padding=(0, 1))


def build_summary(result: ScanResult) -> Panel:
    """Row of metric cards, titled 'Scan Summary'."""
    row = Table.grid(expand=True)
    for _ in range(4):
        row.add_column(ratio=1)
    row.add_row(
        _metric(str(result.files_scanned), "Files"),
        _metric(str(len(_providers(result))), "AI Systems"),
        _metric(str(len(result.findings)), "Findings"),
        _metric(str(len(result.gaps)), "Gaps"),
    )
    return Panel(
        row,
        title="Scan Summary",
        title_align="left",
        border_style="grey37",
        box=SIMPLE_HEAVY,
        padding=(0, 1),
    )


def build_coverage(result: ScanResult) -> RenderableType | None:
    if not result.coverage:
        return None
    table = Table(
        title="Compliance Coverage",
        title_style=TITLE_STYLE,
        title_justify="left",
        header_style=HEADER_STYLE,
        box=SIMPLE_HEAVY,
        expand=True,
        padding=(0, 1),
    )
    table.add_column("Article", no_wrap=True)
    table.add_column("Title")
    table.add_column("Status", no_wrap=True)
    table.add_column("Detail", style="dim")
    for entry in result.coverage:
        style = STATUS_STYLES[entry.status]
        if entry.status == "not_applicable":
            detail = entry.reason
        else:
            detail = f"{entry.requirements_met} / {entry.requirements_total} requirements met"
        table.add_row(
            entry.article,
            entry.title,
            Text(STATUS_LABELS[entry.status], style=f"bold {style}"),
            detail,
        )
    return table


def build_frameworks(result: ScanResult) -> RenderableType | None:
    if not result.frameworks_detected:
        return None
    blocks: list[RenderableType] = []
    for fw in result.frameworks_detected:
        patterns = ", ".join(fw.patterns)
        notes = Text()
        for note in fw.risk_notes:
            notes.append(f"  → {note}\n", style="dim")
        header = Text(f"{fw.name} ", style="bold")
        header.append(f"({patterns})", style="dim")
        blocks.append(Group(header, notes))
    return Panel(
        Group(*blocks),
        title="Frameworks Detected",
        title_align="left",
        border_style="grey37",
        box=SIMPLE_HEAVY,
        padding=(0, 1),
    )


def build_findings(result: ScanResult) -> RenderableType:
    if not result.findings:
        return Panel(
            Text("No AI usage patterns detected.", style="green"),
            title="Findings",
            title_align="left",
            border_style="grey37",
            box=SIMPLE_HEAVY,
            padding=(0, 1),
        )
    table = Table(
        title="Findings",
        title_style=TITLE_STYLE,
        title_justify="left",
        header_style=HEADER_STYLE,
        box=SIMPLE_HEAVY,
        expand=True,
        padding=(0, 1),
    )
    table.add_column("Severity", no_wrap=True)
    table.add_column("Category", style="dim", ratio=3, overflow="fold")
    table.add_column("Location", ratio=3, overflow="fold")
    table.add_column("Article", no_wrap=True)
    table.add_column("Finding", ratio=4, overflow="fold")
    ordered = sorted(result.findings, key=lambda f: (f.file_path, f.line_number or 0))
    for f in ordered:
        style = SEVERITY_STYLES[f.severity]
        sev = Text(f"{SEVERITY_ICONS[f.severity]} {f.severity.value.upper()}", style=style)
        location = f.file_path + (f":{f.line_number}" if f.line_number else "")
        message = f.message + (f" (×{f.occurrences})" if f.occurrences > 1 else "")
        table.add_row(sev, f.category, location, _short_article(f.article), message)
    return table


def build_gaps(result: ScanResult) -> RenderableType | None:
    if not result.gaps:
        return None
    blocks: list[RenderableType] = []
    for gap in result.gaps:
        style = SEVERITY_STYLES[gap.severity]
        body = Text()
        body.append(f"{SEVERITY_ICONS[gap.severity]} {gap.status.upper()}  ", style=f"bold {style}")
        body.append(gap.title, style="bold")
        body.append(f"\n{gap.description}\n", style="default")
        body.append("Fix: ", style="bold")
        body.append(gap.recommendation, style="dim")
        title = f"Article {gap.article.replace('Art. ', '')} — {gap.article_title or gap.title}"
        blocks.append(
            Panel(
                body,
                title=title,
                title_align="left",
                border_style=style,
                box=ROUNDED,
                padding=(0, 1),
            )
        )
    return Panel(
        Group(*blocks),
        title="Compliance Gaps",
        title_align="left",
        border_style="grey37",
        box=SIMPLE_HEAVY,
        padding=(0, 1),
    )


def build_recommendations(result: ScanResult) -> RenderableType | None:
    if not result.recommendations:
        return None
    blocks: list[RenderableType] = []
    for idx, rec in enumerate(result.recommendations, start=1):
        body = Text()
        body.append(rec.description + "\n\n", style="default")
        if rec.steps:
            body.append("Steps:\n", style="bold")
            for i, step in enumerate(rec.steps, start=1):
                body.append(f"  {i}. {step}\n", style="default")
        body.append("\nTemplate: ", style="bold")
        body.append(f"templates/{rec.template_path}", style="cyan")
        blocks.append(
            Panel(
                body,
                title=f"{idx}. {rec.title}  ·  {rec.article}",
                title_align="left",
                border_style="blue",
                box=ROUNDED,
                padding=(0, 1),
            )
        )
    return Panel(
        Group(*blocks),
        title="Recommendations",
        title_align="left",
        border_style="grey37",
        box=SIMPLE_HEAVY,
        padding=(0, 1),
    )


# ---------- entry points -----------------------------------------------------


def render_summary(console: Console, result: ScanResult) -> None:
    """Print only the header + summary metrics (used by --quiet)."""
    console.print(build_header(result))
    console.print(build_summary(result))


def render_report(console: Console, result: ScanResult) -> None:
    """Print the full professional terminal report."""
    console.print(build_header(result))
    console.print(build_summary(result))
    for section in (
        build_coverage(result),
        build_frameworks(result),
        build_findings(result),
        build_gaps(result),
        build_recommendations(result),
    ):
        if section is not None:
            console.print(section)
