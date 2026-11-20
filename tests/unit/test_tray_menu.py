import os
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from agentdiode.tray.application import TrayController, menu_signature
from agentdiode.tray.icon_renderer import render_icon


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
    controller._icon_key = ("idle", True)
    controller._tooltip = ""
    return controller


class RecordingTray:
    """Stands in for QSystemTrayIcon and records the calls the KDE backend reacts to."""

    def __init__(self) -> None:
        self.icons: list[Any] = []
        self.tooltips: list[str] = []

    def setIcon(self, icon: Any) -> None:
        self.icons.append(icon)

    def setToolTip(self, text: str) -> None:
        self.tooltips.append(text)


def recording_controller(state: str = "running") -> tuple[TrayController, RecordingTray]:
    controller = make_controller()
    tray = RecordingTray()
    controller.tray = tray  # type: ignore[assignment]
    controller.state = state
    controller.frame = True
    controller.config = SimpleNamespace(  # type: ignore[assignment]
        tray=SimpleNamespace(blink_running=True, blink_waiting=True)
    )
    return controller, tray


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


def test_render_icon_is_cached_per_state_brightness_and_size() -> None:
    QApplication.instance() or QApplication([])
    assert render_icon("running") is render_icon("running")
    assert render_icon("running", False) is render_icon("running", False)
    assert render_icon("running") is not render_icon("running", False)
    assert render_icon("running") is not render_icon("error")
    assert render_icon("running", True, 32) is not render_icon("running", True, 22)


def test_idle_polls_do_not_repeat_icon_or_tooltip_updates() -> None:
    controller, tray = recording_controller()
    idle = {"overall_state": "idle", "sessions": []}
    for _ in range(50):
        controller.update(idle)
    assert len(tray.icons) == 0  # the controller already shows the idle icon
    assert len(tray.tooltips) == 1
    controller.update({"overall_state": "idle", "sessions": []})
    assert (len(tray.icons), len(tray.tooltips)) == (0, 1)


def test_unchanged_state_sets_icon_once_but_tooltip_follows_durations() -> None:
    controller, tray = recording_controller()
    for tick in range(10):
        controller.update(fake_snapshot(2, elapsed=tick * 60))
    assert len(tray.icons) == 1  # idle -> running once, then never again
    assert len(tray.tooltips) == 10  # durations changed, so the tooltip must follow
    assert tray.tooltips[-1] != tray.tooltips[0]


def test_state_change_updates_icon_and_reuses_cached_objects() -> None:
    controller, tray = recording_controller()
    snapshot = fake_snapshot(1)
    controller.update(snapshot)
    controller.update({**snapshot, "overall_state": "error"})
    controller.update({**snapshot, "overall_state": "running"})
    controller.update({**snapshot, "overall_state": "error"})
    assert tray.icons[0] is render_icon("running", True)
    assert tray.icons[1] is render_icon("error", True)
    assert tray.icons[3] is tray.icons[1]  # same object, not a fresh QIcon


def test_blink_animation_still_alternates_cached_icons() -> None:
    controller, tray = recording_controller()
    controller.update(fake_snapshot(1))
    tray.icons.clear()
    for _ in range(4):
        controller.animate()
    assert tray.icons == [render_icon("running", False), render_icon("running", True)] * 2
    assert len({id(icon) for icon in tray.icons}) == 2


def test_poll_during_dim_blink_frame_restores_bright_icon() -> None:
    controller, tray = recording_controller()
    controller.update(fake_snapshot(1))
    controller.animate()  # dim frame
    controller.update(fake_snapshot(1, elapsed=5))
    assert tray.icons[-1] is render_icon("running", True)


def test_tooltip_cache_stays_coherent_after_error_tooltip() -> None:
    controller, tray = recording_controller()
    idle = {"overall_state": "idle", "sessions": []}
    controller.update(idle)
    controller._set_tooltip("AgentDiode\nInvalid daemon response")
    controller.update(idle)
    assert tray.tooltips[-1] == "AgentDiode\nNo active AI agents"
    assert len(tray.tooltips) == 3
