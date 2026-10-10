"""Transport authority and atomic publication, independent of gameplay rules."""
import asyncio
from collections import deque
import struct
import sys
from uuid import uuid4

import httpx
import pytest

from dnd.player.audience import PlayerAudience
from server import connection, host as owner, protocol as wire
from server.app import create_app
from server.config import SeatCredential, ServerConfig
from server.recording import commit_records, stage_record
from server.worker_protocol import Advance, Publication, Reply


def setup_host(tmp_path, seats=('a',)):
    app = create_app(ServerConfig(credentials=tuple(SeatCredential(seat_id=seat,
        token=f'{seat}-transport-test-credential') for seat in seats), spool_directory=tmp_path,
        allowed_origins=('http://localhost:5173',)))
    host = app.state.player_host
    for seat in host.seats.values():
        actor = uuid4()
        seat.publication = Publication(seat_id=seat.seat_id, cursor=owner.cursor(host, seat, 0),
            state_revision='initial', audience=PlayerAudience((actor,), (actor,)), content_revision='public',
            boundary=wire.BoundaryState(lifecycle='waiting_for_human', input_actor_uuid=actor, state_revision='initial'))
        commit_records(host.recording, {seat.seat_id: stage_record(host.recording, seat.seat_id, 0, b'{}')})
    return app, host


def test_attachment_retry_replacement_ack_authority_and_cors(tmp_path):
    async def exercise():
        app, host = setup_host(tmp_path)
        seat = host.seats['a']
        headers = {'Authorization': 'Bearer a-transport-test-credential',
            'X-Game-Epoch': str(host.epoch), 'X-Audience-Id': str(seat.audience_id)}
        path = '/api/v1/games/encounter/'
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                for origin, code in [('http://localhost:5173', 200), ('http://untrusted.example', 400)]:
                    response = await client.options(path+'attachment', headers={'Origin': origin,
                        'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Authorization'})
                    assert response.status_code == code
                request = {'acquisition_id': str(uuid4()), 'expected_attachment_epoch': None}
                acquired = await client.post(path+'attachment', json=request, headers=headers)
                repeated = await client.post(path+'attachment', json=request, headers=headers)
                assert acquired.status_code == repeated.status_code == 200
                first_epoch = acquired.json()['attachment_epoch']
                assert repeated.json()['attachment_epoch'] == first_epoch
                first_headers = {**headers, 'X-Attachment-Epoch': first_epoch}
                # Zero has not been delivered yet: even ACK(0) cannot claim unseen consumption.
                response = await client.post(path+'ack', json={'cursor': owner.cursor(host, seat, 0).model_dump(mode='json')}, headers=first_headers)
                assert response.json()['code'] == 'invalid_cursor'
                assert (await client.get(path+'initialization', headers=first_headers)).status_code == 200
                assert (await client.post(path+'ack', json={'cursor': owner.cursor(host, seat, 0).model_dump(mode='json')}, headers=first_headers)).status_code == 200
                replacement = await client.post(path+'attachment', headers=headers, json={
                    'acquisition_id': str(uuid4()), 'expected_attachment_epoch': first_epoch})
                assert replacement.status_code == 200 and replacement.json()['attachment_epoch'] != first_epoch
                assert (await client.get(path+'initialization', headers=first_headers)).json()['code'] == 'attachment_replaced'
                assert (await client.post(path+'attachment', json=request, headers=headers)).json()['code'] == 'attachment_conflict'
                assert host.pending is None and seat.next_command_number == 1
        finally:
            await owner.shutdown(host)
    asyncio.run(exercise())


def test_command_conflict_busy_and_capacity_do_not_create_a_second_reservation(tmp_path):
    async def exercise():
        app, host = setup_host(tmp_path)
        seat = host.seats['a']
        attachment = owner.attach(host, seat, wire.AttachmentRequest(acquisition_id=uuid4(), expected_attachment_epoch=None))
        assert seat.attachment is not None and seat.publication is not None
        seat.attachment.highest_sent = 0
        owner.acknowledge(host, seat, seat.attachment, owner.cursor(host, seat, 0))
        headers = {'Authorization': 'Bearer a-transport-test-credential', 'X-Game-Epoch': str(host.epoch),
            'X-Audience-Id': str(seat.audience_id), 'X-Attachment-Epoch': str(attachment.attachment_epoch)}
        body = {'command_number': 1, 'actor_uuid': str(seat.publication.boundary.input_actor_uuid),
            'state_revision': 'initial', 'intent': {'kind': 'end_turn'}}
        path = '/api/v1/games/encounter/commands'
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                host.blocked = True
                refused = await client.post(path, headers=headers, json=body)
                assert refused.json()['code'] == 'recording_capacity' and seat.next_command_number == 1
                host.blocked = False
                pending = await client.post(path, headers=headers, json=body)
                repeated = await client.post(path, headers=headers, json=body)
                assert pending.status_code == repeated.status_code == 202
                assert pending.json() == repeated.json()
                conflict = await client.post(path, headers=headers, json={**body, 'state_revision': 'different'})
                assert conflict.json()['code'] == 'command_conflict'
                busy = await client.post(path, headers=headers, json={**body, 'command_number': 2})
                assert busy.json()['code'] == 'busy'
                assert seat.next_command_number == 2 and len(seat.receipts) == 1
        finally:
            await owner.shutdown(host)
        # An admitted command with no completed native worker result is never declared rejected.
        assert seat.receipts[1].receipt.kind == 'indeterminate'
    asyncio.run(exercise())


def test_second_audience_spool_failure_exposes_neither_new_publication(tmp_path, monkeypatch):
    async def exercise():
        _, host = setup_host(tmp_path, ('a', 'b'))
        before = {key: seat.publication for key, seat in host.seats.items()}
        publications = tuple(value.model_copy(update={'cursor': owner.cursor(host, host.seats[key], 1)})
            for key, value in before.items())
        reply = Reply(publications=publications)
        packet = lambda value: struct.pack('!I', len(value)) + value
        frames = packet(reply.model_dump_json().encode()) + packet(b'{"next":"a"}') + packet(b'{"next":"b"}')
        # A tiny real pipe peer is the I/O fault fixture, not an alternative native engine.
        script = 'import sys,struct; n=struct.unpack("!I",sys.stdin.buffer.read(4))[0];sys.stdin.buffer.read(n);sys.stdout.buffer.write(bytes.fromhex(sys.argv[1]));sys.stdout.buffer.flush()'
        process = await asyncio.create_subprocess_exec(sys.executable, '-c', script, frames.hex(),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        async def drain():
            assert process.stderr is not None
            await process.stderr.read()
        host.process = connection.Connection(process, deque(), asyncio.create_task(drain()))
        original = connection.stage_record
        def fail_second(recording, seat, sequence, payload):
            if seat == 'b':
                raise OSError('Injected disk failure on second audience')
            return original(recording, seat, sequence, payload)
        monkeypatch.setattr(connection, 'stage_record', fail_second)
        try:
            with pytest.raises(OSError, match='second audience'):
                await owner._exchange(host, Advance())
            assert {key: seat.publication for key, seat in host.seats.items()} == before
            for spool in host.recording.audiences.values():
                assert len(spool.offsets) == 1 and spool.path.stat().st_size == spool.committed_bytes
        finally:
            await connection.close(host.process)
            await owner.shutdown(host)
    asyncio.run(exercise())
