# Troubleshooting

Common problems and how to fix them. If none of these help, open an issue:
<https://github.com/latreon/compliance-agent/issues>

## "command not found: compliance-agent"

The tool isn't on your PATH yet. Fix depends on how you installed it:

```bash
# Installed with uv tool:
uv tool update-shell        # then open a new terminal tab

# Installed with pipx:
pipx ensurepath             # then open a new terminal tab

# Any install — run it as a module instead:
python -m compliance_agent scan .
```

## Install fails: "requires a different Python" / "no matching distribution"

ComplianceAgent needs **Python 3.12 or newer**. Many systems still ship 3.10 or
3.11. Check your version:

```bash
python3 --version
```

If it's below 3.12, install a newer Python and point your installer at it:

```bash
# uv can fetch and pin a Python for the tool:
uv python install 3.12
uv tool install --python 3.12 compliance-agent

# pipx:
pipx install --python python3.12 compliance-agent

# venv (use a 3.12+ interpreter explicitly):
python3.12 -m venv .venv && source .venv/bin/activate
pip install compliance-agent
```

On macOS: `brew install python@3.12`. On Debian/Ubuntu: use `deadsnakes` or
`uv python install 3.12`.

## "No such file or directory" when scanning

You're probably not in the folder you think you are:

```bash
pwd                                     # Where am I?
ls                                      # What's here?
compliance-agent scan .                 # Scan the current folder
compliance-agent scan /path/to/project  # Or scan a specific folder
```

## PDF generation fails

PDF output uses WeasyPrint, which needs system libraries.

**macOS:**

```bash
brew install pango
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```

**Ubuntu / Debian:**

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0
```

**Still failing?** Skip PDF — use markdown or JSON instead:

```bash
compliance-agent scan . --format markdown
compliance-agent scan . --format json
```

## Too many findings (false positives)

The scanner may be flagging code you don't need to check. Narrow it down:

```bash
# Skip test files
compliance-agent scan . --exclude "tests/*"

# Only show serious issues
compliance-agent scan . --severity high

# See exactly what is being detected
compliance-agent scan . --verbose
```

## Wrong risk tier, or my AI usage wasn't detected

The scanner reads code statically (AST + patterns), so it can miss things:

- **Risk tier looks too low.** The tool only assigns **HIGH** when your code
  matches an [Annex III](https://github.com/latreon/compliance-agent/blob/main/rules/annex3.yaml)
  high-risk domain by keyword. Agentic patterns alone (tools, multi-agent) raise
  oversight/logging *gaps* but do not by themselves make the tier HIGH. If you
  operate in a high-risk domain, treat the tier as a floor, not a verdict, and
  self-assess.
- **Banned (Art. 5) practices are never flagged.** `UNACCEPTABLE` is not
  auto-detected — that's a legal determination. Self-assess against Article 5.
- **My provider wasn't detected.** Only `.py/.yaml/.yml/.json/.toml/.md` files
  under 1 MB are scanned, `.gitignore` is honored, and only known providers
  (OpenAI, Anthropic, Mistral, Google `google.generativeai`, and local runtimes)
  are matched. Newer SDK import paths may be missed — please
  [open an issue](https://github.com/latreon/compliance-agent/issues) with the
  import you expected to be caught.

This tool is a technical aid, not legal advice — see the README disclaimer.

## "Module not found" errors

The tool probably isn't installed. Install it as an isolated CLI tool:

```bash
uv tool install compliance-agent
# or:  pipx install compliance-agent
```

Working from a clone of the repo instead? Use uv from the project directory:

```bash
uv sync
uv run compliance-agent scan .
```

## Exit code 1 in CI/CD

This means the tool found issues at or above your `--fail-on` threshold — that's
the check working as intended. To fix:

```bash
# See what the issues are
compliance-agent scan .

# Fix them, then re-run the gate
compliance-agent scan . --ci --fail-on high
```

To run a scan without failing the build (report only), drop `--fail-on`:

```bash
compliance-agent scan .
```

## The scan is slow

Most projects finish in about 5 seconds. If yours is slow, you're probably
scanning large vendored folders:

```bash
compliance-agent scan . --exclude "node_modules/*" --exclude ".venv/*"
```

See what's taking time:

```bash
compliance-agent scan . --verbose
```

If it's still slow, please report it: <https://github.com/latreon/compliance-agent/issues>
