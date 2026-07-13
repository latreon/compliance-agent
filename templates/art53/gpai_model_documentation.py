"""
EU AI Act Articles 53-55 — Obligations of Providers of General-Purpose AI Models
Requirement: A provider of a general-purpose AI (GPAI) model must draw up and
keep up to date technical documentation of the model (Art. 53(1)(a)), make
information available to downstream integrators (Art. 53(1)(b)), put in place
a policy to comply with EU copyright law (Art. 53(1)(c)), and publish a
sufficiently detailed summary of the training content (Art. 53(1)(d)). A GPAI
model classified as carrying systemic risk has the additional Art. 55
obligations: model evaluation (including adversarial testing), systemic risk
assessment/mitigation, and serious-incident tracking.

This applies to whoever *trains/fine-tunes and publishes* the model, not to a
project that only calls a hosted provider's API — that project is a
*deployer* (see templates/art26, templates/art50), not a GPAI model provider.

Usage: Call check_gpai_obligations() with the paths you use for each artifact,
set is_systemic_risk=True only if the model has been classified (or you have
declared it) as carrying systemic risk under Art. 51, then write_report() to
produce GPAI_MODEL_OBLIGATIONS.md.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MIN_ARTIFACT_CHARS = 40


@dataclass
class ObligationCheck:
    """One Art. 53-55 sub-obligation and whether its artifact was found."""

    name: str
    article: str
    satisfied: bool
    detail: str


def _has_content(path: Path) -> bool:
    return path.is_file() and len(path.read_text(encoding="utf-8").strip()) >= MIN_ARTIFACT_CHARS


def check_gpai_obligations(
    *,
    technical_doc: str | Path = "TECHNICAL_DOC.md",
    model_card: str | Path = "MODEL_CARD.md",
    training_data_summary: str | Path = "docs/training-data-summary.md",
    copyright_policy: str | Path = "docs/copyright-policy.md",
    is_systemic_risk: bool = False,
    systemic_risk_doc: str | Path = "docs/systemic-risk-evaluation.md",
) -> list[ObligationCheck]:
    """Check the artifacts backing each Art. 53-55 GPAI provider sub-obligation.

    ``is_systemic_risk`` gates the Art. 55 checks: they only apply once the
    model has been classified (or self-declared) as carrying systemic risk
    under Art. 51 — pass False (the default) for an ordinary GPAI model.
    """
    checks = [
        ObligationCheck(
            name="Technical documentation of the model",
            article="Art. 53(1)(a)",
            satisfied=_has_content(Path(technical_doc)),
            detail=f"expects {technical_doc} (architecture, training process, evaluation results)",
        ),
        ObligationCheck(
            name="Downstream integrator documentation (model card)",
            article="Art. 53(1)(b)",
            satisfied=_has_content(Path(model_card)),
            detail=f"expects {model_card} (capabilities, limitations, intended use)",
        ),
        ObligationCheck(
            name="Public summary of training content",
            article="Art. 53(1)(d)",
            satisfied=_has_content(Path(training_data_summary)),
            detail=f"expects {training_data_summary}",
        ),
        ObligationCheck(
            name="Copyright compliance policy",
            article="Art. 53(1)(c)",
            satisfied=_has_content(Path(copyright_policy)),
            detail=f"expects {copyright_policy} (TDM opt-out handling)",
        ),
    ]
    if is_systemic_risk:
        checks.append(
            ObligationCheck(
                name="Systemic-risk model evaluation and incident tracking",
                article="Art. 55",
                satisfied=_has_content(Path(systemic_risk_doc)),
                detail=f"expects {systemic_risk_doc} (adversarial testing, risk mitigation)",
            )
        )
    return checks


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
    return f"""# GPAI Model Provider Obligations — Art. 53-55

_Generated {generated}. This checklist verifies artifacts exist; it does not
substitute for a legal assessment of whether your project is a GPAI model
provider or carries systemic risk under Art. 51._

| Obligation | Article | Status | Detail |
|---|---|---|---|
{rows}

## Outstanding

{outstanding}
"""


def write_report(
    checks: list[ObligationCheck], output: str | Path = "GPAI_MODEL_OBLIGATIONS.md"
) -> Path:
    path = Path(output)
    path.write_text(generate_markdown(checks), encoding="utf-8")
    return path


if __name__ == "__main__":
    demo_checks = check_gpai_obligations(
        technical_doc="TECHNICAL_DOC.md",
        model_card="MODEL_CARD.md",
        training_data_summary="docs/training-data-summary.md",
        copyright_policy="docs/copyright-policy.md",
        is_systemic_risk=False,
    )
    print(generate_markdown(demo_checks))
    print(f"all satisfied: {all_satisfied(demo_checks)}")
