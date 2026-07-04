# Architecture

ComplianceAgent is a static analyzer. It reads project files, decides how the
project uses AI, checks that usage against EU AI Act obligations, and emits a
report with copy-pasteable fixes. It never executes the code it scans.

## Pipeline

```
files ─▶ Scanner ─▶ Classifier ─▶ Gap Analyzer ─▶ Recommender ─▶ Reporter
        detectors    risk tier     coverage+gaps    templates      terminal/md/json/pdf
```

1. **Scanner** (`scanner/engine.py`, `scanner/detectors/`)
   Walks the project, honoring `.gitignore` and hard-skipping vendored/build
   directories. Reads only `.py/.yaml/.yml/.json/.toml/.md` files under 1 MB.
   Detectors emit **findings**:
   - `providers.py` — OpenAI, Anthropic, Mistral, Google (`google.generativeai`),
     local runtimes (transformers, ollama, vLLM, torch, llama.cpp). Python uses
     AST so provider names in comments/strings do not match.
   - `agents.py` — MCP servers, tool calls, multi-agent orchestration, prompt
     templates.
   - `patterns.py` — chat interfaces, user input into AI, missing logging,
     data processing.
   - `detectors/frameworks/` — LangChain, CrewAI, AutoGen, LangGraph, each
     mapping framework constructs to the articles they implicate.

2. **Classifier** (`classifier/risk.py`, `classifier/annex3.py`) — see below.

3. **Gap Analyzer** (`analyzer/articles/`) — one module per article. Each
   reports a coverage status (Met / Partial / Missing / Not applicable) and any
   gaps. Covered articles: **6, 7, 9, 10, 11, 12, 13, 14, 15, 26, 28, 50**.

4. **Recommender** (`recommender/`) — maps findings and gaps to fix templates in
   `templates/` (`rules.py` holds the mapping) and can export them to a folder.

5. **Reporter** (`reporter/`) — `terminal.py` (default boxed Rich report),
   `markdown.py`, `json_report.py` (versioned envelope), `pdf_report.py`
   (WeasyPrint).

## Risk classification

`RiskClassifier.classify()` produces one of **MINIMAL**, **LIMITED**, or **HIGH**
with a confidence score and reasoning:

1. **No findings** → `MINIMAL`, confidence 1.0 ("no AI usage detected").
2. **Annex III match** → `HIGH`. The classifier matches the
   [Annex III](../rules/annex3.yaml) high-risk domain keywords (biometrics,
   critical infrastructure, employment, essential services/credit, law
   enforcement, etc.) against finding paths, messages, and descriptions using
   word-boundary regex. One hit is enough to classify HIGH; confidence rises
   0.25 per hit (capped at 1.0).
3. **Provider usage + user-facing interaction** (chat interface / user input)
   but no Annex III match → `LIMITED`, confidence 0.7 (Art. 50 transparency
   applies).
4. **Provider usage only** → `MINIMAL`, confidence 0.6.
5. **Generic patterns only, no provider** → `MINIMAL`, confidence 0.8.

### Why there is no automatic `UNACCEPTABLE` tier

The Act's fourth tier — `UNACCEPTABLE` (Article 5 prohibited practices: social
scoring, untargeted facial-image scraping, certain biometric categorization,
manipulative techniques, and so on) — is a **legal determination** that cannot
be made reliably from source code. A keyword match would produce dangerous false
negatives (missing a banned use) and alarming false positives. The tool
therefore never assigns `UNACCEPTABLE`; treat Article 5 as a manual
self-assessment and consult counsel. The `RiskTier.UNACCEPTABLE` enum value
exists only so reports can render the full tier scale for reference.

### Interpreting the tier

The tier is a **floor, not a verdict**. Agentic patterns (tools, multi-agent)
raise oversight and logging *gaps* without, by themselves, forcing a HIGH tier —
HIGH depends on the Annex III domain. If you operate in a high-risk domain the
scanner did not key on, self-assess accordingly.

## Extending

See [CONTRIBUTING.md](../CONTRIBUTING.md) for how to add detectors, article
analyzers, and fix templates (each with tests).
