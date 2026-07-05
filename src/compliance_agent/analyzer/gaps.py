"""Compliance gap analyzer: orchestrates per-article analyzers.

Callers must set risk fields (risk_tier, risk_assessment) on the ScanResult
BEFORE calling analyze()/coverage() — article applicability depends on them.
"""

from compliance_agent.analyzer.articles import ALL_ARTICLE_ANALYZERS
from compliance_agent.analyzer.articles.base import ProjectProbe
from compliance_agent.models.findings import (
    SEVERITY_ORDER,
    ArticleCoverage,
    ComplianceGap,
    ScanResult,
)


class GapAnalyzer:
    """Identifies compliance gaps across all tracked EU AI Act articles."""

    def __init__(self) -> None:
        self.analyzers = [analyzer_cls() for analyzer_cls in ALL_ARTICLE_ANALYZERS]
        self._probe: ProjectProbe | None = None

    def _probe_for(self, scan_result: ScanResult) -> ProjectProbe:
        """Return a probe for the project, reusing one across analyze/coverage.

        analyze() and coverage() are called back-to-back on the same result;
        a shared probe avoids reading every doc/source file from disk twice
        (its doc_text/code_text are cached per instance).
        """
        path = str(scan_result.project_path)
        if self._probe is None or str(self._probe.root) != path:
            self._probe = ProjectProbe(path)
        return self._probe

    def analyze(self, scan_result: ScanResult) -> list[ComplianceGap]:
        """Return all gaps, most severe first."""
        probe = self._probe_for(scan_result)
        gaps: list[ComplianceGap] = []
        for analyzer in self.analyzers:
            gaps.extend(analyzer.analyze(scan_result, probe))
        # Most severe first — negate the shared ascending order so there is a
        # single source of truth for severity ranking (see models.findings).
        return sorted(gaps, key=lambda g: -SEVERITY_ORDER[g.severity])

    def coverage(self, scan_result: ScanResult) -> list[ArticleCoverage]:
        """Return the per-article coverage table."""
        probe = self._probe_for(scan_result)
        return [analyzer.coverage(scan_result, probe) for analyzer in self.analyzers]
