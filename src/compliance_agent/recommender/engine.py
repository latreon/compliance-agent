"""Fix recommender engine: maps scan results to concrete fix templates."""

import logging
import shutil
from pathlib import Path

from compliance_agent.models.findings import ScanResult
from compliance_agent.models.recommendations import FixRecommendation
from compliance_agent.recommender.rules import FIX_RULES, PROVIDER_RULE, TRIGGER_TO_RULE

logger = logging.getLogger(__name__)

# Presentation order: hardest obligations first.
RULE_ORDER = ["art9", "art12", "art14", "art50", "art10", "art11"]


def _default_templates_dir() -> Path:
    """Locate the packaged templates directory."""
    from compliance_agent import get_templates_dir

    return get_templates_dir()


class FixRecommender:
    """Generates fix recommendations for compliance gaps and findings."""

    def __init__(self, templates_dir: Path | None = None):
        self.templates_dir = Path(templates_dir) if templates_dir else _default_templates_dir()

    def recommend(self, scan_result: ScanResult) -> list[FixRecommendation]:
        """Generate deduplicated fix recommendations for a scan result.

        Triggers come from both analyzer gaps and detector findings; multiple
        triggers for the same article collapse into one recommendation.
        """
        triggers: dict[str, list[str]] = {}

        for gap in scan_result.gaps:
            # "Art. 12" -> "art12"; only articles with fix templates map.
            rule_key = "art" + "".join(ch for ch in gap.article if ch.isdigit())
            if rule_key in FIX_RULES:
                triggers.setdefault(rule_key, []).append(gap.id)

        for finding in scan_result.findings:
            if finding.category.startswith("provider:"):
                rule_key = PROVIDER_RULE
            else:
                rule_key = TRIGGER_TO_RULE.get(finding.category)
            if rule_key:
                triggers.setdefault(rule_key, []).append(finding.category)

        recommendations = [
            self._build(rule_key, sorted(set(trigger_ids)))
            for rule_key, trigger_ids in triggers.items()
        ]
        order = {key: idx for idx, key in enumerate(RULE_ORDER)}
        return sorted(recommendations, key=lambda r: order.get(r.rule_key, 99))

    def export(self, recommendations: list[FixRecommendation], output_dir: Path) -> list[Path]:
        """Copy the templates for the given recommendations into output_dir.

        Preserves the templates/ substructure and writes a RECOMMENDATIONS.md
        with the steps. Returns the list of written file paths.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        for rec in recommendations:
            for rel_path in [rec.template_path, *rec.extra_templates]:
                source = self.templates_dir / rel_path
                if not source.is_file():
                    logger.warning("Template missing, skipped: %s", source)
                    continue
                target = output_dir / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                written.append(target)

        instructions = output_dir / "RECOMMENDATIONS.md"
        instructions.write_text(self._instructions_markdown(recommendations), encoding="utf-8")
        written.append(instructions)
        return written

    def _build(self, rule_key: str, triggered_by: list[str]) -> FixRecommendation:
        rule = FIX_RULES[rule_key]
        template_path = self.templates_dir / rule["template"]
        template_content: str | None = None
        if template_path.is_file():
            template_content = template_path.read_text(encoding="utf-8")
        else:
            logger.warning("Template not found: %s", template_path)
        return FixRecommendation(
            rule_key=rule_key,
            title=rule["title"],
            description=rule["description"],
            article=rule["article"],
            template_path=rule["template"],
            template_content=template_content,
            extra_templates=list(rule["extra_templates"]),
            steps=list(rule["steps"]),
            triggered_by=triggered_by,
        )

    @staticmethod
    def _instructions_markdown(recommendations: list[FixRecommendation]) -> str:
        lines = ["# Fix Recommendations", ""]
        for idx, rec in enumerate(recommendations, start=1):
            lines.append(f"## {idx}. {rec.title} ({rec.article})")
            lines.append("")
            lines.append(rec.description)
            lines.append("")
            lines.append(f"**Template:** `{rec.template_path}`")
            if rec.extra_templates:
                extras = ", ".join(f"`{path}`" for path in rec.extra_templates)
                lines.append(f"**Also included:** {extras}")
            lines.append("")
            lines.append("**Steps:**")
            for step in rec.steps:
                lines.append(f"1. {step}")
            lines.append("")
        return "\n".join(lines)
