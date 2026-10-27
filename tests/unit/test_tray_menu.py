import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from agentdiode.tray.application import TrayController


def fake_snapshot(count: int) -> dict[str, object]:
    return {
        "overall_state": "running",
        "sessions": [
            {
                "session_id": f"s{index}",
                "agent_name": "Codex",
                "state": "stale" if index % 2 else "running",
                "project_name": "demo",
                "cwd": "/tmp/demo",
                "duration_seconds": index,
            }
            for index in range(count)
        ],
    }


def test_update_does_not_leak_submenus() -> None:
    app = QApplication.instance() or QApplication([])
    controller = TrayController.__new__(TrayController)
    controller.app = app
    controller.tray = QSystemTrayIcon()
    controller.menu = QMenu()
    snapshot = fake_snapshot(30)
    for _ in range(200):
        controller.update(snapshot)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert len(controller.menu.findChildren(QMenu)) == 30
    controller.update(fake_snapshot(3))
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert len(controller.menu.findChildren(QMenu)) == 3
