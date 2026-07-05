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


def test_relative_import_of_local_module_is_not_extracted() -> None:
    # `from .openai import x` is a LOCAL sibling module that merely shares a name
    # with the real SDK — it must not be reported as an import of `openai`,
    # which would falsely flag AI-provider usage.
    content = "from .openai import get_client\nfrom ..agents.langchain import Agent\n"
    imports = extract_imports(Path("integrations/wrapper.py"), content)
    assert "openai" not in imports
    assert "agents.langchain" not in imports


def test_absolute_import_still_extracted_alongside_relative() -> None:
    content = "from .local_openai import x\nimport openai\n"
    imports = extract_imports(Path("app.py"), content)
    assert "openai" in imports


def test_top_level_modules_reduces_dotted_names() -> None:
    assert top_level_modules(["google.generativeai", "os.path", "openai"]) == {
        "google",
        "os",
        "openai",
    }
