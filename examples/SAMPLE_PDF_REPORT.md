# Sample PDF Report

Running `compliance-agent scan examples/sample-chatbot --format pdf` produces
an audit-ready PDF (`compliance-report-sample-chatbot.pdf`). Contents:

## Cover Page

Centered title block with project name, scan date, a colored **LIMITED** risk
tier badge (yellow), the tool version, and the legal disclaimer. Other pages
carry a "COMPLIANCE REPORT" header and "Page X of Y" footer.

## 1. Executive Summary

Four metric cards — **1** file scanned, **1** AI provider, **4** findings, and
the requirements-met ratio — followed by a one-paragraph assessment and the full
per-article compliance-coverage table (Art. 5–50).

## 2. Risk Assessment

Tier and confidence (LIMITED · 70%), classifier reasoning, and the key-deadline
table (Feb 2025 prohibitions · Aug 2026 general application + Art. 50 · Aug 2027
Art. 6(1) products).

## 3. Findings

Color-coded table (severity, category, file, line, article, finding):

| Severity | Category | File | Line | Article | Finding |
|----------|----------|------|------|---------|---------|
| ⚠ warning | pattern:missing-logging | app.py | — | Art. 12 | AI usage without logging |
| ℹ info | pattern:chat-interface | app.py | 1 | Art. 50 | Chat interface detected (×6) |
| ℹ info | provider:openai | app.py | 19 | Art. 3/6 | OpenAI usage detected (×3) |
| ℹ info | pattern:user-input | app.py | 22 | Art. 50 | User input feeding an AI system (×5) |

## 4. Compliance Gaps

One card per gap (10 total, highest severity first), each with a severity color
on the left border, status line, description, and remediation — including the
Art. 50 disclosure gap and the Art. 15 error-handling / cybersecurity gaps.

## 5. Recommendations

One card per fix, each with implementation steps, the template path, and a
10-line code snippet preview (Art. 12 logging, Art. 50 transparency, Art. 11
technical documentation).

## Appendix: EU AI Act Reference

Summary table of key articles (Art. 5, 9, 10, 11, 12, 14, 50), penalty amounts
(up to €35M / 7% for prohibited practices, €15M / 3% for most other
violations), and resource links.
