"""Detector precision tests: true positives fire, false positives stay silent."""

from pathlib import Path

from compliance_agent.scanner.engine import ScannerEngine


def _scan(tmp_path: Path, name: str, content: str):
    (tmp_path / name).write_text(content, encoding="utf-8")
    return ScannerEngine(tmp_path).scan()


# --- providers: false positives ---------------------------------------------


def test_provider_name_in_comment_not_flagged(tmp_path: Path) -> None:
    result = _scan(
        tmp_path,
        "app.py",
        "# talk to openai support\nimport os\nURL = 'https://openai.com/docs'\n",
    )
    assert not [f for f in result.findings if f.category.startswith("provider:")]


def test_provider_name_in_docstring_not_flagged(tmp_path: Path) -> None:
    result = _scan(
        tmp_path,
        "app.py",
        '"""This module wraps an openai-style anthropic-compatible API."""\nimport json\n',
    )
    assert not result.findings


def test_provider_mention_in_markdown_not_flagged(tmp_path: Path) -> None:
    result = _scan(
        tmp_path,
        "README.md",
        "# My project\n\nWe use openai and anthropic models via the API.\n",
    )
    assert not [f for f in result.findings if f.category.startswith("provider:")]


# --- providers: true positives -----------------------------------------------


def test_constructor_call_without_import_flagged(tmp_path: Path) -> None:
    result = _scan(tmp_path, "app.py", "client = OpenAI()\n")
    assert any(f.category == "provider:openai" for f in result.findings)


def test_fallback_catches_imports_in_broken_python(tmp_path: Path) -> None:
    result = _scan(tmp_path, "broken.py", "import anthropic\ndef broken(:\n")
    assert any(f.category == "provider:anthropic" for f in result.findings)


# --- agents: precision --------------------------------------------------------


def test_agent_word_alone_not_flagged(tmp_path: Path) -> None:
    content = (
        "USER_AGENT = 'my-crawler/1.0'\n"
        "# the estate agent called\n"
        "headers = {'User-Agent': USER_AGENT}\n"
    )
    result = _scan(tmp_path, "http_client.py", content)
    assert not [f for f in result.findings if f.category.startswith("agent:")]


def test_agent_with_ai_context_flagged(tmp_path: Path) -> None:
    result = _scan(
        tmp_path,
        "app.py",
        "import openai\n\nagent = build_agent(tools=[search], llm=model)\n",
    )
    assert any(f.category == "agent:multi-agent" for f in result.findings)


def test_bare_mcp_word_not_flagged(tmp_path: Path) -> None:
    result = _scan(tmp_path, "notes.md", "We evaluated mcp adoption last quarter.\n")
    assert not [f for f in result.findings if f.category == "agent:mcp"]


def test_real_mcp_import_flagged(tmp_path: Path) -> None:
    result = _scan(tmp_path, "server.py", "from mcp.server import Server\n")
    assert any(f.category == "agent:mcp" for f in result.findings)


def test_tool_calls_require_ai_import(tmp_path: Path) -> None:
    result = _scan(
        tmp_path,
        "config.py",
        "tools = [hammer, wrench]\nfunction_call = None\n",
    )
    assert not [f for f in result.findings if f.category == "agent:tool-calls"]


# --- patterns: precision ------------------------------------------------------


def test_input_builtin_never_flagged(tmp_path: Path) -> None:
    result = _scan(
        tmp_path,
        "app.py",
        "import openai\n\nname = input('your name: ')\n",
    )
    assert not [f for f in result.findings if "input(" in f.message.lower()]


def test_query_without_ai_context_not_flagged(tmp_path: Path) -> None:
    result = _scan(
        tmp_path,
        "db.py",
        "def run_query(sql):\n    return db.query(sql)\n",
    )
    assert not [f for f in result.findings if f.category.startswith("pattern:")]


def test_missing_logging_only_for_ai_files(tmp_path: Path) -> None:
    result = _scan(tmp_path, "utils.py", "def add(a, b):\n    return a + b\n")
    assert not [f for f in result.findings if f.category == "pattern:missing-logging"]


# --- deduplication -------------------------------------------------------------


def test_repeated_pattern_produces_single_finding(tmp_path: Path) -> None:
    content = (
        "import openai\n"
        "from openai import OpenAI\n"
        "client = OpenAI()\n"
        "r = client.chat.completions.create(model='gpt-4o', messages=[])\n"
    )
    result = _scan(tmp_path, "app.py", content)
    provider_findings = [f for f in result.findings if f.category == "provider:openai"]
    assert len(provider_findings) == 1
    assert provider_findings[0].occurrences >= 3
    assert provider_findings[0].line_number == 1  # first occurrence kept
