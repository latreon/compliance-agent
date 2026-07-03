"""Typer CLI entry point for ComplianceAgent."""

import sys
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import typer
from rich.console import Console

from compliance_agent import __version__, updates
from compliance_agent.analyzer.gaps import GapAnalyzer
from compliance_agent.classifier.risk import RiskClassifier
from compliance_agent.models.findings import SEVERITY_ORDER, ScanResult, Severity
from compliance_agent.recommender.engine import FixRecommender
from compliance_agent.reporter import terminal
from compliance_agent.reporter.json_report import render_json
from compliance_agent.reporter.markdown import (
    render_markdown,
    render_recommendations,
    render_summary,
)
from compliance_agent.scanner.engine import ScannerEngine

app = typer.Typer(
    name="compliance-agent",
    help="EU AI Act Compliance Scanner for AI Projects",
    no_args_is_help=True,
)
console = Console()

VALID_FORMATS = {"markdown", "json"}
SCAN_FORMATS = {"markdown", "json", "pdf"}
REPORT_FORMATS = {"markdown", "pdf"}


@app.command()
def scan(
    path: str = typer.Argument(".", help="The folder to check. Use '.' for the current folder."),
    format: str = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Output type: 'markdown' (for reading), 'json' (for computers), 'pdf' (for sharing).",
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Where to save the report file (PDF format only)."
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
    """
    if ci:
        no_color = True
        quiet = True
    out = Console(no_color=no_color) if no_color else console
    project_path = Path(path).resolve()
    if not project_path.exists():
        out.print(
            f"[red]Error:[/red] path '{path}' does not exist (resolved to {project_path}).\n"
            "Check the path and try again, e.g.: compliance-agent scan ./my-project"
        )
        raise typer.Exit(code=2)
    if not project_path.is_dir():
        out.print(
            f"[red]Error:[/red] '{path}' is a file, not a folder. "
            "Point ComplianceAgent at a project directory, e.g.: compliance-agent scan ./my-project"
        )
        raise typer.Exit(code=2)
    if format not in SCAN_FORMATS:
        out.print(
            f"[red]Error:[/red] invalid format '{format}'. "
            f"Use one of: {', '.join(sorted(SCAN_FORMATS))}. "
            "Example: --format json"
        )
        raise typer.Exit(code=2)
    fail_threshold = _parse_severity(fail_on, out) if fail_on else None
    show_threshold = _parse_severity(severity, out) if severity else None

    if verbose:
        out.print(f"Scanning [bold]{project_path}[/bold] ...")

    # Show a live spinner only for interactive terminal runs — never when the
    # output is piped, machine-readable, or running in CI (would corrupt output).
    interactive = format != "json" and not ci and sys.stdout.isatty()
    with _status(out, "Analyzing project for EU AI Act compliance...", active=interactive):
        result = _run_pipeline(
            project_path,
            exclude=exclude or [],
            include=include or [],
            with_recommendations=fix or format == "pdf",
        )

    display = _filter_by_severity(result, show_threshold) if show_threshold else result

    if format == "pdf":
        pdf_path = _write_pdf(out, display, output)
        out.print(f"[green]Report saved to:[/green] {pdf_path}")
    elif format == "json":
        # plain print keeps output machine-parseable (no Rich wrapping)
        typer.echo(render_json(display))
    elif ci:
        # CI logs stay clean: plain-text summary, no boxes or color.
        typer.echo(render_summary(display))
    elif quiet:
        terminal.render_summary(out, display)
    else:
        terminal.render_report(out, display)

    # Human-friendly next steps — skip for machine output (json/pdf) and CI runs.
    if format not in {"json", "pdf"} and not ci:
        _print_next_steps(out, result, path)
        if interactive and not no_update_check:
            _notify_update(out)

    # fail-on is evaluated on the FULL result, not the severity-filtered view
    if fail_threshold is not None and _has_findings_at_or_above(result, fail_threshold):
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
    project_path = Path(path).resolve()
    if not project_path.exists():
        console.print(
            f"[red]Error:[/red] path '{path}' does not exist (resolved to {project_path}).\n"
            "Check the path and try again, e.g.: compliance-agent recommend ./my-project"
        )
        raise typer.Exit(code=2)
    if not project_path.is_dir():
        console.print(
            f"[red]Error:[/red] '{path}' is a file, not a folder.\n"
            "Point ComplianceAgent at a project directory, e.g.: "
            "compliance-agent recommend ./my-project"
        )
        raise typer.Exit(code=2)
    if format not in VALID_FORMATS:
        console.print(
            f"[red]Error:[/red] invalid format '{format}'. "
            f"Use one of: {', '.join(sorted(VALID_FORMATS))}. "
            "Example: --format json"
        )
        raise typer.Exit(code=2)

    result = _analyze_project(project_path)

    recommender = FixRecommender()
    recommendations = recommender.recommend(result)
    result = result.model_copy(update={"recommendations": recommendations})

    if format == "json":
        typer.echo(render_json(result))
    elif not recommendations:
        console.print("No compliance gaps found — nothing to recommend.")
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


@app.command()
def report(
    path: str = typer.Argument(".", help="Project path"),
    format: str = typer.Option("pdf", "--format", "-f", help="Report format: pdf, markdown"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Generate a compliance report file (PDF or Markdown)."""
    project_path = Path(path).resolve()
    if not project_path.exists():
        console.print(
            f"[red]Error:[/red] path '{path}' does not exist (resolved to {project_path}).\n"
            "Check the path and try again, e.g.: compliance-agent report ./my-project"
        )
        raise typer.Exit(code=2)
    if not project_path.is_dir():
        console.print(
            f"[red]Error:[/red] '{path}' is a file, not a folder.\n"
            "Point ComplianceAgent at a project directory, e.g.: "
            "compliance-agent report ./my-project"
        )
        raise typer.Exit(code=2)
    if format not in REPORT_FORMATS:
        console.print(
            f"[red]Error:[/red] invalid format '{format}'. "
            f"Use one of: {', '.join(sorted(REPORT_FORMATS))}. "
            "Example: --format pdf"
        )
        raise typer.Exit(code=2)

    result = _analyze_project(project_path)
    result = result.model_copy(update={"recommendations": FixRecommender().recommend(result)})

    if format == "pdf":
        report_path = _write_pdf(console, result, output)
    else:
        report_path = Path(output or f"compliance-report-{project_path.name}.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_markdown(result), encoding="utf-8")
    console.print(f"[green]Report saved to:[/green] {report_path}")


def _analyze_project(project_path: Path) -> ScanResult:
    """Run the full pipeline: scan -> classify -> gaps + coverage."""
    result = ScannerEngine(project_path).scan()
    assessment = RiskClassifier().classify(result)
    result = result.model_copy(update={"risk_tier": assessment.tier, "risk_assessment": assessment})
    analyzer = GapAnalyzer()
    return result.model_copy(
        update={"gaps": analyzer.analyze(result), "coverage": analyzer.coverage(result)}
    )


def _status(out: Console, message: str, *, active: bool) -> AbstractContextManager:
    """A live spinner for interactive runs; a no-op context otherwise."""
    if active:
        return out.status(message, spinner="dots")
    return nullcontext()


def _run_pipeline(
    project_path: Path,
    *,
    exclude: list[str],
    include: list[str],
    with_recommendations: bool,
) -> ScanResult:
    """Run the full pipeline: scan -> classify -> gaps + coverage (+ recommendations)."""
    result = ScannerEngine(project_path, exclude=exclude, include=include).scan()
    assessment = RiskClassifier().classify(result)
    result = result.model_copy(update={"risk_tier": assessment.tier, "risk_assessment": assessment})
    analyzer = GapAnalyzer()
    result = result.model_copy(
        update={"gaps": analyzer.analyze(result), "coverage": analyzer.coverage(result)}
    )
    if with_recommendations:
        result = result.model_copy(update={"recommendations": FixRecommender().recommend(result)})
    return result


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


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"ComplianceAgent v{__version__}")
    latest = updates.check_for_update()
    if latest:
        console.print(
            f"[yellow]A newer version is available: v{latest}.[/yellow] "
            "Run [bold]compliance-agent upgrade[/bold] to update."
        )


@app.command()
def upgrade(
    version: str = typer.Argument(
        "latest", help="Version to install: 'latest' (default) or an exact one like 0.1.2."
    ),
) -> None:
    """Upgrade ComplianceAgent to the latest (or a specific) version."""
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


_RULE = "━" * 50


def _print_next_steps(out: Console, result: ScanResult, path: str) -> None:
    """Tell the user what to do next, based on whether gaps were found."""
    out.print("")
    out.print("[bold]NEXT STEPS[/bold]")
    out.print(f"[dim]{_RULE}[/dim]")
    if result.gaps:
        out.print("1. Review the issues above.")
        out.print(
            f"2. Get the fix files: [bold]compliance-agent recommend {path} --output ./fixes[/bold]"
        )
        out.print("3. Copy the files from ./fixes into your project.")
        out.print(f"4. Check again: [bold]compliance-agent scan {path}[/bold]")
    else:
        out.print("[green]✓ No issues found — your project looks compliant.[/green]")
        out.print("")
        out.print("To share this result as a PDF:")
        out.print(f"  [bold]compliance-agent scan {path} --format pdf --output report.pdf[/bold]")


def _parse_severity(value: str, out: Console) -> Severity:
    try:
        return Severity(value.lower())
    except ValueError as exc:
        valid = ", ".join(s.value for s in Severity)
        out.print(f"[red]Error:[/red] invalid severity '{value}'. Use one of: {valid}")
        raise typer.Exit(code=2) from exc


def _filter_by_severity(result: ScanResult, threshold: Severity) -> ScanResult:
    minimum = SEVERITY_ORDER[threshold]
    visible = [f for f in result.findings if SEVERITY_ORDER[f.severity] >= minimum]
    return result.model_copy(update={"findings": visible})


def _has_findings_at_or_above(result: ScanResult, threshold: Severity) -> bool:
    minimum = SEVERITY_ORDER[threshold]
    return any(SEVERITY_ORDER[f.severity] >= minimum for f in result.findings)


if __name__ == "__main__":
    app()
