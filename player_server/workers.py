"""Exclusive native-process leases; completed worlds are reset before reuse."""
import asyncio
from dataclasses import dataclass, field
import logging
from uuid import UUID

from player_server import connection
from player_server.config import ServiceLimits
from player_server.recording import Recording
from player_server.worker_protocol import EndGame

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Workers:
    limits: ServiceLimits = field(default_factory=ServiceLimits)
    idle: list[connection.Connection] = field(default_factory=list)
    count: int = 0
    closing: bool = False
    available: asyncio.Condition = field(default_factory=asyncio.Condition)


async def acquire(workers: Workers) -> connection.Connection:
    async with workers.available:
        await workers.available.wait_for(lambda: workers.closing or workers.idle
            or workers.count < workers.limits.max_workers)
        if workers.closing:
            raise RuntimeError('Worker service is closing')
        if workers.idle:
            return workers.idle.pop()
        workers.count += 1
    launch = asyncio.create_task(connection.launch())
    try:
        try:
            return await asyncio.shield(launch)
        except asyncio.CancelledError:
            # Subprocess creation can finish after its waiter is cancelled.
            process = await launch
            await connection.close(process)
            raise
    except BaseException:
        async with workers.available:
            workers.count -= 1
            workers.available.notify_all()
        raise


async def release(workers: Workers, process: connection.Connection, *,
                  clean: bool, epoch: UUID, recording: Recording, timeout: float) -> float | None:
    reusable = False
    elapsed = None
    try:
        if clean and not workers.closing and process.process.returncode is None:
            reply, staged, response = await asyncio.wait_for(connection.exchange(process,
                EndGame(game_epoch=epoch), recording), timeout)
            if (reply.ended_epoch != epoch or reply.publications or staged or response is not None
                    or reply.has_response or reply.needs_advance or reply.rejection or reply.query_error):
                raise RuntimeError('Native worker did not acknowledge clean retirement')
            reusable = True
            elapsed = reply.elapsed_ms
    except Exception:
        # The published prefix remains valid. Only reuse of this process failed.
        logger.exception('Discarding native worker after failed retirement')
    finally:
        async with workers.available:
            keep = reusable and not workers.closing and len(workers.idle) < workers.limits.idle_workers
            if keep:
                workers.idle.append(process)
                workers.available.notify_all()
        if not keep:
            try:
                await connection.close(process)
            finally:
                async with workers.available:
                    workers.count -= 1
                    workers.available.notify_all()
    return elapsed


async def shutdown(workers: Workers) -> None:
    """Called after game owners finish; queued acquisitions are also woken."""
    async with workers.available:
        workers.closing = True
        idle, workers.idle = workers.idle, []
        workers.available.notify_all()
    try:
        await asyncio.gather(*(connection.close(process) for process in idle))
    finally:
        workers.count -= len(idle)
