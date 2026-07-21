"""Shared no-follow file writes.

Every report writer (CLI, MCP server, and the web dashboard's PDF/HTML export)
eventually writes a caller-supplied output path. Between a caller resolving/
allowlist-checking that path and the actual write happening, something could
replace the path with a symlink (a TOCTOU race) — a plain ``write_bytes``/
``write_text`` would silently follow it and write through to wherever it
points. ``O_NOFOLLOW`` makes that open fail with ``ELOOP`` instead.

This only narrows the race (a fully closed check would need dir_fd-relative
opens through every path segment, not just the last one) and only matters
where a local attacker already has write access inside an allowlisted
directory — but it's free, so every report writer uses it consistently
rather than some paths getting the protection and others not.
"""

import os
from pathlib import Path


def write_bytes_no_follow(path: Path, data: bytes, mode: int = 0o644) -> None:
    """Write ``data`` to ``path`` without following a symlink at ``path``."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def write_text_no_follow(
    path: Path, content: str, encoding: str = "utf-8", mode: int = 0o644
) -> None:
    """Write ``content`` to ``path`` without following a symlink at ``path``."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w", encoding=encoding) as f:
        f.write(content)
