from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def runtime_dir() -> Path:
    override = os.environ.get("XDG_RUNTIME_DIR")
    if override:
        return Path(override) / "agentdiode"
    if sys.platform == "darwin":
        # macOS has no /run/user equivalent; $TMPDIR is already a
        # per-user, mode-0700 directory managed by the OS.
        return Path(tempfile.gettempdir()) / "agentdiode"
    return Path(f"/run/user/{os.getuid()}") / "agentdiode"


def socket_path() -> Path:
    override = os.environ.get("AGENTDIODE_SOCKET")
    return Path(override) if override else runtime_dir() / "agentdiode.sock"


def state_dir() -> Path:
    override = os.environ.get("XDG_STATE_HOME")
    if override:
        return Path(override) / "agentdiode"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "agentdiode"
    return Path.home() / ".local" / "state" / "agentdiode"


def database_path() -> Path:
    override = os.environ.get("AGENTDIODE_DATABASE")
    return Path(override) if override else state_dir() / "history.sqlite3"


def ensure_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
