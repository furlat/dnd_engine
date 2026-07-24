"""Generic isolated-process adapter for the managed-agent service contract."""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Protocol

from server.agent_runtime.service import (
    AgentExecutionMode,
    AgentHandleStatus,
    AgentLaunchRequest,
    ManagedAgentHandle,
)


@dataclass(frozen=True)
class AgentProcessSpec:
    """Dependency-neutral process description supplied by an AI package."""

    argv: tuple[str, ...]
    cwd: Path

    def __post_init__(self) -> None:
        if not self.argv or not self.argv[0]:
            raise ValueError("Agent process argv must name an executable")
        if not self.cwd.is_dir():
            raise ValueError(f"Agent process cwd does not exist: {self.cwd}")


class AgentProcessSpecBuilder(Protocol):
    """AI-owned command builder consumed by the generic process adapter."""

    service_id: str

    def preflight(self, required_agents: int) -> None:
        """Validate that process specifications can be built."""
        ...

    def build_process_spec(self, request: AgentLaunchRequest) -> AgentProcessSpec:
        """Build one process specification without starting it."""
        ...


class SubprocessAgentHandle(ManagedAgentHandle):
    """One isolated process implementing a managed agent session."""

    def __init__(self, session_id: str, process: subprocess.Popen) -> None:
        self._session_id = str(session_id)
        self._process = process
        self._stop_requested = False
        self._stop_error: str | None = None

    @property
    def session_id(self) -> str:
        return self._session_id

    def status(self) -> AgentHandleStatus:
        return_code = self._process.poll()
        return AgentHandleStatus(
            session_id=self._session_id,
            execution_mode=AgentExecutionMode.ISOLATED_PROCESS,
            running=return_code is None,
            process_id=self._process.pid,
            return_code=return_code,
            failure=self._stop_error,
        )

    def request_stop(self) -> None:
        if self._stop_requested or self._process.poll() is not None:
            return
        self._stop_requested = True
        try:
            self._process.terminate()
        except Exception as exc:
            self._stop_error = str(exc)

    async def wait_stopped(self, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self._process.poll() is not None:
            self._stop_error = None
            return
        try:
            await asyncio.to_thread(self._wait_with_escalation, timeout_seconds)
        except Exception as exc:
            failure = str(exc)
            if self._stop_error is not None:
                failure = f"{self._stop_error}; {failure}"
            self._stop_error = failure
            raise RuntimeError(failure) from exc
        self._stop_error = None

    def _wait_with_escalation(self, timeout_seconds: float) -> None:
        deadline = monotonic() + timeout_seconds
        try:
            self._process.wait(timeout=self._remaining_seconds(deadline))
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=self._remaining_seconds(deadline))
        if self._process.poll() is None:
            raise RuntimeError("Agent process remained alive after kill escalation")

    @staticmethod
    def _remaining_seconds(deadline: float) -> float:
        return max(0.0, deadline - monotonic())


class SubprocessAgentService:
    """Adapt an AI-owned command builder to the neutral service lifecycle."""

    execution_mode = AgentExecutionMode.ISOLATED_PROCESS

    def __init__(self, builder: AgentProcessSpecBuilder) -> None:
        self._builder = builder
        self.service_id = builder.service_id

    def preflight(self, required_agents: int) -> None:
        self._builder.preflight(required_agents)

    def start(self, request: AgentLaunchRequest) -> ManagedAgentHandle:
        spec = self._builder.build_process_spec(request)
        environment = os.environ.copy()
        environment["PYTHONUNBUFFERED"] = "1"
        process = subprocess.Popen(
            list(spec.argv),
            cwd=str(spec.cwd),
            env=environment,
            start_new_session=os.environ.get("DND_GAME_WORKER") != "1",
        )
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                "Agent process exited during startup for session "
                f"{request.session_id} with code {return_code}"
            )
        return SubprocessAgentHandle(request.session_id, process)
