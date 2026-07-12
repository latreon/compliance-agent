"""Tests for the compliance.yaml project config loader and its wiring."""

from pathlib import Path

import pytest

from compliance_agent.config import (
    CONFIG_FILENAMES,
    ConfigError,
    find_config_file,
    load_config,
)
from compliance_agent.models.findings import RiskAssessment, RiskTier, Severity
from compliance_agent.pipeline import apply_declared_tier, run_pipeline


@pytest.fixture
def project(openai_project: Path) -> Path:
    """The shared OpenAI sample project (LIMITED tier, warning-level gaps)."""
    return openai_project


# ---------- loading & validation ----------------------------------------


def test_no_config_file_returns_none(project: Path) -> None:
    assert load_config(project) is None
    assert find_config_file(project) is None


def test_loads_full_config(project: Path) -> None:
    (project / "compliance.yaml").write_text(
        """
version: 1
posture:
  risk_tier: high
  intended_purpose: "CV screening assistant"
scan:
  exclude: ["docs/*"]
  include: []
  fail_on: high
  severity: warning
  format: json
  output: report.json
"""
    )
    config = load_config(project)
    assert config is not None
    assert config.posture.risk_tier == RiskTier.HIGH
    assert config.posture.intended_purpose == "CV screening assistant"
    assert config.scan.exclude == ["docs/*"]
    assert config.scan.fail_on == Severity.HIGH
    assert config.scan.severity == Severity.WARNING
    assert config.scan.format == "json"
    assert config.scan.output == "report.json"
    assert config.source_path == project / "compliance.yaml"


def test_empty_config_file_is_all_defaults(project: Path) -> None:
    (project / "compliance.yaml").write_text("")
    config = load_config(project)
    assert config is not None
    assert config.posture.risk_tier is None
    assert config.scan.exclude == []


@pytest.mark.parametrize("name", CONFIG_FILENAMES)
def test_all_candidate_filenames_are_found(project: Path, name: str) -> None:
    (project / name).write_text("version: 1\n")
    found = find_config_file(project)
    assert found is not None and found.name == name


def test_invalid_yaml_is_a_hard_error(project: Path) -> None:
    (project / "compliance.yaml").write_text("scan: [unclosed")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(project)


def test_unknown_key_is_a_hard_error(project: Path) -> None:
    # A typo like `fail-on:` (hyphen) must not silently disable a CI gate.
    (project / "compliance.yaml").write_text("scan:\n  fail-on: high\n")
    with pytest.raises(ConfigError, match="fail-on"):
        load_config(project)


def test_invalid_severity_value_is_a_hard_error(project: Path) -> None:
    (project / "compliance.yaml").write_text("scan:\n  fail_on: hihg\n")
    with pytest.raises(ConfigError, match="fail_on"):
        load_config(project)


def test_non_mapping_root_is_a_hard_error(project: Path) -> None:
    (project / "compliance.yaml").write_text("- just\n- a\n- list\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(project)


def test_unsupported_version_is_a_hard_error(project: Path) -> None:
    (project / "compliance.yaml").write_text("version: 2\n")
    with pytest.raises(ConfigError, match="version 2"):
        load_config(project)


# ---------- declared-tier semantics --------------------------------------


def _assessment(tier: RiskTier) -> RiskAssessment:
    return RiskAssessment(tier=tier, confidence=0.6, reasoning=["heuristic"])


def test_declared_tier_raises_detected_tier() -> None:
    raised = apply_declared_tier(_assessment(RiskTier.LIMITED), RiskTier.HIGH)
    assert raised.tier == RiskTier.HIGH
    assert raised.confidence == 1.0
    assert any("compliance.yaml" in line for line in raised.reasoning)


def test_declared_tier_never_lowers_detected_tier() -> None:
    # A config file must not be able to talk the scanner down a tier.
    kept = apply_declared_tier(_assessment(RiskTier.HIGH), RiskTier.MINIMAL)
    assert kept.tier == RiskTier.HIGH
    assert any("higher tier applies" in line for line in kept.reasoning)


def test_declared_tier_equal_is_a_noop() -> None:
    same = apply_declared_tier(_assessment(RiskTier.LIMITED), RiskTier.LIMITED)
    assert same.tier == RiskTier.LIMITED
    assert same.reasoning == ["heuristic"]


def test_pipeline_applies_declared_tier(project: Path) -> None:
    baseline = run_pipeline(project)
    assert baseline.risk_tier == RiskTier.LIMITED  # plain chatbot, no Annex III domain

    declared = run_pipeline(project, declared_tier=RiskTier.HIGH)
    assert declared.risk_tier == RiskTier.HIGH
    # Raising the tier must also unlock the high-risk article analyzers.
    assert len(declared.gaps) > len(baseline.gaps)


# ---------- CLI integration ----------------------------------------------


def test_cli_uses_config_scan_defaults(project: Path) -> None:
    from typer.testing import CliRunner

    from compliance_agent.cli import app

    (project / "compliance.yaml").write_text("scan:\n  format: json\n")
    result = CliRunner().invoke(app, ["scan", str(project)])
    assert result.exit_code == 0
    assert '"schema_version"' in result.output  # config's json format was used


def test_cli_flag_overrides_config(project: Path) -> None:
    from typer.testing import CliRunner

    from compliance_agent.cli import app

    (project / "compliance.yaml").write_text("scan:\n  format: json\n")
    result = CliRunner().invoke(app, ["scan", str(project), "--format", "sarif"])
    assert result.exit_code == 0
    assert '"2.1.0"' in result.output  # SARIF, not the config's json


def test_cli_broken_config_exits_2(project: Path) -> None:
    from typer.testing import CliRunner

    from compliance_agent.cli import app

    (project / "compliance.yaml").write_text("scan: [unclosed")
    result = CliRunner().invoke(app, ["scan", str(project)])
    assert result.exit_code == 2
    assert "Config error" in result.output


def test_cli_config_fail_on_gates_the_run(project: Path) -> None:
    from typer.testing import CliRunner

    from compliance_agent.cli import app

    # The fixture project is LIMITED-tier with warning-level gaps, so a
    # config-declared warning gate must trip without any CLI flag.
    (project / "compliance.yaml").write_text("scan:\n  fail_on: warning\n")
    result = CliRunner().invoke(app, ["scan", str(project), "--ci"])
    assert result.exit_code == 1


def test_cli_config_declared_tier_raises_scan_tier(project: Path) -> None:
    from typer.testing import CliRunner

    from compliance_agent.cli import app

    (project / "compliance.yaml").write_text("posture:\n  risk_tier: high\n")
    result = CliRunner().invoke(app, ["scan", str(project), "--format", "json"])
    assert result.exit_code == 0
    assert '"risk_tier": "high"' in result.output
