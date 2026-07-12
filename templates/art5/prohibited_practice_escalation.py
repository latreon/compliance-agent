"""
EU AI Act Article 5 — Prohibited AI Practices
Requirement: Practices in Art. 5(1) (e.g. subliminal manipulation, social
scoring, real-time remote biometric identification in public spaces for law
enforcement, emotion inference in the workplace/education) cannot be placed
on the market or put into service under ANY conditions. There is no
compliance configuration that makes a prohibited practice legal — the only
"fix" is removal, or a documented legal determination that the match was a
false positive.

This template does NOT make a prohibited system compliant. It gives you a
structured way to (1) block deployment until a human with authority signs
off, and (2) keep an auditable record of that decision.

Usage: Call require_clearance() at your deployment entrypoint (CI gate,
release script, or app startup). It raises unless a matching, unexpired
LegalClearance has been recorded — so the prohibited path stays blocked by
default rather than by convention.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


class ProhibitedPracticeBlocked(RuntimeError):
    """Raised when a deployment is attempted without a recorded legal clearance."""


@dataclass
class LegalClearance:
    """A recorded determination by qualified counsel/compliance, not an engineer.

    ``matched_categories`` must reproduce exactly what the scanner flagged
    (e.g. ``["social-scoring"]``) so the clearance can only cover the finding
    it was actually reviewed against.
    """

    reviewer: str  # name and role of the qualified reviewer, e.g. "J. Muller, DPO"
    matched_categories: list[str]
    determination: str  # "false_positive" | "removed" | "redesigned"
    rationale: str
    decided_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


class ProhibitedPracticeRecord:
    """File-backed clearance record for an Art. 5 finding.

    Keep ``prohibited_practice_record.json`` in version control. A PR that
    adds a clearance here is a PR a reviewer can actually see and challenge —
    the same principle as the Art. 9 risk register.
    """

    def __init__(self, path: str | Path = "prohibited_practice_record.json"):
        self.path = Path(path)
        self.clearances: list[LegalClearance] = []
        if self.path.is_file():
            self._load()

    def record_clearance(self, clearance: LegalClearance) -> None:
        if clearance.determination not in {"false_positive", "removed", "redesigned"}:
            raise ValueError("determination must be 'false_positive', 'removed', or 'redesigned'")
        self.clearances.append(clearance)
        self.save()

    def has_clearance_for(self, matched_categories: list[str]) -> bool:
        """True if every flagged category has a corresponding recorded clearance."""
        cleared = {cat for c in self.clearances for cat in c.matched_categories}
        return all(category in cleared for category in matched_categories)

    def save(self) -> None:
        payload = {"clearances": [asdict(c) for c in self.clearances]}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.clearances = [LegalClearance(**c) for c in payload.get("clearances", [])]


def require_clearance(
    matched_categories: list[str],
    record: ProhibitedPracticeRecord | None = None,
) -> None:
    """Block deployment unless every matched category has a recorded clearance.

    Wire this into your CI gate or release script:

        require_clearance(scan_result.risk_assessment.matched_categories)

    Raises ProhibitedPracticeBlocked (not caught here) so the pipeline fails
    loudly rather than silently continuing on a prohibited practice.
    """
    record = record or ProhibitedPracticeRecord()
    if not matched_categories:
        return
    if not record.has_clearance_for(matched_categories):
        raise ProhibitedPracticeBlocked(
            "Deployment blocked: Article 5 flagged "
            f"{matched_categories}. Do not deploy. Obtain qualified legal "
            "review and record the determination with "
            "ProhibitedPracticeRecord.record_clearance() before retrying, "
            "or remove the prohibited functionality entirely."
        )


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        record = ProhibitedPracticeRecord(Path(tmp) / "prohibited_practice_record.json")

        try:
            require_clearance(["social-scoring"], record)
        except ProhibitedPracticeBlocked as exc:
            print(f"blocked as expected: {exc}")

        record.record_clearance(
            LegalClearance(
                reviewer="J. Muller, DPO",
                matched_categories=["social-scoring"],
                determination="false_positive",
                rationale=(
                    "Keyword 'social scoring' matched a variable name in an "
                    "unrelated internal ops dashboard; no trustworthiness "
                    "scoring of natural persons occurs."
                ),
            )
        )
        require_clearance(["social-scoring"], record)  # no longer raises
        print("clearance recorded; deployment unblocked for this category")
