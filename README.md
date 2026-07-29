<p align="center">
  <img src="docs/assets/agentdiode-header.webp" alt="AgentDiode" width="1000">
</p>

AgentDiode is a lightweight, local-first desktop utility that shows the live
status of AI coding agents in the system tray — the KDE Plasma tray on Linux,
or the menu bar on macOS.

It answers a simple question after you switch away from a terminal or editor:
is the agent still working, waiting for you, finished, or broken?

![License](https://img.shields.io/badge/license-MIT-yellow)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Platform](https://img.shields.io/badge/platform-KDE%20Plasma%206%20%7C%20macOS%2026%2B-F85149)

## Features

- Native KDE-compatible Qt system tray indicator
- Multiple concurrent agent sessions
- Animated status LED with accessible text tooltips
- Running, input, approval, completed, error, stale and disconnected states
- Official Codex lifecycle-hook integration
- Generic command wrapper for arbitrary CLI agents
- Optional VS Code companion extension
- Local SQLite history with JSON and CSV export
- Desktop notifications
- PID reuse protection and daemon restart reconciliation
- User-level systemd services
- No telemetry, cloud account, prompt storage or source-code storage

## Status indicators

| Preview | State |
|:---:|---|
| <img src="docs/assets/status/dim-gray.webp" alt="Dim gray" width="22"> | No active agents |
| <img src="docs/assets/status/pulsing-blue.webp" alt="Pulsing blue" width="22"> | Running |
| <img src="docs/assets/status/blinking-yellow.webp" alt="Blinking yellow" width="22"> | Waiting for input |
| <img src="docs/assets/status/blinking-violet.webp" alt="Blinking violet" width="22"> | Waiting for approval |
| <img src="docs/assets/status/green-temporarily.webp" alt="Green temporarily" width="22"> | Completed |
| <img src="docs/assets/status/red.webp" alt="Red" width="22"> | Error |
| <img src="docs/assets/status/muted-orange.webp" alt="Muted orange" width="22"> | Stale or disconnected |

When sessions have different states, AgentDiode displays the highest-priority
state while keeping every session visible in the tray menu.

## Screenshots

| Hover status | Tray menu |
|:---:|:---:|
| <img src="docs/assets/tray-hover.webp" alt="AgentDiode hover status showing active agents" width="421"> | <img src="docs/assets/tray-menu.webp" alt="AgentDiode tray menu showing agent sessions" width="281"> |

## Requirements

**Linux**

- KDE Plasma 6
- Wayland or X11
- Python 3.11 or newer
- systemd user services
- `notify-send` for notification fallback

**macOS**

- macOS 26 (Tahoe) or macOS 27 or newer
- Python 3.11 or newer
- launchd (built in; used for the user agents instead of systemd)
- `osascript` (built in) or `terminal-notifier` for notifications

The installer creates an isolated virtual environment. It does not modify the
system Python and does not require root access.

## Install

```bash
git clone https://github.com/emreartz/AgentDiode.git
cd AgentDiode
./install.sh
agentdiode doctor
agentdiode status
```

`install.sh` detects the host OS automatically. On Linux it registers
`systemd --user` services and a `.desktop` launcher; on macOS it registers
`~/Library/LaunchAgents` agents and the tray runs from the menu bar instead of
a `.desktop` entry. Pass `--no-start` to install without starting the
background services.

Set up Codex:

```bash
agentdiode integrations setup --codex
```

Start a new Codex session, run `/hooks`, review the AgentDiode callback path and
trust the hooks. Existing Codex processes must be restarted because lifecycle
hooks are loaded when the process starts.

Set up Claude Code and Antigravity CLI:

```bash
agentdiode integrations setup --claude
agentdiode integrations setup --antigravity
```

Restart each CLI after setup. AgentDiode uses official lifecycle hooks and
preserves unrelated settings in both configuration files.

## Usage

Inspect the current state:

```bash
agentdiode status
agentdiode sessions
agentdiode history
```

Emit an event from a custom integration:

```bash
agentdiode emit \
  --agent custom \
  --session build-agent-1 \
  --state running \
  --cwd "$PWD"
```

Wrap any command:

```bash
agentdiode run --agent custom --name "My Agent" -- my-agent-command
```

The wrapper preserves the child exit code and records success or failure.

Export history:

```bash
agentdiode history --export history.json
agentdiode history --export history.csv
```

Diagnostics and logs:

```bash
agentdiode doctor
agentdiode integrations
agentdiode logs
agentdiode logs --follow
```

## Integration reliability

AgentDiode never presents inferred state as guaranteed fact.

| Integration | Current support | Reliability |
|---|---|---|
| Codex CLI | Official lifecycle hooks | Partial |
| Generic CLI | Process start and exit | Partial |
| VS Code | Optional explicit lifecycle commands | Partial |
| Claude Code | Official lifecycle hooks | Partial |
| Antigravity CLI (`agy`) | Official lifecycle hooks | Partial |

Codex is marked partial because official hooks reliably expose start, running,
approval and completion events, but the tested release has no dedicated event
for every situation where a turn is waiting for a user answer.

Claude Code is integrated through `SessionStart`, `UserPromptSubmit`,
`PermissionRequest`, `Notification`, `Stop` and related official events.
Antigravity uses `PreInvocation`, `PostInvocation`, `PreToolUse`,
`PostToolUse`, and `Stop`. Its current hook API does not expose a dedicated
permission-wait event. Callback parsers retain only allowlisted operational
metadata.

See [integration details](docs/integrations.md).

## Privacy

AgentDiode runs locally and uses no network service at runtime. By default it
does not store:

- prompts or assistant messages;
- source or generated code;
- chat transcripts;
- tool arguments or output;
- API keys, tokens or environment dumps.

The Codex callback forwards only allowlisted operational metadata over a
user-only Unix socket. See the full [privacy policy](docs/privacy.md).

## Architecture

```text
Agent hooks / CLI / VS Code
             │
             │ JSON Lines over a user-only Unix socket
             ▼
      AgentDiode daemon
       │      │      │
       │      │      └── Desktop notifications
       │      └───────── SQLite history
       └──────────────── Tray client
```

The daemon and tray are separate processes. A tray crash does not stop session
tracking. The runtime directory is mode `0700` and the socket is mode `0600`.

More detail: [architecture](docs/architecture.md) and
[protocol](docs/protocol.md).

## Configuration

Configuration follows XDG standards:

```text
~/.config/agentdiode/config.toml
```

Examples:

```bash
agentdiode config
agentdiode config general.stale_timeout_seconds 600
agentdiode config notifications.enabled false
```

AgentDiode validates changes and edits only the requested key instead of
replacing the entire file.

## Uninstall

Remove AgentDiode while preserving history:

```bash
./uninstall.sh --keep-data
```

Remove history after an explicit confirmation:

```bash
./uninstall.sh --remove-data
```

By default this also removes the Codex/Claude Code/Antigravity lifecycle
hooks it installed (only its own `agentdiode-*` hook entries; unrelated
hooks and settings are preserved). Pass `--keep-integrations` to leave the
hooks in place instead.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,tray]'
./scripts/run-tests.sh
```

VS Code companion:

```bash
cd integrations/vscode-agentdiode
npm install
npm run check
npm run compile
```

The automated quality gate runs pytest, Ruff and strict mypy checks. See
[development](docs/development.md) and [manual testing](docs/manual-testing.md).

## Project documentation

- [Architecture](docs/architecture.md)
- [Event protocol](docs/protocol.md)
- [Integrations](docs/integrations.md)
- [Privacy](docs/privacy.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Development](docs/development.md)
- [Changelog](CHANGELOG.md)

## Contributing

Bug reports and focused pull requests are welcome. Read
[CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.

## License

AgentDiode is available under the [MIT License](LICENSE).
