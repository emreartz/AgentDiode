# Troubleshooting

Run:

```bash
agentdiode doctor
agentdiode logs
```

Linux:

```bash
systemctl --user status agentdiode-daemon.service
systemctl --user status agentdiode-tray.service
```

macOS:

```bash
launchctl print gui/$(id -u)/io.agentdiode.daemon
launchctl print gui/$(id -u)/io.agentdiode.tray
```

If the CLI says the daemon is unavailable:

```bash
# Linux
systemctl --user restart agentdiode-daemon.service

# macOS
launchctl kickstart -k gui/$(id -u)/io.agentdiode.daemon
```

If Codex events do not appear, start a new Codex session, run `/hooks`, inspect
the AgentDiode entries and trust their current definitions. Codex hashes hook
definitions, so a changed callback path requires another review.

Wayland can prevent focusing an existing terminal/editor window. Opening a
project directory remains reliable.

Invalid configuration is reported rather than replaced. Move the invalid file
temporarily or correct the named value:

```text
~/.config/agentdiode/config.toml
```
