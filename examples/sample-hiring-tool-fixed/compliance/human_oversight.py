"""
EU AI Act Article 14 — Human Oversight
Requirement: High-risk AI systems must be designed so natural persons can
effectively oversee them: understand outputs, intervene, and stop the system.

Usage: Add human-in-the-loop checkpoints at high-stakes decision points.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from functools import wraps
from pathlib import Path
from typing import Any


class DecisionRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HumanOversightCheckpoint:
    """Human-in-the-loop checkpoint for AI decisions.

    HIGH and CRITICAL decisions block until a human approves, rejects, or
    modifies them. Every decision — including auto-approvals — is written to
    an audit trail (Art. 14(4)(e): ability to intervene must be verifiable).
    """

    def __init__(
        self,
        risk_level: DecisionRisk = DecisionRisk.MEDIUM,
        audit_file: str | Path = "oversight_audit.jsonl",
        prompt_fn: Callable[[str], str] = input,
    ):
        self.risk_level = risk_level
        self.approval_required = risk_level in (DecisionRisk.HIGH, DecisionRisk.CRITICAL)
        self.audit_file = Path(audit_file)
        # prompt_fn is injectable so tests and non-TTY environments can
        # substitute the interactive prompt.
        self.prompt_fn = prompt_fn

    def require_approval(self, decision: Any, context: str = "") -> dict:
        """Present a decision for human approval. Blocks until answered."""
        print(f"\n{'=' * 60}")
        print(f"HUMAN OVERSIGHT CHECKPOINT — Risk: {self.risk_level.value.upper()}")
        print(f"{'=' * 60}")
        print(f"Context:  {context}")
        print(f"Decision: {decision}")
        print(f"{'=' * 60}")

        if not self.approval_required:
            return self._record(decision, context, approved=True, auto=True)

        response = self.prompt_fn("Approve? (yes/no/modify): ").strip().lower()
        if response == "yes":
            return self._record(decision, context, approved=True)
        if response == "modify":
            modified = self.prompt_fn("Enter modified decision: ")
            return self._record(modified, context, approved=True, modified=True)
        return self._record(None, context, approved=False)

    def auto_approve_if_low_risk(self, decision: Any) -> dict:
        """Auto-approve LOW-risk decisions; escalate everything else."""
        if self.risk_level == DecisionRisk.LOW:
            return self._record(decision, context="auto-approval", approved=True, auto=True)
        return self.require_approval(decision)

    def _record(
        self,
        decision: Any,
        context: str,
        *,
        approved: bool,
        auto: bool = False,
        modified: bool = False,
    ) -> dict:
        """Append the oversight outcome to the audit trail and return it."""
        outcome = {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "risk_level": self.risk_level.value,
            "context": context,
            "decision": None if decision is None else str(decision),
            "approved": approved,
            "auto_approved": auto,
            "modified": modified,
        }
        with self.audit_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(outcome, ensure_ascii=False) + "\n")
        return {"approved": approved, "decision": decision, **(
            {"auto_approved": True} if auto else {}
        ), **({"modified": True} if modified else {})}


def human_oversight(risk_level: DecisionRisk = DecisionRisk.MEDIUM):
    """Decorator that adds a human oversight checkpoint to AI decision functions.

        @human_oversight(DecisionRisk.HIGH)
        def approve_loan(application) -> str: ...

    The wrapped function computes a *preliminary* decision; a human confirms,
    modifies, or rejects it before it takes effect.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            checkpoint = HumanOversightCheckpoint(risk_level)
            preliminary = func(*args, **kwargs)
            result = checkpoint.require_approval(
                preliminary, context=f"Function: {func.__name__}"
            )
            if result["approved"]:
                return result["decision"]
            raise PermissionError("Decision rejected by human oversight")

        return wrapper

    return decorator


if __name__ == "__main__":
    # Demo with a scripted approver instead of interactive input.
    scripted = iter(["yes"])
    checkpoint = HumanOversightCheckpoint(
        DecisionRisk.HIGH, prompt_fn=lambda _msg: next(scripted)
    )
    outcome = checkpoint.require_approval("approve applicant #42", context="demo")
    print(f"outcome: {outcome}")
