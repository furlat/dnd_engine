"""Player callback contracts against native SDK HTTP responses, without an engine process."""
import asyncio
import json

import httpx
from mcp import Client
import pytest
from dnd_player import ApiError, Connection, Follower

from monty_sandbox import player as player_module
from monty_sandbox.app import create_mcp
from monty_sandbox.player import Player, act, close_player, consume_record, discover, open_player, read_game, resolve_receipt, wait_game


ACTOR = '00000000-0000-4000-8000-000000000001'
OPPONENT = '00000000-0000-4000-8000-000000000002'
SUMMON = '00000000-0000-4000-8000-000000000003'
SCOPE = {'game_id': 'test', 'game_epoch': ACTOR, 'audience_id': ACTOR}
CURSOR = {**SCOPE, 'sequence': 1}


def status(actor=ACTOR, revision='r0', lifecycle='waiting_for_human'):
    return {**SCOPE, 'boundary': {'lifecycle': lifecycle,
        'input_actor_uuid': actor, 'state_revision': revision}, 'published_cursor': CURSOR,
        'final_cursor': None, 'attachment_epoch': ACTOR, 'catch_up_cursor': CURSOR,
        'acknowledged_cursor': CURSOR, 'next_command_number': 1, 'pending_command_numbers': []}


def player_for(http):
    connection = Connection(http, {'status': status(), 'audience': audience([ACTOR], 0)})
    player = Player(connection)

    async def consume(packet, raw):
        consume_record(player, packet, raw)

    player.follower = Follower(connection, consume, consumed=CURSOR, status=status())
    return player


def audience(actors, revision):
    return {'controlled': actors, 'observers': actors, 'revision': revision}


def membership_packet(*memberships):
    return {'cursor': CURSOR, 'lineages': [{'events': [
        {'fact': {'kind': 'audience', 'audience': value}} for value in memberships]}]}


def observation_reply(request, current):
    if request.url.path.endswith('/status'):
        return httpx.Response(200, json={'kind': 'status', 'status': current})
    if request.url.path.endswith('/ack'):
        return httpx.Response(200, json={'kind': 'ack', 'cursor': CURSOR, 'catch_up_cursor': CURSOR})
    return None


def test_ambiguous_retry_retains_payload_until_definite_rejection_allows_next_action():
    async def check():
        sent = []

        async def handle(request):
            response = observation_reply(request, status())
            if response is not None:
                return response
            if request.url.path.endswith('/commands'):
                sent.append(json.loads(request.content))
                if len(sent) < 3:
                    raise httpx.ReadError('reply lost')
                if len(sent) == 3:
                    return httpx.Response(403, json={'kind': 'error', 'code': 'forbidden',
                        'http_status': 403, 'retryable': False})
            else:
                assert request.url.path.endswith('/commands/1')
            receipt = {**SCOPE, 'command_number': 1, 'kind': 'unknown'}
            if len(sent) >= 4:
                receipt.update(kind='rejected', reason='stale_state')
            return httpx.Response(200, json={'kind': 'receipt', 'receipt': receipt})

        async with httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(handle)) as http:
            player = player_for(http)
            with pytest.raises(httpx.ReadError, match='reply lost'):
                await act(player, ACTOR, 'r0', {'kind': 'end_turn'})
            pending = (await read_game(player))['unresolved_command']
            assert pending == sent[0] == sent[1]
            with pytest.raises(ApiError, match='forbidden'):
                await resolve_receipt(player)
            observed = await read_game(player)
            assert observed['unresolved_command'] is None
            assert observed['commands'][-1]['api_error']['code'] == 'forbidden'
            following = await act(player, ACTOR, 'r1', {'kind': 'end_turn'})
            assert following['receipt']['kind'] == 'rejected'
            assert sent[:3] == [pending] * 3
            assert sent[3]['state_revision'] == 'r1'
    asyncio.run(check())


@pytest.mark.parametrize('current_actor,expected_timeout', [(OPPONENT, True), (ACTOR, False)])
def test_wait_rechecks_authoritative_boundary_when_stream_status_is_stale(current_actor, expected_timeout):
    async def check():
        async def handle(request):
            response = observation_reply(request, status(current_actor, 'r1'))
            assert response is not None, request.url
            return response

        async with httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(handle)) as http:
            player = player_for(http)  # Last SSE status still says our turn at r0.
            observed = await wait_game(player, timeout_seconds=.02)
            assert observed['wait_timed_out'] is expected_timeout
            assert observed['status']['boundary']['input_actor_uuid'] == current_actor
    asyncio.run(check())


def test_read_tracks_ordered_grants_and_revocations_without_rewriting_history_or_other_games():
    async def check():
        async def handle(request):
            return observation_reply(request, status())

        async with httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(handle)) as http:
            player, other = player_for(http), player_for(http)
            granted = audience([ACTOR, SUMMON], 1)
            packet = membership_packet(granted)
            original = json.dumps(packet)
            consume_record(player, packet, original.encode())
            observed_grant = await read_game(player)
            assert observed_grant['audience'] == granted
            assert (await read_game(other))['audience'] == audience([ACTOR], 0)
            assert player.connection.bootstrap['audience'] == audience([ACTOR], 0)
            revoked = audience([ACTOR], 4)
            packet = membership_packet(audience([ACTOR], 2), audience([ACTOR, SUMMON], 3), revoked)
            # A canceled change is not a new authority grant.
            packet['lineages'][0]['events'].append({'canceled': True,
                'fact': {'kind': 'audience', 'audience': audience([ACTOR, SUMMON], 5)}})
            consume_record(player, packet, json.dumps(packet).encode())
            assert (await read_game(player))['audience'] == revoked
            assert observed_grant['audience'] == granted
            assert json.dumps(player.packets[0]) == original
    asyncio.run(check())


def test_initialization_restores_historical_membership_before_catch_up():
    async def check():
        async def handle(request):
            return observation_reply(request, status())

        async with httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(handle)) as http:
            player = player_for(http)
            player.connection.bootstrap['audience'] = audience([ACTOR, SUMMON], 1)
            initial = {'cursor': {**CURSOR, 'sequence': 0}, 'initialization': {
                'audience': audience([ACTOR], 0), 'nodes': []}}
            consume_record(player, initial, json.dumps(initial).encode())
            assert (await read_game(player))['audience'] == audience([ACTOR], 0)
            packet = membership_packet(audience([ACTOR, SUMMON], 1))
            consume_record(player, packet, json.dumps(packet).encode())
            assert (await read_game(player))['audience'] == player.connection.bootstrap['audience']
    asyncio.run(check())


@pytest.mark.parametrize('lifecycle', ['waiting_for_human', 'waiting_for_codex'])
def test_new_owned_summon_can_wait_and_discover_then_loses_local_discovery_on_revocation(lifecycle):
    async def check():
        async def handle(request):
            response = observation_reply(request, status(SUMMON, 'r1', lifecycle))
            if response is not None:
                return response
            assert request.url.path.endswith('/choices')
            assert json.loads(request.content)['actor_uuid'] == SUMMON
            return httpx.Response(409, json={'kind': 'error', 'code': 'stale_state',
                'http_status': 409, 'retryable': False})

        async with httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(handle)) as http:
            player = player_for(http)
            packet = membership_packet(audience([ACTOR, SUMMON], 1))
            consume_record(player, packet, json.dumps(packet).encode())
            assert not (await wait_game(player, timeout_seconds=.02))['wait_timed_out']
            with pytest.raises(ApiError, match='stale_state'):
                await discover(player)
            packet = membership_packet(audience([ACTOR], 2))
            consume_record(player, packet, json.dumps(packet).encode())
            with pytest.raises(ValueError, match='Not a controlled actor'):
                await discover(player)
            assert (await wait_game(player, timeout_seconds=.02))['wait_timed_out']
    asyncio.run(check())


def test_wait_rechecks_membership_granted_while_waiting_for_another_actor():
    async def check():
        requested = asyncio.Event()
        current = status(OPPONENT)

        async def handle(request):
            response = observation_reply(request, current)
            if request.url.path.endswith('/status'):
                requested.set()
            return response

        async with httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(handle)) as http:
            player = player_for(http)
            waiting = asyncio.create_task(wait_game(player, timeout_seconds=1))
            await requested.wait()
            packet = membership_packet(audience([ACTOR, SUMMON], 1))
            consume_record(player, packet, json.dumps(packet).encode())
            current = status(SUMMON, 'r1')
            async with player.follower.changed:
                player.follower.status = current
                player.follower.changed.notify_all()
            observation = await waiting
            assert not observation['wait_timed_out']
            assert observation['audience']['controlled'] == [ACTOR, SUMMON]
    asyncio.run(check())


@pytest.mark.parametrize('expected_epoch,attached_epoch,raced,error,through_mcp', [
    (None, ACTOR, False, 'Seat already attached', False),
    (OPPONENT, ACTOR, False, 'Expected attachment epoch does not match', False),
    (ACTOR, ACTOR, False, None, False),
    (ACTOR, ACTOR, True, 'attachment_conflict', False),
    (None, None, False, None, False),
    (ACTOR, ACTOR, False, None, True),
])
def test_explicit_resume_uses_exact_attachment_compare_and_swap(monkeypatch, expected_epoch, attached_epoch, raced, error, through_mcp):
    async def check():
        sent = []
        current = {**status(), 'attachment_epoch': attached_epoch}

        async def handle(request):
            response = observation_reply(request, current)
            if response is not None:
                return response
            assert request.url.path.endswith('/attachment')
            body = json.loads(request.content)
            sent.append(body)
            assert body['expected_attachment_epoch'] == expected_epoch
            if raced:
                return httpx.Response(409, json={'kind': 'error', 'code': 'attachment_conflict',
                    'http_status': 409, 'retryable': False})
            current['attachment_epoch'] = SUMMON
            return httpx.Response(200, json={'kind': 'attachment', 'acquisition_id': body['acquisition_id'],
                'attachment_epoch': SUMMON, 'status': {**current, 'attachment_epoch': SUMMON}})

        http = httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(handle))
        connection = Connection(http, {'status': current, 'audience': audience([ACTOR], 0)})

        async def connect(url, credential):
            return connection

        async def follow(follower):
            async with follower.changed:
                follower.consumed = CURSOR
                follower.changed.notify_all()
            await asyncio.Event().wait()

        monkeypatch.setattr(player_module, 'connect', connect)
        monkeypatch.setattr(player_module, 'follow', follow)
        arguments = {} if expected_epoch is None else {'expected_attachment_epoch': expected_epoch}
        if error is not None:
            with pytest.raises((ValueError, ApiError), match=error):
                await open_player('https://peer.invalid', 'seat-test', **arguments)
            assert len(sent) == int(raced)
            assert http.is_closed
        elif through_mcp:
            async with Client(create_mcp({'amber': {'url': 'https://peer.invalid', 'credential': 'seat-test'}})) as client:
                result = await client.call_tool('open_session', {'seat': 'amber',
                    'expected_attachment_epoch': expected_epoch})
                assert not result.is_error, result
                assert result.structured_content['observation']['status']['attachment_epoch'] == SUMMON
                assert len(sent) == 1
            assert http.is_closed
        else:
            player = await open_player('https://peer.invalid', 'seat-test', **arguments)
            assert len(sent) == 1
            assert player.connection.attachment['attachment_epoch'] == SUMMON
            await close_player(player)
            assert http.is_closed
    asyncio.run(check())


def test_wait_returns_at_natural_encounter_end_without_game_shutdown():
    async def check():
        async def handle(request):
            return observation_reply(request, status(None, 'ended', 'outside_encounter'))

        async with httpx.AsyncClient(base_url='https://peer.invalid', transport=httpx.MockTransport(handle)) as http:
            observed = await wait_game(player_for(http), timeout_seconds=.02)
            assert not observed['wait_timed_out']
            assert observed['status']['boundary']['lifecycle'] == 'outside_encounter'
    asyncio.run(check())
