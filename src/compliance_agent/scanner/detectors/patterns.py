"""Detect general AI application patterns: user input, chat UIs, data, logging.

Precision rules:
- Generic words (``query``, ``chat``, ``user_input``) only count in files
  that actually import an AI library (verified via AST).
- ``input(`` is never flagged — far too common in ordinary Python.
- The missing-logging check only applies to files with real AI imports.
"""

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
        """Flag AI-importing files that have no logging at all."""
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
