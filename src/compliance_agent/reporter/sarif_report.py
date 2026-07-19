"""SARIF 2.1.0 report rendering for GitHub code scanning.

Emits a single-run SARIF log so findings and gaps show up in the GitHub
Security tab (via ``github/codeql-action/upload-sarif``) and in any other
SARIF consumer.

Mapping decisions:

- Findings map to per-file results at their detected line. Gaps are
  project-level obligations with no single source line, so they are anchored
  to a stable root file (pyproject.toml, package.json, README.md, ...) at
  line 1 — GitHub requires every result to carry a location to display it.
- Rule ids are derived from the detector/category (findings) or the gap id
  (gaps), NOT from the per-file finding id: SARIF rules describe a *class*
  of issue, and per-file ids would explode the rule table and break GitHub's
  deduplication across commits.
- ``security-severity`` follows GitHub's scoring bands (critical >= 9.0,
  high 7.0-8.9, medium 4.0-6.9, low < 4.0).
- Files that crashed a detector (``scan_errors``) become invocation
  ``toolExecutionNotifications`` and flip ``executionSuccessful`` to false,
  so an incomplete scan never reads as a clean one.
"""

import json
from pathlib import Path, PurePosixPath

from compliance_agent import DISCLAIMER, __version__
from compliance_agent.models.findings import ComplianceGap, Finding, ScanResult, Severity

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
INFO_URI = "https://github.com/latreon/compliance-agent"

# SARIF `level` per finding severity. SARIF has no "critical" level — that
# distinction is carried by the security-severity score below.
_LEVELS: dict[Severity, str] = {
    Severity.INFO: "note",
    Severity.WARNING: "warning",
    Severity.HIGH: "error",
    Severity.CRITICAL: "error",
}

# GitHub security-severity bands: critical >=9.0, high 7.0-8.9, medium 4.0-6.9.
_SECURITY_SEVERITY: dict[Severity, str] = {
    Severity.INFO: "2.0",
    Severity.WARNING: "5.0",
    Severity.HIGH: "8.0",
    Severity.CRITICAL: "9.5",
}

# Root files (in preference order) that can anchor project-level gap results.
_GAP_ANCHOR_CANDIDATES = (
    "pyproject.toml",
    "package.json",
    "README.md",
    "readme.md",
    "setup.py",
)


def _rule_id_for_finding(finding: Finding) -> str:
    """Stable per-class rule id: detector + category, path-free."""
    return f"finding.{finding.detector}.{finding.category}".replace(":", ".").replace("/", ".")


def _rule_id_for_gap(gap: ComplianceGap) -> str:
    return gap.id.replace(":", ".").replace("/", ".")


def _relative_uri(file_path: str) -> str:
    """Normalise a finding path to the forward-slash relative URI SARIF wants.

    Strips a literal leading ``./`` only — ``str.lstrip("./")`` would strip
    any leading run of ``.``/``/`` characters, corrupting dotfile paths like
    ``.github/workflows/ci.yml`` into ``github/workflows/ci.yml``.
    """
    posix = PurePosixPath(Path(file_path).as_posix()).as_posix()
    while posix.startswith("./"):
        posix = posix[2:]
    return posix or file_path


def _gap_anchor_uri(scan_result: ScanResult) -> str | None:
    """A stable existing file to anchor project-level gap results to.

    Prefers a well-known root manifest; falls back to the first scanned file
    that produced a finding. Returns None when nothing suitable exists (the
    result is then emitted without a location — valid SARIF, though GitHub
    may not display it).
    """
    project = Path(scan_result.project_path)
    for name in _GAP_ANCHOR_CANDIDATES:
        if (project / name).is_file():
            return name
    if scan_result.findings:
        return _relative_uri(scan_result.findings[0].file_path)
    return None


def _location(uri: str, line: int | None = None) -> dict:
    region = {"startLine": max(1, line or 1)}
    return {
        "physicalLocation": {
            "artifactLocation": {"uri": uri, "uriBaseId": "%SRCROOT%"},
            "region": region,
        }
    }


def _finding_rule(finding: Finding) -> dict:
    rule: dict = {
        "id": _rule_id_for_finding(finding),
        "name": finding.category.replace(":", "-"),
        "shortDescription": {"text": finding.message},
        "fullDescription": {"text": finding.description},
        "helpUri": INFO_URI,
        "defaultConfiguration": {"level": _LEVELS[finding.severity]},
        "properties": {
            "tags": ["compliance", "eu-ai-act"],
            "security-severity": _SECURITY_SEVERITY[finding.severity],
        },
    }
    if finding.article:
        rule["properties"]["article"] = finding.article
    if finding.suggestion:
        rule["help"] = {"text": finding.suggestion}
    return rule


def _gap_rule(gap: ComplianceGap) -> dict:
    return {
        "id": _rule_id_for_gap(gap),
        "name": gap.title,
        "shortDescription": {"text": f"{gap.article}: {gap.title}"},
        "fullDescription": {"text": gap.description},
        "helpUri": INFO_URI,
        "defaultConfiguration": {"level": _LEVELS[gap.severity]},
        "help": {"text": gap.recommendation},
        "properties": {
            "tags": ["compliance", "eu-ai-act", "gap"],
            "security-severity": _SECURITY_SEVERITY[gap.severity],
            "article": gap.article,
        },
    }


def _finding_result(finding: Finding, rule_index: int) -> dict:
    message = finding.message
    if finding.occurrences > 1:
        message = f"{message} ({finding.occurrences} occurrences in this file)"
    result: dict = {
        "ruleId": _rule_id_for_finding(finding),
        "ruleIndex": rule_index,
        "level": _LEVELS[finding.severity],
        "message": {"text": message},
        "locations": [_location(_relative_uri(finding.file_path), finding.line_number)],
        # The tool's own deterministic id: stable across runs on the same
        # tree, so consumers can correlate results between scans.
        "partialFingerprints": {"complianceAgentId": finding.id},
    }
    if finding.article:
        result["properties"] = {"article": finding.article}
    return result


def _gap_result(gap: ComplianceGap, rule_index: int, anchor_uri: str | None) -> dict:
    result: dict = {
        "ruleId": _rule_id_for_gap(gap),
        "ruleIndex": rule_index,
        "level": _LEVELS[gap.severity],
        "message": {
            "text": (
                f"{gap.article} ({gap.article_title}): {gap.title} — {gap.description} "
                f"Fix: {gap.recommendation}"
                if gap.article_title
                else f"{gap.article}: {gap.title} — {gap.description} Fix: {gap.recommendation}"
            )
        },
        "partialFingerprints": {"complianceAgentId": gap.id},
        "properties": {"article": gap.article, "status": gap.status},
    }
    if anchor_uri is not None:
        result["locations"] = [_location(anchor_uri)]
    return result


def _invocation(scan_result: ScanResult) -> dict:
    invocation: dict = {"executionSuccessful": not scan_result.scan_errors}
    if scan_result.scan_errors:
        invocation["toolExecutionNotifications"] = [
            {
                "level": "error",
                "message": {"text": f"File could not be fully analyzed: {error}"},
            }
            for error in scan_result.scan_errors
        ]
    return invocation


def build_sarif(scan_result: ScanResult) -> dict:
    """Build the SARIF 2.1.0 log dict for a scan result."""
    rules: list[dict] = []
    rule_index: dict[str, int] = {}
    results: list[dict] = []

    for finding in scan_result.findings:
        rule_id = _rule_id_for_finding(finding)
        if rule_id not in rule_index:
            rule_index[rule_id] = len(rules)
            rules.append(_finding_rule(finding))
        results.append(_finding_result(finding, rule_index[rule_id]))

    anchor_uri = _gap_anchor_uri(scan_result)
    for gap in scan_result.gaps:
        rule_id = _rule_id_for_gap(gap)
        if rule_id not in rule_index:
            rule_index[rule_id] = len(rules)
            rules.append(_gap_rule(gap))
        results.append(_gap_result(gap, rule_index[rule_id], anchor_uri))

    run: dict = {
        "tool": {
            "driver": {
                "name": "ComplianceAgent",
                "organization": "latreon",
                "informationUri": INFO_URI,
                "version": __version__,
                "rules": rules,
            }
        },
        "invocations": [_invocation(scan_result)],
        "results": results,
        # No result ever carries a startColumn/endColumn (see _location — line
        # only), so declaring columnKind here would assert a column-tracking
        # capability that does not exist. Per the SARIF spec, columnKind is
        # only meaningful when a region actually reports column values.
        "properties": {
            "riskTier": scan_result.risk_tier.value if scan_result.risk_tier else None,
            "filesScanned": scan_result.files_scanned,
            "disclaimer": DISCLAIMER,
        },
    }

    return {"$schema": SARIF_SCHEMA, "version": SARIF_VERSION, "runs": [run]}


def render_sarif(scan_result: ScanResult) -> str:
    """Serialize the scan result as a pretty-printed SARIF 2.1.0 log."""
    return json.dumps(build_sarif(scan_result), indent=2, ensure_ascii=False)
