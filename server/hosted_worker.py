"""Process-isolated lifecycle management for hot game workers."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Literal
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from dnd.core.content.identities import validate_sha256


class HostedWorkerError(RuntimeError):
    """Raised when a hosted game worker cannot be started or contacted."""


class HostedWorkerState(str, Enum):
    """Lifecycle state of one isolated game worker."""

    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class HostedWorkerPlacement(BaseModel):
    """Serializable placement metadata for one hot game worker."""

    hosted_game_id: UUID = Field(description="Gateway identity of the hosted game.")
    worker_instance_id: UUID = Field(description="Identity of this worker process generation.")
    process_id: int = Field(gt=0, description="Operating-system process identifier.")
    process_group_id: int = Field(gt=0, description="Dedicated process-group identifier.")
    socket_path: str = Field(description="Private Unix-domain socket path.")
    state: HostedWorkerState = Field(description="Current worker lifecycle state.")
    started_at: float = Field(description="Unix timestamp when worker spawning began.")
    ready_at: float | None = Field(default=None, description="Unix timestamp when readiness succeeded.")
    return_code: int | None = Field(default=None, description="Process return code after exit.")


class HostedWorkerAssignment(BaseModel):
    """Runtime identity assigned to a ready, unclaimed worker."""

    hosted_game_id: UUID = Field(description="Gateway game identity assigned to the worker.")
    public_game_base_url: str = Field(
        min_length=1,
        description="Public gateway runtime URL used by external controllers.",
    )
    character_deployments: tuple[CharacterDeploymentSnapshot, ...] = Field(
        default=(),
        description=(
            "Gateway-authenticated character revisions pinned before game "
            "creation; never accepted from a player runtime route."
        ),
    )
    worker_instance_id: UUID = Field(
        description="Exact process-generation identity writing terminal evidence.",
    )
    worker_generation: int = Field(
        default=1,
        ge=1,
        description="Monotonic directory generation fenced into terminal evidence.",
    )
    terminal_runtime_directory: str = Field(
        min_length=1,
        description="Gateway-owned private directory for durable terminal files.",
    )


class HostedWorkerReadiness(BaseModel):
    """Private worker identity checked before admission to the warm pool."""

    status: Literal["ready", "content_mismatch"] = "ready"
    content_set_digest: str = Field(min_length=64, max_length=64)
    expected_content_set_digest: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )


@dataclass
class _HostedWorkerHandle:
    """Runtime-only process handle paired with serializable placement."""

    process: asyncio.subprocess.Process
    placement: HostedWorkerPlacement


@dataclass(frozen=True)
class HostedWorkerApplication:
    """Dependency-neutral ASGI composition selected by a deployment root."""

    import_path: str

    def __post_init__(self) -> None:
        module_name, separator, attribute_name = self.import_path.partition(":")
        if (
            not separator
            or not module_name
            or not attribute_name
            or any(
                not segment.isidentifier()
                for segment in module_name.split(".")
            )
            or not attribute_name.isidentifier()
        ):
            raise ValueError(
                "Hosted worker application must use a Python module:attribute "
                f"import path, received {self.import_path!r}"
            )


CORE_HOSTED_WORKER_APPLICATION = HostedWorkerApplication(
    import_path="server.event_server:app",
)


class HostedWorkerManager:
    """Spawn and supervise one unchanged event-server process per game."""

    def __init__(
        self,
        runtime_root: Path,
        *,
        socket_root: Path | None = None,
        worker_cwd: Path | None = None,
        worker_application: HostedWorkerApplication = CORE_HOSTED_WORKER_APPLICATION,
        expected_content_set_digest: str | None = None,
        startup_timeout_seconds: float = 60.0,
        terminate_grace_seconds: float = 2.0,
        warm_pool_size: int = 0,
    ) -> None:
        """Create an empty hosted-worker manager.

        Args:
            runtime_root: Directory containing private sockets and worker logs.
            socket_root: Short local directory for Unix-domain sockets. Linux
                limits the complete socket path to approximately 108 bytes.
            worker_cwd: Repository root used as the worker working directory.
            worker_application: Explicit ASGI composition imported by each
                worker process.
            expected_content_set_digest: Exact parent-frozen content identity.
                When omitted, the manager resolves it through the same shared
                bootstrap before spawning any worker.
            startup_timeout_seconds: Maximum wait for worker readiness.
            terminate_grace_seconds: Grace period before forced process-group kill.
            warm_pool_size: Number of imported, unclaimed workers kept ready.
        """
        self._runtime_root = runtime_root.resolve()
        self._socket_root = (
            socket_root or Path(f"/tmp/dnd-engine-workers-{os.getuid()}")
        ).resolve()
        self._worker_cwd = (worker_cwd or Path(__file__).resolve().parents[1]).resolve()
        self._worker_application = worker_application
        self._expected_content_set_digest = validate_sha256(
            (
                bootstrap_content_system().content_set_digest
                if expected_content_set_digest is None
                else expected_content_set_digest
            ),
            "expected_content_set_digest",
        )
        self._startup_timeout_seconds = startup_timeout_seconds
        self._terminate_grace_seconds = terminate_grace_seconds
        self._warm_pool_size = max(0, warm_pool_size)
        self._workers: dict[UUID, _HostedWorkerHandle] = {}
        self._warm_workers: list[_HostedWorkerHandle] = []
        self._lock = asyncio.Lock()
        self._prewarm_lock = asyncio.Lock()
        self._replenishment_task: asyncio.Task[None] | None = None
        self._closing = False

    @property
    def expected_content_set_digest(self) -> str:
        """Return the exact content identity required from every worker."""
        return self._expected_content_set_digest

    @property
    def application_import_path(self) -> str:
        """Return the exact ASGI application imported by worker processes."""
        return self._worker_application.import_path

    def runtime_directory(self, hosted_game_id: UUID) -> Path:
        """Return the durable private runtime directory for one game."""

        return self._runtime_root / str(hosted_game_id)

    async def prewarm(self) -> None:
        """Fill the configured warm-worker pool before games are requested."""
        if self._warm_pool_size == 0 or self._closing:
            return
        async with self._prewarm_lock:
            while not self._closing:
                async with self._lock:
                    self._discard_stopped_warm_workers()
                    missing = self._warm_pool_size - len(self._warm_workers)
                if missing <= 0:
                    return
                reservation_id = uuid4()
                handle = await self._spawn_worker(reservation_id)
                async with self._lock:
                    if self._closing:
                        keep_handle = False
                    else:
                        self._warm_workers.append(handle)
                        keep_handle = True
                if not keep_handle:
                    await self._stop_handle(handle)
                    return

    async def start(
        self,
        hosted_game_id: UUID,
        *,
        public_game_base_url: str,
        character_deployments: tuple[
            CharacterDeploymentSnapshot,
            ...,
        ] = (),
    ) -> HostedWorkerPlacement:
        """Start one event-server worker and wait for private readiness.

        Args:
            hosted_game_id: Stable gateway game identity.
            public_game_base_url: Gateway runtime URL used by external agents.

        Returns:
            Ready worker placement.

        Raises:
            HostedWorkerError: If the game already has a live worker or startup
                does not reach readiness.
        """
        if os.name == "nt":
            raise HostedWorkerError("Hosted workers require Unix-domain sockets")

        async with self._lock:
            existing = self._workers.get(hosted_game_id)
            if existing is not None and existing.process.returncode is None:
                raise HostedWorkerError(f"Game {hosted_game_id} already has a live worker")
            self._discard_stopped_warm_workers()
            handle = self._warm_workers.pop(0) if self._warm_workers else None
            if handle is not None:
                handle.placement.hosted_game_id = hosted_game_id
                self._workers[hosted_game_id] = handle

        try:
            if handle is None:
                handle = await self._spawn_worker(hosted_game_id)
                async with self._lock:
                    self._workers[hosted_game_id] = handle
            self.runtime_directory(hosted_game_id).mkdir(
                parents=True,
                exist_ok=True,
            )
            await self._configure_worker(
                handle,
                HostedWorkerAssignment(
                    hosted_game_id=hosted_game_id,
                    public_game_base_url=public_game_base_url.rstrip("/"),
                    character_deployments=character_deployments,
                    worker_instance_id=handle.placement.worker_instance_id,
                    worker_generation=1,
                    terminal_runtime_directory=str(
                        self.runtime_directory(hosted_game_id),
                    ),
                ),
            )
        except BaseException:
            await self.stop(hosted_game_id)
            raise
        finally:
            self._schedule_replenishment()
        return handle.placement.model_copy(deep=True)

    def placement(self, hosted_game_id: UUID) -> HostedWorkerPlacement | None:
        """Return current placement without consulting persistent storage."""
        handle = self._workers.get(hosted_game_id)
        if handle is None:
            return None
        if handle.process.returncode is not None:
            handle.placement.state = HostedWorkerState.STOPPED
            handle.placement.return_code = handle.process.returncode
        return handle.placement.model_copy(deep=True)

    def active_game_ids(self) -> tuple[UUID, ...]:
        """Return games with live worker processes owned by this manager."""
        return tuple(
            game_id
            for game_id, handle in self._workers.items()
            if handle.process.returncode is None
        )

    def warm_worker_count(self) -> int:
        """Return the number of live, imported workers awaiting assignment."""
        self._discard_stopped_warm_workers()
        return len(self._warm_workers)

    def socket_path(self, hosted_game_id: UUID) -> Path:
        """Return the private socket path for a live worker."""
        handle = self._workers.get(hosted_game_id)
        if handle is None or handle.process.returncode is not None:
            raise HostedWorkerError(f"Game {hosted_game_id} has no live worker")
        return Path(handle.placement.socket_path)

    @contextlib.asynccontextmanager
    async def client(
        self,
        hosted_game_id: UUID,
        *,
        timeout: httpx.Timeout | float | None = 30.0,
    ) -> AsyncIterator[httpx.AsyncClient]:
        """Yield an HTTP client connected directly to one worker socket."""
        transport = httpx.AsyncHTTPTransport(uds=str(self.socket_path(hosted_game_id)))
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://game-worker",
            timeout=timeout,
        ) as client:
            yield client

    async def stop(self, hosted_game_id: UUID) -> HostedWorkerPlacement | None:
        """Terminate a worker and every descendant in its process group."""
        async with self._lock:
            handle = self._workers.pop(hosted_game_id, None)
        if handle is None:
            return None

        await self._stop_handle(handle)
        return handle.placement.model_copy(deep=True)

    async def stop_all(self) -> None:
        """Stop all workers currently owned by this manager."""
        self._closing = True
        replenishment = self._replenishment_task
        self._replenishment_task = None
        if replenishment is not None:
            replenishment.cancel()
            await asyncio.gather(replenishment, return_exceptions=True)
        for hosted_game_id in list(self._workers):
            await self.stop(hosted_game_id)

        async with self._lock:
            warm_workers = tuple(self._warm_workers)
            self._warm_workers.clear()
        for handle in warm_workers:
            await self._stop_handle(handle)

    async def _spawn_worker(
        self,
        hosted_game_id: UUID,
    ) -> _HostedWorkerHandle:
        """Spawn one worker process and wait until its private API is ready."""
        game_dir = self._runtime_root / str(hosted_game_id)
        game_dir.mkdir(parents=True, exist_ok=True)
        self._socket_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._socket_root.chmod(0o700)
        socket_path = self._socket_root / f"{hosted_game_id.hex}.sock"
        if len(os.fsencode(socket_path)) >= 104:
            raise HostedWorkerError(f"Unix-domain socket path is too long: {socket_path}")
        socket_path.unlink(missing_ok=True)
        stdout_path = game_dir / "stdout.log"
        stderr_path = game_dir / "stderr.log"
        started_at = time.time()
        worker_instance_id = uuid4()
        environment = os.environ.copy()
        environment.update({
            "PYTHONUNBUFFERED": "1",
            "DND_GAME_WORKER": "1",
            "DND_WORKER_UNIX_SOCKET": str(socket_path),
            "DND_EXPECTED_CONTENT_SET_DIGEST": (
                self._expected_content_set_digest
            ),
        })
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            self._worker_application.import_path,
            "--uds",
            str(socket_path),
            "--log-level",
            "warning",
            "--no-access-log",
        ]
        with stdout_path.open("ab") as stdout_stream, stderr_path.open("ab") as stderr_stream:
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    cwd=str(self._worker_cwd),
                    env=environment,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                    start_new_session=True,
                )
            except OSError as exc:
                raise HostedWorkerError(f"Unable to spawn worker: {exc}") from exc
        handle = _HostedWorkerHandle(
            process=process,
            placement=HostedWorkerPlacement(
                hosted_game_id=hosted_game_id,
                worker_instance_id=worker_instance_id,
                process_id=process.pid,
                process_group_id=process.pid,
                socket_path=str(socket_path),
                state=HostedWorkerState.STARTING,
                started_at=started_at,
            ),
        )
        try:
            await self._wait_until_ready(handle)
        except BaseException:
            await self._stop_handle(handle)
            raise
        return handle

    async def _configure_worker(
        self,
        handle: _HostedWorkerHandle,
        assignment: HostedWorkerAssignment,
    ) -> None:
        """Assign game identity and public routing to a ready worker."""
        async with self._client_for_handle(handle, timeout=2.0) as client:
            response = await client.post(
                "/hosted/configure",
                json=assignment.model_dump(mode="json"),
            )
        if response.status_code != 200:
            raise HostedWorkerError(
                f"Worker assignment failed with HTTP {response.status_code}: {response.text}"
            )

    def _schedule_replenishment(self) -> None:
        """Restore the warm-worker reserve without delaying game creation."""
        if self._warm_pool_size == 0 or self._closing:
            return
        if self._replenishment_task is not None and not self._replenishment_task.done():
            return
        self._replenishment_task = asyncio.create_task(self.prewarm())

    def _discard_stopped_warm_workers(self) -> None:
        """Remove dead reserve processes before calculating pool capacity."""
        live: list[_HostedWorkerHandle] = []
        for handle in self._warm_workers:
            if handle.process.returncode is None:
                live.append(handle)
            else:
                Path(handle.placement.socket_path).unlink(missing_ok=True)
        self._warm_workers = live

    @contextlib.asynccontextmanager
    async def _client_for_handle(
        self,
        handle: _HostedWorkerHandle,
        *,
        timeout: httpx.Timeout | float | None,
    ) -> AsyncIterator[httpx.AsyncClient]:
        """Yield a private client for an assigned or reserve worker."""
        transport = httpx.AsyncHTTPTransport(uds=handle.placement.socket_path)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://game-worker",
            timeout=timeout,
        ) as client:
            yield client

    async def _stop_handle(self, handle: _HostedWorkerHandle) -> None:
        """Terminate one handle regardless of whether it has a game assignment."""
        handle.placement.state = HostedWorkerState.STOPPING
        if handle.process.returncode is None:
            await _terminate_process_group(
                handle.process,
                handle.placement.process_group_id,
                self._terminate_grace_seconds,
            )
        handle.placement.state = HostedWorkerState.STOPPED
        handle.placement.return_code = handle.process.returncode
        Path(handle.placement.socket_path).unlink(missing_ok=True)

    async def _wait_until_ready(self, handle: _HostedWorkerHandle) -> None:
        deadline = time.monotonic() + self._startup_timeout_seconds
        socket_path = Path(handle.placement.socket_path)
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if handle.process.returncode is not None:
                handle.placement.state = HostedWorkerState.FAILED
                handle.placement.return_code = handle.process.returncode
                raise HostedWorkerError(
                    f"Worker exited during startup with code {handle.process.returncode}"
                )
            if socket_path.exists():
                try:
                    async with self._client_for_handle(handle, timeout=0.5) as client:
                        status_response = await client.get(
                            "/hosted/readiness",
                        )
                    if status_response.status_code == 200:
                        readiness = HostedWorkerReadiness.model_validate_json(
                            status_response.content,
                        )
                        if readiness.status == "content_mismatch":
                            raise HostedWorkerError(
                                "Worker content set mismatch: expected "
                                f"{self._expected_content_set_digest}, "
                                f"received {readiness.content_set_digest}",
                            )
                        if (
                            readiness.content_set_digest
                            != self._expected_content_set_digest
                        ):
                            raise HostedWorkerError(
                                "Worker content set mismatch: expected "
                                f"{self._expected_content_set_digest}, "
                                f"received {readiness.content_set_digest}",
                            )
                        handle.placement.state = HostedWorkerState.READY
                        handle.placement.ready_at = time.time()
                        return
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    last_error = exc
            await asyncio.sleep(0.025)

        handle.placement.state = HostedWorkerState.FAILED
        detail = f": {last_error}" if last_error is not None else ""
        raise HostedWorkerError(f"Worker readiness timed out{detail}")


def _process_group_exists(process_group_id: int) -> bool:
    """Return whether the operating system still knows a process group."""
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


async def _wait_for_process_group_exit(process_group_id: int, timeout: float) -> bool:
    """Wait for every member of a process group to exit."""
    deadline = time.monotonic() + timeout
    while _process_group_exists(process_group_id):
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(0.025)
    return True


async def _terminate_process_group(
    process: asyncio.subprocess.Process,
    process_group_id: int,
    grace_seconds: float,
) -> None:
    """Terminate a process group with TERM followed by KILL escalation."""
    try:
        os.killpg(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(asyncio.shield(process.wait()), timeout=grace_seconds)
    except asyncio.TimeoutError:
        pass
    if await _wait_for_process_group_exit(process_group_id, grace_seconds):
        return
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        return
    if process.returncode is None:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(process.wait()), timeout=grace_seconds)
    await _wait_for_process_group_exit(process_group_id, grace_seconds)
