"""Tests for the ProjectProbe code scan (Python + JS/TS) and term matching."""

from pathlib import Path

from compliance_agent.analyzer.articles.base import ProjectProbe


def test_code_text_includes_typescript_files(tmp_path: Path) -> None:
    (tmp_path / "banner.tsx").write_text(
        'export const notice = "You are interacting with an AI";\n'
    )

    probe = ProjectProbe(tmp_path)

    assert "you are interacting with an ai" in probe.code_text


def test_code_mentions_text_phrase_in_typescript(tmp_path: Path) -> None:
    (tmp_path / "Banner.tsx").write_text(
        "export function Banner() { return <div>You are interacting with an AI</div>; }\n"
    )

    probe = ProjectProbe(tmp_path)

    assert probe.code_mentions("you are interacting with an ai")


def test_code_mentions_matches_camelcase_js_identifier(tmp_path: Path) -> None:
    # A TS kill switch written as camelCase must satisfy a snake_case probe term.
    (tmp_path / "oversight.ts").write_text("export function killSwitch() { stop(); }\n")

    probe = ProjectProbe(tmp_path)

    assert probe.code_mentions("kill_switch")


def test_code_mentions_matches_kebab_case_header(tmp_path: Path) -> None:
    (tmp_path / "mw.ts").write_text('res.setHeader("X-AI-Disclosure", "1");\n')

    probe = ProjectProbe(tmp_path)

    # "x-ai-disclosure" already matches verbatim; "ai_disclosure" should match
    # the kebab form via separator-flexible matching.
    assert probe.code_mentions("ai_disclosure")


def test_snake_case_still_matches_in_python(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def human_in_the_loop():\n    return approve()\n")

    probe = ProjectProbe(tmp_path)

    assert probe.code_mentions("human_in_the_loop")


def test_js_line_comment_is_stripped(tmp_path: Path) -> None:
    # A term that only appears in a JS comment must not count as a real mechanism.
    (tmp_path / "note.ts").write_text("// TODO: add killSwitch later\nexport const x = 1;\n")

    probe = ProjectProbe(tmp_path)

    assert not probe.code_mentions("kill_switch")


def test_camelcase_flex_does_not_over_match_unrelated_words(tmp_path: Path) -> None:
    # Separator flexibility must not make "kill_switch" match unrelated tokens.
    (tmp_path / "a.ts").write_text("export const killProcess = true; const mainSwitch = 2;\n")

    probe = ProjectProbe(tmp_path)

    assert not probe.code_mentions("kill_switch")


def test_art50_disclosure_met_by_typescript_mechanism(tmp_path: Path) -> None:
    """End to end: a TS AI-disclosure construct satisfies Art. 50, no gap raised."""
    from datetime import datetime

    from compliance_agent.analyzer.articles.art50 import Art50Analyzer
    from compliance_agent.analyzer.articles.base import ProjectProbe
    from compliance_agent.models.findings import (
        Finding,
        RiskTier,
        ScanResult,
        Severity,
    )

    (tmp_path / "chat.tsx").write_text(
        'export const aiDisclosure = "You are interacting with an AI";\n'
        "export function Chat() { return useChat(); }\n"
    )

    # Findings that make has_ai() and has_user_interaction() true so Art. 50 applies.
    findings = [
        Finding(
            id="1",
            file_path="chat.tsx",
            detector="providers",
            severity=Severity.INFO,
            category="provider:openai",
            message="m",
            description="d",
        ),
        Finding(
            id="2",
            file_path="chat.tsx",
            detector="patterns",
            severity=Severity.INFO,
            category="pattern:chat-interface",
            message="m",
            description="d",
        ),
    ]
    result = ScanResult(
        project_path=str(tmp_path),
        findings=findings,
        scan_time=datetime(2026, 1, 1, 12, 0, 0),
        risk_tier=RiskTier.LIMITED,
    )
    probe = ProjectProbe(tmp_path)

    gaps = Art50Analyzer().analyze(result, probe)

    assert not any(g.title == "AI interaction disclosure required" for g in gaps)
