"""Pydantic models for fix recommendations."""

from pydantic import BaseModel, Field


class FixRecommendation(BaseModel):
    """A concrete, actionable fix for a compliance gap."""

    rule_key: str  # e.g. "art50"
    title: str
    description: str
    article: str
    template_path: str  # repo-relative path, e.g. "art50/transparency_notice.py"
    template_content: str | None = None
    extra_templates: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    triggered_by: list[str] = Field(default_factory=list)  # finding/gap categories or ids
