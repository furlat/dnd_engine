"""Command admission and JSON failures stay at the authorized HTTP boundary."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from server import host as owner, protocol as wire, service
from server.app import create_app
from server.config import SeatCredential, ServerConfig
from server.recording import commit_records, stage_record
from server.worker_protocol import Publication
from dnd.player.audience import PlayerAudience
from dnd.player.facts import PlayerInitialization, PlayerWorld


def test_stale_and_out_of_turn_commands_keep_receipts_but_foreign_actor_does_not(tmp_path):
    async def exercise():
        token = "review-seat-credential-only"
        app = create_app(ServerConfig(encounter_id=None,
            credentials=(SeatCredential(seat_id="party", token=token),),
            spool_directory=tmp_path, test_seed=0))
        host = app.state.player_host
        host.task = asyncio.create_task(owner.run(host))
        try:
            async with asyncio.timeout(60):
                async with host.changed:
                    await host.changed.wait_for(lambda: host.failure is not None or (
                        host.seats["party"].publication is not None
                        and host.seats["party"].publication.boundary.lifecycle == "waiting_for_human"))
            assert host.failure is None
            seat = host.seats["party"]
            publication = seat.publication
            assert publication is not None
            acquired = owner.attach(host, seat, wire.AttachmentRequest(
                acquisition_id=uuid4(), expected_attachment_epoch=None))
            assert seat.attachment is not None
            # This admission test starts after the attachment consumed its head.
            seat.attachment.highest_sent = publication.cursor.sequence
            owner.acknowledge(host, seat, seat.attachment, publication.cursor)
            headers = {"Authorization": f"Bearer {token}", "X-Game-Epoch": str(host.epoch),
                "X-Audience-Id": str(seat.audience_id),
                "X-Attachment-Epoch": str(acquired.attachment_epoch)}
            endpoint = "/api/v1/games/encounter/commands"
            active = publication.boundary.input_actor_uuid
            other = next(identity for identity in publication.audience.controlled if identity != active)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                for number, actor, revision, reason in (
                    (1, active, "old-state", "stale_state"),
                    (2, other, publication.state_revision, "not_your_turn"),
                ):
                    body = {"command_number": number, "actor_uuid": str(actor),
                        "state_revision": revision, "intent": {"kind": "end_turn"}}
                    response = await client.post(endpoint, headers=headers, json=body)
                    assert response.status_code == 202, response.text
                    async with asyncio.timeout(10):
                        async with host.changed:
                            await host.changed.wait_for(lambda: seat.receipts[number].receipt.kind != "pending")
                    receipt = seat.receipts[number].receipt
                    assert receipt.kind == "rejected" and receipt.reason == reason
                    repeated = await client.post(endpoint, headers=headers, json=body)
                    assert repeated.status_code == 200
                    assert repeated.json()["receipt"] == receipt.model_dump(mode="json")
                    assert seat.next_command_number == number + 1
                    assert seat.publication == publication

                response = await client.post(endpoint, headers=headers, json={
                    "command_number": 3, "actor_uuid": str(uuid4()),
                    "state_revision": publication.state_revision, "intent": {"kind": "end_turn"}})
                assert response.status_code == 403
                assert seat.next_command_number == 3 and 3 not in seat.receipts
        finally:
            await service.shutdown(app.state.player_service)

    asyncio.run(exercise())


@pytest.mark.parametrize("value", (True, "0", 0.0))
def test_action_selection_handles_do_not_coerce_json_scalars(value):
    body = {"command_number": 1, "actor_uuid": str(uuid4()), "state_revision": "current",
        "intent": {"kind": "execute_selection", "discovery_generation": 1,
            "selection": {"action_index": value, "target_indices": [0], "extra_target_positions": []}}}
    with pytest.raises(ValueError):
        wire.CommandRequest.model_validate_json(json.dumps(body))


@pytest.mark.parametrize("value", (True, "0"))
def test_position_selection_does_not_coerce_json_scalars(value):
    body = {"command_number": 1, "actor_uuid": str(uuid4()), "state_revision": "current",
        "intent": {"kind": "execute_selection", "discovery_generation": 1,
            "selection": {"action_index": 0, "target_indices": [0], "extra_target_positions": [[value, -1]]}}}
    with pytest.raises(ValueError):
        wire.CommandRequest.model_validate_json(json.dumps(body))


def test_game_scoped_status_checks_epoch_and_audience_headers(tmp_path):
    async def exercise():
        token = "review-seat-credential-only"
        app = create_app(ServerConfig(credentials=(SeatCredential(seat_id="party", token=token),),
            spool_directory=tmp_path))
        host = app.state.player_host
        try:
            seat = host.seats["party"]
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/games/encounter/status", headers={
                    "Authorization": f"Bearer {token}", "X-Game-Epoch": str(uuid4()),
                    "X-Audience-Id": str(seat.audience_id)})
                assert response.status_code == 409
                assert response.json()["code"] == "epoch_mismatch"
                response = await client.get("/api/v1/games/encounter/status", headers={
                    "Authorization": f"Bearer {token}", "X-Game-Epoch": str(host.epoch),
                    "X-Audience-Id": str(uuid4())})
                assert response.status_code == 403
                assert response.json()["code"] == "audience_mismatch"
        finally:
            await service.shutdown(app.state.player_service)

    asyncio.run(exercise())


def test_stream_drains_terminal_publication_that_arrives_during_send(tmp_path):
    async def exercise():
        token = "review-seat-credential-only"
        app = create_app(ServerConfig(credentials=(SeatCredential(seat_id="party", token=token),),
            spool_directory=tmp_path))
        host = app.state.player_host
        seat = host.seats["party"]
        actor = uuid4()
        audience = PlayerAudience((actor,), (actor,))
        protocol = wire.protocol_identity()
        initial = wire.InitializationResponse(protocol=protocol, cursor=owner.cursor(host, seat, 0),
            content_revision="public", content_additions=(), initialization=PlayerInitialization(
                generation=uuid4(), observer_uuid=actor, audience=audience,
                world=PlayerWorld(battlefield_id="review", battlefield_name="Review", bounds=(0, 0, 1, 1),
                    width=1, height=1), nodes=(), version_rows=(), end_cursor=0,
                observations=(), world_updates=()))

        def publish(sequence, lifecycle):
            boundary = wire.BoundaryState(lifecycle=lifecycle, input_actor_uuid=None, state_revision=None)
            publication = Publication(seat_id="party", cursor=owner.cursor(host, seat, sequence),
                state_revision=f"revision-{sequence}", boundary=boundary, audience=audience,
                content_revision="public")
            record = wire.PlayerOperation(protocol=protocol, cursor=publication.cursor,
                state_revision=publication.state_revision, boundary=boundary, command_number=None,
                audience=audience, lineages=(), hud=None, combat_log_appends=(), content_additions=())
            commit_records(host.recording, {"party": stage_record(host.recording, "party", sequence,
                record.model_dump_json().encode())})
            seat.publication = publication

        commit_records(host.recording, {"party": stage_record(host.recording, "party", 0,
            initial.model_dump_json().encode())})
        publish(1, "advancing")
        acquired = owner.attach(host, seat, wire.AttachmentRequest(
            acquisition_id=uuid4(), expected_attachment_epoch=None))
        assert seat.attachment is not None
        seat.attachment.highest_sent = 0
        messages = []

        async def send(message):
            messages.append(message)
            if message["type"] == "http.response.body" and message.get("body", b"").startswith(b"id: 1\n"):
                publish(2, "terminal")
                await owner.changed(host)

        async def receive():
            await asyncio.Future()

        headers = {"authorization": f"Bearer {token}", "x-game-epoch": str(host.epoch),
            "x-audience-id": str(seat.audience_id), "x-attachment-epoch": str(acquired.attachment_epoch)}
        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": "GET", "scheme": "http", "root_path": "",
            "path": "/api/v1/games/encounter/events", "query_string": b"after=0",
            "headers": [(key.encode(), value.encode()) for key, value in headers.items()],
            "client": ("127.0.0.1", 12345), "server": ("test", 80)}
        try:
            await asyncio.wait_for(app(scope, receive, send), 3)
            operations = [message["body"].split(b"\n", 1)[0] for message in messages
                if message["type"] == "http.response.body" and message.get("body", b"").startswith(b"id:")]
            assert operations == [b"id: 1", b"id: 2"]
        finally:
            await service.shutdown(app.state.player_service)

    asyncio.run(exercise())
