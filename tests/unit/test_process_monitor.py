import subprocess
from datetime import datetime
from pathlib import Path

from agentdiode.daemon import process_monitor
from agentdiode.daemon.process_monitor import process_start_ticks


def test_process_start_ticks_handles_spaces_in_name(tmp_path: Path) -> None:
    process_dir = tmp_path / "42"
    process_dir.mkdir()
    # Fields after the command start at field 3. starttime is field 22.
    process_dir.joinpath("stat").write_text(
        "42 (name with spaces) S 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 999 20\n",
        encoding="utf-8",
    )
    assert process_start_ticks(42, tmp_path) == 999


def test_missing_process(tmp_path: Path) -> None:
    assert process_start_ticks(404, tmp_path) is None


def test_missing_process_stays_none_on_macos_with_custom_root(tmp_path: Path, monkeypatch) -> None:
    # A caller-supplied proc_root (as used by tests) must never trigger the
    # macOS `ps` fallback, even when running the suite on macOS.
    monkeypatch.setattr(process_monitor.sys, "platform", "darwin")
    assert process_start_ticks(404, tmp_path) is None


def test_macos_fallback_parses_ps_lstart(monkeypatch) -> None:
    expected = datetime(2026, 7, 28, 10, 30, 0).astimezone()

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=expected.strftime("%a %b %d %H:%M:%S %Y") + "\n"
        )

    monkeypatch.setattr(process_monitor.subprocess, "run", fake_run)
    assert process_monitor._macos_process_start_ticks(42) == int(expected.timestamp())


def test_macos_fallback_returns_none_when_ps_has_no_output(monkeypatch) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="")

    monkeypatch.setattr(process_monitor.subprocess, "run", fake_run)
    assert process_monitor._macos_process_start_ticks(404) is None


def test_process_start_ticks_uses_macos_fallback_when_proc_missing(monkeypatch) -> None:
    def raise_missing(self: Path, encoding: str | None = None) -> str:
        raise FileNotFoundError

    monkeypatch.setattr(process_monitor.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "read_text", raise_missing)
    monkeypatch.setattr(process_monitor, "_macos_process_start_ticks", lambda pid: 12345)
    assert process_start_ticks(42) == 12345
