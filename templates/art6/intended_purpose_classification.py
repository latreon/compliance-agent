"""
EU AI Act Article 6 — Classification of High-Risk AI Systems
Requirement: Whether a system is high-risk under Annex III turns on its
documented intended purpose (Art. 6(2)) — the classification must name the
specific Annex III category it falls under, not just assert "high-risk" or
"compliant".

Usage: Fill in IntendedPurposeClassification, call write_classification() to
produce docs/intended-purpose.md. Do this before relying on any other Art. 9+
obligation, since several of them are gated on being high-risk in the first
place.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Mirrors rules/annex3.yaml category ids — keep in sync if you add categories.
ANNEX_III_CATEGORIES = {
    "biometric": "Annex III(1) — biometric identification and categorisation",
    "critical-infrastructure": "Annex III(2) — critical infrastructure",
    "education": "Annex III(3) — education and vocational training",
    "employment": "Annex III(4) — employment, workers management, self-employment",
    "essential-services": "Annex III(5) — essential private and public services",
    "law-enforcement": "Annex III(6) — law enforcement",
    "migration": "Annex III(7) — migration, asylum, border control",
    "justice": "Annex III(8) — administration of justice, democratic processes",
    "none": "Not in an Annex III high-risk category",
}


@dataclass
class IntendedPurposeClassification:
    """Inputs for the Art. 6(2) intended-purpose and classification record."""

    system_name: str
    intended_purpose: str  # what the system does, and for/to whom
    deployment_context: str  # who operates it, and in what setting
    annex_iii_category_id: str  # key into ANNEX_III_CATEGORIES
    classification_rationale: str
    classified_by: str = ""
    classified_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )

    @property
    def is_high_risk(self) -> bool:
        return self.annex_iii_category_id != "none"

    @property
    def annex_iii_category(self) -> str:
        return ANNEX_III_CATEGORIES.get(
            self.annex_iii_category_id, f"unknown category: {self.annex_iii_category_id}"
        )


def generate_markdown(classification: IntendedPurposeClassification) -> str:
    verdict = "HIGH-RISK" if classification.is_high_risk else "not high-risk (Annex III)"
    return f"""# Intended Purpose and Classification — {classification.system_name}

_EU AI Act Article 6(2). Classified {classification.classified_at} by \
{classification.classified_by or "_unassigned_"}._

## Intended purpose

{classification.intended_purpose}

## Deployment context

{classification.deployment_context}

## Annex III classification

- **Category:** {classification.annex_iii_category}
- **Verdict:** {verdict}

## Rationale

{classification.classification_rationale}

## Re-classify when

- The intended purpose changes
- The system is deployed in a new context
- A new Annex III category could plausibly apply
"""


def write_classification(
    classification: IntendedPurposeClassification,
    output: str | Path = "docs/intended-purpose.md",
) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_markdown(classification), encoding="utf-8")
    return path


if __name__ == "__main__":
    demo = IntendedPurposeClassification(
        system_name="Resume Screener",
        intended_purpose=(
            "Ranks incoming job applications by fit against a role's stated "
            "requirements, for use by internal recruiters."
        ),
        deployment_context="Deployed internally by the recruiting team of the provider.",
        annex_iii_category_id="employment",
        classification_rationale=(
            "Scores candidates for hiring decisions; falls under Annex III(4) "
            "employment/recruitment even though a human makes the final call."
        ),
        classified_by="J. Doe, Compliance Lead",
    )
    print(generate_markdown(demo))
    print(f"is_high_risk: {demo.is_high_risk}")
