"""Annex III category definitions loaded from rules/annex3.yaml."""

from pathlib import Path

import yaml
from pydantic import BaseModel


class Annex3Category(BaseModel):
    """One high-risk category from Annex III of the EU AI Act."""

    id: str
    name: str
    article: str
    keywords: list[str]


def _bundled_rules_path(filename: str = "annex3.yaml") -> Path:
    """Locate a rules YAML file via the packaged rules directory."""
    from compliance_agent import get_rules_dir

    candidate = get_rules_dir() / filename
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"{filename} rules file not found. Expected at {candidate}.")


def _load(path: Path) -> list[Annex3Category]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "categories" not in raw:
        raise ValueError(f"Malformed rules file: {path}")
    return [Annex3Category.model_validate(entry) for entry in raw["categories"]]


def load_categories(rules_path: Path | None = None) -> list[Annex3Category]:
    """Load and validate Annex III (high-risk) categories from YAML."""
    return _load(rules_path or _bundled_rules_path("annex3.yaml"))


def load_prohibited_categories(rules_path: Path | None = None) -> list[Annex3Category]:
    """Load and validate Article 5 prohibited-practice categories from YAML."""
    return _load(rules_path or _bundled_rules_path("prohibited.yaml"))
