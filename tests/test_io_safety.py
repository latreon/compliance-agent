"""Tests for the shared no-follow file-write helpers.

These exist specifically to verify the actual security property (a symlink
planted at the output path is refused, not silently followed) — the normal
write path is already exercised indirectly by test_pdf_reporter.py,
test_html_report.py, and test_mcp_server.py, but none of those assert the
symlink-rejection behavior itself.
"""

import pytest

from compliance_agent.io_safety import write_bytes_no_follow, write_text_no_follow


def test_write_text_no_follow_writes_normally(tmp_path):
    target = tmp_path / "report.html"
    write_text_no_follow(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_write_text_no_follow_overwrites_existing_file(tmp_path):
    target = tmp_path / "report.html"
    target.write_text("old", encoding="utf-8")
    write_text_no_follow(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_write_text_no_follow_refuses_symlink(tmp_path):
    real_target = tmp_path / "elsewhere.txt"
    real_target.write_text("do not touch", encoding="utf-8")
    link = tmp_path / "report.html"
    link.symlink_to(real_target)

    with pytest.raises(OSError):
        write_text_no_follow(link, "attacker-controlled content")

    # The symlink's real target must be untouched — the write must never
    # have followed through to it.
    assert real_target.read_text(encoding="utf-8") == "do not touch"


def test_write_bytes_no_follow_writes_normally(tmp_path):
    target = tmp_path / "report.pdf"
    write_bytes_no_follow(target, b"%PDF-1.7 fake")
    assert target.read_bytes() == b"%PDF-1.7 fake"


def test_write_bytes_no_follow_refuses_symlink(tmp_path):
    real_target = tmp_path / "elsewhere.bin"
    real_target.write_bytes(b"do not touch")
    link = tmp_path / "report.pdf"
    link.symlink_to(real_target)

    with pytest.raises(OSError):
        write_bytes_no_follow(link, b"attacker-controlled content")

    assert real_target.read_bytes() == b"do not touch"
