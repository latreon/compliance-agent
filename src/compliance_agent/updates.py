"""Update checking and self-upgrade.

Two responsibilities, both fully optional and network-guarded:

- ``check_for_update`` — compares the running version against the latest on
  PyPI (cached for a day) and returns the newer version, or ``None``. Every
  failure path returns ``None`` so a scan is never broken or slowed by more
  than a short timeout, and it can be disabled entirely via env var.
- ``build_upgrade_command`` / ``run_upgrade`` — detect how the tool was
  installed (uv tool / pipx / pip) and run the right upgrade command.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from packaging.version import InvalidVersion, Version

from compliance_agent import __version__

PACKAGE = "compliance-agent"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PACKAGE}/json"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60
DEFAULT_TIMEOUT = 1.0


# ---------- version comparison ----------------------------------------------


def _version_key(version: str) -> tuple[int, ...]:
    """Best-effort numeric key for non-PEP-440 dotted version strings."""
    parts: list[int] = []
    for chunk in version.split("."):
        match = re.match(r"\d+", chunk)
        parts.append(int(match.group()) if match else 0)
    return tuple(parts)


def is_newer(candidate: str, current: str) -> bool:
    """True when ``candidate`` is a strictly newer version than ``current``.

    Uses PEP 440 ordering (via ``packaging``) so prereleases compare correctly
    — e.g. ``1.0.0`` is newer than ``1.0.0rc1``, and ``1.0.0rc1`` is *not*
    newer than the already-released ``1.0.0``. Falls back to a best-effort
    numeric comparison for strings that aren't valid PEP 440 versions.
    """
    try:
        return Version(candidate) > Version(current)
    except InvalidVersion:
        a, b = _version_key(candidate), _version_key(current)
        length = max(len(a), len(b))
        a += (0,) * (length - len(a))
        b += (0,) * (length - len(b))
        return a > b


def is_valid_version_spec(version: str) -> bool:
    """True for ``"latest"`` or any version string parseable as PEP 440.

    Used to allowlist what may be passed to the package manager in
    ``build_upgrade_command`` — includes prereleases (e.g. ``0.5.0rc1``) but
    rejects anything malformed (whitespace, shell metacharacters, garbage).
    """
    if version == "latest":
        return True
    try:
        Version(version)
    except InvalidVersion:
        return False
    return True


# ---------- disable switches -------------------------------------------------


def update_check_disabled() -> bool:
    """Respect common opt-out signals (explicit env var or CI environments)."""
    if os.environ.get("COMPLIANCE_AGENT_NO_UPDATE_CHECK"):
        return True
    if os.environ.get("NO_UPDATE_NOTIFIER"):
        return True
    return bool(os.environ.get("CI"))


# ---------- cache ------------------------------------------------------------


def _cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "compliance-agent" / "update-check.json"


def _read_cache() -> dict:
    try:
        return json.loads(_cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_cache(latest: str) -> None:
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"checked_at": time.time(), "latest": latest}),
            encoding="utf-8",
        )
    except OSError:
        pass  # cache is best-effort; never fail a scan over it


# ---------- PyPI lookup ------------------------------------------------------


def _fetch_latest(timeout: float) -> str | None:
    try:
        req = urllib.request.Request(PYPI_JSON_URL, headers={"User-Agent": PACKAGE})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https only)
            data = json.loads(resp.read().decode("utf-8"))
        version = data.get("info", {}).get("version")
        return version if isinstance(version, str) and version else None
    except Exception:
        # Any failure (offline, timeout, DNS, malformed) is non-fatal.
        return None


def latest_version(*, timeout: float = DEFAULT_TIMEOUT, force: bool = False) -> str | None:
    """Return the latest version on PyPI, using a day-long cache.

    Never raises. Returns the cached value when the network lookup fails.
    """
    cache = _read_cache()
    fresh = (time.time() - cache.get("checked_at", 0)) < CHECK_INTERVAL_SECONDS
    if not force and fresh and cache.get("latest"):
        return cache["latest"]

    fetched = _fetch_latest(timeout)
    if fetched:
        _write_cache(fetched)
        return fetched
    return cache.get("latest")


def check_for_update(current: str = __version__, *, timeout: float = DEFAULT_TIMEOUT) -> str | None:
    """Return the latest version if it is newer than ``current``, else None."""
    if update_check_disabled():
        return None
    latest = latest_version(timeout=timeout)
    if latest and is_newer(latest, current):
        return latest
    return None


# ---------- self-upgrade -----------------------------------------------------


def detect_install_method() -> str:
    """Best-effort detection of how this tool was installed: uv / pipx / pip."""
    markers = f"{Path(sys.prefix).resolve()}|{Path(sys.executable).resolve()}"
    if "uv/tools" in markers or "uv\\tools" in markers:
        return "uv"
    if "pipx" in markers:
        return "pipx"
    return "pip"


def build_upgrade_command(version: str = "latest") -> list[str]:
    """Build the correct upgrade command for the detected install method.

    ``version`` is either "latest" or a PEP 440 version string (validated by
    the caller via ``is_valid_version_spec``); the spec is only ever a fixed
    package name plus that version, and the command is run without a shell,
    so there is no injection surface.
    """
    latest = version == "latest"
    spec = PACKAGE if latest else f"{PACKAGE}=={version}"
    method = detect_install_method()

    if method == "uv" and shutil.which("uv"):
        if latest:
            return ["uv", "tool", "upgrade", PACKAGE]
        return ["uv", "tool", "install", "--force", spec]
    if method == "pipx" and shutil.which("pipx"):
        if latest:
            return ["pipx", "upgrade", PACKAGE]
        return ["pipx", "install", "--force", spec]
    return [sys.executable, "-m", "pip", "install", "--upgrade", spec]


def run_upgrade(version: str = "latest") -> int:
    """Run the upgrade command, returning its exit code."""
    cmd = build_upgrade_command(version)
    return subprocess.run(cmd, check=False).returncode
