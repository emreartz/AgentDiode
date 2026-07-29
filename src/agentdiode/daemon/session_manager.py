from __future__ import annotations

import logging
from datetime import datetime

from agentdiode.constants import TERMINAL_STATES
from agentdiode.daemon.process_monitor import process_matches, process_start_ticks
from agentdiode.models import Session, aggregate_state, project_name
from agentdiode.protocol import Event, ProtocolError
from agentdiode.storage.database import Database

LOGGER = logging.getLogger("agentdiode.daemon")

# States that mean "this session is definitively over" — the underlying
# CLI/agent process ended (idle) or finished a turn (completed). They are
# auto-hidden from snapshots after a short grace period and then pruned
# outright, so a closed terminal disappears from the tray on its own.
FINISHED_STATES = frozenset({"completed", "idle"})


class SessionManager:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.sessions = {item.session_id: item for item in database.load_current()}

    def apply(self, event: Event) -> Session | None:
        if event.event == "session.remove":
            self.sessions.pop(event.session_id, None)
            self.database.remove(event.session_id)
            return None
        state = event.event.removeprefix("session.")
        existing = self.sessions.get(event.session_id)
        if event.event == "session.heartbeat":
            if existing is None:
                raise ProtocolError("heartbeat for unknown session")
            existing.updated_at = event.timestamp
            self.database.save(existing, event.event, event.to_dict())
            return existing
        if existing is None:
            if state not in {"starting", "running"}:
                raise ProtocolError("first event must be starting or running")
            existing = Session(
                session_id=event.session_id,
                agent_id=event.agent_id,
                agent_name=event.agent_name or event.agent_id.title(),
                state=state,
                reliability=event.reliability,
                project_name=project_name(event.cwd),
                cwd=event.cwd,
                started_at=event.timestamp,
                updated_at=event.timestamp,
                pid=event.pid,
                parent_pid=event.parent_pid,
                source=event.source,
                metadata=event.metadata,
            )
            if event.pid:
                existing.metadata["process_start_ticks"] = process_start_ticks(event.pid)
            self.sessions[event.session_id] = existing
        else:
            if existing.agent_id != event.agent_id:
                raise ProtocolError("session agent_id cannot change")
            existing.state = state
            existing.updated_at = event.timestamp
            existing.cwd = event.cwd or existing.cwd
            existing.project_name = project_name(existing.cwd)
            existing.pid = event.pid or existing.pid
            existing.parent_pid = event.parent_pid or existing.parent_pid
            existing.metadata.update(event.metadata)
        existing.summary = event.summary
        existing.error_message = event.error_message
        if state in TERMINAL_STATES:
            existing.completed_at = event.timestamp
        self.database.save(existing, event.event, event.to_dict())
        return existing

    def snapshot(self, completed_display_seconds: int = 8) -> dict[str, object]:
        items = sorted(self.sessions.values(), key=lambda item: item.updated_at, reverse=True)
        visible = [
            item for item in items if self._is_visible(item, completed_display_seconds)
        ]
        state = aggregate_state(visible)
        return {"overall_state": state, "sessions": [item.to_dict() for item in visible]}

    def _is_visible(self, item: Session, display_seconds: int) -> bool:
        if item.state not in FINISHED_STATES:
            return True
        # completed_at may be missing on rows written before a state was
        # added to TERMINAL_STATES; updated_at is always set and is a fine
        # anchor for "since when has this been finished".
        anchor = item.completed_at or item.updated_at
        ended = datetime.fromisoformat(anchor)
        now = datetime.now().astimezone()
        return (now - ended).total_seconds() <= display_seconds

    def _remove(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        self.database.remove(session_id)

    def mark_stale(self, timeout_seconds: int) -> list[Session]:
        now = datetime.now().astimezone()
        changed = []
        for session in list(self.sessions.values()):
            if session.state not in {"starting", "running", "waiting_input", "waiting_approval"}:
                continue
            updated = datetime.fromisoformat(session.updated_at)
            timed_out = (now - updated).total_seconds() > timeout_seconds
            process_invalid = bool(
                session.pid
                and not process_matches(
                    session.pid, session.metadata.get("process_start_ticks")
                )
            )
            if not timed_out and not process_invalid:
                continue
            if process_invalid:
                # The tracked process is confirmed gone (not merely quiet) —
                # drop it outright instead of leaving a stale entry that
                # needs a manual "Remove stale session" click.
                LOGGER.info("Session %s removed (process no longer running)", session.session_id)
                self._remove(session.session_id)
                continue
            session.state = "stale"
            session.updated_at = now.isoformat()
            self.database.save(session, "session.stale", {"reason": "heartbeat_timeout"})
            changed.append(session)
        return changed

    def prune_finished(self, display_seconds: int) -> list[str]:
        removed = []
        for session in list(self.sessions.values()):
            if self._is_visible(session, display_seconds):
                continue
            removed.append(session.session_id)
            self._remove(session.session_id)
        return removed

    def reconcile_startup(self) -> list[Session]:
        changed = []
        now = datetime.now().astimezone().isoformat()
        for session in self.sessions.values():
            if session.state not in {"starting", "running", "waiting_input", "waiting_approval"}:
                continue
            session.state = "stale"
            session.updated_at = now
            self.database.save(session, "session.stale", {"reason": "daemon_restart"})
            changed.append(session)
        return changed
