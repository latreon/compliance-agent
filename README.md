# ComplianceAgent

**EU AI Act compliance scanner for AI projects. Run one command, know your status.**

[![CI](https://github.com/latreon/compliance-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/latreon/compliance-agent/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Why This Exists

The EU AI Act (Regulation 2024/1689) has **hard deadlines**:

- **August 2, 2026** — Transparency obligations (Article 50): chatbots, AI-generated content, deepfakes
- **August 2, 2027** — High-risk systems (Annex III): biometrics, employment, credit scoring, law enforcement

Fines: up to **€35M or 7% of global annual turnover**.

Existing compliance tools are enterprise SaaS costing **$30K+/year**. ComplianceAgent is:

- **Free and open source** (MIT license)
- **CLI-first** — run one command, get a report in seconds
- **Developer-native** — CI/CD integration, GitHub Actions, pre-commit hooks
- **Agent-aware** — detects MCP servers, tool calls, multi-agent patterns
- **Precise** — AST-based detection; provider names in comments, docstrings, and READMEs don't trigger false positives

## Quick Start

```bash
# Install
pip install compliance-agent

# Scan your project
compliance-agent scan .

# Get fix recommendations with ready-to-use templates
compliance-agent recommend . --output ./fixes
```

## What It Detects

**AI Providers**

- OpenAI (GPT-4, GPT-4o, o1)
- Anthropic (Claude)
- Google (Gemini)
- Mistral
- Local models (Ollama, vLLM, transformers, llama.cpp, torch)

**Agent Patterns**

- MCP servers and tool definitions
- Tool calls and function calling
- Multi-agent orchestration (CrewAI, AutoGen, LangGraph)
- Prompt templates and system prompts

**Risk Classification**

Maps detected patterns to EU AI Act risk tiers using the eight Annex III
categories (customizable keyword rules in `rules/annex3.yaml`):

| Tier | Meaning |
|------|---------|
| **Unacceptable** | Prohibited AI practices (Art. 5) |
| **High** | Annex III categories — biometrics, employment, credit, law enforcement |
| **Limited** | Transparency obligations apply (chatbots, generated content) |
| **Minimal** | Most AI applications |

## Example Output

```text
$ compliance-agent scan examples/sample-chatbot

## Scan Summary

- Files scanned: 2
- AI providers detected: 1 (OpenAI)
- Risk tier: LIMITED
- Findings: 1 warning, 4 info

## Compliance Gaps

🟡 Missing record-keeping for AI calls (Art. 12)
   → Add structured logging around all model invocations.

🟡 AI interaction transparency not verified (Art. 50)
   → Add a clear AI disclosure notice in the user interface.

## Findings

examples/sample-chatbot/app.py
- warning  pattern:missing-logging  AI usage without logging
- info     provider:openai (line 7, ×3)  OpenAI usage detected
- info     pattern:user-input (line 12, ×5)  User input feeding an AI system
```

Full sample: [`examples/EXPECTED_OUTPUT.md`](examples/EXPECTED_OUTPUT.md)

## CLI Reference

```bash
# Scan a project
compliance-agent scan <path>

# Output formats
compliance-agent scan . --format json      # Machine-readable
compliance-agent scan . --format markdown  # Human-readable (default)

# Filtering
compliance-agent scan . --severity high      # Only show high/critical findings
compliance-agent scan . --exclude "tests/*"  # Exclude paths (repeatable)
compliance-agent scan . --include "src/*"    # Restrict scan scope

# CI/CD integration
compliance-agent scan . --ci --fail-on high  # Plain output, exit 1 on high+

# Fix recommendations
compliance-agent scan . --fix                    # Include recommendations in scan
compliance-agent recommend . --output ./fixes   # Copy templates locally
```

Exit codes: `0` success · `1` fail-on threshold met · `2` usage error.
`.gitignore` is honored automatically; vendored directories are always skipped.

## CI/CD Integration

**GitHub Actions**

```yaml
- name: EU AI Act Compliance Check
  run: |
    pip install compliance-agent
    compliance-agent scan . --ci --fail-on high
```

**Pre-commit Hook**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/latreon/compliance-agent
    rev: v0.1.0
    hooks:
      - id: compliance-agent-scan
        args: [--fail-on, high]
```

## Fix Templates

ComplianceAgent doesn't just find problems — it ships solutions. Every gap
maps to a real, copy-pasteable template ([index](templates/README.md)):

| Article | Template | Purpose |
|---------|----------|---------|
| 50 | `transparency_notice.py` | AI interaction disclosure (decorator + ASGI middleware) |
| 50 | `content_marking.py` | Machine-readable AI content marking |
| 50 | `deepfake_disclosure.py` | Synthetic media labeling |
| 12 | `event_logging.py` | AI event logging with retention + cleanup |
| 14 | `human_oversight.py` | Human-in-the-loop checkpoints with audit trail |
| 9 | `risk_management.py` | Risk register and review cycle |
| 10 | `data_governance.py` | Dataset provenance cards |
| 11 | `technical_documentation.py` | Annex IV technical documentation generator |

Each template is fully working Python (compile-checked in CI), well-commented,
and framework-agnostic (FastAPI, Flask, Streamlit).

## Development

```bash
git clone https://github.com/latreon/compliance-agent.git
cd compliance-agent
uv sync
uv run pytest                     # tests with coverage
uv run compliance-agent scan .    # dogfood: scan this repo
```

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Priority areas:

- New detector patterns (framework-specific: LangChain, LlamaIndex, Haystack)
- Additional templates for other articles
- Integration with more AI frameworks
- Documentation improvements

## Resources

- [EU AI Act (Regulation (EU) 2024/1689) — full text](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)
- [EU AI Act explorer](https://artificialintelligenceact.eu/)

## License

MIT License — see [LICENSE](LICENSE).

## Disclaimer

This tool provides technical analysis, not legal advice. Consult qualified
legal counsel for EU AI Act compliance decisions.
