"""Packaging tests: bundled resources must be reachable after import."""

import re

from compliance_agent import __version__, get_rules_dir, get_templates_dir


def test_version_is_set() -> None:
    # Assert a valid semver rather than a literal, so version bumps don't break the test.
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_templates_accessible() -> None:
    templates_dir = get_templates_dir()
    assert templates_dir.exists()
    assert (templates_dir / "art50" / "transparency_notice.py").exists()
    assert (templates_dir / "art12" / "event_logging.py").exists()


def test_rules_accessible() -> None:
    rules_dir = get_rules_dir()
    assert rules_dir.exists()
    assert (rules_dir / "annex3.yaml").exists()
