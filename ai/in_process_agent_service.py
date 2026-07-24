"""Embedded subjective-policy service for the standalone game server.

This adapter owns the concrete AI implementation.  The core server sees only
the dependency-neutral managed-agent service contract, while every embedded
agent still observes and acts exclusively through the canonical subjective
HTTP/SSE protocol.
"""

from __future__ import annotations

import asyncio
from threading import Event as ThreadEvent, Lock, Thread
from time import monotonic
from typing import Optional, Protocol

from ai.external_agent import ExternalAgent
from ai.service_identity import EMBEDDED_SUBJECTIVE_SERVICE_ID
from ai.subjective.policy_agent import MAX_COMMANDS_PER_TURN
from ai.subjective.runtime_gc import PRESERVE_AUTOMATIC_GC
from server.agent_protocol.observation import SubjectiveWorldState
from server.agent_runtime.service import (
    AgentExecutionMode,
    AgentHandleStatus,
    AgentLaunchRequest,
    ManagedAgentHandle,
)


_POLICY_TURN_LOCK = Lock()
EMBEDDED_CONTROL_REQUEST_TIMEOUT_SECONDS = 3.0
EMBEDDED_AGENT_CLEANUP_TIMEOUT_SECONDS = 4.0


class EmbeddedExternalAgent(ExternalAgent):
    """External-policy transport with serialized shared-cache mutation."""

    def play_current_turn(
        self,
        max_commands: int = MAX_COMMANDS_PER_TURN,
        materialized: Optional[SubjectiveWorldState] = None,
    ) -> SubjectiveWorldState:
        """Run one complete turn while owning the shared policy cache."""
        with _POLICY_TURN_LOCK:
            return super().play_current_turn(max_commands, materialized)


class EmbeddedSubjectiveAgent(Protocol):
    """Concrete policy-loop lifecycle used by the thread adapter."""

    def run_forever(self) -> None:
        """Run until the subjective runtime closes or the encounter ends."""
        ...

    def request_stop(self) -> None:
        """Wake the policy loop without blocking."""
        ...

    def close(
        self,
        timeout_seconds: float = EMBEDDED_AGENT_CLEANUP_TIMEOUT_SECONDS,
    ) -> None:
        """Release runtime and policy resources."""
        ...


class EmbeddedSubjectiveAgentFactory(Protocol):
    """Construct an isolated policy instance for one server session."""

    def __call__(
        self,
        request: AgentLaunchRequest,
    ) -> EmbeddedSubjectiveAgent:
        """Create one agent bound to the request's subjective session."""
        ...


def create_embedded_subjective_agent(
    request: AgentLaunchRequest,
) -> EmbeddedSubjectiveAgent:
    """Build the bundled policy using the server-safe runtime GC policy."""
    if request.readiness_token is None:
        raise ValueError("Managed agent launch request has no readiness token")
    return EmbeddedExternalAgent(
        request.base_url.rstrip("/"),
        request.session_id,
        unix_socket_path=request.unix_socket_path,
        readiness_token=request.readiness_token,
        gc_policy=PRESERVE_AUTOMATIC_GC,
        control_request_timeout=EMBEDDED_CONTROL_REQUEST_TIMEOUT_SECONDS,
    )


class EmbeddedSubjectiveAgentHandle(ManagedAgentHandle):
    """One independently owned policy loop running in a managed thread."""

    def __init__(
        self,
        request: AgentLaunchRequest,
        factory: EmbeddedSubjectiveAgentFactory,
    ) -> None:
        self._request = request
        self._factory = factory
        self._state_lock = Lock()
        self._stop_requested = ThreadEvent()
        self._agent: EmbeddedSubjectiveAgent | None = None
        self._run_failure: str | None = None
        self._cleanup_failure: str | None = None
        self._thread = Thread(
            target=self._run,
            name=f"subjective-agent-{request.session_id}",
            daemon=True,
        )

    @property
    def session_id(self) -> str:
        """Return the exact subjective session controlled by this thread."""
        return self._request.session_id

    def start(self) -> None:
        """Start this handle exactly once."""
        self._thread.start()

    def status(self) -> AgentHandleStatus:
        """Return non-blocking thread lifecycle diagnostics."""
        with self._state_lock:
            failure_parts = tuple(
                part
                for part in (self._run_failure, self._cleanup_failure)
                if part is not None
            )
        return AgentHandleStatus(
            session_id=self.session_id,
            execution_mode=AgentExecutionMode.EMBEDDED_THREAD,
            running=self._thread.is_alive(),
            failure="; cleanup: ".join(failure_parts) if failure_parts else None,
        )

    def request_stop(self) -> None:
        """Signal the current or not-yet-constructed agent without joining."""
        self._stop_requested.set()
        with self._state_lock:
            agent = self._agent
        if agent is None:
            return
        try:
            agent.request_stop()
        except Exception as exc:
            self._record_failure(exc, cleanup=True)

    async def wait_stopped(self, timeout_seconds: float) -> None:
        """Join outside the event loop and fail if the policy thread survives."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        deadline = monotonic() + timeout_seconds
        await asyncio.to_thread(
            self._thread.join,
            max(0.0, deadline - monotonic()),
        )
        if self._thread.is_alive():
            raise TimeoutError(
                "Embedded subjective agent remained alive after cooperative stop"
            )
        with self._state_lock:
            cleanup_failure = self._cleanup_failure
            agent = self._agent
        if cleanup_failure is not None:
            if agent is None:
                raise RuntimeError(cleanup_failure)
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError(cleanup_failure)
            try:
                await asyncio.to_thread(agent.close, remaining)
            except BaseException as exc:
                self._record_failure(exc, cleanup=True)
                raise RuntimeError(str(exc)) from exc
            with self._state_lock:
                self._cleanup_failure = None
                self._agent = None

    def _run(self) -> None:
        """Own construction, execution, and cleanup inside one thread."""
        agent: EmbeddedSubjectiveAgent | None = None
        try:
            agent = self._factory(self._request)
            with self._state_lock:
                self._agent = agent
            if self._stop_requested.is_set():
                agent.request_stop()
            else:
                agent.run_forever()
        except BaseException as exc:
            self._record_failure(exc)
        finally:
            cleanup_succeeded = True
            if agent is not None:
                try:
                    agent.close(EMBEDDED_AGENT_CLEANUP_TIMEOUT_SECONDS)
                except BaseException as exc:
                    self._record_failure(exc, cleanup=True)
                    cleanup_succeeded = False
            with self._state_lock:
                if cleanup_succeeded:
                    self._agent = None

    def _record_failure(
        self,
        exc: BaseException,
        *,
        cleanup: bool = False,
    ) -> None:
        """Retain the first lifecycle failure for diagnostics."""
        failure = f"{type(exc).__name__}: {exc}"
        with self._state_lock:
            if cleanup:
                self._cleanup_failure = failure
            elif self._run_failure is None:
                self._run_failure = failure


class EmbeddedSubjectiveAgentService:
    """Register the bundled policy as the standalone embedded capability."""

    service_id = EMBEDDED_SUBJECTIVE_SERVICE_ID
    execution_mode = AgentExecutionMode.EMBEDDED_THREAD

    def __init__(
        self,
        factory: EmbeddedSubjectiveAgentFactory = create_embedded_subjective_agent,
    ) -> None:
        self._factory = factory

    def preflight(self, required_agents: int) -> None:
        """Validate the requested standalone policy capacity."""
        if required_agents <= 0:
            raise ValueError("required_agents must be positive")

    def start(self, request: AgentLaunchRequest) -> ManagedAgentHandle:
        """Start one fresh policy/runtime instance for one AI session."""
        handle = EmbeddedSubjectiveAgentHandle(request, self._factory)
        handle.start()
        return handle
