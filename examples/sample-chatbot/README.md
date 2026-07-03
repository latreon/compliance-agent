# Sample Chatbot (intentionally non-compliant)

A minimal OpenAI chatbot with **no compliance measures** — no AI disclosure,
no event logging. Used to demonstrate what ComplianceAgent detects.

```bash
# From the repo root:
compliance-agent scan examples/sample-chatbot
compliance-agent recommend examples/sample-chatbot --output ./fixes
```

See [../EXPECTED_OUTPUT.md](../EXPECTED_OUTPUT.md) for the scan result this
project produces.
