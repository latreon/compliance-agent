"""Sanity checks for the GitHub Action metadata (action.yml).

The real end-to-end run happens in CI (the ``action-test`` job uses the local
action via ``uses: ./``); these tests catch metadata regressions that would
only surface after publishing to the Marketplace.
"""

from pathlib import Path

import yaml

ACTION_FILE = Path(__file__).parent.parent / "action.yml"


def _load() -> dict:
    return yaml.safe_load(ACTION_FILE.read_text(encoding="utf-8"))


def test_action_file_exists_and_parses() -> None:
    action = _load()
    assert action["name"] == "EU AI Act Compliance Scan"
    assert action["runs"]["using"] == "composite"


def test_action_has_marketplace_branding() -> None:
    # Marketplace listing requires name, description, and branding.
    action = _load()
    assert action["description"]
    assert action["branding"]["icon"] == "shield"
    assert action["branding"]["color"] == "blue"


def test_action_inputs_have_safe_defaults() -> None:
    inputs = _load()["inputs"]
    assert inputs["path"]["default"] == "."
    assert inputs["format"]["default"] == "sarif"
    assert inputs["output"]["default"] == "compliance-results.sarif"
    # fail-on defaults to empty: the action reports by default, gates on opt-in.
    assert inputs["fail-on"]["default"] == ""


def test_action_exposes_report_output() -> None:
    action = _load()
    assert "report" in action["outputs"]


def test_action_scan_step_shields_inputs_behind_env() -> None:
    # Inputs must reach the shell via env vars, never inline interpolation —
    # inline `${{ inputs.x }}` inside `run:` is a shell-injection vector.
    steps = _load()["runs"]["steps"]
    scan_step = next(s for s in steps if s.get("id") == "scan")
    assert "${{ inputs" not in scan_step["run"]
    assert scan_step["env"]["CA_PATH"] == "${{ inputs.path }}"
