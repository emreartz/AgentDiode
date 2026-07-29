# Changelog

## Unreleased

- Added macOS 26 (Tahoe) and macOS 27 support: menu-bar tray, launchd user
  agents, `osascript`/`terminal-notifier` notifications, `$TMPDIR`-based
  runtime socket directory, `Library/Application Support` state directory,
  and `ps`-based process/PID-reuse detection.
- Fixed finished sessions (a closed terminal, a completed turn) piling up
  in the tray forever; they now disappear automatically, and sessions
  whose process is confirmed gone are removed outright instead of waiting
  for a manual "Remove stale session" click.
- Hardened `uninstall.sh` to only remove files/symlinks it can verify it
  owns, and to reject running with an unset or unsafe `HOME`.
- `uninstall.sh` now removes its Codex/Claude Code/Antigravity lifecycle
  hooks by default (`--restore-integrations` is now implied; pass
  `--keep-integrations` to opt out).

## 0.1.0

- Added Unix-socket daemon, CLI, SQLite history, stale detection and PID reuse protection.
- Added native KDE-compatible Qt tray, LED animation, menus, session details, settings and history.
- Added generic command wrapper and official Codex lifecycle-hook integration.
- Added privacy-safe notifications, diagnostics, logging, systemd units and home-directory installer.
- Added official-hook integrations for Claude Code and Antigravity CLI.
- Added a partial VS Code companion.
