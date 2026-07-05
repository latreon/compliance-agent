"""Codebase parser: AST-based import extraction with regex fallback."""

import ast
import io
import logging
import re
import tokenize
from pathlib import Path

logger = logging.getLogger(__name__)

IMPORT_REGEX = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.MULTILINE)
# Drops ``#…`` comment runs when the file cannot be tokenized. Applied only as a
# fallback, so it need not be string-literal aware for the common case.
_COMMENT_FALLBACK_REGEX = re.compile(r"#[^\n]*")


def strip_comments(source: str) -> str:
    """Return Python source with comments removed, string literals preserved.

    Domain/keyword matching must not fire on prose that merely *mentions* a
    high-risk or prohibited practice — a comment that names a banned or
    Annex III practice (as this tool's own rule descriptions do) is
    documentation, not behaviour, and must not escalate the risk tier. String
    literals (prompt templates, disclosure text) are genuine signal and are
    kept.

    Falls back to a regex that drops ``#…`` runs when the source cannot be
    tokenized (syntax errors, partial code), so a comment in a broken file
    cannot slip through intact.
    """
    try:
        tokens = [
            tok
            for tok in tokenize.generate_tokens(io.StringIO(source).readline)
            if tok.type != tokenize.COMMENT
        ]
        return tokenize.untokenize(tokens)
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return _COMMENT_FALLBACK_REGEX.sub("", source)


def extract_imports(file_path: Path, content: str) -> list[str]:
    """Extract imported module names from a Python file.

    Uses the AST when the file parses; falls back to a regex scan for
    files with syntax errors (partial code, templates, notebooks exports).
    """
    if file_path.suffix != ".py":
        return []
    # A leading BOM (U+FEFF) makes ast.parse raise SyntaxError for the whole
    # file, silently dropping every import to the weaker regex fallback.
    content = content.lstrip("\ufeff")
    try:
        tree = ast.parse(content)
    except SyntaxError:
        logger.debug("AST parse failed for %s; using regex fallback", file_path)
        return _extract_imports_regex(content)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            # node.level > 0 is a relative import (``from .openai import x``) —
            # a LOCAL sibling module that merely shares a name with a tracked
            # package, not the real third-party dependency. Skip it, or a local
            # ``integrations/openai.py`` falsely reports OpenAI/LangChain usage.
            imports.append(node.module)
    return imports


def _extract_imports_regex(content: str) -> list[str]:
    return IMPORT_REGEX.findall(content)


def top_level_modules(imports: list[str]) -> set[str]:
    """Reduce dotted imports to their top-level package names."""
    return {name.split(".")[0] for name in imports}
