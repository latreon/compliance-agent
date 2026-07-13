"""Detect general AI application patterns: user input, chat UIs, data, logging.

Precision rules:
- Generic words (``query``, ``chat``, ``user_input``) only count in files
  that actually import an AI library (verified via AST).
- ``input(`` is never flagged — far too common in ordinary Python.
- The missing-logging check only applies to files with real AI imports.
"""

import ast
import re
from pathlib import Path

from compliance_agent.models.findings import Finding, Severity
from compliance_agent.scanner.detectors.base import BaseDetector, detect_ai_imports

# Only meaningful in files that import an AI library.
GATED_USER_INPUT_PATTERNS = [
    r"\brequest\.form\b",
    r"\buser_input\b",
]
QUERY_PATTERN = re.compile(r"\bquery\b", re.IGNORECASE)
AI_PATH_HINT_REGEX = re.compile(r"(llm|model|prompt)", re.IGNORECASE)

# Strong chat signals on their own.
CHAT_STRONG_PATTERNS = [
    r"\bchatbot\b",
    r"\bchat_interface\b",
    r"\bChatCompletion\b",
]
# Chat UI framework imports.
CHAT_FRAMEWORK_IMPORT_REGEX = re.compile(r"^\s*(?:from|import)\s+(streamlit|gradio|chainlit)\b")
# Bare "chat" needs an AI import.
CHAT_WEAK_PATTERN = re.compile(r"\bchat\b", re.IGNORECASE)

DATA_PROCESSING_IMPORT_REGEX = re.compile(r"^\s*(?:from|import)\s+(pandas|numpy)\b")
DATA_PROCESSING_CALL_PATTERNS = [r"\bread_csv\s*\(", r"\bload_dataset\s*\("]

LOGGING_PATTERNS = [
    r"^\s*(?:from|import)\s+logging\b",
    r"\blogger\b",
    r"\blog\.",
    r"\bstructlog\b",
]

# `__init__.py` and pure dataclass/typing modules commonly import an AI SDK
# only to re-export a type or annotate a field — they never call the API, so
# "missing logging" is a false positive there, not a real compliance gap.
_LOGGING_EXEMPT_FILENAMES = frozenset({"__init__.py"})

# Calls that are part of declaring a dataclass/pydantic model rather than real
# logic — used by _is_declarative_only to tell "field declarations only" apart
# from "this file actually does something" (see that method's docstring).
_DECLARATIVE_CALL_ALLOWLIST = frozenset({"field", "Field"})

# The exact bare name `run_agent()` is unambiguous evidence on its own. Any
# other call only counts as an agent step when "agent" appears in the call
# itself (`agent.step()`, `self.agent.run()`, `run_agent_loop()`) — generic
# verbs like `run`/`execute`/`chat`/`generate`/`predict` are far too common in
# non-agentic code (subprocess.run, cursor.execute, a bounded retry loop
# calling client.chat(...)) to use as a bare-name match on their own.
_UNAMBIGUOUS_AGENT_CALL_NAMES = frozenset({"run_agent"})


class PatternDetector(BaseDetector):
    """Detects general AI app patterns plus missing logging in AI files."""

    name = "patterns"

    def __init__(self) -> None:
        self._gated_user_input = [re.compile(p) for p in GATED_USER_INPUT_PATTERNS]
        self._chat_strong = [re.compile(p) for p in CHAT_STRONG_PATTERNS]
        self._data_calls = [re.compile(p) for p in DATA_PROCESSING_CALL_PATTERNS]
        self._logging = [re.compile(p, re.MULTILINE) for p in LOGGING_PATTERNS]

    def analyze(self, file_path: Path, content: str) -> list[Finding]:
        ai_imports = detect_ai_imports(file_path, content)
        findings: list[Finding] = []
        findings.extend(self._detect_user_input(file_path, content, ai_imports))
        findings.extend(self._detect_chat(file_path, content, ai_imports))
        if ai_imports:
            findings.extend(self._detect_data_processing(file_path, content))
            findings.extend(self._check_logging(file_path, content))
            findings.extend(self._detect_agent_loop(file_path, content))
        return findings

    def _detect_user_input(
        self, file_path: Path, content: str, ai_imports: set[str]
    ) -> list[Finding]:
        findings: list[Finding] = []
        if ai_imports:
            for pattern in self._gated_user_input:
                for line_no, _line in self._match_lines(content, pattern):
                    findings.append(
                        self._pattern_finding(
                            file_path,
                            line_no,
                            "user-input",
                            "User input feeding an AI system detected",
                            "Art. 50 (transparency obligations)",
                        )
                    )
        # `query` needs AI imports OR an AI-suggestive file path (llm/model/prompt).
        if ai_imports or (file_path.suffix == ".py" and AI_PATH_HINT_REGEX.search(file_path.name)):
            for line_no, _line in self._match_lines(content, QUERY_PATTERN):
                findings.append(
                    self._pattern_finding(
                        file_path,
                        line_no,
                        "user-input",
                        "Query handling in AI context detected",
                        "Art. 50 (transparency obligations)",
                    )
                )
        return findings

    def _detect_chat(self, file_path: Path, content: str, ai_imports: set[str]) -> list[Finding]:
        findings: list[Finding] = []
        for pattern in self._chat_strong:
            for line_no, _line in self._match_lines(content, pattern):
                findings.append(
                    self._pattern_finding(
                        file_path,
                        line_no,
                        "chat-interface",
                        "Chat interface detected",
                        "Art. 50 (transparency obligations)",
                    )
                )
        for line_no, line in enumerate(content.splitlines(), start=1):
            if CHAT_FRAMEWORK_IMPORT_REGEX.match(line):
                findings.append(
                    self._pattern_finding(
                        file_path,
                        line_no,
                        "chat-interface",
                        "Chat UI framework import detected",
                        "Art. 50 (transparency obligations)",
                    )
                )
        if ai_imports:
            for line_no, _line in self._match_lines(content, CHAT_WEAK_PATTERN):
                findings.append(
                    self._pattern_finding(
                        file_path,
                        line_no,
                        "chat-interface",
                        "Chat usage in AI context detected",
                        "Art. 50 (transparency obligations)",
                    )
                )
        return findings

    def _detect_data_processing(self, file_path: Path, content: str) -> list[Finding]:
        findings: list[Finding] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            if DATA_PROCESSING_IMPORT_REGEX.match(line):
                findings.append(
                    self._pattern_finding(
                        file_path,
                        line_no,
                        "data-processing",
                        "Data processing alongside AI usage detected",
                        "Art. 10 (data and data governance)",
                    )
                )
        for pattern in self._data_calls:
            for line_no, _line in self._match_lines(content, pattern):
                findings.append(
                    self._pattern_finding(
                        file_path,
                        line_no,
                        "data-processing",
                        "Data loading alongside AI usage detected",
                        "Art. 10 (data and data governance)",
                    )
                )
        return findings

    def _check_logging(self, file_path: Path, content: str) -> list[Finding]:
        """Flag AI-importing files that have no logging at all.

        Skips `__init__.py`: a package init commonly re-exports an AI client
        class or type for other modules to import, without ever calling it —
        there is no API call in that file for logging to wrap, so flagging it
        is a false positive, not a real gap.
        """
        if file_path.name in _LOGGING_EXEMPT_FILENAMES:
            return []
        if file_path.suffix == ".py" and self._is_declarative_only(content):
            return []
        if any(p.search(content) for p in self._logging):
            return []
        return [
            self._make_finding(
                file_path=file_path,
                line_number=None,
                severity=Severity.WARNING,
                category="pattern:missing-logging",
                message="AI usage without logging",
                description=(
                    "File imports an AI provider but contains no logging. "
                    "High-risk AI systems must support automatic event recording."
                ),
                article="Art. 12 (record-keeping)",
                suggestion="Add structured logging around AI model calls.",
            )
        ]

    def _is_declarative_only(self, content: str) -> bool:
        """True when every call in the module is a dataclass/pydantic field call.

        A pure dataclass/pydantic-model/TypedDict file has field declarations
        only (at most a `field(...)`/`Field(...)` default and a `@dataclass(...)`
        decorator) — no code path in it ever calls the AI SDK it imports (often
        imported there only for a type annotation or re-export), so "missing
        logging" would be a false positive there, not a real gap. A file with
        ANY other call — including a real, unlogged, top-level API call with
        no enclosing function — is not exempt: "no function defs" alone was
        too broad and silenced genuine missing-logging findings on ordinary
        top-level scripts.
        """
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return False
        decorator_call_ids = {
            id(dec)
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            for dec in node.decorator_list
            if isinstance(dec, ast.Call)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or id(node) in decorator_call_ids:
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name not in _DECLARATIVE_CALL_ALLOWLIST:
                return False
        return True

    def _detect_agent_loop(self, file_path: Path, content: str) -> list[Finding]:
        """Flag a hand-rolled autonomous agent loop: `while True: run_agent()`.

        Only known agent *frameworks* (LangChain, CrewAI, AutoGen, LangGraph,
        ...) triggered an Art. 14 oversight gap before this — a custom loop
        that repeatedly calls an AI system with no framework in sight was
        invisible. Gated on an unconditionally-repeating loop (`while True`/
        `while 1`) whose body calls something that names an agent step (see
        `_loop_calls_agent`) — a bounded retry loop around `client.chat(...)`
        is not flagged, since neither `client` nor `chat` names an agent.
        """
        if file_path.suffix != ".py":
            return []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        findings: list[Finding] = []
        for node in ast.walk(tree):
            # Nested (not combined via `and`) so mypy narrows `node` to
            # `ast.While` before `_loop_calls_agent`/`node.lineno` are used.
            if isinstance(node, ast.While) and self._is_always_true(node.test):  # noqa: SIM102
                if self._loop_calls_agent(node):
                    findings.append(
                        self._make_finding(
                            file_path=file_path,
                            line_number=node.lineno,
                            severity=Severity.WARNING,
                            category="pattern:custom-agent-loop",
                            message="Custom autonomous agent loop detected",
                            description=(
                                "An unconditionally repeating loop calls an AI "
                                "system on every iteration — a hand-rolled agent "
                                "loop not tied to a known framework. Art. 14 human "
                                "oversight still applies without a named framework."
                            ),
                            article="Art. 14",
                            suggestion=(
                                "Add a human oversight checkpoint or an "
                                "iteration/step limit to the loop."
                            ),
                        )
                    )
        return findings

    @staticmethod
    def _is_always_true(test: ast.expr) -> bool:
        return isinstance(test, ast.Constant) and test.value in (True, 1)

    @staticmethod
    def _loop_calls_agent(loop: ast.While) -> bool:
        """True when a call in the loop body plausibly names an agent step.

        Requires "agent" to appear in the call itself — either as the bare
        function name (`run_agent()`) or as the attribute owner/method
        (`agent.step()`, `self.agent.run()`) — rather than matching generic
        verbs (`run`, `execute`, `chat`, `generate`, `predict`) on their own,
        which collide with far too much ordinary, non-agentic code
        (`subprocess.run`, `cursor.execute`, a retry loop around
        `client.chat(...)`) to serve as a standalone signal.
        """
        for node in ast.walk(loop):
            if node is loop or not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                owner = func.value.id if isinstance(func.value, ast.Name) else ""
                name = func.attr
            else:
                owner = ""
                name = getattr(func, "id", "")
            if name.lower() in _UNAMBIGUOUS_AGENT_CALL_NAMES:
                return True
            if "agent" in owner.lower() or "agent" in name.lower():
                return True
        return False

    def _pattern_finding(
        self,
        file_path: Path,
        line_no: int,
        category: str,
        message: str,
        article: str,
    ) -> Finding:
        return self._make_finding(
            file_path=file_path,
            line_number=line_no,
            severity=Severity.INFO,
            category=f"pattern:{category}",
            message=message,
            description=f"{message} at line {line_no}.",
            article=article,
        )
