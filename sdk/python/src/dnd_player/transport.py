"""Independent HTTP/SSE transport; the consumer owns game state and recording."""
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from importlib.resources import files
import json
import math
import random
import time
from typing import Any, cast
from urllib.parse import quote

import httpx
from jsonschema_rs import Draft202012Validator, ValidationError

from . import contracts as c

MAX_BYTES = 64 * 1024 * 1024
_SCHEMA = json.loads(files('dnd_player').joinpath('player-api-v1.schema.json').read_bytes())
IDENTITY = json.loads(files('dnd_player').joinpath('protocol-identity.json').read_bytes())
_VALIDATORS: dict[str, Draft202012Validator] = {}


class ProtocolError(Exception):
    pass


class ApiError(Exception):
    def __init__(self, value: dict[str, Any], retry_after: float = 0):
        super().__init__(value['code'])
        self.value = value
        self.retry_after = retry_after


def validate(root: str, value: Any) -> Any:
    # The compiled binding converts non-finite Python floats to null. Reject
    # non-JSON caller values before that conversion, including nullable fields.
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError, OverflowError) as error:
        raise ProtocolError('Invalid JSON value') from error
    return _validate(root, value)


def _validate(root: str, value: Any) -> Any:
    validator = _VALIDATORS.get(root)
    if validator is None:
        validator = Draft202012Validator({'$defs': _SCHEMA['$defs'], '$ref': '#/$defs/' + root},
            validate_formats=True, ignore_unknown_formats=False)
        _VALIDATORS[root] = validator
    try:
        validator.validate(value)
    except ValidationError as error:
        raise ProtocolError(f'{root}: {error.instance_path}: {error.message}') from error
    except (ValueError, TypeError, OverflowError) as error:
        raise ProtocolError('Invalid JSON value') from error
    if root == 'InitializationResponse' and value['cursor']['sequence'] != 0:
        raise ProtocolError('Initialization sequence must be zero')
    if root == 'PlayerOperation' and value['cursor']['sequence'] < 1:
        raise ProtocolError('Operation sequence must be positive')
    return value


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite JSON number')
    return result


def decode(root: str, raw: bytes) -> Any:
    if len(raw) > MAX_BYTES:
        raise ProtocolError('Record exceeds 64 MiB')
    try:
        value = json.loads(raw.decode('utf-8-sig'), parse_float=_finite_float,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError, UnicodeError) as error:
        raise ProtocolError('Invalid JSON record') from error
    return _validate(root, value)


def check_protocol(value: c.ProtocolIdentity) -> None:
    if value != IDENTITY:
        raise ProtocolError('Protocol/schema identity mismatch')


def check_scope(scope: c.StatusSnapshot, value: c.PlayerCursor | c.StatusSnapshot) -> None:
    if any(scope[key] != value[key] for key in ('game_id', 'game_epoch', 'audience_id')):
        raise ProtocolError('Game/epoch/audience mismatch')


def check_status(scope: c.StatusSnapshot, value: c.StatusSnapshot) -> None:
    check_scope(scope, value)
    for key in ('published_cursor', 'final_cursor', 'catch_up_cursor', 'acknowledged_cursor'):
        if value[key] is not None:
            check_scope(scope, value[key])


@dataclass(slots=True)
class Connection:
    http: httpx.AsyncClient
    bootstrap: c.BootstrapResponse
    attachment: c.AttachmentResponse | None = None


def headers(connection: Connection) -> dict[str, str]:
    if not connection.bootstrap:
        return {}
    scope = connection.bootstrap['status']
    result = {'X-Game-Epoch': scope['game_epoch'], 'X-Audience-Id': scope['audience_id']}
    if connection.attachment is not None:
        result['X-Attachment-Epoch'] = connection.attachment['attachment_epoch']
    return result


def route(connection: Connection, suffix: str) -> str:
    return '/api/v1/games/' + quote(connection.bootstrap['status']['game_id'], safe='') + '/' + suffix


def _api_error(response: httpx.Response, raw: bytes) -> ApiError:
    value = decode('ApiError', raw)
    if value['http_status'] != response.status_code:
        raise ProtocolError('HTTP error status mismatch')
    retry_after = 0
    header = response.headers.get('retry-after')
    if header is not None:
        try:
            retry_after = float(header) if header.isascii() and header.isdigit() else parsedate_to_datetime(header).timestamp() - time.time()
        except (ValueError, OverflowError, TypeError):
            pass
    return ApiError(value, min(5, max(0, retry_after)))


async def request(connection: Connection, method: str, path: str, root: str,
                  body: Any = None) -> tuple[Any, bytes]:
    async with connection.http.stream(method, path, headers=headers(connection), json=body) as response:
        if response.is_redirect:
            raise ProtocolError('Authenticated redirects are forbidden')
        chunks = bytearray()
        async for chunk in response.aiter_bytes():
            if len(chunks) + len(chunk) > MAX_BYTES:
                raise ProtocolError('HTTP response exceeds 64 MiB')
            chunks.extend(chunk)
        raw = bytes(chunks)
        if response.is_error:
            raise _api_error(response, raw)
        value = decode(root, raw)
        return value, raw


async def connect(base_url: str, credential: str, *, timeout: float = 30) -> Connection:
    http = httpx.AsyncClient(base_url=base_url.rstrip('/'), headers={'Authorization': 'Bearer ' + credential},
        follow_redirects=False, timeout=timeout, limits=httpx.Limits(max_connections=8))
    connection = Connection(http, cast(c.BootstrapResponse, {}))
    try:
        value, _ = await request(connection, 'GET', '/api/v1/bootstrap', 'BootstrapResponse')
        check_protocol(value['protocol'])
        check_status(value['status'], value['status'])
        connection.bootstrap = value
        return connection
    except BaseException:
        await http.aclose()
        raise


async def attach(connection: Connection, request_body: c.AttachmentRequest) -> c.AttachmentResponse:
    validate('AttachmentRequest', request_body)
    result, _ = await request(connection, 'POST', route(connection, 'attachment'), 'AttachmentResponse', request_body)
    check_status(connection.bootstrap['status'], result['status'])
    if result['acquisition_id'] != request_body['acquisition_id']:
        raise ProtocolError('Attachment acquisition mismatch')
    connection.attachment = result
    return result


async def status(connection: Connection) -> c.StatusSnapshot:
    result, _ = await request(connection, 'GET', route(connection, 'status'), 'StatusResponse')
    check_status(connection.bootstrap['status'], result['status'])
    return result['status']


async def choices(connection: Connection, body: c.ChoicesRequest) -> c.ChoicesResponse:
    validate('ChoicesRequest', body)
    result, _ = await request(connection, 'POST', route(connection, 'choices'), 'ChoicesResponse', body)
    check_scope(connection.bootstrap['status'], result)
    if (result['correlation_id'], result['state_revision'], result['force_attack']) != (
            body['correlation_id'], body['state_revision'], body['force_attack']):
        raise ProtocolError('Choices correlation mismatch')
    if result['choices']['entity_uuid'] != body['actor_uuid']:
        raise ProtocolError('Choices actor mismatch')
    return result


async def preview(connection: Connection, body: c.PreviewRequest) -> c.PreviewResponse:
    validate('PreviewRequest', body)
    result, _ = await request(connection, 'POST', route(connection, 'preview'), 'PreviewResponse', body)
    check_scope(connection.bootstrap['status'], result)
    echoed = result['request']
    if result['state_revision'] != body['state_revision'] or any(echoed[key] != body[key] for key in (
            'actor_uuid', 'state_revision', 'discovery_generation', 'correlation_id')) or any(
            echoed['selection'].get(key, []) != body['selection'].get(key, []) for key in (
                'action_index', 'target_indices', 'extra_target_positions')) or (
            echoed['selection'].get('prefer_safe', True) != body['selection'].get('prefer_safe', True)):
        raise ProtocolError('Preview correlation mismatch')
    return result


async def submit_command(connection: Connection, body: c.CommandRequest) -> c.ReceiptResponse:
    validate('CommandRequest', body)
    result, _ = await request(connection, 'POST', route(connection, 'commands'), 'ReceiptResponse', body)
    check_scope(connection.bootstrap['status'], result['receipt'])
    if result['receipt']['kind'] == 'committed':
        check_scope(connection.bootstrap['status'], result['receipt']['cursor'])
    if result['receipt']['command_number'] != body['command_number']:
        raise ProtocolError('Command receipt mismatch')
    return result


async def receipt(connection: Connection, number: int) -> c.ReceiptResponse:
    result, _ = await request(connection, 'GET', route(connection, 'commands/' + str(number)), 'ReceiptResponse')
    check_scope(connection.bootstrap['status'], result['receipt'])
    if result['receipt']['kind'] == 'committed':
        check_scope(connection.bootstrap['status'], result['receipt']['cursor'])
    if result['receipt']['command_number'] != number:
        raise ProtocolError('Command receipt mismatch')
    return result


async def acknowledge(connection: Connection, cursor: c.PlayerCursor) -> None:
    result, _ = await request(connection, 'POST', route(connection, 'ack'), 'AckResponse', {'cursor': cursor})
    if result['cursor'] != cursor:
        raise ProtocolError('ACK mismatch')
    check_scope(connection.bootstrap['status'], result['catch_up_cursor'])


async def content(connection: Connection, revision: str) -> c.ContentResponse:
    result, _ = await request(connection, 'GET', '/api/v1/content/' + quote(revision, safe=''), 'ContentResponse')
    if result['revision'] != revision:
        raise ProtocolError('Content revision mismatch')
    return result


async def sse_records(chunks: AsyncIterator[bytes]) -> AsyncIterator[tuple[str, str | None, bytes]]:
    """Bounded SSE framing. An unterminated final event is deliberately discarded."""
    buffer = bytearray()
    data: list[bytes] = []
    size = 0
    event = 'message'
    event_id = None
    skip_lf = False
    first_line = True
    async for chunk in chunks:
        buffer.extend(chunk)
        if skip_lf and buffer:
            if buffer[0] == 10:
                del buffer[0]
            skip_lf = False
        while True:
            cr, lf = buffer.find(b'\r'), buffer.find(b'\n')
            endings = [n for n in (cr, lf) if n >= 0]
            if not endings:
                if len(buffer) + size > MAX_BYTES + 1024:
                    raise ProtocolError('SSE record exceeds 64 MiB')
                break
            end = min(endings)
            skip_lf = buffer[end] == 13 and end + 1 == len(buffer)
            width = 2 if buffer[end:end + 2] == b'\r\n' else 1
            line = bytes(buffer[:end])
            del buffer[:end + width]
            if first_line:
                line = line.removeprefix(b'\xef\xbb\xbf')
                first_line = False
            try:
                line.decode('utf-8', errors='strict')
            except UnicodeError as error:
                raise ProtocolError('Invalid SSE UTF-8') from error
            if not line:
                if data:
                    yield event, event_id, b'\n'.join(data)
                data, size, event, event_id = [], 0, 'message', None
                continue
            size += len(line) + width
            if size > MAX_BYTES + 1024:
                raise ProtocolError('SSE record exceeds 64 MiB')
            field_name, separator, value = line.partition(b':')
            if value.startswith(b' '):
                value = value[1:]
            if field_name == b'data':
                data.append(value)
            elif field_name == b'event':
                event = value.decode('utf-8', errors='strict')
            elif field_name == b'id' and b'\0' not in value:
                event_id = value.decode('utf-8', errors='strict')


async def stream(connection: Connection, after: int) -> AsyncIterator[tuple[str, str | None, bytes]]:
    async with connection.http.stream('GET', route(connection, 'events'), params={'after': after},
            headers=headers(connection), timeout=httpx.Timeout(30, read=45)) as response:
        if response.is_redirect:
            raise ProtocolError('Authenticated redirects are forbidden')
        if response.status_code != 200:
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ProtocolError('Oversized SSE error')
            raise _api_error(response, bytes(body))
        if response.headers.get('content-type', '').split(';')[0] != 'text/event-stream':
            raise ProtocolError('Expected event stream')
        async for record in sse_records(response.aiter_bytes()):
            yield record


Consumer = Callable[[c.InitializationResponse | c.PlayerOperation, bytes], Awaitable[None]]


@dataclass(slots=True)
class Follower:
    connection: Connection
    consumer: Consumer
    consumed: c.PlayerCursor | None = None
    status: c.StatusSnapshot | None = None
    failure: BaseException | None = None
    completed: bool = False
    running: bool = False
    waiters: int = 0
    changed: asyncio.Condition = field(default_factory=asyncio.Condition)


async def _notify(follower: Follower) -> None:
    async with follower.changed:
        follower.changed.notify_all()


async def wait_for_cursor(follower: Follower, cursor: c.PlayerCursor, *, timeout: float = 30) -> None:
    validate('PlayerCursor', cursor)
    check_scope(follower.connection.bootstrap['status'], cursor)
    if follower.consumed is not None and follower.consumed['sequence'] >= cursor['sequence']:
        return
    if follower.waiters >= 64:
        raise ProtocolError('Too many cursor waits')
    follower.waiters += 1
    try:
        async with asyncio.timeout(timeout), follower.changed:
            while follower.consumed is None or follower.consumed['sequence'] < cursor['sequence']:
                if follower.failure is not None:
                    raise follower.failure
                if follower.completed:
                    raise ProtocolError('Final cursor precedes requested cursor')
                if follower.status is not None and follower.status['final_cursor'] is not None and (
                        cursor['sequence'] > follower.status['final_cursor']['sequence']):
                    raise ProtocolError('Final cursor precedes requested cursor')
                await follower.changed.wait()
    finally:
        follower.waiters -= 1


async def follow(follower: Follower, *, reconnect_timeout: float = 60) -> None:
    if follower.running or follower.completed or follower.failure is not None:
        raise ProtocolError('Follower already started or completed')
    follower.running = True
    connection = follower.connection
    retry_since = None
    attempt = 0
    iterator = None
    try:
        initial, raw = await request(connection, 'GET', route(connection, 'initialization'), 'InitializationResponse')
        check_protocol(initial['protocol'])
        check_scope(connection.bootstrap['status'], initial['cursor'])
        await follower.consumer(initial, raw)
        follower.consumed = initial['cursor']
        await _notify(follower)
        while True:
            assert follower.consumed is not None
            iterator = None
            transport_error = None
            try:
                await acknowledge(connection, follower.consumed)
                iterator = stream(connection, follower.consumed['sequence']).__aiter__()
            except (httpx.TransportError, ApiError) as error:
                transport_error = error
            while iterator is not None and transport_error is None:
                try:
                    event, event_id, raw = await anext(iterator)
                except StopAsyncIteration:
                    transport_error = httpx.ReadError('Stream ended before final cursor')
                    break
                except (httpx.TransportError, ApiError) as error:
                    transport_error = error
                    break
                # Consumer failures are deliberately outside transport recovery.
                if event == 'error':
                    raise ApiError(decode('ApiError', raw))
                if event in ('ready', 'status'):
                    packet = decode('StreamReady' if event == 'ready' else 'StreamStatus', raw)
                    check_status(connection.bootstrap['status'], packet['status'])
                    if event == 'ready':
                        check_protocol(packet['protocol'])
                        if packet['after'] != follower.consumed:
                            raise ProtocolError('Resume cursor mismatch')
                        check_scope(connection.bootstrap['status'], packet['head'])
                    follower.status = packet['status']
                    await _notify(follower)
                elif event == 'operation':
                    packet = decode('PlayerOperation', raw)
                    check_protocol(packet['protocol'])
                    check_scope(connection.bootstrap['status'], packet['cursor'])
                    sequence = packet['cursor']['sequence']
                    if event_id != str(sequence):
                        raise ProtocolError('SSE ID/body mismatch')
                    if sequence <= follower.consumed['sequence']:
                        continue
                    if sequence != follower.consumed['sequence'] + 1:
                        raise ProtocolError('Non-contiguous operation')
                    await follower.consumer(packet, raw)
                    follower.consumed = packet['cursor']
                    await _notify(follower)
                    try:
                        await acknowledge(connection, follower.consumed)
                    except (httpx.TransportError, ApiError) as error:
                        transport_error = error
                else:
                    raise ProtocolError('Unknown SSE event')
                retry_since, attempt = None, 0
                if transport_error is None and follower.status is not None and follower.status['final_cursor'] is not None and (
                        follower.consumed['sequence'] >= follower.status['final_cursor']['sequence']):
                    lifecycle = follower.status['boundary']['lifecycle']
                    if lifecycle != 'terminal':
                        raise ApiError({'kind': 'error', 'code': 'game_failed' if lifecycle == 'failed' else 'game_closed',
                            'http_status': 503 if lifecycle == 'failed' else 410, 'retryable': False,
                            'incident_id': follower.status['boundary'].get('incident_id')})
                    follower.completed = True
                    return
            if iterator is not None:
                await iterator.aclose()
            if isinstance(transport_error, ApiError) and not transport_error.value['retryable']:
                raise transport_error
            now = asyncio.get_running_loop().time()
            retry_since = now if retry_since is None else retry_since
            if now - retry_since >= reconnect_timeout:
                raise ProtocolError('Reconnect deadline exceeded') from transport_error
            delay = min(5, .25 * 2 ** min(attempt, 5) * random.uniform(.8, 1.2))
            if isinstance(transport_error, ApiError):
                delay = max(delay, transport_error.retry_after, min(5, transport_error.value.get('retry_after_ms', 0) / 1000))
            await asyncio.sleep(min(delay, max(0, reconnect_timeout - (now - retry_since))))
            attempt += 1
    except BaseException as error:
        follower.failure = error
        raise
    finally:
        try:
            if iterator is not None:
                await iterator.aclose()
        finally:
            follower.running = False
            await _notify(follower)
