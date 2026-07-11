"""
EU AI Act Article 43 (with Art. 49) — Conformity Assessment and EU Database
Registration
Requirement: High-risk AI systems must undergo a conformity assessment
before market placement (internal control per Annex VI, or notified-body
assessment per Annex VII where the system uses biometrics), and must be
registered in the EU database before being placed on the market or put into
service (Art. 49).

Usage: Fill in ConformityAssessment, call write_report() to produce
docs/conformity-assessment.md. Fill in EUDatabaseRegistration and call
write_registration_record() once actually registered — this template does
not submit to the EU database for you, it just gives you an auditable record
that registration happened before deployment.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class ConformityAssessment:
    """Inputs for an Art. 43 conformity assessment record."""

    system_name: str
    version: str
    provider: str
    procedure: str  # "annex_vi_internal_control" | "annex_vii_notified_body"
    annex_iii_category: str  # e.g. "Annex III(4) — employment"
    requirements_checked: dict[str, bool] = field(default_factory=dict)
    # e.g. {"Art. 9 risk management": True, "Art. 10 data governance": True, ...}
    notified_body: str | None = None  # required if procedure is notified_body
    assessed_by: str = ""
    assessed_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )

    @property
    def passed(self) -> bool:
        return bool(self.requirements_checked) and all(self.requirements_checked.values())


@dataclass
class EUDatabaseRegistration:
    """Art. 49 record of EU database registration, kept before deployment."""

    system_name: str
    version: str
    registration_number: str
    registered_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )


def generate_markdown(assessment: ConformityAssessment) -> str:
    checks = (
        "\n".join(
            f"- {'✅' if ok else '❌'} {name}"
            for name, ok in assessment.requirements_checked.items()
        )
        or "- _no requirements recorded yet_"
    )
    verdict = "PASSED" if assessment.passed else "NOT YET PASSED — do not deploy"
    assessor = assessment.assessed_by or "_unassigned_"
    return f"""# Conformity Assessment — {assessment.system_name} v{assessment.version}

_EU AI Act Article 43. Assessed {assessment.assessed_at} by {assessor}._

## Procedure

- **Type:** {assessment.procedure}
- **Annex III category:** {assessment.annex_iii_category}
- **Notified body:** {assessment.notified_body or "n/a (internal control)"}

## Requirements checked

{checks}

## Verdict

**{verdict}**
"""


def write_report(
    assessment: ConformityAssessment, output: str | Path = "docs/conformity-assessment.md"
) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_markdown(assessment), encoding="utf-8")
    return path


def write_registration_record(
    registration: EUDatabaseRegistration, output: str | Path = "docs/eu-database-registration.md"
) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"""# EU Database Registration — {registration.system_name} v{registration.version}

_EU AI Act Article 49. Registered {registration.registered_at}._

- **Registration number:** {registration.registration_number}

Register before market placement or putting into service — this record
documents that registration happened, it does not perform it. Submit the
system at the European Commission's EU database for high-risk AI systems.
"""
    path.write_text(content, encoding="utf-8")
    return path


if __name__ == "__main__":
    demo = ConformityAssessment(
        system_name="Resume Screener",
        version="2.1.0",
        provider="Example GmbH",
        procedure="annex_vi_internal_control",
        annex_iii_category="Annex III(4) — employment",
        requirements_checked={
            "Art. 9 risk management": True,
            "Art. 10 data governance": True,
            "Art. 11 technical documentation": True,
            "Art. 12 record-keeping": True,
            "Art. 13 instructions for use": True,
            "Art. 14 human oversight": True,
            "Art. 15 accuracy/robustness/cybersecurity": True,
        },
        assessed_by="J. Doe, Compliance Lead",
    )
    print(generate_markdown(demo))
    print(f"passed: {demo.passed}")
