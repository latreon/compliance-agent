"""Tests for update checking and self-upgrade command building."""

import pytest

from compliance_agent import updates


def test_is_newer_compares_semver() -> None:
    assert updates.is_newer("0.1.2", "0.1.1")
    assert updates.is_newer("0.2.0", "0.1.9")
    assert updates.is_newer("1.0.0", "0.9.9")
    assert not updates.is_newer("0.1.1", "0.1.1")
    assert not updates.is_newer("0.1.0", "0.1.1")


def test_is_newer_handles_uneven_lengths() -> None:
    assert updates.is_newer("0.1.1", "0.1")
    assert not updates.is_newer("0.1", "0.1.1")


def _enable_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("COMPLIANCE_AGENT_NO_UPDATE_CHECK", "NO_UPDATE_NOTIFIER", "CI"):
        monkeypatch.delenv(var, raising=False)


def test_check_for_update_respects_disable_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPLIANCE_AGENT_NO_UPDATE_CHECK", "1")
    # Even if a newer version would be found, disable short-circuits to None.
    monkeypatch.setattr(updates, "latest_version", lambda **_: "99.0.0")
    assert updates.check_for_update("0.1.0") is None


def test_check_for_update_returns_newer_version(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_checks(monkeypatch)
    monkeypatch.setattr(updates, "latest_version", lambda **_: "0.2.0")
    assert updates.check_for_update("0.1.0") == "0.2.0"


def test_check_for_update_none_when_current_is_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_checks(monkeypatch)
    monkeypatch.setattr(updates, "latest_version", lambda **_: "0.1.0")
    assert updates.check_for_update("0.1.0") is None


def test_latest_version_network_failure_is_non_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_checks(monkeypatch)
    monkeypatch.setattr(updates, "_read_cache", lambda: {})
    monkeypatch.setattr(updates, "_fetch_latest", lambda timeout: None)
    assert updates.latest_version(force=True) is None


def test_build_upgrade_command_uv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updates, "detect_install_method", lambda: "uv")
    monkeypatch.setattr(updates.shutil, "which", lambda _: "/usr/local/bin/uv")
    assert updates.build_upgrade_command("latest") == ["uv", "tool", "upgrade", "compliance-agent"]
    assert updates.build_upgrade_command("0.1.2") == [
        "uv",
        "tool",
        "install",
        "--force",
        "compliance-agent==0.1.2",
    ]


def test_build_upgrade_command_pipx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updates, "detect_install_method", lambda: "pipx")
    monkeypatch.setattr(updates.shutil, "which", lambda _: "/usr/local/bin/pipx")
    assert updates.build_upgrade_command("latest") == ["pipx", "upgrade", "compliance-agent"]


def test_build_upgrade_command_pip_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updates, "detect_install_method", lambda: "pip")
    monkeypatch.setattr(updates.shutil, "which", lambda _: None)
    cmd = updates.build_upgrade_command("latest")
    assert cmd[1:] == ["-m", "pip", "install", "--upgrade", "compliance-agent"]
