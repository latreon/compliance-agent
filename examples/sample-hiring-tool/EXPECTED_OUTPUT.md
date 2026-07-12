# Expected Output

Real output from `compliance-agent scan examples/sample-hiring-tool` (run from
the repo root; timestamps and absolute paths will differ). The
`sample-hiring-tool` directory contains only `app.py` and
`requirements.txt`, so the scanner sees just the application code.

Unlike [`sample-chatbot`](../sample-chatbot) (LIMITED risk, a plain assistant),
this project scores job applicants for a hiring decision — Annex III(4)
"employment, workers management and access to self-employment" — so it is
classified **HIGH** risk and every Chapter III, Section 2 obligation applies.

## Summary

```markdown
## Scan Summary

- **Files scanned:** 1
- **AI providers detected:** 1 (OpenAI)
- **Risk tier:** **HIGH**
- **Findings:** 2 warning, 2 info

> _This tool performs automated, heuristic technical analysis — not legal advice
> — and does not guarantee regulatory compliance. Results may include false
> positives and false negatives. Consult qualified legal counsel before relying
> on them._
```

## Risk assessment

```markdown
Confidence: 75% (heuristic estimate, not a calibrated probability)

- Matched Annex III category 'Employment, workers management and access to
  self-employment' (Annex III(4)) with 3 keyword hit(s).
- High-risk tier is provisional: Art. 6(3) exempts systems performing narrow
  procedural tasks that do not materially influence decisions. Confirm the
  intended purpose before relying on this classification.
```

The keyword hits come from `rank_candidate`, `screen_applicants`, and the
docstrings describing a hiring decision — a real static match, not a guess.
The Art. 6(3) caveat always accompanies a HIGH verdict: this is a heuristic
floor, and only a documented intended purpose (see the Art. 6 gap below)
settles it.

## Compliance coverage

| Article | Title | Status |
|---------|-------|--------|
| Art. 5 | Prohibited AI practices | Not assessed (no prohibited AI practices detected) |
| Art. 6 | High-risk AI systems | Missing — 0/2 requirements met |
| Art. 9 | Risk management system | Missing — 0/1 requirements met |
| Art. 10 | Data and data governance | Missing — 0/1 requirements met |
| Art. 11 | Technical documentation | Missing — 0/1 requirements met |
| Art. 12 | Record-keeping | Missing — 0/1 requirements met |
| Art. 13 | Transparency and provision of information to deployers | Missing — 0/3 requirements met |
| Art. 14 | Human oversight | Missing — 0/2 requirements met |
| Art. 15 | Accuracy, robustness, and cybersecurity | Missing — 0/4 requirements met |
| Art. 16 | Obligations of providers of high-risk AI systems | Missing — 0/5 requirements met |
| Art. 17 | Quality management system | Missing — 0/3 requirements met |
| Art. 24 | Obligations of distributors | Not assessed (no distribution/deployment artifacts detected) |
| Art. 26 | Obligations of deployers of high-risk AI systems | Missing — 0/5 requirements met |
| Art. 27 | Fundamental rights impact assessment | Missing — 0/2 requirements met |
| Art. 43 | Conformity assessment | Missing — 0/2 requirements met |
| Art. 50 | Transparency obligations (user-facing AI) | Missing — 0/1 requirements met |

Every article this project is high-risk enough to trigger now has a working
fix template — including Art. 6, 13, 15, 16, and 43, which previously had
analyzers but no template to close the gap.

## Findings

### `app.py`

- 🟡 **warning** `pattern:missing-logging` (file-level): AI usage without logging
- 🟡 **warning** `agent:multi-agent` (line 18): Agent pattern with AI context detected
- 🔵 **info** `provider:openai` (line 26, ×3): OpenAI usage detected
- 🔵 **info** `pattern:chat-interface` (line 38): Chat usage in AI context detected

## Gaps (28 total, highest severity first)

Critical (blocking obligations for a high-risk system):

- **Intended purpose must be documented** (Art. 6)
- **Risk management system required** (Art. 9)
- **Technical documentation required** (Art. 11)
- **Quality management system required** (Art. 16)
- **Automated logging system required** (Art. 16)
- **Quality management system must be documented** (Art. 17)
- **Fundamental rights impact assessment required before deployment** (Art. 27)
- **Conformity assessment required for high-risk systems** (Art. 43)

High (statutory obligations, unverified or missing):

- **Annex III category must be identified** (Art. 6)
- **Dataset governance must be documented** (Art. 10)
- **Automated logging of AI events required** (Art. 12)
- **Instructions of use must be provided** (Art. 13)
- **Human oversight mechanism required** (Art. 14)
- **Ability to override or reverse AI system output required** (Art. 14)
- **Error handling mechanisms required** (Art. 15)
- **Cybersecurity measures required** (Art. 15)
- **Post-market monitoring plan required** (Art. 16)
- **Incident reporting procedure required** (Art. 16)
- **Human oversight must be assigned to competent, trained staff** (Art. 26)
- **Deployer must monitor operation and report serious incidents** (Art. 26)
- **Deployer log retention (at least 6 months) required** (Art. 26)
- **Individuals subject to a high-risk AI decision must be informed** (Art. 26)
- **EU database registration required** (Art. 43)
- **AI interaction disclosure required** (Art. 50)

Warning (recommended, not always statutory):

- Output interpretation guidance, input data information (Art. 13)
- Accuracy metrics, robustness testing (Art. 15)
- QMS testing/validation procedures, accountability framework (Art. 17)
- Deployer must use the system per the provider's instructions (Art. 26)
- FRIA must document mitigation measures and a complaint mechanism (Art. 27)

## Fixing it

```bash
compliance-agent recommend examples/sample-hiring-tool --output ./fixes
```

produces 14 recommendations — one per applicable article — each backed by a
real template:

```
fixes/
├── RECOMMENDATIONS.md
├── art6/intended_purpose_classification.py
├── art9/risk_management.py
├── art10/data_governance.py
├── art11/technical_documentation.py
├── art12/event_logging.py
├── art13/instructions_for_use.py
├── art14/human_oversight.py
├── art15/robustness_and_security.py
├── art16/provider_obligations_checklist.py
├── art17/quality_management_system.py
├── art26/deployer_obligations.py
├── art27/fria.py
├── art43/conformity_assessment.py
└── art50/...
```

Art. 24 (distributor obligations) does not fire here because this project has
no deployment/packaging artifacts (no `Dockerfile`, `k8s/`, etc.) — add one to
see that gap and its template (`art24/distributor_verification.py`) too.
