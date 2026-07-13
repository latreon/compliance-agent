"""Articles 53-55 — Obligations of providers of general-purpose AI (GPAI) models.

These are a distinct obligation track from the rest of this module: they
apply to whoever *develops/trains* a general-purpose AI model, not to a
project that merely calls a hosted provider's API (that project is a
*deployer*, covered by Art. 26/50, not a GPAI model *provider*). Gating this
on ``is_high_risk`` or ``has_provider`` — the signals every other analyzer
here uses — would misfire on the overwhelming majority of scanned projects,
which call OpenAI/Anthropic/etc. rather than train a foundation model.

Applicability instead looks for actual model-training signals (a training
loop, a fine-tuning/PEFT config, publishing a model to a hub) or an explicit
self-description as a general-purpose/foundation model provider in the docs.

Art. 55's additional systemic-risk obligations (model evaluation including
adversarial testing, systemic risk mitigation, incident tracking) apply only
to GPAI models classified as carrying systemic risk (Art. 51) — inferred here
from an explicit systemic-risk self-declaration, since compute-threshold
classification cannot be determined by static analysis.
"""

from compliance_agent.analyzer.articles.base import (
    MIN_ARTIFACT_CHARS,
    ArticleAnalyzer,
    ProjectProbe,
    Requirement,
    evidence,
)
from compliance_agent.models.findings import ScanResult, Severity

# Code-level evidence that the project trains, fine-tunes, or publishes a
# model — as opposed to only calling a hosted inference API.
_GPAI_TRAINING_SIGNALS = (
    "trainingarguments",
    "trainer(",
    "peft",
    "loraconfig",
    "deepspeed",
    "accelerate.accelerator",
    "push_to_hub",
    "pretrain",
)

# A project's own docs asserting it IS a general-purpose/foundation model
# provider — mention-only evidence (can downgrade MISSING to UNVERIFIED, see
# `evidence()`), never enough on its own to mark an obligation MET.
_GPAI_SELF_DESCRIPTION_TERMS = ("general-purpose ai model", "gpai model", "foundation model")

_SYSTEMIC_RISK_TERMS = ("systemic risk",)


class Art53_55Analyzer(ArticleAnalyzer):  # noqa: N801 - article number pair, not a normal class name
    article_number = 53
    article_title = "Obligations of providers of general-purpose AI models (Art. 53-55)"

    def applies(self, scan_result: ScanResult) -> bool:
        probe = ProjectProbe(scan_result.project_path)
        return probe.code_mentions(*_GPAI_TRAINING_SIGNALS) or probe.docs_mention(
            *_GPAI_SELF_DESCRIPTION_TERMS
        )

    def not_applicable_reason(self, scan_result: ScanResult) -> str:
        return "no general-purpose AI model training/provider signals detected"

    def requirements(self, scan_result: ScanResult, probe: ProjectProbe) -> list[Requirement]:
        requirements = [
            Requirement(
                name="Technical documentation of the model required",
                status=evidence(
                    mechanism=probe.any_file(
                        "TECHNICAL_DOC.md",
                        "docs/technical*",
                        "MODEL_CARD*",
                        "model_card*",
                        min_content_chars=MIN_ARTIFACT_CHARS,
                    ),
                    mention=probe.docs_mention(
                        "training process", "evaluation results", "model architecture"
                    ),
                ),
                severity=Severity.HIGH,
                details=(
                    "GPAI model providers must draw up and keep up to date technical "
                    "documentation of the model, including its training and testing "
                    "process and evaluation results (Art. 53(1)(a))."
                ),
                suggestion=(
                    "Document the model's architecture, training process, compute used, "
                    "and evaluation results"
                ),
            ),
            Requirement(
                name="Downstream integrator documentation required",
                status=evidence(
                    mechanism=probe.any_file(
                        "MODEL_CARD*", "model_card*", min_content_chars=MIN_ARTIFACT_CHARS
                    ),
                    mention=probe.docs_mention("intended use", "limitations", "model card"),
                ),
                severity=Severity.HIGH,
                details=(
                    "Providers must make available information and documentation to "
                    "downstream providers that integrate the model, so they understand "
                    "its capabilities and limitations (Art. 53(1)(b))."
                ),
                suggestion=(
                    "Publish a model card documenting capabilities, limitations, and intended use"
                ),
            ),
            Requirement(
                name="Public summary of training content required",
                status=evidence(
                    mechanism=probe.any_file(
                        "TRAINING_DATA_SUMMARY*",
                        "docs/training-data*",
                        "docs/training_data*",
                        min_content_chars=MIN_ARTIFACT_CHARS,
                    ),
                    mention=probe.docs_mention("training data", "dataset sources"),
                ),
                severity=Severity.WARNING,
                details=(
                    "Providers must draw up and make publicly available a sufficiently "
                    "detailed summary of the content used to train the model "
                    "(Art. 53(1)(d))."
                ),
                suggestion="Publish a public summary of training data sources and content",
            ),
            Requirement(
                name="Copyright compliance policy required",
                status=evidence(
                    mechanism=probe.any_file(
                        "COPYRIGHT_POLICY*", "docs/copyright*", min_content_chars=MIN_ARTIFACT_CHARS
                    ),
                    mention=probe.docs_mention(
                        "copyright", "text and data mining", "tdm opt-out", "opt-out"
                    ),
                ),
                severity=Severity.WARNING,
                details=(
                    "Providers must put in place a policy to comply with EU copyright "
                    "law, including identifying and respecting text-and-data-mining "
                    "opt-outs (Art. 53(1)(c))."
                ),
                suggestion=(
                    "Document how training data collection respects copyright and TDM opt-outs"
                ),
            ),
        ]
        if probe.docs_mention(*_SYSTEMIC_RISK_TERMS):
            requirements.append(
                Requirement(
                    name="Systemic-risk model evaluation and incident tracking required",
                    status=evidence(
                        mechanism=probe.any_file(
                            "docs/systemic-risk*",
                            "docs/systemic_risk*",
                            min_content_chars=MIN_ARTIFACT_CHARS,
                        ),
                        mention=probe.docs_mention("adversarial testing", "red team", "red-team"),
                    ),
                    severity=Severity.CRITICAL,
                    details=(
                        "GPAI models with systemic risk require model evaluation "
                        "(including adversarial testing), systemic risk assessment and "
                        "mitigation, and serious-incident tracking/reporting (Art. 55)."
                    ),
                    suggestion=(
                        "Document adversarial/red-team evaluation results and the "
                        "systemic risk mitigation and incident-tracking process"
                    ),
                )
            )
        return requirements
