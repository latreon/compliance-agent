"""Tests for the PDF reporter and report CLI command.

HTML rendering tests always run. Tests that produce actual PDF bytes are
skipped when WeasyPrint's native libraries (pango/gobject) are unavailable.
"""

import os
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from compliance_agent.cli import app
from compliance_agent.models.findings import Finding, RiskTier, ScanResult, Severity
from compliance_agent.reporter import pdf_report
from compliance_agent.reporter.pdf_report import PDFReporter

runner = CliRunner()


def _weasyprint_available() -> bool:
    pdf_report._prime_macos_library_path()  # find Homebrew libs on macOS
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


needs_weasyprint = pytest.mark.skipif(
    not _weasyprint_available(),
    reason="weasyprint native libraries (pango/gobject) not available",
)


def _sample_result() -> ScanResult:
    return ScanResult(
        project_path="test-project",
        findings=[
            Finding(
                id="test-1",
                file_path="app.py",
                line_number=7,
                detector="providers",
                severity=Severity.WARNING,
                category="pattern:missing-logging",
                message="No AI event logging",
                description="Article 12 requires event logging",
                article="Art. 12",
            )
        ],
        scan_time=datetime.now(),
        files_scanned=10,
        risk_tier=RiskTier.LIMITED,
    )


# --- HTML rendering (no native libs needed) -----------------------------------


def test_render_html_contains_all_sections() -> None:
    html = PDFReporter()._render_html(_sample_result())
    for expected in (
        "EU AI ACT",  # cover
        "Executive Summary",
        "Risk Assessment",
        "Findings",
        "Compliance Gaps",
        "Recommendations",
        "Appendix: EU AI Act Reference",
        "LIMITED",  # tier badge
        "No AI event logging",  # the finding
        "test-project",
    ):
        assert expected in html, f"missing section/content: {expected}"


def test_render_html_escapes_content() -> None:
    result = _sample_result().model_copy(
        update={
            "findings": [
                _sample_result()
                .findings[0]
                .model_copy(update={"message": "<script>alert(1)</script>"})
            ]
        }
    )
    html = PDFReporter()._render_html(result)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# --- PDF generation ------------------------------------------------------------


@needs_weasyprint
def test_pdf_generation(tmp_path: Path) -> None:
    reporter = PDFReporter()
    output = reporter.generate(_sample_result(), tmp_path / "report.pdf")

    assert output.exists()
    assert output.stat().st_size > 1000  # not empty
    with open(output, "rb") as handle:
        assert handle.read(4) == b"%PDF"


@needs_weasyprint
def test_pdf_default_output_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    output = PDFReporter().generate(_sample_result())
    assert output.name == "compliance-report-test-project.pdf"
    assert output.exists()


@needs_weasyprint
def test_pdf_from_real_scan(agent_project: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["scan", str(agent_project), "--format", "pdf", "--output", str(tmp_path / "out.pdf")],
    )
    assert result.exit_code == 0
    assert "Report saved to" in result.output
    pdf = tmp_path / "out.pdf"
    assert pdf.exists()
    assert pdf.read_bytes()[:4] == b"%PDF"
    assert 5_000 < pdf.stat().st_size < 5_000_000  # sane size range


@needs_weasyprint
def test_report_command_pdf(agent_project: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["report", str(agent_project), "--output", str(tmp_path / "audit.pdf")],
    )
    assert result.exit_code == 0
    assert (tmp_path / "audit.pdf").read_bytes()[:4] == b"%PDF"


def test_report_command_markdown(agent_project: Path, tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    result = runner.invoke(
        app,
        ["report", str(agent_project), "--format", "markdown", "--output", str(out)],
    )
    assert result.exit_code == 0
    content = out.read_text(encoding="utf-8")
    assert "# EU AI Act Compliance Report" in content
    assert "Recommendations" in content


def test_report_command_invalid_format(agent_project: Path) -> None:
    result = runner.invoke(app, ["report", str(agent_project), "--format", "docx"])
    assert result.exit_code == 2
    assert "invalid format" in result.output


def test_prime_macos_library_path_prepends_brew_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    # On macOS the Homebrew lib dir must be prepended so dyld can load pango,
    # without clobbering an existing DYLD_FALLBACK_LIBRARY_PATH.
    monkeypatch.setattr(pdf_report.sys, "platform", "darwin")
    monkeypatch.setattr(pdf_report.os.path, "isdir", lambda p: p == "/opt/homebrew/lib")
    monkeypatch.setenv("DYLD_FALLBACK_LIBRARY_PATH", "/existing")

    pdf_report._prime_macos_library_path()

    parts = os.environ["DYLD_FALLBACK_LIBRARY_PATH"].split(os.pathsep)
    assert parts[0] == "/opt/homebrew/lib"
    assert "/existing" in parts


def test_prime_macos_library_path_is_noop_off_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_report.sys, "platform", "linux")
    monkeypatch.delenv("DYLD_FALLBACK_LIBRARY_PATH", raising=False)

    pdf_report._prime_macos_library_path()

    assert "DYLD_FALLBACK_LIBRARY_PATH" not in os.environ


def test_prime_macos_library_path_does_not_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_report.sys, "platform", "darwin")
    monkeypatch.setattr(pdf_report.os.path, "isdir", lambda p: p == "/opt/homebrew/lib")
    monkeypatch.setenv("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")

    pdf_report._prime_macos_library_path()

    assert os.environ["DYLD_FALLBACK_LIBRARY_PATH"].count("/opt/homebrew/lib") == 1


def test_pdf_failure_produces_helpful_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate missing native libraries by making the import raise OSError.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise OSError("cannot load library 'libgobject-2.0-0'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="pango"):
        PDFReporter().generate(_sample_result(), tmp_path / "x.pdf")
