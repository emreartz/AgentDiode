from datetime import datetime, timedelta
from pathlib import Path

import pytest

from agentdiode.daemon.session_manager import SessionManager
from agentdiode.models import Session, aggregate_state, project_name
from agentdiode.protocol import Event, ProtocolError
from agentdiode.storage.database import Database


def test_priority_and_project_name() -> None:
    sessions = [
        Session("a", "codex", "Codex", "running"),
        Session("b", "claude", "Claude", "waiting_approval"),
    ]
    assert aggregate_state(sessions) == "waiting_approval"
    assert project_name("/home/user/Projects/after9") == "after9"


def test_event_validation() -> None:
    Event(event="session.running", agent_id="codex", session_id="codex-1").validate()
    with pytest.raises(ProtocolError):
        Event(event="bad", agent_id="codex", session_id="codex-1").validate()
    with pytest.raises(ProtocolError):
        Event(event="session.running", agent_id="../bad", session_id="x").validate()


def test_concurrent_lifecycle(tmp_path: Path) -> None:
    manager = SessionManager(Database(tmp_path / "history.sqlite3"))
    manager.apply(Event(event="session.running", agent_id="codex", session_id="c1"))
    manager.apply(
        Event(event="session.starting", agent_id="claude", session_id="c2")
    )
    manager.apply(
        Event(event="session.waiting_approval", agent_id="claude", session_id="c2")
    )
    snapshot = manager.snapshot()
    assert snapshot["overall_state"] == "waiting_approval"
    assert len(snapshot["sessions"]) == 2
    manager.apply(Event(event="session.completed", agent_id="claude", session_id="c2"))
    assert manager.snapshot()["overall_state"] == "running"


def test_snapshot_hides_old_completed_sessions(tmp_path: Path) -> None:
    database = Database(tmp_path / "history.sqlite3")
    manager = SessionManager(database)
    old = (datetime.now().astimezone() - timedelta(hours=1)).isoformat()
    manager.apply(Event(event="session.running", agent_id="codex", session_id="live"))
    manager.apply(
        Event(event="session.running", agent_id="codex", session_id="old", timestamp=old)
    )
    manager.apply(
        Event(event="session.completed", agent_id="codex", session_id="old", timestamp=old)
    )
    manager.apply(Event(event="session.running", agent_id="claude", session_id="recent"))
    manager.apply(Event(event="session.completed", agent_id="claude", session_id="recent"))
    snapshot = manager.snapshot(completed_display_seconds=8)
    assert {item["session_id"] for item in snapshot["sessions"]} == {"live", "recent"}
    assert "old" in manager.sessions
    assert {item["session_id"] for item in database.history()} == {"live", "old", "recent"}


def test_heartbeat_requires_session(tmp_path: Path) -> None:
    manager = SessionManager(Database(tmp_path / "history.sqlite3"))
    with pytest.raises(ProtocolError):
        manager.apply(Event(event="session.heartbeat", agent_id="codex", session_id="missing"))


def test_restart_reconciliation(tmp_path: Path) -> None:
    database = Database(tmp_path / "history.sqlite3")
    manager = SessionManager(database)
    manager.apply(Event(event="session.running", agent_id="codex", session_id="live"))
    restarted = SessionManager(Database(tmp_path / "history.sqlite3"))
    assert restarted.reconcile_startup()[0].state == "stale"
