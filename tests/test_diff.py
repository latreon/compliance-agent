"""Tests for scan-to-scan comparison (diff)."""

from datetime import datetime

from compliance_agent.diff import diff_scan_results
from compliance_agent.models.findings import (
    ArticleCoverage,
    ComplianceGap,
    Finding,
    RiskTier,
    ScanResult,
    Severity,
)


def _finding(detector: str, category: str, file_path: str, line: int = 1) -> Finding:
    return Finding(
        id=f"{detector}:{category}:{file_path}:{line}",
        file_path=file_path,
        line_number=line,
        detector=detector,
        severity=Severity.WARNING,
        category=category,
        message="m",
        description="d",
    )


def _gap(
    gap_id: str,
    article: str,
    severity: Severity = Severity.HIGH,
    status: str = "missing",
) -> ComplianceGap:
    return ComplianceGap(
        id=gap_id,
        title=f"gap {gap_id}",
        article=article,
        severity=severity,
        description="desc",
        recommendation="fix",
        status=status,
    )


def _result(
    *,
    tier: RiskTier = RiskTier.LIMITED,
    findings: list[Finding] | None = None,
    gaps: list[ComplianceGap] | None = None,
    coverage: list[ArticleCoverage] | None = None,
) -> ScanResult:
    return ScanResult(
        project_path="/proj",
        findings=findings or [],
        scan_time=datetime(2026, 1, 1, 12, 0, 0),
        files_scanned=10,
        risk_tier=tier,
        gaps=gaps or [],
        coverage=coverage or [],
    )


def test_identical_scans_report_no_change() -> None:
    base = _result(
        gaps=[_gap("g1", "Art. 9")], findings=[_finding("providers", "provider:openai", "a.py")]
    )
    target = _result(
        gaps=[_gap("g1", "Art. 9")], findings=[_finding("providers", "provider:openai", "a.py")]
    )

    diff = diff_scan_results(base, target)

    assert diff.verdict == "unchanged"
    assert diff.gaps_new == [] and diff.gaps_resolved == []
    assert diff.findings_added == [] and diff.findings_removed == []
    assert diff.tier_direction == "unchanged"


def test_resolved_gap_is_an_improvement() -> None:
    base = _result(gaps=[_gap("g1", "Art. 9"), _gap("g2", "Art. 10")])
    target = _result(gaps=[_gap("g1", "Art. 9")])

    diff = diff_scan_results(base, target)

    assert [g.id for g in diff.gaps_resolved] == ["g2"]
    assert diff.gaps_new == []
    assert diff.verdict == "improved"


def test_new_gap_is_a_regression() -> None:
    base = _result(gaps=[_gap("g1", "Art. 9")])
    target = _result(gaps=[_gap("g1", "Art. 9"), _gap("g3", "Art. 14")])

    diff = diff_scan_results(base, target)

    assert [g.id for g in diff.gaps_new] == ["g3"]
    assert diff.gaps_resolved == []
    assert diff.verdict == "regressed"


def test_lower_tier_is_an_improvement() -> None:
    base = _result(tier=RiskTier.HIGH)
    target = _result(tier=RiskTier.LIMITED)

    diff = diff_scan_results(base, target)

    assert diff.tier_direction == "improved"
    assert diff.verdict == "improved"


def test_higher_tier_is_a_regression() -> None:
    base = _result(tier=RiskTier.LIMITED)
    target = _result(tier=RiskTier.HIGH)

    diff = diff_scan_results(base, target)

    assert diff.tier_direction == "regressed"
    assert diff.verdict == "regressed"


def test_findings_matched_by_detector_category_file_ignoring_line() -> None:
    # Same logical finding, moved to a different line — not added/removed.
    base = _result(findings=[_finding("patterns", "pattern:user-input", "a.py", line=5)])
    target = _result(findings=[_finding("patterns", "pattern:user-input", "a.py", line=42)])

    diff = diff_scan_results(base, target)

    assert diff.findings_added == []
    assert diff.findings_removed == []
    assert diff.findings_unchanged == 1


def test_added_and_removed_findings_are_reported() -> None:
    base = _result(findings=[_finding("providers", "provider:openai", "a.py")])
    target = _result(findings=[_finding("providers", "provider:anthropic", "b.py")])

    diff = diff_scan_results(base, target)

    assert [f.category for f in diff.findings_removed] == ["provider:openai"]
    assert [f.category for f in diff.findings_added] == ["provider:anthropic"]


def test_requirements_met_counts_from_coverage() -> None:
    base = _result(
        coverage=[
            ArticleCoverage(
                article="Art. 9",
                title="t",
                status="partial",
                requirements_met=1,
                requirements_total=3,
            )
        ]
    )
    target = _result(
        coverage=[
            ArticleCoverage(
                article="Art. 9", title="t", status="met", requirements_met=3, requirements_total=3
            )
        ]
    )

    diff = diff_scan_results(base, target)

    assert diff.requirements_met_base == 1
    assert diff.requirements_met_target == 3
    assert diff.requirements_total_target == 3


def test_gain_and_loss_together_is_mixed() -> None:
    base = _result(gaps=[_gap("g1", "Art. 9")])
    target = _result(gaps=[_gap("g2", "Art. 10")])

    diff = diff_scan_results(base, target)

    assert [g.id for g in diff.gaps_resolved] == ["g1"]
    assert [g.id for g in diff.gaps_new] == ["g2"]
    assert diff.verdict == "mixed"


def test_not_applicable_coverage_excluded_from_requirement_totals() -> None:
    base = _result(
        coverage=[
            ArticleCoverage(
                article="Art. 9",
                title="t",
                status="partial",
                requirements_met=1,
                requirements_total=2,
            ),
            ArticleCoverage(
                article="Art. 50",
                title="t",
                status="not_applicable",
                requirements_met=0,
                requirements_total=4,
            ),
        ]
    )
    target = _result(coverage=[])

    diff = diff_scan_results(base, target)

    # The not_applicable article's 4 requirements must not inflate the total.
    assert diff.requirements_total_base == 2


def test_gap_status_improvement_missing_to_unverified() -> None:
    # Remediation reached "unverified" (evidence added) but not full "met":
    # the diff must show movement, not silently count it as unchanged.
    base = _result(gaps=[_gap("g1", "Art. 9", status="missing")])
    target = _result(gaps=[_gap("g1", "Art. 9", status="unverified")])

    diff = diff_scan_results(base, target)

    assert [g.id for g in diff.gaps_status_changed] == ["g1"]
    assert diff.gaps_unchanged == 0
    assert diff.gaps_new == [] and diff.gaps_resolved == []
    assert diff.verdict == "improved"


def test_gap_status_regression_unverified_to_missing() -> None:
    base = _result(gaps=[_gap("g1", "Art. 9", status="unverified")])
    target = _result(gaps=[_gap("g1", "Art. 9", status="missing")])

    diff = diff_scan_results(base, target)

    assert [g.id for g in diff.gaps_status_changed] == ["g1"]
    assert diff.verdict == "regressed"


def test_same_status_gap_is_unchanged_not_status_changed() -> None:
    base = _result(gaps=[_gap("g1", "Art. 9", status="missing")])
    target = _result(gaps=[_gap("g1", "Art. 9", status="missing")])

    diff = diff_scan_results(base, target)

    assert diff.gaps_status_changed == []
    assert diff.gaps_unchanged == 1
    assert diff.verdict == "unchanged"
