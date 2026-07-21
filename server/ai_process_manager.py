"""Subprocess lifecycle management for local external AI agents."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict
from uuid import UUID


class AIProcessStartError(RuntimeError):
    """Raised when an external AI subprocess cannot be started."""


class ExternalAIProcessManager:
    """Track and stop local AI subprocesses by session id."""

    def __init__(self) -> None:
        """Create an empty process manager."""
        self._processes: Dict[str, subprocess.Popen] = {}

    def start_external_agent(
        self,
        session_id: UUID | str,
        base_url: str,
    ) -> subprocess.Popen:
        """Start or replace the external agent for a session.

        Args:
            session_id: AI session id assigned by the game session.
            base_url: HTTP base URL the subprocess can use to reach the server.

        Returns:
            Started subprocess handle.

        Raises:
            AIProcessStartError: If the process cannot be spawned.
        """
        session_key = str(session_id)
        self.stop_session(session_key)

        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        command = [
            sys.executable,
            "-m",
            "ai.external_agent",
            "--base-url",
            base_url.rstrip("/"),
            "--session-id",
            session_key,
            "--spawned-at",
            str(time.time()),
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=str(repo_root),
                env=env,
                start_new_session=True,
            )
        except OSError as exc:
            raise AIProcessStartError(str(exc)) from exc

        self._processes[session_key] = process
        return process

    def stop_session(self, session_id: UUID | str) -> None:
        """Stop a tracked subprocess for one session, if present."""
        session_key = str(session_id)
        process = self._processes.pop(session_key, None)
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def stop_all(self) -> None:
        """Stop every tracked AI subprocess."""
        for session_id in list(self._processes):
            self.stop_session(session_id)

    def is_running(self, session_id: UUID | str) -> bool:
        """Return whether a tracked process is still alive."""
        process = self._processes.get(str(session_id))
        return process is not None and process.poll() is None

    def running_session_ids(self) -> list[str]:
        """Return session ids for currently alive tracked processes."""
        return [
            session_id for session_id, process in self._processes.items()
            if process.poll() is None
        ]

    def process_statuses(self) -> list[dict[str, int | bool | str | None]]:
        """Return status rows for every tracked subprocess."""
        return [
            {
                "session_id": session_id,
                "running": process.poll() is None,
                "returncode": process.poll(),
            }
            for session_id, process in self._processes.items()
        ]
