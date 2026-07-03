# Troubleshooting

Common problems and how to fix them. If none of these help, open an issue:
<https://github.com/latreon/compliance-agent/issues>

## "command not found: compliance-agent"

The tool isn't on your PATH. Any of these work:

```bash
# Option 1 — run it as a Python module (always works)
python -m compliance_agent scan .

# Option 2 — find where pip installed it, then add that folder to PATH
pip show compliance-agent          # look at the "Location" line
# add the neighboring Scripts/ (Windows) or bin/ (Linux/macOS) dir to PATH

# Option 3 — run from the project with uv
cd ~/Desktop/Playground/compliance-agent
uv run compliance-agent scan .
```

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

# See exactly what's being detected
compliance-agent scan . --verbose
```

## "Module not found" errors

The tool probably isn't installed:

```bash
pip install compliance-agent
```

Or, if you use `uv` from the project directory:

```bash
cd ~/Desktop/Playground/compliance-agent
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
