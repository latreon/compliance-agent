"""JSON report rendering.

Output envelope (stable contract for CI/CD consumers):

    {
      "schema_version": "1.0",   # bumped on breaking output changes
      "tool_version": "0.1.0",   # compliance-agent version that produced it
      "scan_result": { ... }     # full scan result: findings, gaps, recommendations
    }
"""

import json

from compliance_agent import __version__
from compliance_agent.models.findings import ScanResult

SCHEMA_VERSION = "1.0"


def render_json(scan_result: ScanResult) -> str:
    """Serialize the scan result to a versioned, pretty-printed JSON envelope."""
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": __version__,
        "scan_result": scan_result.model_dump(mode="json"),
    }
    return json.dumps(envelope, indent=2, ensure_ascii=False)
