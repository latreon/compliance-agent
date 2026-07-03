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
    severity: Severity
    description: str
    recommendation: str


class ScanResult(BaseModel):
    """Aggregate result of scanning a project."""

    project_path: str
    findings: list[Finding]
    scan_time: datetime
    files_scanned: int = 0
    risk_tier: RiskTier | None = None
    risk_assessment: RiskAssessment | None = None
    gaps: list[ComplianceGap] = Field(default_factory=list)
