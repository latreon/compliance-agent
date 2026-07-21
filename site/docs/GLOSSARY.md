# Glossary

Terms used throughout ComplianceAgent's output, docs, and the EU AI Act
itself — collected in one place. If a scan result or another doc uses a term
you don't recognize, it's probably here.

## EU AI Act concepts

**EU AI Act** — Regulation (EU) 2024/1689, the European Union's risk-based
legal framework for AI systems. It sorts AI use into risk tiers and attaches
different obligations to each. ComplianceAgent is a static-analysis tool
that estimates where your project likely sits and what a corresponding
obligation looks like in code/docs — not a legal determination.

**Provider** — under the Act, whoever *develops* an AI system or a
general-purpose AI (GPAI) model, or has one developed, and places it on the
market under their own name. Training a model is what makes you a provider —
see **GPAI model**, below.

**Deployer** — whoever *uses* an AI system under their own authority in a
professional context. If your project calls OpenAI's or Anthropic's hosted
API, you're almost always a **deployer** of their model, not a provider —
this distinction is why [Art. 26](ARTICLES.md#art-26--deployer-obligations)
(deployer duties) applies to most scanned projects, while
[Art. 53-55](ARTICLES.md#art-53-55--gpai-model-provider-obligations) (GPAI
provider duties) only applies if the project actually trains/fine-tunes a
model itself.

**GPAI (general-purpose AI) model** — a model trained on broad data and
capable of a wide range of tasks (the large language models behind most
hosted AI APIs are GPAI models). ComplianceAgent gates its GPAI-provider
analyzer on real training signals (`TrainingArguments`, `Trainer(`, `peft`,
`push_to_hub`, etc. — see [DETECTORS.md](DETECTORS.md)), not on merely
calling one.

**Annex III** — the Act's list of eight high-risk application domains:
biometric identification/categorisation, critical infrastructure, education,
employment, essential services (credit/insurance), law enforcement,
migration/asylum/border control, and administration of justice/democratic
processes. ComplianceAgent matches Annex III keywords
(`rules/annex3.yaml`) against your project's file paths and code content —
one keyword hit is enough to classify a project HIGH risk (see
[Risk tier](#risk-tier) below).

**Prohibited practice (Art. 5)** — a small set of AI uses banned outright
regardless of risk tier: social scoring, subliminal/manipulative techniques
causing harm, exploiting vulnerabilities, untargeted facial-image scraping,
certain biometric categorization, workplace/education emotion recognition,
predictive-policing profiling, and real-time remote biometric identification
in public spaces (`rules/prohibited.yaml`). A match classifies a project
`UNACCEPTABLE` tier — see [Risk tier](#risk-tier).

## ComplianceAgent's own terms

### Risk tier

The classifier's output for "how risky is this project, per the Act,"
strictly ordered:

| Tier | Meaning |
|---|---|
| `UNACCEPTABLE` | Matched an Art. 5 prohibited-practice keyword. Outranks every other tier — checked first. |
| `HIGH` | Matched an Annex III high-risk domain keyword. Every article obligation gated *exclusively* on this tier (Art. 6, 9, 13, 15, 16, 17, 26, 27, 43) applies here; several others (Art. 10, 11, 12, 14, 24, 50) also apply at `HIGH`, but each has its own broader or separate trigger too — see [ARTICLES.md](ARTICLES.md) for the exact gate per article. |
| `LIMITED` | AI usage with user-facing interaction (a chat interface or user input reaching the model), but no Annex III match — Art. 50 transparency applies. |
| `MINIMAL` | AI usage detected, but neither of the above — or no AI usage at all. |

A tier is a **floor, not a verdict** — it's the minimum obligation set the
scan can prove is relevant; it never rules out that your project needs more
scrutiny than the tier implies (keyword heuristics can miss a use case
expressed in ordinary business language). A project's `compliance.yaml` can
*declare* a tier that only **raises** the detected one — a declaration can
never talk the scanner down a tier, because that would let a config file
manufacture false assurance.

### Requirement status (Met / Unverified / Missing)

Every EU AI Act article breaks down into named requirements, and each one
gets exactly one of three statuses:

- **Met** — a verifiable signal exists: a real code mechanism (a specific
  function/identifier used) or a concrete artifact file with real content.
- **Unverified** — only a bare keyword hit in documentation prose. Reported
  as an open item needing manual verification — never treated as compliant.
- **Missing** — no signal at all.

See [ARTICLES.md](ARTICLES.md#the-shared-model) for the full mechanics,
including why several requirements can *never* reach Met by design.

### Article coverage status (Met / Partial / Unverified / Missing / Not applicable)

The rollup status for an entire article, computed from its requirements —
same three words as above, plus two more: **Partial** (a mix of statuses) and
**Not applicable** (the article's gate condition — e.g. "project is HIGH
tier" — isn't met, so the article isn't relevant here at all, which is
different from every requirement being Missing).

### Gap

An open, unresolved item — one gap per non-Met requirement, or a
project-wide gap like an Art. 5 prohibited-practice match. Each gap carries
a `severity` (info/warning/high/critical), a `details` description, and a
`suggestion` for what to do about it. `diff_scans` tracks gaps as
resolved/new/status-changed between two scans.

### Finding

A single, concrete observation the scanner made in your code — "this file
imports `openai`," "this file has no logging import." Findings are
lower-level than gaps: they're what detectors emit; gaps are what article
analyzers derive from findings (plus risk tier, plus doc/artifact checks).
See [DETECTORS.md](DETECTORS.md#finding-shape) for the exact shape.

### Severity

Ordered `info < warning < high < critical`, used by both findings and gaps.
Detectors only ever emit `info`/`warning` findings — the more severe
`high`/`critical` signals live in gaps (a missing mandatory control at HIGH
tier, or a prohibited-practice match). This is why `--fail-on` checks both
findings *and* gaps, not just findings — see
[CI-CD.md](CI-CD.md#--fail-on-mechanics) for why that distinction matters
for a CI gate.

### `compliance.yaml`

A project's own declared scan defaults and compliance posture. See
[CONFIGURATION.md](CONFIGURATION.md) for the full schema.
