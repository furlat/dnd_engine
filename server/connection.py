"""Async bounded pipe I/O; the host never runs native mechanics."""
import asyncio
from collections import deque
from dataclasses import dataclass
import os
from pathlib import Path
import struct
import sys

from server.framing import MAX_PACKET_BYTES
from server.recording import Recording, discard_tails, stage_record
from server.worker_protocol import REQUEST_CODEC, Request, Reply


@dataclass(slots=True)
class Connection:
    process: asyncio.subprocess.Process
    diagnostics: deque[bytes]
    drain: asyncio.Task[None]


async def _drain(stream: asyncio.StreamReader, diagnostics: deque[bytes]) -> None:
    while chunk := await stream.read(1024):
        diagnostics.append(chunk)


async def launch() -> Connection:
    process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'server.worker',
        cwd=Path(__file__).resolve().parents[1], env=dict(os.environ, PYTHONUNBUFFERED='1'),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    assert process.stderr is not None
    diagnostics: deque[bytes] = deque(maxlen=64)
    return Connection(process, diagnostics, asyncio.create_task(_drain(process.stderr, diagnostics)))


async def _read(stream: asyncio.StreamReader) -> bytes:
    header = await stream.readexactly(4)
    size, = struct.unpack('!I', header)
    if size > MAX_PACKET_BYTES:
        raise ValueError('Native frame exceeded the protocol limit')
    return await stream.readexactly(size)


async def exchange(connection: Connection, request: Request, recording: Recording
                   ) -> tuple[Reply, dict[str, tuple[int, int]], bytes | None]:
    process = connection.process
    assert process.stdin is not None and process.stdout is not None
    payload = REQUEST_CODEC.dump_json(request)
    process.stdin.write(struct.pack('!I', len(payload)) + payload)
    await process.stdin.drain()
    staged = {}
    try:
        reply = Reply.model_validate_json(await _read(process.stdout))
        for publication in reply.publications:
            if publication.seat_id in staged:
                raise ValueError('Duplicate audience in publication batch')
            payload = await _read(process.stdout)
            staged[publication.seat_id] = await asyncio.to_thread(stage_record, recording,
                publication.seat_id, publication.cursor.sequence, payload)
        response = await _read(process.stdout) if reply.has_response else None
        return reply, staged, response
    except BaseException:
        await asyncio.to_thread(discard_tails, recording)
        raise


async def close(connection: Connection) -> None:
    closing = asyncio.create_task(_close(connection))
    try:
        await asyncio.shield(closing)
    except asyncio.CancelledError:
        await closing
        raise


async def _close(connection: Connection) -> None:
    process = connection.process
    if process.stdin is not None:
        process.stdin.close()
    try:
        await asyncio.wait_for(process.wait(), 3)
    except TimeoutError:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 1)
        except TimeoutError:
            process.kill()
            await process.wait()
    await connection.drain
