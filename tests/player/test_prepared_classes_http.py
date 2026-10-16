"""Real HTTP/process lane for class preparation after combat.

Boundary: authenticated HTTP -> native worker -> retained SSE/HUD.
Input: a real Cleric10 ends combat with Sunder, then changes preparation.
Output: persistent Intervention use and accepted preparation, with stale,
foreign-actor and ordinary turn commands rejected without another operation.
This deliberately starts one native process; it is transport qualification.
"""

import asyncio
from uuid import uuid4

import httpx

from dnd.types.character_progression import CharacterClass, PreparedSpellSelection
from server import host as owner
from server import protocol as wire
from server import service
from server.app import create_app
from server.config import SeatCredential, ServerConfig
from tests.player.test_compact_choices import rows
from tests.progression.prepared_class_support import prepared_build


async def receive_operations(app, headers, *, after, through):
    """Consume actual SSE bytes and disconnect after the requested committed head."""
    delivered = asyncio.Event()
    chunks = []
    request_sent = False
    status = None
    marker = f"id: {through}\nevent: operation\ndata: ".encode()

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await delivered.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
        elif message.get("body"):
            chunks.append(message["body"])
            body = b"".join(chunks)
            if marker in body and body.endswith(b"\n\n"):
                delivered.set()

    path = "/api/v1/games/encounter/events"
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": f"after={after}".encode(),
        "root_path": "",
        "headers": [
            (key.lower().encode(), value.encode()) for key, value in headers.items()
        ],
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
    }
    async with asyncio.timeout(15):
        await app(scope, receive, send)
    assert status == 200
    return tuple(
        wire.PlayerOperation.model_validate_json(frame.split(b"\ndata: ", 1)[1])
        for frame in b"".join(chunks).split(b"\n\n")
        if b"\nevent: operation\ndata: " in frame
    )


async def completed_receipt(client, host, seat, headers, body):
    """Wait for the owner's completion signal, then read the public receipt."""
    endpoint = "/api/v1/games/encounter/commands"
    accepted = await client.post(endpoint, headers=headers, json=body)
    assert accepted.status_code == 202, accepted.text
    number = body["command_number"]
    async with asyncio.timeout(30):
        async with host.changed:
            await host.changed.wait_for(
                lambda: (
                    host.failure is not None
                    or seat.receipts[number].receipt.kind != "pending"
                )
            )
    assert host.failure is None
    result = await client.get(f"{endpoint}/{number}", headers=headers)
    assert result.status_code == 200
    return wire.ReceiptResponse.model_validate_json(result.text).receipt


def command(number, actor, revision, intent):
    return {
        "command_number": number,
        "actor_uuid": str(actor),
        "state_revision": revision,
        "intent": intent,
    }


def test_http_preparation_after_combat_preserves_permanent_use_and_authority(tmp_path):
    async def exercise():
        token = "prepared-class-http-test-credential"
        app = create_app(
            ServerConfig(
                encounter_id=None,
                credentials=(SeatCredential(seat_id="party", token=token),),
                spool_directory=tmp_path,
                test_seed=6,
                player_builds=(prepared_build(CharacterClass.CLERIC, 10),),
            )
        )
        host = app.state.player_host
        host.task = asyncio.create_task(owner.run(host))
        try:
            async with asyncio.timeout(60):
                async with host.changed:
                    await host.changed.wait_for(
                        lambda: (
                            host.failure is not None
                            or (
                                host.seats["party"].publication is not None
                                and host.seats["party"].publication.boundary.lifecycle
                                == "waiting_for_human"
                            )
                        )
                    )
            assert host.failure is None
            seat = host.seats["party"]
            publication = seat.publication
            actor = publication.boundary.input_actor_uuid
            assert actor is not None
            base_headers = {
                "Authorization": f"Bearer {token}",
                "X-Game-Epoch": str(host.epoch),
                "X-Audience-Id": str(seat.audience_id),
            }
            path = "/api/v1/games/encounter/"
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                attachment = await client.post(
                    path + "attachment",
                    headers=base_headers,
                    json={
                        "acquisition_id": str(uuid4()),
                        "expected_attachment_epoch": None,
                    },
                )
                assert attachment.status_code == 200
                headers = {
                    **base_headers,
                    "X-Attachment-Epoch": attachment.json()["attachment_epoch"],
                }
                initial = await client.get(path + "initialization", headers=headers)
                assert initial.status_code == 200
                head = publication.cursor.sequence
                if head:
                    await receive_operations(app, headers, after=0, through=head)
                acknowledged = await client.post(
                    path + "ack",
                    headers=headers,
                    json={
                        "cursor": publication.cursor.model_dump(mode="json"),
                    },
                )
                assert acknowledged.status_code == 200
                response = await client.post(
                    path + "choices",
                    headers=headers,
                    json={
                        "actor_uuid": str(actor),
                        "state_revision": publication.state_revision,
                        "correlation_id": str(uuid4()),
                        "force_attack": False,
                    },
                )
                assert response.status_code == 200, response.text
                choices = wire.ChoicesResponse.model_validate_json(
                    response.text
                ).choices
                sunder = next(
                    row
                    for row in rows(choices)
                    if row.behavior_id
                    == "action.class.cleric.divine_intervention.sunder_heretical"
                )
                target = choices.target_sets[sunder.target_set][0]
                result = await completed_receipt(
                    client,
                    host,
                    seat,
                    headers,
                    command(
                        1,
                        actor,
                        publication.state_revision,
                        {
                            "kind": "execute_selection",
                            "discovery_generation": choices.discovery_generation,
                            "selection": {
                                "action_index": sunder.discovery_index,
                                "target_indices": [target.index],
                                "extra_target_positions": [],
                            },
                        },
                    ),
                )
                assert result.kind == "committed"
                delivered = await receive_operations(
                    app, headers, after=head, through=result.cursor.sequence
                )
                intervention = delivered[-1]
                assert intervention.boundary.lifecycle == "outside_encounter"
                assert (
                    intervention.boundary.state_revision == intervention.state_revision
                )
                assert not host.retired
                sheet = next(
                    row for row in intervention.hud.sheets if row.actor_uuid == actor
                )
                assert sheet.permanent_feature_uses == (
                    "class_feature.cleric.divine_intervention",
                )
                await client.post(
                    path + "ack",
                    headers=headers,
                    json={
                        "cursor": result.cursor.model_dump(mode="json"),
                    },
                )

                previous_revision = intervention.state_revision
                preparation = {
                    "kind": "prepare_spells",
                    "selection": {
                        "source_id": "class.cleric.spellcasting",
                        "spell_ids": ["spell.bane"],
                    },
                }
                prepared = await completed_receipt(
                    client,
                    host,
                    seat,
                    headers,
                    command(2, actor, previous_revision, preparation),
                )
                assert prepared.kind == "committed"
                delivered = await receive_operations(
                    app,
                    headers,
                    after=intervention.cursor.sequence,
                    through=prepared.cursor.sequence,
                )
                updated = delivered[-1]
                sheet = next(
                    row for row in updated.hud.sheets if row.actor_uuid == actor
                )
                assert sheet.prepared_spell_selections == (
                    PreparedSpellSelection(
                        "class.cleric.spellcasting", ("spell.bane",)
                    ),
                )
                assert sheet.permanent_feature_uses == (
                    "class_feature.cleric.divine_intervention",
                )
                await client.post(
                    path + "ack",
                    headers=headers,
                    json={
                        "cursor": prepared.cursor.model_dump(mode="json"),
                    },
                )

                stale = await completed_receipt(
                    client,
                    host,
                    seat,
                    headers,
                    command(3, actor, previous_revision, preparation),
                )
                assert stale.kind == "rejected" and stale.reason == "stale_state"
                foreign = await client.post(
                    path + "commands",
                    headers=headers,
                    json=command(4, uuid4(), updated.state_revision, preparation),
                )
                assert (
                    foreign.status_code == 403 and foreign.json()["code"] == "forbidden"
                )
                ended = await completed_receipt(
                    client,
                    host,
                    seat,
                    headers,
                    command(4, actor, updated.state_revision, {"kind": "end_turn"}),
                )
                assert ended.kind == "rejected" and ended.reason == "not_your_turn"
                status = await client.get(path + "status", headers=headers)
                current = wire.StatusResponse.model_validate_json(status.text).status
                assert current.published_cursor == updated.cursor
                assert current.boundary.lifecycle == "outside_encounter"
                assert current.boundary.state_revision == updated.state_revision
        finally:
            await service.shutdown(app.state.player_service)

    asyncio.run(exercise())
