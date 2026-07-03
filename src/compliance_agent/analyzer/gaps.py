"""Compliance gap analyzer: orchestrates per-article analyzers.

Callers must set risk fields (risk_tier, risk_assessment) on the ScanResult
BEFORE calling analyze()/coverage() — article applicability depends on them.
"""

from compliance_agent.analyzer.articles import ALL_ARTICLE_ANALYZERS
from compliance_agent.analyzer.articles.base import ProjectProbe
from compliance_agent.models.findings import (
    ArticleCoverage,
    ComplianceGap,
    ScanResult,
    Severity,
)

_SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.WARNING: 2,
    Severity.INFO: 3,
}


class GapAnalyzer:
    """Identifies compliance gaps across all tracked EU AI Act articles."""

    def __init__(self) -> None:
        self.analyzers = [analyzer_cls() for analyzer_cls in ALL_ARTICLE_ANALYZERS]

    def analyze(self, scan_result: ScanResult) -> list[ComplianceGap]:
        """Return all gaps, most severe first."""
        probe = ProjectProbe(scan_result.project_path)
        gaps: list[ComplianceGap] = []
        for analyzer in self.analyzers:
            gaps.extend(analyzer.analyze(scan_result, probe))
        return sorted(gaps, key=lambda g: _SEVERITY_RANK[g.severity])

    def coverage(self, scan_result: ScanResult) -> list[ArticleCoverage]:
        """Return the per-article coverage table."""
        probe = ProjectProbe(scan_result.project_path)
        return [analyzer.coverage(scan_result, probe) for analyzer in self.analyzers]
