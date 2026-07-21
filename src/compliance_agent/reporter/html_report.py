"""Self-contained HTML dashboard export.

Renders the scan result into a single .html file: the dashboard UI (shared
with `compliance-agent serve`) with the JSON envelope embedded inline. No
network access, no external assets — the file can be attached to an email or
a ticket and opened anywhere.
"""

import json
from pathlib import Path

from compliance_agent.io_safety import write_text_no_follow
from compliance_agent.models.findings import ScanResult
from compliance_agent.reporter.json_report import build_envelope

_STATIC_DIR = Path(__file__).parent.parent / "web" / "static"

_STYLES_MARK = "<!--%STYLES%-->"
_SCRIPTS_MARK = "<!--%SCRIPTS%-->"
_DATA_MARK = "<!--%DATA%-->"


def _embed_json(envelope: dict) -> str:
    """Serialize the envelope for inline <script> embedding.

    `</` is escaped so a scanned file named e.g. `</script><script>…` cannot
    close the data block and inject markup into its own compliance report;
    U+2028/U+2029 are escaped because they are line terminators in JavaScript
    source but not in JSON.
    """
    text = json.dumps(envelope, ensure_ascii=False)
    text = text.replace("</", "<\\/")
    return text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render_html(scan_result: ScanResult) -> str:
    """Render the scan result as a self-contained HTML dashboard."""
    template = (_STATIC_DIR / "dashboard.html").read_text(encoding="utf-8")
    css = (_STATIC_DIR / "dashboard.css").read_text(encoding="utf-8")
    js = (_STATIC_DIR / "dashboard.js").read_text(encoding="utf-8")
    data = _embed_json(build_envelope(scan_result))
    return (
        template.replace(_STYLES_MARK, f"<style>\n{css}\n</style>")
        .replace(_DATA_MARK, f"<script>window.__SCAN_DATA__ = {data};</script>")
        .replace(_SCRIPTS_MARK, f"<script>\n{js}\n</script>")
    )


def write_html(scan_result: ScanResult, output_path: Path | None = None) -> Path:
    """Write the HTML dashboard to disk. Returns the output path."""
    if output_path is None:
        project_name = Path(scan_result.project_path).name or "project"
        output_path = Path(f"compliance-dashboard-{project_name}.html")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_no_follow(output_path, render_html(scan_result))
    return output_path
