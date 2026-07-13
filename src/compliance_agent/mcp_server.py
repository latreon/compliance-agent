"""MCP server for ComplianceAgent — expose EU AI Act compliance scanning as tools.

Lets any MCP-compatible client (Claude Desktop, Cursor, etc.) drive the same
scan -> classify -> gaps -> coverage -> recommendations pipeline the CLI uses,
without shelling out to a subprocess.

Usage:
    compliance-agent-mcp          # stdio transport (for Claude Desktop, Cursor, etc.)
    compliance-agent-mcp --http   # HTTP transport (for remote access)

Install:
    pip install compliance-agent[mcp]
"""

from __future__ import annotations

import json
from pathlib import Path

from fastmcp import FastMCP

from compliance_agent import get_rules_dir, get_templates_dir
from compliance_agent.config import ConfigError, ProjectConfig, load_config
from compliance_agent.diff import diff_scan_results
from compliance_agent.models.findings import SEVERITY_ORDER, ScanResult, Severity
from compliance_agent.pipeline import run_pipeline
from compliance_agent.reporter.json_report import build_envelope
from compliance_agent.reporter.markdown import render_markdown, render_summary

mcp = FastMCP(
    "ComplianceAgent",
    instructions=(
        "EU AI Act compliance scanner for AI projects. "
        "Scan a project directory to check for compliance issues, "
        "generate fix recommendations, compare scans over time, "
        "and look up specific EU AI Act articles."
    ),
)

_VALID_SEVERITIES = ", ".join(s.value for s in Severity)
_VALID_FORMATS = ("markdown", "json")


# ---------------------------------------------------------------------------
# Shared validation helpers — every tool funnels its path/severity/config
# handling through these so error wording stays identical across tools and no
# tool can raise instead of returning a clear error string.
# ---------------------------------------------------------------------------


def _resolve_project_path(path: str) -> tuple[Path | None, str | None]:
    """Resolve and validate a project directory path.

    Returns ``(resolved_path, None)`` on success or ``(None, error_message)``
    when the path does not exist or is not a directory.
    """
    project_path = Path(path).expanduser().resolve()
    if not project_path.exists():
        return None, (
            f"Error: path '{path}' does not exist (resolved to '{project_path}'). "
            "Check the path and try again."
        )
    if not project_path.is_dir():
        return None, (
            f"Error: '{path}' is a file, not a folder. "
            "Point this tool at a project directory, e.g. '.' or './my-project'."
        )
    return project_path, None


def _parse_severity(value: str) -> tuple[Severity | None, str | None]:
    """Parse a severity string. Returns ``(Severity, None)`` or ``(None, error)``."""
    try:
        return Severity(value.lower()), None
    except (ValueError, AttributeError):
        return None, (f"Error: invalid severity '{value}'. Valid options: {_VALID_SEVERITIES}.")


def _load_project_config(project_path: Path) -> tuple[ProjectConfig | None, str | None]:
    """Load compliance.yaml for a project. Returns ``(config, None)`` or ``(None, error)``.

    A broken compliance.yaml is reported back to the caller rather than raised,
    since a raised exception would look like a tool crash to an MCP client
    instead of a fixable configuration problem in the scanned project.
    """
    try:
        return load_config(project_path), None
    except ConfigError as exc:
        return None, f"Error: invalid compliance.yaml in '{project_path}' — {exc}"


def _filter_by_severity(result: ScanResult, threshold: Severity) -> ScanResult:
    """Return a copy of result with findings/gaps filtered to the threshold."""
    threshold_rank = SEVERITY_ORDER[threshold]
    filtered_findings = [f for f in result.findings if SEVERITY_ORDER[f.severity] >= threshold_rank]
    filtered_gaps = [g for g in result.gaps if SEVERITY_ORDER[g.severity] >= threshold_rank]
    return result.model_copy(update={"findings": filtered_findings, "gaps": filtered_gaps})


def _merge_unique(cli_values: list[str], config_values: list[str]) -> list[str]:
    """Combine two pattern lists, deduped, first-list-wins order."""
    merged = list(cli_values)
    seen = set(merged)
    for value in config_values:
        if value not in seen:
            merged.append(value)
            seen.add(value)
    return merged


def _article_sort_key(name: str) -> tuple[int, int | str]:
    """Sort ``art<N>`` directory names numerically instead of as strings.

    A plain string sort puts "art5" after "art43" and "art6"/"art9" after
    "art53" — confusing in a report meant to be read in article order.
    Non-article names (e.g. "common") sort after all articles, alphabetically.
    """
    if name.startswith("art") and name[3:].isdigit():
        return (0, int(name[3:]))
    return (1, name)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def scan_project(
    path: str,
    severity: str = "info",
    exclude: list[str] | None = None,
    include: list[str] | None = None,
    format: str = "markdown",
) -> str:
    """Run a full EU AI Act compliance scan on a project directory.

    Runs the complete pipeline (scan -> classify risk tier -> find compliance
    gaps -> compute obligation coverage -> generate fix recommendations) and
    returns a report. This is the most expensive of the tools — for a quick
    check use ``get_summary`` instead, and for a project's compliance.yaml
    defaults (excludes, declared risk tier) this tool loads and merges them
    automatically.

    Args:
        path: Absolute or relative path to the project root directory, e.g.
            "/Users/me/my-ai-app". Prefer an absolute path: a relative path
            resolves against the MCP server process's working directory, not
            the caller's, which is usually not what you want.
        severity: Minimum severity to include in the report: one of
            "info", "warning", "high", "critical" (default "info", i.e. show
            everything). Filtering only affects what is displayed — nothing
            about the underlying scan changes.
        exclude: Glob patterns for files/directories to skip, e.g.
            ["tests/*", "docs/*", "*.md"]. Combined (not replaced) with any
            excludes declared in the project's compliance.yaml.
        include: If set, only scan paths matching these globs, e.g.
            ["src/**/*.py"]. Combined with compliance.yaml's include list.
        format: "markdown" for a human-readable report, or "json" for a
            structured, versioned envelope (the same shape the CLI's
            ``--format json`` produces) suitable for feeding into
            ``diff_scans`` later.

    Returns:
        A Markdown report string, or a JSON string containing
        ``schema_version``, ``tool_version``, ``disclaimer``, and
        ``scan_result``. A project with zero findings still returns a full
        report with a "Findings: none" summary line — never an empty string.

    Limitations:
        This is a heuristic static scan, not a legal compliance
        determination — it can have false positives and false negatives.
        A malformed compliance.yaml in the project is reported as an error
        string rather than raised.
    """
    project_path, error = _resolve_project_path(path)
    if error:
        return error
    assert project_path is not None  # guaranteed by _resolve_project_path's contract

    severity_enum, error = _parse_severity(severity)
    if error:
        return error

    if format not in _VALID_FORMATS:
        return f"Error: invalid format '{format}'. Valid options: {', '.join(_VALID_FORMATS)}."

    config, error = _load_project_config(project_path)
    if error:
        return error

    merged_exclude = list(exclude or [])
    merged_include = list(include or [])
    if config and config.scan:
        merged_exclude = _merge_unique(merged_exclude, config.scan.exclude)
        merged_include = _merge_unique(merged_include, config.scan.include)

    result = run_pipeline(
        project_path,
        exclude=merged_exclude,
        include=merged_include,
        with_recommendations=True,
        declared_tier=config.posture.risk_tier if config else None,
    )

    display = _filter_by_severity(result, severity_enum) if severity_enum else result

    if format == "json":
        return json.dumps(build_envelope(display), indent=2, ensure_ascii=False)
    return render_markdown(display, summary_source=result)


@mcp.tool()
def get_summary(path: str) -> str:
    """Get a quick, lightweight compliance summary for a project.

    Runs the scan and classification steps but skips fix-recommendation
    generation, so it is faster than ``scan_project``. Use this for a quick
    "how does this project look" check before running the full scan.

    Args:
        path: Absolute or relative path to the project root directory. Prefer
            an absolute path — a relative path resolves against the MCP
            server process's working directory, not the caller's.

    Returns:
        A short Markdown summary: files scanned, detected AI providers, risk
        tier, and finding counts by severity. For a project with no AI usage
        at all, this still returns a complete summary reading "Findings:
        none" — never an empty string.

    Limitations:
        Does not include compliance gaps, coverage, or fix recommendations —
        use ``scan_project`` or ``recommend_fixes`` for those.
    """
    project_path, error = _resolve_project_path(path)
    if error:
        return error
    assert project_path is not None  # guaranteed by _resolve_project_path's contract

    config, error = _load_project_config(project_path)
    if error:
        return error

    result = run_pipeline(
        project_path,
        with_recommendations=False,
        declared_tier=config.posture.risk_tier if config else None,
    )
    return render_summary(result)


@mcp.tool()
def recommend_fixes(path: str) -> str:
    """Generate concrete, copy-paste fix recommendations for a project's compliance gaps.

    Runs the full pipeline with recommendation generation enabled, then
    returns only the recommendations section — each one naming the EU AI Act
    article it addresses, the fix template file to use, and numbered steps to
    apply it.

    Args:
        path: Absolute or relative path to the project root directory. Prefer
            an absolute path — a relative path resolves against the MCP
            server process's working directory, not the caller's.

    Returns:
        A Markdown-formatted list of fix recommendations with steps, or a
        clear "nothing to recommend" message when the project has no
        compliance gaps. If gaps exist but no fix template covers them yet,
        says so explicitly and names the uncovered articles rather than
        silently returning nothing.

    Limitations:
        Only covers gaps that map to an existing fix template (see
        ``list_templates`` / ``get_article_info`` for what's covered).
    """
    project_path, error = _resolve_project_path(path)
    if error:
        return error
    assert project_path is not None  # guaranteed by _resolve_project_path's contract

    config, error = _load_project_config(project_path)
    if error:
        return error

    result = run_pipeline(
        project_path,
        with_recommendations=True,
        declared_tier=config.posture.risk_tier if config else None,
    )

    if not result.recommendations and not result.gaps:
        return "No compliance gaps found — nothing to recommend."
    if not result.recommendations:
        articles = sorted({gap.article for gap in result.gaps})
        return (
            f"Found {len(result.gaps)} compliance gap(s), but no "
            f"copy-paste fix template is available yet for: {', '.join(articles)}.\n"
            "Run scan_project to see the full details of each gap."
        )

    lines = ["## Fix Recommendations", ""]
    for idx, rec in enumerate(result.recommendations, start=1):
        lines.append(f"### {idx}. {rec.title} ({rec.article})")
        lines.append("")
        lines.append(rec.description)
        lines.append("")
        lines.append(f"**Template:** `templates/{rec.template_path}`")
        if rec.extra_templates:
            extras = ", ".join(f"`templates/{p}`" for p in rec.extra_templates)
            lines.append(f"**Also relevant:** {extras}")
        lines.append("")
        lines.append("**Steps:**")
        for i, step in enumerate(rec.steps, start=1):
            lines.append(f"{i}. {step}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def diff_scans(base_path: str, target_path: str) -> str:
    """Compare two JSON scan reports to see whether compliance improved or regressed.

    Both arguments must point at JSON files previously produced by
    ``scan_project`` with ``format="json"`` (or the CLI's
    ``compliance-agent scan --format json``) — not arbitrary JSON.

    Args:
        base_path: Path to the earlier baseline JSON report file. Prefer an
            absolute path — a relative path resolves against the MCP server
            process's working directory, not the caller's.
        target_path: Path to the later (newer) JSON report file. Same
            path-resolution caveat as base_path.

    Returns:
        A Markdown summary: risk-tier movement, gaps resolved/newly
        introduced/changed status, a findings added/removed/unchanged count,
        and the requirements-met ratio for each scan.

    Limitations:
        Both files must exist and be valid ComplianceAgent JSON report
        envelopes (containing a top-level "scan_result" key); anything else
        — a missing file, plain text, unrelated JSON, or a report from an
        incompatible schema version — returns a clear error string instead of
        raising.
    """
    base_file = Path(base_path).expanduser().resolve()
    target_file = Path(target_path).expanduser().resolve()

    paths = (("base", base_file, base_path), ("target", target_file, target_path))
    for label, fpath, original in paths:
        if not fpath.exists():
            return f"Error: {label} report '{original}' does not exist (resolved to '{fpath}')."
        if not fpath.is_file():
            return f"Error: {label} report '{original}' is a directory, not a file."

    try:
        base_envelope = json.loads(base_file.read_text(encoding="utf-8"))
        target_envelope = json.loads(target_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"Error: could not read/parse a report file ({exc}). Both files must be valid JSON."

    try:
        base_result = ScanResult.model_validate(base_envelope["scan_result"])
        target_result = ScanResult.model_validate(target_envelope["scan_result"])
    except (KeyError, TypeError) as exc:
        return (
            f"Error: file is missing the expected 'scan_result' key ({exc}). "
            "Both files must be JSON reports produced by scan_project(format='json') "
            "or `compliance-agent scan --format json`."
        )
    except Exception as exc:  # pydantic.ValidationError and friends
        return (
            f"Error: report does not match the expected ComplianceAgent schema ({exc}). "
            "Ensure both files came from a compatible version of ComplianceAgent."
        )

    diff = diff_scan_results(base_result, target_result)

    lines = ["## Scan Comparison", ""]
    base_tier_text = diff.base_tier.value.upper() if diff.base_tier else "n/a"
    target_tier_text = diff.target_tier.value.upper() if diff.target_tier else "n/a"
    lines.append(f"**Base tier:** {base_tier_text}")
    lines.append(f"**Target tier:** {target_tier_text}")
    lines.append(f"**Tier direction:** {diff.tier_direction}")
    lines.append(f"**Verdict:** {diff.verdict}")
    lines.append("")

    if diff.gaps_resolved:
        lines.append(f"### Gaps resolved ({len(diff.gaps_resolved)})")
        for g in diff.gaps_resolved:
            lines.append(f"- {g.title} ({g.article})")
        lines.append("")

    if diff.gaps_new:
        lines.append(f"### New gaps ({len(diff.gaps_new)})")
        for g in diff.gaps_new:
            lines.append(f"- {g.title} ({g.article})")
        lines.append("")

    if diff.gaps_status_changed:
        lines.append(f"### Gaps with status change ({len(diff.gaps_status_changed)})")
        for g in diff.gaps_status_changed:
            lines.append(f"- {g.title} ({g.article}) — now: {g.status}")
        lines.append("")

    lines.append(
        f"**Findings:** +{len(diff.findings_added)} added, "
        f"-{len(diff.findings_removed)} removed, {diff.findings_unchanged} unchanged"
    )
    lines.append(
        f"**Requirements met:** {diff.requirements_met_base}/{diff.requirements_total_base} → "
        f"{diff.requirements_met_target}/{diff.requirements_total_target}"
    )
    return "\n".join(lines)


@mcp.tool()
def get_article_info(article_number: int) -> str:
    """Look up what ComplianceAgent knows about a specific EU AI Act article.

    Covers prohibited-practice rules (Art. 5), high-risk classification rules
    (Art. 6, via Annex III), and every article with a fix-template directory
    (currently 9, 10, 11, 12, 13, 14, 15, 16, 17, 24, 26, 27, 43, 50, 53).

    Args:
        article_number: The EU AI Act article number, e.g. 5, 6, 9, 12, 50.

    Returns:
        A Markdown snippet describing what the article covers and where its
        rules/templates live. For an article ComplianceAgent does not cover,
        returns a message naming the article as uncovered plus the full list
        of articles that are covered — never a bare error or empty string.

    Limitations:
        This describes ComplianceAgent's own rule/template coverage, not the
        full legal text of the EU AI Act.
    """
    rules_dir = get_rules_dir()
    templates_dir = get_templates_dir()

    if article_number == 5:
        prohibited = rules_dir / "prohibited.yaml"
        if prohibited.is_file():
            content = prohibited.read_text(encoding="utf-8")
            return (
                "## Article 5 — Prohibited AI Practices\n\n"
                "This article defines AI practices that are banned outright under "
                "the EU AI Act.\n\nRules file: `rules/prohibited.yaml`\n\n"
                f"{content[:2000]}"
            )

    if article_number == 6:
        annex3 = rules_dir / "annex3.yaml"
        if annex3.is_file():
            content = annex3.read_text(encoding="utf-8")
            return (
                "## Article 6 — High-Risk AI Systems\n\n"
                "Defines which AI systems are classified as high-risk.\n\n"
                f"Rules file: `rules/annex3.yaml`\n\n{content[:2000]}"
            )

    art_dir = templates_dir / f"art{article_number}"
    if art_dir.is_dir():
        files = [f for f in art_dir.rglob("*") if f.is_file() and "__pycache__" not in f.parts]
        file_list = "\n".join(f"  - `{f.relative_to(templates_dir)}`" for f in files)
        return (
            f"## Article {article_number}\n\n"
            f"Available fix templates ({len(files)} files):\n"
            f"{file_list}\n\n"
            "Use recommend_fixes on a project to see which templates apply to your gaps."
        )

    available = sorted(
        {
            d.name
            for d in templates_dir.iterdir()
            if d.is_dir() and d.name.startswith("art") and d.name != "art"
        },
        key=_article_sort_key,
    )
    return (
        f"Article {article_number} is not currently covered by ComplianceAgent's "
        "rules or templates.\n"
        f"Covered articles: {', '.join(available)}\n"
        "See the full list in the project README."
    )


@mcp.tool()
def list_templates() -> str:
    """List every fix template ComplianceAgent ships, grouped by article.

    Useful for discovering what fixes are available before running a scan, or
    for cross-checking ``recommend_fixes`` output against the full catalog.

    Returns:
        A Markdown list of template directories and files, one section per
        article (e.g. "art50"). Directories with no template files (or only
        ``__pycache__`` contents) are omitted. Returns "No templates found."
        if the templates directory is missing or entirely empty — never an
        empty string.
    """
    templates_dir = get_templates_dir()
    if not templates_dir.is_dir():
        return "Templates directory not found."

    lines = ["## Available Fix Templates", ""]
    art_dirs = sorted(
        (d for d in templates_dir.iterdir() if d.is_dir()),
        key=lambda d: _article_sort_key(d.name),
    )
    for art_dir in art_dirs:
        files = [f for f in art_dir.rglob("*") if f.is_file() and "__pycache__" not in f.parts]
        if files:
            lines.append(f"### {art_dir.name}")
            for f in files:
                lines.append(f"  - `{f.relative_to(templates_dir)}`")
            lines.append("")
    return "\n".join(lines) if len(lines) > 2 else "No templates found."


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Console-script entry point (``compliance-agent-mcp``)."""
    import argparse

    parser = argparse.ArgumentParser(description="ComplianceAgent MCP Server")
    parser.add_argument(
        "--http", action="store_true", help="Run with HTTP transport instead of stdio"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for HTTP transport (default: 8000)"
    )
    args = parser.parse_args()

    if args.http:
        mcp.run(transport="http", port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
