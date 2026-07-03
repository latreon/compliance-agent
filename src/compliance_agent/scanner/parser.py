"""Codebase parser: AST-based import extraction with regex fallback."""

import ast
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

IMPORT_REGEX = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.MULTILINE)


def extract_imports(file_path: Path, content: str) -> list[str]:
    """Extract imported module names from a Python file.

    Uses the AST when the file parses; falls back to a regex scan for
    files with syntax errors (partial code, templates, notebooks exports).
    """
    if file_path.suffix != ".py":
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        logger.debug("AST parse failed for %s; using regex fallback", file_path)
        return _extract_imports_regex(content)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _extract_imports_regex(content: str) -> list[str]:
    return IMPORT_REGEX.findall(content)


def top_level_modules(imports: list[str]) -> set[str]:
    """Reduce dotted imports to their top-level package names."""
    return {name.split(".")[0] for name in imports}
