"""Tests for ScannerEngine and detectors."""

from pathlib import Path

from compliance_agent.scanner.engine import ScannerEngine


def test_detects_openai_provider(openai_project: Path) -> None:
    # Arrange
    engine = ScannerEngine(openai_project)

    # Act
    result = engine.scan()

    # Assert
    provider_findings = [f for f in result.findings if f.category == "provider:openai"]
    assert provider_findings, "expected OpenAI provider findings"
    assert all(f.detector == "providers" for f in provider_findings)


def test_detects_anthropic_and_tool_calls(agent_project: Path) -> None:
    # Arrange
    engine = ScannerEngine(agent_project)

    # Act
    result = engine.scan()

    # Assert
    categories = {f.category for f in result.findings}
    assert "provider:anthropic" in categories
    assert "agent:tool-calls" in categories


def test_flags_missing_logging_when_ai_used_without_logger(agent_project: Path) -> None:
    # Arrange
    engine = ScannerEngine(agent_project)

    # Act
    result = engine.scan()

    # Assert
    assert any(f.category == "pattern:missing-logging" for f in result.findings)


def test_no_missing_logging_flag_when_logging_present(openai_project: Path) -> None:
    # Arrange
    engine = ScannerEngine(openai_project)

    # Act
    result = engine.scan()

    # Assert
    assert not any(f.category == "pattern:missing-logging" for f in result.findings)


def test_returns_empty_findings_for_clean_project(clean_project: Path) -> None:
    # Arrange
    engine = ScannerEngine(clean_project)

    # Act
    result = engine.scan()

    # Assert
    assert result.findings == []
    assert result.files_scanned == 1


def test_counts_scanned_files_and_skips_unsupported_suffixes(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.yaml").write_text("key: value\n")
    (tmp_path / "c.bin").write_bytes(b"\x00\x01")
    engine = ScannerEngine(tmp_path)

    # Act
    result = engine.scan()

    # Assert
    assert result.files_scanned == 2


def test_skips_vendored_directories(tmp_path: Path) -> None:
    # Arrange
    vendored = tmp_path / "node_modules" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "index.json").write_text('{"uses": "openai"}')
    (tmp_path / "app.py").write_text("import openai\n")
    engine = ScannerEngine(tmp_path)

    # Act
    result = engine.scan()

    # Assert
    assert result.files_scanned == 1
    assert all("node_modules" not in f.file_path for f in result.findings)


def test_finding_line_numbers_point_to_matches(openai_project: Path) -> None:
    # Arrange
    engine = ScannerEngine(openai_project)

    # Act
    result = engine.scan()

    # Assert
    import_findings = [
        f
        for f in result.findings
        if f.category == "provider:openai" and f.line_number == 2
    ]
    assert import_findings, "expected finding on line 2 (import openai)"
