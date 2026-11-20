# Changelog

## 0.1.1

- Fixed a tray memory leak: session submenus were never deleted when the menu was rebuilt on each poll.
- The daemon snapshot (used by the tray and `agentdiode status`/`sessions`) no longer includes
  completed sessions older than `completed_display_seconds`; they remain available in history.
- Fixed remaining tray memory growth: the menu is rebuilt only when sessions or their states change,
  and durations are updated in place on each poll.
- Fixed tray memory growth on KDE Plasma caused by creating a new icon on every poll and blink frame;
  icons are now cached and the tray skips redundant icon and tooltip updates.
- Tray menu actions now always use the latest session data.
- Replaced em dashes in tray and dialog text with plain hyphens.
- The tray menu test is skipped when the optional PySide6 dependency is not installed.

## 0.1.0

- Added Unix-socket daemon, CLI, SQLite history, stale detection and PID reuse protection.
- Added native KDE-compatible Qt tray, LED animation, menus, session details, settings and history.
- Added generic command wrapper and official Codex lifecycle-hook integration.
- Added privacy-safe notifications, diagnostics, logging, systemd units and home-directory installer.
- Added official-hook integrations for Claude Code and Antigravity CLI.
- Added a partial VS Code companion.
