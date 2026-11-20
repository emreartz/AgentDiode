from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from agentdiode.tray.tooltip import duration


class SessionDialog(QDialog):
    def __init__(self, session: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"AgentDiode - {session['agent_name']}")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        values = (
            ("Agent", session["agent_name"]),
            ("State", session["state"].replace("_", " ").title()),
            ("Reliability", session["reliability"].title()),
            ("Project", session["project_name"] or "-"),
            ("Working directory", session["cwd"] or "-"),
            ("Session ID", session["session_id"]),
            ("Started", session["started_at"]),
            ("Last update", session["updated_at"]),
            ("Duration", duration(session["duration_seconds"])),
            ("PID", str(session.get("pid") or "-")),
            ("Parent PID", str(session.get("parent_pid") or "-")),
            ("Source", session["source"]),
            ("Error", session.get("error_message") or "-"),
        )
        for name, value in values:
            label = QLabel(str(value))
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setWordWrap(True)
            form.addRow(name, label)
        layout.addLayout(form)
        metadata = QPlainTextEdit(json.dumps(session.get("metadata", {}), indent=2))
        metadata.setReadOnly(True)
        metadata.setMaximumHeight(130)
        metadata.setAccessibleName("Session diagnostics metadata")
        layout.addWidget(QLabel("Diagnostics metadata"))
        layout.addWidget(metadata)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
