import os
from typing import Any

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from agentdiode.tray.application import TrayController, menu_signature


def fake_snapshot(count: int, *, flip: bool = False, elapsed: int = 0) -> dict[str, Any]:
    """`flip` changes every session's state (structure); `elapsed` only changes durations."""
    return {
        "overall_state": "running",
        "sessions": [
            {
                "session_id": f"s{index}",
                "agent_id": "codex",
                "agent_name": "Codex",
                "state": "stale" if (index % 2) != flip else "running",
                "reliability": "partial",
                "project_name": "demo",
                "cwd": "/tmp/demo",
                "duration_seconds": index + elapsed,
            }
            for index in range(count)
        ],
    }


def make_controller() -> TrayController:
    app = QApplication.instance() or QApplication([])
    controller = TrayController.__new__(TrayController)
    controller.app = app  # type: ignore[assignment]
    controller.tray = QSystemTrayIcon()
    controller.menu = QMenu()
    controller.latest_snapshot = {}
    controller._menu_signature = None
    controller._subtitles = {}
    return controller


def flush() -> None:
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def submenus(controller: TrayController) -> list[QMenu]:
    return controller.menu.findChildren(QMenu)


def subtitle_texts(controller: TrayController) -> list[str]:
    return [action.text() for action in controller._subtitles.values()]


def test_signature_ignores_durations_but_not_structure() -> None:
    assert menu_signature(fake_snapshot(3)) == menu_signature(fake_snapshot(3, elapsed=99))
    assert menu_signature(fake_snapshot(3)) != menu_signature(fake_snapshot(3, flip=True))
    assert menu_signature(fake_snapshot(3)) != menu_signature(fake_snapshot(2))
    changed = fake_snapshot(1)
    changed["sessions"][0]["cwd"] = "/elsewhere"
    assert menu_signature(fake_snapshot(1)) != menu_signature(changed)


def test_unchanged_structure_keeps_menu_objects_and_updates_durations() -> None:
    controller = make_controller()
    controller.update(fake_snapshot(5))
    before = submenus(controller)
    before_actions = controller.menu.actions()
    first_texts = subtitle_texts(controller)
    for tick in range(1, 50):
        controller.update(fake_snapshot(5, elapsed=tick * 60))
        flush()
    after = submenus(controller)
    assert len(after) == 5
    assert all(old is new for old, new in zip(before, after, strict=True))
    assert controller.menu.actions() == before_actions
    assert subtitle_texts(controller) != first_texts
    assert subtitle_texts(controller)[0] == "demo · 49:00"


def test_changed_structure_rebuilds_menu_without_leaking_submenus() -> None:
    controller = make_controller()
    for tick in range(200):
        controller.update(fake_snapshot(30, flip=bool(tick % 2)))
        flush()
    assert len(submenus(controller)) == 30
    controller.update(fake_snapshot(3))
    flush()
    assert len(submenus(controller)) == 3
    assert len(controller._subtitles) == 3
    controller.update(fake_snapshot(0))
    flush()
    assert submenus(controller) == []
    assert controller._subtitles == {}


def test_actions_use_latest_session_data_after_in_place_update() -> None:
    controller = make_controller()
    shown: list[dict[str, Any]] = []
    controller.show_details = shown.append  # type: ignore[method-assign]
    controller.update(fake_snapshot(2))
    controller.update(fake_snapshot(2, elapsed=600))  # same structure: no rebuild
    submenu = submenus(controller)[1]
    details = next(a for a in submenu.actions() if a.text() == "Open details")
    details.trigger()
    assert shown[0]["session_id"] == "s1"
    assert shown[0]["duration_seconds"] == 601
