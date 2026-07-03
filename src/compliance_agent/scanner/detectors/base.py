"""Base detector interface and shared AI-context helpers."""

import re
from abc import ABC, abstractmethod
from pathlib import Path

from compliance_agent.models.findings import Finding, Severity
from compliance_agent.scanner.parser import extract_imports

# Top-level modules whose import marks a file as AI-relevant.
AI_TOP_LEVEL_MODULES = {
    "openai",
    "anthropic",
    "mistralai",
    "transformers",
    "ollama",
    "vllm",
    "torch",
    "llama_cpp",
    "langchain",
    "langchain_core",
    "langchain_community",
    "crewai",
    "autogen",
    "langgraph",
}


def detect_ai_imports(file_path: Path, content: str) -> set[str]:
    """Return AI-related modules actually imported by a Python file.

    Uses AST-based import extraction, so provider names in comments,
    docstrings, or string literals do not count.
    """
    if file_path.suffix != ".py":
        return set()
    imports = extract_imports(file_path, content)
    found = {name.split(".")[0] for name in imports} & AI_TOP_LEVEL_MODULES
    if any(
        name == "google.generativeai" or name.startswith("google.generativeai.") for name in imports
    ):
        found.add("google.generativeai")
    return found


class BaseDetector(ABC):
    """Base class for all detectors.

    Subclasses implement `analyze` to inspect a single file's content and
    return zero or more findings.
    """

    name: str = "base"

    @abstractmethod
    def analyze(self, file_path: Path, content: str) -> list[Finding]:
        """Analyze a file and return findings."""

    def _match_lines(self, content: str, pattern: re.Pattern[str]) -> list[tuple[int, str]]:
        """Return (1-based line number, line) pairs matching the pattern."""
        matches = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            if pattern.search(line):
                matches.append((line_no, line))
        return matches

    def _make_finding(
        self,
        *,
        file_path: Path,
        line_number: int | None,
        severity: Severity,
        category: str,
        message: str,
        description: str,
        article: str | None = None,
        suggestion: str | None = None,
    ) -> Finding:
        """Build a Finding with a deterministic ID."""
        finding_id = f"{self.name}:{category}:{file_path}:{line_number or 0}"
        return Finding(
            id=finding_id,
            file_path=str(file_path),
            line_number=line_number,
            detector=self.name,
            severity=severity,
            category=category,
            message=message,
            description=description,
            article=article,
            suggestion=suggestion,
        )
