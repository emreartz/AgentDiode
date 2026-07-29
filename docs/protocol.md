# Local protocol

AgentDiode listens on:

```text
$XDG_RUNTIME_DIR/agentdiode/agentdiode.sock
```

On macOS, where there is no `XDG_RUNTIME_DIR`/`/run/user` equivalent, it falls
back to `$TMPDIR/agentdiode/agentdiode.sock`. The directory is mode `0700` and
the socket mode is `0600`. Requests and
responses are UTF-8 JSON Lines. Protocol version 1 accepts lifecycle events:

```json
{
  "command": "event",
  "payload": {
    "protocol_version": 1,
    "event": "session.running",
    "timestamp": "2026-07-27T19:00:00+03:00",
    "agent_id": "custom",
    "session_id": "custom-123",
    "cwd": "/home/user/project",
    "reliability": "partial",
    "source": "example",
    "metadata": {}
  }
}
```

Payload size, identifiers, states, timestamps, PIDs, text fields, and metadata
size are validated. Unknown safe metadata is preserved.
