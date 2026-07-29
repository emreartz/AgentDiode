from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sqlite3
import sys
from dataclasses import dataclass

from agentdiode.paths import database_path, socket_path, state_dir

MIN_MACOS_VERSION = (26, 0)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def _session_check() -> Check:
    if sys.platform == "darwin":
        return Check("Session", True, "macOS")
    is_kde = bool(os.environ.get("KDE_FULL_SESSION"))
    return Check("Session", is_kde, "KDE Plasma" if is_kde else "not KDE")


def _display_check() -> Check:
    if sys.platform == "darwin":
        return Check("Display", True, "Aqua")
    has_display = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
    return Check("Display", has_display, os.environ.get("XDG_SESSION_TYPE", "unknown"))


def _notifications_check() -> Check:
    if sys.platform == "darwin":
        backend = shutil.which("terminal-notifier") or shutil.which("osascript")
        return Check("Notifications", backend is not None, backend or "unavailable")
    backend = shutil.which("notify-send")
    return Check("Notifications", backend is not None, backend or "unavailable")


def _macos_version_check() -> Check | None:
    if sys.platform != "darwin":
        return None
    release = platform.mac_ver()[0]
    try:
        major, minor, *_ = (int(part) for part in release.split("."))
    except ValueError:
        return Check("macOS version", False, release or "unknown")
    ok = (major, minor) >= MIN_MACOS_VERSION or major >= MIN_MACOS_VERSION[0]
    return Check("macOS version", ok, release or "unknown")


def run_checks() -> list[Check]:
    sock = socket_path()
    database = database_path()
    checks = [
        Check("Python", sys.version_info >= (3, 11), sys.version.split()[0]),
        Check(
            "PySide6",
            importlib.util.find_spec("PySide6") is not None,
            "available" if importlib.util.find_spec("PySide6") else "not installed",
        ),
        _session_check(),
        _display_check(),
        Check("Socket", sock.exists(), str(sock)),
        _notifications_check(),
        Check("Codex", shutil.which("codex") is not None, shutil.which("codex") or "not installed"),
        Check("Claude", shutil.which("claude") is not None, shutil.which("claude") or "not installed"),
        Check(
            "Antigravity",
            shutil.which("agy") is not None,
            shutil.which("agy") or "not installed",
        ),
        Check("VS Code", shutil.which("code") is not None, shutil.which("code") or "not installed"),
        Check("State directory", os.access(state_dir().parent, os.W_OK), str(state_dir())),
    ]
    macos_version = _macos_version_check()
    if macos_version is not None:
        checks.append(macos_version)
    if database.exists():
        try:
            with sqlite3.connect(database) as connection:
                result = connection.execute("PRAGMA quick_check").fetchone()
            checks.append(Check("Database", result == ("ok",), str(database)))
        except sqlite3.Error as exc:
            checks.append(Check("Database", False, str(exc)))
    else:
        checks.append(Check("Database", True, "not created yet"))
    return checks


def format_checks(checks: list[Check]) -> str:
    return "\n".join(
        f"{'OK' if check.ok else 'WARN':<4} {check.name:<18} {check.detail}" for check in checks
    )
