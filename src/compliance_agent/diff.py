"""Compare two scans to see whether compliance improved or regressed.

The comparison is deliberately conservative about what counts as an
improvement or a regression: the compliance signal lives in the *gaps* (missing
obligations) and the *risk tier*, so the overall verdict is driven by those.
Findings — which are AI-usage observations, mostly informational — are diffed
and reported for context but do not, on their own, flip the verdict.

Identity rules:
- Findings match on ``(detector, category, file_path)`` so a finding that only
  moved to a different line is "unchanged", not removed-and-re-added. A
  matched finding whose ``severity`` differs between scans (e.g. after a
  ComplianceAgent upgrade reclassifies a category) is reported separately as
  "severity changed", not silently folded into "unchanged" — the same
  visibility gaps already get via ``gaps_status_changed``.
- Gaps match on their stable ``id``.
- Coverage requirement totals exclude ``not_applicable`` articles, so an
  article gated out by tier detection can't inflate the "requirements" totals.
"""

from pydantic import BaseModel, Field

from compliance_agent.models.findings import (
    TIER_ORDER,
    ComplianceGap,
    Finding,
    RiskTier,
    ScanResult,
)

# Directional labels shared by tier movement and the overall verdict.
IMPROVED = "improved"
REGRESSED = "regressed"
UNCHANGED = "unchanged"
MIXED = "mixed"

# How "bad" a gap status is: a lower rank is closer to resolved. A gap that
# moves missing -> unverified gained partial evidence (an improvement) even
# though it is still an open item; the reverse is a regression. Absence from a
# scan entirely (resolved) is handled separately as gaps_resolved/gaps_new.
_GAP_STATUS_RANK = {"unverified": 1, "missing": 2}
_UNKNOWN_STATUS_RANK = 2


class ScanDiff(BaseModel):
    """Structured difference between a base scan and a later target scan."""

    base_tier: RiskTier | None = None
    target_tier: RiskTier | None = None
    # improved (lower risk) | regressed (higher risk) | unchanged
    tier_direction: str = UNCHANGED

    findings_added: list[Finding] = Field(default_factory=list)
    findings_removed: list[Finding] = Field(default_factory=list)
    # Present in both scans (same detector/category/file_path) but with a
    # different severity; holds the target-scan version of each. Excluded
    # from findings_unchanged.
    findings_severity_changed: list[Finding] = Field(default_factory=list)
    findings_unchanged: int = 0

    gaps_new: list[ComplianceGap] = Field(default_factory=list)
    gaps_resolved: list[ComplianceGap] = Field(default_factory=list)
    # Gaps present in both scans whose status changed (e.g. missing -> unverified);
    # holds the target-scan version of each such gap.
    gaps_status_changed: list[ComplianceGap] = Field(default_factory=list)
    gaps_unchanged: int = 0

    requirements_met_base: int = 0
    requirements_met_target: int = 0
    requirements_total_base: int = 0
    requirements_total_target: int = 0

    # improved | regressed | mixed | unchanged — the headline signal.
    verdict: str = UNCHANGED


def _finding_key(finding: Finding) -> tuple[str, str, str]:
    return (finding.detector, finding.category, finding.file_path)


def _tier_direction(base: RiskTier | None, target: RiskTier | None) -> str:
    if base is None or target is None or base == target:
        return UNCHANGED
    # A lower position in TIER_ORDER is a lower (better) risk tier.
    return IMPROVED if TIER_ORDER[target] < TIER_ORDER[base] else REGRESSED


def _requirement_totals(result: ScanResult) -> tuple[int, int]:
    """(met, total) across assessed articles; not_applicable ones are excluded."""
    met = 0
    total = 0
    for coverage in result.coverage:
        if coverage.status == "not_applicable":
            continue
        met += coverage.requirements_met
        total += coverage.requirements_total
    return met, total


def _status_rank(status: str) -> int:
    return _GAP_STATUS_RANK.get(status, _UNKNOWN_STATUS_RANK)


def _verdict(
    tier_direction: str,
    *,
    has_improvement: bool,
    has_regression: bool,
) -> str:
    """Overall signal from tier movement and gap changes.

    Findings are intentionally not part of the verdict: they are AI-usage
    observations, not compliance failures, so a project that simply added a new
    provider integration must not be reported as a compliance "regression".
    """
    improved = tier_direction == IMPROVED or has_improvement
    regressed = tier_direction == REGRESSED or has_regression
    if improved and regressed:
        return MIXED
    if regressed:
        return REGRESSED
    if improved:
        return IMPROVED
    return UNCHANGED


def diff_scan_results(base: ScanResult, target: ScanResult) -> ScanDiff:
    """Diff two scan results, reporting how compliance changed base -> target."""
    base_findings = {_finding_key(f): f for f in base.findings}
    target_findings = {_finding_key(f): f for f in target.findings}
    added = [f for key, f in target_findings.items() if key not in base_findings]
    removed = [f for key, f in base_findings.items() if key not in target_findings]

    severity_changed: list[Finding] = []
    unchanged_findings = 0
    for key in base_findings.keys() & target_findings.keys():
        if base_findings[key].severity == target_findings[key].severity:
            unchanged_findings += 1
        else:
            severity_changed.append(target_findings[key])

    base_gaps = {g.id: g for g in base.gaps}
    target_gaps = {g.id: g for g in target.gaps}
    new_gaps = [g for gid, g in target_gaps.items() if gid not in base_gaps]
    resolved_gaps = [g for gid, g in base_gaps.items() if gid not in target_gaps]

    # Gaps present in both scans: split into status-changed vs. truly unchanged,
    # and record which direction each status change moved.
    status_changed: list[ComplianceGap] = []
    unchanged_gaps = 0
    status_improved = False
    status_regressed = False
    for gid in base_gaps.keys() & target_gaps.keys():
        base_status = base_gaps[gid].status
        target_status = target_gaps[gid].status
        if base_status == target_status:
            unchanged_gaps += 1
            continue
        status_changed.append(target_gaps[gid])
        delta = _status_rank(target_status) - _status_rank(base_status)
        if delta < 0:
            status_improved = True
        elif delta > 0:
            status_regressed = True

    tier_direction = _tier_direction(base.risk_tier, target.risk_tier)
    met_base, total_base = _requirement_totals(base)
    met_target, total_target = _requirement_totals(target)

    return ScanDiff(
        base_tier=base.risk_tier,
        target_tier=target.risk_tier,
        tier_direction=tier_direction,
        findings_added=added,
        findings_removed=removed,
        findings_severity_changed=severity_changed,
        findings_unchanged=unchanged_findings,
        gaps_new=new_gaps,
        gaps_resolved=resolved_gaps,
        gaps_status_changed=status_changed,
        gaps_unchanged=unchanged_gaps,
        requirements_met_base=met_base,
        requirements_met_target=met_target,
        requirements_total_base=total_base,
        requirements_total_target=total_target,
        verdict=_verdict(
            tier_direction,
            has_improvement=bool(resolved_gaps) or status_improved,
            has_regression=bool(new_gaps) or status_regressed,
        ),
    )
