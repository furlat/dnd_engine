"""Player callback contracts against native SDK HTTP responses, without an engine process."""
import asyncio
import json

import httpx
import pytest
from dnd_player import ApiError, Connection, Follower

from monty_sandbox.player import Player, act, read_game, resolve_receipt, wait_game


ACTOR = '00000000-0000-4000-8000-000000000001'
OPPONENT = '00000000-0000-4000-8000-000000000002'
SCOPE = {'game_id': 'test', 'game_epoch': ACTOR, 'audience_id': ACTOR}
CURSOR = {**SCOPE, 'sequence': 1}


def status(actor=ACTOR, revision='r0'):
    return {**SCOPE, 'boundary': {'lifecycle': 'waiting_for_human',
        'input_actor_uuid': actor, 'state_revision': revision}, 'published_cursor': CURSOR,
        'final_cursor': None, 'attachment_epoch': ACTOR, 'catch_up_cursor': CURSOR,
        'acknowledged_cursor': CURSOR, 'next_command_number': 1, 'pending_command_numbers': []}


def player_for(http):
    connection = Connection(http, {'status': status(), 'audience': {'controlled': [ACTOR]}})
    player = Player(connection)

    async def consume(packet, raw):
        player.packets.append(packet)

    player.follower = Follower(connection, consume, consumed=CURSOR, status=status())
    return player


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
