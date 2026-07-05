"""PDF report generator for EU AI Act compliance.

Renders the scan result into HTML (see templates/report.html) and converts it
to an audit-ready PDF with WeasyPrint. WeasyPrint is imported lazily so the
rest of the CLI works even when its native libraries (pango/gobject) are not
installed.
"""

import os
import sys
from collections import Counter
from html import escape
from pathlib import Path
from string import Template

from compliance_agent import __version__
from compliance_agent.models.findings import RiskTier, ScanResult, Severity

# Homebrew installs WeasyPrint's native libs (pango, gobject, cairo) here, but
# macOS dyld does not search these paths by default, so `import weasyprint`
# fails with "cannot load library 'libgobject-2.0-0'" even when `brew install
# pango` succeeded. Priming DYLD_FALLBACK_LIBRARY_PATH before the import lets
# users generate PDFs without manually exporting the variable every run.
_MACOS_BREW_LIB_DIRS = ("/opt/homebrew/lib", "/usr/local/lib")


def _prime_macos_library_path() -> None:
    """On macOS, add Homebrew lib dirs to DYLD_FALLBACK_LIBRARY_PATH in-process.

    dyld reads the variable at dlopen time, so setting it here (before WeasyPrint
    is imported) is enough for ctypes to find the native libraries. No-op on
    other platforms and when the dirs are already present.
    """
    if sys.platform != "darwin":
        return
    current = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    existing = current.split(os.pathsep) if current else []
    additions = [d for d in _MACOS_BREW_LIB_DIRS if os.path.isdir(d) and d not in existing]
    if additions:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join([*additions, *existing])


TIER_COLORS = {
    RiskTier.MINIMAL: "#276749",  # green
    RiskTier.LIMITED: "#b7791f",  # yellow
    RiskTier.HIGH: "#dd6b20",  # orange
    RiskTier.UNACCEPTABLE: "#c53030",  # red
}

SEVERITY_ICONS = {
    Severity.CRITICAL: "✗",
    Severity.HIGH: "✗",
    Severity.WARNING: "⚠",
    Severity.INFO: "ℹ",
}

SNIPPET_LINES = 10

COVERAGE_STATUS_PILLS = {
    "met": ("Met", "pill-met"),
    "partial": ("Partial", "pill-partial"),
    "unverified": ("Unverified", "pill-partial"),
    "missing": ("Missing", "pill-missing"),
    "not_applicable": ("N/A", "pill-na"),
}

TIER_SCALE = [RiskTier.MINIMAL, RiskTier.LIMITED, RiskTier.HIGH, RiskTier.UNACCEPTABLE]

APPENDIX_ARTICLES = [
    ("Art. 5", "Prohibited AI practices", "Manipulation, mass surveillance, and other banned uses"),
    ("Art. 9", "Risk management system", "Continuous, iterative risk process for high-risk AI"),
    ("Art. 10", "Data and data governance", "Documented provenance, bias examination"),
    ("Art. 11", "Technical documentation", "Annex IV documentation before market placement"),
    ("Art. 12", "Record-keeping", "Automatic event logging over the system lifetime"),
    ("Art. 14", "Human oversight", "Effective oversight and intervention capability"),
    ("Art. 50", "Transparency obligations", "AI disclosure, content marking, deepfake labeling"),
]


class PDFReporter:
    """Generate audit-ready PDF compliance reports."""

    def __init__(self) -> None:
        self.template_dir = Path(__file__).parent / "templates"

    def generate(self, scan_result: ScanResult, output_path: Path | None = None) -> Path:
        """Generate a PDF report from scan results. Returns the output path."""
        html = self._render_html(scan_result)
        if output_path is None:
            project_name = Path(scan_result.project_path).name or "project"
            output_path = Path(f"compliance-report-{project_name}.pdf")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        _prime_macos_library_path()
        try:
            from weasyprint import HTML
        except OSError as exc:  # native libs (pango/gobject) missing
            raise RuntimeError(
                "PDF generation requires WeasyPrint's native libraries (pango, gobject). "
                "Install them — macOS: `brew install pango`; "
                "Debian/Ubuntu: `apt install libpango-1.0-0 libpangoft2-1.0-0`; "
                "then re-run. (Markdown and JSON reports work without them.) "
                f"Underlying error: {exc}"
            ) from exc

        HTML(string=html).write_pdf(str(output_path))
        return output_path

    def _render_html(self, scan_result: ScanResult) -> str:
        """Render scan results as HTML for PDF conversion."""
        template = Template((self.template_dir / "report.html").read_text(encoding="utf-8"))
        tier = scan_result.risk_tier or RiskTier.MINIMAL
        return template.substitute(
            project_name=escape(Path(scan_result.project_path).name or "project"),
            scan_date=escape(scan_result.scan_time.strftime("%Y-%m-%d %H:%M")),
            tier_label=escape(tier.value.upper()),
            tier_color=TIER_COLORS[tier],
            tool_version=escape(__version__),
            executive_summary=self._executive_summary(scan_result),
            risk_assessment=self._risk_assessment(scan_result),
            frameworks=self._frameworks_section(scan_result),
            findings=self._findings_table(scan_result),
            gaps=self._gaps_section(scan_result),
            recommendations=self._recommendations_section(scan_result),
            appendix=self._appendix(),
        )

    # ---------- sections -------------------------------------------------

    def _executive_summary(self, result: ScanResult) -> str:
        counts = Counter(f.severity for f in result.findings)
        providers = sorted(
            {
                f.category.split(":", 1)[1]
                for f in result.findings
                if f.category.startswith("provider:")
            }
        )
        applicable = [c for c in result.coverage if c.status != "not_applicable"]
        met_count = sum(c.requirements_met for c in applicable)
        total_count = sum(c.requirements_total for c in applicable)
        requirements_metric = f"{met_count} / {total_count}" if total_count else "n/a"
        tier = result.risk_tier or RiskTier.MINIMAL

        metrics = f"""
        <table class="metrics"><tr>
          <td><div class="value">{result.files_scanned}</div><div class="label">Files scanned</div></td>
          <td><div class="value">{len(providers)}</div><div class="label">AI providers</div></td>
          <td><div class="value">{len(result.findings)}</div><div class="label">Findings</div></td>
          <td><div class="value">{requirements_metric}</div><div class="label">Requirements met</div></td>
        </tr></table>
        """

        severity_bits = (
            ", ".join(
                f"{counts[sev]} {sev.value}"
                for sev in (Severity.CRITICAL, Severity.HIGH, Severity.WARNING, Severity.INFO)
                if counts.get(sev)
            )
            or "none"
        )

        if not result.findings:
            assessment = (
                "No AI usage was detected in this project. No EU AI Act obligations "
                "were identified by the scan."
            )
        else:
            provider_text = ", ".join(escape(p) for p in providers) or "no direct provider"
            assessment = (
                f"The scan detected AI usage ({provider_text}) and classified the project "
                f"in the <strong>{escape(tier.value.upper())}</strong> risk tier. "
                f"Findings by severity: {escape(severity_bits)}. "
                f"{len(result.gaps)} compliance gap(s) require attention; the "
                "Recommendations section pairs each gap with a ready-to-use code template."
            )

        return metrics + f"<p>{assessment}</p>" + self._coverage_table(result)

    def _coverage_table(self, result: ScanResult) -> str:
        if not result.coverage:
            return ""
        rows = []
        for entry in result.coverage:
            label, pill = COVERAGE_STATUS_PILLS[entry.status]
            if entry.status == "not_applicable":
                detail = escape(entry.reason)
            else:
                detail = f"{entry.requirements_met} / {entry.requirements_total} requirements met"
            rows.append(
                f"<tr><td>{escape(entry.article)}</td><td>{escape(entry.title)}</td>"
                f'<td><span class="pill {pill}">{label}</span></td><td>{detail}</td></tr>'
            )
        return (
            "<h3>Compliance coverage</h3>"
            "<table><tr><th>Article</th><th>Title</th><th>Status</th><th>Detail</th></tr>"
            + "".join(rows)
            + "</table>"
        )

    def _tier_scale(self, current: RiskTier) -> str:
        """Horizontal tier scale with the project's tier highlighted."""
        cells = []
        for tier in TIER_SCALE:
            if tier == current:
                mark = "&#9650; "  # ▲
                cells.append(
                    f'<td class="current" style="background:{TIER_COLORS[tier]}">'
                    f"{mark}{escape(tier.value.capitalize())}</td>"
                )
            else:
                cells.append(f"<td>{escape(tier.value.capitalize())}</td>")
        return f'<table class="tier-scale"><tr>{"".join(cells)}</tr></table>'

    def _risk_assessment(self, result: ScanResult) -> str:
        parts: list[str] = []
        assessment = result.risk_assessment
        tier = assessment.tier if assessment else (result.risk_tier or RiskTier.MINIMAL)
        parts.append(self._tier_scale(tier))
        if assessment:
            parts.append(
                f"<p><strong>Tier:</strong> {escape(assessment.tier.value.upper())} "
                f"&nbsp;·&nbsp; <strong>Confidence:</strong> {assessment.confidence:.0%}</p>"
            )
            if assessment.matched_categories:
                cats = ", ".join(escape(c) for c in assessment.matched_categories)
                parts.append(f"<p><strong>Annex III categories matched:</strong> {cats}</p>")
            parts.append("<ul>")
            for reason in assessment.reasoning:
                parts.append(f"<li>{escape(reason)}</li>")
            parts.append("</ul>")
        else:
            parts.append("<p>No risk assessment available.</p>")

        parts.append(
            """
            <h3>Key deadlines</h3>
            <table>
              <tr><th>Date</th><th>What applies</th></tr>
              <tr><td>February 2, 2025</td><td>Prohibited practices (Art. 5)</td></tr>
              <tr><td>August 2, 2026</td><td>General application, incl. transparency (Art. 50)
                  and Annex III high-risk obligations</td></tr>
              <tr><td>August 2, 2027</td><td>High-risk AI in regulated products (Art. 6(1))</td></tr>
            </table>
            """
        )
        return "".join(parts)

    def _frameworks_section(self, result: ScanResult) -> str:
        """Section 3 — only rendered when frameworks were detected."""
        if not result.frameworks_detected:
            return ""
        blocks = ["<section>", "<h2>3. Frameworks Detected</h2>"]
        for framework in result.frameworks_detected:
            patterns = ", ".join(escape(p) for p in framework.patterns)
            notes = "".join(f"<li>{escape(note)}</li>" for note in framework.risk_notes)
            blocks.append(
                f'<div class="rec"><h3>{escape(framework.name)} ({patterns})</h3>'
                f"<ul>{notes}</ul></div>"
            )
        blocks.append("</section>")
        return "".join(blocks)

    def _findings_table(self, result: ScanResult) -> str:
        if not result.findings:
            return "<p>No findings.</p>"
        rows = []
        ordered = sorted(result.findings, key=lambda f: (f.file_path, f.line_number or 0))
        for f in ordered:
            sev = f.severity.value
            line = f'<span class="ln">:{f.line_number}</span>' if f.line_number else ""
            occurrences = f' <span class="occ">×{f.occurrences}</span>' if f.occurrences > 1 else ""
            rows.append(
                f'<tr class="sev-{sev}">'
                f'<td class="sev">'
                f'<span class="pill pill-{sev}">{SEVERITY_ICONS[f.severity]} {escape(sev)}</span>'
                f"</td>"
                f'<td class="cat">{escape(f.category)}</td>'
                f'<td class="loc"><code>{escape(f.file_path)}</code>{line}</td>'
                f'<td class="art">{escape(f.article or "—")}</td>'
                f"<td>{escape(f.message)}{occurrences}</td>"
                f"</tr>"
            )
        return (
            '<table class="findings">'
            "<colgroup>"
            '<col style="width:12%"><col style="width:15%"><col style="width:31%">'
            '<col style="width:14%"><col style="width:28%">'
            "</colgroup>"
            "<tr><th>Severity</th><th>Category</th><th>Location</th>"
            "<th>Article</th><th>Finding</th></tr>" + "".join(rows) + "</table>"
        )

    def _gaps_section(self, result: ScanResult) -> str:
        if not result.gaps:
            return "<p>No compliance gaps identified.</p>"
        blocks = []
        for gap in result.gaps:
            status_text = "unverified" if gap.status == "unverified" else "unmet"
            blocks.append(
                f'<div class="gap {gap.severity.value}">'
                f"<h3>{SEVERITY_ICONS[gap.severity]} {escape(gap.title)} ({escape(gap.article)})</h3>"
                f'<p class="muted">Status: {status_text} &nbsp;·&nbsp; '
                f"Severity: {escape(gap.severity.value)}</p>"
                f"<p>{escape(gap.description)}</p>"
                f"<p><strong>Remediation:</strong> {escape(gap.recommendation)}</p>"
                f"</div>"
            )
        return "".join(blocks)

    def _recommendations_section(self, result: ScanResult) -> str:
        if not result.recommendations:
            return (
                "<p>No recommendations generated. Run "
                "<code>compliance-agent recommend &lt;path&gt;</code> for fix templates.</p>"
            )
        blocks = []
        for idx, rec in enumerate(result.recommendations, start=1):
            steps = "".join(f"<li>{escape(step)}</li>" for step in rec.steps)
            snippet = ""
            if rec.template_content:
                preview = "\n".join(rec.template_content.splitlines()[:SNIPPET_LINES])
                snippet = f"<pre>{escape(preview)}\n…</pre>"
            blocks.append(
                f'<div class="rec">'
                f"<h3>{idx}. {escape(rec.title)} ({escape(rec.article)})</h3>"
                f"<p>{escape(rec.description)}</p>"
                f"<p><strong>Template:</strong> <code>templates/{escape(rec.template_path)}</code></p>"
                f"<ol>{steps}</ol>"
                f"{snippet}"
                f"</div>"
            )
        return "".join(blocks)

    def _appendix(self) -> str:
        rows = "".join(
            f"<tr><td>{escape(article)}</td><td>{escape(title)}</td><td>{escape(summary)}</td></tr>"
            for article, title, summary in APPENDIX_ARTICLES
        )
        return f"""
        <table><tr><th>Article</th><th>Title</th><th>In short</th></tr>{rows}</table>
        <h3>Penalties</h3>
        <p>Non-compliance fines reach up to <strong>€35M or 7% of global annual
        turnover</strong> (prohibited practices), €15M / 3% for most other violations.</p>
        <h3>Resources</h3>
        <ul>
          <li>Regulation (EU) 2024/1689 full text: https://eur-lex.europa.eu/eli/reg/2024/1689/oj</li>
          <li>EU AI Act explorer: https://artificialintelligenceact.eu/</li>
        </ul>
        <p class="muted">This report is generated by automated heuristics and does not
        constitute legal advice.</p>
        """
