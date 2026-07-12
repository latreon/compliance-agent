"""Typer CLI entry point for ComplianceAgent."""

import logging
import sys
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler

from compliance_agent import __version__, updates
from compliance_agent.config import ConfigError, ProjectConfig, load_config
from compliance_agent.models.findings import SEVERITY_ORDER, ScanResult, Severity
from compliance_agent.pipeline import run_pipeline
from compliance_agent.recommender.engine import FixRecommender
from compliance_agent.reporter import terminal
from compliance_agent.reporter.json_report import render_json
from compliance_agent.reporter.markdown import (
    render_markdown,
    render_recommendations,
    render_summary,
)
from compliance_agent.reporter.sarif_report import render_sarif

app = typer.Typer(
    name="compliance-agent",
    help="EU AI Act Compliance Scanner for AI Projects",
    no_args_is_help=False,
)
console = Console()
logger = logging.getLogger(__name__)

VALID_FORMATS = {"markdown", "json"}
SCAN_FORMATS = {"markdown", "json", "pdf", "html", "sarif"}
REPORT_FORMATS = {"markdown", "pdf", "html"}
# Formats whose primary output is a machine-readable stream/file — no
# spinners, no colored "next steps" coaching.
MACHINE_FORMATS = {"json", "sarif"}


def _resolve_project_dir(path: str, out: Console, command: str) -> Path:
    """Resolve a project path, exiting (code 2) with guidance if it is not a dir.

    Shared by scan/recommend/report so the existence, is-a-directory, and error
    wording stay identical across every command.
    """
    project_path = Path(path).resolve()
    if not project_path.exists():
        out.print(
            f"[red]Error:[/red] path '{path}' does not exist (resolved to {project_path}).\n"
            f"Check the path and try again, e.g.: compliance-agent {command} ./my-project"
        )
        raise typer.Exit(code=2)
    if not project_path.is_dir():
        out.print(
            f"[red]Error:[/red] '{path}' is a file, not a folder. "
            f"Point ComplianceAgent at a project directory, e.g.: "
            f"compliance-agent {command} ./my-project"
        )
        raise typer.Exit(code=2)
    return project_path


def _check_format(format: str, allowed: set[str], out: Console) -> None:
    """Validate an output format against the allowed set, exiting (code 2) if not."""
    if format not in allowed:
        options = sorted(allowed)
        out.print(
            f"[red]Error:[/red] invalid format '{format}'. "
            f"Use one of: {', '.join(options)}. "
            f"Example: --format {options[0]}"
        )
        raise typer.Exit(code=2)


def _load_project_config(project_path: Path, out: Console) -> ProjectConfig | None:
    """Load compliance.yaml for a project, exiting (code 2) when it is broken.

    A malformed config is a hard error, never a silent fallback: a typo in
    ``fail_on`` must not quietly disable a CI compliance gate.
    """
    try:
        return load_config(project_path)
    except ConfigError as exc:
        out.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(code=2) from exc


def _configure_logging(verbose: bool) -> None:
    """Route library warnings/errors through Rich (stderr) instead of the

    default ``lastResort`` handler, which printed raw ``WARNING:...`` lines
    disconnected from the report. ``--verbose`` lowers the level to INFO.
    """
    level = logging.INFO if verbose else logging.WARNING
    handler = RichHandler(
        console=Console(stderr=True),
        show_time=False,
        show_path=False,
        rich_tracebacks=True,
    )
    root = logging.getLogger("compliance_agent")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False


def _show_version() -> None:
    """Print the version and, when interactive, whether an update is available."""
    console.print(f"ComplianceAgent v{__version__}")
    # Only reach the network for a real terminal, and never when disabled.
    if not sys.stdout.isatty() or updates.update_check_disabled():
        return
    latest = updates.latest_version()
    if latest and updates.is_newer(latest, __version__):
        console.print(
            f"[yellow]⚠ Update available: v{latest}[/yellow] — "
            "run [bold]compliance-agent upgrade[/bold] to update."
        )
    elif latest:
        console.print("[dim]You are on the latest version.[/dim]")


def _version_flag(value: bool) -> None:
    if value:
        _show_version()
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version (and any available update) and exit.",
        is_eager=True,
        callback=_version_flag,
    ),
) -> None:
    """Check if your AI project follows EU rules — run `compliance-agent scan .`."""
    # Bare `compliance-agent`: show version + update status, then the command list.
    if ctx.invoked_subcommand is None:
        _show_version()
        console.print()
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def scan(
    path: str = typer.Argument(".", help="The folder to check. Use '.' for the current folder."),
    format: str = typer.Option(
        None,
        "--format",
        "-f",
        help="Output type: 'markdown' (for reading), 'json' (for computers), "
        "'sarif' (GitHub code scanning), 'pdf' (for sharing), "
        "'html' (interactive dashboard file). Default: markdown.",
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Where to save the report file (PDF, Markdown, or HTML)."
    ),
    fail_on: str = typer.Option(
        None,
        "--fail-on",
        help="Exit with an error code if issues this important or higher are found "
        "(info, warning, high, critical). Use in CI to block a build.",
    ),
    exclude: list[str] = typer.Option(
        None,
        "--exclude",
        help="Skip folders. Example: --exclude 'tests/*' --exclude 'docs/*'",
    ),
    include: list[str] = typer.Option(
        None, "--include", help="Only check folders matching this pattern (repeatable)."
    ),
    severity: str = typer.Option(
        None,
        "--severity",
        "-s",
        help="Only show issues this important or higher: 'info', 'warning', 'high', 'critical'.",
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Turn off colored output."),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Show only the summary, not the details."
    ),
    fix: bool = typer.Option(False, "--fix", help="Show how to fix each problem."),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="For automated pipelines: plain output, no color. "
        "Pair with --fail-on to block a build when issues are found.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show extra detail about what was checked."
    ),
    no_update_check: bool = typer.Option(
        False, "--no-update-check", help="Do not check PyPI for a newer version."
    ),
) -> None:
    """Check if your AI project follows EU rules.

    Examples:

      compliance-agent scan .                    # Basic check

      compliance-agent scan . --format pdf       # Save as a shareable PDF

      compliance-agent scan . --severity high    # Only serious issues

      compliance-agent scan . --fix              # Show how to fix problems

      compliance-agent scan . --format sarif -o results.sarif   # GitHub code scanning

    Defaults for these flags can live in a compliance.yaml at the project
    root — see the README's "Project config file" section.
    """
    if ci:
        no_color = True
        quiet = True
    _configure_logging(verbose)
    out = Console(no_color=no_color) if no_color else console
    project_path = _resolve_project_dir(path, out, "scan")

    # compliance.yaml supplies defaults; explicit CLI flags always win.
    config = _load_project_config(project_path, out)
    scan_defaults = config.scan if config else None
    if scan_defaults:
        if not format and scan_defaults.format:
            format = scan_defaults.format
        if not output and scan_defaults.output:
            output = scan_defaults.output
        if not fail_on and scan_defaults.fail_on:
            fail_on = scan_defaults.fail_on.value
        if not severity and scan_defaults.severity:
            severity = scan_defaults.severity.value
        exclude = exclude or list(scan_defaults.exclude)
        include = include or list(scan_defaults.include)
    format = format or "markdown"

    _check_format(format, SCAN_FORMATS, out)
    fail_threshold = _parse_severity(fail_on, out) if fail_on else None
    show_threshold = _parse_severity(severity, out) if severity else None

    if verbose:
        out.print(f"Scanning [bold]{project_path}[/bold] ...")
        if config and config.source_path:
            logger.info("Using project config: %s", config.source_path)

    # Show a live spinner only for interactive terminal runs — never when the
    # output is piped, machine-readable, or running in CI (would corrupt output).
    interactive = format not in MACHINE_FORMATS and not ci and sys.stdout.isatty()
    with _status(out, "Analyzing project for EU AI Act compliance...", active=interactive):
        result = run_pipeline(
            project_path,
            exclude=exclude or [],
            include=include or [],
            with_recommendations=fix or format in {"pdf", "html"},
            declared_tier=config.posture.risk_tier if config else None,
        )

    display = _filter_by_severity(result, show_threshold) if show_threshold else result

    if verbose:
        logger.info(
            "Scan finished: %d file(s), risk tier %s, %d finding(s), %d gap(s)",
            result.files_scanned,
            result.risk_tier.value if result.risk_tier else "n/a",
            len(result.findings),
            len(result.gaps),
        )
        if result.scan_errors:
            logger.info("%d file(s) could not be fully analyzed", len(result.scan_errors))

    # `markdown` is the readable format. Interactively it renders as the Rich
    # terminal report; but when piped to a file or given --output, emit *raw*
    # Markdown (box-drawing art is useless in a .md file). --ci/--quiet keep
    # their own summary formats.
    raw_markdown = format == "markdown" and (
        output is not None or (not ci and not quiet and not sys.stdout.isatty())
    )

    if format == "pdf":
        pdf_path = _write_pdf(out, display, output)
        out.print(f"[green]Report saved to:[/green] {pdf_path}")
    elif format == "html":
        html_path = _write_html(out, display, output)
        out.print(f"[green]Dashboard saved to:[/green] {html_path.resolve()}")
    elif format in MACHINE_FORMATS:
        rendered = render_sarif(display) if format == "sarif" else render_json(display)
        if output:
            machine_path = _write_text_report(out, rendered, Path(output), format)
            out.print(f"[green]Report saved to:[/green] {machine_path.resolve()}")
        else:
            # plain print keeps output machine-parseable (no Rich wrapping)
            typer.echo(rendered)
    elif raw_markdown:
        md = render_markdown(display, summary_source=result)
        if output:
            md_path = Path(output)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(md, encoding="utf-8")
            out.print(f"[green]Report saved to:[/green] {md_path.resolve()}")
        else:
            typer.echo(md)
    elif ci:
        # CI logs stay clean: plain-text summary, no boxes or color. Summary
        # counts come from the full result so --severity never understates totals.
        typer.echo(render_summary(result))
    elif quiet:
        terminal.print_summary(out, display, summary_source=result)
    else:
        terminal.render_report(out, display, summary_source=result)

    # Human-friendly next steps — skip for machine/file output
    # (json/sarif/pdf/html), CI runs, and raw Markdown (would corrupt a piped
    # .md stream or saved file).
    if format not in ({"pdf", "html"} | MACHINE_FORMATS) and not ci and not raw_markdown:
        _print_next_steps(out, result, path)
        if interactive and not no_update_check:
            _notify_update(out)

    # fail-on is evaluated on the FULL result, not the severity-filtered view
    if fail_threshold is not None and _should_fail(result, fail_threshold):
        raise typer.Exit(code=1)


@app.command()
def recommend(
    path: str = typer.Argument(".", help="Project path to analyze"),
    output_dir: str = typer.Option(
        None, "--output", "-o", help="Directory to write recommendation files"
    ),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown, json"),
) -> None:
    """Generate fix recommendations for compliance gaps."""
    _configure_logging(False)
    project_path = _resolve_project_dir(path, console, "recommend")
    _check_format(format, VALID_FORMATS, console)

    result = _analyze_project(project_path, _load_project_config(project_path, console))

    recommender = FixRecommender()
    recommendations = recommender.recommend(result)
    result = result.model_copy(update={"recommendations": recommendations})

    if format == "json":
        typer.echo(render_json(result))
    elif not recommendations and not result.gaps:
        console.print("No compliance gaps found — nothing to recommend.")
    elif not recommendations:
        # Gaps exist but none map to a fix template yet — never claim "clean".
        articles = sorted({gap.article for gap in result.gaps})
        console.print(
            f"[yellow]Found {len(result.gaps)} compliance gap(s)[/yellow], but no "
            "copy-paste fix template is available yet for: "
            f"{', '.join(articles)}.\n"
            "Run [bold]compliance-agent scan .[/bold] to see the full details of each gap."
        )
    else:
        console.print(render_recommendations(result))
        if not output_dir:
            console.print(
                "[dim]Tip: add --output ./fixes to copy these templates into your project.[/dim]"
            )

    if output_dir and recommendations:
        written = recommender.export(recommendations, Path(output_dir))
        out_path = Path(output_dir).resolve()
        console.print(f"\n[green]Wrote {len(written)} file(s) to {out_path}[/green]")
        console.print(
            f"[dim]Next: open {out_path / 'RECOMMENDATIONS.md'} for "
            "step-by-step instructions.[/dim]"
        )


def _load_envelope_result(path_str: str, out: Console) -> ScanResult:
    """Load a ScanResult from a JSON report envelope, exiting (code 2) on error."""
    import json

    path = Path(path_str)
    if not path.is_file():
        out.print(
            f"[red]Error:[/red] report file '{path_str}' not found.\n"
            "Pass a JSON report produced by: compliance-agent scan . --format json -o report.json"
        )
        raise typer.Exit(code=2)
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        return ScanResult.model_validate(envelope["scan_result"])
    except (OSError, ValueError, KeyError) as exc:
        out.print(
            f"[red]Error:[/red] '{path_str}' is not a valid ComplianceAgent JSON report ({exc}).\n"
            "Regenerate it with: compliance-agent scan . --format json -o report.json"
        )
        raise typer.Exit(code=2) from exc


@app.command()
def diff(
    base: str = typer.Argument(..., help="Earlier JSON report (the baseline to compare against)."),
    target: str = typer.Argument(..., help="Later JSON report (the new scan to compare)."),
    format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: 'markdown' (for reading) or 'json'."
    ),
    fail_on_regression: bool = typer.Option(
        False,
        "--fail-on-regression",
        help="Exit with an error code if compliance regressed (new gaps or a higher risk tier). "
        "Use in CI to block a change that makes compliance worse.",
    ),
) -> None:
    """Compare two scans to see whether compliance improved or regressed.

    Both arguments are JSON reports from `scan --format json`:

      compliance-agent scan . --format json -o before.json

      # ...make changes...

      compliance-agent scan . --format json -o after.json

      compliance-agent diff before.json after.json
    """
    from compliance_agent.diff import MIXED, REGRESSED, diff_scan_results
    from compliance_agent.reporter.diff_report import render_diff_markdown

    _check_format(format, VALID_FORMATS, console)
    base_result = _load_envelope_result(base, console)
    target_result = _load_envelope_result(target, console)
    result = diff_scan_results(base_result, target_result)

    if format == "json":
        import json

        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    else:
        typer.echo(render_diff_markdown(result, base, target))

    if fail_on_regression and result.verdict in (REGRESSED, MIXED):
        raise typer.Exit(code=1)


@app.command()
def report(
    path: str = typer.Argument(".", help="Project path"),
    format: str = typer.Option("pdf", "--format", "-f", help="Report format: pdf, markdown, html"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Generate a compliance report file (PDF, Markdown, or HTML dashboard)."""
    _configure_logging(False)
    project_path = _resolve_project_dir(path, console, "report")
    _check_format(format, REPORT_FORMATS, console)

    result = _analyze_project(project_path, _load_project_config(project_path, console))
    result = result.model_copy(update={"recommendations": FixRecommender().recommend(result)})

    if format == "pdf":
        report_path = _write_pdf(console, result, output)
    elif format == "html":
        report_path = _write_html(console, result, output)
    else:
        report_path = Path(output or f"compliance-report-{project_path.name}.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_markdown(result), encoding="utf-8")
    console.print(f"[green]Report saved to:[/green] {report_path.resolve()}")


def _analyze_project(project_path: Path, config: ProjectConfig | None = None) -> ScanResult:
    """Run the full pipeline: scan -> classify -> gaps + coverage.

    Honors the project's compliance.yaml (exclusions, declared risk tier) so
    ``recommend`` and ``report`` see the same project as ``scan``.
    """
    return run_pipeline(
        project_path,
        exclude=config.scan.exclude if config else (),
        include=config.scan.include if config else (),
        declared_tier=config.posture.risk_tier if config else None,
    )


def _status(out: Console, message: str, *, active: bool) -> AbstractContextManager:
    """A live spinner for interactive runs; a no-op context otherwise."""
    if active:
        return out.status(message, spinner="dots")
    return nullcontext()


def _write_pdf(out: Console, result: ScanResult, output: str | None) -> Path:
    """Generate the PDF report, exiting with a helpful message on failure."""
    from compliance_agent.reporter.pdf_report import PDFReporter

    try:
        return PDFReporter().generate(result, Path(output) if output else None)
    except RuntimeError as exc:
        # Missing native libraries — the exception already explains how to fix it.
        out.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    except OSError as exc:
        target = output or f"compliance-report-{Path(result.project_path).name}.pdf"
        out.print(
            f"[red]Error:[/red] Cannot write the report to '{target}' ({exc.strerror or exc}).\n"
            "Try a different location, e.g.: "
            "compliance-agent scan . --format pdf --output ~/report.pdf"
        )
        raise typer.Exit(code=2) from exc


def _write_text_report(out: Console, content: str, output_path: Path, format: str) -> Path:
    """Write a text-format report (json/sarif) to disk with friendly errors."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        out.print(
            f"[red]Error:[/red] Cannot write the report to '{output_path}' "
            f"({exc.strerror or exc}).\n"
            f"Try a different location, e.g.: "
            f"compliance-agent scan . --format {format} --output ~/report.{format}"
        )
        raise typer.Exit(code=2) from exc
    return output_path


def _write_html(out: Console, result: ScanResult, output: str | None) -> Path:
    """Write the self-contained HTML dashboard, exiting helpfully on failure."""
    from compliance_agent.reporter.html_report import write_html

    try:
        return write_html(result, Path(output) if output else None)
    except OSError as exc:
        target = output or f"compliance-dashboard-{Path(result.project_path).name}.html"
        out.print(
            f"[red]Error:[/red] Cannot write the dashboard to '{target}' "
            f"({exc.strerror or exc}).\n"
            "Try a different location, e.g.: "
            "compliance-agent scan . --format html --output ~/dashboard.html"
        )
        raise typer.Exit(code=2) from exc


@app.command()
def serve(
    path: str = typer.Argument(".", help="Project folder to serve the dashboard for."),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Interface to bind. Keep the localhost default — the dashboard has no auth.",
    ),
    port: int = typer.Option(8420, "--port", "-p", help="Port to listen on."),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Do not open the dashboard in a browser automatically."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show server logs."),
) -> None:
    """Open the local compliance dashboard (scan, browse results, track history).

    Requires the 'web' extra — install with:

      uv tool install 'compliance-agent\\[web]'   or   pip install 'compliance-agent\\[web]'
    """
    _configure_logging(verbose)
    project_path = _resolve_project_dir(path, console, "serve")
    # Fail fast on a broken compliance.yaml — better a clear startup error
    # than a 422 surfacing mid-scan in the dashboard.
    _load_project_config(project_path, console)

    try:
        import uvicorn

        from compliance_agent.web.app import create_app
    except ImportError as exc:
        console.print(
            "[red]Error:[/red] the web dashboard requires the 'web' extra.\n"
            "Install it with: [bold]uv tool install 'compliance-agent\\[web]'[/bold] "
            "or [bold]pip install 'compliance-agent\\[web]'[/bold]"
        )
        raise typer.Exit(code=2) from exc

    url = f"http://{host}:{port}/"
    console.print(f"Serving the compliance dashboard for [bold]{project_path}[/bold]")
    console.print(f"[green]Open:[/green] {url}  (Ctrl+C to stop)")
    if not no_browser and sys.stdout.isatty():
        import threading
        import webbrowser

        # Fire after uvicorn has had a moment to bind the socket.
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()

    uvicorn.run(
        create_app(project_path, host=host),
        host=host,
        port=port,
        log_level="info" if verbose else "warning",
    )


@app.command()
def version() -> None:
    """Show the installed version (and whether an update is available)."""
    _show_version()


@app.command()
def upgrade(
    version: str = typer.Argument(
        "latest", help="Version to install: 'latest' (default) or an exact one like 0.1.2."
    ),
) -> None:
    """Upgrade ComplianceAgent to the latest (or a specific) version.

    Examples:

      compliance-agent upgrade          # upgrade to the latest release

      compliance-agent upgrade 0.1.2    # install a specific version
    """
    if version != "latest" and not updates.VERSION_RE.match(version):
        console.print(
            f"[red]Error:[/red] invalid version '{version}'. "
            "Use 'latest' or an exact version like 0.1.2."
        )
        raise typer.Exit(code=2)

    target = "the latest version" if version == "latest" else f"version {version}"
    cmd = updates.build_upgrade_command(version)
    console.print(f"Upgrading ComplianceAgent to {target} ...")
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    code = updates.run_upgrade(version)
    if code == 0:
        console.print("[green]Done.[/green] Run [bold]compliance-agent version[/bold] to confirm.")
    else:
        console.print(
            f"[red]Upgrade failed (exit {code}).[/red] "
            "Upgrade manually, e.g.: pip install --upgrade compliance-agent"
        )
        raise typer.Exit(code=code)


def _notify_update(out: Console) -> None:
    """Print a one-line notice if a newer version is on PyPI (best-effort)."""
    latest = updates.check_for_update()
    if latest:
        out.print(
            f"\n[yellow]Update available:[/yellow] v{latest} "
            f"(you have v{__version__}). Run [bold]compliance-agent upgrade[/bold]."
        )


def _print_next_steps(out: Console, result: ScanResult, path: str) -> None:
    """Tell the user what to do next, based on whether gaps were found."""
    out.print()
    out.print(terminal.build_next_steps(result, path))


def _parse_severity(value: str, out: Console) -> Severity:
    try:
        return Severity(value.lower())
    except ValueError as exc:
        valid = ", ".join(s.value for s in Severity)
        out.print(f"[red]Error:[/red] invalid severity '{value}'. Use one of: {valid}")
        raise typer.Exit(code=2) from exc


def _filter_by_severity(result: ScanResult, threshold: Severity) -> ScanResult:
    """Return a view showing only findings AND gaps at/above the threshold.

    Gaps are filtered too — previously only findings were, so ``--severity
    critical`` still listed lower-severity gaps. Summary metric tiles are drawn
    from the unfiltered result (see the scan command), so the totals stay
    truthful even though the detail lists are narrowed.
    """
    minimum = SEVERITY_ORDER[threshold]
    visible = [f for f in result.findings if SEVERITY_ORDER[f.severity] >= minimum]
    visible_gaps = [g for g in result.gaps if SEVERITY_ORDER[g.severity] >= minimum]
    return result.model_copy(update={"findings": visible, "gaps": visible_gaps})


def _should_fail(result: ScanResult, threshold: Severity) -> bool:
    """True when the scan was incomplete OR any finding/gap meets the threshold.

    Detectors only ever emit INFO/WARNING findings; the severe signals — a
    CRITICAL Art. 5 prohibited practice, HIGH oversight/robustness gaps —
    live in ``result.gaps``. A ``--fail-on`` CI gate that inspected findings
    alone silently passed builds on UNACCEPTABLE-tier projects, defeating the
    whole point of the flag.

    An incomplete scan (``scan_errors`` non-empty, i.e. a detector crashed on a
    file) also fails the gate regardless of threshold: coverage is unknown, so a
    green build would falsely assert a clean scan of the whole project — the very
    false-assurance the tool is built to avoid.
    """
    if result.scan_errors:
        return True
    minimum = SEVERITY_ORDER[threshold]
    findings_hit = any(SEVERITY_ORDER[f.severity] >= minimum for f in result.findings)
    gaps_hit = any(SEVERITY_ORDER[g.severity] >= minimum for g in result.gaps)
    return findings_hit or gaps_hit


if __name__ == "__main__":
    app()
