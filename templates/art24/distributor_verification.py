"""
EU AI Act Article 24 — Obligations of Distributors
Requirement: Before making a high-risk AI system available on the market,
distributors must verify the provider carried out the conformity assessment,
that the required technical documentation exists, and that instructions of
use accompany the system. Distributors must also stop distribution and
inform the provider/authorities if they have reason to believe the system is
non-conformant.

Usage: Record verification with DistributorRecord.verify() before shipping;
call halt_distribution() if a concern surfaces.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


class DistributionHalted(RuntimeError):
    """Raised when a non-conformance concern requires distribution to stop."""


@dataclass
class ProviderVerification:
    """Art. 24(1): what was checked about the provider's own compliance."""

    provider_name: str
    system_name: str
    system_version: str
    conformity_assessment_confirmed: bool
    technical_documentation_received: bool
    instructions_of_use_received: bool
    ce_marking_present: bool
    verified_by: str
    verified_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )

    @property
    def cleared_to_distribute(self) -> bool:
        return (
            self.conformity_assessment_confirmed
            and self.technical_documentation_received
            and self.instructions_of_use_received
            and self.ce_marking_present
        )


@dataclass
class NonConformanceReport:
    """Art. 24(3)-(4): a concern that required halting distribution."""

    system_name: str
    concern: str
    reported_to_provider: bool
    reported_to_authority: bool
    reported_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )


class DistributorRecord:
    """File-backed Art. 24 verification and non-conformance trail.

    Keep ``distributor_record.json`` in version control so "did we check
    before shipping this version" is answerable from git history, not memory.
    """

    def __init__(self, path: str | Path = "distributor_record.json"):
        self.path = Path(path)
        self.verifications: list[ProviderVerification] = []
        self.non_conformance_reports: list[NonConformanceReport] = []
        if self.path.is_file():
            self._load()

    def verify(self, verification: ProviderVerification) -> None:
        self.verifications.append(verification)
        self.save()

    def report_non_conformance(self, report: NonConformanceReport) -> None:
        self.non_conformance_reports.append(report)
        self.save()

    def save(self) -> None:
        payload = {
            "verifications": [asdict(v) for v in self.verifications],
            "non_conformance_reports": [asdict(r) for r in self.non_conformance_reports],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.verifications = [ProviderVerification(**v) for v in payload.get("verifications", [])]
        self.non_conformance_reports = [
            NonConformanceReport(**r) for r in payload.get("non_conformance_reports", [])
        ]


def require_clearance_to_distribute(verification: ProviderVerification) -> None:
    """Block distribution unless every Art. 24(1) check passed.

    Wire this into your shipping/release script:

        require_clearance_to_distribute(verification)
    """
    if not verification.cleared_to_distribute:
        raise DistributionHalted(
            f"Distribution halted for {verification.system_name} "
            f"v{verification.system_version}: provider verification incomplete. "
            "Confirm conformity assessment, technical documentation, "
            "instructions of use, and CE marking before shipping."
        )


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        record = DistributorRecord(Path(tmp) / "distributor_record.json")

        incomplete = ProviderVerification(
            provider_name="Acme AI GmbH",
            system_name="Resume Screener",
            system_version="2.1.0",
            conformity_assessment_confirmed=True,
            technical_documentation_received=True,
            instructions_of_use_received=False,
            ce_marking_present=True,
            verified_by="J. Doe, Distribution Compliance",
        )
        try:
            require_clearance_to_distribute(incomplete)
        except DistributionHalted as exc:
            print(f"halted as expected: {exc}")

        record.verify(incomplete)
        record.report_non_conformance(
            NonConformanceReport(
                system_name="Resume Screener",
                concern="Instructions of use were not supplied with v2.1.0",
                reported_to_provider=True,
                reported_to_authority=False,
            )
        )
        print(f"verifications recorded: {len(record.verifications)}")
        print(f"non-conformance reports: {len(record.non_conformance_reports)}")
