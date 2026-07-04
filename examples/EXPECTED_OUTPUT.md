# Expected Output

Real output from `compliance-agent scan examples/sample-chatbot` (run from the
repo root; paths and timestamps will differ). The sample folder has three
scannable files (`app.py`, `README.md`, `REPORT.md`).

## Default terminal output

`compliance-agent scan .` renders a **boxed terminal report** (via Rich), not
raw markdown. It has five sections: a header, a summary strip, per-article
coverage, the findings table, and the compliance gaps — followed by next steps.
Abridged (box drawing simplified for readability):

```text
╭─ EU AI Act Compliance Report ────────────────────────────────╮
│   Project        .../examples/sample-chatbot                 │
│   Scan date      2026-07-04 19:50                            │
│   Files scanned  3                                           │
│   Risk tier      LIMITED                                     │
╰──────────────────────────────────────────── ComplianceAgent ─╯

╭─ Scan Summary ───────────────────────────────────────────────╮
│    3            1             6             9                 │
│  FILES      AI SYSTEMS     FINDINGS       GAPS               │
╰──────────────────────────────────────────────────────────────╯

╭─ Compliance Coverage ────────────────────────────────────────╮
│  Art. 11   Technical documentation     MISSING  0/1          │
│  Art. 12   Record-keeping              MISSING  0/1          │
│  Art. 13   Transparency to deployers   MISSING  0/3          │
│  Art. 15   Accuracy, robustness, sec.  MISSING  0/4          │
│  Art. 50   Transparency (user-facing)  MET      1/1          │
│  (Art. 6, 7, 9, 10, 14, 26, 28 — Not applicable at this tier)│
╰──────────────────────────────────────────────────────────────╯

╭─ Findings ───────────────────────────────────────────────────╮
│  ⚠ WARNING  pattern:missing-logging   app.py       Art. 12   │
│  ℹ INFO     provider:openai           app.py:19    Art. 3/6  │
│  ℹ INFO     pattern:user-input        app.py:22    Art. 50   │
│  ℹ INFO     pattern:chat-interface    app.py:1     Art. 50   │
│  ℹ INFO     pattern:chat-interface    README.md:3  Art. 50   │
│  ℹ INFO     pattern:chat-interface    REPORT.md:3  Art. 50   │
╰──────────────────────────────────────────────────────────────╯
```

## Markdown report file

`compliance-agent report examples/sample-chatbot --format markdown` writes a
plain-markdown file (this is the raw-markdown form; `scan --format markdown`
renders the boxed terminal view above):

```markdown
# EU AI Act Compliance Report

- **Project:** `.../examples/sample-chatbot`
- **Scanned:** 2026-07-04T19:50:18

## Scan Summary

- **Files scanned:** 3
- **AI providers detected:** 1 (OpenAI)
- **Risk tier:** **LIMITED**
- **Findings:** 1 warning, 5 info

## Risk Assessment

Confidence: 70%

- AI provider usage combined with user-facing interaction detected;
  transparency obligations (Art. 50) apply, but no Annex III high-risk
  domain matched.

## Compliance Gaps (9)

- 🟠 Instructions of use must be provided (Art. 13)
- 🟠 Error handling mechanisms required (Art. 15)
- 🟠 Cybersecurity measures required (Art. 15)
- 🟡 Technical documentation required (Art. 11)
- 🟡 Automated logging of AI events required (Art. 12)
- 🟡 Output interpretation guidance required (Art. 13)
- 🟡 Input data information required (Art. 13)
- 🟡 Accuracy metrics should be documented (Art. 15)
- 🟡 Robustness testing recommended (Art. 15)
```

## What each finding means

| Finding | Why it fired | EU AI Act hook |
|---------|-------------|----------------|
| `provider:openai` | `import openai` + `OpenAI()` + `client.chat.completions` (AST-verified, 3 occurrences) | Art. 3/6 — the project operates an AI system |
| `pattern:missing-logging` | The file imports an AI provider but contains no logging at all | Art. 12 — record-keeping |
| `pattern:user-input` | `user_input` / `input` flows into the AI call in an AI-importing file | Art. 50 — transparency |
| `pattern:chat-interface` | Chat wording in an AI context (also matched in the sample's `README.md` and `REPORT.md`) | Art. 50 — transparency |

The Art. 12 and Art. 50 signals drive the **LIMITED** risk tier: user-facing AI
without Annex III high-risk domain indicators. (`README.md` and `REPORT.md` are
scanned too — that is why three files are counted, and why chat-interface fires
in the docs.)

## JSON format

`compliance-agent scan examples/sample-chatbot --format json` produces a
versioned envelope (excerpt; full output includes all findings, gaps, and the
risk assessment):

```json
{
  "schema_version": "1.0",
  "tool_version": "0.1.3",
  "scan_result": {
    "project_path": ".../examples/sample-chatbot",
    "files_scanned": 3,
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
        "description": "File imports an AI provider but contains no logging. High-risk AI systems must support automatic event recording.",
        "article": "Art. 12 (record-keeping)",
        "suggestion": "Add structured logging around AI model calls.",
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

copies the applicable templates:

```
fixes/
├── RECOMMENDATIONS.md              # step-by-step instructions
├── art12/event_logging.py          # Art. 12 — event logging with retention
├── art50/transparency_notice.py    # Art. 50 — AI disclosure
├── art50/content_marking.py
├── art50/deepfake_disclosure.py
├── art11/technical_documentation.py
└── common/...
```

Apply the Art. 50 notice and the Art. 12 logger to `app.py`, re-scan, and the
warning finding disappears.
