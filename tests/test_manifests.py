"""Tests for dependency-manifest version detection."""

from pathlib import Path

from compliance_agent.scanner.manifests import (
    detect_dependency_versions,
    resolve_framework_version,
)


def test_reads_pinned_version_from_requirements_txt(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("langchain==0.2.5\ncrewai~=0.30\n")

    versions = detect_dependency_versions(tmp_path)

    assert versions["langchain"] == "0.2.5"
    assert versions["crewai"] == "0.30"


def test_reads_ranged_version_from_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["crewai>=0.30.1", "openai"]\n'
    )

    versions = detect_dependency_versions(tmp_path)

    # First concrete version token of the specifier is kept; a bare name (openai)
    # has no version and is skipped.
    assert versions["crewai"] == "0.30.1"
    assert "openai" not in versions


def test_reads_optional_dependencies_from_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "x"\n'
        "dependencies = []\n"
        "[project.optional-dependencies]\n"
        'ai = ["langgraph==0.1.0"]\n'
    )

    versions = detect_dependency_versions(tmp_path)

    assert versions["langgraph"] == "0.1.0"


def test_reads_npm_version_stripping_range_prefix(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"ai": "^3.1.0", "@langchain/langgraph": "~0.2.3"}}'
    )

    versions = detect_dependency_versions(tmp_path)

    assert versions["ai"] == "3.1.0"
    assert versions["@langchain/langgraph"] == "0.2.3"


def test_normalizes_python_package_names(tmp_path: Path) -> None:
    # PEP 503 normalization: Langchain_Core -> langchain-core.
    (tmp_path / "requirements.txt").write_text("Langchain_Core==0.3.0\n")

    versions = detect_dependency_versions(tmp_path)

    assert versions["langchain-core"] == "0.3.0"


def test_missing_manifests_returns_empty(tmp_path: Path) -> None:
    assert detect_dependency_versions(tmp_path) == {}


def test_malformed_manifest_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{ this is not json")
    (tmp_path / "pyproject.toml").write_text("[project\nbroken")

    # Best-effort: a broken manifest must never crash the scan.
    assert detect_dependency_versions(tmp_path) == {}


def test_resolve_framework_version_maps_name_to_package() -> None:
    versions = {"crewai": "0.30.1", "@langchain/langgraph": "0.2.3"}

    assert resolve_framework_version("crewai", versions) == "0.30.1"
    # langgraph resolves via its npm package when the py package is absent.
    assert resolve_framework_version("langgraph", versions) == "0.2.3"


def test_resolve_framework_version_prefers_python_package() -> None:
    versions = {"langgraph": "0.1.5", "@langchain/langgraph": "0.2.3"}

    assert resolve_framework_version("langgraph", versions) == "0.1.5"


def test_resolve_framework_version_none_when_absent() -> None:
    assert resolve_framework_version("crewai", {}) is None
    assert resolve_framework_version("unknown-framework", {"crewai": "1.0"}) is None
