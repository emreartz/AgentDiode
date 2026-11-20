from __future__ import annotations

from typing import Any


def duration(value: int) -> str:
    minutes, seconds = divmod(value, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def build_tooltip(snapshot: dict[str, Any]) -> str:
    sessions = snapshot.get("sessions", [])
    active = [
        item for item in sessions
        if item["state"] not in {"completed", "idle", "disconnected"}
    ]
    if not active:
        return "AgentDiode\nNo active AI agents"
    lines = ["AgentDiode", f"{len(active)} active agent{'s' if len(active) != 1 else ''}", ""]
    for item in active[:6]:
        state = item["state"].replace("_", " ").title()
        lines.append(
            f"{item['agent_name']}: {state} - {item['project_name'] or '-'}"
            f" - {duration(item['duration_seconds'])}"
        )
    return "\n".join(lines)
