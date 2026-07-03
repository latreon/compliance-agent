# ComplianceAgent

**Check if your AI project follows EU rules.**

[![CI](https://github.com/latreon/compliance-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/latreon/compliance-agent/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

The EU has new rules for AI. If you're building with OpenAI, Anthropic, LangChain,
or any AI framework, you need to check whether you comply. This tool does it for
you — one command, about 5 seconds.

[30-Second Start](#30-second-start) · [What It Does](#what-it-does-simple-version) · [How It Works](#how-it-works) · [Examples](#real-examples) · [All Commands](#command-reference) · [FAQ](#common-questions)

---

## 30-Second Start

```bash
# Install
pip install compliance-agent

# Check your project
compliance-agent scan .

# That's it — read what it found.
```

## What It Does (Simple Version)

1. **Scans your code** — finds where you use AI (OpenAI, LangChain, etc.).
2. **Checks the rules** — compares your code against EU AI Act requirements.
3. **Tells you what's missing** — shows exactly what you need to fix.
4. **Gives you the code** — provides copy-paste fixes for each problem.

## What You'll See

When you run `compliance-agent scan .`, you get something like:

```text
YOUR PROJECT STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Risk Level: LIMITED (some rules apply)
AI Found:   OpenAI chatbot, LangChain agent
Issues:     3 things to fix

WHAT TO FIX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Add a "You're talking to AI" notice to your chat
   → Copy this file: templates/art50/transparency_notice.py

2. Log all AI conversations (EU requires record-keeping)
   → Copy this file: templates/art12/event_logging.py

3. Add error handling for AI failures
   → Add try/except blocks around AI calls

NEXT STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Get the fix files:  compliance-agent recommend . --output ./fixes
```

## Do I Need This?

**Yes, if you:**

- Use OpenAI, Anthropic, Google, or any AI API
- Build chatbots or AI assistants
- Use LangChain, CrewAI, AutoGen, or LangGraph
- Deploy AI in the EU or serve EU users
- Want to avoid fines (up to €35M)

**No, if you:**

- Don't use AI in your project
- Only use AI for personal projects (not a business)
- Don't operate in, or serve users in, the EU

## Installation

### For most users

```bash
pip install compliance-agent
```

That's it. Skip to the [30-Second Start](#30-second-start).

**If `pip install` fails**, try:

```bash
python -m pip install compliance-agent
```

**If you get "Permission denied":**

```bash
pip install --user compliance-agent
```

**If you use a virtual environment**, activate it first:

```bash
source venv/bin/activate   # Linux / macOS
venv\Scripts\activate      # Windows
pip install compliance-agent
```

**If you use `uv`:**

```bash
uv pip install compliance-agent
```

**Install the latest unreleased version from GitHub:**

```bash
pip install git+https://github.com/latreon/compliance-agent.git
```

**Verify it worked:**

```bash
compliance-agent version
# ComplianceAgent v0.1.0
```

Trouble installing or running? See the [Troubleshooting guide](docs/TROUBLESHOOTING.md).

## How It Works

### Step 1: Scan your code

The scanner reads your project files and looks for AI-related patterns:

- `import openai` — you're using OpenAI
- `from langchain` — you're using LangChain
- `AgentExecutor()` — you're running an AI agent
- `client.chat.completions.create()` — you're calling an AI API

It uses **AST parsing** (not just text search) to avoid false positives. A comment
that mentions "OpenAI" won't trigger a finding — only real code does.

### Step 2: Classify risk

Based on what it finds, the tool assigns a risk level:

| Risk Level | What It Means | Rules That Apply |
|------------|---------------|------------------|
| **MINIMAL** | Basic AI usage, no user interaction | Almost none |
| **LIMITED** | AI interacts with users | Transparency rules (Art. 50) |
| **HIGH** | AI makes important decisions | Full compliance required |
| **UNACCEPTABLE** | Banned AI practices (Art. 5) | Cannot be deployed |

### Step 3: Check compliance

The tool checks 12 specific articles of the EU AI Act:

| Article | What It Checks | When It Matters |
|---------|----------------|-----------------|
| Art. 50 | "You're talking to AI" notice | Any user-facing AI |
| Art. 12 | Logging AI conversations | All AI systems |
| Art. 14 | Human oversight for decisions | High-risk / agentic AI |
| Art. 15 | Error handling and robustness | All AI systems |
| ... | [see the full list](#compliance-coverage) | ... |

### Step 4: Recommend fixes

For each issue found, the tool:

1. Explains what's wrong
2. Shows which rule requires the fix
3. Provides a code template you can copy
4. Tells you exactly where to put it

```text
ISSUE: No "You're talking to AI" notice
RULE:  EU AI Act Article 50(1)
FIX:   Copy templates/art50/transparency_notice.py into your project
WHERE: Add it before your chat endpoint
```

## Real Examples

### Example 1: Simple chatbot (Limited risk)

A basic chatbot using OpenAI:

```python
# chatbot.py
import openai

client = openai.OpenAI()

def chat(user_input):
    return client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": user_input}],
    ).choices[0].message.content
```

Scan result:

```text
RISK: LIMITED (Article 50 applies)
ISSUES: 2
  1. No "You're talking to AI" notice
  2. No logging of conversations
FIX: Add a transparency notice + logging.
```

### Example 2: LangChain agent (Higher risk)

An agent that can search the web and send emails:

```python
# agent.py
from langchain.agents import AgentExecutor
from langchain.tools import Tool

tools = [
    Tool(name="search", func=search_web, description="Search the web"),
    Tool(name="email", func=send_email, description="Send an email"),
]

executor = AgentExecutor(agent=agent, tools=tools)
```

Scan result:

```text
RISK: HIGH (agent with tool access)
FRAMEWORKS: LangChain (agent, tools)
ISSUES: 5
  1. No human oversight before tool use
  2. No logging of tool calls
  3. No error handling for API failures
  4. No "You're talking to AI" notice
  5. No data governance documentation
FIX: Add human-in-the-loop, logging, error handling, transparency.
```

### Example 3: CrewAI multi-agent (High risk)

A crew of agents researching and writing:

```python
# crew.py
from crewai import Agent, Task, Crew

researcher = Agent(role="Researcher", tools=[search])
writer = Agent(role="Writer", tools=[write])

crew = Crew(
    agents=[researcher, writer],
    tasks=[Task(description="Research", agent=researcher),
           Task(description="Write", agent=writer)],
)
crew.kickoff()
```

Scan result:

```text
RISK: HIGH (multiple autonomous agents)
FRAMEWORKS: CrewAI (agent, crew, task)
ISSUES: 4
  1. No oversight before crew execution
  2. No logging of agent actions
  3. No documentation of agent roles
  4. No incident reporting procedure
FIX: Add an approval workflow, logging, documentation, incident plan.
```

## Command Reference

```bash
# Scan a folder ('.' = current folder)
compliance-agent scan .

# Output types
compliance-agent scan . --format markdown   # for reading (default)
compliance-agent scan . --format json       # for computers / CI
compliance-agent scan . --format pdf         # for sharing

# Only show serious issues
compliance-agent scan . --severity high

# Skip folders
compliance-agent scan . --exclude "tests/*" --exclude "docs/*"

# Show how to fix each problem
compliance-agent scan . --fix

# Copy fix templates into your project
compliance-agent recommend . --output ./fixes

# Make a shareable report file
compliance-agent report . --output audit-2026.pdf

# For CI/CD: plain output, fail the build on serious issues
compliance-agent scan . --ci --fail-on high
```

Run `compliance-agent scan --help` to see every option explained.

**Exit codes:** `0` success · `1` `--fail-on` threshold met · `2` usage error.
`.gitignore` is honored automatically, and vendored directories are always skipped.

JSON output is a versioned envelope — safe to parse in CI:

```json
{
  "schema_version": "1.0",
  "tool_version": "0.1.0",
  "scan_result": { "files_scanned": 2, "risk_tier": "limited", "findings": ["..."] }
}
```

## What It Detects

**AI providers**

- OpenAI (GPT-4, GPT-4o, o1)
- Anthropic (Claude)
- Google (Gemini)
- Mistral
- Local models (Ollama, vLLM, transformers, llama.cpp, torch)

**Agent patterns**

- MCP servers and tool definitions
- Tool calls and function calling
- Multi-agent orchestration (CrewAI, AutoGen, LangGraph)
- Prompt templates and system prompts

### Framework-aware detection

Beyond generic provider detection, dedicated detectors understand what each
framework construct means for compliance (only in files that actually import the
framework — AST-verified):

| Framework | Detection | Compliance Mapping |
|-----------|-----------|--------------------|
| LangChain | Agents, tools, memory, chains | Art. 14 (oversight), Art. 9 (risk), Art. 12 (logging), Art. 50 (transparency) |
| CrewAI | Crews, agents, tasks, processes | Art. 14 (oversight), Art. 12 (logging), Art. 11 (docs) |
| AutoGen | Agents, group chat, function/code execution | Art. 50 (transparency), Art. 12 (logging), Art. 9 (risk) |
| LangGraph | State graphs, conditional edges, tool nodes, checkpoints | Art. 12 (logging), Art. 11 (docs), Art. 14 (oversight) |

## Compliance Coverage

ComplianceAgent checks the following EU AI Act articles and reports a per-article
status (Met / Partial / Missing / Not applicable):

| Article | Title | When Applicable |
|---------|-------|-----------------|
| 6 | High-risk definition | High-risk tier |
| 7 | Conformity assessment | High-risk tier |
| 9 | Risk management | High-risk tier |
| 10 | Data governance | Data processing or high-risk tier |
| 11 | Technical documentation | Any AI usage |
| 12 | Record-keeping | Any AI usage |
| 13 | Transparency to deployers | User-facing systems |
| 14 | Human oversight | Agentic patterns or high-risk tier |
| 15 | Accuracy, robustness, cybersecurity | Any AI usage |
| 26 | Provider obligations | High-risk tier |
| 28 | Distributor obligations | Deployment artifacts present |
| 50 | User transparency | User-facing AI |

## Fix Templates

ComplianceAgent doesn't just find problems — it ships solutions. Every gap maps to
a real, copy-pasteable template ([index](templates/README.md)):

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

Each template is fully working Python (compile-checked in CI), well-commented, and
framework-agnostic (FastAPI, Flask, Streamlit).

## PDF Reports

Generate an audit-ready PDF for compliance teams, legal, or auditors:

```bash
compliance-agent scan . --format pdf
# Report saved to: compliance-report-myproject.pdf

# Or the dedicated report command (PDF or Markdown, custom path)
compliance-agent report . --output audit-2026.pdf
```

The PDF includes a cover page, an executive summary with a risk-tier badge and
metrics, a risk assessment with deadlines, a color-coded findings table, compliance
gaps with remediation steps, fix recommendations with code snippets, and an EU AI
Act reference appendix.

> PDF generation uses [WeasyPrint](https://weasyprint.org/), which needs the pango
> native libraries: `brew install pango` (macOS — run with
> `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` if needed) or
> `apt install libpango-1.0-0 libpangoft2-1.0-0` (Debian/Ubuntu). Markdown and JSON
> formats work without it.

## CI/CD Integration

**GitHub Actions**

```yaml
- name: EU AI Act Compliance Check
  run: |
    pip install compliance-agent
    compliance-agent scan . --ci --fail-on high
```

**Pre-commit hook**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/latreon/compliance-agent
    rev: v0.1.0
    hooks:
      - id: compliance-agent-scan
        args: [--fail-on, high]
```

## Common Questions

**Is this legal advice?**
No. It's a technical tool that checks your code. Consult a lawyer for legal advice.

**Will this slow down my CI/CD?**
No. It takes about 5 seconds on most projects.

**What if I'm not in the EU?**
If you serve EU users, you still need to comply. The EU AI Act applies to anyone
providing AI to EU residents.

**What if I find issues?**
The tool gives you exact code fixes. Copy the templates into your project and
re-run the scan.

**Can I use this in production?**
Yes. Add it to your CI/CD pipeline to catch issues automatically.

## Troubleshooting

Common problems and fixes are in the [Troubleshooting guide](docs/TROUBLESHOOTING.md).
Quick hits:

- **`command not found: compliance-agent`** → run `python -m compliance_agent scan .`
- **PDF generation fails** → `brew install pango` (macOS), or just use
  `--format markdown` / `--format json`
- **Too many findings** → `--exclude "tests/*"` or `--severity high`

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

- New detector patterns (LlamaIndex, Haystack)
- Additional templates for other articles
- Integration with more AI frameworks
- Documentation improvements

## Roadmap

- [x] PyPI release
- [ ] GitHub Action on the Marketplace
- [ ] Project config file (`compliance.yaml`) for declared posture and scan defaults
- [ ] SARIF output for GitHub code scanning integration
- [ ] JS/TS project scanning

## Resources

- [EU AI Act (Regulation (EU) 2024/1689) — full text](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)
- [EU AI Act explorer](https://artificialintelligenceact.eu/)

## License

MIT License — see [LICENSE](LICENSE).

## Disclaimer

This tool provides technical analysis, not legal advice. Consult qualified legal
counsel for EU AI Act compliance decisions.
