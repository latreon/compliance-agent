"""Best-effort dependency-version detection from project manifests.

Reads the dependency manifests at a project root (``requirements.txt``,
``pyproject.toml``, ``package.json``) and returns a map of normalized package
name -> declared version. Used to populate ``FrameworkDetection.version`` so a
detected AI framework can report which version the project pins.

Everything here is best-effort: a missing, unreadable, or malformed manifest
degrades to "no version known" and must never crash a scan. Versions are taken
verbatim from what the project declares — this reports the *declared* pin, not
the installed/resolved version.
"""

import json
import logging
import re
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

# Cap manifest reads: a manifest far larger than this is almost certainly not a
# real dependency file, and we never want to stream an unbounded file here.
_MAX_MANIFEST_BYTES = 500_000

# First version-looking token in a PEP 508 / semver specifier: a digit run,
# then dot/hyphen-joined alphanumerics (captures "0.2.5", "0.30", "3.1.0-beta").
_VERSION_RE = re.compile(r"\d[\dA-Za-z.\-]*")
# Leading package name in a requirement line (before any extras or specifier).
_REQ_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")

# Framework detector name -> candidate manifest package keys, Python package
# first so a project that pins both the Python and the npm package reports the
# Python version. Keys are matched against the normalized version map.
FRAMEWORK_PACKAGES: dict[str, tuple[str, ...]] = {
    "langchain": ("langchain", "langchain-core"),
    "langgraph": ("langgraph", "@langchain/langgraph"),
    "crewai": ("crewai",),
    "autogen": ("autogen-agentchat", "pyautogen", "autogen", "autogen-core"),
    "vercel-ai-sdk": ("ai",),
}


def _normalize_py_name(name: str) -> str:
    """PEP 503 normalization: lowercase, runs of -_. collapse to a single -."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


# Markers of a URL / VCS / local-path dependency, which carries no clean
# version — extracting the "first digit run" from one yields a commit hash or
# path fragment (e.g. "git+https://.../repo.git#a1b2c3d" -> "1b2c3d").
_NON_VERSION_MARKERS = ("://", "git+", "file:")


def _first_version(spec: str) -> str | None:
    """Extract the first concrete version token from a specifier string."""
    if any(marker in spec for marker in _NON_VERSION_MARKERS):
        return None
    match = _VERSION_RE.search(spec)
    return match.group(0) if match else None


def _read_capped(path: Path) -> str | None:
    """Read a manifest as UTF-8, capped; None if it cannot be read."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(_MAX_MANIFEST_BYTES)
    except OSError as exc:
        logger.debug("Cannot read manifest %s: %s", path, exc)
        return None


def _parse_requirement(line: str) -> tuple[str, str] | None:
    """Parse a single requirements.txt / PEP 508 line into (name, version)."""
    stripped = line.split("#", 1)[0].strip()
    if not stripped or stripped.startswith("-"):
        return None  # blank, comment, or an option line (-r, --hash, ...)
    name_match = _REQ_NAME_RE.match(stripped)
    if not name_match:
        return None
    name = name_match.group(1)
    remainder = stripped[name_match.end() :]
    version = _first_version(remainder)
    if version is None:
        return None
    return _normalize_py_name(name), version


def _from_requirements_txt(project_path: Path, out: dict[str, str]) -> None:
    text = _read_capped(project_path / "requirements.txt")
    if text is None:
        return
    for line in text.splitlines():
        parsed = _parse_requirement(line)
        if parsed:
            out.setdefault(parsed[0], parsed[1])


def _from_pyproject(project_path: Path, out: dict[str, str]) -> None:
    text = _read_capped(project_path / "pyproject.toml")
    if text is None:
        return
    try:
        data = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        logger.debug("Malformed pyproject.toml: %s", exc)
        return
    project = data.get("project", {})
    if not isinstance(project, dict):
        return
    specs: list[str] = []
    deps = project.get("dependencies", [])
    if isinstance(deps, list):
        specs.extend(str(d) for d in deps)
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for group in optional.values():
            if isinstance(group, list):
                specs.extend(str(d) for d in group)
    for spec in specs:
        parsed = _parse_requirement(spec)
        if parsed:
            out.setdefault(parsed[0], parsed[1])


def _from_package_json(project_path: Path, out: dict[str, str]) -> None:
    text = _read_capped(project_path / "package.json")
    if text is None:
        return
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.debug("Malformed package.json: %s", exc)
        return
    if not isinstance(data, dict):
        return
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for name, spec in deps.items():
            if not isinstance(name, str) or not isinstance(spec, str):
                continue
            version = _first_version(spec)
            if version is not None:
                out.setdefault(name.strip().lower(), version)


def detect_dependency_versions(project_path: Path) -> dict[str, str]:
    """Return declared package versions from the project's root manifests.

    Python package names are PEP 503 normalized; npm names are lowercased with
    their scope preserved. When more than one manifest declares the same
    package, the first one read wins (requirements.txt, then pyproject.toml,
    then package.json).
    """
    versions: dict[str, str] = {}
    _from_requirements_txt(project_path, versions)
    _from_pyproject(project_path, versions)
    _from_package_json(project_path, versions)
    return versions


def resolve_framework_version(framework_name: str, versions: dict[str, str]) -> str | None:
    """Resolve a framework detector's name to a declared version, if any."""
    for candidate in FRAMEWORK_PACKAGES.get(framework_name, ()):
        if candidate in versions:
            return versions[candidate]
    return None
