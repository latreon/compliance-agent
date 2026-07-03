# ComplianceAgent

EU AI Act compliance scanner for AI projects. ComplianceAgent scans your codebase for AI usage (model providers, agentic patterns, user-facing interfaces), classifies the project into an EU AI Act risk tier, and reports compliance gaps with references to the relevant articles.

## What it does

1. **Scans** `.py`, `.yaml`, `.yml`, `.json`, `.toml`, and `.md` files for:
   - AI providers — OpenAI, Anthropic, Google, Mistral, local models (transformers, ollama, vLLM, torch)
   - Agent patterns — MCP servers, tool calling, multi-agent frameworks (CrewAI, AutoGen, LangGraph)
   - General patterns — user input handling, chat interfaces, data processing, logging presence
2. **Classifies** the project into a risk tier (`unacceptable` / `high` / `limited` / `minimal`) by mapping findings to the eight Annex III high-risk categories, with a confidence score and reasoning.
3. **Analyzes gaps** against key obligations: record-keeping (Art. 12), human oversight (Art. 14), transparency (Art. 50), risk management (Art. 9).
4. **Reports** in Markdown (with Rich terminal output) or JSON.

## Installation

```bash
# with uv
uv pip install compliance-agent

# or with pip
pip install compliance-agent
```

For development:

```bash
git clone https://github.com/latreon/compliance-agent.git
cd compliance-agent
uv sync
```

## Quick start

```bash
# Scan the current directory
compliance-agent scan .

# Scan a specific project, JSON output
compliance-agent scan ~/projects/my-ai-app --format json

# CI gate: exit 1 if any warning-or-above findings exist
compliance-agent scan . --fail-on warning
```

## CLI usage

```text
compliance-agent scan [PATH] [OPTIONS]

Arguments:
  PATH                  Project path to scan (default: .)

Options:
  -f, --format TEXT     Output format: markdown, json (default: markdown)
  --fail-on TEXT        Fail with exit code 1 if findings at this severity
                        or above exist (info, warning, high, critical)
  -v, --verbose         Verbose output

compliance-agent version
```

Exit codes: `0` success, `1` fail-on threshold met, `2` usage error.

## Risk classification

Risk tiers follow the EU AI Act structure:

| Tier | Meaning |
|------|---------|
| `unacceptable` | Prohibited practices (Art. 5) |
| `high` | Matches an Annex III high-risk category |
| `limited` | AI with user interaction — transparency obligations apply |
| `minimal` | Everything else |

Annex III keyword rules live in [`rules/annex3.yaml`](rules/annex3.yaml) and are fully customizable.

## Development

```bash
uv run pytest                     # tests with coverage
uv run compliance-agent scan .    # scan this repo
```

## Resources

- [EU AI Act (Regulation (EU) 2024/1689)](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)
- [EU AI Act explorer](https://artificialintelligenceact.eu/)

## Disclaimer

This tool provides automated heuristics, not legal advice. Consult a qualified professional for compliance decisions.

## License

[MIT](LICENSE)
