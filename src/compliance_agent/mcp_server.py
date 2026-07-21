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
import logging
import os
import re
import secrets
import sys
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, AuthProvider

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
from compliance_agent.reporter.sarif_report import render_sarif
from compliance_agent.scanner.engine import HARD_SKIP_DIRS, SCANNABLE_SUFFIXES

logger = logging.getLogger(__name__)
_audit_logger = logging.getLogger(f"{__name__}.audit")

mcp = FastMCP(
    "ComplianceAgent",
    instructions=(
        "EU AI Act compliance scanner for AI projects. "
        "Scan a project directory to check for compliance issues, "
        "generate fix recommendations, compare scans over time, "
        "export results as SARIF for code-scanning tools, "
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

# ---------------------------------------------------------------------------
# Networked-deployment safety controls
#
# stdio transport (the documented default — Claude Desktop, Cursor spawn this
# as a local subprocess) needs none of this: the trust boundary is "whoever
# can run a process on this machine", same as the CLI. --http changes that
# boundary to "whoever can reach this port", so it needs its own auth, an
# optional path allowlist, and resource limits. All three are environment
# variables, never CLI flags, so a bearer token never lands in shell history
# or `ps -ef` output.
# ---------------------------------------------------------------------------

ENV_AUTH_TOKEN = "COMPLIANCE_AGENT_MCP_TOKEN"  # noqa: S105 (name, not a secret)
ENV_ALLOWED_ROOTS = "COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS"
ENV_MAX_FILES = "COMPLIANCE_AGENT_MCP_MAX_FILES"
ENV_TIMEOUT_SECONDS = "COMPLIANCE_AGENT_MCP_TIMEOUT_SECONDS"
ENV_MAX_CONCURRENT_SCANS = "COMPLIANCE_AGENT_MCP_MAX_CONCURRENT_SCANS"
ENV_LOG_LEVEL = "COMPLIANCE_AGENT_MCP_LOG_LEVEL"

_DEFAULT_MAX_FILES = 20_000
_DEFAULT_TIMEOUT_SECONDS = 120.0
_DEFAULT_MAX_CONCURRENT_SCANS = 4


# A per-call timeout alone only bounds one caller's *wait* — Python can't
# forcibly cancel the background thread it leaves running, so repeatedly
# triggering timeouts in --http mode could otherwise accumulate an unbounded
# number of permanently-running threads. This semaphore bounds the number
# actually running at once; a slot is held until its thread truly finishes
# (via the future's done-callback below), not just until the caller stops
# waiting for it. Sized once at import — like a conventional thread-pool
# size — rather than re-read per call the way MAX_FILES/TIMEOUT are.
def _initial_max_concurrent_scans() -> int:
    raw = os.environ.get(ENV_MAX_CONCURRENT_SCANS, "")
    try:
        return int(raw) if raw else _DEFAULT_MAX_CONCURRENT_SCANS
    except ValueError:
        return _DEFAULT_MAX_CONCURRENT_SCANS


_SCAN_SLOTS = threading.BoundedSemaphore(_initial_max_concurrent_scans())

# Hosts that only accept connections from this machine. "0.0.0.0" and a real
# hostname/IP are deliberately excluded — only these three are loopback-only.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class StaticBearerAuthProvider(AuthProvider):
    """Single shared-secret bearer token check, used only for --http mode.

    This is deliberately not an OAuth flow — just a constant-time comparison
    against one token read from an environment variable at startup. That is
    the right amount of auth for a single-tenant, ops-managed deployment
    (one trusted service or team sharing one token); per-user identity,
    scopes, and expiry are out of scope until an actual multi-tenant use case
    asks for them.
    """

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not secrets.compare_digest(token, self._token):
            return None
        return AccessToken(token=token, client_id="http-client", scopes=[])


def _audit(event: str, **fields: object) -> None:
    """Emit one structured audit log line for a security-relevant MCP event.

    Goes through the standard ``logging`` module only — never ``print`` —
    because stdio-transport MCP reserves stdout exclusively for the
    JSON-RPC stream; anything else written to stdout would corrupt the
    protocol. ``main()`` points the root logger at stderr before serving.
    Every call site logs *what* was accessed (a path, a rejection reason),
    not *who* accessed it: under the shared-token auth above there is only
    one caller identity to log, so a per-caller audit trail is future work
    for whenever per-user tokens exist.
    """
    detail = " ".join(f"{key}={value!r}" for key, value in fields.items())
    _audit_logger.info("event=%s %s", event, detail)


def _get_allowed_roots() -> list[Path]:
    """Parse ``COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS`` into resolved directories.

    Read fresh on every call (cheap — a handful of ``Path.resolve()`` calls)
    rather than cached at import time, so tests can ``monkeypatch.setenv`` it
    per-test and a long-running server picks up a change without a restart.
    Unset/empty means "no restriction" — the historical, stdio/local-trust
    behavior that every existing stdio deployment keeps by default.
    """
    raw = os.environ.get(ENV_ALLOWED_ROOTS, "")
    roots: list[Path] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if entry:
            roots.append(Path(entry).expanduser().resolve())
    return roots


def _check_path_allowed(path: Path) -> str | None:
    """Return an error string if ``path`` falls outside the configured allowlist.

    Returns ``None`` (allowed) whenever ``COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS``
    is unset. Both the candidate path and every configured root are resolved
    (symlinks and ``..`` included) before comparison, so a symlink planted
    inside an allowed root can't be used to point back out at the rest of the
    filesystem — a bare string-prefix check would miss exactly that case.
    """
    allowed_roots = _get_allowed_roots()
    if not allowed_roots:
        return None
    resolved = path.resolve()
    for root in allowed_roots:
        if resolved == root or root in resolved.parents:
            return None
    _audit("path_blocked", path=str(resolved))
    allowed_list = ", ".join(str(root) for root in allowed_roots)
    return (
        f"Error: '{resolved}' is outside the allowed roots configured via "
        f"{ENV_ALLOWED_ROOTS} ({allowed_list}). Ask an operator to add this "
        "location to the allowlist."
    )


def _write_text_no_follow(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` without following a symlink at ``path``.

    Narrows (does not fully close — that would need dir_fd-relative opens
    through every path segment) the gap between ``_check_path_allowed``
    resolving a path and the write actually happening: if something replaces
    ``path`` itself with a symlink in between, ``O_NOFOLLOW`` makes the
    open fail with ``ELOOP`` (an ``OSError``, already handled by callers)
    instead of silently writing through it.
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)


def _get_max_files() -> int:
    raw = os.environ.get(ENV_MAX_FILES, "")
    try:
        return int(raw) if raw else _DEFAULT_MAX_FILES
    except ValueError:
        return _DEFAULT_MAX_FILES


def _get_timeout_seconds() -> float:
    raw = os.environ.get(ENV_TIMEOUT_SECONDS, "")
    try:
        return float(raw) if raw else _DEFAULT_TIMEOUT_SECONDS
    except ValueError:
        return _DEFAULT_TIMEOUT_SECONDS


def _project_exceeds_file_limit(project_path: Path, limit: int) -> bool:
    """True as soon as more than ``limit`` scannable-suffix files are found.

    A cheap, approximate pre-flight check — it mirrors the scanner's own
    ``HARD_SKIP_DIRS`` pruning and ``SCANNABLE_SUFFIXES`` filter but not its
    .gitignore/--exclude/--include logic, so it can occasionally admit a
    project the real scan would trim further. That imprecision is fine: this
    guard exists only to catch pathological cases (a whole home directory or
    filesystem root pointed at by mistake, or by a malicious network caller),
    not to predict the real scan's exact file count. Walks with an early exit
    once the limit is crossed, so a massive tree is never fully counted.
    """
    count = 0
    for _root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in HARD_SKIP_DIRS]
        for name in files:
            if Path(name).suffix in SCANNABLE_SUFFIXES:
                count += 1
                if count > limit:
                    return True
    return False


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
            # Filter through the allowlist *before* building the ambiguous-list
            # message: _search_common_locations probes the whole home-folder
            # tree regardless of COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS, so an
            # unfiltered multi-match error would disclose real project/user
            # folder names entirely outside the caller's allowed scope —
            # exactly what the allowlist exists to prevent.
            matches = [m for m in matches if _check_path_allowed(m.resolve()) is None]
            if len(matches) == 1:
                return _finalize_resolved_path(matches[0].resolve())
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
    return _finalize_resolved_path(project_path)


def _finalize_resolved_path(path: Path) -> tuple[Path | None, str | None]:
    """Apply the allowlist check to a path `_resolve_project_path` is about to return.

    Both success branches of `_resolve_project_path` (the bare-name match and
    the literal-path match) funnel through here so the allowlist can never be
    bypassed by adding a future third way of finding a project directory.
    """
    error = _check_path_allowed(path)
    if error:
        return None, error
    return path, None


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

    Two resource guards wrap the actual scan, both configurable via
    environment variables so a legitimately large project isn't stuck with a
    default that's too tight:

    - A file-count pre-check (``_project_exceeds_file_limit``) rejects a
      project outright before any file content is read — cheap protection
      against a whole home directory or filesystem root pointed at by
      mistake (or by a malicious network caller in --http mode).
    - A wall-clock timeout bounds how long a single tool call can block a
      caller. Python cannot forcibly cancel a running thread, so a scan that
      times out keeps running in the background rather than actually
      stopping — this bounds the *caller's* wait, it does not free the
      CPU/memory the stuck scan is using. Good enough to stop one slow
      request from hanging an HTTP client indefinitely; a genuinely hostile
      input needs process-level isolation, which is out of scope here.
    """
    max_files = _get_max_files()
    if _project_exceeds_file_limit(project_path, max_files):
        _audit("scan_rejected_too_large", path=str(project_path), max_files=max_files)
        return None, (
            f"Error: '{project_path}' has more than {max_files} scannable files — "
            f"refusing to scan (limit set by {ENV_MAX_FILES}). Narrow the scan "
            "with `include`/`exclude` glob patterns, or raise the limit if this "
            "project is legitimately this large."
        )

    timeout = _get_timeout_seconds()
    if not _SCAN_SLOTS.acquire(timeout=timeout):
        _audit("scan_rejected_server_busy", path=str(project_path))
        return None, (
            "Error: the server is already running the maximum number of "
            f"concurrent scans (set by {ENV_MAX_CONCURRENT_SCANS}). Try again "
            "shortly."
        )
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        run_pipeline,
        project_path,
        exclude=exclude,
        include=include,
        with_recommendations=with_recommendations,
        declared_tier=declared_tier,
    )
    # Release the slot when the thread actually finishes, not when the
    # caller stops waiting for it — a timed-out caller below must not free
    # up a slot for a new scan while its own stuck thread is still running.
    future.add_done_callback(lambda _f: _SCAN_SLOTS.release())
    try:
        result = future.result(timeout=timeout)
    except FutureTimeoutError:
        # wait=False so this call returns promptly instead of blocking until
        # the stuck scan finishes — see the docstring's timeout caveat.
        executor.shutdown(wait=False, cancel_futures=False)
        _audit("scan_timed_out", path=str(project_path), timeout_seconds=timeout)
        return None, (
            f"Error: scan of '{project_path}' did not finish within "
            f"{timeout:.0f}s (limit set by {ENV_TIMEOUT_SECONDS}). Narrow the "
            "scan with `include`/`exclude`, or raise the limit for a large "
            "project."
        )
    except Exception as exc:
        executor.shutdown(wait=False, cancel_futures=False)
        return None, (
            f"Error: scan failed unexpectedly ({exc}). "
            "This may indicate a bug in ComplianceAgent — please report it."
        )
    executor.shutdown(wait=False)
    return result, None


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
    error = _check_path_allowed(output_path)
    if error:
        return error
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
    except Exception as exc:
        # Every MCP tool must return a clean error string, never a raw
        # traceback — the same rule _run_pipeline_safely enforces for the
        # scan itself. A template-rendering bug here must not escape either.
        return (
            f"Error: writing the {format} report failed unexpectedly ({exc}). "
            "This may indicate a bug in ComplianceAgent — please report it."
        )
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
    _audit("scan_project", path=str(project_path), format=format)

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

    out_path = Path(output).expanduser()
    error = _check_path_allowed(out_path)
    if error:
        return error
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_text_no_follow(out_path, rendered)
    except OSError as exc:
        return f"Error: cannot write report to '{output}' ({exc.strerror or exc})."
    except Exception as exc:
        return (
            f"Error: writing the report failed unexpectedly ({exc}). "
            "This may indicate a bug in ComplianceAgent — please report it."
        )
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
    _audit("get_summary", path=str(project_path))

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
    _audit("recommend_fixes", path=str(project_path), output_dir=output_dir)

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
        error = _check_path_allowed(out_path)
        if error:
            return error
        try:
            written = FixRecommender().export(result.recommendations, out_path)
        except OSError as exc:
            return (
                f"Error: cannot write recommendation files to '{output_dir}' "
                f"({exc.strerror or exc})."
            )
        except Exception as exc:
            return (
                f"Error: writing recommendation files failed unexpectedly ({exc}). "
                "This may indicate a bug in ComplianceAgent — please report it."
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
        error = _check_path_allowed(fpath)
        if error:
            return error
        if not fpath.exists():
            return f"Error: {label} report '{original}' does not exist (resolved to '{fpath}')."
        if not fpath.is_file():
            return f"Error: {label} report '{original}' is a directory, not a file."

    _audit("diff_scans", base=str(base_file), target=str(target_file))

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

    out_path = Path(output).expanduser()
    error = _check_path_allowed(out_path)
    if error:
        return error
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_text_no_follow(out_path, rendered)
    except OSError as exc:
        return f"Error: cannot write diff report to '{output}' ({exc.strerror or exc})."
    except Exception as exc:
        return (
            f"Error: writing the diff report failed unexpectedly ({exc}). "
            "This may indicate a bug in ComplianceAgent — please report it."
        )
    return f"Diff report written to {out_path.resolve()}"


@mcp.tool()
def export_sarif(
    path: str,
    severity: str = "info",
    exclude: list[str] | None = None,
    include: list[str] | None = None,
    output: str | None = None,
) -> str:
    """Run a compliance scan and render the result as a SARIF 2.1.0 log.

    SARIF is the format GitHub's `github/codeql-action/upload-sarif` action
    (and most other code-scanning consumers) expect — findings and gaps show
    up in the repository's Security tab instead of only in a chat reply. Use
    `scan_project` instead for a markdown/json report meant to be read
    directly, or when fix recommendations are wanted (SARIF has no field for
    those). Runs the same scan -> classify -> gaps -> coverage pipeline as
    `scan_project`, minus recommendation generation.

    Args:
        path: Absolute or relative path to the project root directory.
            Prefer an absolute path — a relative path resolves against the
            MCP server process's working directory, not the caller's. If you
            only know the project's *name*, not its location, pass just the
            name — this tool searches common dev-folder locations
            (~/Developer, ~/dev, ~/code, ~/Desktop, and others) first, same
            as `scan_project`.
        severity: Minimum severity to include: one of "info", "warning",
            "high", "critical" (default "info", i.e. everything). Filtering
            only affects what is emitted — nothing about the underlying scan
            changes.
        exclude: Glob patterns for files/directories to skip, e.g.
            ["tests/*", "docs/*", "*.md"]. Combined (not replaced) with any
            excludes declared in the project's compliance.yaml.
        include: If set, only scan paths matching these globs, e.g.
            ["src/**/*.py"]. Combined with compliance.yaml's include list.
        output: Absolute file path to write the SARIF log to, e.g.
            "/Users/me/results.sarif" — the shape `upload-sarif` expects.
            Optional: without it, the SARIF JSON is returned inline instead.

    Returns:
        With `output` given: a short confirmation string naming the absolute
        path the SARIF file was written to. Without it: the SARIF 2.1.0 JSON
        log itself, pretty-printed. A project with zero findings/gaps still
        returns valid SARIF (an empty `results` array), never an empty
        string.

    Limitations:
        This is a heuristic static scan, not a legal compliance
        determination — it can have false positives and false negatives.
        A malformed compliance.yaml in the project is reported as an error
        string rather than raised. SARIF has no concept of fix
        recommendations — use `recommend_fixes` for those.
    """
    project_path, error = _resolve_project_path(path)
    if error:
        return error
    assert project_path is not None  # guaranteed by _resolve_project_path's contract
    _audit("export_sarif", path=str(project_path), output=output)

    severity_enum, error = _parse_severity(severity)
    if error:
        return error

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
        with_recommendations=False,
        declared_tier=config.posture.risk_tier if config else None,
    )
    if error:
        return error
    assert result is not None  # guaranteed by _run_pipeline_safely's contract

    display = _filter_by_severity(result, severity_enum) if severity_enum else result
    rendered = render_sarif(display)

    if not output:
        return rendered

    out_path = Path(output).expanduser()
    error = _check_path_allowed(out_path)
    if error:
        return error
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_text_no_follow(out_path, rendered)
    except OSError as exc:
        return f"Error: cannot write SARIF report to '{output}' ({exc.strerror or exc})."
    except Exception as exc:
        return (
            f"Error: writing the SARIF report failed unexpectedly ({exc}). "
            "This may indicate a bug in ComplianceAgent — please report it."
        )
    return f"SARIF report written to {out_path.resolve()}"


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
        A short string like "ComplianceAgent v0.6.0" — the same version the
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
        "--host",
        default="127.0.0.1",
        help=(
            "Host to bind for --http transport (default: 127.0.0.1, loopback-only). "
            f"Only widen this once {ENV_AUTH_TOKEN} and {ENV_ALLOWED_ROOTS} are "
            "configured — see README's 'MCP Server' section."
        ),
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for HTTP transport (default: 8000)"
    )
    args = parser.parse_args()

    # stdout is reserved for the JSON-RPC stream on stdio transport — every
    # log line, including this module's audit log, must go to stderr instead.
    logging.basicConfig(
        stream=sys.stderr,
        level=os.environ.get(ENV_LOG_LEVEL, "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not args.http:
        mcp.run()
        return

    token = os.environ.get(ENV_AUTH_TOKEN)
    if not token:
        print(
            f"Error: --http requires {ENV_AUTH_TOKEN} to be set to a bearer "
            "token — refusing to start an unauthenticated network-reachable "
            "server. Generate one with:\n"
            '  python3 -c "import secrets; print(secrets.token_urlsafe(32))"',
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not _get_allowed_roots():
        if args.host not in _LOOPBACK_HOSTS:
            # Auth alone (bearer token) is not enough once the server is
            # actually reachable off-box: without an allowlist, any token
            # holder can read/write any path the host process can access.
            # Loopback-only binding is the one case where that's an
            # accepted, deliberate tradeoff for local single-operator use —
            # widening --host is exactly the point at which this must
            # become a hard failure, not a log line that's easy to miss.
            print(
                f"Error: --http --host {args.host} (not loopback-only) requires "
                f"{ENV_ALLOWED_ROOTS} to be set — refusing to expose an "
                "unrestricted filesystem over the network. Set it to a "
                "comma-separated list of allowed project root directories, "
                "or bind to 127.0.0.1 for local-only access.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        logger.warning(
            "%s is not set — this HTTP server can read and write any path "
            "the host process can access. Set it to a comma-separated list "
            "of allowed project root directories before exposing this "
            "beyond your own machine.",
            ENV_ALLOWED_ROOTS,
        )

    mcp.auth = StaticBearerAuthProvider(token)
    mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
