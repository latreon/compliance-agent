"""
EU AI Act Article 9 — Risk Management System
Requirement: High-risk AI systems need a continuous, iterative risk management
process across the whole lifecycle: identify, estimate, mitigate, monitor.

Usage: Maintain a RiskRegister in your repo; review it every release.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class Likelihood(StrEnum):
    RARE = "rare"
    POSSIBLE = "possible"
    LIKELY = "likely"


class Impact(StrEnum):
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


# Simple ordinal scoring: likelihood x impact -> priority bucket.
_SCORE = {
    Likelihood.RARE: 1,
    Likelihood.POSSIBLE: 2,
    Likelihood.LIKELY: 3,
    Impact.MINOR: 1,
    Impact.MODERATE: 2,
    Impact.SEVERE: 3,
}


@dataclass
class Risk:
    """One identified risk to health, safety, or fundamental rights."""

    id: str  # short slug, e.g. "biased-training-data"
    description: str
    likelihood: Likelihood
    impact: Impact
    mitigation: str  # concrete measure (Art. 9(4): eliminate or reduce)
    owner: str  # person/team accountable
    status: str = "open"  # open | mitigated | accepted
    identified_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )

    @property
    def score(self) -> int:
        """1 (negligible) .. 9 (act immediately)."""
        return _SCORE[self.likelihood] * _SCORE[self.impact]


class RiskRegister:
    """File-backed risk register with a review cycle.

    Store `risk_register.json` in version control so risk decisions are
    reviewable in PRs, exactly like code.
    """

    def __init__(self, path: str | Path = "risk_register.json"):
        self.path = Path(path)
        self.risks: list[Risk] = []
        self.last_review: str | None = None
        if self.path.is_file():
            self._load()

    def add(self, risk: Risk) -> None:
        if any(existing.id == risk.id for existing in self.risks):
            raise ValueError(f"risk id already registered: {risk.id}")
        self.risks.append(risk)
        self.save()

    def prioritized(self) -> list[Risk]:
        """Open risks first, highest score first — your work queue."""
        return sorted(
            self.risks, key=lambda r: (r.status != "open", -r.score)
        )

    def mark_reviewed(self) -> None:
        """Record a completed review cycle (Art. 9(2): iterative process)."""
        self.last_review = datetime.now(UTC).isoformat(timespec="seconds")
        self.save()

    def save(self) -> None:
        payload = {
            "last_review": self.last_review,
            "risks": [asdict(risk) for risk in self.risks],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.last_review = payload.get("last_review")
        self.risks = [
            Risk(
                id=raw["id"],
                description=raw["description"],
                likelihood=Likelihood(raw["likelihood"]),
                impact=Impact(raw["impact"]),
                mitigation=raw["mitigation"],
                owner=raw["owner"],
                status=raw.get("status", "open"),
                identified_at=raw.get("identified_at", ""),
            )
            for raw in payload.get("risks", [])
        ]


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        register = RiskRegister(Path(tmp) / "risk_register.json")
        register.add(
            Risk(
                id="hallucinated-legal-advice",
                description="Model presents fabricated regulations as fact.",
                likelihood=Likelihood.POSSIBLE,
                impact=Impact.SEVERE,
                mitigation="Ground answers in retrieved statute text; cite sources.",
                owner="ml-platform",
            )
        )
        register.mark_reviewed()
        for risk in register.prioritized():
            print(f"[{risk.score}] {risk.id} ({risk.status}) -> {risk.mitigation}")
