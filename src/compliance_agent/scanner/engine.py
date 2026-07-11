"""Main scanner engine: walks a project tree and runs detectors on each file.

Path filtering order (cheapest first, applied before reading file contents):
1. Hard-skip directories (.git, .venv, node_modules, ...) — always skipped.
2. .gitignore rules from the project root (via pathspec).
3. User-supplied --exclude glob patterns.
4. User-supplied --include glob patterns (when given, only matches are scanned).
"""

import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pathspec

from compliance_agent.models.findings import Finding, FrameworkDetection, ScanResult
from compliance_agent.scanner.detectors import ALL_DETECTORS
from compliance_agent.scanner.detectors.base import BaseDetector
from compliance_agent.scanner.parser import JS_TS_SUFFIXES, strip_comments, strip_js_comments

logger = logging.getLogger(__name__)

CODE_SUFFIXES = {".py"} | JS_TS_SUFFIXES
SCANNABLE_SUFFIXES = CODE_SUFFIXES | {".yaml", ".yml", ".json", ".toml", ".md"}
# Cap on the domain-classification corpus (relative paths + bounded file text).
# Large enough to catch domain language across a real project, small enough to
# keep the classifier's keyword regex fast.
DOMAIN_CORPUS_MAX_BYTES = 500_000
DOMAIN_CORPUS_PER_FILE_BYTES = 20_000
HARD_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".tox",
    ".eggs",
}
MAX_FILE_SIZE_BYTES = 1_000_000  # skip files above 1 MB


_TEST_DIRS = {"tests", "test", "testing", "__tests__"}


def _is_test_path(rel_path: Path) -> bool:
    """True for test files/dirs, which carry sample data, not the real system.

    Matching is case-insensitive so a capitalized ``Tests/`` directory (common
    in scaffolded or .NET/Java-influenced repos) is still recognised as test
    code and cannot leak fixtures into the domain corpus or the article probes.
    """
    if any(part.lower() in _TEST_DIRS for part in rel_path.parts):
        return True
    name = rel_path.name.lower()
    return name.startswith("test_") or rel_path.stem.lower().endswith("_test")


def _read_text_capped(path: Path) -> str:
    """Read a file as UTF-8 (BOM-stripped), capped to the size limit.

    Reading is capped independently of ``stat()`` so a file that misreports
    its size (e.g. a device node reached through a symlink) cannot stream
    unboundedly. ``utf-8-sig`` transparently drops a leading BOM, so
    BOM-prefixed sources (common from Windows editors) still parse cleanly
    instead of failing every AST detector.
    """
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        return handle.read(MAX_FILE_SIZE_BYTES + 1)


def _build_spec(patterns: Sequence[str]) -> pathspec.GitIgnoreSpec | None:
    """GitIgnoreSpec gives full git semantics (dir patterns match descendants)."""
    if not patterns:
        return None
    return pathspec.GitIgnoreSpec.from_lines(patterns)


class ScannerEngine:
    """Scans a project directory for AI usage and compliance-relevant patterns."""

    def __init__(
        self,
        project_path: Path,
        exclude: Sequence[str] | None = None,
        include: Sequence[str] | None = None,
    ):
        self.project_path = Path(project_path)
        self.detectors = self._load_detectors()
        self._gitignore_spec = self._load_gitignore()
        self._exclude_spec = _build_spec(exclude or [])
        self._include_spec = _build_spec(include or [])
        # Lowercased corpus of scanned relative paths + bounded file content,
        # populated by scan(). The risk classifier matches Annex III / Art. 5
        # domain keywords against this so classification reflects what the code
        # actually does — not merely how files happen to be named. Honors the
        # same exclude/include/.gitignore filtering as the scan itself.
        self.domain_corpus: str = ""

    def _load_detectors(self) -> list[BaseDetector]:
        return [detector_cls() for detector_cls in ALL_DETECTORS]

    def _load_gitignore(self) -> pathspec.GitIgnoreSpec | None:
        gitignore = self.project_path / ".gitignore"
        if not gitignore.is_file():
            return None
        try:
            # errors="replace" so a non-UTF-8 .gitignore (stray bytes, Windows
            # tooling, bad merges) degrades gracefully instead of crashing.
            lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            logger.warning("Cannot read .gitignore: %s", exc)
            return None
        return pathspec.GitIgnoreSpec.from_lines(lines)

    def _should_skip_path(self, path: Path) -> bool:
        """Return True when the path must not be scanned."""
        rel = path.relative_to(self.project_path)
        if any(part in HARD_SKIP_DIRS or part.endswith(".egg-info") for part in rel.parts):
            return True
        rel_str = rel.as_posix()
        if self._gitignore_spec and self._gitignore_spec.match_file(rel_str):
            return True
        if self._exclude_spec and self._exclude_spec.match_file(rel_str):
            return True
        return bool(self._include_spec and not self._include_spec.match_file(rel_str))

    def _collect_files(self) -> list[Path]:
        """Collect scannable files, applying all exclusion rules before reads."""
        files: list[Path] = []
        for path in sorted(self.project_path.rglob("*")):
            # Never follow symlinks. Scanning untrusted third-party repos is the
            # norm, and a symlinked file can point outside the project (e.g.
            # `utils.py -> ~/.ssh/id_rsa`, materialized by git) or at a device
            # node (`/dev/zero`, whose stat size is 0) that would bypass the
            # size cap and hang on read.
            if path.is_symlink():
                continue
            if not path.is_file():
                continue
            if path.suffix not in SCANNABLE_SUFFIXES:
                continue
            if self._should_skip_path(path):
                continue
            try:
                if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                    logger.warning("Skipping oversized file: %s", path)
                    continue
            except OSError as exc:
                logger.warning("Cannot stat %s: %s", path, exc)
                continue
            files.append(path)
        return files

    def scan(self) -> ScanResult:
        """Scan the project and return deduplicated findings."""
        files = self._collect_files()
        logger.info(
            "Collected %d scannable file(s) under %s (running %d detectors)",
            len(files),
            self.project_path,
            len(self.detectors),
        )
        findings: list[Finding] = []
        scan_errors: list[str] = []
        corpus_parts: list[str] = []
        corpus_size = 0
        for file_path in files:
            try:
                content = _read_text_capped(file_path)
            except OSError as exc:
                logger.warning("Cannot read %s: %s", file_path, exc)
                continue
            if corpus_size < DOMAIN_CORPUS_MAX_BYTES:
                try:
                    rel_path = file_path.relative_to(self.project_path)
                    rel = rel_path.as_posix()
                except ValueError:
                    rel_path = Path(file_path.name)
                    rel = file_path.name
                # Test fixtures routinely name high-risk domains as sample data —
                # they are not the deployed AI system, so they must not drive risk
                # classification.
                if not _is_test_path(rel_path):
                    # Path always contributes (a domain-named directory is a real
                    # signal); free-text content is trusted only from code files —
                    # prose/config/keyword-lists are false-positive prone (e.g. a
                    # README that merely disclaims a banned practice). Comments are
                    # stripped from code too: a comment that merely *names* a
                    # high-risk/prohibited practice (or a keyword list explaining
                    # the rules, as in this tool's own source) is prose, not
                    # behaviour, and must not escalate the risk tier. String
                    # literals (prompt templates) are kept — they are real signal.
                    snippet_text = content[:DOMAIN_CORPUS_PER_FILE_BYTES]
                    if file_path.suffix == ".py":
                        body = strip_comments(snippet_text)
                    elif file_path.suffix in JS_TS_SUFFIXES:
                        body = strip_js_comments(snippet_text)
                    else:
                        body = ""
                    snippet = f"{rel}\n{body}"
                    corpus_parts.append(snippet)
                    corpus_size += len(snippet)
            for detector in self.detectors:
                try:
                    findings.extend(detector.analyze(file_path, content))
                except Exception as exc:  # a broken detector must not kill the scan
                    logger.error("Detector %s failed on %s: %s", detector.name, file_path, exc)
                    # Record it too: a crash swallowed only to stderr makes a
                    # saved report read as clean when coverage was incomplete.
                    try:
                        where = file_path.relative_to(self.project_path).as_posix()
                    except ValueError:
                        where = file_path.name
                    scan_errors.append(f"{detector.name} failed on {where}: {exc}")
        self.domain_corpus = "\n".join(corpus_parts).lower()
        deduped = self._dedupe(self._relativize(findings))
        logger.info(
            "Scan complete: %d finding(s) after dedupe, %d detector error(s)",
            len(deduped),
            len(scan_errors),
        )
        return ScanResult(
            project_path=str(self.project_path),
            findings=deduped,
            scan_time=datetime.now(),
            files_scanned=len(files),
            frameworks_detected=self._summarize_frameworks(deduped),
            scan_errors=scan_errors,
        )

    @staticmethod
    def _summarize_frameworks(findings: list[Finding]) -> list[FrameworkDetection]:
        """Aggregate framework-detector findings into per-framework summaries."""
        grouped: dict[str, dict] = {}
        for finding in findings:
            if not finding.detector.startswith("frameworks:"):
                continue
            name = finding.detector.split(":", 1)[1]
            entry = grouped.setdefault(name, {"patterns": set(), "notes": []})
            pattern = (
                finding.category.split("_", 1)[1] if "_" in finding.category else finding.category
            )
            entry["patterns"].add(pattern)
            if finding.suggestion and finding.suggestion not in entry["notes"]:
                entry["notes"].append(finding.suggestion)
        return [
            FrameworkDetection(
                name=name,
                patterns=sorted(data["patterns"]),
                risk_notes=data["notes"],
            )
            for name, data in sorted(grouped.items())
        ]

    def _relativize(self, findings: list[Finding]) -> list[Finding]:
        """Rewrite finding paths relative to the project root for readable reports."""
        relativized = []
        for finding in findings:
            path = Path(finding.file_path)
            try:
                rel = path.relative_to(self.project_path)
            except ValueError:
                relativized.append(finding)
                continue
            relativized.append(
                finding.model_copy(
                    update={
                        "file_path": str(rel),
                        "id": (
                            f"{finding.detector}:{finding.category}:"
                            f"{rel}:{finding.line_number or 0}"
                        ),
                    }
                )
            )
        return relativized

    @staticmethod
    def _dedupe(findings: list[Finding]) -> list[Finding]:
        """Collapse repeated (detector, category, file) hits into one finding.

        Keeps the first (lowest line number) occurrence and records the total
        occurrence count on the surviving finding.
        """
        merged: dict[tuple[str, str, str], Finding] = {}
        ordered = sorted(findings, key=lambda f: (f.file_path, f.line_number or 0))
        for finding in ordered:
            key = (finding.detector, finding.category, finding.file_path)
            if key in merged:
                existing = merged[key]
                merged[key] = existing.model_copy(update={"occurrences": existing.occurrences + 1})
            else:
                merged[key] = finding
        return list(merged.values())
