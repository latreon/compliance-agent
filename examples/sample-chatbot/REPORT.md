# Sample PDF Report

Running `compliance-agent scan examples/sample-chatbot --format pdf` produces
a 6-page audit-ready PDF (`compliance-report-sample-chatbot.pdf`). Contents:

## Cover Page

Centered title block with project name, scan date, a colored **LIMITED** risk
tier badge (yellow), the tool version, and the legal disclaimer. No
header/footer on the cover; all other pages carry a "COMPLIANCE REPORT"
header and "Page X of Y" footer.

## 1. Executive Summary

Four metric cards — **2** files scanned, **1** AI provider, **5** findings,
**2/4** requirements met — followed by a one-paragraph assessment:

> The scan detected AI usage (openai) and classified the project in the
> LIMITED risk tier. Findings by severity: 1 warning, 4 info. 2 compliance
> gap(s) require attention; the Recommendations section pairs each gap with
> a ready-to-use code template.

## 2. Risk Assessment

Tier and confidence (LIMITED · 70%), classifier reasoning, and the key
deadline table (Feb 2025 prohibitions · Aug 2026 general application +
Art. 50 · Aug 2027 Art. 6(1) products).

## 3. Findings

Color-coded table (severity, category, file, line, article, finding):

| Severity | Category | File | Line | Article | Finding |
|----------|----------|------|------|---------|---------|
| ⚠ warning | pattern:missing-logging | app.py | — | Art. 12 | AI usage without logging |
| ℹ info | provider:openai | app.py | 19 | Art. 3/6 | OpenAI usage detected (×3) |
| ℹ info | pattern:user-input | app.py | 22 | Art. 50 | User input feeding an AI system (×5) |
| ℹ info | pattern:chat-interface | app.py | 1 | Art. 50 | Chat interface detected (×6) |
| ℹ info | pattern:chat-interface | README.md | 3 | Art. 50 | Chat interface detected (×3) |

Warning rows get a yellow background, info rows light blue.

## 4. Compliance Gaps

One card per gap with severity color on the left border, status line,
description, and remediation:

- ⚠ **Missing record-keeping for AI calls (Art. 12)** — add structured
  logging around all model invocations
- ⚠ **AI interaction transparency not verified (Art. 50)** — add a clear AI
  disclosure notice in the user interface

## 5. Recommendations

One card per fix, each with implementation steps, the template path, and a
10-line code snippet preview:

1. **Implement Event Logging (Art. 12)** — `templates/art12/event_logging.py`
2. **Add AI Transparency Disclosure (Art. 50)** — `templates/art50/transparency_notice.py`
3. **Create Technical Documentation (Art. 11)** — `templates/art11/technical_documentation.py`

## Appendix: EU AI Act Reference

Summary table of key articles (Art. 5, 9, 10, 11, 12, 14, 50), penalty
amounts (up to €35M / 7% of global turnover), and resource links.
