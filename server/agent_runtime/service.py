"""Dependency-neutral lifecycle contract for managed agent services."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class AgentExecutionMode(str, Enum):
    """Placement of one managed policy runtime."""

    EMBEDDED_THREAD = "embedded_thread"
    ISOLATED_PROCESS = "isolated_process"


@dataclass(frozen=True)
class AgentLaunchRequest:
    """Server facts needed to start one externally controlled AI session."""

    session_id: str
    base_url: str
    spawned_at: float
    unix_socket_path: str | None = None
    readiness_token: str | None = None


@dataclass(frozen=True)
class AgentHandleStatus:
    """Serializable diagnostics for one service-owned session handle."""

    session_id: str
    execution_mode: AgentExecutionMode
    running: bool
    process_id: int | None = None
    return_code: int | None = None
    failure: str | None = None


class ManagedAgentHandle(Protocol):
    """One live policy runtime owned by a registered service."""

    @property
    def session_id(self) -> str:
        """Return the exact server session controlled by this handle."""
        ...

    def status(self) -> AgentHandleStatus:
        """Return current non-blocking lifecycle diagnostics."""
        ...

    def request_stop(self) -> None:
        """Signal cooperative termination without waiting for completion."""
        ...

    async def wait_stopped(self, timeout_seconds: float) -> None:
        """Wait until the handle is stopped or raise on timeout/failure."""
        ...


class ManagedAgentService(Protocol):
    """AI-owned implementation registered with the core server."""

    service_id: str
    execution_mode: AgentExecutionMode

    def preflight(self, required_agents: int) -> None:
        """Validate capacity before the server replaces live game state."""
        ...

    def start(self, request: AgentLaunchRequest) -> ManagedAgentHandle:
        """Start one session runtime and return its lifecycle handle."""
        ...
