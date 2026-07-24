"""Registered managed-agent service coordination and readiness ownership."""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import replace
from typing import Iterable, Sequence

from server.agent_runtime.service import (
    AgentHandleStatus,
    AgentLaunchRequest,
    ManagedAgentHandle,
    ManagedAgentService,
)


DEFAULT_AGENT_STARTUP_TIMEOUT_SECONDS = 15.0
DEFAULT_AGENT_READINESS_POLL_SECONDS = 0.02
DEFAULT_AGENT_STOP_TIMEOUT_SECONDS = 5.0


class AgentServiceUnavailableError(RuntimeError):
    """Raised when a route requests managed AI without a registered service."""


class AgentServiceStartError(RuntimeError):
    """Raised when a registered managed-agent service cannot start."""


class AgentServiceStopError(RuntimeError):
    """Raised when one or more managed-agent handles cannot be stopped."""


class ManagedAgentServiceManager:
    """Own service registration, readiness tokens, and session lifecycles."""

    def __init__(
        self,
        *,
        startup_timeout_seconds: float = DEFAULT_AGENT_STARTUP_TIMEOUT_SECONDS,
        readiness_poll_seconds: float = DEFAULT_AGENT_READINESS_POLL_SECONDS,
        stop_timeout_seconds: float = DEFAULT_AGENT_STOP_TIMEOUT_SECONDS,
    ) -> None:
        if startup_timeout_seconds <= 0:
            raise ValueError("startup_timeout_seconds must be positive")
        if readiness_poll_seconds <= 0:
            raise ValueError("readiness_poll_seconds must be positive")
        if stop_timeout_seconds <= 0:
            raise ValueError("stop_timeout_seconds must be positive")
        self._service: ManagedAgentService | None = None
        self._handles: dict[str, ManagedAgentHandle] = {}
        self._pending_readiness_tokens: dict[str, str] = {}
        self._ready_session_ids: set[str] = set()
        self._startup_timeout_seconds = startup_timeout_seconds
        self._readiness_poll_seconds = readiness_poll_seconds
        self._stop_timeout_seconds = stop_timeout_seconds

    @property
    def has_service(self) -> bool:
        """Return whether a concrete managed-agent service is registered."""
        return self._service is not None

    @property
    def service_id(self) -> str | None:
        """Return the registered service identity, if any."""
        return self._service.service_id if self._service is not None else None

    @property
    def execution_mode(self) -> str | None:
        """Return the registered placement mode, if any."""
        return (
            self._service.execution_mode.value
            if self._service is not None
            else None
        )

    def register_service(self, service: ManagedAgentService) -> None:
        """Register the sole managed-agent implementation for this server."""
        service_id = service.service_id.strip()
        if not service_id:
            raise ValueError("Managed-agent service_id must not be empty")
        if self._service is not None:
            raise RuntimeError(
                "A managed-agent service is already registered: "
                f"{self._service.service_id}"
            )
        self._service = service

    def unregister_service(self, service_id: str) -> None:
        """Stop all handles and remove the exact registered service."""
        service = self._service
        if service is None:
            raise AgentServiceUnavailableError(
                "No managed-agent service is registered"
            )
        if service.service_id != service_id:
            raise ValueError(
                f"Registered managed-agent service is {service.service_id!r}, "
                f"not {service_id!r}"
            )
        self.stop_all_blocking()
        self._pending_readiness_tokens.clear()
        self._ready_session_ids.clear()
        self._service = None

    def require_service(self, required_agents: int) -> ManagedAgentService:
        """Return the registered service after its capacity preflight."""
        if required_agents <= 0:
            raise ValueError("required_agents must be positive")
        service = self._service
        if service is None:
            raise AgentServiceUnavailableError(
                "This server has no registered managed-agent service"
            )
        service.preflight(required_agents)
        return service

    async def start_agents(
        self,
        requests: Sequence[AgentLaunchRequest],
    ) -> tuple[ManagedAgentHandle, ...]:
        """Start and authenticate one atomic batch of agent runtimes."""
        launch_requests = tuple(requests)
        if not launch_requests:
            return ()
        service = self.require_service(len(launch_requests))
        session_ids = tuple(request.session_id for request in launch_requests)
        if len(set(session_ids)) != len(session_ids):
            raise AgentServiceStartError(
                "Managed-agent launch batch contains duplicate sessions"
            )
        conflicts = [
            session_id
            for session_id in session_ids
            if (
                (handle := self._handles.get(session_id)) is not None
                and handle.status().running
            )
        ]
        if conflicts:
            raise AgentServiceStartError(
                "Managed agent already running for session(s): "
                + ", ".join(conflicts)
            )

        prepared_session_ids: list[str] = []
        started_handles: list[ManagedAgentHandle] = []
        try:
            for request in launch_requests:
                stale_handle = self._handles.get(request.session_id)
                if stale_handle is not None:
                    await self.stop_session(request.session_id)
                readiness_token = secrets.token_urlsafe(32)
                prepared_request = replace(
                    request,
                    readiness_token=readiness_token,
                )
                self._pending_readiness_tokens[request.session_id] = readiness_token
                self._ready_session_ids.discard(request.session_id)
                prepared_session_ids.append(request.session_id)
                handle = service.start(prepared_request)
                # The service has transferred ownership as soon as ``start``
                # returns. Track that exact handle before inspecting any of
                # its reported identity or status so validation failure still
                # has a concrete lifecycle target to stop and join.
                self._handles[request.session_id] = handle
                if handle.session_id != request.session_id:
                    raise AgentServiceStartError(
                        "Managed-agent service returned a handle for session "
                        f"{handle.session_id!r}, expected {request.session_id!r}"
                    )
                status = handle.status()
                if status.session_id != request.session_id:
                    raise AgentServiceStartError(
                        "Managed-agent handle status disagrees with its session identity"
                    )
                if status.execution_mode is not service.execution_mode:
                    raise AgentServiceStartError(
                        "Managed-agent handle execution mode disagrees with its service"
                    )
                if not status.running:
                    failure_detail = (
                        f": {status.failure}"
                        if status.failure is not None
                        else ""
                    )
                    raise AgentServiceStartError(
                        "Managed-agent service stopped during startup for session "
                        f"{request.session_id}{failure_detail}"
                    )
                started_handles.append(handle)
            await self._wait_until_ready(tuple(prepared_session_ids))
        except asyncio.CancelledError:
            cleanup_errors = await self._stop_sessions_collect(
                reversed(prepared_session_ids)
            )
            if cleanup_errors:
                raise AgentServiceStopError(
                    "Managed-agent start cancellation could not stop every handle: "
                    + "; ".join(cleanup_errors)
                )
            raise
        except Exception as exc:
            cleanup_errors = await self._stop_sessions_collect(
                reversed(prepared_session_ids)
            )
            if cleanup_errors:
                raise AgentServiceStartError(
                    f"{exc}; managed-agent rollback failed: "
                    + "; ".join(cleanup_errors)
                ) from exc
            if isinstance(exc, AgentServiceStartError):
                raise
            raise AgentServiceStartError(str(exc)) from exc
        return tuple(started_handles)

    def acknowledge_ready(self, session_id: str, readiness_token: str) -> bool:
        """Accept the exact one-time readiness token for a pending handle."""
        normalized_session_id = str(session_id)
        expected_token = self._pending_readiness_tokens.get(normalized_session_id)
        if expected_token is None or not secrets.compare_digest(
            expected_token,
            readiness_token,
        ):
            return False
        self._pending_readiness_tokens.pop(normalized_session_id, None)
        self._ready_session_ids.add(normalized_session_id)
        return True

    async def _wait_until_ready(self, session_ids: tuple[str, ...]) -> None:
        """Wait concurrently for one batch's readiness acknowledgements."""
        deadline = asyncio.get_running_loop().time() + self._startup_timeout_seconds
        while True:
            stopped_statuses: list[AgentHandleStatus] = []
            service = self._service
            if service is None:
                raise AgentServiceStartError(
                    "Managed-agent service was unregistered during startup"
                )
            for session_id in session_ids:
                handle = self._handles.get(session_id)
                if handle is None:
                    stopped_statuses.append(AgentHandleStatus(
                        session_id=session_id,
                        execution_mode=service.execution_mode,
                        running=False,
                        failure="service returned no tracked handle",
                    ))
                    continue
                status = handle.status()
                if not status.running:
                    stopped_statuses.append(status)
            if stopped_statuses:
                details = ", ".join(
                    (
                        status.session_id
                        + (f" ({status.failure})" if status.failure else "")
                    )
                    for status in stopped_statuses
                )
                raise AgentServiceStartError(
                    "Managed-agent service stopped before readiness for session(s): "
                    + details
                )
            pending = [
                session_id
                for session_id in session_ids
                if session_id not in self._ready_session_ids
            ]
            if not pending:
                return
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise AgentServiceStartError(
                    "Managed-agent service readiness timed out for session(s): "
                    + ", ".join(pending)
                )
            await asyncio.sleep(min(self._readiness_poll_seconds, remaining))

    async def stop_session(self, session_id: str) -> None:
        """Stop and join the managed handle for one session, if present."""
        normalized_session_id = str(session_id)
        handle = self._handles.get(normalized_session_id)
        if handle is None:
            self._clear_readiness(normalized_session_id)
            return
        handle.request_stop()
        try:
            await handle.wait_stopped(self._stop_timeout_seconds)
        except Exception as exc:
            raise AgentServiceStopError(
                "Failed to stop managed agent for session "
                f"{normalized_session_id}: {exc}"
            ) from exc
        status = handle.status()
        if status.running:
            raise AgentServiceStopError(
                "Managed agent remained alive after stop for session "
                f"{normalized_session_id}"
            )
        self._handles.pop(normalized_session_id, None)
        self._clear_readiness(normalized_session_id)

    def request_stop_all(self) -> None:
        """Signal every managed handle without blocking the caller."""
        for handle in tuple(self._handles.values()):
            handle.request_stop()

    async def stop_all(self) -> None:
        """Stop every managed handle without blocking the event loop."""
        handles = tuple(self._handles.items())
        for _session_id, handle in handles:
            handle.request_stop()
        results = await asyncio.gather(
            *(
                handle.wait_stopped(self._stop_timeout_seconds)
                for _session_id, handle in handles
            ),
            return_exceptions=True,
        )
        errors: list[str] = []
        for (session_id, handle), result in zip(handles, results):
            status = handle.status()
            if isinstance(result, BaseException):
                errors.append(f"{session_id}: {result}")
                continue
            if status.running:
                errors.append(f"{session_id}: handle remained alive")
                continue
            self._handles.pop(session_id, None)
            self._clear_readiness(session_id)
        if errors:
            raise AgentServiceStopError(
                "Failed to stop every managed agent: " + "; ".join(errors)
            )

    def stop_all_blocking(self) -> None:
        """Stop all handles from a synchronous composition or test boundary."""
        if not self._handles:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.stop_all())
            return
        raise RuntimeError(
            "stop_all_blocking cannot run on an event loop; await stop_all()"
        )

    async def _stop_sessions_collect(
        self,
        session_ids: Iterable[str],
    ) -> list[str]:
        """Attempt every requested stop and return session-scoped failures."""
        errors: list[str] = []
        for session_id in session_ids:
            try:
                await self.stop_session(session_id)
            except AgentServiceStopError as exc:
                errors.append(f"{session_id}: {exc}")
        return errors

    def _clear_readiness(self, session_id: str) -> None:
        """Forget pending and accepted readiness state for one session."""
        self._pending_readiness_tokens.pop(session_id, None)
        self._ready_session_ids.discard(session_id)

    def is_running(self, session_id: str) -> bool:
        """Return whether a managed handle is still alive."""
        handle = self._handles.get(str(session_id))
        return handle is not None and handle.status().running

    def is_ready(self, session_id: str) -> bool:
        """Return whether a live handle completed its service handshake."""
        normalized_session_id = str(session_id)
        return (
            normalized_session_id in self._ready_session_ids
            and self.is_running(normalized_session_id)
        )

    def running_session_ids(self) -> list[str]:
        """Return session ids for currently alive managed handles."""
        return [
            session_id
            for session_id, handle in self._handles.items()
            if handle.status().running
        ]

    def session_statuses(self) -> list[dict[str, int | bool | str | None]]:
        """Return diagnostics for every tracked managed handle."""
        rows: list[dict[str, int | bool | str | None]] = []
        for session_id, handle in self._handles.items():
            status: AgentHandleStatus = handle.status()
            rows.append({
                "session_id": session_id,
                "execution_mode": status.execution_mode.value,
                "running": status.running,
                "ready": self.is_ready(session_id),
                "process_id": status.process_id,
                "return_code": status.return_code,
                "failure": status.failure,
            })
        return rows
