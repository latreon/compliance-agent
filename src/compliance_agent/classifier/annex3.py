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


def _bundled_rules_path() -> Path:
    """Locate annex3.yaml via the packaged rules directory."""
    from compliance_agent import get_rules_dir

    candidate = get_rules_dir() / "annex3.yaml"
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"annex3.yaml rules file not found. Expected at {candidate}.")


def load_categories(rules_path: Path | None = None) -> list[Annex3Category]:
    """Load and validate Annex III categories from YAML."""
    path = rules_path or _bundled_rules_path()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "categories" not in raw:
        raise ValueError(f"Malformed annex3 rules file: {path}")
    return [Annex3Category.model_validate(entry) for entry in raw["categories"]]
