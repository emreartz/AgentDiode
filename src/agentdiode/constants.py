from __future__ import annotations

PROTOCOL_VERSION = 1
STATES = frozenset(
    {
        "starting",
        "running",
        "waiting_input",
        "waiting_approval",
        "completed",
        "error",
        "idle",
        "stale",
        "disconnected",
        "unknown",
    }
)
EVENTS = frozenset(
    {
        "session.starting",
        "session.running",
        "session.waiting_input",
        "session.waiting_approval",
        "session.completed",
        "session.error",
        "session.idle",
        "session.heartbeat",
        "session.disconnected",
        "session.remove",
    }
)
STATE_PRIORITY = {
    "error": 100,
    "waiting_approval": 90,
    "waiting_input": 80,
    "running": 70,
    "starting": 65,
    "stale": 60,
    "disconnected": 55,
    "completed": 40,
    "idle": 20,
    "unknown": 10,
}
TERMINAL_STATES = frozenset({"completed", "error", "disconnected", "idle"})
MAX_LINE_BYTES = 256 * 1024
MAX_METADATA_BYTES = 64 * 1024
