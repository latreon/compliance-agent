# Examples

## `sample-chatbot/` — intentionally non-compliant

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
[EXPECTED_OUTPUT.md](EXPECTED_OUTPUT.md) for the full, real scan output and
[SAMPLE_PDF_REPORT.md](SAMPLE_PDF_REPORT.md) for what the PDF contains.

### Run it (optional)

```bash
pip install -r sample-chatbot/requirements.txt
export OPENAI_API_KEY=sk-...
python sample-chatbot/app.py
```
