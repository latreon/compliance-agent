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

All three must pass before a PR — CI enforces them.

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

- New detector patterns (framework-specific: LangChain, LlamaIndex, Haystack)
- Additional templates for other articles
- Config file support (`compliance.yaml`)
- Documentation improvements
