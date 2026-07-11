"""Tests for the codebase parser (AST + regex fallback)."""

from pathlib import Path

from compliance_agent.scanner.parser import (
    extract_imports,
    extract_js_imports,
    strip_js_comments,
    top_level_modules,
)


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


# --- JS/TS import extraction --------------------------------------------------


def test_extracts_named_and_default_imports() -> None:
    content = (
        "import OpenAI from 'openai';\n"
        "import { ChatOpenAI } from '@langchain/openai';\n"
        "import * as anthropic from '@anthropic-ai/sdk';\n"
    )
    imports = extract_imports(Path("app.ts"), content)
    assert imports == ["openai", "@langchain/openai", "@anthropic-ai/sdk"]


def test_extracts_side_effect_and_multiline_imports() -> None:
    content = "import 'openai/shim';\nimport {\n  generateText,\n} from 'ai';\n"
    imports = extract_imports(Path("app.ts"), content)
    assert imports == ["openai/shim", "ai"]


def test_extracts_require_and_dynamic_import() -> None:
    content = (
        "const { Groq } = require('groq-sdk');\n"
        "const mod = await import('@ai-sdk/openai');\n"
    )
    imports = extract_imports(Path("app.js"), content)
    assert "groq-sdk" in imports
    assert "@ai-sdk/openai" in imports


def test_export_from_extracted() -> None:
    content = "export * from '@langchain/core';\n"
    imports = extract_imports(Path("index.ts"), content)
    assert imports == ["@langchain/core"]


def test_commented_out_js_import_not_extracted() -> None:
    content = "// import OpenAI from 'openai';\n/* import Anthropic from '@anthropic-ai/sdk'; */\n"
    assert extract_imports(Path("app.ts"), content) == []


def test_js_import_inside_string_url_not_treated_as_comment() -> None:
    # The "//" in a URL string must not be mistaken for a line comment, which
    # would swallow the real import that follows it.
    content = 'const DOCS = "https://openai.com/docs";\nimport OpenAI from "openai";\n'
    assert extract_imports(Path("app.ts"), content) == ["openai"]


def test_returns_empty_for_non_js_non_python_files() -> None:
    assert extract_imports(Path("config.yaml"), "import: fake") == []


def test_top_level_modules_handles_scoped_and_subpath_npm_names() -> None:
    imports = ["@langchain/openai", "openai/resources/chat", "./local", "../lib"]
    assert top_level_modules(imports) == {"@langchain/openai", "openai"}


def test_strip_js_comments_preserves_strings() -> None:
    source = "// leading comment\nconst url = 'http://example.com'; /* trailing */\n"
    stripped = strip_js_comments(source)
    assert "leading comment" not in stripped
    assert "trailing" not in stripped
    assert "http://example.com" in stripped


def test_extract_js_imports_direct_helper() -> None:
    assert extract_js_imports("import x from 'openai';\n") == ["openai"]
