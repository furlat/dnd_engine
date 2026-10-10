"""Bounded pipe I/O for one isolated native process; polling never reads a pipe."""

from collections import deque
from dataclasses import dataclass
import os
from pathlib import Path
from queue import Empty, Full, Queue
import subprocess
import sys
from threading import Event, Thread

from game.runtime_protocol import (
    RuntimeRequest, RuntimeReply, REQUEST_CODEC, REPLY_CODEC, read_packet, write_packet,
)


@dataclass(frozen=True, slots=True)
class RuntimeFailure:
    message: str


@dataclass(slots=True)
class RuntimeConnection:
    process: subprocess.Popen[bytes]
    outbound: Queue[RuntimeRequest | None]
    inbound: Queue[RuntimeReply | RuntimeFailure]
    diagnostics: deque[bytes]
    stopped: Event
    reply_ready: Event
    io_thread: Thread
    stderr_thread: Thread
    pending: RuntimeRequest | None = None
    received_bytes: int = 0
    sent_bytes: int = 0


def _exchange(connection: RuntimeConnection) -> None:
    process = connection.process
    assert process.stdin is not None and process.stdout is not None
    try:
        while not connection.stopped.is_set():
            request = connection.outbound.get()
            if request is None:
                return
            payload = REQUEST_CODEC.dump_json(request)
            connection.sent_bytes += len(payload)
            write_packet(process.stdin, payload)
            payload = read_packet(process.stdout)
            if payload is None:
                raise EOFError("The encounter process closed unexpectedly")
            connection.received_bytes += len(payload)
            reply = REPLY_CODEC.validate_json(payload)
            if reply.request_id != request.request_id:
                raise ValueError("Native reply does not match its request")
            connection.inbound.put_nowait(reply)
            connection.reply_ready.set()
    except Exception as error:
        if not connection.stopped.is_set():
            connection.stopped.set()
            connection.stderr_thread.join(timeout=.1)
            connection.inbound.put_nowait(RuntimeFailure(str(error)))
            connection.reply_ready.set()
    finally:
        # This thread is the only pipe writer. On quit, finish any in-flight
        # exchange, then give the worker EOF so its native finally can run.
        process.stdin.close()


def _drain_diagnostics(connection: RuntimeConnection) -> None:
    assert connection.process.stderr is not None
    while chunk := connection.process.stderr.read(1024):
        connection.diagnostics.append(chunk)


def launch_runtime() -> RuntimeConnection:
    environment = dict(os.environ, PYGAME_HIDE_SUPPORT_PROMPT="1", PYTHONUNBUFFERED="1")
    process = subprocess.Popen([sys.executable, "-m", "game.runtime_worker"],
        cwd=Path(__file__).resolve().parents[1], env=environment,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Thread targets only perform transport/serialization. Native code lives in
    # the separately launched interpreter; no Session crosses this boundary.
    connection = RuntimeConnection(process, Queue(maxsize=1), Queue(maxsize=1),
        deque(maxlen=64), Event(), Event(), Thread(), Thread())
    connection.io_thread = Thread(target=_exchange, args=(connection,), daemon=True, name="native-pipe")
    connection.stderr_thread = Thread(target=_drain_diagnostics, args=(connection,), daemon=True, name="native-stderr")
    connection.io_thread.start()
    connection.stderr_thread.start()
    return connection


def submit_request(connection: RuntimeConnection, request: RuntimeRequest) -> None:
    if connection.stopped.is_set() or connection.process.poll() is not None or connection.pending is not None:
        raise RuntimeError("The native process is not ready for another request")
    connection.pending = request
    connection.outbound.put_nowait(request)


def poll_reply(connection: RuntimeConnection) -> RuntimeReply | RuntimeFailure | None:
    try:
        reply = connection.inbound.get_nowait()
    except Empty:
        return None
    connection.pending = None
    connection.reply_ready.clear()
    return reply


def close_runtime(connection: RuntimeConnection) -> None:
    """Bounded shutdown; a failed/unfinished operation is never retried."""
    connection.stopped.set()
    try:
        connection.outbound.put_nowait(None)
    except Full:
        pass
    try:
        connection.process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        connection.process.terminate()
        try:
            connection.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            connection.process.kill()
            connection.process.wait()
    connection.io_thread.join(timeout=.1)
    connection.stderr_thread.join(timeout=.1)
    for stream in (connection.process.stdin, connection.process.stdout, connection.process.stderr):
        if stream is not None:
            stream.close()
