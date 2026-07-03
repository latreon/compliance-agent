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

from compliance_agent.models.findings import Finding, ScanResult
from compliance_agent.scanner.detectors import ALL_DETECTORS
from compliance_agent.scanner.detectors.base import BaseDetector

logger = logging.getLogger(__name__)

SCANNABLE_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".toml", ".md"}
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

    def _load_detectors(self) -> list[BaseDetector]:
        return [detector_cls() for detector_cls in ALL_DETECTORS]

    def _load_gitignore(self) -> pathspec.GitIgnoreSpec | None:
        gitignore = self.project_path / ".gitignore"
        if not gitignore.is_file():
            return None
        try:
            lines = gitignore.read_text(encoding="utf-8").splitlines()
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
            if not path.is_file():
                continue
            if path.suffix not in SCANNABLE_SUFFIXES and path.name != ".mcp.json":
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
        findings: list[Finding] = []
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                logger.warning("Cannot read %s: %s", file_path, exc)
                continue
            for detector in self.detectors:
                try:
                    findings.extend(detector.analyze(file_path, content))
                except Exception as exc:  # a broken detector must not kill the scan
                    logger.error("Detector %s failed on %s: %s", detector.name, file_path, exc)
        return ScanResult(
            project_path=str(self.project_path),
            findings=self._dedupe(self._relativize(findings)),
            scan_time=datetime.now(),
            files_scanned=len(files),
        )

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
