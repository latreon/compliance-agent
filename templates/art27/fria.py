"""
EU AI Act Article 27 — Fundamental Rights Impact Assessment (FRIA)
Requirement: Certain deployers of high-risk AI systems (bodies governed by
public law, private operators providing public services, and deployers of
the credit-scoring/insurance-risk systems in Annex III 5(b)-(c)) must assess
the impact on fundamental rights before first use.

Usage: Fill in FundamentalRightsImpactAssessment, call generate_markdown(),
commit docs/fria.md before deploying, and re-run when the use case changes.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class FundamentalRightsImpactAssessment:
    """Inputs for the Art. 27(1) fundamental rights impact assessment."""

    system_name: str
    deployer_role: str  # e.g. "body governed by public law", "credit provider"
    process_description: str  # 27(1)(a): deployer's processes using the system
    intended_use_period: str  # 27(1)(b): period and frequency of use
    affected_persons: list[str]  # 27(1)(c): categories of natural persons affected
    specific_risks: list[str]  # 27(1)(d): specific risks of harm to those persons
    human_oversight_measures: str  # 27(1)(e): oversight measures per Art. 14
    mitigation_measures: list[str] = field(default_factory=list)  # 27(1)(f)
    complaint_mechanism: str = ""  # 27(1)(f): governance, complaint, and redress


def generate_markdown(fria: FundamentalRightsImpactAssessment) -> str:
    """Render an Art. 27(1)-style FRIA skeleton in Markdown."""
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    affected = "\n".join(f"- {p}" for p in fria.affected_persons) or "- _none identified yet_"
    risks = "\n".join(f"- {r}" for r in fria.specific_risks) or "- _none identified yet_"
    mitigations = (
        "\n".join(f"- {m}" for m in fria.mitigation_measures) or "- _none recorded yet_"
    )

    return f"""# Fundamental Rights Impact Assessment — {fria.system_name}

_EU AI Act Article 27(1). Generated {generated}. Complete this before first
use and re-run when the deployment or use case materially changes._

## 1. Deployer role and processes (27(1)(a))

**Role:** {fria.deployer_role}

{fria.process_description}

## 2. Intended period and frequency of use (27(1)(b))

{fria.intended_use_period}

## 3. Categories of affected natural persons (27(1)(c))

{affected}

## 4. Specific risks of harm (27(1)(d))

{risks}

## 5. Human oversight measures (27(1)(e), see Art. 14)

{fria.human_oversight_measures}

## 6. Mitigation measures and complaint mechanism (27(1)(f))

{mitigations}

**Complaint / redress mechanism:** {fria.complaint_mechanism or "_to be documented_"}
"""


def write_documentation(
    fria: FundamentalRightsImpactAssessment, output: str | Path = "docs/fria.md"
) -> Path:
    """Generate and write the FRIA document. Returns the path."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_markdown(fria), encoding="utf-8")
    return path


if __name__ == "__main__":
    demo = FundamentalRightsImpactAssessment(
        system_name="Public Housing Eligibility Assistant",
        deployer_role="body governed by public law",
        process_description="Used by caseworkers to triage housing applications.",
        intended_use_period="Continuous use, reviewed quarterly.",
        affected_persons=["housing applicants", "existing tenants under review"],
        specific_risks=["disparate impact on applicants with thin credit history"],
        human_oversight_measures="Caseworker confirms every decline before it is issued.",
        mitigation_measures=["quarterly bias audit", "manual review queue for edge cases"],
        complaint_mechanism="Applicants may request human review within 30 days.",
    )
    print(generate_markdown(demo)[:400] + "...")
