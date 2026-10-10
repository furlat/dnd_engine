"""HTTP/SSE adapter. The only game decisions are native worker requests."""
import asyncio
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from starlette.types import ASGIApp, Receive, Scope, Send

from server import host as owner, protocol as wire, service as hosting
from server.config import ServerConfig, ServiceLimits
from server.openapi import document, result_schema
from server.recording import RecordUnavailable, read_chunk, require_record

MAX_REQUEST_BYTES = 256 * 1024


def encoded(value: BaseModel, status: int = 200) -> Response:
    return Response(value.model_dump_json(), status_code=status, media_type='application/json',
        headers={'Cache-Control': 'no-store'})


class BoundedBody:
    """ASGI transport limit, before JSON validation allocates an unbounded body."""
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' or scope['method'] not in ('POST', 'PUT', 'PATCH'):
            await self.app(scope, receive, send)
            return
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body = message.get('body', b'')
            size += len(body)
            if size > MAX_REQUEST_BYTES:
                await encoded(wire.ErrorRequestTooLarge(), 413)(scope, receive, send)
                return
            chunks.append(body)
            if not message.get('more_body', False):
                break
        consumed = False
        async def limited_receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        await self.app(scope, limited_receive, send)


class QueryResponse(StreamingResponse):
    """Hold the native response's delivery credit through socket completion."""
    def __init__(self, host: owner.Host, body: bytes):
        self.host = host
        self.size = len(body)
        async def chunks():
            view = memoryview(body)
            for offset in range(0, len(body), 65536):
                yield view[offset:offset + 65536]
        super().__init__(chunks(), media_type='application/json', headers={'Cache-Control': 'no-store'})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            owner.release_delivery(self.host, self.size)


def create_app(config: ServerConfig, *, limits: ServiceLimits | None = None) -> FastAPI:
    service = hosting.create_service(config, limits or ServiceLimits())
    initial_host = service.games[config.game_id]

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        initial_host.task = asyncio.create_task(owner.run(initial_host), name='native-game-owner')
        try:
            yield
        finally:
            await hosting.shutdown(service)

    app = FastAPI(title='Player server', version='1', lifespan=lifespan)
    app.state.player_host = initial_host
    app.state.player_service = service
    app.add_middleware(BoundedBody)
    if config.allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(config.allowed_origins),
            allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type',
                'X-Game-Epoch', 'X-Audience-Id', 'X-Attachment-Epoch'], allow_credentials=False)

    def seat_for(request: Request, game_id: str | None = None) -> tuple[owner.Host, owner.Seat]:
        authorization = request.headers.get('authorization', '')
        token = authorization[7:] if authorization.startswith('Bearer ') else ''
        host, seat = hosting.authorize(service, token, game_id)
        if game_id is not None:
            try:
                game_epoch = UUID(request.headers['x-game-epoch'])
                audience_id = UUID(request.headers['x-audience-id'])
            except (KeyError, ValueError):
                raise owner.ApiFailure(wire.ErrorInvalidRequest()) from None
            if game_epoch != host.epoch:
                raise owner.ApiFailure(wire.ErrorEpochMismatch())
            if audience_id != seat.audience_id:
                raise owner.ApiFailure(wire.ErrorAudienceMismatch())
        return host, seat

    def attached(request: Request, game_id: str) -> tuple[owner.Host, owner.Seat, owner.Attachment]:
        host, seat = seat_for(request, game_id)
        try:
            epoch = UUID(request.headers['x-attachment-epoch'])
            game_epoch = UUID(request.headers['x-game-epoch'])
            audience_id = UUID(request.headers['x-audience-id'])
        except (KeyError, ValueError):
            raise owner.ApiFailure(wire.ErrorInvalidRequest()) from None
        return host, seat, owner.require_attachment(host, seat, epoch, game_epoch, audience_id)

    @app.exception_handler(owner.ApiFailure)
    async def api_failure(_request: Request, failure: owner.ApiFailure):
        return encoded(failure.error, failure.error.http_status)

    @app.exception_handler(RequestValidationError)
    async def invalid(_request: Request, _error: RequestValidationError):
        return encoded(wire.ErrorInvalidRequest(), 400)

    @app.exception_handler(RecordUnavailable)
    async def unavailable(_request: Request, _error: RecordUnavailable):
        return encoded(wire.ErrorResumeUnavailable(earliest_cursor=None), 410)

    async def readable(host: owner.Host, seat: owner.Seat, sequence: int) -> None:
        if host.history_expired:
            raise RecordUnavailable('Public history retention expired')
        await asyncio.to_thread(require_record, host.recording, seat.seat_id, sequence)

    async def record_chunks(host: owner.Host, seat: owner.Seat, sequence: int):
        if host.history_expired:
            raise RecordUnavailable('Public history retention expired')
        length = host.recording.audiences[seat.seat_id].offsets[sequence][1]
        offset = 0
        while offset < length:
            # Credits cover only 64 KiB chunks, not a game lock or whole record.
            size = min(65536, length - offset)
            await owner.wait_delivery(host, size)
            try:
                chunk = await asyncio.to_thread(read_chunk, host.recording, seat.seat_id, sequence, offset, 65536)
                offset += len(chunk)
                yield chunk
            finally:
                owner.release_delivery(host, size)

    @app.get('/health', responses={200: result_schema('HealthResponse')})
    async def health():
        return encoded(wire.HealthResponse())

    @app.get('/api/v1/bootstrap', responses={200: result_schema('BootstrapResponse')})
    async def bootstrap(request: Request):
        host, seat = seat_for(request)
        publication = seat.publication
        return encoded(wire.BootstrapResponse(protocol=wire.protocol_identity(), status=owner.snapshot(host, seat),
            audience=publication.audience if publication is not None else None, encounter_name=host.encounter_name,
            content_revision=publication.content_revision if publication is not None else None))

    @app.get('/api/v1/games/{game_id}/status', responses={200: result_schema('StatusResponse')})
    async def status(request: Request, game_id: str):
        host, seat = seat_for(request, game_id)
        return encoded(wire.StatusResponse(status=owner.snapshot(host, seat)))

    @app.post('/api/v1/games/{game_id}/attachment', responses={200: result_schema('AttachmentResponse')})
    async def attach(request: Request, game_id: str, body: wire.AttachmentRequest):
        host, seat = seat_for(request, game_id)
        result = owner.attach(host, seat, body)
        await owner.changed(host)
        return encoded(result)

    @app.get('/api/v1/games/{game_id}/initialization', responses={200: result_schema('InitializationResponse')})
    async def initialization(request: Request, game_id: str):
        host, seat, attachment = attached(request, game_id)
        await readable(host, seat, 0)
        async def initial_bytes():
            async for chunk in record_chunks(host, seat, 0):
                yield chunk
            attachment.highest_sent = max(attachment.highest_sent, 0)
        return StreamingResponse(initial_bytes(), media_type='application/json', headers={'Cache-Control': 'no-store'})

    @app.post('/api/v1/games/{game_id}/ack', responses={200: result_schema('AckResponse')})
    async def acknowledge(request: Request, game_id: str, body: wire.AckRequest):
        host, seat, attachment = attached(request, game_id)
        result = owner.acknowledge(host, seat, attachment, body.cursor)
        await owner.changed(host)
        return encoded(result)

    @app.post('/api/v1/games/{game_id}/choices', responses={200: result_schema('ChoicesResponse')})
    async def choices(request: Request, game_id: str, body: wire.ChoicesRequest):
        host, seat, _ = attached(request, game_id)
        return QueryResponse(host, await owner.query(host, seat, body))

    @app.post('/api/v1/games/{game_id}/preview', responses={200: result_schema('PreviewResponse')})
    async def preview(request: Request, game_id: str, body: wire.PreviewRequest):
        host, seat, _ = attached(request, game_id)
        return QueryResponse(host, await owner.query(host, seat, body))

    @app.post('/api/v1/games/{game_id}/commands', responses={200: result_schema('ReceiptResponse'), 202: result_schema('ReceiptResponse')})
    async def command(request: Request, game_id: str, body: wire.CommandRequest):
        host, seat, _ = attached(request, game_id)
        result = owner.submit(host, seat, body)
        return encoded(result, 202 if result.receipt.kind == 'pending' else 200)

    @app.get('/api/v1/games/{game_id}/commands/{number}', responses={200: result_schema('ReceiptResponse')})
    async def receipt(request: Request, game_id: str, number: int):
        if not 1 <= number <= wire.MAX_SAFE_INTEGER:
            raise owner.ApiFailure(wire.ErrorInvalidRequest())
        host, seat = seat_for(request, game_id)
        return encoded(owner.receipt(host, seat, number))

    @app.get('/api/v1/content/{revision}', responses={200: result_schema('ContentResponse')})
    async def content(request: Request, revision: str):
        host, seat = seat_for(request)
        publication = owner.require_ready(host, seat)
        if revision != publication.content_revision or host.content is None:
            raise owner.ApiFailure(wire.ErrorForbidden())
        return Response(host.content, media_type='application/json')

    @app.get('/api/v1/games/{game_id}/events', response_class=StreamingResponse, responses={200: {
        'description': 'Exact retained SSE; numbered operations, unnumbered status/ready/error.',
        'content': {'text/event-stream': {'schema': {'type': 'string'}}},
        'x-event-schemas': {name: {'$ref': '#/components/schemas/' + root} for name, root in (
            ('ready', 'StreamReady'), ('status', 'StreamStatus'), ('operation', 'PlayerOperation'), ('error', 'ApiError'))}}})
    async def events(request: Request, game_id: str, after: int):
        host, seat, attachment = attached(request, game_id)
        if after < 0 or after > attachment.highest_sent:
            raise owner.ApiFailure(wire.ErrorInvalidCursor())
        owner.check_cursor(host, seat, owner.cursor(host, seat, after))
        assert seat.publication is not None
        await readable(host, seat, seat.publication.cursor.sequence)
        stream_id = uuid4()
        attachment.stream_id = stream_id
        await owner.changed(host)

        async def stream():
            sent = after
            status = owner.snapshot(host, seat)
            assert status.published_cursor is not None
            ready = wire.StreamReady(protocol=wire.protocol_identity(), after=owner.cursor(host, seat, after),
                head=status.published_cursor, status=status)
            yield b'event: ready\ndata: ' + ready.model_dump_json().encode() + b'\n\n'
            while not host.closing:
                if seat.attachment is not attachment or attachment.stream_id != stream_id:
                    yield b'event: error\ndata: ' + wire.ErrorAttachmentReplaced().model_dump_json().encode() + b'\n\n'
                    return
                publication = seat.publication
                assert publication is not None
                while sent < publication.cursor.sequence:
                    # The exact file prefix is the backfill and live queue. No duplicate subscription buffer.
                    sequence = sent + 1
                    try:
                        await readable(host, seat, sequence)
                    except RecordUnavailable:
                        yield b'event: error\ndata: ' + wire.ErrorResumeUnavailable(earliest_cursor=None).model_dump_json().encode() + b'\n\n'
                        return
                    yield b'id: ' + str(sequence).encode() + b'\nevent: operation\ndata: '
                    async for chunk in record_chunks(host, seat, sequence):
                        yield chunk
                    attachment.highest_sent = max(attachment.highest_sent, sequence)
                    yield b'\n\n'
                    sent = sequence
                    if seat.attachment is not attachment or attachment.stream_id != stream_id:
                        break
                current = owner.snapshot(host, seat)
                if current != status:
                    yield b'event: status\ndata: ' + wire.StreamStatus(status=current).model_dump_json().encode() + b'\n\n'
                    status = current
                if current.boundary.lifecycle in ('terminal', 'failed', 'closed') and current.final_cursor is not None and sent == current.final_cursor.sequence:
                    return
                heartbeat = False
                async with host.changed:
                    if seat.publication is not publication or owner.snapshot(host, seat) != current:
                        continue
                    try:
                        await asyncio.wait_for(host.changed.wait(), 15)
                    except TimeoutError:
                        heartbeat = True
                if heartbeat:
                    yield b'event: status\ndata: ' + wire.StreamStatus(status=owner.snapshot(host, seat)).model_dump_json().encode() + b'\n\n'

        return StreamingResponse(stream(), media_type='text/event-stream', headers={
            'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    app.openapi = lambda: document(app)
    return app
