"""Seat authority, serial worker admission and exact-byte publication."""
import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from hashlib import sha256
import logging
from time import monotonic
from uuid import UUID, uuid4

from server import connection, protocol as wire, workers
from server.config import ServerConfig
from server.framing import MAX_PACKET_BYTES
from server.recording import Recording, close_recording, commit_records, expire_recording, has_capacity, open_recording
from server.worker_protocol import Advance, Choices, Command, Preview, Publication, Reply, Request, Start

logger = logging.getLogger(__name__)
TERMINAL_RETENTION_SECONDS = 24 * 60 * 60
DELIVERY_LIMIT_BYTES = 128 * 1024 * 1024


class ApiFailure(Exception):
    def __init__(self, error: wire.ApiError):
        super().__init__(error.code)
        self.error = error


@dataclass(slots=True)
class Attachment:
    epoch: UUID
    acquisition_id: UUID
    expected_epoch: UUID | None
    catch_up: int
    highest_sent: int = -1
    acknowledged: int = -1
    stream_id: UUID | None = None


@dataclass(slots=True)
class StoredReceipt:
    digest: str
    receipt: wire.CommandReceipt
    size: int


@dataclass(slots=True)
class Seat:
    seat_id: str
    audience_id: UUID
    publication: Publication | None = None
    attachment: Attachment | None = None
    next_command_number: int = 1
    receipts: OrderedDict[int, StoredReceipt] = field(default_factory=OrderedDict)
    receipt_bytes: int = 0


@dataclass(slots=True)
class Query:
    request: Choices | Preview
    future: asyncio.Future[bytes]
    encoded_size: int
    attachment_epoch: UUID


@dataclass(slots=True)
class Host:
    config: ServerConfig
    epoch: UUID
    seats: dict[str, Seat]
    recording: Recording
    changed: asyncio.Condition = field(default_factory=asyncio.Condition)
    work: asyncio.Event = field(default_factory=asyncio.Event)
    delivery_available: asyncio.Event = field(default_factory=asyncio.Event)
    delivery_bytes: int = 0
    process: connection.Connection | None = None
    task: asyncio.Task[None] | None = None
    pending: tuple[str, wire.CommandRequest] | None = None
    queries: OrderedDict[str, Query] = field(default_factory=OrderedDict)
    query_bytes: int = 0
    content: bytes | None = None
    encounter_name: str = ''
    needs_advance: bool = False
    blocked: bool = False
    closing: bool = False
    failure: UUID | None = None
    retained_until: float | None = None
    history_expired: bool = False
    timings: list[tuple[str, float]] = field(default_factory=list)
    worker_set: workers.Workers | None = None
    ending: bool = False
    retired: bool = False
    native_done: asyncio.Event = field(default_factory=asyncio.Event)
    acquiring: bool = False


def create_host(config: ServerConfig, worker_set: workers.Workers | None = None) -> Host:
    epoch = uuid4()
    seats = {row.seat_id: Seat(row.seat_id, uuid4()) for row in config.credentials}
    recording = open_recording(config.spool_directory / str(epoch), tuple(seats), config.spool_limit_bytes)
    return Host(config, epoch, seats, recording, worker_set=worker_set)


def reserve_delivery(host: Host, size: int) -> bool:
    if host.delivery_bytes + size > DELIVERY_LIMIT_BYTES:
        return False
    host.delivery_bytes += size
    return True


def release_delivery(host: Host, size: int) -> None:
    host.delivery_bytes -= size
    host.delivery_available.set()


async def wait_delivery(host: Host, size: int) -> None:
    while not reserve_delivery(host, size):
        host.delivery_available.clear()
        await host.delivery_available.wait()


def identity(host: Host, seat: Seat) -> dict:
    return dict(game_id=host.config.game_id, game_epoch=host.epoch, audience_id=seat.audience_id)


def cursor(host: Host, seat: Seat, sequence: int) -> wire.PlayerCursor:
    return wire.PlayerCursor(**identity(host, seat), sequence=sequence)


def snapshot(host: Host, seat: Seat) -> wire.StatusSnapshot:
    publication = seat.publication
    head = publication.cursor if publication is not None else None
    boundary = publication.boundary if publication is not None else wire.BoundaryState(
        lifecycle='starting', input_actor_uuid=None, state_revision=None)
    if host.history_expired:
        boundary = wire.BoundaryState(lifecycle='closed', input_actor_uuid=None, state_revision=None)
    elif host.failure is not None:
        boundary = wire.BoundaryState(lifecycle='failed', input_actor_uuid=None, state_revision=None,
            reason='worker_failure', incident_id=host.failure)
    elif host.closing:
        boundary = wire.BoundaryState(lifecycle='closing', input_actor_uuid=None, state_revision=None, reason='host_close')
    elif host.retired and boundary.lifecycle != 'terminal':
        boundary = wire.BoundaryState(lifecycle='closed', input_actor_uuid=None, state_revision=None)
    elif host.ending and boundary.lifecycle != 'terminal':
        boundary = wire.BoundaryState(lifecycle='closing', input_actor_uuid=None, state_revision=None, reason='host_close')
    elif host.blocked:
        boundary = boundary.model_copy(update={'lifecycle': 'delivery_blocked', 'reason': 'recording_capacity'})
    attachment = seat.attachment
    return wire.StatusSnapshot(**identity(host, seat), boundary=boundary, published_cursor=head,
        final_cursor=head if boundary.lifecycle in ('terminal', 'failed', 'closed') else None,
        attachment_epoch=attachment.epoch if attachment is not None else None,
        catch_up_cursor=cursor(host, seat, attachment.catch_up) if attachment is not None else None,
        acknowledged_cursor=cursor(host, seat, attachment.acknowledged) if attachment is not None and attachment.acknowledged >= 0 else None,
        next_command_number=seat.next_command_number,
        pending_command_numbers=tuple(number for number, row in seat.receipts.items() if row.receipt.kind == 'pending'))


def require_ready(host: Host, seat: Seat) -> Publication:
    if host.closing:
        raise ApiFailure(wire.ErrorGameClosed())
    if seat.publication is None:
        if host.failure is not None:
            raise ApiFailure(wire.ErrorGameFailed(incident_id=host.failure))
        raise ApiFailure(wire.ErrorStarting())
    return seat.publication


def attach(host: Host, seat: Seat, request: wire.AttachmentRequest) -> wire.AttachmentResponse:
    publication = require_ready(host, seat)
    current = seat.attachment
    if current is not None and current.acquisition_id == request.acquisition_id:
        if request.expected_attachment_epoch != current.expected_epoch:
            raise ApiFailure(wire.ErrorAttachmentConflict())
    else:
        if request.expected_attachment_epoch != (current.epoch if current is not None else None):
            raise ApiFailure(wire.ErrorAttachmentConflict())
        seat.attachment = Attachment(uuid4(), request.acquisition_id, request.expected_attachment_epoch,
            publication.cursor.sequence)
        queued = host.queries.pop(seat.seat_id, None)
        if queued is not None:
            host.query_bytes -= queued.encoded_size
            queued.future.set_exception(ApiFailure(wire.ErrorAttachmentReplaced()))
    assert seat.attachment is not None
    return wire.AttachmentResponse(acquisition_id=request.acquisition_id, attachment_epoch=seat.attachment.epoch,
        status=snapshot(host, seat))


def require_attachment(host: Host, seat: Seat, epoch: UUID, game_epoch: UUID, audience_id: UUID) -> Attachment:
    require_ready(host, seat)
    if game_epoch != host.epoch:
        raise ApiFailure(wire.ErrorEpochMismatch())
    if audience_id != seat.audience_id:
        raise ApiFailure(wire.ErrorAudienceMismatch())
    if seat.attachment is None or seat.attachment.epoch != epoch:
        raise ApiFailure(wire.ErrorAttachmentReplaced())
    return seat.attachment


def check_cursor(host: Host, seat: Seat, value: wire.PlayerCursor) -> None:
    if value.game_id != host.config.game_id or value.game_epoch != host.epoch:
        raise ApiFailure(wire.ErrorEpochMismatch())
    if value.audience_id != seat.audience_id:
        raise ApiFailure(wire.ErrorAudienceMismatch())
    if seat.publication is None or value.sequence > seat.publication.cursor.sequence:
        raise ApiFailure(wire.ErrorInvalidCursor())


def acknowledge(host: Host, seat: Seat, attachment: Attachment, value: wire.PlayerCursor) -> wire.AckResponse:
    check_cursor(host, seat, value)
    if value.sequence > attachment.highest_sent or value.sequence < attachment.acknowledged:
        raise ApiFailure(wire.ErrorInvalidCursor())
    attachment.acknowledged = value.sequence
    return wire.AckResponse(cursor=value, catch_up_cursor=cursor(host, seat, attachment.catch_up))


def admitted_input(host: Host, seat: Seat, actor: UUID, revision: str) -> Publication:
    publication = require_ready(host, seat)
    if host.history_expired or ((host.ending or host.retired) and not terminal(host)):
        raise ApiFailure(wire.ErrorGameClosed())
    if host.failure is not None:
        raise ApiFailure(wire.ErrorGameFailed(incident_id=host.failure))
    attachment = seat.attachment
    assert attachment is not None
    if attachment.acknowledged < attachment.catch_up:
        raise ApiFailure(wire.ErrorCatchUpRequired(required_cursor=cursor(host, seat, attachment.catch_up)))
    if publication.boundary.lifecycle == 'terminal':
        raise ApiFailure(wire.ErrorGameTerminal())
    if not publication.audience.controls(actor) or publication.boundary.input_actor_uuid != actor:
        raise ApiFailure(wire.ErrorNotYourTurn())
    if publication.state_revision != revision:
        raise ApiFailure(wire.ErrorStaleState())
    return publication


def store_receipt(seat: Seat, number: int, digest: str, receipt: wire.CommandReceipt) -> None:
    old = seat.receipts.get(number)
    if old is not None:
        seat.receipt_bytes -= old.size
    size = len(receipt.model_dump_json().encode()) + len(digest)
    seat.receipts[number] = StoredReceipt(digest, receipt, size)
    seat.receipt_bytes += size
    while len(seat.receipts) > 1024 or seat.receipt_bytes > 4 * 1024 * 1024:
        oldest, entry = next(iter(seat.receipts.items()))
        if entry.receipt.kind == 'pending':
            raise RuntimeError('Pinned receipt exceeded bounded retention')
        del seat.receipts[oldest]
        seat.receipt_bytes -= entry.size


def receipt(host: Host, seat: Seat, number: int) -> wire.ReceiptResponse:
    old = seat.receipts.get(number)
    value = old.receipt if old is not None else (
        wire.ExpiredReceipt(**identity(host, seat), command_number=number) if number < seat.next_command_number
        else wire.UnknownReceipt(**identity(host, seat), command_number=number))
    return wire.ReceiptResponse(receipt=value)


def submit(host: Host, seat: Seat, request: wire.CommandRequest) -> wire.ReceiptResponse:
    digest = sha256(request.model_dump_json().encode()).hexdigest()
    old = seat.receipts.get(request.command_number)
    if old is not None:
        if old.digest != digest:
            raise ApiFailure(wire.ErrorCommandConflict())
        return wire.ReceiptResponse(receipt=old.receipt)
    if request.command_number < seat.next_command_number:
        return receipt(host, seat, request.command_number)
    if request.command_number != seat.next_command_number or seat.next_command_number == wire.MAX_SAFE_INTEGER:
        raise ApiFailure(wire.ErrorCommandNumber())
    publication = require_ready(host, seat)
    if host.history_expired or ((host.ending or host.retired) and not terminal(host)):
        raise ApiFailure(wire.ErrorGameClosed())
    if host.failure is not None:
        raise ApiFailure(wire.ErrorGameFailed(incident_id=host.failure))
    if not publication.audience.controls(request.actor_uuid):
        raise ApiFailure(wire.ErrorForbidden())
    assert seat.attachment is not None
    if seat.attachment.acknowledged < seat.attachment.catch_up:
        raise ApiFailure(wire.ErrorCatchUpRequired(required_cursor=cursor(host, seat, seat.attachment.catch_up)))
    if publication.boundary.lifecycle == 'terminal':
        raise ApiFailure(wire.ErrorGameTerminal())
    if host.pending is not None:
        raise ApiFailure(wire.ErrorBusy())
    if host.blocked or not has_capacity(host.recording):
        raise ApiFailure(wire.ErrorRecordingCapacity())
    value = wire.PendingReceipt(**identity(host, seat), command_number=request.command_number)
    store_receipt(seat, request.command_number, digest, value)
    seat.next_command_number += 1
    host.pending = seat.seat_id, request
    host.work.set()
    return wire.ReceiptResponse(receipt=value)


async def query(host: Host, seat: Seat, request: wire.ChoicesRequest | wire.PreviewRequest) -> bytes:
    admitted_input(host, seat, request.actor_uuid, request.state_revision)
    assert seat.attachment is not None
    native = Choices(seat_id=seat.seat_id, request=request) if isinstance(request, wire.ChoicesRequest) else Preview(seat_id=seat.seat_id, request=request)
    size = len(native.model_dump_json().encode())
    previous = host.queries.get(seat.seat_id)
    total = host.query_bytes + size - (previous.encoded_size if previous is not None else 0)
    if total > 8 * 1024 * 1024:
        raise ApiFailure(wire.ErrorBusy())
    if previous is not None:
        previous.future.set_exception(ApiFailure(wire.ErrorQuerySuperseded()))
    future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
    host.queries[seat.seat_id] = Query(native, future, size, seat.attachment.epoch)
    host.query_bytes = total
    host.work.set()
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        # Dispatch may already be in flight; its eventual response still needs
        # an owner to release delivery credit after this HTTP caller leaves.
        def discard(completed: asyncio.Future[bytes]) -> None:
            if not completed.cancelled() and completed.exception() is None:
                release_delivery(host, len(completed.result()))
        future.add_done_callback(discard)
        raise


async def changed(host: Host) -> None:
    async with host.changed:
        host.changed.notify_all()


def terminal(host: Host) -> bool:
    return all(seat.publication is not None and seat.publication.boundary.lifecycle == 'terminal'
               for seat in host.seats.values())


async def retain_final_prefix(host: Host) -> None:
    """Retain immutable final records after the native process has closed."""
    if host.retained_until is None:
        host.retained_until = monotonic() + TERMINAL_RETENTION_SECONDS
    while not host.closing:
        remaining = host.retained_until - monotonic()
        if remaining <= 0:
            await asyncio.to_thread(expire_recording, host.recording)
            host.history_expired = True
            await changed(host)
            return
        host.work.clear()
        try:
            await asyncio.wait_for(host.work.wait(), remaining)
        except TimeoutError:
            continue


async def _exchange(host: Host, request: Request) -> tuple[Reply, bytes | None]:
    assert host.process is not None
    reply, staged, response = await asyncio.wait_for(
        connection.exchange(host.process, request, host.recording), host.config.worker_timeout_seconds)
    commit_records(host.recording, staged)
    for publication in reply.publications:
        seat = host.seats[publication.seat_id]
        seat.publication = publication
        if seat.attachment is not None:
            seat.attachment.catch_up = publication.cursor.sequence
    if reply.encounter_name is not None:
        host.encounter_name = reply.encounter_name
    host.timings.append((request.kind, reply.elapsed_ms))
    if len(host.timings) > 4096:
        del host.timings[:2048]
    host.needs_advance = reply.needs_advance if isinstance(request, (Start, Advance, Command)) else host.needs_advance
    if terminal(host) and host.retained_until is None:
        host.retained_until = monotonic() + TERMINAL_RETENTION_SECONDS
    await changed(host)
    return reply, response


async def run(host: Host) -> None:
    active_query = None
    clean = False
    try:
        if host.ending or host.closing:
            raise asyncio.CancelledError
        host.acquiring = True
        try:
            host.process = (await workers.acquire(host.worker_set) if host.worker_set is not None
                else await connection.launch())
        finally:
            host.acquiring = False
        _, host.content = await _exchange(host, Start(game_id=host.config.game_id, game_epoch=host.epoch,
            audience_ids={seat.seat_id: seat.audience_id for seat in host.seats.values()},
            encounter_id=host.config.encounter_id, recipe=host.config.recipe,
            assignments=host.config.assignments, test_seed=host.config.test_seed))
        if host.content is not None and not reserve_delivery(host, len(host.content)):
            raise RuntimeError('Public content exceeded the delivery budget')
        while host.pending is not None or not (host.closing or host.ending):
            host.work.clear()
            if host.pending is not None or host.needs_advance:
                capacity = await asyncio.to_thread(has_capacity, host.recording)
                if not capacity:
                    host.blocked = True
                    await changed(host)
                    try:
                        await asyncio.wait_for(host.work.wait(), 1)
                    except TimeoutError:
                        pass
                    continue
                if host.blocked:
                    host.blocked = False
                    await changed(host)
            if host.pending is not None:
                seat_id, request = host.pending
                seat = host.seats[seat_id]
                reply, _ = await _exchange(host, Command(seat_id=seat_id, request=request))
                stored = seat.receipts[request.command_number]
                value: wire.CommandReceipt
                if reply.rejection is not None:
                    value = wire.RejectedReceipt(**identity(host, seat), command_number=request.command_number, reason=reply.rejection)
                else:
                    assert seat.publication is not None
                    value = wire.CommittedReceipt(**identity(host, seat), command_number=request.command_number, cursor=seat.publication.cursor)
                store_receipt(seat, request.command_number, stored.digest, value)
                host.pending = None
                await changed(host)
            elif host.queries:
                seat_id, active_query = host.queries.popitem(last=False)
                host.query_bytes -= active_query.encoded_size
                if not reserve_delivery(host, MAX_PACKET_BYTES):
                    active_query.future.set_exception(ApiFailure(wire.ErrorBusy()))
                    active_query = None
                    continue
                retained = 0
                try:
                    reply, response = await _exchange(host, active_query.request)
                    seat = host.seats[seat_id]
                    if seat.attachment is None or seat.attachment.epoch != active_query.attachment_epoch:
                        active_query.future.set_exception(ApiFailure(wire.ErrorAttachmentReplaced()))
                    elif reply.query_error is not None:
                        active_query.future.set_exception(ApiFailure(wire.ErrorResponseTooLarge()))
                    elif reply.rejection is not None:
                        error = wire.ErrorStaleDiscovery() if reply.rejection == 'stale_discovery' else wire.ErrorStaleState()
                        active_query.future.set_exception(ApiFailure(error))
                    else:
                        assert response is not None
                        retained = len(response)
                        active_query.future.set_result(response)
                    response = None
                finally:
                    release_delivery(host, MAX_PACKET_BYTES - retained)
                active_query = None
            elif host.needs_advance:
                await _exchange(host, Advance())
            elif terminal(host):
                break
            else:
                await host.work.wait()
        clean = True
    except asyncio.CancelledError:
        # Native cancellation discards the worker; public prefix retention is
        # still owned by this Host unless the service itself is shutting down.
        pass
    except Exception:
        host.failure = uuid4()
        logger.exception('Player native owner failed; incident %s', host.failure)
        if host.process is not None:
            logger.error('Native stderr: %s', b''.join(host.process.diagnostics).decode(errors='replace'))
        if host.pending is not None:
            seat_id, request = host.pending
            seat = host.seats[seat_id]
            store_receipt(seat, request.command_number, seat.receipts[request.command_number].digest,
                wire.IndeterminateReceipt(**identity(host, seat), command_number=request.command_number, incident_id=host.failure))
            host.pending = None
        if active_query is not None and not active_query.future.done():
            active_query.future.set_exception(ApiFailure(wire.ErrorGameFailed(incident_id=host.failure)))
        for waiting in host.queries.values():
            waiting.future.set_exception(ApiFailure(wire.ErrorGameFailed(incident_id=host.failure)))
        host.queries.clear()
        host.query_bytes = 0
        host.retained_until = monotonic() + TERMINAL_RETENTION_SECONDS
        await changed(host)
    finally:
        if active_query is not None and not active_query.future.done():
            active_query.future.set_exception(ApiFailure(wire.ErrorGameClosed()))
        process, host.process = host.process, None
        try:
            if process is not None:
                if host.worker_set is None:
                    await connection.close(process)
                else:
                    elapsed = await workers.release(host.worker_set, process, clean=clean,
                        epoch=host.epoch, recording=host.recording, timeout=host.config.worker_timeout_seconds)
                    if elapsed is not None:
                        host.timings.append(('end_game', elapsed))
        except asyncio.CancelledError:
            # Lease cleanup finishes closing a cancelled exchange before this
            # propagates. The game's recorded prefix still needs retention.
            pass
        finally:
            if host.pending is not None:
                seat_id, request = host.pending
                seat = host.seats[seat_id]
                store_receipt(seat, request.command_number, seat.receipts[request.command_number].digest,
                    wire.IndeterminateReceipt(**identity(host, seat), command_number=request.command_number,
                        incident_id=host.failure or uuid4()))
                host.pending = None
            host.retired = True
            host.native_done.set()
            close_recording(host.recording)
            await changed(host)
    if not host.closing:
        await retain_final_prefix(host)


def stop_input(host: Host) -> None:
    host.ending = True
    for waiting in host.queries.values():
        waiting.future.set_exception(ApiFailure(wire.ErrorGameClosed()))
    host.queries.clear()
    host.query_bytes = 0
    host.work.set()


async def end_game(host: Host) -> None:
    """Retire native state; retain this game's authorized public recordings."""
    stop_input(host)
    await changed(host)
    if host.task is None:
        host.retired = True
        host.native_done.set()
        close_recording(host.recording)
        host.task = asyncio.create_task(retain_final_prefix(host), name='retired-game-prefix')
        return
    if host.acquiring:
        host.task.cancel()
    try:
        await asyncio.wait_for(host.native_done.wait(), host.config.worker_timeout_seconds)
    except TimeoutError:
        host.task.cancel()
        await host.native_done.wait()
    await changed(host)


async def shutdown(host: Host) -> None:
    host.closing = True
    stop_input(host)
    await changed(host)
    if host.task is not None:
        try:
            await asyncio.wait_for(asyncio.shield(host.task), 4)
        except TimeoutError:
            host.task.cancel()
            try:
                await host.task
            except asyncio.CancelledError:
                pass
    if host.pending is not None:
        seat_id, request = host.pending
        seat = host.seats[seat_id]
        store_receipt(seat, request.command_number, seat.receipts[request.command_number].digest,
            wire.IndeterminateReceipt(**identity(host, seat), command_number=request.command_number,
                incident_id=uuid4()))
        host.pending = None
    close_recording(host.recording)
