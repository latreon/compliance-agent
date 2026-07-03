"""Tests for the fix recommender engine, rules, templates, and CLI commands."""

import json
import py_compile
from pathlib import Path

from typer.testing import CliRunner

from compliance_agent.analyzer.gaps import GapAnalyzer
from compliance_agent.classifier.risk import RiskClassifier
from compliance_agent.cli import app
from compliance_agent.models.findings import ScanResult
from compliance_agent.recommender.engine import FixRecommender
from compliance_agent.recommender.rules import FIX_RULES, TRIGGER_TO_RULE
from compliance_agent.scanner.engine import ScannerEngine

runner = CliRunner()

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def _analyzed_scan(project: Path) -> ScanResult:
    result = ScannerEngine(project).scan()
    assessment = RiskClassifier().classify(result)
    result = result.model_copy(update={"risk_tier": assessment.tier, "risk_assessment": assessment})
    return result.model_copy(update={"gaps": GapAnalyzer().analyze(result)})


# --- engine ---------------------------------------------------------------------


def test_recommends_fixes_for_agent_project(agent_project: Path) -> None:
    # agent_project: anthropic + tool calls, no logging -> art12 + art14 + art11
    result = _analyzed_scan(agent_project)
    recs = FixRecommender().recommend(result)
    rule_keys = {r.rule_key for r in recs}
    assert "art12" in rule_keys  # missing logging
    assert "art14" in rule_keys  # tool calls / oversight gap
    assert "art11" in rule_keys  # provider usage -> tech documentation


def test_no_recommendations_for_clean_project(clean_project: Path) -> None:
    result = _analyzed_scan(clean_project)
    assert FixRecommender().recommend(result) == []


def test_recommendations_deduplicate_by_rule(agent_project: Path) -> None:
    # Multiple triggers (gap + finding) for the same article -> one rec.
    result = _analyzed_scan(agent_project)
    recs = FixRecommender().recommend(result)
    rule_keys = [r.rule_key for r in recs]
    assert len(rule_keys) == len(set(rule_keys))
    art12 = next(r for r in recs if r.rule_key == "art12")
    assert len(art12.triggered_by) >= 2  # gap:record-keeping + pattern:missing-logging


def test_recommendation_includes_template_content(agent_project: Path) -> None:
    result = _analyzed_scan(agent_project)
    recs = FixRecommender().recommend(result)
    art12 = next(r for r in recs if r.rule_key == "art12")
    assert art12.template_content is not None
    assert "AILogger" in art12.template_content
    assert art12.steps


def test_export_copies_templates(agent_project: Path, tmp_path: Path) -> None:
    result = _analyzed_scan(agent_project)
    recommender = FixRecommender()
    recs = recommender.recommend(result)

    out = tmp_path / "fixes"
    written = recommender.export(recs, out)

    assert (out / "RECOMMENDATIONS.md").is_file()
    assert (out / "art12" / "event_logging.py").is_file()
    assert (out / "art14" / "human_oversight.py").is_file()
    assert all(p.exists() for p in written)


# --- rules and templates ----------------------------------------------------------


def test_every_rule_template_exists_and_is_readable() -> None:
    for rule_key, rule in FIX_RULES.items():
        for rel_path in [rule["template"], *rule["extra_templates"]]:
            template = TEMPLATES_DIR / rel_path
            assert template.is_file(), f"missing template for {rule_key}: {rel_path}"
            assert template.read_text(encoding="utf-8").strip(), f"empty template: {rel_path}"


def test_every_trigger_maps_to_known_rule() -> None:
    assert set(TRIGGER_TO_RULE.values()) <= set(FIX_RULES.keys())


def test_python_templates_compile() -> None:
    # Templates must be real working Python, not pseudocode.
    py_templates = list(TEMPLATES_DIR.rglob("*.py"))
    assert len(py_templates) >= 8
    for template in py_templates:
        py_compile.compile(str(template), doraise=True)


# --- CLI ---------------------------------------------------------------------------


def test_recommend_command_markdown_output(agent_project: Path) -> None:
    result = runner.invoke(app, ["recommend", str(agent_project)])
    assert result.exit_code == 0
    assert "Recommendations" in result.output
    assert "Art. 12" in result.output


def test_recommend_command_json_output(agent_project: Path) -> None:
    result = runner.invoke(app, ["recommend", str(agent_project), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "1.0"
    recommendations = payload["scan_result"]["recommendations"]
    assert recommendations
    keys = {rec["rule_key"] for rec in recommendations}
    assert "art12" in keys


def test_recommend_command_output_flag_copies_templates(
    agent_project: Path, tmp_path: Path
) -> None:
    out = tmp_path / "fixes"
    result = runner.invoke(app, ["recommend", str(agent_project), "--output", str(out)])
    assert result.exit_code == 0
    assert (out / "RECOMMENDATIONS.md").is_file()
    assert (out / "art12" / "event_logging.py").is_file()


def test_recommend_command_clean_project(clean_project: Path) -> None:
    result = runner.invoke(app, ["recommend", str(clean_project)])
    assert result.exit_code == 0
    assert "nothing to recommend" in result.output


def test_scan_fix_flag_includes_recommendations(agent_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(agent_project), "--fix"])
    assert result.exit_code == 0
    assert "Recommendations" in result.output


def test_scan_without_fix_flag_has_no_recommendations(agent_project: Path) -> None:
    result = runner.invoke(app, ["scan", str(agent_project), "--format", "json"])
    payload = json.loads(result.output)
    assert payload["scan_result"]["recommendations"] == []
