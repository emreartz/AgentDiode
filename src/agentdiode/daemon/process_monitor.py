from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROC_ROOT = Path("/proc")


def process_start_ticks(pid: int, proc_root: Path = PROC_ROOT) -> int | None:
    try:
        content = (proc_root / str(pid) / "stat").read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, OSError):
        if proc_root == PROC_ROOT and sys.platform == "darwin":
            return _macos_process_start_ticks(pid)
        return None
    closing = content.rfind(")")
    if closing < 0:
        return None
    fields = content[closing + 2 :].split()
    try:
        return int(fields[19])
    except (IndexError, ValueError):
        return None


def _macos_process_start_ticks(pid: int) -> int | None:
    # macOS has no /proc. Ask `ps` for the process's absolute start time
    # and use its epoch seconds as a stable, comparable surrogate for
    # /proc's jiffies-since-boot start ticks.
    try:
        result = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = result.stdout.strip()
    if not output:
        return None
    try:
        # `ps` prints local wall-clock time with no timezone; astimezone()
        # attaches the system timezone to the naive result.
        started = datetime.strptime(output, "%a %b %d %H:%M:%S %Y").astimezone()
    except ValueError:
        return None
    return int(started.timestamp())


def process_matches(pid: int, expected_start_ticks: int | None) -> bool:
    actual = process_start_ticks(pid)
    return actual is not None and (
        expected_start_ticks is None or actual == expected_start_ticks
    )
