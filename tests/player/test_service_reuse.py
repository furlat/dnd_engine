"""Real native workers: reuse, retained replay and independent game authority."""
import asyncio
from time import monotonic
from uuid import uuid4

import httpx
import pytest

from devtools.player_server_acceptance.fixtures import configuration
from server import connection, host as owner, protocol as wire, service
from server.app import create_app
from server.config import ServiceLimits
from server.worker_protocol import EndGame


async def ready(host):
    async with asyncio.timeout(45):
        async with host.changed:
            await host.changed.wait_for(lambda: host.failure is not None or any(
                seat.publication is not None and seat.publication.boundary.input_actor_uuid is not None
                for seat in host.seats.values()))
    assert host.failure is None
    assert host.process is not None
    return host.process.process


def next_config(tmp_path, name, mode='two_sides'):
    return configuration(mode, tmp_path).model_copy(update={'game_id': name})


def admit_end_turn(host):
    seat = next(row for row in host.seats.values() if row.publication.boundary.input_actor_uuid is not None)
    publication = seat.publication
    owner.attach(host, seat, wire.AttachmentRequest(acquisition_id=uuid4(), expected_attachment_epoch=None))
    # Input admission starts at the already consumed published boundary. Exact
    # delivery/ACK is exercised separately through the unchanged SDK transport.
    seat.attachment.highest_sent = publication.cursor.sequence
    owner.acknowledge(host, seat, seat.attachment, publication.cursor)
    command = wire.CommandRequest(command_number=1, actor_uuid=publication.boundary.input_actor_uuid,
        state_revision=publication.state_revision, intent=wire.EndTurnIntent())
    owner.submit(host, seat, command)
    return seat


async def read_prefix(http, host, credential):
    seat = host.seats[credential.seat_id]
    headers = {'Authorization': 'Bearer ' + credential.token, 'X-Game-Epoch': str(host.epoch),
        'X-Audience-Id': str(seat.audience_id)}
    response = await http.post(f'/api/v1/games/{host.config.game_id}/attachment', headers=headers,
        json={'acquisition_id': str(uuid4()), 'expected_attachment_epoch':
            str(seat.attachment.epoch) if seat.attachment else None})
    assert response.status_code == 200, response.text
    headers['X-Attachment-Epoch'] = response.json()['attachment_epoch']
    initial = await http.get(f'/api/v1/games/{host.config.game_id}/initialization', headers=headers)
    stream = await http.get(f'/api/v1/games/{host.config.game_id}/events?after=0', headers=headers)
    assert initial.status_code == stream.status_code == 200
    assert '"lifecycle":"closed"' in stream.text
    return headers, initial.content, stream.content


def test_successive_games_reuse_worker_but_keep_old_replay_and_authority(tmp_path):
    async def exercise():
        config = next_config(tmp_path, 'first')
        app = create_app(config)
        async with app.router.lifespan_context(app):
            hosting = app.state.player_service
            first = app.state.player_host
            process = await ready(first)
            seat = admit_end_turn(first)
            # An admitted mutation finishes before native retirement.
            await service.end_game(hosting, 'first')
            assert seat.receipts[1].receipt.kind == 'committed'
            assert first.process is None and process.returncode is None
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as http:
                old_headers, initial, stream = await read_prefix(http, first, config.credentials[0])
                second_config = next_config(tmp_path, 'second', 'per_entity')
                second = service.start_game(hosting, second_config)
                reused = await ready(second)
                assert reused.pid == process.pid
                assert len(second.seats) == 4 and all(row.next_command_number == 1 for row in second.seats.values())
                assert first.epoch != second.epoch
                old_actors = {actor for row in first.seats.values() for actor in row.publication.audience.controlled}
                new_actors = {actor for row in second.seats.values() for actor in row.publication.audience.controlled}
                assert old_actors.isdisjoint(new_actors)
                assert (await http.get('/api/v1/games/second/status', headers=old_headers)).json()['code'] == 'game_not_found'
                token = second_config.credentials[0].token
                wrong_epoch = {**old_headers, 'Authorization': 'Bearer ' + token}
                assert (await http.get('/api/v1/games/second/status', headers=wrong_epoch)).json()['code'] == 'epoch_mismatch'
                assert (await http.get('/api/v1/games/first/initialization', headers=old_headers)).content == initial
                assert (await http.get('/api/v1/games/first/events?after=0', headers=old_headers)).content == stream
                # Even shutdown of the old Host cannot close the now-reused process.
                await owner.shutdown(first)
                assert reused.returncode is None
                second_seat = admit_end_turn(second)
                await service.end_game(hosting, 'second')
                assert second_seat.receipts[1].receipt.kind == 'committed'
        assert process.returncode == 0 and hosting.workers.count == 0
    asyncio.run(exercise())


def test_simultaneous_worlds_are_isolated_and_failed_worker_is_replaced(tmp_path):
    async def exercise():
        app = create_app(next_config(tmp_path, 'first'))
        async with app.router.lifespan_context(app):
            hosting = app.state.player_service
            first = app.state.player_host
            first_process = await ready(first)
            second = service.start_game(hosting, next_config(tmp_path, 'second'))
            second_process = await ready(second)
            assert first_process.pid != second_process.pid
            second_head = tuple(row.publication for row in second.seats.values())
            first_process.kill()
            await first_process.wait()
            seat = admit_end_turn(first)
            async with asyncio.timeout(15):
                await first.native_done.wait()
            assert first.failure is not None and seat.receipts[1].receipt.kind == 'indeterminate'
            assert tuple(row.publication for row in second.seats.values()) == second_head
            third = service.start_game(hosting, next_config(tmp_path, 'third'))
            third_process = await ready(third)
            assert third_process.pid not in (first_process.pid, second_process.pid)
        assert second_process.returncode == third_process.returncode == 0
        assert hosting.workers.count == 0
    asyncio.run(exercise())


def test_capacity_waiter_reuses_released_worker_and_retention_reserves_budget(tmp_path):
    async def exercise():
        config = next_config(tmp_path, 'first')
        limits = ServiceLimits(max_workers=1, idle_workers=1, max_games=2,
            recording_budget_bytes=4 * config.spool_limit_bytes)
        app = create_app(config, limits=limits)
        async with app.router.lifespan_context(app):
            hosting = app.state.player_service
            first = app.state.player_host
            process = await ready(first)
            second = service.start_game(hosting, next_config(tmp_path, 'second'))
            with pytest.raises(ValueError, match='budget'):
                service.start_game(hosting, next_config(tmp_path, 'over-budget'))
            with pytest.raises(ValueError, match='Credentials'):
                service.start_game(hosting, config.model_copy(update={'game_id': 'reused-credential'}))
            assert set(hosting.games) == {'first', 'second'}
            await service.end_game(hosting, 'first')
            assert (await ready(second)).pid == process.pid
            # Retained history still reserves storage; ending does not evict it.
            with pytest.raises(ValueError, match='budget'):
                service.start_game(hosting, next_config(tmp_path, 'still-over-budget'))
            first.retained_until = monotonic() - 1
            first.work.set()
            async with asyncio.timeout(5):
                await first.task
            third = service.start_game(hosting, next_config(tmp_path, 'third'))
            assert set(hosting.games) == {'second', 'third'}
            await service.end_game(hosting, 'second')
            assert (await ready(third)).pid == process.pid
        assert hosting.workers.count == 0 and process.returncode == 0
    asyncio.run(exercise())


def test_ending_capacity_waiter_does_not_wait_for_or_start_a_world(tmp_path):
    async def exercise():
        app = create_app(next_config(tmp_path, 'first'), limits=ServiceLimits(max_workers=1))
        async with app.router.lifespan_context(app):
            hosting = app.state.player_service
            first = app.state.player_host
            process = await ready(first)
            second = service.start_game(hosting, next_config(tmp_path, 'queued'))
            await asyncio.sleep(0)  # Run the scheduled acquisition, not a timing delay.
            await asyncio.wait_for(service.end_game(hosting, 'queued'), 1)
            assert second.retired and second.process is None
            assert all(seat.publication is None for seat in second.seats.values())
            assert process.returncode is None and first.process.process is process
            second.retained_until = monotonic() - 1
            second.work.set()
            await asyncio.wait_for(second.task, 2)
            assert second.history_expired
        assert process.returncode == 0
    asyncio.run(exercise())


def test_cancelled_and_failed_games_still_expire_their_recordings(tmp_path):
    async def exercise():
        app = create_app(next_config(tmp_path, 'first'))
        async with app.router.lifespan_context(app):
            hosting = app.state.player_service
            first = app.state.player_host
            process = await ready(first)
            first.task.cancel()
            await asyncio.wait_for(first.native_done.wait(), 5)
            assert process.returncode == 0
            bad_config = next_config(tmp_path, 'failed')
            # Real configuration/engine seat disagreement fails inside Start.
            bad_config = bad_config.model_copy(update={'credentials': (bad_config.credentials[0],)})
            failed = service.start_game(hosting, bad_config)
            await asyncio.wait_for(failed.native_done.wait(), 45)
            assert failed.failure is not None
            prepared = service.prepare_game(hosting, next_config(tmp_path, 'prepared'))
            await service.end_game(hosting, 'prepared')
            for host in (first, failed, prepared):
                host.retained_until = monotonic() - 1
                host.work.set()
                await asyncio.wait_for(host.task, 2)
                assert host.history_expired and not host.recording.directory.exists()
        assert hosting.workers.count == 0
    asyncio.run(exercise())


def test_cancelled_service_shutdown_still_closes_active_and_idle_workers(tmp_path):
    async def exercise():
        config = next_config(tmp_path, 'initial')
        hosting = service.create_service(config, ServiceLimits())
        first = hosting.games['initial']
        first.task = asyncio.create_task(owner.run(first))
        first_process = await ready(first)
        second = service.start_game(hosting, next_config(tmp_path, 'second'))
        second_process = await ready(second)
        await service.end_game(hosting, 'initial')
        closing = asyncio.create_task(service.shutdown(hosting))
        await asyncio.sleep(0)  # Enter the shutdown coroutine's first await.
        closing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closing
        assert first_process.returncode == second_process.returncode == 0
        assert hosting.workers.count == 0
    asyncio.run(exercise())


def test_failed_recording_deletion_does_not_free_service_budget(tmp_path, monkeypatch):
    async def exercise():
        config = next_config(tmp_path, 'first')
        hosting = service.create_service(config, ServiceLimits(max_games=1))
        host = hosting.games['first']
        await service.end_game(hosting, 'first')
        host.retained_until = monotonic() - 1
        original_unlink = type(tmp_path).unlink
        def unavailable(path, *args, **kwargs):
            if path.parent == host.recording.directory:
                raise PermissionError('Recording is temporarily locked')
            return original_unlink(path, *args, **kwargs)
        with monkeypatch.context() as failure:
            failure.setattr(type(tmp_path), 'unlink', unavailable)
            host.work.set()
            with pytest.raises(PermissionError, match='locked'):
                await host.task
            assert not host.history_expired
            with pytest.raises(ValueError, match='budget'):
                service.start_game(hosting, next_config(tmp_path, 'second'))
        # Retry the existing owner's expiry once the filesystem is available.
        host.task = asyncio.create_task(owner.retain_final_prefix(host))
        await host.task
        assert host.history_expired
        replacement = service.prepare_game(hosting, next_config(tmp_path, 'second'))
        assert replacement.config.game_id == 'second'
        await service.shutdown(hosting)
    asyncio.run(exercise())


@pytest.mark.parametrize('cancel_retirement', (False, True))
def test_retirement_ack_is_distinct_from_waiting_for_worker_capacity(tmp_path, monkeypatch, cancel_retirement):
    async def exercise():
        app = create_app(next_config(tmp_path, 'first'))
        async with app.router.lifespan_context(app):
            hosting = app.state.player_service
            host = app.state.player_host
            process = await ready(host)
            entered, release = asyncio.Event(), asyncio.Event()
            exchange = connection.exchange
            async def delayed_ack(process, request, recording):
                if isinstance(request, EndGame):
                    entered.set()
                    await release.wait()
                return await exchange(process, request, recording)
            # Delay only the private I/O boundary; the native peer/cleanup stay real.
            with monkeypatch.context() as delay:
                delay.setattr(connection, 'exchange', delayed_ack)
                ending = asyncio.create_task(service.end_game(hosting, 'first'))
                await asyncio.wait_for(entered.wait(), 5)
                if cancel_retirement:
                    host.task.cancel()
                else:
                    repeated = asyncio.create_task(service.end_game(hosting, 'first'))
                    await asyncio.sleep(0)
                release.set()
                await asyncio.wait_for(ending, 5)
                if not cancel_retirement:
                    await repeated
            assert host.native_done.is_set() and not host.task.done()
            if cancel_retirement:
                assert process.returncode == 0
            else:
                second = service.start_game(hosting, next_config(tmp_path, 'second'))
                assert (await ready(second)).pid == process.pid
            host.retained_until = monotonic() - 1
            host.work.set()
            await host.task
            assert host.history_expired
    asyncio.run(exercise())
