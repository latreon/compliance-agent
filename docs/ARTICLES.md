# Article Coverage — Full Reference

ComplianceAgent ships one analyzer module per EU AI Act article it covers
(`analyzer/articles/art*.py`, 17 modules — see `ALL_ARTICLE_ANALYZERS` in
`analyzer/articles/__init__.py`). Each analyzer inspects the scan result and
reports a coverage status for its article, plus a list of gaps for anything
not fully met. This doc explains **exactly what code signal produces each
status**, so "why did this article show as Partial?" has a concrete answer
instead of a guess. For the high-level pipeline and risk-tier logic, see
[ARCHITECTURE.md](ARCHITECTURE.md); for what each detector looks for in your
code, see [DETECTORS.md](DETECTORS.md).

## The shared model

Every analyzer is built on the same primitives (`analyzer/articles/base.py`):

**Requirement status** — each article breaks down into a handful of named
requirements (e.g. "risk management system documented"). Each requirement
gets one of three statuses via a single helper, `evidence(mechanism=...,
mention=...)`:

| `mechanism` | `mention` | Status | Meaning |
|---|---|---|---|
| `True` | — | **Met** | A verifiable signal exists — a real code construct (specific function/identifier calls) or a concrete artifact file with real content. |
| `False` | `True` | **Unverified** | Only a bare keyword hit in documentation prose — "referenced, but not confirmed. Check manually." Reported as an open item, never as compliant. |
| `False` | `False` | **Missing** | No signal at all. |

A bare doc mention can only ever get you to Unverified — never to Met.
Several requirements have `mechanism` hardcoded to `False` on purpose (noted
per-article below) because there is no way to verify that requirement from
static analysis alone; keyword-matching it as "Met" would be false assurance.

**Article-level rollup status**, computed from all of an article's
requirements:

- **Met** — every requirement is Met.
- **Partial** — a mix (some Met, some not, or some Unverified alongside some Met).
- **Unverified** — no requirement is Met and none is Missing (everything landed on a bare doc mention).
- **Missing** — every requirement is Missing.
- **Not applicable** — the article's `applies()` gate returned false (see per-article "Applies" below) — the article isn't relevant to this project at all, and this is different from Missing.

**Gaps**: one `ComplianceGap` is emitted per non-Met requirement, with a
deterministic id `gap:art{N}:{requirement-slug}`. An Unverified gap gets a
fixed suffix appended to its description — *"A related reference was found in
documentation, but no implementing mechanism could be verified
automatically."* — and its suggestion is prefixed with *"Verify manually,
then: ..."*.

**`ProjectProbe`** is the shared filesystem/text helper every analyzer uses to
look for artifact files and doc mentions:

- `any_file(*globs, min_content_chars=0)` — checks for a matching file
  (symlinks skipped), and if `min_content_chars` is set, requires the
  stripped content to be at least that long. The default floor used almost
  everywhere a file must exist is **40 characters** — this exists specifically
  so an empty `touch`-created placeholder file (e.g. `docs/risk.md` with zero
  real content) can't flip a mandatory control to Met.
- `docs_mention(...)` — lowercased text from `README*`, `docs/**/*.md`,
  `.rst`, `.adoc`, and a plain `wiki/` directory.
- `code_mentions(...)` — lowercased, comment-stripped Python + JS/TS source
  (test paths excluded), capped at 1000 files / 200 KB per file per language.
- Word-boundary matching treats `_`/`-` as interchangeable, so a snake_case
  probe term also matches a camelCase or kebab-case identifier in code.

Findings from files under a test path never drive an article's obligations
(`_production_findings()`) — AI usage that exists only in your test suite
doesn't create a compliance obligation.

## Articles, one by one

### Art. 5 — Prohibited AI practices

**Applies:** only when the project's risk tier classified as `UNACCEPTABLE`
(a prohibited-practice keyword match — see [GLOSSARY.md](GLOSSARY.md)).
**Never reaches Met** — the single requirement is hardcoded Missing always,
because a prohibited practice must be *removed*, not documented around. Gap
(CRITICAL): *"The scan matched indicators of a practice prohibited under
Article 5 of the EU AI Act (\<matched categories\>). Prohibited AI systems
cannot be placed on the EU market or put into service under any conditions."*
Suggestion: stop — remove the functionality or get legal review before
proceeding.

### Art. 6 — High-risk classification rules

**Applies:** project classified `HIGH` risk tier. Two requirements:
1. Intended purpose documented (CRITICAL) — Met by `docs/intended-purpose.md`
   with real content, or Unverified if docs merely mention "intended purpose."
2. Annex III category identified (HIGH) — **`mechanism` is always `False`**
   here on purpose: the evidence has to be *your own* documentation
   confirming the category, not the scanner's own classifier match grading
   itself Met. Only a doc mention of "annex iii" / "annex 3" / "high-risk
   category" gets you to Unverified.

### Art. 9 — Risk management system

**Applies:** `HIGH` tier. Met by `risk_register.json` or a `docs/risk*` file
with real content; a bare doc mention of "risk management" is Unverified.
Severity CRITICAL — a documented, continuously maintained risk management
system is a mandatory, non-optional control at this tier.

### Art. 10 — Data and data governance

**Applies:** the project processes data (pandas/numpy usage, `read_csv`,
`load_dataset` — see DETECTORS.md) **or** is `HIGH` tier; "not applicable"
when neither is true. Met by `dataset_cards/*` or `docs/data*` with real
content; mention of "dataset card"/"data governance" → Unverified. **Severity
is dynamic**: HIGH if the project is high-risk, WARNING otherwise — the only
article whose severity moves with tier for a mandatory-vs-recommended
distinction rather than being fixed.

### Art. 11 — Technical documentation

**Applies:** any AI usage detected at all. Met by `TECHNICAL_DOC.md` or
`docs/technical*` with real content; mention of "technical documentation" →
Unverified. Severity CRITICAL if high-risk, WARNING otherwise.

### Art. 12 — Record-keeping / automatic event logging

**Applies:** any AI usage. **This requirement can never reach Met** —
`mechanism` is hardcoded `False`. Rationale: the absence of a
`pattern:missing-logging` finding is "absence of a negative," not proof that
AI calls are actually logged (a stray `logger` import or a framework call the
scanner's AST can't see through could suppress the missing-logging signal
without a real audit trail existing). So the best this requirement can do is
Unverified, based on whether logging *appears* present. Gap (HIGH/WARNING):
*"Automatic logging of AI events (Art. 12) could not be verified at the model
call site. It is a statutory obligation for high-risk systems and strongly
recommended for all others."*

### Art. 13 — Transparency to deployers

**Applies:** `HIGH` tier only (previously gated on any user-facing AI at all,
which over-stated the obligation for a limited-risk chatbot — fixed). Three
requirements, all HIGH/WARNING:
1. Instructions of use — Met by `docs/instructions*`; mention of
   "instructions"/"## usage"/"quick start" → Unverified.
2. Output interpretation guidance — `mechanism` always `False`; mention of
   "interpret"/"confidence"/"limitations" → Unverified (WARNING).
3. Input data information — `mechanism` always `False`; mention of "input
   format"/"input data"/"validation" → Unverified (WARNING).

### Art. 14 — Human oversight

**Applies:** the project has autonomous-agent patterns (tool calls,
multi-agent orchestration — see DETECTORS.md) **or** is `HIGH` tier. Two
requirements, HIGH if high-risk else WARNING:
1. **Oversight mechanism** — Met by specific code identifiers:
   `HumanOversightCheckpoint`, `human_input_mode`, `human_in_the_loop`,
   `require_approval`/`requires_approval`/`approval_required`,
   `await_approval`. A previous version matched the bare word "approval,"
   which false-triggered on identifiers like `process_loan_approval` and
   "silently cleared human oversight" on fully autonomous high-risk agents —
   now it requires one of the specific compound terms above. Mention of
   "human oversight" in docs → Unverified.
2. **Override/reverse/stop capability** — kept as its own requirement,
   separate from #1, because Art. 14(4)(e) requires an *after-the-fact*
   override/reversal/stop capability distinct from a pre-action approval
   gate. Met by: `override_decision`, `reverse_decision`, `disregard_output`,
   `manual_override`, `kill_switch`, `emergency_stop`, `human_override`.
   Mention of "override the output"/"reverse the output"/"disregard the
   output"/"stop button" → Unverified.

### Art. 15 — Accuracy, robustness, cybersecurity

**Applies:** `HIGH` tier only (same over-statement fix as Art. 13). Four
requirements:
1. Accuracy metrics documented — `mechanism` always `False`; mention of
   "accuracy"/"accurate"/"precision"/"recall"/"f1"/"benchmark" → Unverified
   (WARNING).
2. Error handling — `mechanism` always `False` (a project-wide `try:` block
   can't be localized to the AI call site by keyword matching alone); mention
   = generic error-handling signal in code (HIGH).
3. Cybersecurity measures — `mechanism` always `False`; mention of terms like
   "validate", "sanitize", "rate_limit", "authentication", "authorization",
   "access_control", `escape(` (HIGH).
4. **Robustness testing** — the one requirement here with a real `mechanism`:
   test files whose *filename itself* contains a robustness keyword
   (`adversarial`, `robust`, `security`, `fuzz`, `edge_case`, `malicious`).
   A generic `tests/test_models.py` does **not** satisfy this — the rationale
   comment is explicit: "a generic test suite... proves tests exist, not that
   any of them target robustness." Mention of "adversarial"/"robustness" in
   docs → Unverified (WARNING).

### Art. 16 — Provider obligations umbrella

**Applies:** `HIGH` tier. Bundles five distinct provider duties (QMS, tech
docs, logging, post-market monitoring, incident reporting) — deliberately
distinct from Art. 26's deployer obligations, since most scanned projects are
deployers integrating a hosted model, not the model's provider. Five
requirements, CRITICAL/HIGH, each Met by a corresponding artifact file
(`docs/quality*`, `TECHNICAL_DOC.md`/`docs/technical*`, non-missing-logging
signal, `docs/post-market*`, `docs/incident*`).

### Art. 17 — Quality management system detail

**Applies:** `HIGH` tier. Complements Art. 16's single QMS line item by
tracking deeper QMS elements (17(1)(d)-(g), (n)): a provider that documents
*a* QMS but never describes testing/validation procedures or an
accountability framework still has real Art. 17 gaps. Three requirements:
QMS documented (Met by `docs/quality*`/`QMS*`, CRITICAL); testing/validation
procedures documented (`mechanism` always `False`, WARNING); accountability
framework documented (`mechanism` always `False`, WARNING).

### Art. 24 — Distributor obligations

**Applies:** heuristic — the project has deployment artifacts
(`Dockerfile`, `docker-compose*`, `Procfile`, `helm/*`, `deploy/*`,
`.github/workflows/deploy*`, `k8s/*`); "not applicable" if none exist. Three
requirements: conformity assessment verified before distribution
(`mechanism` always `False`, HIGH); technical documentation available
(`TECHNICAL_DOC.md`/`docs/technical*`, WARNING); instructions of use provided
(`docs/instructions*`, WARNING).

### Art. 26 — Deployer obligations

**Applies:** `HIGH` tier. Most scanned projects are deployers (they call a
third-party model, they don't train one), so this is often the most relevant
provider-side article for a typical repo. Five requirements (WARNING/HIGH):
1. Use per provider instructions — `mechanism` always `False`; mention of
   "instructions of use"/"operated in accordance with."
2. Oversight assigned to trained staff — `mechanism` always `False`; mention
   of "trained personnel"/"trained staff"/"human oversight training." Explicitly
   distinct from Art. 14's *design-level* oversight mechanism — this one is
   the deployer's staffing/training duty.
3. Monitor & report incidents — Met by code terms `report_incident`,
   `incident_report`, `serious_incident`; mention of "serious incident"/
   "incident reporting"/"notify the provider" → Unverified.
4. Log retention ≥ 6 months — Met by `retention_months`, `retention_until`,
   `cleanup_expired`, `log_retention`; mention of "6 months"/"six months"/
   "retention period" → Unverified.
5. Inform individuals subject to high-risk decisions — Met by
   `automated_decision_notice`, `subject_to_automated_decision`,
   `right_to_explanation`, `decisionnotice`, `notify_subject`; mention of
   "subject to an automated decision"/"right to an explanation" → Unverified.

### Art. 27 — Fundamental rights impact assessment (FRIA)

**Applies:** `HIGH` tier — but the actual legal FRIA duty applies to a
**narrower** set of deployers (public bodies, public-service operators, and
Annex III 5(b)-(c) credit/insurance deployers) than this tool's blanket
high-risk gate. The requirement text itself says to verify whether your
project falls in that narrower scope before treating this as mandatory — this
is one of the few articles where "flagged" doesn't necessarily mean
"applies to you." Two requirements: FRIA performed (Met by `docs/fria*`,
`FRIA*`, `docs/fundamental-rights*`; CRITICAL); complaint/mitigation
mechanism documented (`mechanism` always `False`; WARNING).

### Art. 43 — Conformity assessment / EU database registration

**Applies:** `HIGH` tier. (Conformity assessment is Art. 43, not Art. 7;
database registration is Art. 49 — both tracked here for convenience.) Two
requirements: conformity assessment (Met by `docs/conformity*`/`CONFORMITY*`;
CRITICAL); EU database registration (`mechanism` always `False`; HIGH).

### Art. 50 — Transparency to users

**Applies:** the project both uses AI and has user-facing interaction (a chat
interface or user input reaching the model). One requirement always applies;
three more are added *conditionally*, only when the corresponding capability
is actually detected — a plain-text chatbot doesn't get demanded to disclose
image/video-generation or emotion-recognition transparency it has no surface
for:
1. **AI disclosure** (always evaluated) — Met by a deliberate identifier/
   header/field: `ai-disclosure`, `transparency_notice`, `x-ai-disclosure`,
   `ai_transparency`, `ai_disclosure`. A weaker, mention-only signal is
   literal phrases like "generated by ai" / "you are interacting with an ai"
   / "this is an ai" found in code text (HIGH).
2. **Content marking** (only if a synthetic-media provider signal is present
   — `generate_image`, `text_to_speech`, `dall_e`, `stable_diffusion`,
   `elevenlabs`, `runwayml`, etc.) — Met by `AIContentMarker`,
   `mark_json_payload`, `http_marker_headers`; mention of "content marking"/
   "watermark"/"machine-readable" (WARNING).
3. **Deepfake disclosure** (only if `deepfake`/`face_swap`/`voice_clone`/
   `video_generation` signals are present) — Met by `DeepfakeLabel`,
   `label_media`, `is_labeled`; mention of "deepfake"/"artificially generated
   or manipulated" (WARNING).
4. **Emotion/biometric disclosure** (only if emotion/biometric terms appear
   in code, or docs mention "emotion recognition"/"biometric
   categorisation") — Met by `EmotionExposureNotice`,
   `biometric_exposure_notice`; mention of doc phrasing like "exposed to an
   emotion recognition" (HIGH).

### Art. 53-55 — GPAI model provider obligations

**Applies:** the project shows **model-training** signals — not merely
calling a hosted provider's API, which makes a project a *deployer*
(Art. 26/50), not a general-purpose-AI (GPAI) model *provider*. Gating on
"any provider usage" would misfire on the overwhelming majority of scanned
projects, which only call an API. The actual gate is code mentions of
training-specific constructs: `TrainingArguments`, `Trainer(`, `peft`,
`LoraConfig`, `deepspeed`, `Accelerator`, `push_to_hub`, `pretrain`,
`SFTTrainer`, `DPOTrainer`, `PPOTrainer`, `RewardTrainer`, `GRPOTrainer` (bare
`trl` is deliberately excluded — it collides with "Technology Readiness
Level" in unrelated docs), **or** the project's own docs self-describing as a
"general-purpose ai model" / "gpai model" / "foundation model." Requirements
(HIGH/WARNING, with one CRITICAL conditional):
1. Technical documentation of the model (`TECHNICAL_DOC.md`/`docs/technical*`
   /`MODEL_CARD*`/`model_card*`; mention "training process"/"evaluation
   results"/"model architecture").
2. Downstream integrator documentation (`MODEL_CARD*`/`model_card*`; mention
   "intended use"/"limitations"/"model card").
3. Public training-content summary (`TRAINING_DATA_SUMMARY*`/`docs/training-
   data*`; mention "training data"/"dataset sources," WARNING).
4. Copyright compliance policy (`COPYRIGHT_POLICY*`/`docs/copyright*`;
   mention "copyright"/"text and data mining"/"tdm opt-out," WARNING).
5. **Conditional** — systemic-risk evaluation & incident tracking, added only
   if the project's docs mention "systemic risk": Met by `docs/systemic-
   risk*`; mention "adversarial testing"/"red team" (CRITICAL).

## Why some requirements can never reach "Met"

A recurring pattern above: several requirements have `mechanism` hardcoded to
`False`, meaning no code signal can ever satisfy them — the best outcome is
Unverified. This isn't a bug or an oversight; it's a deliberate line the
scanner won't cross. Every one of those cases is a requirement that would
need either (a) a real legal/organizational judgment call (e.g. "is a
conformity assessment done," "is this deployer in the narrower FRIA scope"),
or (b) evidence a static scanner fundamentally cannot produce (e.g. "is this
particular try/except block actually around the AI call, everywhere it
matters"). Reporting those as Met from a keyword match would be false
assurance — worse than reporting Unverified and asking you to check by hand.

## Uncovered articles

Articles not listed above (Art. 7, 18-19, 21-23, 25, 28-42, 44-49, 56+) are
procedural, organizational, or registration/governance obligations —
conformity-assessment bureaucracy, notified-body processes, CE marking,
penalties — that leave no trace in source code for a static scanner to key
on. These are documented as out-of-scope limitations in the README rather
than analyzer modules; there is nothing in this codebase to point at for
them.
