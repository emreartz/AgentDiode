from agentdiode.config import Config, NotificationConfig
from agentdiode.models import Session
from agentdiode.notifications.manager import NotificationManager, _osa_quote


def test_notifications_are_deduplicated(monkeypatch) -> None:
    manager = NotificationManager()
    manager.executable = None
    manager.terminal_notifier = None
    manager.osascript = None
    session = Session("one", "codex", "Codex", "completed")
    assert manager.notify(session) is False
    assert manager.notify(session) is False


def test_notifications_respect_configuration(monkeypatch) -> None:
    manager = NotificationManager()
    manager.executable = "/usr/bin/notify-send"
    monkeypatch.setattr(
        "agentdiode.notifications.manager.load_config",
        lambda: Config(notifications=NotificationConfig(enabled=False)),
    )
    called = False

    def unexpected_call(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("subprocess.Popen", unexpected_call)
    session = Session("disabled", "codex", "Codex", "completed")
    assert manager.notify(session) is False
    assert called is False


def test_osa_quote_escapes_quotes_and_backslashes() -> None:
    assert _osa_quote('say "hi"\\bye') == '"say \\"hi\\"\\\\bye"'


def test_macos_prefers_terminal_notifier_over_osascript() -> None:
    manager = NotificationManager()
    manager.executable = None
    manager.terminal_notifier = "/usr/local/bin/terminal-notifier"
    manager.osascript = "/usr/bin/osascript"
    command = manager._command("Codex completed", "my-project")
    assert command == [
        "/usr/local/bin/terminal-notifier",
        "-title",
        "AgentDiode",
        "-subtitle",
        "Codex completed",
        "-message",
        "my-project",
    ]


def test_macos_falls_back_to_osascript() -> None:
    manager = NotificationManager()
    manager.executable = None
    manager.terminal_notifier = None
    manager.osascript = "/usr/bin/osascript"
    command = manager._command("Codex completed", "my-project")
    assert command is not None
    assert command[0] == "/usr/bin/osascript"
    assert command[1] == "-e"
    assert '"Codex completed"' in command[2]
    assert '"my-project"' in command[2]


def test_notify_uses_macos_backend_when_notify_send_absent(monkeypatch) -> None:
    manager = NotificationManager()
    manager.executable = None
    manager.terminal_notifier = None
    manager.osascript = "/usr/bin/osascript"
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda command, **_kwargs: calls.append(command),
    )
    session = Session("mac-one", "codex", "Codex", "completed")
    assert manager.notify(session) is True
    assert calls and calls[0][0] == "/usr/bin/osascript"
