"""ComplianceAgent — EU AI Act compliance scanner for AI projects."""

from importlib import resources
from pathlib import Path

__version__ = "0.1.8"

# Shown on every report surface. A compliance scanner must never be mistaken for
# a legal determination, so the same disclaimer rides the terminal, Markdown,
# JSON, and PDF outputs — not just the PDF.
DISCLAIMER = (
    "This tool performs automated, heuristic technical analysis — not legal "
    "advice — and does not guarantee regulatory compliance. Results may include "
    "false positives and false negatives. Consult qualified legal counsel before "
    "relying on them."
)


def _resource_dir(name: str) -> Path:
    """Resolve a bundled resource directory.

    Installed wheels ship templates/ and rules/ inside the package
    (via hatch force-include). Development checkouts keep them at the
    repo root, so fall back to <repo>/<name> when the package-relative
    directory is absent.
    """
    package_dir = Path(str(resources.files("compliance_agent")))
    bundled = package_dir / name
    if bundled.is_dir():
        return bundled
    repo_level = package_dir.parents[1] / name  # src/compliance_agent -> repo root
    if repo_level.is_dir():
        return repo_level
    return bundled


def get_templates_dir() -> Path:
    """Get the fix templates directory path."""
    return _resource_dir("templates")


def get_rules_dir() -> Path:
    """Get the classification rules directory path."""
    return _resource_dir("rules")
