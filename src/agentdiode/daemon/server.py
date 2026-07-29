from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal

from agentdiode.config import load as load_config
from agentdiode.constants import MAX_LINE_BYTES
from agentdiode.daemon.session_manager import SessionManager
from agentdiode.logging_setup import configure_logging
from agentdiode.notifications.manager import NotificationManager
from agentdiode.paths import database_path, ensure_private_directory, socket_path
from agentdiode.protocol import ProtocolError, decode_event
from agentdiode.storage.database import Database

LOGGER = logging.getLogger("agentdiode.daemon")


class Server:
    def __init__(self) -> None:
        self.config = load_config()
        self.manager = SessionManager(Database(database_path()))
        self.manager.reconcile_startup()
        self.notifications = NotificationManager()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            if not line or len(line) > MAX_LINE_BYTES:
                raise ProtocolError("empty or oversized request")
            request = json.loads(line)
            command = request.get("command")
            if command == "snapshot":
                response = {
                    "ok": True,
                    **self.manager.snapshot(self.config.general.completed_display_seconds),
                }
            elif command == "history":
                limit = request.get("limit", 100)
                if not isinstance(limit, int) or not 1 <= limit <= 10000:
                    raise ProtocolError("history limit must be between 1 and 10000")
                response = {"ok": True, "sessions": self.manager.database.history(limit)}
            elif command == "event":
                event = decode_event(json.dumps(request.get("payload")).encode())
                session = self.manager.apply(event)
                if session is not None:
                    self.notifications.notify(session)
                response = {
                    "ok": True,
                    **self.manager.snapshot(self.config.general.completed_display_seconds),
                }
            else:
                raise ProtocolError("unknown command")
        except (ProtocolError, json.JSONDecodeError, TypeError) as exc:
            LOGGER.warning("Rejected request: %s", exc)
            response = {"ok": False, "error": str(exc)}
        writer.write(json.dumps(response).encode() + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def monitor_stale(self, stop: asyncio.Event) -> None:
        timeout_seconds = self.config.general.stale_timeout_seconds
        display_seconds = self.config.general.completed_display_seconds
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=min(30, timeout_seconds))
            except TimeoutError:
                changed = self.manager.mark_stale(timeout_seconds)
                for session in changed:
                    LOGGER.warning("Session %s became stale", session.session_id)
                removed = self.manager.prune_finished(display_seconds)
                for session_id in removed:
                    LOGGER.info("Session %s pruned (finished)", session_id)


async def serve() -> None:
    path = socket_path()
    ensure_private_directory(path.parent)
    if path.exists():
        path.unlink()
    app = Server()
    server = await asyncio.start_unix_server(app.handle, path=path)
    os.chmod(path, 0o600)
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    LOGGER.info("Listening on %s", path)
    monitor = asyncio.create_task(app.monitor_stale(stop))
    async with server:
        await stop.wait()
    await monitor
    path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(prog="agentdiode-daemon")
    parser.parse_args()
    configure_logging("daemon")
    asyncio.run(serve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
