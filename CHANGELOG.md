# Changelog

All notable changes to ComplianceAgent are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- New MCP tool `export_sarif`: scans a project and renders the result as a
  SARIF 2.1.0 log — the format `github/codeql-action/upload-sarif` (and
  most other code-scanning consumers) expect — inline or written to a file
  via `output`. Reuses the same scan -> classify -> gaps -> coverage
  pipeline as `scan_project`, minus recommendation generation.
- MCP server `--http` mode now requires `COMPLIANCE_AGENT_MCP_TOKEN` (a
  bearer token) and refuses to start without it — previously it served
  unauthenticated. Requests without a matching `Authorization: Bearer`
  header get a 401.
- New `COMPLIANCE_AGENT_MCP_ALLOWED_ROOTS` env var: an optional
  comma-separated allowlist of directories every scanned/read/written path
  must resolve inside (symlink-safe). Recommended for any `--http`
  deployment; stdio's local single-user usage is unaffected when unset.
- New `COMPLIANCE_AGENT_MCP_MAX_FILES` (default 20,000) and
  `COMPLIANCE_AGENT_MCP_TIMEOUT_SECONDS` (default 120) env vars bound scan
  size and wall-clock duration, so a huge or pathological project can't tie
  up the server indefinitely.
- New `--host` flag (default `127.0.0.1`) for explicit control over what
  `--http` binds to, instead of only the implicit FastMCP default.
- The MCP server now emits a structured audit log line (tool name, resolved
  path) to stderr for every `scan_project`/`get_summary`/`recommend_fixes`/
  `diff_scans` call, plus a line for every allowlist rejection — configurable
  via `COMPLIANCE_AGENT_MCP_LOG_LEVEL`.

## [0.5.0] - 2026-07-13

MCP server, plus a batch of CLI correctness fixes.

### Added

- **MCP server** (`compliance-agent-mcp`, optional install via
  `pip install compliance-agent[mcp]`): exposes the scan -> classify -> gaps
  -> coverage -> recommendations pipeline as 7 tools for Claude Desktop,
  Cursor, and any other MCP-compatible client — `scan_project`,
  `get_summary`, `recommend_fixes`, `diff_scans`, `get_article_info`,
  `list_templates`, `get_version`. Runs over stdio (default) or `--http`.
- `scan_project` supports `format="pdf"`/`"html"` (written to disk via
  `output`, since a PDF can't be returned as chat text) alongside the
  existing `markdown`/`json`.
- `recommend_fixes` can export the actual fix template files plus a
  `RECOMMENDATIONS.md` into a directory via `output_dir` — previously it
  only ever returned recommendation text.
- `diff_scans` supports `format="json"` and an `output` file path,
  mirroring `compliance-agent diff --format json --output`.
- `scan_project`/`get_summary`/`recommend_fixes` resolve a bare project
  name (e.g. `"perch"`) against common dev-folder locations (`~/Developer`,
  `~/dev`, `~/code`, `~/Desktop`, and others, including one level of
  subdirectories) when no exact path is given, instead of requiring the
  full path up front.
- **LlamaIndex framework detector** (Python + JS/TS): document indexing
  (Art. 10 data governance), retrieval/query pipelines (Art. 15 robustness), and
  agents (Art. 14 oversight). Version detected from manifests like the others.
- `RELEASING.md`: one-time setup for PyPI Trusted Publishing (OIDC) and the
  GitHub Marketplace listing, plus the tag-to-release flow.
- Scanner-engine error-path tests (broken detector recorded to `scan_errors`,
  oversized-file skip), lifting engine coverage from 85% to 89%.
- **DeepSeek, Fireworks AI, and xAI (Grok) provider detection**: native Python
  imports, `langchain-deepseek`/`langchain-fireworks`/`langchain-xai`
  integrations, and the corresponding Vercel AI SDK packages
  (`@ai-sdk/deepseek`, `@ai-sdk/fireworks`, `@ai-sdk/xai`).
- **Haystack, Semantic Kernel, DSPy, and Instructor framework detectors**:
  pipelines/agents/retrieval (Haystack), kernel/plugins/agents (Semantic
  Kernel), modules/optimizers/ReAct agents (DSPy), and structured-output
  extraction (Instructor).
- **Generic agent-loop detection for Art. 14**: a hand-rolled
  `while True: run_agent()` loop with no framework in sight, and Semantic
  Kernel agents, now trigger the human-oversight check — previously only
  LangChain/CrewAI/AutoGen/LangGraph (and now LlamaIndex/Vercel AI) agent
  constructs did.
- **New Art. 53-55 analyzer for GPAI (general-purpose AI) model provider
  obligations**: technical documentation, downstream-integrator
  documentation (model card), a public summary of training content,
  a copyright-compliance policy, and — when a project's own docs claim
  systemic risk — model evaluation/incident-tracking requirements. Gated on
  actual training/fine-tuning code signals or an explicit self-declaration,
  never on merely calling a hosted provider's API (that makes a project a
  *deployer*, not a GPAI model *provider*).
- `--fail-on`/`--severity` help text now documents their interaction:
  `--fail-on` always evaluates the full, unfiltered scan, independent of
  `--severity`.

### Fixed

- `get_summary`/`recommend_fixes` now honor a project's `compliance.yaml`
  `exclude`/`include` lists, matching `scan_project` and the CLI's own
  `recommend`/`report` commands — previously ignored, so the same project
  could give inconsistent results depending on which tool was called.
- `recommend_fixes`'s "no fix template available yet" message now sorts
  EU AI Act article labels ("Art. 5", "Art. 53") numerically instead of as
  strings (same bug class fixed in `list_templates`/`get_article_info`,
  missed here initially).
- An unexpected pipeline failure inside an MCP tool now returns a clean
  error string instead of surfacing as a raw Python traceback.
- `get_article_info`'s rules-file preview now truncates at a full line
  boundary (with a note on how many lines were omitted) instead of cutting
  off mid-line.
- **Article probes now scan JS/TS, not just Python.** `ProjectProbe.code_text`
  read only `*.py`, so the Art. 14/15/26/50 code checks missed controls that
  live in TypeScript (an AI-disclosure banner, `killSwitch`, a human-in-the-loop
  gate in a Next.js app). It now scans Python + JS/TS with per-language comment
  stripping. Probe term matching also spans `snake_case` / `camelCase` /
  `kebab-case`, so `human_in_the_loop` matches `humanInTheLoop`.
- `@ai-sdk/azure` now maps to the `openai` provider (Azure-hosted OpenAI),
  matching the `AzureOpenAI` constructor convention — Azure-hosted Vercel AI
  projects are now identified correctly.
- Vercel AI SDK `experimental_generateObject` / `experimental_streamObject` are
  now detected as structured-output calls.
- `@langchain/textsplitters` (common in RAG pipelines) is recognized as a
  LangChain import.
- CrewAI `memory=True` now requires a word boundary (no longer matches an
  unrelated `memory=Trueish`), and explicit `EntityMemory` / `UserMemory` /
  `ExternalMemory` classes are detected.
- Test suite is warning-free: the Starlette `TestClient` httpx-deprecation
  warning is scoped-ignored in pytest config (we deliberately stay on the
  well-audited `httpx` rather than pull `httpx2` into the TLS chain for a
  test-only warning).
- Stale `v0.3.0` version references in the README corrected to `v0.4.0`
  (badge line, CI example output, GitHub Action `rev:` pin).
- `scan --exclude`/`--include` now merge with compliance.yaml's `scan.exclude`/
  `scan.include` lists instead of silently replacing them — a project with
  `exclude: ["docs/*"]` in its config that also passes `--exclude tests/*` on
  the command line now gets both patterns excluded, not just the CLI one.
- A `--fail-on` exit forced by a detector crash (`scan_errors`, not a severity
  threshold) is now explained in `--quiet` output too — previously only
  `--verbose`, `--ci`, and file-based reports surfaced the reason.
- `ProjectProbe.doc_text` now also reads reStructuredText (`**/*.rst`,
  Sphinx/ReadTheDocs), AsciiDoc (`**/*.adoc`), and a plain `wiki/` directory —
  previously only `README*` and `docs/**/*.md` were read, so projects
  documenting compliance artifacts outside Markdown were invisible to every
  Art. 14/15/26/50 doc-mention probe.
- The regex import fallback (used only when a Python file fails to parse) now
  recognizes `from google import genai` / `generativeai`, matching the AST
  path's existing behavior.
- `_check_logging` no longer flags `__init__.py` files, nor a pure
  dataclass/type-only module that imports an AI SDK solely for a type
  annotation or re-export and never calls it.
- `.vue` and `.svelte` single-file components are now scanned for AI imports
  and framework/pattern usage — every extractor here is a line-based regex
  over raw text, so the surrounding template/style markup is simply ignored.
- Art. 15's "robustness testing" requirement now looks for adversarial- or
  robustness-named test files specifically (`*adversarial*`, `*robust*`,
  `*security*`, `*fuzz*`, `*edge_case*`, `*malicious*`), not just any file
  under `tests/`.
- SARIF output no longer declares `columnKind` — no result ever carries a
  `startColumn`/`endColumn`, so the field asserted a capability that doesn't
  exist.
- `--quiet` no longer prints the "Next steps" panel, matching its help text
  ("show only the summary, not the details").
- compliance.yaml's `scan.format` is now validated against the same format
  set the CLI uses (`markdown`/`json`/`pdf`/`html`/`sarif`) at config-parse
  time — a typo like `format: yml` now fails fast with a clear config error
  instead of only surfacing once `scan` actually ran.
- `compliance-agent diff`'s Markdown output now lists each added/removed
  finding individually (file, message, category) under the Findings section,
  not just counts — previously seeing what changed required diffing two JSON
  reports by hand.

## [0.4.0] - 2026-07-12

Comparison, API docs, and automated publishing.

### Added

- **Scan comparison (`compliance-agent diff`)**: compare two JSON reports
  (`scan --format json`) to see whether compliance improved or regressed —
  risk-tier movement, gaps resolved vs. newly introduced, requirements-met
  delta, and finding changes. `--fail-on-regression` exits non-zero when a
  change makes compliance worse, for use as a CI gate. The core lives in the
  new `compliance_agent.diff` module (findings match on
  `(detector, category, file_path)` so a line move isn't a false change; the
  verdict is driven by gaps and tier, not by informational findings).
- **Dashboard comparison view**: select a scan in the history and hit
  **Compare with previous scan** to render the same diff, backed by a new
  read-only `GET /api/diff` endpoint (defaults to latest vs. previous).
- **OpenAPI / Swagger docs for the dashboard API**: the local server now
  exposes `/openapi.json` (machine-readable spec for integrating other tools),
  `/docs` (Swagger UI), and `/redoc`. The docs pages run under a relaxed,
  docs-only CSP; every other route keeps the restrictive baseline, and the
  mutating `POST /api/scan` still requires its custom header. A rail link
  points at the docs.
- **Automated PyPI publishing** ([`.github/workflows/publish.yml`](.github/workflows/publish.yml)):
  pushing a `vX.Y.Z` tag builds the distributions, verifies the tag matches
  `__version__`, checks the wheel contents and metadata, publishes to PyPI via
  Trusted Publishing (OIDC — no stored token), and creates a GitHub release.
- **Framework version detection**: `FrameworkDetection.version` is now
  populated from the project's dependency manifests (`requirements.txt`,
  `pyproject.toml`, `package.json`) and shown in the terminal, Markdown, PDF,
  and dashboard reports. New `compliance_agent.scanner.manifests` module.

### Changed

- Internal cleanups: removed a duplicated/dead `_TEST_DIRS` constant, dropped
  the fragile instance-level line cache in `BaseDetector` (`_lines` is now
  stateless and reentrant), and removed a redundant always-true branch in the
  risk classifier.

## [0.3.0] - 2026-07-12

Distribution and integration release: GitHub Action, project config file,
SARIF output for GitHub code scanning, and dashboard export.

### Added

- **GitHub Action** ([`action.yml`](action.yml)): a Marketplace-ready
  composite action — `uses: latreon/compliance-agent@v0` scans the repo,
  optionally gates the build with `fail-on`, and writes a SARIF report whose
  path is exposed as the `report` output for
  `github/codeql-action/upload-sarif`. Inputs: `path`, `format`, `output`,
  `fail-on`, `args`, `python-version`. Inputs reach the shell only via
  environment variables (no inline interpolation of untrusted values), and
  the CLI is installed from the action's own checkout so the scanner version
  always matches the action tag. CI dogfoods the action on every push
  (`action-test` job).
- **Project config file** (`compliance.yaml` / `.compliance.yaml`): declare
  your AI posture and scan defaults once instead of passing flags every run.
  `posture.risk_tier` participates in classification but can only *raise*
  the detected tier — never lower it — so a config file cannot manufacture
  false assurance; `posture.intended_purpose` records the system's purpose;
  `scan.{exclude,include,fail_on,severity,format,output}` mirror the CLI
  flags. Explicit CLI flags always override the config, a malformed config
  is a hard error (exit 2, never silently ignored), and every surface
  (`scan`, `recommend`, `report`, `serve`, and the dashboard's scan API)
  honors the same file.
- **SARIF output** (`--format sarif`): standard SARIF 2.1.0 for the GitHub
  Security tab and other code-scanning consumers. Findings map to per-file
  results at their detected line; compliance gaps map to project-level
  results anchored to a root manifest; rules are per issue *class* (stable
  across commits, so GitHub deduplicates correctly) and carry
  `security-severity` scores (critical 9.5 / high 8.0 / warning 5.0 /
  info 2.0); files that crashed a detector flip
  `invocations[].executionSuccessful` to `false` so an incomplete scan never
  reads as clean. `--format json` and `--format sarif` both honor
  `--output <file>` now.
- **Dashboard export**: the `serve` dashboard grew **Export → HTML / PDF**
  buttons that download the scan you are viewing (any history entry) as a
  self-contained HTML dashboard or an audit-ready PDF, via new
  `GET /api/export/{html,pdf}` endpoints. PDF rendering is in-memory
  (`PDFReporter.render_pdf_bytes`); when WeasyPrint's native libraries are
  missing the endpoint answers 501 with install instructions instead of
  crashing.
- Fix templates for the 7 articles that previously had an analyzer but no
  template: **Art. 5** (prohibited-practice deployment gate + legal-clearance
  record), **Art. 6** (intended-purpose/Annex III classification record),
  **Art. 13** (instructions for use), **Art. 15** (guarded-call decorator,
  rate limiter, input validation, accuracy log), **Art. 16** (provider
  obligations checklist), **Art. 24** (distributor verification), and
  **Art. 43** (conformity assessment + EU database registration record).
  `compliance-agent recommend` now returns a real, working template for every
  article it can flag a gap against.
- Three new runnable examples: `examples/sample-hiring-tool` (HIGH-risk
  Annex III(4) employment use case, exercising every Chapter III obligation
  and all 14 applicable fix templates), `examples/sample-multi-framework`
  (LangChain + CrewAI + LangGraph combined and deduplicated in one project),
  and `examples/sample-ci-cd` (a copy-paste GitHub Actions workflow gating a
  PR on `--fail-on`, with a real screenshot of `compliance-agent serve`
  added to the docs).

## [0.2.0] - 2026-07-07

Adds a local compliance dashboard and folds in the fixes accumulated since
0.1.9. The dashboard opens a local (loopback-only) HTTP server, so this
release also ships the hardening that comes with any such surface — read
`SECURITY.md` if you're deploying `serve` in anything other than your own
terminal.

### Added

- **`compliance-agent serve <path>`** — a local dashboard (FastAPI + a
  vanilla-JS client shared with the `--format html` export) to run scans,
  browse results, and track history without leaving the browser. Binds to
  `127.0.0.1:8420` by default, scoped to the one project directory it's
  launched for; opens your browser automatically unless `--no-browser` is
  passed. History is capped at the last 50 scans per project, stored under
  `$XDG_DATA_HOME/compliance-agent/history/`, with a gap-count trend line.

### Security

- `serve` rejects requests with a spoofed/rebound `Host` header
  (`TrustedHostMiddleware`), closing a DNS-rebinding path that would
  otherwise let a remote page read dashboard responses as if same-origin.
- `POST /api/scan` requires a same-origin-only request header, so no other
  open browser tab/site can silently trigger a scan (blind CSRF / drive-by
  resource exhaustion) — a cross-origin request can't set the header without
  a CORS preflight this app never grants.
- Every response now carries `Content-Security-Policy` (nonce-scoped for the
  dashboard's own inline bootstrap script), `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer`.
  `/docs`, `/redoc`, and `/openapi.json` stay disabled.
- Scan-history writes are now race-safe: entry ids are reserved atomically,
  so two scans finishing in the same millisecond can no longer overwrite or
  corrupt each other's history file; a symlink planted at the history path
  is refused rather than followed.
- `SECURITY.md`'s threat model now documents the dashboard's attack surface
  and the defenses above.

### Fixed

_(merged after the 0.1.9 tag, not yet part of a prior release)_

- **Provider detection false-negatives**: AWS Bedrock, Cohere, LiteLLM, Groq,
  Together, Replicate, Hugging Face, the `google.genai` SDK, Vertex, and
  `langchain_*` provider bindings are now recognized — a project using them
  was previously reported as containing no AI (MINIMAL). OpenAI-compatible
  clients are now labeled by their actual import/constructor (e.g. `from
  groq import Groq` reads as Groq, not OpenAI).
- **Document-existence checks now require real content.** Art. 10/11/16/24/43
  mechanisms no longer mark a CRITICAL obligation MET from an empty
  `touch TECHNICAL_DOC.md`-style file.
- **Art. 12/16 event-logging gap downgraded from MET to UNVERIFIED** — the
  absence of a "missing logging" signal is not proof an actual event log
  exists.
- **Risk-tier false alarms**: comments are stripped from the domain corpus
  before keyword matching (mirroring the article layer), so prose that
  merely *names* a prohibited/Annex III practice no longer escalates the
  tier. Scanning this project's own source no longer classifies UNACCEPTABLE.
- **`scan --format markdown` now emits real Markdown** when piped or given
  `--output` (previously rendered the Rich terminal report / box-drawing art
  to files).
- **Art. 15 (accuracy/robustness/cybersecurity) now gates on `is_high_risk`**,
  not merely "has AI" — a limited-risk chatbot no longer receives a
  HIGH-severity gap citing statutory language meant for high-risk systems.
- **ANSI/OSC injection closed**: terminal and Markdown reporters strip C0
  control characters from all repo-derived strings (filenames, messages), so
  a hostile filename can no longer recolor output or spoof the rendered risk
  tier.
- Agent/framework detection: snake_case file-path signals (`sales_agent.py`),
  LangChain `AgentType`, and LangGraph `tools=[` patterns are now recognized;
  relative imports (`from .openai import ...`) are no longer misdetected as
  third-party SDK usage; MCP code-signal regexes now run only on `.py` files
  (no longer flag README prose).

### Changed

- PDF MINIMAL-tier badge is neutral slate, never green.
- `--severity` empty state now says "No findings at or above the selected
  severity" instead of the misleading "No AI usage patterns detected".

## [0.1.9] - 2026-07-05

Third pre-promotion review. Fixes two reproducible wrong verdicts (a lawful
high-risk practice branded "prohibited", and a scan that could hang forever),
tightens the CI gate and framework detection, and surfaces heuristic caveats on
every report surface instead of letting a low tier read as a clean bill. Users
who scanned biometric-categorisation or predictive-policing projects with 0.1.8
should re-scan — those verdicts were wrong.

### Fixed

- **Lawful high-risk practices are no longer branded "prohibited".** Bare
  `biometric categorisation` and `predictive policing` appeared in both the
  Annex III (high-risk) and Article 5 (prohibited) keyword sets, and prohibited
  outranks — so any project mentioning them was classified UNACCEPTABLE ("cannot
  be deployed"). Art. 5(1)(g) bans only categorisation that *infers* sensitive
  attributes, and Art. 5(1)(d) only crime prediction based *solely* on profiling;
  the general practices are high-risk, not banned. The prohibited keywords are now
  scoped to the genuinely-banned wording.
- **A scanned symlink can no longer hang the tool.** The compliance-gap probe
  (`ProjectProbe`, run on every scan) followed symlinks and read entire files
  into memory before truncating. A repo containing `x.py -> /dev/zero` hung the
  scan forever. The probe now skips symlinks and caps every read, matching the
  scanner engine's existing guards.
- **`--fail-on` no longer passes an incomplete scan.** The CI gate ignored
  `scan_errors`, so a build stayed green even when a detector crashed and coverage
  was known-incomplete. An incomplete scan now fails the gate regardless of
  threshold.
- **Local modules named like SDKs are no longer misdetected.** Relative imports
  (`from .openai import ...`, `from ..agents.langchain import ...`) were treated as
  imports of the real third-party package, inflating provider/framework detection
  and every downstream obligation. Relative imports are now skipped in both the
  parser and the provider detector.
- **Article 13 is scoped to high-risk systems.** It applied (at HIGH severity) to
  any user-facing AI; instructions-for-use to deployers is a high-risk-only
  obligation, so a limited-risk chatbot no longer sees a spurious HIGH gap.

### Changed

- **Reports no longer let a low tier read as "safe".** Tier-gated articles now
  render as **NOT ASSESSED** (a heuristic non-detection) rather than **N/A** (an
  affirmative "does not apply"); the classifier's undetected-AI caveat now appears
  on the terminal surface, not only in JSON/PDF; confidence is labelled a
  heuristic estimate; the PDF "Requirements met" metric is labelled "assessed
  articles only"; and MINIMAL renders neutral cyan rather than a pass-signalling
  green.
- **PDF "Key deadlines" now includes 2 August 2025** — general-purpose AI model
  obligations (Arts. 51–56), governance, and penalties — which was omitted.

## [0.1.8] - 2026-07-05

Second full pre-promotion review. Fixes reproducible wrong verdicts (in both
directions), a crash on hostile filenames, and report-injection vectors. Users
who scanned with an earlier version should re-scan: some verdicts were
incorrect, most consequentially for framework-based and biometric projects.

### Fixed

- **Prohibited real-time biometric identification is now detected in real code.**
  The Art. 5(1)(h) keyword ("real-time remote biometric identification") is the
  only hyphenated prohibited term; the matcher expanded spaces but not hyphens,
  so it required a literal `-` and could never match the snake_case form
  (`real_time_remote_biometric_identification`) that actually appears in Python.
  The single most severe practice silently classified as LIMITED. Separators
  (space, underscore, hyphen) now match interchangeably.
- **Framework-based AI apps are no longer misclassified as MINIMAL.** The risk
  tier gated on `has_provider` alone, so a LangChain/CrewAI/AutoGen/LangGraph app
  with no raw provider-SDK import collapsed to MINIMAL — contradicting the report
  body, which still listed the framework and its Art. 50 gap. Tier logic now
  gates on AI usage (provider **or** framework).
- **AI usage confined to tests no longer drives obligations.** The AI-presence
  gates (provider/framework/user-interaction) in both the risk classifier and
  the article analyzers counted findings under test paths, so a mocked
  `from openai import OpenAI` in `tests/` classified a no-AI project as LIMITED
  and demanded disclosure/robustness controls. All gates now use production
  (non-test) findings, matching the existing domain-corpus exclusion.
- **Human oversight (Art. 14) can no longer be cleared by an unrelated word.**
  The mechanism check matched the bare token `approval`, so an ordinary
  identifier like `process_loan_approval` satisfied it on a fully autonomous
  high-risk lending agent. Only specific oversight constructs
  (`require_approval`, `human_in_the_loop`, `human_input_mode`, …) now count.
- **Empty placeholder files no longer satisfy mandatory controls.** An empty
  `risk_register.json` (e.g. `touch`ed) flipped the CRITICAL Art. 9 requirement
  to "met". Artifact checks for Art. 9, Art. 6, and Art. 13 now require real,
  non-trivial file content.
- **Transparency (Art. 50) is not "met" from an arbitrary string literal.** Any
  string containing a phrase like "this is an ai" (including marketing copy)
  marked the disclosure requirement satisfied. Only deliberate disclosure
  constructs (named identifiers/headers) count as met; a bare phrase downgrades
  the gap to UNVERIFIED for manual review.
- **Art. 15 error-handling/cybersecurity are no longer falsely "met".** A
  project-wide `try/except` or a `validate` helper anywhere in the repo cannot be
  tied to the model call site, so these now report UNVERIFIED ("verify manually")
  rather than a confirmed mechanism.
- **`scan` no longer crashes on a hostile or coincidental filename.** File paths
  from the scanned repo were passed to Rich as markup, so a directory named e.g.
  `[/bold]` aborted the default report with `MarkupError` (and `[link=…]` could
  inject a clickable link). Untrusted values now render literally.
- **Markdown reports escape scanned file paths.** A backtick in a filename broke
  out of the inline code span, leaving raw Markdown/HTML — a stored-injection
  vector when the report is rendered downstream. Backticks/newlines/pipes are now
  neutralized (the PDF path already escaped correctly).
- **Art. 6 "Annex III category identified" is graded on documentation, not on
  the scanner's own match** — it was tautologically always "met", inflating
  coverage.
- **`--severity` now filters gaps too, and summary tiles show true totals.**
  Previously only findings were filtered, and the metric tiles were computed from
  the filtered set — so `--severity high` could show "0 AI systems / 0 findings"
  while gaps remained.

### Added

- **Incomplete-scan visibility.** Detector crashes (previously logged only to
  stderr) are recorded in `scan_result.scan_errors` and surfaced in the terminal,
  Markdown, and JSON reports, so a partial scan never reads as clean. New JSON
  field: `scan_errors`.

### Changed

- **A "no AI detected" result is reported at 0.5 confidence, not 1.0**, with an
  explicit caveat that detection covers known SDKs/frameworks and may miss others
  (AWS Bedrock, Azure OpenAI, Vertex, Cohere, raw HTTP).
- **Legal citation precision:** high-risk classification cites Art. 6(2) (not
  6(1)); log-retention cites Art. 19 / Art. 26(6) (not Art. 12); instructions for
  use cite Art. 13(2)–(3). README now distinguishes high-risk statutory
  obligations (Art. 11/12/13/15) from all-AI best practice.
- **Test-directory detection is case-insensitive** (`Tests/`, `TESTS/`), so
  fixtures in capitalized directories don't leak into analysis.

## [0.1.7] - 2026-07-05

### Fixed

- **PDF generation now works on macOS/Homebrew out of the box.** WeasyPrint's
  native libraries (pango, gobject, cairo) live in `/opt/homebrew/lib` (or
  `/usr/local/lib` on Intel), which macOS `dyld` does not search by default — so
  `scan --format pdf` failed with "cannot load library 'libgobject-2.0-0'" even
  after `brew install pango`. The reporter now primes
  `DYLD_FALLBACK_LIBRARY_PATH` with the Homebrew lib directory before importing
  WeasyPrint, so no manual environment export is needed. The failure message was
  also simplified accordingly.

## [0.1.6] - 2026-07-05

Correctness, security, and honesty fixes from a full pre-promotion review.

### Fixed

- **`--fail-on` now considers compliance gaps, not just findings.** Detectors
  only emit INFO/WARNING findings; the severe signals (CRITICAL Art. 5
  prohibited practice, HIGH oversight/robustness gaps) live in `gaps`. The CI
  gate previously inspected findings alone, so `--fail-on high`/`critical`
  silently passed builds on high-risk and UNACCEPTABLE-tier projects.
- **Test-fixture paths no longer inflate the risk tier.** A file such as
  `tests/recruitment.py` is sample data, not the deployed system. The scanner
  already excluded test paths from its domain corpus; the risk classifier's
  second corpus (finding paths/messages) did not, so descriptively named
  fixtures could push a project to a false HIGH/UNACCEPTABLE tier. Both corpora
  now apply the same exclusion.
- **A requirement can no longer be marked "met" from a code comment.** The
  documentation probe strips Python comments before matching, so a leftover
  `# TODO: add an AI disclosure` no longer counts as an implemented mechanism.
  Test directories are also excluded from the probe.
- **BOM-prefixed source files are parsed correctly.** A leading byte-order mark
  (common from Windows editors) previously made `ast.parse` fail the whole
  file, silently degrading provider detection to import-line-only regex and
  missing constructor/API-call evidence.

### Security

- **The scanner no longer follows symlinks.** Scanning an untrusted repository
  containing a symlink to a file outside the project (e.g. `utils.py ->
  ~/.ssh/id_rsa`) could read arbitrary local files, and a symlink to a device
  node (`/dev/zero`) bypassed the size cap and could hang the scan. File reads
  are additionally byte-capped independently of the reported size.

### Changed

- **Every LIMITED/MINIMAL result now carries a domain caveat** (terminal header
  and risk reasoning): keyword-based domain detection can miss high-risk uses
  expressed in ordinary wording, so a low tier is never presented as "safe".
- Broadened Annex III keyword coverage (hiring, credit/insurance, education,
  biometrics synonyms) to improve recall, and replaced the collision-prone bare
  `biometric` keyword with specific phrases.
- Single-sourced the severity ranking used for gap ordering and the `--fail-on`
  gate, so the two can no longer drift.

## [0.1.5] - 2026-07-05

Accuracy and honesty hardening so the tool neither under-warns high-risk
projects nor asserts false "compliant" verdicts.

### Changed

- **Risk classification now inspects code content, not just file names.** Annex
  III / Art. 5 domain keywords are matched against the scanned project's file
  paths **and actual file content**, so an AI hiring or credit-scoring system is
  classified HIGH even when its files are plainly named (e.g. `app.py`).
  Previously classification effectively keyed off file/directory names only.
- **Domain classification is gated on real AI usage.** A project is only
  escalated to HIGH/UNACCEPTABLE when an AI provider or framework is actually
  detected — the EU AI Act governs AI systems, and this prevents false high-risk
  flags on projects that merely mention these domains. Test fixtures and
  documentation/config prose no longer drive classification (they are
  false-positive prone).
- **Article requirements are no longer marked "met" from documentation prose.**
  A requirement is **Met** only with a verifiable signal — a real code mechanism
  or a concrete artifact file. An obligation merely *referenced* in prose is now
  reported as a new **Unverified** state ("referenced, but not confirmed — verify
  manually"), never as compliant. This removes false compliance assurance (e.g.
  a README saying "conformity assessment" no longer marks Art. 43 as met).

### Added

- **Legal disclaimer on every output surface.** The "not legal advice" disclaimer
  now appears in the terminal, Markdown, JSON (`disclaimer` field), and CI output
  — previously it was only in the PDF/HTML.
- Art. 5(1)(b) exploitation-of-vulnerabilities to the prohibited-practice rules.
- Static type checking (`mypy`) in CI and the dev dependencies.

### Fixed

- The terminal "no issues" message no longer claims the project "looks
  compliant"; it states that static analysis found no gaps and is not a
  compliance determination.
- Deduplicated the path/format validation shared by `scan`, `recommend`, and
  `report`.
- Repointed the dead "Discussions" issue-template link (Discussions is disabled)
  and added the Python 3.13 trove classifier.
- Regenerated `examples/EXPECTED_OUTPUT.md` against a real 0.1.5 run and
  relabelled the Markdown summary (the default `scan` renders the boxed terminal
  report; the Markdown form is produced by `--ci` / `report --format markdown`).

## [0.1.4] - 2026-07-04

### Fixed

- **Correct EU AI Act article numbers in reports.** Conformity assessment is now
  reported as **Art. 43** (was Art. 7), provider obligations as **Art. 16** (was
  Art. 26), and distributor obligations as **Art. 24** (was Art. 28).
- **Requirement checks no longer pass on incidental substrings.** Doc/code
  keyword probes now match on word boundaries, so `auth` no longer satisfies the
  Art. 15 cybersecurity check via `__author__`, and a README that merely mentions
  "AI disclosure" (or says it is missing) no longer marks Art. 50 as met.
- **Art. 50 disclosure is judged from code, not prose** — "met" now requires an
  actual disclosure mechanism, and the gap is rated HIGH (was WARNING).
- **`recommend` no longer prints "nothing to recommend" when gaps exist** without
  a fix template; it now lists the affected articles.
- Corrected the README "What You'll See" and worked examples to match the actual
  boxed terminal report and the real risk behavior (HIGH comes only from an
  Annex III domain match; tool access alone does not raise the tier).
- De-contaminated `examples/sample-chatbot` (now only `app.py` +
  `requirements.txt`) so the scanner no longer ingests the sample's own docs,
  and regenerated `examples/EXPECTED_OUTPUT.md` against a real run (1 file, 4
  findings, 10 gaps, `tool_version` 0.1.4, Art. 50 correctly flagged).
- Marked `compliance_config.yaml` as a documentation-only artifact (the scanner
  does not read it yet).
- Fixed a per-detector line-split cache that could return a previous file's
  lines when a reused detector instance processed a later same-length file
  (CPython address reuse), misattributing findings; added a multi-file
  regression test.

### Added

- **Art. 5 prohibited-practices detection.** Projects matching a prohibited
  practice are classified **UNACCEPTABLE** with a blocking Art. 5 gap (previously
  the tier existed but was never assessed).
- Word-boundary keyword matching and a confidence floor for HIGH-risk
  classification (no longer reported at 0.25 confidence).
- `CHANGELOG.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `docs/ARCHITECTURE.md`,
  and GitHub issue/PR templates.
- PyPI `classifiers` and `[project.urls]` metadata; release process in
  `CONTRIBUTING.md`.
- Documented previously hidden flags: `scan --include`, `--no-color`,
  `--quiet`, `--verbose`, `--no-update-check`, and `recommend --format json`;
  documented the `NO_UPDATE_NOTIFIER` env var, scannable file types, and the
  1 MB file cap. Troubleshooting entries for Python 3.12+ install and for
  wrong-tier / false-negative detection.

### Changed

- Annex III keywords narrowed to specific multi-word phrases to cut false HIGH
  classifications from generic words (`student`, `electricity`, `voting`, …).
- HIGH-risk classification now notes the Art. 6(3) narrow-purpose exemption.
- Recommender framework→article mappings regrouped to defensible categories
  (oversight / record-keeping / documentation).
- Single shared filesystem probe per analysis (removes duplicated file reads);
  library warnings/errors now route through Rich and respect `--verbose`.
- `--version` short flag is now `-V` (was `-v`, which collided with `--verbose`).
- CI test matrix covers Python 3.12 and 3.13.

## [0.1.3] - 2026-07

### Added

- `--version` / `-v` top-level flag; version shown on bare invocation.

### Changed

- Uniform boxed terminal sections, consistent spacing, and a boxed "Next Steps"
  panel.

## [0.1.2]

### Added

- Update notifier: after a scan, reports when a newer version is on PyPI
  (cached daily, skipped in CI/JSON, opt-out via env var).
- `upgrade` command that auto-detects the install method (uv / pipx / pip).

### Fixed

- Installation and versioning hardening (single-source version via Hatch,
  bundled `templates/` and `rules/` in the wheel).

## [0.1.1]

### Changed

- Boxed Scan Summary and consistent section spacing in terminal output.

## [0.1.0]

### Added

- Initial release: AST-based scanner for AI providers (OpenAI, Anthropic,
  Mistral, Google, local runtimes), agent patterns, and framework detectors
  (LangChain, CrewAI, AutoGen, LangGraph).
- EU AI Act risk classification (Annex III) and per-article coverage/gap
  analysis.
- Fix recommender with copy-pasteable templates; terminal, Markdown, JSON, and
  PDF reports.

[Unreleased]: https://github.com/latreon/compliance-agent/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/latreon/compliance-agent/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/latreon/compliance-agent/compare/v0.1.9...v0.2.0
[0.1.9]: https://github.com/latreon/compliance-agent/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/latreon/compliance-agent/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/latreon/compliance-agent/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/latreon/compliance-agent/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/latreon/compliance-agent/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/latreon/compliance-agent/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.3
[0.1.2]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.2
[0.1.1]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.1
[0.1.0]: https://github.com/latreon/compliance-agent/releases/tag/v0.1.0
