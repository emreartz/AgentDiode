# Changelog

## Unreleased

- Fixed a tray memory leak: session submenus were never deleted when the menu was rebuilt on each poll.
- The daemon snapshot (used by the tray and `agentdiode status`/`sessions`) no longer includes
  completed sessions older than `completed_display_seconds`; they remain available in history.

## 0.1.0

- Added Unix-socket daemon, CLI, SQLite history, stale detection and PID reuse protection.
- Added native KDE-compatible Qt tray, LED animation, menus, session details, settings and history.
- Added generic command wrapper and official Codex lifecycle-hook integration.
- Added privacy-safe notifications, diagnostics, logging, systemd units and home-directory installer.
- Added official-hook integrations for Claude Code and Antigravity CLI.
- Added a partial VS Code companion.
