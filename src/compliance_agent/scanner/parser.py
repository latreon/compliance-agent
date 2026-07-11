"""Codebase parser: AST-based import extraction with regex fallback.

Python files get real AST parsing. JavaScript/TypeScript files (``.js``,
``.jsx``, ``.mjs``, ``.cjs``, ``.ts``, ``.tsx``, ``.mts``, ``.cts``) get a
hand-rolled comment/string-aware regex extractor — there is no bundled JS/TS
parser dependency, so this is the same "AST where possible, precision-minded
regex otherwise" tradeoff already used for broken Python files.
"""

import ast
import io
import logging
import re
import tokenize
from pathlib import Path

logger = logging.getLogger(__name__)

JS_TS_SUFFIXES = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"})

IMPORT_REGEX = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.MULTILINE)
# Drops ``#…`` comment runs when the file cannot be tokenized. Applied only as a
# fallback, so it need not be string-literal aware for the common case.
_COMMENT_FALLBACK_REGEX = re.compile(r"#[^\n]*")

# Matches `import ... from '<spec>'` / `export ... from '<spec>'`, including
# side-effect imports (`import '<spec>'`) and `import type` / `export type`.
# The middle character class deliberately excludes quotes/`;`/`(` so a greedy
# match cannot run past the end of one import statement into unrelated code.
_JS_STATIC_IMPORT_EXPORT_REGEX = re.compile(
    r"^\s*(?:import|export)\s+(?:type\s+)?(?:[\w*\s{},.$]*\s+from\s+)?['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
_JS_REQUIRE_REGEX = re.compile(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)")
_JS_DYNAMIC_IMPORT_REGEX = re.compile(r"\bimport\(\s*['\"]([^'\"]+)['\"]\s*\)")


def strip_js_comments(source: str) -> str:
    """Return JS/TS source with `//` and `/* */` comments removed, strings kept.

    Hand-rolled single-pass scanner: tracks whether the cursor is inside a
    single/double-quoted string or a template literal so a comment marker
    inside a string (e.g. a URL like ``"http://example.com"``) is not mistaken
    for a real comment — mirroring why :func:`strip_comments` keeps Python
    string literals for the same reason.

    Known limitation: a regex literal containing ``//`` (e.g. ``/https?:\\/\\//``)
    is indistinguishable from division/comment syntax without a real
    tokenizer, so it can be misread as a line comment. Import/require
    statements never contain regex literals, so this does not affect import
    extraction; it is a rare, narrow miss for the general-purpose stripping
    used ahead of line-based pattern matching.
    """
    result: list[str] = []
    i = 0
    n = len(source)
    in_line_comment = False
    in_block_comment = False
    string_char: str | None = None
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                result.append(ch)
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            if ch == "\n":
                result.append(ch)
            i += 1
            continue
        if string_char:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(source[i + 1])
                i += 2
                continue
            if ch == string_char:
                string_char = None
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch in ("'", '"', "`"):
            string_char = ch
            result.append(ch)
            i += 1
            continue
        result.append(ch)
        i += 1
    return "".join(result)


_JS_IMPORT_PATTERNS = (
    _JS_STATIC_IMPORT_EXPORT_REGEX,
    _JS_REQUIRE_REGEX,
    _JS_DYNAMIC_IMPORT_REGEX,
)


def iter_js_import_specs(content: str) -> list[tuple[str, int]]:
    """Return (specifier, 1-based line number) for each JS/TS import found.

    Comments are stripped first so a commented-out import is not extracted as
    real usage — the same precision requirement AST parsing gives Python.
    Matching runs against the whole (multi-line) body rather than per split
    line, so import statements whose specifier list spans several lines (a
    common TypeScript style) are still found; the line number is recovered
    from the match offset.
    """
    body = strip_js_comments(content)
    hits: list[tuple[str, int]] = []
    for pattern in _JS_IMPORT_PATTERNS:
        for match in pattern.finditer(body):
            line_no = body.count("\n", 0, match.start()) + 1
            hits.append((match.group(1), line_no))
    return hits


def extract_js_imports(content: str) -> list[str]:
    """Extract import/require/dynamic-import specifiers from JS/TS source."""
    return [spec for spec, _line_no in iter_js_import_specs(content)]


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
    """Extract imported module names from a Python or JS/TS file.

    Python: uses the AST when the file parses; falls back to a regex scan for
    files with syntax errors (partial code, templates, notebooks exports).
    JS/TS: uses the comment-aware regex extractor (no JS AST parser is
    bundled).
    """
    if file_path.suffix in JS_TS_SUFFIXES:
        return extract_js_imports(content)
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
    """Reduce dotted (Python) or path/scoped (JS/TS) imports to top-level packages.

    Python submodules are dotted (``google.generativeai`` -> ``google``). npm
    packages are slash-separated, and scoped packages carry the scope as part
    of the identity (``@langchain/openai/foo`` -> ``@langchain/openai``, not
    ``@langchain`` — different scoped subpackages are different providers).
    Relative specifiers (``./local``, ``../lib``) are local files, not
    third-party packages, and are dropped.
    """
    result: set[str] = set()
    for name in imports:
        if not name or name.startswith("."):
            continue
        if "/" in name:
            parts = name.split("/")
            result.add("/".join(parts[:2]) if name.startswith("@") else parts[0])
        else:
            result.add(name.split(".")[0])
    return result
