"""Base detector interface and shared regex helpers."""

import re
from abc import ABC, abstractmethod
from pathlib import Path

from compliance_agent.models.findings import Finding, Severity


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
