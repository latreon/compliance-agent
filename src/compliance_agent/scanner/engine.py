"""Main scanner engine: walks a project tree and runs detectors on each file."""

import logging
from datetime import datetime
from pathlib import Path

from compliance_agent.models.findings import Finding, ScanResult
from compliance_agent.scanner.detectors import ALL_DETECTORS
from compliance_agent.scanner.detectors.base import BaseDetector

logger = logging.getLogger(__name__)

SCANNABLE_SUFFIXES = {".py", ".yaml", ".yml", ".json", ".toml", ".md"}
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
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


class ScannerEngine:
    """Scans a project directory for AI usage and compliance-relevant patterns."""

    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.detectors = self._load_detectors()

    def _load_detectors(self) -> list[BaseDetector]:
        return [detector_cls() for detector_cls in ALL_DETECTORS]

    def _collect_files(self) -> list[Path]:
        """Collect scannable files, skipping vendored/cache directories."""
        files: list[Path] = []
        for path in sorted(self.project_path.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in SCANNABLE_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(self.project_path).parts):
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
        """Scan the project and return findings."""
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
            findings=findings,
            scan_time=datetime.now(),
            files_scanned=len(files),
        )
