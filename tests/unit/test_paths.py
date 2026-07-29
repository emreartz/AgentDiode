from pathlib import Path

from agentdiode import paths


def test_runtime_dir_uses_run_user_on_linux(monkeypatch) -> None:
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(paths.os, "getuid", lambda: 1000)
    assert paths.runtime_dir() == Path("/run/user/1000/agentdiode")


def test_runtime_dir_falls_back_to_tmpdir_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(paths.tempfile, "gettempdir", lambda: "/var/folders/xx/T")
    assert paths.runtime_dir() == Path("/var/folders/xx/T/agentdiode")


def test_runtime_dir_respects_explicit_override_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/tmp/custom")
    assert paths.runtime_dir() == Path("/tmp/custom/agentdiode")


def test_state_dir_uses_application_support_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(paths.Path, "home", lambda: Path("/Users/example"))
    assert paths.state_dir() == Path("/Users/example/Library/Application Support/agentdiode")


def test_state_dir_uses_local_state_on_linux(monkeypatch) -> None:
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(paths.Path, "home", lambda: Path("/home/example"))
    assert paths.state_dir() == Path("/home/example/.local/state/agentdiode")
