# Expected Output

Real output from `compliance-agent scan examples/sample-chatbot` (run from the
repo root; timestamps will differ).

## Markdown format (default)

```markdown
# EU AI Act Compliance Report

- **Project:** `.../compliance-agent/examples/sample-chatbot`

## Scan Summary

- **Files scanned:** 2
- **AI providers detected:** 1 (OpenAI)
- **Risk tier:** **LIMITED**
- **Findings:** 1 warning, 4 info

## Risk Assessment

Confidence: 70%

- AI provider usage combined with user-facing interaction detected;
  transparency obligations (Art. 50) apply, but no Annex III high-risk
  domain matched.

## Compliance Gaps

### 🟡 Missing record-keeping for AI calls (Art. 12)

AI provider calls found without logging. The EU AI Act requires automatic
recording of events for high-risk systems.

**Recommendation:** Add structured logging around all model invocations.

### 🟡 AI interaction transparency not verified (Art. 50)

Users appear to interact with AI output. They must be informed they are
interacting with an AI system.

**Recommendation:** Add a clear AI disclosure notice in the user interface.

## Findings

### `README.md`

- 🔵 **info** `pattern:chat-interface` (line 3, ×3): Chat interface detected

### `app.py`

- 🟡 **warning** `pattern:missing-logging` (file-level): AI usage without logging
- 🔵 **info** `pattern:chat-interface` (line 1, ×6): Chat interface detected
- 🔵 **info** `provider:openai` (line 19, ×3): OpenAI usage detected
- 🔵 **info** `pattern:user-input` (line 22, ×5): User input feeding an AI system detected
```

## What each finding means

| Finding | Why it fired | EU AI Act hook |
|---------|-------------|----------------|
| `provider:openai` | `import openai` + `OpenAI()` + `client.chat.completions` (AST-verified, 3 occurrences) | Art. 3/6 — the project operates an AI system |
| `pattern:missing-logging` | The file imports an AI provider but contains no logging at all | Art. 12 — record-keeping |
| `pattern:user-input` | `user_input` / `input` flows into the AI call in an AI-importing file | Art. 50 — transparency |
| `pattern:chat-interface` | Chat wording in an AI context (and `chatbot` in the README) | Art. 50 — transparency |

The two 🟡 **gaps** (Art. 12, Art. 50) drive the **LIMITED** risk tier:
user-facing AI without Annex III high-risk domain indicators.

## JSON format

`compliance-agent scan examples/sample-chatbot --format json` produces a
versioned envelope (excerpt; full output includes all findings, gaps, and the
risk assessment):

```json
{
  "schema_version": "1.0",
  "tool_version": "0.1.0",
  "scan_result": {
    "project_path": ".../examples/sample-chatbot",
    "files_scanned": 2,
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
warning findings disappear.
