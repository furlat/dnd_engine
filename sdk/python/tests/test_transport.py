"""Consumer-visible transport contracts, using an HTTP peer without engine imports."""
import asyncio
import json

import httpx
import pytest

from dnd_player import transport as sdk

UUID = '00000000-0000-4000-8000-000000000001'
SCOPE = {'game_id': 'test', 'game_epoch': UUID, 'audience_id': UUID}
BOUNDARY = {'lifecycle': 'waiting_for_human', 'input_actor_uuid': UUID, 'state_revision': 'r'}


def cursor(sequence):
    return {**SCOPE, 'sequence': sequence}


def status(final=None, lifecycle='terminal'):
    return {**SCOPE, 'boundary': {**BOUNDARY, 'lifecycle': lifecycle if final is not None else 'waiting_for_human'},
        'published_cursor': cursor(final or 0), 'final_cursor': None if final is None else cursor(final),
        'attachment_epoch': UUID, 'catch_up_cursor': cursor(0), 'acknowledged_cursor': None,
        'next_command_number': 1, 'pending_command_numbers': []}


def initialization(sequence=0):
    return {'kind': 'initialization', 'protocol': sdk.IDENTITY, 'cursor': cursor(sequence), 'content_revision': 'r', 'content_additions': [],
        'initialization': {'generation': UUID, 'observer_uuid': UUID, 'world': {'battlefield_id': 'test', 'battlefield_name': 'é',
            'bounds': [-1, -1, 1, 1], 'width': 3, 'height': 3}, 'nodes': [], 'version_rows': [], 'end_cursor': 0,
            'observations': [], 'world_updates': []}}


def operation(sequence):
    return {'kind': 'operation', 'protocol': sdk.IDENTITY, 'cursor': cursor(sequence), 'state_revision': 'r', 'command_number': None,
        'boundary': BOUNDARY, 'audience': {'controlled': [UUID], 'observers': [UUID]}, 'lineages': [], 'hud': None,
        'combat_log_appends': [], 'content_additions': []}


def event(name, value, sequence=None):
    return (f'event: {name}\n' + ('' if sequence is None else f'id: {sequence}\n') + 'data: ' + json.dumps(value) + '\n\n').encode()


def ready(final=None, after=0, lifecycle='terminal'):
    return event('ready', {'kind': 'ready', 'protocol': sdk.IDENTITY, 'after': cursor(after), 'head': cursor(final or 0), 'status': status(final, lifecycle)})


class Peer:
    def __init__(self, streams, initial=None, ack_failure=None):
        self.streams = iter(streams)
        self.initial = initial or initialization()
        self.acks = []
        self.resumes = []
        self.ack_failure = ack_failure

    async def handle(self, request):
        if request.url.path.endswith('/initialization'):
            return httpx.Response(200, json=self.initial)
        if request.url.path.endswith('/ack'):
            value = json.loads(request.content)['cursor']
            self.acks.append(value['sequence'])
            if self.ack_failure is not None:
                result = self.ack_failure(value['sequence'], len(self.acks))
                if result is not None:
                    return result
            return httpx.Response(200, json={'kind': 'ack', 'cursor': value, 'catch_up_cursor': cursor(0)})
        if request.url.path.endswith('/events'):
            self.resumes.append(int(request.url.params['after']))
            return httpx.Response(200, content=next(self.streams), headers={'content-type': 'text/event-stream'})
        raise AssertionError(request.url)

    def connection(self):
        return sdk.Connection(httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(self.handle)),
            {'kind': 'bootstrap', 'protocol': sdk.IDENTITY, 'status': status(), 'audience': None, 'encounter_name': 'test', 'content_revision': 'r'})


def run(coro):
    asyncio.run(coro)


def test_sse_split_utf8_crlf_multiline_comments_and_incomplete_eof():
    async def check():
        async def chunks():
            for byte in b': comment\r\nevent: operation\r\nid: 1\r\ndata: {"name":\r\ndata: "\xc3\xa9"}\r\n\r\nevent: operation\ndata: unfinished':
                yield bytes([byte])
        assert [record async for record in sdk.sse_records(chunks())] == [('operation', '1', b'{"name":\n"\xc3\xa9"}')]
    run(check())


def test_cr_only_blank_line_terminates_at_eof():
    async def check():
        async def chunks():
            yield b'event: operation\rid: 1\rdata: {}\r\r'
        assert [record async for record in sdk.sse_records(chunks())] == [('operation', '1', b'{}')]
    run(check())


def test_duplicate_and_final_prefix_are_consumed_once():
    async def check():
        peer = Peer([ready(2) + event('operation', operation(1), 1) * 2 + event('operation', operation(2), 2)])
        seen = []
        async def consume(packet, raw):
            seen.append(packet['cursor']['sequence'])
            assert json.loads(raw) == packet
        connection = peer.connection()
        async with connection.http:
            follower = sdk.Follower(connection, consume)
            await sdk.follow(follower)
            await sdk.wait_for_cursor(follower, cursor(1))
            with pytest.raises(sdk.ProtocolError):
                await sdk.wait_for_cursor(follower, cursor(3))
        assert seen == [0, 1, 2]
        assert peer.acks == [0, 1, 2]
        assert follower.completed
    run(check())


@pytest.mark.parametrize('packet,sequence', [(operation(2), 2), (operation(1), 2), ({**operation(1), 'cursor': {**cursor(1), 'game_id': 'other'}}, 1)])
def test_gap_id_and_identity_fail_without_ack(packet, sequence):
    async def check():
        peer = Peer([ready() + event('operation', packet, sequence)])
        seen = []
        async def consume(packet, raw):
            seen.append(packet['cursor']['sequence'])
        connection = peer.connection()
        async with connection.http:
            follower = sdk.Follower(connection, consume)
            with pytest.raises(sdk.ProtocolError):
                await sdk.follow(follower)
        assert seen == [0]
        assert peer.acks == [0]
    run(check())


def test_blocked_consumer_failure_keeps_cursor_and_ack_at_previous_operation():
    async def check():
        entered, release = asyncio.Event(), asyncio.Event()
        peer = Peer([ready() + event('operation', operation(1), 1)])
        async def consume(packet, raw):
            if packet['cursor']['sequence']:
                entered.set()
                await release.wait()
                raise ValueError('consumer failed')
        connection = peer.connection()
        async with connection.http:
            follower = sdk.Follower(connection, consume)
            task = asyncio.create_task(sdk.follow(follower))
            await entered.wait()
            assert follower.consumed == cursor(0)
            assert peer.acks == [0]
            release.set()
            with pytest.raises(ValueError, match='consumer failed'):
                await task
            with pytest.raises(ValueError, match='consumer failed'):
                await sdk.wait_for_cursor(follower, cursor(1))
        assert peer.acks == [0]
    run(check())


def test_nonzero_initialization_is_rejected_before_consumption():
    async def check():
        peer = Peer([ready(1, after=1)], initial=initialization(1))
        seen = []
        async def consume(packet, raw):
            seen.append(packet)
        connection = peer.connection()
        async with connection.http:
            with pytest.raises(sdk.ProtocolError):
                await sdk.follow(sdk.Follower(connection, consume))
        assert not seen and not peer.acks
    run(check())


def test_replacement_ack_error_at_final_cursor_is_not_suppressed():
    async def check():
        peer = Peer([ready(1) + event('operation', operation(1), 1)], ack_failure=lambda sequence, _: httpx.Response(409,
            json={'kind': 'error', 'code': 'attachment_replaced', 'http_status': 409, 'retryable': False}) if sequence == 1 else None)
        async def consume(packet, raw):
            pass
        connection = peer.connection()
        async with connection.http:
            follower = sdk.Follower(connection, consume)
            with pytest.raises(sdk.ApiError) as failure:
                await sdk.follow(follower)
            assert failure.value.value['code'] == 'attachment_replaced'
            assert not follower.completed
    run(check())


def test_wrong_identity_inside_final_cursor_is_rejected():
    async def check():
        state = status(0)
        state['final_cursor']['game_id'] = 'other'
        peer = Peer([event('ready', {'kind': 'ready', 'protocol': sdk.IDENTITY, 'after': cursor(0), 'head': cursor(0), 'status': state})])
        async def consume(packet, raw):
            pass
        connection = peer.connection()
        async with connection.http:
            with pytest.raises(sdk.ProtocolError):
                await sdk.follow(sdk.Follower(connection, consume))
    run(check())


def test_lost_ack_reply_resends_consumed_cursor_without_second_consumption():
    async def check():
        def lose_first_ack(sequence, count):
            if sequence == 1 and count == 2:
                raise httpx.ReadError('reply lost')
        peer = Peer([ready(1) + event('operation', operation(1), 1), ready(1, after=1)], ack_failure=lose_first_ack)
        seen = []
        async def consume(packet, raw):
            seen.append(packet['cursor']['sequence'])
        connection = peer.connection()
        async with connection.http:
            await sdk.follow(sdk.Follower(connection, consume))
        assert seen == [0, 1]
        assert peer.acks == [0, 1, 1]
        assert peer.resumes == [0, 1]
    run(check())


def test_incomplete_eof_reconnects_from_consumed_cursor():
    async def check():
        peer = Peer([ready(1) + event('operation', operation(1), 1)[:-1], ready(1) + event('operation', operation(1), 1)])
        seen = []
        async def consume(packet, raw):
            seen.append(packet['cursor']['sequence'])
        connection = peer.connection()
        async with connection.http:
            await sdk.follow(sdk.Follower(connection, consume))
        assert seen == [0, 1]
        assert peer.acks == [0, 0, 1]
        assert peer.resumes == [0, 0]
    run(check())


def test_cancellation_during_consumer_preserves_progress_and_releases_waiters():
    async def check():
        entered = asyncio.Event()
        peer = Peer([ready() + event('operation', operation(1), 1)])
        async def consume(packet, raw):
            if packet['cursor']['sequence']:
                entered.set()
                await asyncio.Future()
        connection = peer.connection()
        async with connection.http:
            follower = sdk.Follower(connection, consume)
            task = asyncio.create_task(sdk.follow(follower))
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            with pytest.raises(asyncio.CancelledError):
                await sdk.wait_for_cursor(follower, cursor(1))
            assert follower.consumed == cursor(0)
            assert follower.waiters == 0 and not follower.running
        assert peer.acks == [0]
    run(check())


def test_failed_final_prefix_drains_before_typed_error():
    async def check():
        peer = Peer([ready(1, lifecycle='failed') + event('operation', operation(1), 1)])
        seen = []
        async def consume(packet, raw):
            seen.append(packet['cursor']['sequence'])
        connection = peer.connection()
        async with connection.http:
            follower = sdk.Follower(connection, consume)
            with pytest.raises(sdk.ApiError) as failure:
                await sdk.follow(follower)
            assert failure.value.value['code'] == 'game_failed'
            await sdk.wait_for_cursor(follower, cursor(1))
            with pytest.raises(sdk.ApiError):
                await sdk.wait_for_cursor(follower, cursor(2))
        assert seen == [0, 1]
        assert peer.resumes == [0]
    run(check())


def test_oversized_unfinished_sse_line_is_rejected_before_json_decode():
    async def check():
        async def chunks():
            for _ in range(65):
                yield b'a' * (1024 * 1024)
        with pytest.raises(sdk.ProtocolError, match='64 MiB'):
            async for _ in sdk.sse_records(chunks()):
                pytest.fail('unfinished line dispatched')
    run(check())


def test_overflowing_json_number_is_rejected():
    with pytest.raises(sdk.ProtocolError):
        sdk.decode('ResidueEllipse', b'{"center":[0,0],"radius_x":1e999,"radius_y":1}')


@pytest.mark.parametrize('root,value', [
    ('PlayerCursor', {**cursor(0), 'extra': 1}),
    ('PlayerCursor', {**cursor(0), 'game_epoch': 'invalid-uuid'}),
    ('PlayerCursor', {**cursor(0), 'audience_id': UUID.replace('-', '')}),
    ('PlayerCursor', {**cursor(0), 'sequence': 10 ** 100}),
    ('CommandRequest', {'command_number': 1, 'actor_uuid': UUID, 'state_revision': 'r',
        'intent': {'kind': 'unknown'}}),
    ('CommandRequest', {'command_number': 1, 'actor_uuid': UUID, 'state_revision': 'r',
        'intent': {'kind': 'end_turn', 'selection': {}}}),
    ('ActionSelection', {'action_index': 0, 'target_indices': [], 'extra_target_positions': [[1]]}),
    ('ActionSelection', {'action_index': 0, 'target_indices': [], 'extra_target_positions': [[1, 2, 3]]}),
    ('ActionSelection', {'action_index': 0, 'target_indices': [], 'extra_target_positions': [[1, '2']]}),
    ('ActionSelection', {'action_index': 0, 'target_indices': [], 'extra_target_positions': [[True, 2]]}),
])
def test_published_schema_rejects_extras_formats_unions_and_invalid_tuples(root, value):
    with pytest.raises(sdk.ProtocolError):
        sdk.decode(root, json.dumps(value).encode())
    with pytest.raises(sdk.ProtocolError):
        sdk.validate(root, value)


@pytest.mark.parametrize('number', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_python_values_cannot_become_nullable_json_fields(number):
    value = {'entity_name': 'Mover', 'entity_uuid': UUID, 'observation_complete': True,
        'observed_path_segments': [], 'observed_distance_feet': 0, 'distance_feet': number}
    with pytest.raises(sdk.ProtocolError):
        sdk.validate('ObservedMovementLogData', value)
    with pytest.raises(sdk.ProtocolError):
        sdk.decode('ObservedMovementLogData', json.dumps(value).encode())


def test_validation_preserves_optional_fields_and_nullable_values():
    value = {'entity_name': 'Mover', 'entity_uuid': UUID, 'observation_complete': True,
        'observed_path_segments': [], 'observed_distance_feet': 0, 'distance_feet': None}
    original = json.dumps(value)
    assert sdk.validate('ObservedMovementLogData', value) is value
    assert json.dumps(value) == original
    assert sdk.decode('ObservedMovementLogData', original.encode()) == value


@pytest.mark.parametrize('value', [object(), {1: 'non-string key'}])
def test_non_json_python_values_raise_protocol_error(value):
    with pytest.raises(sdk.ProtocolError):
        sdk.validate('PlayerCursor', value)


def test_choices_for_different_actor_are_rejected():
    async def check():
        body = {'actor_uuid': UUID, 'state_revision': 'r', 'force_attack': False, 'correlation_id': UUID}
        reply = {**SCOPE, 'kind': 'choices', 'state_revision': 'r', 'force_attack': False, 'correlation_id': UUID,
            'choices': {'entity_uuid': '00000000-0000-4000-8000-000000000002'}}
        peer = Peer([])
        connection = peer.connection()
        await connection.http.aclose()
        async with httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(lambda _: httpx.Response(200, json=reply))) as http:
            connection.http = http
            with pytest.raises(sdk.ProtocolError):
                await sdk.choices(connection, body)
    run(check())


def test_cursor_waiters_are_bounded_and_cancelled_registrations_are_released():
    async def check():
        async def consume(packet, raw):
            pass
        connection = Peer([]).connection()
        async with connection.http:
            follower = sdk.Follower(connection, consume)
            waits = [asyncio.create_task(sdk.wait_for_cursor(follower, cursor(1))) for _ in range(64)]
            registered = asyncio.Event()
            asyncio.get_running_loop().call_soon(registered.set)
            await registered.wait()
            with pytest.raises(sdk.ProtocolError, match='Too many'):
                await sdk.wait_for_cursor(follower, cursor(1))
            for task in waits:
                task.cancel()
            results = await asyncio.gather(*waits, return_exceptions=True)
            assert all(isinstance(result, asyncio.CancelledError) for result in results)
            assert follower.waiters == 0
    run(check())


def test_command_reply_loss_is_surfaced_without_automatic_command_retry():
    async def check():
        sent = []
        async def handle(request):
            if request.method == 'POST':
                sent.append(json.loads(request.content))
                raise httpx.ReadError('reply lost')
            assert request.url.path.endswith('/commands/1')
            return httpx.Response(200, json={'kind': 'receipt', 'receipt': {**SCOPE, 'kind': 'committed', 'command_number': 1, 'cursor': cursor(1)}})
        connection = Peer([]).connection()
        await connection.http.aclose()
        async with httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(handle)) as http:
            connection.http = http
            body = {'command_number': 1, 'actor_uuid': UUID, 'state_revision': 'r', 'intent': {'kind': 'end_turn'}}
            with pytest.raises(httpx.ReadError, match='reply lost'):
                await sdk.submit_command(connection, body)
            result = await sdk.receipt(connection, 1)
        assert sent == [body]
        assert result['receipt']['kind'] == 'committed'
    run(check())


@pytest.mark.parametrize('sequence', [9007199254740992, -1, '1', True])
def test_cursor_rejects_unsafe_or_coerced_ordering(sequence):
    with pytest.raises(sdk.ProtocolError):
        sdk.decode('PlayerCursor', json.dumps(cursor(sequence)).encode())


def test_maximum_safe_cursor_and_signed_unicode_initialization_validate():
    assert sdk.decode('PlayerCursor', json.dumps(cursor(9007199254740991)).encode()) == cursor(9007199254740991)
    assert sdk.decode('InitializationResponse', json.dumps(initialization(), ensure_ascii=False).encode()) == initialization()
    with pytest.raises(sdk.ProtocolError):
        sdk.decode('PlayerCursor', json.dumps(cursor(0)).encode('utf-16'))


def test_unknown_version_and_tag_stop_before_consumption():
    wrong = operation(1)
    wrong['protocol'] = {**sdk.IDENTITY, 'protocol_version': 2}
    with pytest.raises(sdk.ProtocolError):
        sdk.decode('PlayerOperation', json.dumps(wrong).encode())
    wrong = operation(1)
    wrong['kind'] = 'objective'
    with pytest.raises(sdk.ProtocolError):
        sdk.decode('PlayerOperation', json.dumps(wrong).encode())


def test_cursor_wait_deadline_releases_its_registration():
    async def check():
        async def consume(packet, raw):
            pass
        connection = Peer([]).connection()
        async with connection.http:
            follower = sdk.Follower(connection, consume)
            with pytest.raises(TimeoutError):
                await sdk.wait_for_cursor(follower, cursor(1), timeout=0)
            assert follower.waiters == 0
    run(check())
