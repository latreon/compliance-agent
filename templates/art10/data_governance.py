"""
EU AI Act Article 10 — Data and Data Governance
Requirement: Training, validation, and testing datasets for high-risk AI
systems need documented governance: provenance, collection process,
representativeness, and bias examination.

Usage: Create a DatasetCard per dataset; run the checklist before training.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class DatasetCard:
    """Provenance and governance record for one dataset (Art. 10(2))."""

    name: str
    version: str
    source: str  # where the data came from (URL, vendor, internal system)
    collection_process: str  # how it was collected/selected
    intended_use: str  # training | validation | testing
    contains_personal_data: bool
    legal_basis: str  # e.g. "consent", "legitimate interest", "n/a"
    known_gaps: list[str] = field(default_factory=list)  # Art. 10(2)(h)
    bias_examination: str = ""  # summary of Art. 10(2)(f) analysis
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )

    def save(self, directory: str | Path = "dataset_cards") -> Path:
        """Write the card as JSON; keep cards in version control."""
        out_dir = Path(directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.name}-{self.version}.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path


# Governance checklist derived from Art. 10(2)(a)-(h). Every item must be
# answerable "yes" (or explicitly waived with a reason) before training.
GOVERNANCE_CHECKLIST: list[str] = [
    "Design choices for the dataset are documented",
    "Data origin and collection process are recorded",
    "Preparation steps (labeling, cleaning, enrichment) are documented",
    "Assumptions about what the data measures are stated",
    "Dataset availability and suitability were assessed",
    "Possible biases were examined and findings recorded",
    "Measures to detect and correct biases are in place",
    "Data gaps or shortcomings are identified with a remediation plan",
]


def run_checklist(answers: dict[str, bool]) -> dict:
    """Evaluate checklist answers; returns pass/fail plus open items.

    `answers` maps checklist text -> bool. Missing items count as failed —
    silence is not compliance.
    """
    open_items = [item for item in GOVERNANCE_CHECKLIST if not answers.get(item, False)]
    return {
        "passed": not open_items,
        "open_items": open_items,
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    card = DatasetCard(
        name="support-tickets",
        version="2026-06",
        source="internal helpdesk export",
        collection_process="all resolved tickets Jan-Jun 2026, PII stripped",
        intended_use="training",
        contains_personal_data=False,
        legal_basis="n/a",
        known_gaps=["non-English tickets underrepresented"],
        bias_examination="language distribution skews 90% English; mitigation planned",
    )
    print(f"card written: {card.save('dataset_cards_demo')}")
    result = run_checklist({item: True for item in GOVERNANCE_CHECKLIST[:6]})
    print(json.dumps(result, indent=2))
