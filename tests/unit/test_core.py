from pathlib import Path

import pytest

from agentdiode.daemon import session_manager as session_manager_module
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


def test_idle_session_drops_out_of_the_snapshot_after_the_display_window(
    tmp_path: Path,
) -> None:
    manager = SessionManager(Database(tmp_path / "history.sqlite3"))
    manager.apply(Event(event="session.running", agent_id="claude", session_id="closed"))
    manager.apply(Event(event="session.idle", agent_id="claude", session_id="closed"))
    # Still within the grace window: the just-ended session stays visible.
    assert len(manager.snapshot(completed_display_seconds=60)["sessions"]) == 1
    # Once the window has elapsed it should no longer be reported.
    assert manager.snapshot(completed_display_seconds=0)["sessions"] == []


def test_idle_session_without_completed_at_falls_back_to_updated_at(tmp_path: Path) -> None:
    # Rows written before "idle" was a terminal state have no completed_at.
    manager = SessionManager(Database(tmp_path / "history.sqlite3"))
    manager.sessions["legacy"] = Session(
        session_id="legacy",
        agent_id="claude",
        agent_name="Claude Code",
        state="idle",
        completed_at="",
    )
    assert manager.snapshot(completed_display_seconds=0)["sessions"] == []


def test_prune_finished_removes_expired_idle_and_completed_sessions(
    tmp_path: Path,
) -> None:
    manager = SessionManager(Database(tmp_path / "history.sqlite3"))
    manager.apply(Event(event="session.running", agent_id="claude", session_id="ended"))
    manager.apply(Event(event="session.idle", agent_id="claude", session_id="ended"))
    manager.apply(Event(event="session.running", agent_id="codex", session_id="live"))
    removed = manager.prune_finished(display_seconds=0)
    assert removed == ["ended"]
    assert set(manager.sessions) == {"live"}


def test_mark_stale_removes_sessions_whose_process_is_confirmed_gone(
    tmp_path: Path, monkeypatch
) -> None:
    manager = SessionManager(Database(tmp_path / "history.sqlite3"))
    manager.apply(
        Event(event="session.running", agent_id="codex", session_id="killed", pid=4242)
    )
    monkeypatch.setattr(session_manager_module, "process_matches", lambda pid, ticks: False)
    changed = manager.mark_stale(timeout_seconds=3600)
    assert changed == []
    assert "killed" not in manager.sessions


def test_mark_stale_keeps_timed_out_sessions_for_manual_review(tmp_path: Path) -> None:
    manager = SessionManager(Database(tmp_path / "history.sqlite3"))
    manager.apply(Event(event="session.running", agent_id="codex", session_id="quiet"))
    changed = manager.mark_stale(timeout_seconds=0)
    assert [session.session_id for session in changed] == ["quiet"]
    assert manager.sessions["quiet"].state == "stale"
