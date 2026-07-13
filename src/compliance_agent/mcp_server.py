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
import re
from collections.abc import Sequence
from pathlib import Path

from fastmcp import FastMCP

from compliance_agent import __version__, get_rules_dir, get_templates_dir
from compliance_agent.config import ConfigError, ProjectConfig, load_config
from compliance_agent.diff import diff_scan_results
from compliance_agent.models.findings import SEVERITY_ORDER, RiskTier, ScanResult, Severity
from compliance_agent.pipeline import run_pipeline
from compliance_agent.recommender.engine import FixRecommender
from compliance_agent.reporter.diff_report import render_diff_markdown
from compliance_agent.reporter.html_report import write_html
from compliance_agent.reporter.json_report import build_envelope
from compliance_agent.reporter.markdown import render_markdown, render_summary
from compliance_agent.reporter.pdf_report import PDFReporter

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
_VALID_FORMATS = ("markdown", "json", "pdf", "html")
# PDF/HTML are binary/large — they get written to disk and the tool returns a
# confirmation + path, never the raw content (a multi-KB self-contained HTML
# file dumped into the LLM's context is not useful, and a PDF can't be
# returned as text at all).
_FILE_ONLY_FORMATS = frozenset({"pdf", "html"})

# Searched (2 levels deep) when a tool is given a bare project name instead of
# a path — e.g. "perch" instead of "/Users/me/Developer/perch" — so an LLM
# doesn't have to blindly guess through common dev folders across several
# turns before asking the user for the exact path.
_COMMON_PROJECT_ROOTS = (
    "~/projects",
    "~/Projects",
    "~/Developer",
    "~/dev",
    "~/code",
    "~/work",
    "~/workspace",
    "~/Documents",
    "~/src",
    "~/repos",
    "~/git",
    "~/Desktop",
)


# ---------------------------------------------------------------------------
# Shared validation helpers — every tool funnels its path/severity/config
# handling through these so error wording stays identical across tools and no
# tool can raise instead of returning a clear error string.
# ---------------------------------------------------------------------------


def _looks_like_bare_name(path: str) -> bool:
    """True for a bare project name like "perch" — not a path.

    A path separator, a leading "~", or "." / ".." means the caller already
    gave (or meant to give) an explicit path — never second-guess that with a
    common-locations search.
    """
    return "/" not in path and "\\" not in path and path not in (".", "..", "") and path[0] != "~"


def _search_common_locations(name: str) -> list[Path]:
    """Search common dev-folder locations for a directory matching ``name``.

    Checks each root in ``_COMMON_PROJECT_ROOTS`` plus each root's immediate
    subdirectories (so ``~/Desktop/Playground/perch`` is found via the
    ``~/Desktop`` root) — bounded to two directory-listing levels, never
    descending into a matched project's own contents, so this stays fast.
    """
    matches: list[Path] = []
    seen: set[Path] = set()

    def _add(candidate: Path) -> None:
        if candidate.is_dir():
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                matches.append(candidate)

    for root_str in _COMMON_PROJECT_ROOTS:
        root = Path(root_str).expanduser()
        if not root.is_dir():
            continue
        _add(root / name)
        try:
            subdirs = [c for c in root.iterdir() if c.is_dir()]
        except OSError:
            continue
        for sub in subdirs:
            _add(sub / name)
    return matches


def _resolve_project_path(path: str) -> tuple[Path | None, str | None]:
    """Resolve and validate a project directory path.

    Returns ``(resolved_path, None)`` on success or ``(None, error_message)``
    when the path does not exist or is not a directory. When given a bare
    project name that doesn't exist as a literal relative/absolute path,
    falls back to searching common dev-folder locations (see
    ``_search_common_locations``) before giving up.
    """
    project_path = Path(path).expanduser().resolve()
    if not project_path.exists():
        if _looks_like_bare_name(path):
            matches = _search_common_locations(path)
            if len(matches) == 1:
                return matches[0].resolve(), None
            if len(matches) > 1:
                options = "\n".join(f"  - {m.resolve()}" for m in matches)
                return None, (
                    f"Error: '{path}' is ambiguous — found {len(matches)} matching "
                    f"folders:\n{options}\nPass the exact absolute path you want."
                )
            return None, (
                f"Error: no folder named '{path}' exists here, and none was found "
                "in common project locations (~/projects, ~/Developer, ~/dev, "
                "~/code, ~/work, ~/Desktop, and others) either. "
                "Give the exact absolute path, e.g. /Users/you/Developer/perch."
            )
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


_ARTICLE_LABEL_RE = re.compile(r"Art\.\s*(\d+)")


def _article_label_sort_key(label: str) -> tuple[int, str]:
    """Sort ``gap.article`` labels ("Art. 5", "Art. 53") numerically.

    Same bug class as ``_article_sort_key``, just on the "Art. N" label
    format gaps use instead of the "artN" template-directory format — a
    plain string sort puts "Art. 11" before "Art. 5" and "Art. 53" before
    "Art. 6". A label that doesn't match the expected format sorts last
    rather than crashing.
    """
    match = _ARTICLE_LABEL_RE.search(label)
    if match:
        return (int(match.group(1)), label)
    return (10**9, label)


def _run_pipeline_safely(
    project_path: Path,
    *,
    exclude: Sequence[str] = (),
    include: Sequence[str] = (),
    with_recommendations: bool = False,
    declared_tier: RiskTier | None = None,
) -> tuple[ScanResult | None, str | None]:
    """Run the scan pipeline, converting any unexpected exception to an error string.

    The scanner engine already isolates per-file detector crashes into
    ``scan_errors``, and the classifier/analyzer/recommender only operate on
    validated in-memory models, so a pipeline-level exception should be rare —
    but an MCP tool must never let one escape as a raw traceback instead of a
    clean error string.
    """
    try:
        result = run_pipeline(
            project_path,
            exclude=exclude,
            include=include,
            with_recommendations=with_recommendations,
            declared_tier=declared_tier,
        )
        return result, None
    except Exception as exc:
        return None, (
            f"Error: scan failed unexpectedly ({exc}). "
            "This may indicate a bug in ComplianceAgent — please report it."
        )


def _truncate_at_line_boundary(content: str, limit: int) -> str:
    """Truncate ``content`` to at most ``limit`` chars without cutting mid-line.

    A raw ``content[:limit]`` slice can land in the middle of a YAML line
    (mangling it) and gives no indication that anything was cut. This backs
    up to the last newline before the limit and appends a truncation note
    with the omitted line count, when truncation actually happened.
    """
    if len(content) <= limit:
        return content
    truncated = content[:limit]
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]
    omitted_lines = content[len(truncated) :].count("\n")
    return f"{truncated}\n\n... ({omitted_lines} more line(s) truncated) ..."


def _write_report_file(result: ScanResult, format: str, output: str) -> str:
    """Write a PDF or HTML report to disk. Returns a confirmation or error string.

    Shared by every tool that offers ``format="pdf"``/``"html"`` so the
    file-writing, path-resolution, and error wording stay identical.
    """
    output_path = Path(output).expanduser()
    try:
        if format == "pdf":
            written = PDFReporter().generate(result, output_path)
            kind = "PDF report"
        else:
            written = write_html(result, output_path)
            kind = "HTML dashboard"
    except RuntimeError as exc:
        # WeasyPrint's native libraries (pango/gobject) are missing — the
        # exception message already explains what to install.
        return f"Error: {exc}"
    except OSError as exc:
        return f"Error: cannot write {format} report to '{output}' ({exc.strerror or exc})."
    return f"{kind} written to {written.resolve()}"


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
    output: str | None = None,
) -> str:
    """Run a full EU AI Act compliance scan on a project directory, from scratch.

    Give it a project path and nothing else is required: it always runs the
    complete pipeline fresh (scan -> classify risk tier -> find compliance
    gaps -> compute obligation coverage -> generate fix recommendations) —
    there is no setup step and no cached/stale state to worry about. This is
    the most expensive of the tools — for a quick check use ``get_summary``
    instead. compliance.yaml defaults (excludes, declared risk tier) are
    loaded and merged in automatically if the project has one.

    Args:
        path: Absolute or relative path to the project root directory, e.g.
            "/Users/me/my-ai-app". Prefer an absolute path: a relative path
            resolves against the MCP server process's working directory, not
            the caller's, which is usually not what you want. If you only
            know the project's *name*, not its location (e.g. "perch"),
            pass just the name — this tool searches common dev-folder
            locations (~/Developer, ~/dev, ~/code, ~/Desktop, and others,
            including one level of subdirectories) before giving up, so you
            don't need to guess paths across several tool calls.
        severity: Minimum severity to include in the report: one of
            "info", "warning", "high", "critical" (default "info", i.e. show
            everything). Filtering only affects what is displayed — nothing
            about the underlying scan changes.
        exclude: Glob patterns for files/directories to skip, e.g.
            ["tests/*", "docs/*", "*.md"]. Combined (not replaced) with any
            excludes declared in the project's compliance.yaml.
        include: If set, only scan paths matching these globs, e.g.
            ["src/**/*.py"]. Combined with compliance.yaml's include list.
        format: One of "markdown" (human-readable text), "json" (structured,
            versioned envelope — the same shape the CLI's ``--format json``
            produces, suitable for feeding into ``diff_scans`` later), "pdf"
            (audit-ready PDF), or "html" (self-contained interactive
            dashboard file, openable in any browser).
        output: Absolute file path to write the report to, e.g.
            "/Users/me/report.pdf". **Required** for format="pdf"/"html"
            (a PDF can't be returned as text, and a full HTML dashboard is
            too large to usefully dump into a conversation) — pass an
            absolute path there. Optional for "markdown"/"json": if given,
            the report is written to that file instead of being returned
            inline (useful for a report you want to keep or share).

    Returns:
        For "markdown"/"json" without ``output``: the report content
        directly (a project with zero findings still returns a full report
        with a "Findings: none" summary line — never an empty string). If
        ``output`` is given, or format is "pdf"/"html": a short confirmation
        string naming the absolute path the file was written to.

    Limitations:
        This is a heuristic static scan, not a legal compliance
        determination — it can have false positives and false negatives.
        A malformed compliance.yaml in the project is reported as an error
        string rather than raised. Generating a PDF requires WeasyPrint's
        native libraries (pango/gobject) to be installed on the machine
        running the server; if they're missing, the error message explains
        what to install.
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

    if format in _FILE_ONLY_FORMATS and not output:
        return (
            f"Error: format='{format}' produces a file, not text — pass `output` "
            f"with an absolute path, e.g. output='/Users/me/report.{format}'."
        )

    config, error = _load_project_config(project_path)
    if error:
        return error

    merged_exclude = list(exclude or [])
    merged_include = list(include or [])
    if config and config.scan:
        merged_exclude = _merge_unique(merged_exclude, config.scan.exclude)
        merged_include = _merge_unique(merged_include, config.scan.include)

    result, error = _run_pipeline_safely(
        project_path,
        exclude=merged_exclude,
        include=merged_include,
        with_recommendations=True,
        declared_tier=config.posture.risk_tier if config else None,
    )
    if error:
        return error
    assert result is not None  # guaranteed by _run_pipeline_safely's contract

    display = _filter_by_severity(result, severity_enum) if severity_enum else result

    if format in _FILE_ONLY_FORMATS:
        assert output is not None  # validated above
        return _write_report_file(display, format, output)

    rendered = (
        json.dumps(build_envelope(display), indent=2, ensure_ascii=False)
        if format == "json"
        else render_markdown(display, summary_source=result)
    )
    if not output:
        return rendered

    try:
        out_path = Path(output).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    except OSError as exc:
        return f"Error: cannot write report to '{output}' ({exc.strerror or exc})."
    return f"Report written to {out_path.resolve()}"


@mcp.tool()
def get_summary(path: str) -> str:
    """Get a quick, lightweight compliance summary for a project.

    Runs the scan and classification steps but skips fix-recommendation
    generation, so it is faster than ``scan_project``. Use this for a quick
    "how does this project look" check before running the full scan.

    Args:
        path: Absolute or relative path to the project root directory. Prefer
            an absolute path — a relative path resolves against the MCP
            server process's working directory, not the caller's. If you
            only know the project's *name*, not its location, pass just the
            name — this tool searches common dev-folder locations
            (~/Developer, ~/dev, ~/code, ~/Desktop, and others) first.

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

    result, error = _run_pipeline_safely(
        project_path,
        exclude=config.scan.exclude if config else (),
        include=config.scan.include if config else (),
        with_recommendations=False,
        declared_tier=config.posture.risk_tier if config else None,
    )
    if error:
        return error
    assert result is not None  # guaranteed by _run_pipeline_safely's contract
    return render_summary(result)


@mcp.tool()
def recommend_fixes(path: str, output_dir: str | None = None) -> str:
    """Generate concrete, copy-paste fix recommendations for a project's compliance gaps.

    Runs the full pipeline with recommendation generation enabled, then
    returns the recommendations section — each one naming the EU AI Act
    article it addresses, the fix template file to use, and numbered steps to
    apply it.

    Args:
        path: Absolute or relative path to the project root directory. Prefer
            an absolute path — a relative path resolves against the MCP
            server process's working directory, not the caller's. If you
            only know the project's *name*, not its location, pass just the
            name — this tool searches common dev-folder locations
            (~/Developer, ~/dev, ~/code, ~/Desktop, and others) first.
        output_dir: If given, an absolute path to a directory to copy the
            actual fix template files into (preserving their `templates/...`
            structure) plus a RECOMMENDATIONS.md with the same steps — the
            same files ``compliance-agent recommend . --output ./fixes``
            writes. Without it, this tool only returns recommendation text;
            with it, you get real, ready-to-edit files in your project.

    Returns:
        A Markdown-formatted list of fix recommendations with steps, or a
        clear "nothing to recommend" message when the project has no
        compliance gaps. If gaps exist but no fix template covers them yet,
        says so explicitly and names the uncovered articles rather than
        silently returning nothing. When ``output_dir`` is given and files
        were written, a line naming how many files and where is appended.

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

    result, error = _run_pipeline_safely(
        project_path,
        exclude=config.scan.exclude if config else (),
        include=config.scan.include if config else (),
        with_recommendations=True,
        declared_tier=config.posture.risk_tier if config else None,
    )
    if error:
        return error
    assert result is not None  # guaranteed by _run_pipeline_safely's contract

    if not result.recommendations and not result.gaps:
        return "No compliance gaps found — nothing to recommend."
    if not result.recommendations:
        articles = sorted({gap.article for gap in result.gaps}, key=_article_label_sort_key)
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

    if output_dir:
        out_path = Path(output_dir).expanduser()
        try:
            written = FixRecommender().export(result.recommendations, out_path)
        except OSError as exc:
            return (
                f"Error: cannot write recommendation files to '{output_dir}' "
                f"({exc.strerror or exc})."
            )
        out_path = out_path.resolve()
        lines.append(f"**Wrote {len(written)} file(s) to {out_path}**")
        lines.append(f"Open `{out_path / 'RECOMMENDATIONS.md'}` for step-by-step instructions.")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def diff_scans(
    base_path: str,
    target_path: str,
    format: str = "markdown",
    output: str | None = None,
) -> str:
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
        format: "markdown" for a human-readable comparison (default), or
            "json" for the structured diff (tier movement, gap/finding lists,
            requirements totals) as a JSON object — the same shape the CLI's
            ``compliance-agent diff --format json`` produces.
        output: Absolute file path to write the diff report to instead of
            returning it inline, e.g. "/Users/me/diff.md".

    Returns:
        A Markdown summary (risk-tier movement, gaps resolved/new/changed,
        findings added/removed/unchanged, requirements-met ratio) or a JSON
        string, depending on ``format``. If ``output`` is given, a short
        confirmation string naming the absolute path instead.

    Limitations:
        Both files must exist and be valid ComplianceAgent JSON report
        envelopes (containing a top-level "scan_result" key); anything else
        — a missing file, plain text, unrelated JSON, or a report from an
        incompatible schema version — returns a clear error string instead of
        raising.
    """
    if format not in ("markdown", "json"):
        return f"Error: invalid format '{format}'. Valid options: markdown, json."

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
    rendered = (
        json.dumps(diff.model_dump(mode="json"), indent=2, ensure_ascii=False)
        if format == "json"
        else render_diff_markdown(diff, base_path, target_path)
    )

    if not output:
        return rendered

    try:
        out_path = Path(output).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    except OSError as exc:
        return f"Error: cannot write diff report to '{output}' ({exc.strerror or exc})."
    return f"Diff report written to {out_path.resolve()}"


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
                f"{_truncate_at_line_boundary(content, 2000)}"
            )

    if article_number == 6:
        annex3 = rules_dir / "annex3.yaml"
        if annex3.is_file():
            content = annex3.read_text(encoding="utf-8")
            return (
                "## Article 6 — High-Risk AI Systems\n\n"
                "Defines which AI systems are classified as high-risk.\n\n"
                f"Rules file: `rules/annex3.yaml`\n\n{_truncate_at_line_boundary(content, 2000)}"
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


@mcp.tool()
def get_version() -> str:
    """Return the installed ComplianceAgent version.

    Returns:
        A short string like "ComplianceAgent v0.4.0" — the same version the
        CLI's ``compliance-agent version`` command reports.

    Limitations:
        This is a local, offline lookup only — it does not check PyPI for a
        newer version (unlike the CLI command, which does when run
        interactively).
    """
    return f"ComplianceAgent v{__version__}"


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
