"""Typer CLI entry point for ComplianceAgent."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from compliance_agent import __version__
from compliance_agent.analyzer.gaps import GapAnalyzer
from compliance_agent.classifier.risk import RiskClassifier
from compliance_agent.models.findings import SEVERITY_ORDER, ScanResult, Severity
from compliance_agent.reporter.json_report import render_json
from compliance_agent.reporter.markdown import render_markdown
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
    format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format: markdown, json"
    ),
    fail_on: str = typer.Option(
        None,
        "--fail-on",
        help="Fail with exit code 1 if findings at this severity or above exist",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Scan a project for EU AI Act compliance."""
    project_path = Path(path).resolve()
    if not project_path.exists():
        console.print(f"[red]Error:[/red] path does not exist: {project_path}")
        raise typer.Exit(code=2)
    if format not in VALID_FORMATS:
        console.print(
            f"[red]Error:[/red] invalid format '{format}'. Use one of: "
            f"{', '.join(sorted(VALID_FORMATS))}"
        )
        raise typer.Exit(code=2)
    threshold = _parse_severity(fail_on) if fail_on else None

    if verbose:
        console.print(f"Scanning [bold]{project_path}[/bold] ...")

    engine = ScannerEngine(project_path)
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

    if format == "json":
        # plain print keeps output machine-parseable (no Rich wrapping)
        typer.echo(render_json(result))
    else:
        _print_rich_report(result, verbose=verbose)

    if threshold is not None and _has_findings_at_or_above(result, threshold):
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"compliance-agent {__version__}")


def _parse_severity(value: str) -> Severity:
    try:
        return Severity(value.lower())
    except ValueError as exc:
        valid = ", ".join(s.value for s in Severity)
        console.print(f"[red]Error:[/red] invalid severity '{value}'. Use one of: {valid}")
        raise typer.Exit(code=2) from exc


def _has_findings_at_or_above(result: ScanResult, threshold: Severity) -> bool:
    minimum = SEVERITY_ORDER[threshold]
    return any(SEVERITY_ORDER[f.severity] >= minimum for f in result.findings)


def _print_rich_report(result: ScanResult, *, verbose: bool) -> None:
    """Print the markdown report plus a Rich findings table."""
    console.print(render_markdown(result))

    if not result.findings:
        return

    table = Table(title="Findings", show_lines=False)
    table.add_column("Severity", style="bold")
    table.add_column("Category")
    table.add_column("File")
    table.add_column("Line", justify="right")
    table.add_column("Message")

    severity_styles = {
        Severity.CRITICAL: "red",
        Severity.HIGH: "dark_orange",
        Severity.WARNING: "yellow",
        Severity.INFO: "cyan",
    }
    for finding in result.findings:
        table.add_row(
            f"[{severity_styles[finding.severity]}]{finding.severity.value}[/]",
            finding.category,
            finding.file_path,
            str(finding.line_number) if finding.line_number else "—",
            finding.message if not verbose else f"{finding.message} — {finding.description}",
        )
    console.print(table)


if __name__ == "__main__":
    app()
