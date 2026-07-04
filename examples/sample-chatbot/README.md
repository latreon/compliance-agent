# Sample Chatbot (intentionally non-compliant)

A realistic minimal OpenAI chatbot with **no compliance measures**:

- ❌ No AI disclosure — users are never told they're talking to AI (Art. 50)
- ❌ No event logging — no record of any AI interaction (Art. 12)

Used to demonstrate what ComplianceAgent detects and how it recommends fixes.

## Scan it

```bash
# From the repo root:
compliance-agent scan examples/sample-chatbot
compliance-agent recommend examples/sample-chatbot --output ./fixes
```

Expected findings: `provider:openai`, `pattern:missing-logging` (warning),
`pattern:user-input`, `pattern:chat-interface` — risk tier **LIMITED**. All
three files here (`app.py`, `README.md`, `REPORT.md`) are scanned, so
`chat-interface` also fires in the docs.
Full output: [../EXPECTED_OUTPUT.md](../EXPECTED_OUTPUT.md)

## Run it (optional)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
python app.py
```
