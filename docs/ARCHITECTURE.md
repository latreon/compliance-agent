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
   gaps. Covered articles: **5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 24, 43, 50**.

4. **Recommender** (`recommender/`) — maps findings and gaps to fix templates in
   `templates/` (`rules.py` holds the mapping) and can export them to a folder.

5. **Reporter** (`reporter/`) — `terminal.py` (default boxed Rich report),
   `markdown.py`, `json_report.py` (versioned envelope), `pdf_report.py`
   (WeasyPrint).

Supporting modules used across the pipeline:

- **`models/`** — the core Pydantic data structures (`findings.py`,
  `recommendations.py`) passed between stages.
- **`updates.py`** — checks PyPI for a newer release and powers the post-scan
  update notice (suppressed by `--no-update-check` /
  `COMPLIANCE_AGENT_NO_UPDATE_CHECK`).

## Risk classification

`RiskClassifier.classify()` produces one of **UNACCEPTABLE**, **HIGH**,
**LIMITED**, or **MINIMAL** with a confidence score and reasoning:

1. **No findings** → `MINIMAL`, confidence 1.0 ("no AI usage detected").
2. **Prohibited-practice match** → `UNACCEPTABLE` (see below). Checked first —
   it outranks every other tier.
3. **Annex III match** → `HIGH`. The classifier matches the
   [Annex III](../rules/annex3.yaml) high-risk domain keywords (biometrics,
   critical infrastructure, employment, essential services/credit, law
   enforcement, etc.) against finding paths, messages, and descriptions using
   word-boundary regex. One hit is enough to classify HIGH; confidence is
   floored at 0.5 and rises 0.25 per hit (capped at 1.0). The reasoning notes
   that HIGH is provisional (Art. 6(3) exempts some narrow-purpose systems).
4. **Provider usage + user-facing interaction** (chat interface / user input)
   but no Annex III match → `LIMITED`, confidence 0.7 (Art. 50 transparency
   applies).
5. **Provider usage only** → `MINIMAL`, confidence 0.6.
6. **Generic patterns only, no provider** → `MINIMAL`, confidence 0.8.

### The `UNACCEPTABLE` tier (Article 5 prohibited practices)

The classifier flags `UNACCEPTABLE` when it matches an Article 5 prohibited
practice (social scoring, untargeted facial-image scraping, certain biometric
categorization, manipulative techniques, and so on) from
[`rules/prohibited.yaml`](../rules/prohibited.yaml), using the same
word-boundary matching as Annex III. To limit false alarms — an UNACCEPTABLE
result is severe — only specific multi-word phrases are used, never bare words.

Whether a practice is actually prohibited is a **legal determination** the
scanner cannot make from code alone, so a match is an explicit prompt to
self-assess against Article 5 and consult counsel, not a verdict; the reasoning
and the Art. 5 gap say as much. Absence of a match is **not** assurance the
system is permitted — keyword heuristics can miss a banned use.

### Interpreting the tier

The tier is a **floor, not a verdict**. Agentic patterns (tools, multi-agent)
raise oversight and logging *gaps* without, by themselves, forcing a HIGH tier —
HIGH depends on the Annex III domain. If you operate in a high-risk domain the
scanner did not key on, self-assess accordingly.

## Extending

See [CONTRIBUTING.md](../CONTRIBUTING.md) for how to add detectors, article
analyzers, and fix templates (each with tests).
