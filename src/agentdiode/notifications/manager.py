from __future__ import annotations

import shutil
import subprocess
import sys

from agentdiode.config import load as load_config
from agentdiode.models import Session

NOTIFIABLE = {"completed", "error", "waiting_input", "waiting_approval"}
TITLES = {
    "completed": "{agent} completed",
    "error": "{agent} failed",
    "waiting_input": "{agent} needs your response",
    "waiting_approval": "{agent} needs approval",
}
CONFIG_KEYS = {
    "completed": "on_completed",
    "error": "on_error",
    "waiting_input": "on_waiting_input",
    "waiting_approval": "on_waiting_approval",
}


def _osa_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class NotificationManager:
    def __init__(self) -> None:
        self.last_state: dict[str, str] = {}
        self.executable = shutil.which("notify-send")
        self.terminal_notifier = (
            shutil.which("terminal-notifier") if sys.platform == "darwin" else None
        )
        self.osascript = shutil.which("osascript") if sys.platform == "darwin" else None

    def notify(self, session: Session) -> bool:
        previous = self.last_state.get(session.session_id)
        self.last_state[session.session_id] = session.state
        available = self.executable or self.terminal_notifier or self.osascript
        if previous == session.state or session.state not in NOTIFIABLE or not available:
            return False
        config = load_config().notifications
        if not config.enabled or not getattr(config, CONFIG_KEYS[session.state]):
            return False
        title = TITLES[session.state].format(agent=session.agent_name)
        detail = session.project_name or "Unknown project"
        if session.error_message:
            detail = f"{detail} · {session.error_message[:160]}"
        command = self._command(title, detail)
        if command is None:
            return False
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True

    def _command(self, title: str, detail: str) -> list[str] | None:
        if self.terminal_notifier:
            return [
                self.terminal_notifier,
                "-title",
                "AgentDiode",
                "-subtitle",
                title,
                "-message",
                detail,
            ]
        if self.osascript:
            script = (
                f"display notification {_osa_quote(detail)} "
                f"with title {_osa_quote('AgentDiode')} "
                f"subtitle {_osa_quote(title)}"
            )
            return [self.osascript, "-e", script]
        if self.executable:
            return [self.executable, "--app-name=AgentDiode", title, detail]
        return None
