# ComplianceAgent v0.1.9 — Production Audit Report

**Date:** 2026-07-06
**Branch:** `fix/production-readiness-ship-blockers`
**Scope:** Full codebase audit — ~200 checks across 14 sections, executed by 7 parallel agents running real commands against fixture projects.

**Overall verdict: SHIP-WORTHY with fixes recommended.** All 185 tests pass, 93% coverage, zero crashes or hangs across every hostile fixture. 3 issues worth fixing before wide distribution; the rest are low-priority or cosmetic.

---

## Section Verdicts

| Section | Verdict | Notes |
|---|---|---|
| 1. Version / build integrity | **PASS** | All version strings 0.1.9, dynamic hatch version, wheel carries `templates/` + `rules/` |
| 2. CLI commands | **PASS w/ 1 bug** | Exit codes 0/1/2 correct everywhere; markdown format bug (#1) |
| 3. Scanner engine | **PASS** | Skip-dirs, gitignore, size caps, symlinks, BOM, dedup, corpus caps — all verified behaviorally |
| 4. Detectors | **PARTIAL** | Providers 20/20 pass incl. Groq-vs-OpenAI labeling; 3 false-negative gaps (#4–6) |
| 5. Risk classifier | **PASS** | All tiers, word boundaries, snake_case matching, prohibited-vs-high distinctions correct |
| 6. Article analyzers | **PASS w/ 1 deviation** | 25/26; Art 15 gating wrong (#2) |
| 7. Recommender | **PASS** | All 11 templates exist + compile; trigger map complete, no unmapped category |
| 8. Reporters | **PASS** | Injection defenses verified live (Rich markup, backticks, pipes, XSS in PDF) |
| 9. Models | **PASS** | All fields / enums / ordering as specified |
| 10. Edge cases / security | **PASS w/ 1 bug** | 24/25; ANSI filename injection (#3) |
| 11. Test suite | **PASS w/ 1 miss** | 185/185 pass; cli.py 89% vs 90% target — only threshold miss |
| 12. Integration e2e | **PASS** | Self-scan 4s, valid JSON envelope, 13 coverage entries, `scan_errors` empty, PDF 135KB valid |
| 13. Documentation | **PASS** | README flags match `--help` exactly; CHANGELOG 0.1.9 entry matches commits |
| 14. Cross-cutting | **PASS** | Update-check env gating, 24h cache, semver compare, install-method detection all correct |

---

## Issues to Fix (Ranked)

### 1. MEDIUM — `scan --format markdown` doesn't produce markdown
`cli.py` `scan()` has branches for pdf / json / ci / quiet / terminal but **none for markdown** — it falls through to the Rich terminal renderer. Users piping `--format markdown` to a `.md` file get box-drawing art, not markdown. `render_markdown()` is only reachable via the `report` subcommand. Confirmed independently by two agents.

**Fix:** add a markdown branch in `scan()` that calls `render_markdown()` when format is markdown (and honor `--output`, currently PDF-only on `scan`).

### 2. MEDIUM — Art 15 applies to all AI, not HIGH-risk only
`src/compliance_agent/analyzer/articles/art15.py:18-19` gates `applies()` on `has_ai()` instead of `is_high_risk`. A LIMITED-tier chatbot receives two HIGH-severity Art 15 gaps ("Error handling mechanisms required", "Cybersecurity measures required") citing statutory language. Art 15 (accuracy / robustness / cybersecurity) is a Chapter III Section 2 obligation for high-risk systems only. The identical reasoning is already documented in `art13.py:20-24` ("Previously it fired on any user-facing AI, overstating the obligation") — Art 15 was missed in that fix.

**Fix:** change the gate to `is_high_risk`, or downgrade severity/wording to advisory below HIGH.

### 3. Security, LOW-MEDIUM — ANSI escape injection via filenames in terminal report
A scanned repo containing a file named with a raw ESC byte (e.g. `evil\x1b[31mred.py`) emits that byte directly into the terminal report. Rich's `strip_control_codes` covers codes 7,8,11,12,13 but **not 27 (ESC)**. Since the tool's stated threat model is scanning untrusted repos, a hostile repo could recolor output, set the window title via OSC, or use cursor movement to overwrite rendered lines (e.g. spoof the displayed risk tier). JSON output is safe (``-escaped); PDF is safe (`html.escape`).

**Fix:** strip/replace C0 control chars in user-derived strings in `terminal.py` `build_findings` and `markdown.py` `_md_code`.

---

## Low-Priority Bugs

4. **snake_case agent filenames never detected** — `detectors/agents.py:35,130`: regex `\bagents?\b` applied to `Path.stem`; underscore is a word character, so `sales_agent.py`, `my_agents.py`, `agent_runner.py` never match. Only literal `agent.py` / `agents.py` fire. Contradicts the detector's own docstring (`agents.py:7-8`). Fix: `r"(^|_|\b)agents?(_|\b|$)"` or split stem on `_`.

5. **LangChain `AgentType` pattern missing** — `frameworks/langchain.py:21-27` has no `AgentType` entry. Low impact (usually co-occurs with `initialize_agent`).

6. **LangGraph `tools=` pattern missing** — `frameworks/langgraph.py:34` only covers `ToolNode` / `ToolExecutor`. Partially compensated by `AgentDetector`'s `agent:tool-calls`.

7. **MCP detector fires on prose** — `AgentDetector._detect_mcp` (`agents.py:72-83`) runs `mcp.server` / `.mcp.json` patterns against `.md` / `.yaml` / `.json` content, so a README documenting MCP setup yields `agent:mcp` findings. Inconsistent with the project's "prose is not behavior" precision rules. INFO only, does not escalate tier.

8. **`--severity` filter empty state misleads** — `reporter/terminal.py:233` prints "No AI usage patterns detected." when the filter removes all findings, even though AI *was* detected. Should say "No findings at or above `<severity>`".

9. **`--verbose` adds almost nothing** — enables INFO log level but the pipeline emits no INFO records, so it only prints one `Scanning <path> ...` line. Help text promises "extra detail about what was checked".

10. **Classifier precision — MINIMAL-0.6 tier nearly unreachable** — `patterns.py:33,121-131`: the bare token `chat` matches `client.chat.completions.create(...)`, the standard OpenAI SDK call. So "AI without user interaction → MINIMAL 0.6" effectively only triggers for projects that never call the chat-completions API; almost everything lands LIMITED 0.7. Conservative direction (over-assigns Art 50 transparency), but the tier branch is largely dead.

---

## Cosmetic / Documentation

- **PDF disclaimer hardcoded** in `pdf_report.py:381-382` + `templates/report.html:33` instead of importing the shared `DISCLAIMER` constant. Terminal / Markdown / JSON all use the constant; PDF wording can drift. The `__init__.py` comment ("the same disclaimer rides the terminal, Markdown, JSON, and PDF outputs") is therefore not literally true.
- **RECOMMENDATIONS.md and markdown report** emit every step as literal `1.` (relies on Markdown auto-renumber; raw-text readers see repeated "1.").
- **Stale docstring** in `json_report.py` shows `"tool_version": "0.1.0"` (actual 0.1.9).
- **`report` default output** lands in the current working directory; the success message prints only the relative filename, so users scanning another directory may not find it.
- **`--quiet` shows a Next Steps panel** after the disclaimer (spec said header + summary only). Likely intentional UX.
- **Coverage margins** — `cli.py` 89% (target ≥90, missing lines 99-106, 368-379, 417-428, mostly error branches); `updates.py` exactly at its 80% floor with no margin.
- **Nested `.gitignore` ignored** — only the root `.gitignore` is honored (documented in the engine docstring, but can surprise monorepo users). Conservative / FP-side only.
- **Self-scan covers 94 files** — the ECC subdirectory (11,412 files) is excluded via `.gitignore`, by design. Anyone expecting ECC to be audited should know it's excluded.

---

## What Passed Cleanly (Highlights)

- **No crashes anywhere** — BOM files, latin-1 bytes, syntax errors, empty files, 1MB+ files, unicode filenames, 80,000-deep nested parens, 900KB single-line files. Detector crashes are caught per-file and surfaced in `scan_errors` + a "Scan Warnings" panel.
- **No tier-escalation false positives** — comments, docstrings, test fixtures, `migrations/`, `risk_score`, `student`, comment mentioning "social scoring" — all correctly ignored even with a production `import openai` present.
- **Injection defenses hold** — markdown (backtick → `'`, pipe escaped), terminal (Rich markup rendered literally via `Text()`), PDF (`html.escape` on every user-derived interpolation; `<script>` filename verified inert).
- **Upgrade path injection-safe** — version regex (`^\d+\.\d+\.\d+$`) + list-form `subprocess.run` (no shell); `0.1.9; rm -rf /` rejected.
- **False-negative prevention works** — bedrock via `boto3.client("bedrock-runtime")`, new (`google.genai`) + legacy (`google.generativeai`) SDKs, langchain provider bindings, prompt-template string literals surviving comment-stripping.
- **Regex safety** — all detector/classifier regexes are linear (no nested quantifiers); no catastrophic backtracking under adversarial input.
- **Version/build integrity** — dynamic hatch version, wheel + sdist both carry `templates/` and `rules/`, JSON envelope `tool_version` matches `__version__`.

---

## Recommended Batching

- **Ship-blockers for next release:** #1, #2, #3
- **Follow-up:** #4–#10 and the cosmetic/doc items

---

## Resolution Log (fixes applied 2026-07-06)

All audited issues addressed except #10, which was left unchanged by design.

| # | Issue | Status | Fix |
|---|-------|--------|-----|
| 1 | `scan --format markdown` not markdown | **FIXED** | `cli.py` scan() now emits raw Markdown when piped or `--output` given; honors `--output` for Markdown. Interactive TTY still renders the Rich report. |
| 2 | Art 15 applies to all AI | **FIXED** | `art15.py` `applies()` now gates on `is_high_risk` (mirrors the Art 13 fix). Two tests updated to HIGH tier; added `test_art15_not_applicable_below_high_risk`. |
| 3 | ANSI escape injection via filenames | **FIXED** | `terminal.py` `_sanitize()` and `markdown.py` `_md_code`/`_plain` strip C0 control chars from all repo-derived strings. |
| 4 | snake_case agent filenames undetected | **FIXED** | `agents.py` `AGENT_STEM_REGEX` matches `sales_agent`, `my_agents`, etc. |
| 5 | LangChain `AgentType` missing | **FIXED** | Added `\bAgentType\b` to `langchain_agent` patterns. |
| 6 | LangGraph `tools=` missing | **FIXED** | Added `\btools\s*=\s*\[` to `langgraph_tools` patterns. |
| 7 | MCP detector fires on prose | **FIXED** | `agents.py` `_detect_mcp` runs code-signal regexes only on `.py` files; `.mcp.json` filename still detected anywhere. |
| 8 | `--severity` empty message misleading | **FIXED** | Terminal and Markdown reporters now say "No findings at or above the selected severity" when AI was detected but filtered out. |
| 9 | `--verbose` adds almost nothing | **FIXED** | `engine.scan()` and `cli.scan()` emit INFO logs (file count, detector count, findings/gaps, tier, scan errors). |
| 10 | `chat` matches `chat.completions` | **WON'T FIX (by design)** | Removing it would trade a *safe over-flag* (LIMITED → Art 50 transparency applies) for an *unsafe under-flag* (MINIMAL, obligation missed). For a compliance scanner, over-flagging is the correct conservative default, consistent with the tool's stated philosophy. |
| — | PDF disclaimer hardcoded | **FIXED** | `pdf_report.py` appendix now renders the shared `DISCLAIMER` constant. |
| — | RECOMMENDATIONS.md `1. 1. 1.` | **FIXED** | `markdown.py` numbers steps sequentially. |
| — | Stale `0.1.0` in json_report docstring | **FIXED** | Replaced with `<x.y.z>` placeholder. |
| — | `report` output path unclear | **FIXED** | Success message prints the resolved absolute path. |
| — | cli.py coverage 89% (< 90 target) | **FIXED** | Now 92% (added CLI + reporter tests). |

Left intentionally unchanged: `--quiet` Next Steps panel (deliberate UX), nested `.gitignore` (documented limitation), ECC subdir excluded from self-scan (by `.gitignore`, expected).

Post-fix state: **214 tests pass, 95% total coverage** (`cli.py` 92%, `terminal.py` 98%, `markdown.py` 99%), `ruff format --check` and `ruff check` both clean.

---

## Test & Coverage Snapshot

```
185 passed in 11.83s   (0 failures, 0 skips, 0 warnings)
Overall coverage: 93% (1929 stmts, 129 miss)

Module                        Cov    Target  Verdict
cli.py                        89%    >=90    FAIL (only miss)
scanner/engine.py             84%    >=80    PASS
scanner/parser.py            100%    >=90    PASS
detectors/providers.py        98%    >=90    PASS
detectors/agents.py           97%    >=90    PASS
detectors/patterns.py         92%    >=85    PASS
classifier/risk.py           100%    >=90    PASS
analyzer/gaps.py             100%    >=90    PASS
reporter/terminal.py          89%    >=85    PASS
reporter/markdown.py          99%    >=90    PASS
reporter/json_report.py      100%    ==100   PASS
reporter/pdf_report.py        97%    >=90    PASS
recommender/engine.py         96%    >=90    PASS
updates.py                    80%    >=80    PASS (at floor)
```
