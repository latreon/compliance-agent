# Expected Output

Real output from `compliance-agent scan examples/sample-chatbot` (run from the
repo root; timestamps and absolute paths will differ). The `sample-chatbot`
directory contains only `app.py` and `requirements.txt`, so the scanner sees
just the application code.

## Summary

The default `scan` renders a boxed Rich report in the terminal (header, summary
metrics, coverage, findings, gaps). The same information in Markdown — as
produced by `--ci` and by `report --format markdown` — looks like this:

```markdown
## Scan Summary

- **Files scanned:** 1
- **AI providers detected:** 1 (OpenAI)
- **Risk tier:** **LIMITED**
- **Findings:** 1 warning, 3 info

> _This tool performs automated, heuristic technical analysis — not legal advice
> — and does not guarantee regulatory compliance. Results may include false
> positives and false negatives. Consult qualified legal counsel before relying
> on them._
```

Risk tier is **LIMITED**: user-facing AI, but no Annex III high-risk domain and
no Art. 5 prohibited practice. The "not legal advice" disclaimer rides every
output surface — terminal, Markdown, JSON, and PDF.

## Compliance coverage

| Article | Title | Status |
|---------|-------|--------|
| Art. 5 | Prohibited AI practices | Not applicable |
| Art. 6 | High-risk AI systems | Not applicable (tier: limited) |
| Art. 9 | Risk management system | Not applicable (tier: limited) |
| Art. 10 | Data and data governance | Not applicable |
| Art. 11 | Technical documentation | Missing — 0/1 |
| Art. 12 | Record-keeping | Missing — 0/1 |
| Art. 13 | Transparency to deployers | Missing — 0/3 |
| Art. 14 | Human oversight | Not applicable |
| Art. 15 | Accuracy, robustness, cybersecurity | Missing — 0/4 |
| Art. 16 | Obligations of providers | Not applicable (tier: limited) |
| Art. 24 | Obligations of distributors | Not applicable |
| Art. 43 | Conformity assessment | Not applicable (tier: limited) |
| Art. 50 | Transparency obligations | Missing — 0/1 |

A requirement is only **Met** when a verifiable signal is found — a real code
mechanism or a concrete artifact file. When an obligation is merely *referenced*
in documentation prose but no implementing mechanism can be confirmed, it is
reported as **Unverified** ("check manually"), never as compliant. This bare
sample has no such docs, so every open item here is **Missing**.

## Findings

```markdown
### `app.py`

- 🟡 **warning** `pattern:missing-logging` (file-level): AI usage without logging
- 🔵 **info** `pattern:chat-interface` (line 1, ×6): Chat interface detected
- 🔵 **info** `provider:openai` (line 19, ×3): OpenAI usage detected
- 🔵 **info** `pattern:user-input` (line 22, ×5): User input feeding an AI system detected
```

### What each finding means

| Finding | Why it fired | EU AI Act hook |
|---------|-------------|----------------|
| `provider:openai` | `import openai` + `OpenAI()` + `client.chat.completions` (AST-verified, 3 occurrences) | Art. 3/6 — the project operates an AI system |
| `pattern:missing-logging` | The file imports an AI provider but contains no logging at all | Art. 12 — record-keeping |
| `pattern:user-input` | `user_input` / `input()` flows into the AI call in an AI-importing file | Art. 50 — transparency |
| `pattern:chat-interface` | Chat wording in an AI context | Art. 50 — transparency |

## Gaps

The scan reports **10 gaps** across Art. 11, 12, 13, 15, and 50 (highest
severity first). The two most important for this project:

- 🟠 **AI interaction disclosure required (Art. 50)** — no disclosure mechanism
  found in code. This is judged from code, not documentation: a README that
  merely mentions "AI disclosure" does not satisfy it.
- 🟠 **Error handling mechanisms required (Art. 15)** — no try/except around the
  model call.

## JSON format

`compliance-agent scan examples/sample-chatbot --format json` produces a
versioned envelope (excerpt):

```json
{
  "schema_version": "1.0",
  "tool_name": "ComplianceAgent",
  "tool_version": "0.1.6",
  "disclaimer": "This tool performs automated, heuristic technical analysis — not legal advice — ...",
  "scan_result": {
    "project_path": ".../examples/sample-chatbot",
    "files_scanned": 1,
    "risk_tier": "limited",
    "findings": [
      {
        "id": "patterns:pattern:missing-logging:app.py:0",
        "file_path": "app.py",
        "line_number": null,
        "detector": "patterns",
        "severity": "warning",
        "category": "pattern:missing-logging",
        "message": "AI usage without logging",
        "article": "Art. 12 (record-keeping)",
        "occurrences": 1
      }
    ]
  }
}
```

## Fixing it

```bash
compliance-agent recommend examples/sample-chatbot --output ./fixes
```

copies the applicable templates (Art. 12 logging, Art. 50 transparency, Art. 11
technical docs) plus a `RECOMMENDATIONS.md` with step-by-step instructions:

```
fixes/
├── RECOMMENDATIONS.md
├── art12/event_logging.py
├── art50/transparency_notice.py
├── art50/content_marking.py
├── art50/deepfake_disclosure.py
├── art11/technical_documentation.py
└── common/...
```
