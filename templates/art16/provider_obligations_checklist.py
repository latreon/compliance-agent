"""
EU AI Act Article 16 — Obligations of Providers of High-Risk AI Systems
Requirement: Providers must, among other things, have a quality management
system (Art. 17), draw up technical documentation (Art. 11), enable
automatic event logging (Art. 12), run post-market monitoring (Art. 72),
and report serious incidents (Art. 73). Art. 16 is the umbrella obligation
that ties these together — there is no single artifact that satisfies it by
itself, so this template is a checklist that verifies the pieces exist and
reports what is still missing.

Usage: Call check_provider_obligations() with the paths you use for each
artifact, then write_report() to produce PROVIDER_OBLIGATIONS.md. Wire this
into a release-gate script alongside require_clearance() (Art. 5) and
report_incident() (Art. 26) if you are also a deployer.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MIN_ARTIFACT_CHARS = 40


@dataclass
class ObligationCheck:
    """One Art. 16 sub-obligation and whether its artifact was found."""

    name: str
    article: str
    satisfied: bool
    detail: str


def _has_content(path: Path) -> bool:
    return path.is_file() and len(path.read_text(encoding="utf-8").strip()) >= MIN_ARTIFACT_CHARS


def check_provider_obligations(
    *,
    quality_management_doc: str | Path = "docs/quality-management.md",
    technical_doc: str | Path = "TECHNICAL_DOC.md",
    logging_module_present: bool = False,
    post_market_monitoring_doc: str | Path = "docs/post-market-monitoring.md",
    incident_reporting_doc: str | Path = "docs/incident-reporting.md",
) -> list[ObligationCheck]:
    """Check the artifacts backing each Art. 16 provider sub-obligation.

    ``logging_module_present`` is a caller-supplied boolean rather than a
    file probe: automatic event logging (Art. 12) is a code-level mechanism,
    not a document, so pass whether your project actually wraps AI calls with
    a logger (e.g. ``templates/art12/event_logging.py``).
    """
    return [
        ObligationCheck(
            name="Quality management system",
            article="Art. 17",
            satisfied=_has_content(Path(quality_management_doc)),
            detail=f"expects {quality_management_doc}",
        ),
        ObligationCheck(
            name="Technical documentation",
            article="Art. 11",
            satisfied=_has_content(Path(technical_doc)),
            detail=f"expects {technical_doc}",
        ),
        ObligationCheck(
            name="Automatic event logging",
            article="Art. 12",
            satisfied=logging_module_present,
            detail="expects AI calls wrapped with an event logger",
        ),
        ObligationCheck(
            name="Post-market monitoring plan",
            article="Art. 72",
            satisfied=_has_content(Path(post_market_monitoring_doc)),
            detail=f"expects {post_market_monitoring_doc}",
        ),
        ObligationCheck(
            name="Incident reporting procedure",
            article="Art. 73",
            satisfied=_has_content(Path(incident_reporting_doc)),
            detail=f"expects {incident_reporting_doc}",
        ),
    ]


def all_satisfied(checks: list[ObligationCheck]) -> bool:
    return all(c.satisfied for c in checks)


def generate_markdown(checks: list[ObligationCheck]) -> str:
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    rows = "\n".join(
        f"| {c.name} | {c.article} | "
        f"{'✅ satisfied' if c.satisfied else '❌ missing'} | {c.detail} |"
        for c in checks
    )
    missing = [c for c in checks if not c.satisfied]
    outstanding = (
        "\n".join(f"- {c.name} ({c.article}): {c.detail}" for c in missing)
        if missing
        else "_none — all checked obligations have supporting artifacts_"
    )
    return f"""# Provider Obligations Checklist — Art. 16

_Generated {generated}. This checklist verifies artifacts exist; it does not
substitute for a legal assessment of your provider status or obligations._

| Obligation | Article | Status | Detail |
|---|---|---|---|
{rows}

## Outstanding

{outstanding}
"""


def write_report(
    checks: list[ObligationCheck], output: str | Path = "PROVIDER_OBLIGATIONS.md"
) -> Path:
    path = Path(output)
    path.write_text(generate_markdown(checks), encoding="utf-8")
    return path


if __name__ == "__main__":
    demo_checks = check_provider_obligations(
        quality_management_doc="docs/quality-management.md",
        technical_doc="TECHNICAL_DOC.md",
        logging_module_present=True,
        post_market_monitoring_doc="docs/post-market-monitoring.md",
        incident_reporting_doc="docs/incident-reporting.md",
    )
    print(generate_markdown(demo_checks))
    print(f"all satisfied: {all_satisfied(demo_checks)}")
