"""Base class and shared signals for article-specific gap analyzers.

Each article analyzer declares its requirements as met/unmet checks against
the scan result plus a lightweight filesystem probe. Gaps and the coverage
table are both derived from the same requirement list, so they never drift.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from compliance_agent.models.findings import (
    ArticleCoverage,
    ComplianceGap,
    RiskTier,
    ScanResult,
    Severity,
)

logger = logging.getLogger(__name__)

_SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", "dist", "build"}
_MAX_PROBE_FILES = 200
_MAX_PROBE_BYTES = 200_000


# ---------- scan-result signals ----------------------------------------------


def has_provider(result: ScanResult) -> bool:
    return any(f.category.startswith("provider:") for f in result.findings)


def has_framework(result: ScanResult) -> bool:
    return bool(result.frameworks_detected) or any(
        f.detector.startswith("frameworks:") for f in result.findings
    )


def has_ai(result: ScanResult) -> bool:
    return has_provider(result) or has_framework(result)


def has_user_interaction(result: ScanResult) -> bool:
    interactive = {
        "pattern:user-input",
        "pattern:chat-interface",
        "langchain_chain",
        "autogen_assistant",
    }
    return any(f.category in interactive for f in result.findings)


def has_agents(result: ScanResult) -> bool:
    agentic_prefixes = ("agent:",)
    agentic_categories = {
        "langchain_agent",
        "crewai_crew",
        "crewai_agent",
        "autogen_groupchat",
        "autogen_userproxy",
        "langgraph_conditional",
    }
    return any(
        f.category.startswith(agentic_prefixes) or f.category in agentic_categories
        for f in result.findings
    )


def has_missing_logging(result: ScanResult) -> bool:
    return any(f.category == "pattern:missing-logging" for f in result.findings)


def has_data_processing(result: ScanResult) -> bool:
    return any(f.category == "pattern:data-processing" for f in result.findings)


def is_high_risk(result: ScanResult) -> bool:
    return result.risk_tier == RiskTier.HIGH


# ---------- filesystem probe ---------------------------------------------------


class ProjectProbe:
    """Cheap, cached filesystem checks for documentation and code signals."""

    def __init__(self, project_path: str | Path):
        self.root = Path(project_path)

    def any_file(self, *globs: str) -> bool:
        """True when any glob matches an existing file under the project root."""
        if not self.root.is_dir():
            return False
        for pattern in globs:
            try:
                if any(p.is_file() for p in self.root.glob(pattern)):
                    return True
            except OSError as exc:
                logger.debug("probe glob failed for %s: %s", pattern, exc)
        return False

    @cached_property
    def doc_text(self) -> str:
        """Lowercased text of README* and docs/**/*.md."""
        if not self.root.is_dir():
            return ""
        chunks: list[str] = []
        candidates = list(self.root.glob("README*")) + list(self.root.glob("docs/**/*.md"))
        for path in candidates[:_MAX_PROBE_FILES]:
            if path.is_file():
                try:
                    chunks.append(
                        path.read_text(encoding="utf-8", errors="replace")[:_MAX_PROBE_BYTES]
                    )
                except OSError:
                    continue
        return "\n".join(chunks).lower()

    @cached_property
    def code_text(self) -> str:
        """Lowercased text of project Python files (bounded)."""
        if not self.root.is_dir():
            return ""
        chunks: list[str] = []
        count = 0
        for path in sorted(self.root.rglob("*.py")):
            rel_parts = path.relative_to(self.root).parts
            if any(part in _SKIP_DIRS for part in rel_parts):
                continue
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="replace")[:_MAX_PROBE_BYTES])
            except OSError:
                continue
            count += 1
            if count >= _MAX_PROBE_FILES:
                break
        return "\n".join(chunks).lower()

    def docs_mention(self, *terms: str) -> bool:
        return any(term.lower() in self.doc_text for term in terms)

    def code_mentions(self, *terms: str) -> bool:
        return any(term.lower() in self.code_text for term in terms)


# ---------- requirements and the base analyzer -----------------------------------


@dataclass(frozen=True)
class Requirement:
    """One checkable obligation under an article."""

    name: str
    met: bool
    severity: Severity
    details: str
    suggestion: str


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


class ArticleAnalyzer(ABC):
    """Base class for article-specific gap analyzers."""

    article_number: int = 0
    article_title: str = ""

    def applies(self, scan_result: ScanResult) -> bool:
        """Whether this article applies to the scanned project at all."""
        return True

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        tier = scan_result.risk_tier.value if scan_result.risk_tier else "unknown"
        return f"tier: {tier}"

    @abstractmethod
    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        """Evaluate every requirement this analyzer tracks."""

    def analyze(
        self, scan_result: ScanResult, probe: ProjectProbe | None = None
    ) -> list[ComplianceGap]:
        """Return one gap per unmet requirement (empty when not applicable)."""
        if not self.applies(scan_result):
            return []
        probe = probe or ProjectProbe(scan_result.project_path)
        return [
            self._create_gap(req) for req in self.requirements(scan_result, probe) if not req.met
        ]

    def coverage(
        self, scan_result: ScanResult, probe: ProjectProbe | None = None
    ) -> ArticleCoverage:
        """Return the coverage-table entry for this article."""
        article = f"Art. {self.article_number}"
        if not self.applies(scan_result):
            return ArticleCoverage(
                article=article,
                title=self.article_title,
                status="not_applicable",
                reason=self.not_applicable_reason(scan_result),
            )
        probe = probe or ProjectProbe(scan_result.project_path)
        reqs = self.requirements(scan_result, probe)
        met = sum(1 for r in reqs if r.met)
        if met == len(reqs):
            status = "met"
        elif met == 0:
            status = "missing"
        else:
            status = "partial"
        return ArticleCoverage(
            article=article,
            title=self.article_title,
            status=status,
            requirements_met=met,
            requirements_total=len(reqs),
        )

    def _create_gap(self, req: Requirement) -> ComplianceGap:
        return ComplianceGap(
            id=f"gap:art{self.article_number}:{_slug(req.name)}",
            title=req.name,
            article=f"Art. {self.article_number}",
            article_title=self.article_title,
            requirement=req.name,
            status="missing",
            severity=req.severity,
            description=req.details,
            recommendation=req.suggestion,
        )
