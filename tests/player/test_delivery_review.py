"""Bounded delivery and final failures stay observable at the HTTP boundary."""

import asyncio
import json
from time import monotonic
from uuid import UUID, uuid4

import httpx
import pytest

from dnd.player.audience import PlayerAudience
from dnd.player.facts import PlayerInitialization, PlayerWorld
from player_server import host as owner, protocol as wire, service
from player_server.app import create_app
from player_server.config import SeatCredential, ServerConfig
from player_server.framing import MAX_PACKET_BYTES
from player_server.recording import commit_records, stage_record
from player_server.worker_protocol import Publication


@pytest.fixture
def published(tmp_path):
    token = 'delivery-review-credential'
    app = create_app(ServerConfig(credentials=(SeatCredential(seat_id='party', token=token),),
        spool_directory=tmp_path))
    host = app.state.player_host
    seat = host.seats['party']
    actor = uuid4()
    audience = PlayerAudience((actor,), (actor,))
    initial = wire.InitializationResponse(protocol=wire.protocol_identity(), cursor=owner.cursor(host, seat, 0),
        content_revision='public', content_additions=(), initialization=PlayerInitialization(
            generation=uuid4(), observer_uuid=actor, audience=audience,
            world=PlayerWorld(battlefield_id='review', battlefield_name='Review', bounds=(0, 0, 1, 1),
                width=1, height=1), nodes=(), version_rows=(), end_cursor=0, observations=(), world_updates=()))
    boundary = wire.BoundaryState(lifecycle='terminal', input_actor_uuid=None, state_revision=None)
    operation = wire.PlayerOperation(protocol=wire.protocol_identity(), cursor=owner.cursor(host, seat, 1),
        state_revision='final', boundary=boundary, command_number=None, audience=audience,
        lineages=(), hud=None, combat_log_appends=(), content_additions=())
    for sequence, record in enumerate((initial, operation)):
        commit_records(host.recording, {'party': stage_record(host.recording, 'party', sequence,
            record.model_dump_json().encode())})
    seat.publication = Publication(seat_id='party', cursor=operation.cursor,
        state_revision='final', boundary=boundary, audience=audience, content_revision='public')
    attachment = owner.attach(host, seat, wire.AttachmentRequest(acquisition_id=uuid4(),
        expected_attachment_epoch=None))
    assert seat.attachment is not None
    seat.attachment.highest_sent = 0
    headers = {'Authorization': f'Bearer {token}', 'X-Game-Epoch': str(host.epoch),
        'X-Audience-Id': str(seat.audience_id), 'X-Attachment-Epoch': str(attachment.attachment_epoch)}
    yield app, host, seat, headers
    asyncio.run(owner.shutdown(host))


def test_startup_failure_is_not_reported_as_retryable_starting(published):
    app, host, seat, headers = published
    seat.publication = None
    host.failure = uuid4()

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post('/api/v1/games/encounter/attachment', headers=headers,
                json={'acquisition_id': str(uuid4()), 'expected_attachment_epoch': None})
            assert response.status_code == 503
            assert response.json()['code'] == 'game_failed'
            assert response.json()['retryable'] is False
            assert response.json()['incident_id'] == str(host.failure)

    asyncio.run(exercise())


def test_non_ascii_bearer_is_a_typed_authentication_failure(published):
    app, _, _, _ = published

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.get('/api/v1/bootstrap', headers={b'Authorization': b'Bearer \xff'})
            assert response.status_code == 401
            assert response.json()['code'] == 'unauthenticated'

    asyncio.run(exercise())


@pytest.mark.parametrize('route', ('initialization', 'events?after=0'))
def test_missing_committed_history_returns_nonretryable_resume_error(published, route):
    app, host, _, headers = published
    host.recording.audiences['party'].file.truncate(0)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.get(f'/api/v1/games/encounter/{route}', headers=headers)
            assert response.status_code == 410
            assert response.json()['code'] == 'resume_unavailable'
            assert response.json()['retryable'] is False

    asyncio.run(exercise())


def test_terminal_expiry_keeps_final_status_and_refuses_unavailable_replay(published):
    app, host, seat, headers = published
    final_cursor = seat.publication.cursor
    host.retained_until = monotonic() - 1

    async def exercise():
        await owner.retain_final_prefix(host)
        assert not host.recording.directory.exists()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            status = (await client.get('/api/v1/games/encounter/status', headers=headers)).json()['status']
            assert status['boundary']['lifecycle'] == 'closed'
            assert status['final_cursor'] == final_cursor.model_dump(mode='json')
            response = await client.get('/api/v1/games/encounter/events?after=0', headers=headers)
            assert response.status_code == 410 and response.json()['code'] == 'resume_unavailable'

    asyncio.run(exercise())


def test_shutdown_finishes_a_queued_http_query_with_typed_closed_error(published):
    app, host, seat, headers = published
    actor = seat.publication.audience.controlled[0]
    seat.publication = seat.publication.model_copy(update={'boundary': wire.BoundaryState(
        lifecycle='waiting_for_human', input_actor_uuid=actor, state_revision='final')})
    seat.attachment.highest_sent = 1
    owner.acknowledge(host, seat, seat.attachment, seat.publication.cursor)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            pending = asyncio.create_task(client.post('/api/v1/games/encounter/choices', headers=headers,
                json={'actor_uuid': str(actor), 'state_revision': 'final', 'force_attack': False,
                    'correlation_id': str(uuid4())}))
            async with asyncio.timeout(1):
                await host.work.wait()
                await service.shutdown(app.state.player_service)
                response = await pending
            assert response.status_code == 410
            assert response.json()['code'] == 'game_closed'
            assert response.json()['retryable'] is False

    asyncio.run(exercise())


@pytest.mark.parametrize('finish', ('complete', 'cancel'))
def test_query_delivery_budget_releases_after_socket_finishes(tmp_path, monkeypatch, finish):
    async def exercise():
        token = 'delivery-review-credential'
        app = create_app(ServerConfig(encounter_id=None,
            credentials=(SeatCredential(seat_id='party', token=token),),
            spool_directory=tmp_path, test_seed=0))
        host = app.state.player_host
        host.task = asyncio.create_task(owner.run(host))
        send_task = None
        try:
            async with asyncio.timeout(60):
                async with host.changed:
                    await host.changed.wait_for(lambda: host.failure is not None or (
                        host.seats['party'].publication is not None
                        and host.seats['party'].publication.boundary.lifecycle == 'waiting_for_human'))
            assert host.failure is None
            seat = host.seats['party']
            publication = seat.publication
            assert publication is not None and host.content is not None
            acquired = owner.attach(host, seat, wire.AttachmentRequest(acquisition_id=uuid4(),
                expected_attachment_epoch=None))
            seat.attachment.highest_sent = publication.cursor.sequence
            owner.acknowledge(host, seat, seat.attachment, publication.cursor)
            headers = {'Authorization': f'Bearer {token}', 'X-Game-Epoch': str(host.epoch),
                'X-Audience-Id': str(seat.audience_id), 'X-Attachment-Epoch': str(acquired.attachment_epoch),
                'Content-Type': 'application/json'}
            body = {'actor_uuid': str(publication.boundary.input_actor_uuid),
                'state_revision': publication.state_revision, 'force_attack': False,
                'correlation_id': str(uuid4())}
            endpoint = '/api/v1/games/encounter/choices'
            # One bounded worker response fits, but a slow response must consume
            # that allowance until its socket completes or is canceled.
            monkeypatch.setattr(owner, 'DELIVERY_LIMIT_BYTES', len(host.content) + MAX_PACKET_BYTES)
            sending = asyncio.Event()
            finish_send = asyncio.Event()
            starts = []

            async def receive():
                return {'type': 'http.request', 'body': json.dumps(body).encode(), 'more_body': False}

            async def send(message):
                if message['type'] == 'http.response.start':
                    starts.append(message['status'])
                elif message.get('body'):
                    sending.set()
                    await finish_send.wait()

            scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
                'http_version': '1.1', 'method': 'POST', 'scheme': 'http', 'path': endpoint,
                'raw_path': endpoint.encode(), 'query_string': b'', 'root_path': '',
                'headers': [(key.lower().encode(), value.encode()) for key, value in headers.items()],
                'client': ('127.0.0.1', 1), 'server': ('test', 80)}
            send_task = asyncio.create_task(app(scope, receive, send))
            async with asyncio.timeout(15):
                await sending.wait()
            assert starts == [200]
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                assert (await client.get('/health')).status_code == 200
                refused = await client.post(endpoint, headers=headers, json=body)
                assert refused.status_code == 429 and refused.json()['code'] == 'busy'
                if finish == 'cancel':
                    send_task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await send_task
                else:
                    finish_send.set()
                    await send_task
                recovered = await client.post(endpoint, headers=headers, json=body)
                assert recovered.status_code == 200, recovered.text
                assert wire.ChoicesResponse.model_validate_json(recovered.content).correlation_id == UUID(body['correlation_id'])
        finally:
            if send_task is not None and not send_task.done():
                send_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await send_task
            await service.shutdown(app.state.player_service)

    asyncio.run(exercise())
