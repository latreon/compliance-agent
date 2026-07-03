"""Detect general AI application patterns: user input, chat UIs, data, logging."""

import re
from pathlib import Path

from compliance_agent.models.findings import Finding, Severity
from compliance_agent.scanner.detectors.base import BaseDetector

GENERAL_PATTERNS: dict[str, tuple[list[str], str, str, str]] = {
    "user-input": (
        [
            r"\binput\s*\(",
            r"\brequest\.form\b",
            r"\buser_input\b",
            r"\bquery\b",
        ],
        "User input handling detected",
        "User-facing input paths feed the AI system; transparency duties may apply.",
        "Art. 50 (transparency obligations)",
    ),
    "chat-interface": (
        [
            r"\bstreamlit\b",
            r"\bgradio\b",
            r"\bchainlit\b",
            r"\bchat\b",
        ],
        "Chat interface detected",
        "Users interacting with an AI system must be informed they are talking to AI.",
        "Art. 50 (transparency obligations)",
    ),
    "data-processing": (
        [
            r"\bimport\s+pandas\b",
            r"\bfrom\s+pandas\b",
            r"\bimport\s+numpy\b",
            r"\bfrom\s+numpy\b",
            r"\bread_csv\s*\(",
            r"\bload_dataset\s*\(",
        ],
        "Data processing detected",
        "Training/serving data pipelines fall under data governance requirements.",
        "Art. 10 (data and data governance)",
    ),
}

LOGGING_PATTERNS: list[str] = [
    r"\bimport\s+logging\b",
    r"\blogger\b",
    r"\blog\.",
]


class PatternDetector(BaseDetector):
    """Detects general AI app patterns plus presence/absence of logging."""

    name = "patterns"

    def __init__(self) -> None:
        self._compiled: dict[str, tuple[list[re.Pattern[str]], str, str, str]] = {
            category: (
                [re.compile(p, re.IGNORECASE) for p in patterns],
                message,
                description,
                article,
            )
            for category, (patterns, message, description, article) in GENERAL_PATTERNS.items()
        }
        self._logging_compiled = [re.compile(p) for p in LOGGING_PATTERNS]

    def analyze(self, file_path: Path, content: str) -> list[Finding]:
        findings: list[Finding] = []
        for category, (patterns, message, description, article) in self._compiled.items():
            seen_lines: set[int] = set()
            for pattern in patterns:
                for line_no, line in self._match_lines(content, pattern):
                    if line_no in seen_lines:
                        continue
                    seen_lines.add(line_no)
                    findings.append(
                        self._make_finding(
                            file_path=file_path,
                            line_number=line_no,
                            severity=Severity.INFO,
                            category=f"pattern:{category}",
                            message=message,
                            description=f"{description} Match: `{line.strip()[:120]}`",
                            article=article,
                        )
                    )
        findings.extend(self._check_logging(file_path, content))
        return findings

    def _check_logging(self, file_path: Path, content: str) -> list[Finding]:
        """Flag Python files that use AI providers but have no logging."""
        if file_path.suffix != ".py":
            return []
        has_ai_usage = bool(
            re.search(r"\b(openai|anthropic|mistralai|ollama|transformers)\b", content)
        )
        has_logging = any(p.search(content) for p in self._logging_compiled)
        if has_ai_usage and not has_logging:
            return [
                self._make_finding(
                    file_path=file_path,
                    line_number=None,
                    severity=Severity.WARNING,
                    category="pattern:missing-logging",
                    message="AI usage without logging",
                    description=(
                        "File uses an AI provider but contains no logging. "
                        "High-risk AI systems must support automatic event recording."
                    ),
                    article="Art. 12 (record-keeping)",
                    suggestion="Add structured logging around AI model calls.",
                )
            ]
        return []
