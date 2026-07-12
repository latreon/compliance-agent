"""Project configuration file (``compliance.yaml``).

A project can declare its AI-compliance posture and default scan options in a
``compliance.yaml`` (or ``.compliance.yaml``) at the project root, so nobody
has to re-type ``--exclude``/``--fail-on`` flags on every run:

    version: 1
    posture:
      # Declared EU AI Act risk tier. It can only RAISE the detected tier —
      # a declaration can never talk the scanner DOWN a tier, because that
      # would let a config file manufacture false assurance.
      risk_tier: high
      intended_purpose: "CV screening assistant for the recruiting team"
    scan:
      exclude:
        - "docs/*"
        - "notebooks/*"
      include: []
      fail_on: high        # CI gate: exit 1 at this severity or above
      severity: warning    # hide details below this severity
      format: markdown     # default output format
      output: null         # default report path (format-dependent)

Explicit CLI flags always override the config file. An invalid config is a
hard error (exit code 2), never silently ignored: a typo like ``fail_on:
hihg`` must not quietly disable a CI compliance gate.
"""

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from compliance_agent.models.findings import RiskTier, Severity

logger = logging.getLogger(__name__)

#: Candidate file names, checked in order; the first match wins.
CONFIG_FILENAMES = (
    "compliance.yaml",
    "compliance.yml",
    ".compliance.yaml",
    ".compliance.yml",
)

_MAX_CONFIG_BYTES = 256_000  # a posture/defaults file has no business being bigger


class ConfigError(Exception):
    """Raised when a compliance.yaml exists but cannot be used.

    The message is written for the terminal: it names the file and says what
    to fix. Callers (CLI, web app) decide how to surface it.
    """


class PostureConfig(BaseModel, extra="forbid"):
    """Declared compliance posture of the project."""

    risk_tier: RiskTier | None = None
    intended_purpose: str | None = None


class ScanConfig(BaseModel, extra="forbid"):
    """Default scan options; each maps 1:1 to a ``scan`` CLI flag."""

    exclude: list[str] = Field(default_factory=list)
    include: list[str] = Field(default_factory=list)
    fail_on: Severity | None = None
    severity: Severity | None = None
    format: str | None = None
    output: str | None = None


class ProjectConfig(BaseModel, extra="forbid"):
    """Parsed, validated contents of a project's compliance.yaml."""

    version: int = 1
    posture: PostureConfig = Field(default_factory=PostureConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    #: Where the config was loaded from (set by ``load_config``; not part of
    #: the file schema).
    source_path: Path | None = Field(default=None, exclude=True)


def find_config_file(project_path: Path) -> Path | None:
    """Return the project's config file path, or None when there is none."""
    for name in CONFIG_FILENAMES:
        candidate = project_path / name
        if candidate.is_file():
            return candidate
    return None


def load_config(project_path: Path) -> ProjectConfig | None:
    """Load and validate the project's compliance.yaml, if present.

    Returns None when the project has no config file. Raises ``ConfigError``
    when a config file exists but is unreadable, malformed, or fails schema
    validation — a broken config must never be silently treated as absent.
    """
    config_path = find_config_file(Path(project_path))
    if config_path is None:
        return None

    try:
        if config_path.stat().st_size > _MAX_CONFIG_BYTES:
            raise ConfigError(
                f"{config_path.name} is larger than {_MAX_CONFIG_BYTES // 1000} kB — "
                "that is not a compliance config file. Remove or shrink it."
            )
        raw = config_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ConfigError(f"Cannot read {config_path}: {exc.strerror or exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path.name} is not valid YAML: {exc}") from exc

    if data is None:
        # An empty file is a valid "all defaults" config.
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(
            f"{config_path.name} must be a YAML mapping (key: value pairs), "
            f"got {type(data).__name__}."
        )

    try:
        config = ProjectConfig.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors()
        )
        raise ConfigError(
            f"{config_path.name} is invalid — {problems}. "
            "See the README's 'Project config file' section for the schema."
        ) from exc

    if config.version != 1:
        raise ConfigError(
            f"{config_path.name} declares version {config.version}, but this "
            "release of ComplianceAgent only supports version 1."
        )

    config = config.model_copy(update={"source_path": config_path})
    logger.info("Loaded project config from %s", config_path)
    return config
