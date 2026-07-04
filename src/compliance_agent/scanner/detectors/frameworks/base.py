"""Base class for framework-specific detectors.

A framework detector only fires on files that actually import the framework
(AST-verified), then matches declarative pattern rules. Each rule carries its
own compliance mapping (article + suggestion), so findings are precise and
actionable.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from compliance_agent.models.findings import Finding, Severity
from compliance_agent.scanner.detectors.base import BaseDetector
from compliance_agent.scanner.parser import extract_imports, top_level_modules


@dataclass(frozen=True)
class FrameworkRule:
    """One detectable framework pattern with its compliance mapping."""

    category: str  # e.g. "langchain_agent"
    patterns: tuple[str, ...]  # regexes matched per line
    message: str
    description: str
    article: str
    suggestion: str
    severity: Severity = Severity.INFO
    _compiled: tuple[re.Pattern[str], ...] = field(default=(), compare=False, repr=False)

    def __post_init__(self) -> None:
        # Compile once at construction (rules are module-level constants).
        # object.__setattr__ is required because the dataclass is frozen; this
        # avoids lazy mutation that would not be thread-safe under parallelism.
        object.__setattr__(self, "_compiled", tuple(re.compile(p) for p in self.patterns))

    def compiled(self) -> tuple[re.Pattern[str], ...]:
        return self._compiled


class FrameworkDetector(BaseDetector):
    """Base class for framework-specific detectors.

    Subclasses set `framework_name`, `import_modules` (top-level packages
    whose import marks the file as using the framework), and `rules`.
    """

    framework_name: str = ""
    import_modules: frozenset[str] = frozenset()
    rules: tuple[FrameworkRule, ...] = ()

    def __init__(self) -> None:
        self.name = f"frameworks:{self.framework_name}"

    def uses_framework(self, file_path: Path, content: str) -> bool:
        """True when the file imports the framework (AST-verified)."""
        if file_path.suffix != ".py":
            return False
        imports = top_level_modules(extract_imports(file_path, content))
        return bool(imports & self.import_modules)

    def analyze(self, file_path: Path, content: str) -> list[Finding]:
        if not self.uses_framework(file_path, content):
            return []
        findings: list[Finding] = []
        for rule in self.rules:
            seen_lines: set[int] = set()
            for pattern in rule.compiled():
                for line_no, _line in self._match_lines(content, pattern):
                    if line_no in seen_lines:
                        continue
                    seen_lines.add(line_no)
                    findings.append(
                        self._make_finding(
                            file_path=file_path,
                            line_number=line_no,
                            severity=rule.severity,
                            category=rule.category,
                            message=rule.message,
                            description=rule.description,
                            article=rule.article,
                            suggestion=rule.suggestion,
                        )
                    )
        return findings
