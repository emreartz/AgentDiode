from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont, QFontDatabase, QIcon
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from agentdiode.config import load as load_config
from agentdiode.logging_setup import configure_logging
from agentdiode.models import now_iso
from agentdiode.paths import socket_path
from agentdiode.tray.icon_renderer import render_icon
from agentdiode.tray.tooltip import build_tooltip, duration
from agentdiode.ui.history_window import HistoryWindow
from agentdiode.ui.session_dialog import SessionDialog
from agentdiode.ui.settings_window import SettingsWindow

ANIMATED = {"starting", "running", "waiting_input", "waiting_approval"}


def menu_signature(snapshot: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    """Everything that determines the menu's structure. Durations are excluded on purpose."""
    return tuple(
        (
            str(item["session_id"]),
            str(item["agent_name"]),
            str(item["state"]),
            str(item.get("project_name") or ""),
            str(item.get("cwd") or ""),
        )
        for item in snapshot.get("sessions", [])
    )


def subtitle_text(item: dict[str, Any]) -> str:
    return f"{item['project_name'] or '-'} · {duration(item['duration_seconds'])}"


class TrayController:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.config = load_config()
        self.state = "idle"
        self.frame = True
        self.dialogs: list[SessionDialog] = []
        self.windows: list[Any] = []
        self.latest_snapshot: dict[str, Any] = {}
        self._menu_signature: tuple[tuple[str, ...], ...] | None = None
        self._subtitles: dict[str, QAction] = {}
        self.socket = QLocalSocket()
        self.socket.readyRead.connect(self._read_response)
        self.socket.errorOccurred.connect(self._request_finished)
        self.tray = QSystemTrayIcon(render_icon("idle"), app)
        self.tray.setToolTip("AgentDiode\nConnecting to daemon…")
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.refresh)
        self.poll_timer.start(1500)
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate)
        self.animation_timer.start(self.config.tray.animation_interval_ms)
        self.refresh()

    def refresh(self) -> None:
        self.send({"command": "snapshot"})

    def send(self, payload: dict[str, Any]) -> None:
        if self.socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            return
        self.socket.connectToServer(str(socket_path()))
        if self.socket.waitForConnected(100):
            encoded = QByteArray(json.dumps(payload).encode() + b"\n")
            self.socket.write(encoded)
            self.socket.flush()

    def _read_response(self) -> None:
        line = self.socket.readLine().data()
        if not line:
            return
        try:
            snapshot = json.loads(bytes(line))
            if snapshot.get("ok"):
                self.update(snapshot)
        except (json.JSONDecodeError, TypeError):
            self.tray.setToolTip("AgentDiode\nInvalid daemon response")
        self._request_finished()

    def _request_finished(self, *_args: object) -> None:
        self.socket.abort()

    def update(self, snapshot: dict[str, Any]) -> None:
        self.state = snapshot["overall_state"]
        self.latest_snapshot = snapshot
        self.tray.setIcon(render_icon(self.state))
        self.tray.setToolTip(build_tooltip(snapshot))
        signature = menu_signature(snapshot)
        if signature != self._menu_signature:
            self._render_menu(snapshot, signature)
            return
        # Same sessions in the same states: only the durations changed, so update the
        # existing actions in place instead of creating a new menu tree.
        for item in snapshot.get("sessions", []):
            self._subtitles[str(item["session_id"])].setText(subtitle_text(item))

    def _session(self, session_id: str) -> dict[str, Any] | None:
        item: dict[str, Any]
        for item in self.latest_snapshot.get("sessions", []):
            if item["session_id"] == session_id:
                return item
        return None

    def _on_session(self, session_id: str, callback: Callable[[dict[str, Any]], object]) -> None:
        # The menu outlives individual snapshots, so always act on the newest data.
        item = self._session(session_id)
        if item is not None:
            callback(item)

    def _render_menu(
        self, snapshot: dict[str, Any], signature: tuple[tuple[str, ...], ...]
    ) -> None:
        # Drop references to actions that are about to be deleted.
        self._subtitles = {}
        # QMenu.clear() does not delete submenus created with addMenu().
        for sub in self.menu.findChildren(QMenu):
            sub.deleteLater()
        self.menu.clear()
        title = self.menu.addAction("AgentDiode")
        title.setEnabled(False)
        self.menu.addSeparator()
        sessions = snapshot.get("sessions", [])
        if not sessions:
            empty = self.menu.addAction("No sessions")
            empty.setEnabled(False)
        for item in sessions:
            sid = str(item["session_id"])
            label = f"{item['agent_name']} — {item['state'].replace('_', ' ').upper()}"
            submenu = self.menu.addMenu(label)
            subtitle = submenu.addAction(subtitle_text(item))
            subtitle.setEnabled(False)
            self._subtitles[sid] = subtitle
            submenu.addSeparator()
            details = submenu.addAction("Open details")
            details.triggered.connect(
                lambda _checked=False, sid=sid: self._on_session(sid, self.show_details)
            )
            if item.get("cwd"):
                open_folder = submenu.addAction("Open project folder")
                open_folder.triggered.connect(
                    lambda _checked=False, sid=sid: self._on_session(
                        sid, lambda s: QDesktopServices.openUrl(QUrl.fromLocalFile(s["cwd"]))
                    )
                )
                copy_path = submenu.addAction("Copy project path")
                copy_path.triggered.connect(
                    lambda _checked=False, sid=sid: self._on_session(
                        sid, lambda s: self.app.clipboard().setText(s["cwd"])
                    )
                )
            if item["state"] not in {"completed", "error", "idle"}:
                complete = submenu.addAction("Mark completed")
                complete.triggered.connect(
                    lambda _checked=False, sid=sid: self._on_session(
                        sid, lambda s: self.session_event(s, "completed")
                    )
                )
            if item["state"] in {"stale", "disconnected"}:
                remove = submenu.addAction("Remove stale session")
                remove.triggered.connect(
                    lambda _checked=False, sid=sid: self._on_session(
                        sid, lambda s: self.session_event(s, "remove")
                    )
                )
        self.menu.addSeparator()
        history = self.menu.addAction("Open history")
        history.triggered.connect(self.show_history)
        settings = self.menu.addAction("Settings")
        settings.triggered.connect(self.show_settings)
        refresh = self.menu.addAction("Refresh")
        refresh.triggered.connect(self.refresh)
        quit_action = self.menu.addAction("Quit tray")
        quit_action.triggered.connect(self.app.quit)
        self._menu_signature = signature

    def show_details(self, session: dict[str, Any]) -> None:
        dialog = SessionDialog(session)
        self.dialogs.append(dialog)
        dialog.finished.connect(lambda _result, value=dialog: self.dialogs.remove(value))
        dialog.show()
        dialog.raise_()

    def session_event(self, session: dict[str, Any], state: str) -> None:
        payload = {
            "protocol_version": 1,
            "event": f"session.{state}",
            "timestamp": now_iso(),
            "agent_id": session["agent_id"],
            "session_id": session["session_id"],
            "cwd": session["cwd"],
            "reliability": session["reliability"],
            "source": "tray-action",
            "metadata": {},
        }
        self.send({"command": "event", "payload": payload})

    def daemon_request(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        client = QLocalSocket()
        client.connectToServer(str(socket_path()))
        if not client.waitForConnected(500):
            return None
        client.write(QByteArray(json.dumps(payload).encode() + b"\n"))
        if not client.waitForReadyRead(1000):
            client.abort()
            return None
        try:
            response = json.loads(bytes(client.readLine().data()))
            return response if isinstance(response, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
        finally:
            client.abort()

    def show_history(self) -> None:
        response = self.daemon_request({"command": "history", "limit": 1000})
        if not response or not response.get("ok"):
            self.tray.showMessage("AgentDiode", "History is unavailable.")
            return
        window = HistoryWindow(response["sessions"])
        self.windows.append(window)
        window.finished.connect(lambda _result, value=window: self.windows.remove(value))
        window.show()

    def show_settings(self) -> None:
        window = SettingsWindow()
        self.windows.append(window)
        window.finished.connect(lambda _result, value=window: self.windows.remove(value))
        window.accepted.connect(self.apply_config)
        window.show()

    def apply_config(self) -> None:
        self.config = load_config()
        self.animation_timer.setInterval(self.config.tray.animation_interval_ms)
        self.frame = True
        self.tray.setIcon(render_icon(self.state))

    def animate(self) -> None:
        if self.state not in ANIMATED:
            return
        if self.state in {"starting", "running"} and not self.config.tray.blink_running:
            return
        if (
            self.state in {"waiting_input", "waiting_approval"}
            and not self.config.tray.blink_waiting
        ):
            return
        self.frame = not self.frame
        self.tray.setIcon(render_icon(self.state, self.frame))


def main() -> int:
    configure_logging("tray")
    app = QApplication(sys.argv)
    available_fonts = set(QFontDatabase.families())
    for family in ("Noto Sans", "DejaVu Sans"):
        if family in available_fonts:
            app.setFont(QFont(family))
            break
    app.setApplicationName("AgentDiode")
    app.setApplicationDisplayName("AgentDiode")
    app.setDesktopFileName("io.agentdiode.AgentDiode")
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    installed_icon = (
        data_home / "icons/hicolor/scalable/apps/io.agentdiode.AgentDiode.svg"
    )
    app.setWindowIcon(
        QIcon.fromTheme("io.agentdiode.AgentDiode", QIcon(str(installed_icon)))
    )
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("agentdiode-tray: no system tray is available", file=sys.stderr)
        return 2
    app._agentdiode_controller = TrayController(app)  # type: ignore[attr-defined]
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
