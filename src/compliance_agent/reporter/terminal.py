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

from compliance_agent import DISCLAIMER
from compliance_agent.models.findings import RiskTier, ScanResult, Severity

# ---------- palette ----------------------------------------------------------

# MINIMAL is deliberately a neutral cyan, not green: a low tier is a heuristic
# non-detection, not an affirmative "safe/pass" verdict, and green reads as the
# latter on a report shown to management.
TIER_STYLES = {
    RiskTier.MINIMAL: "cyan",
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
    "unverified": "yellow",
    "missing": "red",
    "not_applicable": "dim",
}

STATUS_LABELS = {
    "met": "MET",
    "partial": "PARTIAL",
    "unverified": "UNVERIFIED",
    "missing": "MISSING",
    # "N/A" read as an affirmative "this obligation does not apply to us".
    # These articles were gated out by heuristic detection (risk tier, no AI
    # signal, no user interaction, ...), so the honest label is that they were
    # NOT ASSESSED — a non-detection, not a determination of inapplicability.
    "not_applicable": "NOT ASSESSED",
}

HEADER_STYLE = "bold white on blue"
TITLE_STYLE = "bold blue"

TIER_SCALE = [RiskTier.MINIMAL, RiskTier.LIMITED, RiskTier.HIGH, RiskTier.UNACCEPTABLE]

# C0 control characters (except tab/newline) carried in from a scanned repo — a
# hostile filename like ``evil\x1b[31m.py`` can smuggle raw ANSI/OSC sequences
# into the terminal to recolor output, set the window title, or move the cursor
# to overwrite the rendered risk tier. Rich's Text() escapes its own markup but
# passes raw ESC (0x1b) through, so strip these before rendering.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _sanitize(text: str) -> str:
    """Strip terminal control characters from repo-derived text."""
    return _CONTROL_CHARS_RE.sub("", text)


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
    grid.add_row("Project", Text(_sanitize(result.project_path), style="bold"))
    grid.add_row("Scan date", result.scan_time.strftime("%Y-%m-%d %H:%M"))
    grid.add_row("Files scanned", str(result.files_scanned))
    grid.add_row("Risk tier", Text(tier.value.upper(), style=f"bold {TIER_STYLES[tier]}"))
    if tier in (RiskTier.MINIMAL, RiskTier.LIMITED):
        # Domain risk is keyword-detected; a low tier must not read as "safe".
        grid.add_row(
            "",
            Text(
                "Keyword-based domain check — may miss high-risk uses. If this "
                "system is used for hiring, credit, biometrics, education, or "
                "other Annex III domains, treat it as HIGH.",
                style="dim italic",
            ),
        )
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


SECTION_BORDER = "blue"


def _section(title: str, body: RenderableType) -> Panel:
    """Wrap a section body in the standard bordered panel.

    Every section uses this so borders and spacing stay consistent — unlike
    a bare Rich table, a panel adds no stray title/trailing blank lines.
    """
    return Panel(
        body,
        title=title,
        title_align="left",
        border_style=SECTION_BORDER,
        box=ROUNDED,
        padding=(1, 1),
    )


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
    return _section("Scan Summary", row)


def build_risk_notes(result: ScanResult) -> RenderableType | None:
    """Render the risk tier, confidence, and the classifier's caveats.

    Without this the terminal report silently dropped the risk-assessment
    reasoning — including the caveat that signature-based detection cannot see
    every AI integration, so a 'no AI' / low-tier result is not a guarantee.
    Those caveats are exactly what stop a low tier from reading as a clean bill,
    so they belong on the primary (terminal) surface, not only in JSON/PDF.
    """
    assessment = result.risk_assessment
    if assessment is None:
        return None
    tier = assessment.tier
    body = Text()
    body.append("Risk tier: ", style="bold")
    body.append(f"{tier.value.upper()}", style=f"bold {TIER_STYLES[tier]}")
    # Confidence is a heuristic keyword tally, not a calibrated probability —
    # label it so the percentage does not imply statistical precision.
    body.append(f"   ·   Confidence: {assessment.confidence:.0%} (heuristic estimate)\n\n")
    for reason in assessment.reasoning:
        body.append(f"  • {reason}\n", style="dim")
    return _section("Risk Assessment", body)


def build_coverage(result: ScanResult) -> RenderableType | None:
    if not result.coverage:
        return None
    table = Table(
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
    return _section("Compliance Coverage", table)


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
        if fw.version:
            header.append(f"v{fw.version} ", style="cyan")
        header.append(f"({patterns})", style="dim")
        blocks.append(Group(header, notes))
    return _section("Frameworks Detected", Group(*blocks))


def build_findings(result: ScanResult, summary_source: ScanResult | None = None) -> RenderableType:
    if not result.findings:
        # Distinguish "nothing detected" from "everything filtered out by
        # --severity": claiming "No AI usage patterns detected" when AI *was*
        # detected but sits below the display threshold is misleading.
        src = summary_source or result
        if src.findings:
            msg = Text("No findings at or above the selected severity.", style="dim")
        else:
            msg = Text("No AI usage patterns detected.", style="green")
        return _section("Findings", msg)
    table = Table(
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
        # These carry values from the scanned (untrusted) repo — most notably the
        # file path. Passed as plain str, Rich would parse them as console markup:
        # a directory named "[/bold]" crashes the default scan, and "[link=...]"
        # injects a clickable link into the report. Text() renders them literally.
        table.add_row(
            sev,
            Text(_sanitize(f.category)),
            Text(_sanitize(location)),
            Text(_sanitize(_short_article(f.article))),
            Text(_sanitize(message)),
        )
    return _section("Findings", table)


def build_scan_errors(result: ScanResult) -> RenderableType | None:
    """Warn when detectors crashed mid-scan, so a partial scan never reads clean."""
    errors = getattr(result, "scan_errors", None)
    if not errors:
        return None
    body = Text()
    body.append(
        f"{len(errors)} file(s) could not be fully analyzed — coverage is "
        "incomplete and results may be missing findings:\n",
        style="bold yellow",
    )
    for err in errors[:20]:
        body.append(f"  • {err}\n", style="dim")
    if len(errors) > 20:
        body.append(f"  … and {len(errors) - 20} more\n", style="dim")
    return _section("Scan Warnings", body)


def build_gaps(result: ScanResult) -> RenderableType | None:
    if not result.gaps:
        return None
    blocks: list[RenderableType] = []
    for gap in result.gaps:
        # An unverified gap (referenced in docs, mechanism unconfirmed) reads as a
        # caution, not a hard failure — mark it distinctly from a missing control.
        if gap.status == "unverified":
            style = "yellow"
            icon = "⚠"
        else:
            style = SEVERITY_STYLES[gap.severity]
            icon = SEVERITY_ICONS[gap.severity]
        body = Text()
        body.append(f"{icon} {gap.status.upper()}  ", style=f"bold {style}")
        body.append(_sanitize(gap.title), style="bold")
        body.append(f"\n{_sanitize(gap.description)}\n", style="default")
        body.append("Fix: ", style="bold")
        body.append(_sanitize(gap.recommendation), style="dim")
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
    return _section("Compliance Gaps", Group(*blocks))


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
    return _section("Recommendations", Group(*blocks))


def build_next_steps(result: ScanResult, path: str) -> Panel:
    """Boxed 'Next Steps' section, consistent with the other sections."""
    body = Text()
    if result.gaps:
        body.append("1. Review the issues above.\n")
        body.append("2. Get the fix files:  ")
        body.append(f"compliance-agent recommend {path} --output ./fixes\n", style="bold cyan")
        body.append("3. Copy the files from ./fixes into your project.\n")
        body.append("4. Check again:  ")
        body.append(f"compliance-agent scan {path}", style="bold cyan")
    else:
        body.append(
            "✓ No gaps detected by static analysis.\n",
            style="green",
        )
        body.append(
            "This is not a determination of compliance — verify manually and "
            "consult qualified legal counsel.\n",
            style="dim",
        )
        body.append("\nTo share this result as a PDF:\n")
        body.append(
            f"compliance-agent scan {path} --format pdf --output report.pdf", style="bold cyan"
        )
    return _section("Next Steps", body)


# ---------- entry points -----------------------------------------------------


def build_disclaimer() -> Text:
    """The legal disclaimer, shown at the foot of every terminal report."""
    return Text(DISCLAIMER, style="dim italic")


def print_summary(
    console: Console, result: ScanResult, summary_source: ScanResult | None = None
) -> None:
    """Print only the header + summary metrics (used by --quiet).

    ``summary_source`` supplies the metric counts when ``result`` is a
    severity-filtered view, so the tiles report the true totals rather than the
    filtered subset (which otherwise showed "0 AI systems" under --severity high).
    """
    src = summary_source or result
    console.print(build_header(result))
    console.print()
    console.print(build_summary(src))
    scan_errors = build_scan_errors(src)
    if scan_errors is not None:
        console.print()
        console.print(scan_errors)
    console.print()
    console.print(build_disclaimer())


def render_report(
    console: Console, result: ScanResult, summary_source: ScanResult | None = None
) -> None:
    """Print the full professional terminal report.

    A blank line precedes every section so the spacing is consistent
    (header, Scan Summary, Compliance Coverage, Findings, etc.). ``summary_source``
    supplies true metric totals when ``result`` is a severity-filtered view.
    """
    src = summary_source or result
    console.print(build_header(result))
    for section in (
        build_summary(src),
        build_scan_errors(result),
        build_risk_notes(result),
        build_coverage(result),
        build_frameworks(result),
        build_findings(result, summary_source=src),
        build_gaps(result),
        build_recommendations(result),
    ):
        if section is not None:
            console.print()
            console.print(section)
    console.print()
    console.print(build_disclaimer())
