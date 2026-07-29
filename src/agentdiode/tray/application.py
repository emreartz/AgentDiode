from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QIcon
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


class TrayController:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.config = load_config()
        self.state = "idle"
        self.frame = True
        self.dialogs: list[SessionDialog] = []
        self.windows: list[Any] = []
        self.latest_snapshot: dict[str, Any] | None = None
        self.menu_open = False
        self.socket = QLocalSocket()
        self.socket.readyRead.connect(self._read_response)
        self.socket.errorOccurred.connect(self._request_finished)
        self.tray = QSystemTrayIcon(render_icon("idle"), app)
        self.tray.setToolTip("AgentDiode\nConnecting to daemon…")
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self._on_menu_about_to_show)
        self.menu.aboutToHide.connect(self._on_menu_about_to_hide)
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
        # On macOS, changing the status item's icon/tooltip (or rebuilding
        # its menu) while the menu is open can make the OS close or
        # reposition it under the cursor. While it is open we only cache the
        # latest snapshot; _on_menu_about_to_hide() applies it once closed.
        if self.menu_open:
            return
        self._apply_snapshot()

    def _apply_snapshot(self) -> None:
        if self.latest_snapshot is None:
            return
        self.tray.setIcon(render_icon(self.state, self.frame))
        self.tray.setToolTip(build_tooltip(self.latest_snapshot))

    def _on_menu_about_to_show(self) -> None:
        self.menu_open = True
        self._render_menu()

    def _on_menu_about_to_hide(self) -> None:
        self.menu_open = False
        self._apply_snapshot()

    def _render_menu(self) -> None:
        snapshot = self.latest_snapshot
        self.menu.clear()
        title = self.menu.addAction("AgentDiode")
        title.setEnabled(False)
        self.menu.addSeparator()
        if snapshot is None:
            connecting = self.menu.addAction("Connecting to daemon…")
            connecting.setEnabled(False)
        else:
            sessions = snapshot.get("sessions", [])
            if not sessions:
                empty = self.menu.addAction("No sessions")
                empty.setEnabled(False)
            for item in sessions:
                label = f"{item['agent_name']} — {item['state'].replace('_', ' ').upper()}"
                submenu = self.menu.addMenu(label)
                subtitle = submenu.addAction(
                    f"{item['project_name'] or '-'} · {duration(item['duration_seconds'])}"
                )
                subtitle.setEnabled(False)
                submenu.addSeparator()
                details = submenu.addAction("Open details")
                details.triggered.connect(
                    lambda _checked=False, value=item: self.show_details(value)
                )
                if item.get("cwd"):
                    open_folder = submenu.addAction("Open project folder")
                    open_folder.triggered.connect(
                        lambda _checked=False, value=item["cwd"]: QDesktopServices.openUrl(
                            QUrl.fromLocalFile(value)
                        )
                    )
                    copy_path = submenu.addAction("Copy project path")
                    copy_path.triggered.connect(
                        lambda _checked=False, value=item["cwd"]: self.app.clipboard().setText(
                            value
                        )
                    )
                if item["state"] not in {"completed", "error", "idle"}:
                    complete = submenu.addAction("Mark completed")
                    complete.triggered.connect(
                        lambda _checked=False, value=item: self.session_event(value, "completed")
                    )
                if item["state"] in {"stale", "disconnected"}:
                    remove = submenu.addAction("Remove stale session")
                    remove.triggered.connect(
                        lambda _checked=False, value=item: self.session_event(value, "remove")
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
        if self.menu_open:
            return
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
    for family in ("Noto Sans", "DejaVu Sans", "SF Pro Text", "Helvetica Neue"):
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
