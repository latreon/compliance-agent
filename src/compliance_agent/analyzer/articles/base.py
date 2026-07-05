"""Base class and shared signals for article-specific gap analyzers.

Each article analyzer declares its requirements as met/unmet checks against
the scan result plus a lightweight filesystem probe. Gaps and the coverage
table are both derived from the same requirement list, so they never drift.
"""

import io
import logging
import re
import tokenize
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from compliance_agent.models.findings import (
    ArticleCoverage,
    ComplianceGap,
    Finding,
    RequirementStatus,
    RiskTier,
    ScanResult,
    Severity,
)
from compliance_agent.scanner.engine import _is_test_path

logger = logging.getLogger(__name__)

_SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", "dist", "build"}
_TEST_DIRS = {"tests", "test", "testing", "__tests__"}
# Bounds keep the probe cheap on large repos. The file cap is generous so a
# real control living in an alphabetically-late path (e.g. src/z_middleware/)
# is not silently dropped, which would produce a false "MISSING".
_MAX_PROBE_FILES = 1000
_MAX_PROBE_BYTES = 200_000


def _strip_comments(source: str) -> str:
    """Return Python source with comments removed.

    A requirement can only be MET on a real code construct — a leftover
    ``# TODO: add a "you are interacting with an ai" notice`` comment must not
    count as an implemented mechanism. String literals (e.g. the actual notice
    text) are preserved, since they are genuine evidence. Falls back to the raw
    source if the file cannot be tokenized.
    """
    try:
        tokens = [
            tok
            for tok in tokenize.generate_tokens(io.StringIO(source).readline)
            if tok.type != tokenize.COMMENT
        ]
        return tokenize.untokenize(tokens)
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return source


def _mentions(text: str, terms: tuple[str, ...]) -> bool:
    """True when any term appears in text on word boundaries.

    Plain substring matching produced false "met" results — e.g. the term
    ``auth`` matching inside ``__author__``, or ``ai disclosure`` matching a
    sentence that says disclosure is *absent*. Word boundaries are applied only
    to alphanumeric edges, so terms ending in punctuation (``escape(``) or
    starting with it (``## usage``) still match correctly.
    """
    for term in terms:
        needle = term.lower()
        if not needle:
            continue
        left = r"(?<![0-9a-z])" if needle[0].isalnum() else ""
        right = r"(?![0-9a-z])" if needle[-1].isalnum() else ""
        if re.search(left + re.escape(needle) + right, text):
            return True
    return False


# ---------- scan-result signals ----------------------------------------------

# Signals gate which obligations apply and how severe they are, so they must
# reflect the DEPLOYED system. Findings that live under test paths are fixtures
# (mocked SDK imports, sample high-risk data) and must not drive obligations —
# the same rule the risk classifier applies.


def _production_findings(result: ScanResult) -> list[Finding]:
    return [f for f in result.findings if not _is_test_path(Path(f.file_path))]


def has_provider(result: ScanResult) -> bool:
    return any(f.category.startswith("provider:") for f in _production_findings(result))


def has_framework(result: ScanResult) -> bool:
    return any(f.detector.startswith("frameworks:") for f in _production_findings(result))


def has_ai(result: ScanResult) -> bool:
    return has_provider(result) or has_framework(result)


def has_user_interaction(result: ScanResult) -> bool:
    interactive = {
        "pattern:user-input",
        "pattern:chat-interface",
        "langchain_chain",
        "autogen_assistant",
    }
    return any(f.category in interactive for f in _production_findings(result))


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
        for f in _production_findings(result)
    )


def has_missing_logging(result: ScanResult) -> bool:
    return any(f.category == "pattern:missing-logging" for f in _production_findings(result))


def has_data_processing(result: ScanResult) -> bool:
    return any(f.category == "pattern:data-processing" for f in _production_findings(result))


def is_high_risk(result: ScanResult) -> bool:
    return result.risk_tier == RiskTier.HIGH


# ---------- filesystem probe ---------------------------------------------------


class ProjectProbe:
    """Cheap, cached filesystem checks for documentation and code signals."""

    def __init__(self, project_path: str | Path):
        self.root = Path(project_path)

    def any_file(self, *globs: str, min_content_chars: int = 0) -> bool:
        """True when any glob matches a file under the project root.

        ``min_content_chars`` guards against a placeholder artifact satisfying a
        mandatory control: an empty (or near-empty) ``risk_register.json`` —
        e.g. created with ``touch`` — must never flip a CRITICAL requirement to
        MET. When set, the file must hold at least that many non-whitespace
        characters to count. With the default 0, mere existence suffices.
        """
        if not self.root.is_dir():
            return False
        for pattern in globs:
            try:
                for path in self.root.glob(pattern):
                    if not path.is_file():
                        continue
                    if min_content_chars <= 0:
                        return True
                    try:
                        text = path.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    if len(text.strip()) >= min_content_chars:
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
        """Lowercased, comment-stripped text of project Python files (bounded).

        Comments are removed so prose in a comment cannot mark a requirement
        MET, and test directories are skipped so fixture code (which often
        contains sample controls/disclosures) is not counted as a real
        production mechanism.
        """
        if not self.root.is_dir():
            return ""
        chunks: list[str] = []
        count = 0
        for path in sorted(self.root.rglob("*.py")):
            rel = path.relative_to(self.root)
            # Case-insensitive: a capitalized ``Tests/`` (common in scaffolded or
            # .NET/Java-influenced repos) is still test/fixture code and must not
            # count as a production mechanism.
            if any(part.lower() in _SKIP_DIRS for part in rel.parts):
                continue
            if _is_test_path(rel):
                continue
            try:
                raw = path.read_text(encoding="utf-8-sig", errors="replace")[:_MAX_PROBE_BYTES]
            except OSError:
                continue
            chunks.append(_strip_comments(raw))
            count += 1
            if count >= _MAX_PROBE_FILES:
                break
        return "\n".join(chunks).lower()

    def docs_mention(self, *terms: str) -> bool:
        return _mentions(self.doc_text, terms)

    def code_mentions(self, *terms: str) -> bool:
        return _mentions(self.code_text, terms)


# ---------- requirements and the base analyzer -----------------------------------


def evidence(*, mechanism: bool, mention: bool = False) -> RequirementStatus:
    """Grade a requirement from its evidence.

    ``mechanism`` is a verifiable signal — a real code construct (``try/except``,
    an oversight checkpoint) or a concrete artifact file on disk. It is the only
    thing that can mark a requirement MET. ``mention`` is a bare keyword hit in
    documentation prose; on its own it can only downgrade MISSING to UNVERIFIED,
    never confirm compliance.
    """
    if mechanism:
        return RequirementStatus.MET
    if mention:
        return RequirementStatus.UNVERIFIED
    return RequirementStatus.MISSING


@dataclass(frozen=True)
class Requirement:
    """One checkable obligation under an article."""

    name: str
    status: RequirementStatus
    severity: Severity
    details: str
    suggestion: str

    @property
    def met(self) -> bool:
        return self.status is RequirementStatus.MET


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
            self._create_gap(req)
            for req in self.requirements(scan_result, probe)
            if req.status is not RequirementStatus.MET
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
        total = len(reqs)
        met = sum(1 for r in reqs if r.status is RequirementStatus.MET)
        missing = sum(1 for r in reqs if r.status is RequirementStatus.MISSING)
        if total and met == total:
            status = "met"
        elif total and missing == total:
            status = "missing"
        elif met == 0 and missing == 0:
            # Nothing confirmed, nothing outright absent — only doc references.
            status = "unverified"
        else:
            status = "partial"
        return ArticleCoverage(
            article=article,
            title=self.article_title,
            status=status,
            requirements_met=met,
            requirements_total=total,
        )

    def _create_gap(self, req: Requirement) -> ComplianceGap:
        if req.status is RequirementStatus.UNVERIFIED:
            gap_status = "unverified"
            description = (
                f"{req.details} A related reference was found in documentation, but "
                "no implementing mechanism could be verified automatically."
            )
            recommendation = f"Verify manually, then: {req.suggestion}"
        else:
            gap_status = "missing"
            description = req.details
            recommendation = req.suggestion
        return ComplianceGap(
            id=f"gap:art{self.article_number}:{_slug(req.name)}",
            title=req.name,
            article=f"Art. {self.article_number}",
            article_title=self.article_title,
            requirement=req.name,
            status=gap_status,
            severity=req.severity,
            description=description,
            recommendation=recommendation,
        )
