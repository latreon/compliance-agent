"""
EU AI Act Article 26 — Deployer Obligations
Requirement: Deployers of high-risk AI systems must assign competent/trained
oversight staff, follow the provider's instructions of use, monitor
operation and report serious incidents, retain automatically generated logs
for at least 6 months, and inform individuals subject to an AI-assisted
decision made about them.

Usage: Track staffing/incidents/notices with DeployerRecord; call
report_incident() and notify_subject() at the relevant call sites.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class OversightAssignment:
    """Art. 26(2): a natural person assigned human oversight duties."""

    name: str
    role: str
    trained_at: str  # date/description of oversight training completed
    competent_for: list[str] = field(default_factory=list)  # decision types they may oversee


@dataclass
class IncidentRecord:
    """Art. 26(5): a monitored risk or serious incident reported upstream."""

    description: str
    severity: str  # "risk" | "serious_incident"
    reported_to_provider: bool
    reported_to_authority: bool
    reported_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )


@dataclass
class DecisionNotice:
    """Art. 26(11): notice given to a person subject to an AI-assisted decision."""

    subject_id: str  # pseudonymous reference, never raw PII in this record
    decision_summary: str
    explanation_available: bool
    notified_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )


class DeployerRecord:
    """File-backed record of Art. 26 deployer-obligation evidence.

    Keep `deployer_record.json` in version control (or your ops store) so the
    oversight-staffing, incident-reporting, and decision-notice trail is
    auditable, exactly like the Art. 12 event log.
    """

    def __init__(self, path: str | Path = "deployer_record.json"):
        self.path = Path(path)
        self.oversight_staff: list[OversightAssignment] = []
        self.incidents: list[IncidentRecord] = []
        self.decision_notices: list[DecisionNotice] = []
        if self.path.is_file():
            self._load()

    def assign_oversight(self, assignment: OversightAssignment) -> None:
        self.oversight_staff.append(assignment)
        self.save()

    def report_incident(self, incident: IncidentRecord) -> None:
        """Record a monitored risk or serious incident (Art. 26(5))."""
        self.incidents.append(incident)
        self.save()

    def notify_subject(self, notice: DecisionNotice) -> None:
        """Record that an affected individual was informed (Art. 26(11))."""
        self.decision_notices.append(notice)
        self.save()

    def save(self) -> None:
        payload = {
            "oversight_staff": [asdict(a) for a in self.oversight_staff],
            "incidents": [asdict(i) for i in self.incidents],
            "decision_notices": [asdict(n) for n in self.decision_notices],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.oversight_staff = [
            OversightAssignment(**a) for a in payload.get("oversight_staff", [])
        ]
        self.incidents = [IncidentRecord(**i) for i in payload.get("incidents", [])]
        self.decision_notices = [
            DecisionNotice(**n) for n in payload.get("decision_notices", [])
        ]


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        record = DeployerRecord(Path(tmp) / "deployer_record.json")
        record.assign_oversight(
            OversightAssignment(
                name="Jane Doe",
                role="Loan Review Lead",
                trained_at="2026-01-10",
                competent_for=["credit-scoring decisions"],
            )
        )
        record.report_incident(
            IncidentRecord(
                description="Model consistently under-scored applicants over 60",
                severity="serious_incident",
                reported_to_provider=True,
                reported_to_authority=True,
            )
        )
        record.notify_subject(
            DecisionNotice(
                subject_id="applicant-4821",
                decision_summary="Loan application declined; AI-assisted score used",
                explanation_available=True,
            )
        )
        print(f"oversight staff: {len(record.oversight_staff)}")
        print(f"incidents: {len(record.incidents)}")
        print(f"decision notices: {len(record.decision_notices)}")
