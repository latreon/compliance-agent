# Expected Output

Running `compliance-agent scan examples/sample-chatbot` produces (paths
shortened; timestamps will differ):

```markdown
# EU AI Act Compliance Report

- **Project:** `examples/sample-chatbot`

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

### `examples/sample-chatbot/app.py`

- 🟡 **warning** `pattern:missing-logging` (file-level): AI usage without logging
- 🔵 **info** `pattern:chat-interface` (line 1, ×6): Chat interface detected
- 🔵 **info** `provider:openai` (line 7, ×3): OpenAI usage detected
- 🔵 **info** `pattern:user-input` (line 12, ×5): User input feeding an AI system detected
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

Apply the Art. 50 notice and Art. 12 logger to `app.py`, re-scan, and the
warning findings disappear.
