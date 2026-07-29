# Real integration checks

## Codex

```bash
agentdiode integrations setup --codex
# Linux
systemctl --user restart agentdiode-daemon.service
# macOS
launchctl kickstart -k gui/$(id -u)/io.agentdiode.daemon
codex
```

Inside Codex, use `/hooks` to trust AgentDiode, submit a task, trigger a
permission request, and finish the turn. Confirm `starting`, `running`,
`waiting_approval` and `completed` in the tray.

## Generic command

```bash
agentdiode run --agent custom --name "Sleep test" -- sleep 3
agentdiode run --agent custom --name "Failure test" -- sh -c 'exit 7'
```

The first must complete successfully; the second must retain exit status 7 and
produce an error session.

## Claude Code

```bash
agentdiode integrations setup --claude
claude --init-only
```

`--init-only` verifies settings parsing and the `SessionStart` callback without
a model call. Full prompt/permission/stop verification requires Claude access.

## Antigravity

```bash
agentdiode integrations setup --antigravity
agy
```

Use `/hooks` to inspect the registered callbacks, then run a small task and
verify running and completion transitions. Antigravity currently exposes no
dedicated permission-wait hook.
