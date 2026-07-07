"""JSON report rendering.

Output envelope (stable contract for CI/CD consumers):

    {
      "schema_version": "1.0",        # bumped on breaking output changes
      "tool_name": "ComplianceAgent",  # producing tool
      "tool_version": "<x.y.z>",       # compliance_agent.__version__ that produced it
      "disclaimer": "...",             # not legal advice; heuristic analysis
      "scan_result": { ... }           # full scan result: findings, gaps, recommendations
    }
"""

import json

from compliance_agent import DISCLAIMER, __version__
from compliance_agent.models.findings import ScanResult

SCHEMA_VERSION = "1.0"
TOOL_NAME = "ComplianceAgent"


def build_envelope(scan_result: ScanResult) -> dict:
    """Build the versioned envelope dict shared by the JSON and HTML reporters."""
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_name": TOOL_NAME,
        "tool_version": __version__,
        "disclaimer": DISCLAIMER,
        "scan_result": scan_result.model_dump(mode="json"),
    }


def render_json(scan_result: ScanResult) -> str:
    """Serialize the scan result to a versioned, pretty-printed JSON envelope."""
    return json.dumps(build_envelope(scan_result), indent=2, ensure_ascii=False)
