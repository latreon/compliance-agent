# Examples

Five runnable examples, each showing what ComplianceAgent does for a
different real use case. Every scan/recommend output quoted in these docs is
real output from running the tool against that exact directory — not
illustrative text.

| Example | Risk tier | Shows |
|---------|-----------|-------|
| [`sample-chatbot/`](sample-chatbot) | LIMITED | The minimal case: a plain AI chatbot, no Annex III domain |
| [`sample-hiring-tool/`](sample-hiring-tool) | HIGH | An Annex III(4) employment use case — every Chapter III obligation, all fix templates |
| [`sample-hiring-tool-fixed/`](sample-hiring-tool-fixed) | HIGH | The same project, after applying the recommended fix templates — real before/after |
| [`sample-multi-framework/`](sample-multi-framework) | LIMITED | LangChain + CrewAI + LangGraph combined and deduplicated in one project |
| [`sample-ci-cd/`](sample-ci-cd) | LIMITED | A copy-paste GitHub Actions workflow that gates a PR on `--fail-on` |
| Web dashboard | — | `compliance-agent serve` — see [below](#web-dashboard) |

If your project doesn't look like any of these, the closest match is still
the fastest way to see what the tool actually reports for code shaped like
yours — run `compliance-agent scan .` on your own project either way.

## `sample-chatbot/` — intentionally non-compliant (LIMITED risk)

A realistic minimal OpenAI chatbot with **no compliance measures**, kept
deliberately small (`app.py` + `requirements.txt`) so the scanner only sees the
application code — no explanatory docs to skew the result.

What it is missing on purpose:

- ❌ No AI disclosure — users are never told they are talking to AI (Art. 50)
- ❌ No event logging — no record of any AI interaction (Art. 12)
- ❌ No error handling around the model call (Art. 15)

### Scan it

```bash
# From the repo root:
compliance-agent scan examples/sample-chatbot
compliance-agent recommend examples/sample-chatbot --output ./fixes
```

Risk tier: **LIMITED** (user-facing AI, no Annex III high-risk domain). See
[sample-chatbot/EXPECTED_OUTPUT.md](sample-chatbot/EXPECTED_OUTPUT.md) for the full, real scan output and
[sample-chatbot/SAMPLE_PDF_REPORT.md](sample-chatbot/SAMPLE_PDF_REPORT.md) for what the PDF contains.

### Run it (optional)

```bash
pip install -r sample-chatbot/requirements.txt
export OPENAI_API_KEY=sk-...
python sample-chatbot/app.py
```

## `sample-hiring-tool/` — high-risk (Annex III employment)

A candidate-ranking service used for hiring decisions — Annex III(4)
"employment, workers management and access to self-employment" — classified
**HIGH** risk, not LIMITED. Every Chapter III, Section 2 obligation applies:
risk management (Art. 9), data governance (Art. 10), technical documentation
(Art. 11), record-keeping (Art. 12), instructions for use (Art. 13), human
oversight (Art. 14), accuracy/robustness/cybersecurity (Art. 15), provider
obligations (Art. 16), quality management (Art. 17), deployer obligations
(Art. 26), a fundamental rights impact assessment (Art. 27), and conformity
assessment (Art. 43).

```bash
compliance-agent scan examples/sample-hiring-tool
compliance-agent recommend examples/sample-hiring-tool --output ./fixes
# -> 14 recommendations, one real fix template per applicable article
```

Full real output — every gap, all coverage rows, and every recommendation —
is in [`sample-hiring-tool/EXPECTED_OUTPUT.md`](sample-hiring-tool/EXPECTED_OUTPUT.md).

## `sample-hiring-tool-fixed/` — the same project, after the fixes

Not a hypothetical — this is `sample-hiring-tool/` with `compliance-agent
recommend`'s templates actually copied in and wired up: real event logging
around the model call (`compliance/event_logging.py`), a real human oversight
checkpoint before every rejection (`compliance/human_oversight.py`), a real
AI transparency notice (`compliance/transparency_notice.py`), plus the
generated `risk_register.json`, `TECHNICAL_DOC.md`, and `docs/` artifacts.

```bash
compliance-agent scan examples/sample-hiring-tool          # before
compliance-agent scan examples/sample-hiring-tool-fixed    # after
```

![Before/after comparison: 33 gaps (9 critical) dropping to 18 gaps (1 critical) after applying the fix templates](sample-hiring-tool/before-after-comparison.png)

The risk tier stays **HIGH** in both — applying fixes closes compliance gaps,
it does not change the underlying Annex III classification. What changes is
coverage: 15 of 33 gaps close outright, and several more (record-keeping,
robustness) move from a flat "missing" to "unverified" — this tool's honest
middle state for a static keyword match that found real evidence but can't
fully confirm the claim (see [Compliance Coverage](../README.md#compliance-coverage)).

## `sample-multi-framework/` — LangChain + CrewAI + LangGraph in one project

Real agent projects rarely stick to one framework. `research_pipeline.py`
combines a LangChain summarization chain and search tool, a CrewAI
researcher/writer crew, and a LangGraph state graph that orchestrates both —
the way a team migrating between frameworks, or integrating a third-party
crew into their own graph, actually ends up.

```bash
compliance-agent scan examples/sample-multi-framework
```

The report groups findings by framework (`Frameworks Detected: crewai,
langchain, langgraph`) and `compliance-agent recommend` still produces one
deduplicated recommendation per article — not three redundant Art. 14 fixes
for three frameworks that each triggered it. Full real output is in
[`sample-multi-framework/EXPECTED_OUTPUT.md`](sample-multi-framework/EXPECTED_OUTPUT.md).

## `sample-ci-cd/` — gating a pull request

A tiny AI feature plus a real, copyable
[`.github/workflows/compliance-gate.yml`](sample-ci-cd/.github/workflows/compliance-gate.yml)
that runs on every PR, fails the job on statutory gaps, and uploads a PDF
report as a build artifact either way. See
[`sample-ci-cd/README.md`](sample-ci-cd/README.md) for what each `--fail-on`
threshold blocks, why the default is `high` and not `critical`, and how to
adopt the workflow in your own repo.

```bash
compliance-agent scan examples/sample-ci-cd --ci --fail-on high
```

## Web Dashboard

Two ways to see the same report interactively instead of in the terminal:

```bash
# Self-contained HTML file — no install beyond the CLI, works offline
compliance-agent scan examples/sample-hiring-tool --format html --output dashboard.html
open dashboard.html

# Local server — adds a "Run scan" button and scan history
uv tool install 'compliance-agent[web]'
compliance-agent serve examples/sample-hiring-tool
# Open: http://127.0.0.1:8420/
```

Real screenshot of `compliance-agent serve examples/sample-hiring-tool`:

![ComplianceAgent dashboard showing a HIGH risk tier, 33 gaps, and per-article coverage](sample-hiring-tool/dashboard-preview.png)

The dashboard renders every section the terminal report has — summary,
per-article coverage, findings (filterable by severity and free text), gaps,
and recommendations with the full template source inline — plus a scan
history with a gap-count trend line when run via `serve`.
