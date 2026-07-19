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
   - `providers.py` — OpenAI, Anthropic, Mistral, Cohere, Groq, Together,
     Replicate, Hugging Face, Google (`google.generativeai`/`google.genai`),
     AWS Bedrock, DeepSeek, Fireworks AI, xAI (Grok), and local runtimes
     (transformers, ollama, vLLM, torch, llama.cpp). Python uses AST so
     provider names in comments/strings do not match.
   - `agents.py` — a *scanned project's* own use of MCP servers/clients, tool
     calls, multi-agent orchestration, and prompt templates. (Unrelated to
     ComplianceAgent's own MCP server, which exposes this pipeline as tools —
     see [docs/MCP.md](MCP.md).)
   - `patterns.py` — chat interfaces, user input into AI, missing logging,
     data processing, and a hand-rolled agent loop (`while True:` calling
     something that names an agent step) for projects with no framework at all.
   - `detectors/frameworks/` — LangChain, CrewAI, AutoGen, LangGraph,
     LlamaIndex, Vercel AI SDK, Semantic Kernel, Haystack, DSPy, and Instructor,
     each mapping framework constructs to the articles they implicate.

2. **Classifier** (`classifier/risk.py`, `classifier/annex3.py`) — see below.

3. **Gap Analyzer** (`analyzer/articles/`) — one module per article. Each
   reports a coverage status (Met / Partial / Unverified / Missing / Not
   applicable) and any gaps. A requirement is **Met** only with a verifiable
   signal (a real code mechanism or a concrete artifact file); an obligation
   merely referenced in documentation prose is **Unverified** (reported as an
   open item, never as compliant). Covered articles: **5, 6, 9, 10, 11, 12, 13,
   14, 15, 16, 17, 24, 26, 27, 43, 50, 53-55** (17 analyzers — see
   `analyzer/articles/__init__.py`'s `ALL_ARTICLE_ANALYZERS` for the
   authoritative list, and the README's
   [Compliance Coverage](../README.md#compliance-coverage) table for what each
   one checks). Art. 53-55 (general-purpose AI model provider obligations) is
   gated on actual model-training signals or a self-declared GPAI/foundation-model
   provider — not on merely calling a hosted provider's API, which makes a
   project a *deployer* (Art. 26/50), not a GPAI model *provider*.

4. **Recommender** (`recommender/`) — maps findings and gaps to fix templates in
   `templates/` (`rules.py` holds the mapping) and can export them to a folder.

5. **Reporter** (`reporter/`) — `terminal.py` (default boxed Rich report),
   `markdown.py`, `json_report.py` (versioned envelope), `pdf_report.py`
   (WeasyPrint), `sarif_report.py` (SARIF 2.1.0, for GitHub code scanning),
   `html_report.py` (self-contained dashboard export), `diff_report.py`
   (Markdown rendering for `compliance-agent diff`).

## Other surfaces

- **`compliance-agent diff`** (`diff.py`) — compares two JSON reports
  (`(detector, category, file_path)`-keyed finding matching, gap
  resolved/new/status-changed tracking, risk-tier movement) and can gate CI on
  regression with `--fail-on-regression`.
- **`compliance.yaml` project config** (`config.py`) — a project can declare
  scan defaults (`exclude`, `include`, `fail_on`, `severity`, `format`,
  `output`) and a posture (`risk_tier`, `intended_purpose`); a declared
  `risk_tier` can only *raise* the detected tier, never lower it. Explicit CLI
  flags always win over the config file.
- **Web dashboard** (`web/`, `compliance-agent serve`) — a local FastAPI app
  serving the same report interactively, with scan history, a compare-with-
  previous-scan view, and OpenAPI docs (`/docs`, `/redoc`, `/openapi.json`).
  No authentication — binds to `127.0.0.1` only by design; see
  [SECURITY.md](../SECURITY.md) for its threat model.
- **MCP server** (`mcp_server.py`, `compliance-agent-mcp`) — exposes the same
  pipeline as MCP tools for AI assistants (Claude Desktop, Cursor, etc.) to
  call directly. stdio by default (local, single-user trust); `--http` adds
  bearer-token auth, an optional path allowlist, and file-count/timeout
  guards. See [docs/MCP.md](MCP.md) for the full tool reference and
  [README's MCP Server section](../README.md#mcp-server) for the quick
  start.

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
2. **No AI provider or framework detected** → domain matching is skipped
   entirely. The EU AI Act governs AI systems, so a project that merely *names*
   high-risk domains (or is itself a compliance tool) is never escalated on that
   basis. Such projects fall through to `LIMITED`/`MINIMAL` below.
3. **Prohibited-practice match** → `UNACCEPTABLE` (see below). Checked first —
   it outranks every other tier.
4. **Annex III match** → `HIGH`. The classifier matches the
   [Annex III](../rules/annex3.yaml) high-risk domain keywords (biometrics,
   critical infrastructure, employment, essential services/credit, law
   enforcement, etc.) against a corpus of the scanned project's **file paths and
   code (`.py`) content** — assembled by the scanner honoring the same
   exclude/include/.gitignore filtering — using word-boundary regex. Test files
   and non-code prose/config are excluded from the corpus to limit false
   positives. One hit is enough to classify HIGH; confidence is floored at 0.5
   and rises 0.25 per hit (capped at 1.0). The reasoning notes that HIGH is
   provisional (Art. 6(3) exempts some narrow-purpose systems).
5. **Provider usage + user-facing interaction** (chat interface / user input)
   but no Annex III match → `LIMITED`, confidence 0.7 (Art. 50 transparency
   applies).
6. **Provider usage only** → `MINIMAL`, confidence 0.6.
7. **Generic patterns only, no provider** → `MINIMAL`, confidence 0.8.

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
