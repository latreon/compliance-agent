# Contributing to ComplianceAgent

Thanks for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/latreon/compliance-agent.git
cd compliance-agent
uv sync
```

## Running Tests

```bash
uv run pytest                 # full suite with coverage
uv run ruff check src tests   # lint
uv run ruff format src tests  # format
```

All three must pass before a PR — CI enforces them. Coverage is reported by
`pytest-cov`; keep new code covered (aim for parity with the existing suite —
new detectors, templates, and articles ship with tests).

## Project Layout

The pipeline runs scan → classify → analyze gaps → recommend → report:

- `scanner/` — file walking + `detectors/` (providers, agent patterns,
  framework-specific detectors under `detectors/frameworks/`)
- `classifier/` — risk tier from Annex III keyword matching (`risk.py`,
  `annex3.py`)
- `analyzer/articles/` — one module per EU AI Act article, producing coverage +
  gaps
- `recommender/` — maps findings/gaps to `templates/` fixes
- `reporter/` — terminal, markdown, json, pdf renderers

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full data flow and how
risk tiers are decided.

## Branching & PRs

- Branch from `main`; keep PRs focused.
- Conventional commit titles (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Green CI (tests + lint + format) is required before review.

## Regenerating example fixtures

`examples/EXPECTED_OUTPUT.md` and `examples/SAMPLE_PDF_REPORT.md` are
hand-maintained snapshots of real output. If scanner or reporter output changes,
regenerate and update them:

```bash
uv run compliance-agent scan examples/sample-chatbot
uv run compliance-agent report examples/sample-chatbot --format markdown --output /tmp/report.md
```

## Releasing (maintainers)

The version is single-sourced from `src/compliance_agent/__init__.py`
(`__version__`) via Hatch — there is no separate version string to bump.

1. Bump `__version__` in `src/compliance_agent/__init__.py` (semver).
2. Update `CHANGELOG.md` (move Unreleased → the new version + date).
3. Update the pinned `rev:` in the README pre-commit example and any
   `v<version>` references.
4. Commit (`release: vX.Y.Z`), tag `vX.Y.Z`, and push the tag.
5. Build and publish: `uv build` then `uv publish` (or `python -m build` +
   `twine upload dist/*`).
6. Verify: `uv tool install compliance-agent && compliance-agent version`.

## Adding New Detectors

1. Create a new file in `src/compliance_agent/scanner/detectors/`
2. Extend `BaseDetector` and implement `analyze(file_path, content)`
3. Register the class in `ALL_DETECTORS` (`scanner/detectors/__init__.py`)
4. Add precision tests in `tests/test_detectors.py` — cover **both** true
   positives (real AI code fires) and false positives (similar-looking
   non-AI code stays silent)

Precision rules to keep:
- Use AST for Python where possible; provider names in comments, docstrings,
  and strings must not match
- Generic words (`agent`, `chat`, `query`) need AI context gating via
  `detect_ai_imports()`

## Adding New Templates

1. Create the template in `templates/<article>/`
2. Add or extend a rule in `src/compliance_agent/recommender/rules.py`
3. Templates must be real, runnable Python — `tests/test_recommender.py`
   compile-checks every `.py` template
4. Update `templates/README.md` index

## Code Style

- Ruff for linting and formatting (line length 100)
- Type hints required
- Docstrings for public functions
- Tests for new features
- Conventional commit messages (`feat:`, `fix:`, `docs:`, ...)

## Priority Areas

- New framework detectors (e.g. PydanticAI, OpenAI Agents SDK, Mastra — not
  yet covered; see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the
  current list)
- Additional templates for other articles
- Documentation improvements
