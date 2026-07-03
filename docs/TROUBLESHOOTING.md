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
