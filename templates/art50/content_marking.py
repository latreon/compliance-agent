"""
EU AI Act Article 50(2) — Machine-Readable Marking of AI-Generated Content
Requirement: Providers of AI systems generating synthetic text, audio, image,
or video must mark outputs as artificially generated in a machine-readable way.

Usage: Wrap outbound AI content with mark_* helpers before storing or serving.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

# Standard marker fields. Keep the key names stable so downstream systems
# (crawlers, moderation pipelines, other AI systems) can rely on them.
MARKER_SCHEMA_VERSION = "1.0"


@dataclass
class AIContentMarker:
    """Machine-readable provenance record attached to AI-generated content."""

    generator: str  # e.g. "gpt-4o", "claude-sonnet-5", "my-fine-tune-v2"
    provider: str  # e.g. "openai", "anthropic", "self-hosted"
    generated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    schema_version: str = MARKER_SCHEMA_VERSION
    ai_generated: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def mark_json_payload(content: dict, marker: AIContentMarker) -> dict:
    """Embed the marker in a JSON API payload under a reserved key.

    Returns a new dict — the original payload is not mutated.
    """
    return {**content, "_ai_provenance": marker.to_dict()}


def mark_text(text: str, marker: AIContentMarker) -> str:
    """Append a machine-readable marker line to plain text content.

    The marker is a single line starting with `[AI-GENERATED]` followed by a
    compact JSON record, so both humans and parsers can detect it.
    """
    record = json.dumps(marker.to_dict(), separators=(",", ":"))
    return f"{text}\n\n[AI-GENERATED] {record}"


def mark_html(html: str, marker: AIContentMarker) -> str:
    """Inject meta tags flagging AI-generated content into an HTML document.

    Adds `<meta name="ai-generated" ...>` inside <head> when present, else
    prepends a comment block.
    """
    meta = (
        f'<meta name="ai-generated" content="true">\n'
        f'<meta name="ai-generator" content="{marker.generator}">\n'
        f'<meta name="ai-generated-at" content="{marker.generated_at}">'
    )
    if "<head>" in html:
        return html.replace("<head>", f"<head>\n{meta}", 1)
    return f"<!-- {meta} -->\n{html}"


def http_marker_headers(marker: AIContentMarker) -> dict[str, str]:
    """HTTP response headers marking a response body as AI-generated.

    Merge into your framework's response headers:
        response.headers.update(http_marker_headers(marker))
    """
    return {
        "X-AI-Generated": "true",
        "X-AI-Generator": marker.generator,
        "X-AI-Provider": marker.provider,
        "X-AI-Generated-At": marker.generated_at,
    }


if __name__ == "__main__":
    marker = AIContentMarker(generator="gpt-4o", provider="openai")
    print(mark_text("The quarterly summary shows steady growth.", marker))
    print(json.dumps(mark_json_payload({"answer": "42"}, marker), indent=2))
