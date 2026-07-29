from agentdiode.diagnostics import doctor


def test_session_check_reports_macos(monkeypatch) -> None:
    monkeypatch.setattr(doctor.sys, "platform", "darwin")
    check = doctor._session_check()
    assert check.ok is True
    assert check.detail == "macOS"


def test_display_check_reports_aqua_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(doctor.sys, "platform", "darwin")
    check = doctor._display_check()
    assert check.ok is True
    assert check.detail == "Aqua"


def test_notifications_check_prefers_terminal_notifier_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(doctor.sys, "platform", "darwin")
    monkeypatch.setattr(
        doctor.shutil,
        "which",
        lambda name: "/usr/local/bin/terminal-notifier" if name == "terminal-notifier" else None,
    )
    check = doctor._notifications_check()
    assert check.ok is True
    assert check.detail == "/usr/local/bin/terminal-notifier"


def test_notifications_check_falls_back_to_osascript_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(doctor.sys, "platform", "darwin")
    monkeypatch.setattr(
        doctor.shutil,
        "which",
        lambda name: "/usr/bin/osascript" if name == "osascript" else None,
    )
    check = doctor._notifications_check()
    assert check.ok is True
    assert check.detail == "/usr/bin/osascript"


def test_macos_version_check_flags_unsupported_release(monkeypatch) -> None:
    monkeypatch.setattr(doctor.sys, "platform", "darwin")
    monkeypatch.setattr(doctor.platform, "mac_ver", lambda: ("15.5", ("", "", ""), ""))
    check = doctor._macos_version_check()
    assert check is not None
    assert check.ok is False
    assert check.detail == "15.5"


def test_macos_version_check_accepts_supported_release(monkeypatch) -> None:
    monkeypatch.setattr(doctor.sys, "platform", "darwin")
    monkeypatch.setattr(doctor.platform, "mac_ver", lambda: ("27.0", ("", "", ""), ""))
    check = doctor._macos_version_check()
    assert check is not None
    assert check.ok is True


def test_macos_version_check_is_none_on_linux(monkeypatch) -> None:
    monkeypatch.setattr(doctor.sys, "platform", "linux")
    assert doctor._macos_version_check() is None
