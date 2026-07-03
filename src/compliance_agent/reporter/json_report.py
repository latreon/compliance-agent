"""JSON report rendering."""

from compliance_agent.models.findings import ScanResult


def render_json(scan_result: ScanResult) -> str:
    """Serialize the scan result to pretty-printed JSON."""
    return scan_result.model_dump_json(indent=2)
