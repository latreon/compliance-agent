"""Typer CLI entry point for ComplianceAgent."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from compliance_agent import __version__
from compliance_agent.analyzer.gaps import GapAnalyzer
from compliance_agent.classifier.risk import RiskClassifier
from compliance_agent.models.findings import SEVERITY_ORDER, ScanResult, Severity
from compliance_agent.recommender.engine import FixRecommender
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


@app.command()
def scan(
    path: str = typer.Argument(".", help="Project path to scan"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown, json"),
    fail_on: str = typer.Option(
        None,
        "--fail-on",
        help="Fail with exit code 1 if findings at this severity or above exist",
    ),
    exclude: list[str] = typer.Option(
        None, "--exclude", help="Exclude paths matching glob pattern (repeatable)"
    ),
    include: list[str] = typer.Option(
        None, "--include", help="Only scan paths matching glob pattern (repeatable)"
    ),
    severity: str = typer.Option(
        None,
        "--severity",
        help="Only show findings at this severity or above (info, warning, high, critical)",
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Only output the final summary, no detailed findings"
    ),
    fix: bool = typer.Option(False, "--fix", help="Include fix recommendations in the scan output"),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="CI mode: plain summary output without color (implies --quiet --no-color)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Scan a project for EU AI Act compliance."""
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
    if format not in VALID_FORMATS:
        out.print(
            f"[red]Error:[/red] invalid format '{format}'. "
            f"Use one of: {', '.join(sorted(VALID_FORMATS))}. "
            "Example: --format json"
        )
        raise typer.Exit(code=2)
    fail_threshold = _parse_severity(fail_on, out) if fail_on else None
    show_threshold = _parse_severity(severity, out) if severity else None

    if verbose:
        out.print(f"Scanning [bold]{project_path}[/bold] ...")

    engine = ScannerEngine(project_path, exclude=exclude or [], include=include or [])
    result = engine.scan()

    classifier = RiskClassifier()
    assessment = classifier.classify(result)

    analyzer = GapAnalyzer()
    gaps = analyzer.analyze(result, assessment)

    result = result.model_copy(
        update={
            "risk_tier": assessment.tier,
            "risk_assessment": assessment,
            "gaps": gaps,
        }
    )

    if fix:
        recommender = FixRecommender()
        result = result.model_copy(update={"recommendations": recommender.recommend(result)})

    display = _filter_by_severity(result, show_threshold) if show_threshold else result

    if format == "json":
        # plain print keeps output machine-parseable (no Rich wrapping)
        typer.echo(render_json(display))
    elif quiet:
        out.print(render_summary(display))
    else:
        _print_rich_report(out, display, verbose=verbose)

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
    if format not in VALID_FORMATS:
        console.print(
            f"[red]Error:[/red] invalid format '{format}'. "
            f"Use one of: {', '.join(sorted(VALID_FORMATS))}. "
            "Example: --format json"
        )
        raise typer.Exit(code=2)

    result = ScannerEngine(project_path).scan()
    assessment = RiskClassifier().classify(result)
    gaps = GapAnalyzer().analyze(result, assessment)
    result = result.model_copy(
        update={"risk_tier": assessment.tier, "risk_assessment": assessment, "gaps": gaps}
    )

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
def version() -> None:
    """Show version information."""
    console.print(f"compliance-agent {__version__}")


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


def _print_rich_report(out: Console, result: ScanResult, *, verbose: bool) -> None:
    """Print the markdown report; add the detailed findings table in verbose mode."""
    out.print(render_markdown(result))

    # The markdown report already lists findings grouped by file; the table
    # adds per-finding descriptions and is only worth the space in verbose mode.
    if not result.findings or not verbose:
        return

    table = Table(title="Findings", show_lines=False)
    table.add_column("Severity", style="bold")
    table.add_column("Category")
    table.add_column("File")
    table.add_column("Line", justify="right")
    table.add_column("×", justify="right")
    table.add_column("Message")

    severity_styles = {
        Severity.CRITICAL: "red",
        Severity.HIGH: "dark_orange",
        Severity.WARNING: "yellow",
        Severity.INFO: "cyan",
    }
    ordered = sorted(result.findings, key=lambda f: (f.file_path, f.line_number or 0))
    for finding in ordered:
        table.add_row(
            f"[{severity_styles[finding.severity]}]{finding.severity.value}[/]",
            finding.category,
            finding.file_path,
            str(finding.line_number) if finding.line_number else "—",
            str(finding.occurrences),
            f"{finding.message} — {finding.description}",
        )
    out.print(table)


if __name__ == "__main__":
    app()
