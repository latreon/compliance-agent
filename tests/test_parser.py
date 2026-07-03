"""Tests for the codebase parser (AST + regex fallback)."""

from pathlib import Path

from compliance_agent.scanner.parser import extract_imports, top_level_modules


def test_extracts_imports_via_ast() -> None:
    content = "import openai\nfrom anthropic import Anthropic\nimport os.path\n"
    imports = extract_imports(Path("app.py"), content)
    assert imports == ["openai", "anthropic", "os.path"]


def test_falls_back_to_regex_on_syntax_error() -> None:
    content = "import openai\ndef broken(:\n"
    imports = extract_imports(Path("broken.py"), content)
    assert "openai" in imports


def test_returns_empty_for_non_python_files() -> None:
    assert extract_imports(Path("config.yaml"), "import: fake") == []


def test_top_level_modules_reduces_dotted_names() -> None:
    assert top_level_modules(["google.generativeai", "os.path", "openai"]) == {
        "google",
        "os",
        "openai",
    }
