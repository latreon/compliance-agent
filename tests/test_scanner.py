"""Tests for ScannerEngine and detectors."""

import os
from pathlib import Path

import pytest

from compliance_agent.scanner.engine import ScannerEngine


def test_no_stale_line_cache_across_same_length_files(tmp_path: Path) -> None:
    # Regression: detector instances are reused across files. A per-detector
    # line cache keyed only by id(content) could return a previous file's lines
    # when CPython recycled a freed string's address for a same-length file,
    # producing findings attributed to the wrong file. Alternate an MCP file
    # with a non-MCP file of the *same byte length* many times and assert the
    # non-MCP files are never flagged.
    for i in range(400):
        if i % 2 == 0:
            (tmp_path / f"f{i}.py").write_text("@server.tool\n")  # 13 bytes, MCP
        else:
            (tmp_path / f"f{i}.py").write_text("no_mcp_stuff\n")  # 13 bytes, clean

    result = ScannerEngine(tmp_path).scan()
    mcp_files = {f.file_path for f in result.findings if f.category == "agent:mcp"}
    clean_files = {f"f{i}.py" for i in range(1, 400, 2)}

    # No clean (odd-indexed) file may carry an MCP finding.
    assert mcp_files.isdisjoint(clean_files), (
        f"stale MCP findings leaked onto clean files: {sorted(mcp_files & clean_files)}"
    )


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


def test_respects_gitignore(tmp_path: Path) -> None:
    # Arrange
    (tmp_path / ".gitignore").write_text("vendored/\n*.generated.py\n")
    vendored = tmp_path / "vendored"
    vendored.mkdir()
    (vendored / "lib.py").write_text("import openai\n")
    (tmp_path / "skip.generated.py").write_text("import anthropic\n")
    (tmp_path / "app.py").write_text("import openai\n")
    engine = ScannerEngine(tmp_path)

    # Act
    result = engine.scan()

    # Assert
    assert result.files_scanned == 1
    assert all(f.file_path.endswith("app.py") for f in result.findings)


def test_exclude_patterns_skip_matching_paths(tmp_path: Path) -> None:
    # Arrange
    nested = tmp_path / "third_party" / "pkg" / "deep"
    nested.mkdir(parents=True)
    (nested / "vendor.py").write_text("import openai\n")
    (tmp_path / "app.py").write_text("import openai\n")
    engine = ScannerEngine(tmp_path, exclude=["third_party/*"])

    # Act
    result = engine.scan()

    # Assert
    assert result.files_scanned == 1
    assert all("third_party" not in f.file_path for f in result.findings)


def test_include_patterns_restrict_scan(tmp_path: Path) -> None:
    # Arrange
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("import openai\n")
    (tmp_path / "other.py").write_text("import anthropic\n")
    engine = ScannerEngine(tmp_path, include=["src/*"])

    # Act
    result = engine.scan()

    # Assert
    assert result.files_scanned == 1
    assert all("src" in f.file_path for f in result.findings)


def test_bom_prefixed_file_still_detects_full_provider_usage(tmp_path: Path) -> None:
    # Regression: a leading BOM made ast.parse fail the whole file, degrading
    # provider detection to import-line-only regex and missing the constructor
    # and client.method() API calls. It must now parse like a plain file.
    source = (
        "import openai\n"
        "client = openai.OpenAI()\n"
        "resp = client.chat.completions.create(model='gpt-4o', messages=[])\n"
    )
    (tmp_path / "app.py").write_text("\ufeff" + source, encoding="utf-8")
    result = ScannerEngine(tmp_path).scan()
    openai_findings = [f for f in result.findings if f.category == "provider:openai"]
    # import + constructor + attribute API call = 3 distinct lines.
    assert openai_findings and openai_findings[0].occurrences >= 3


def test_symlinks_are_not_followed(tmp_path: Path) -> None:
    # Security regression: scanning an untrusted repo must not read files the
    # symlink points at (potentially outside the project), so symlinks are
    # skipped entirely.
    secret = tmp_path / "outside_secret.py"
    secret.write_text("import openai  # sensitive file outside the scan target\n")
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("x = 1\n")
    link = project / "link.py"
    try:
        os.symlink(secret, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")

    result = ScannerEngine(project).scan()
    assert result.files_scanned == 1
    assert all("link.py" not in f.file_path for f in result.findings)


def test_finding_line_numbers_point_to_matches(openai_project: Path) -> None:
    # Arrange
    engine = ScannerEngine(openai_project)

    # Act
    result = engine.scan()

    # Assert
    import_findings = [
        f for f in result.findings if f.category == "provider:openai" and f.line_number == 2
    ]
    assert import_findings, "expected finding on line 2 (import openai)"
