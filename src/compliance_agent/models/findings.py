"""Pydantic models for compliance findings and scan results."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    """Severity level of a compliance finding."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


class RiskTier(StrEnum):
    """EU AI Act risk tier classification."""

    UNACCEPTABLE = "unacceptable"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"


class RequirementStatus(StrEnum):
    """Whether an article requirement is satisfied, and how strong the evidence is.

    A compliance tool must never assert "met" on the strength of a keyword in a
    README — that produces false assurance. Only a verifiable signal (an actual
    code mechanism or a concrete artifact file) yields MET. A bare documentation
    mention yields UNVERIFIED ("referenced, but not confirmed — check manually"),
    which is reported as an open item, not as compliant.
    """

    MET = "met"
    UNVERIFIED = "unverified"
    MISSING = "missing"


class Finding(BaseModel):
    """A single compliance-relevant observation in the scanned codebase."""

    id: str
    file_path: str
    line_number: int | None = None
    detector: str
    severity: Severity
    category: str
    message: str
    description: str
    article: str | None = None  # EU AI Act article reference
    suggestion: str | None = None
    occurrences: int = 1  # how many times this pattern matched in the file


class RiskAssessment(BaseModel):
    """Result of risk tier classification."""

    tier: RiskTier
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: list[str] = Field(default_factory=list)
    matched_categories: list[str] = Field(default_factory=list)


class ComplianceGap(BaseModel):
    """A missing compliance obligation identified by the gap analyzer."""

    id: str
    title: str
    article: str
    article_title: str = ""
    requirement: str = ""
    status: str = "missing"  # missing | unverified (gaps are never "met")
    severity: Severity
    description: str
    recommendation: str


class ArticleCoverage(BaseModel):
    """Per-article compliance status for the coverage table."""

    article: str  # "Art. 12"
    title: str
    status: str  # met | partial | unverified | missing | not_applicable
    requirements_met: int = 0
    requirements_total: int = 0
    reason: str = ""  # e.g. "tier: limited" for not_applicable


class FrameworkDetection(BaseModel):
    """Summary of one AI framework detected in the project."""

    name: str  # "langchain", "crewai", ...
    version: str | None = None  # reserved; not currently detected
    patterns: list[str] = Field(default_factory=list)  # ["agent", "tools", "memory"]
    risk_notes: list[str] = Field(default_factory=list)  # compliance considerations


class ScanResult(BaseModel):
    """Aggregate result of scanning a project."""

    project_path: str
    findings: list[Finding]
    scan_time: datetime
    files_scanned: int = 0
    risk_tier: RiskTier | None = None
    risk_assessment: RiskAssessment | None = None
    gaps: list[ComplianceGap] = Field(default_factory=list)
    recommendations: list["FixRecommendation"] = Field(default_factory=list)
    frameworks_detected: list[FrameworkDetection] = Field(default_factory=list)
    coverage: list[ArticleCoverage] = Field(default_factory=list)


from compliance_agent.models.recommendations import FixRecommendation  # noqa: E402

ScanResult.model_rebuild()
