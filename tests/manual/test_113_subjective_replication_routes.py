"""Focused HTTP, SSE, and authority checks for canonical player replication."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Iterator
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from starlette.requests import Request

from dnd.blocks.equipment import Weapon
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.actions_functional import get_available_actions
from dnd.entity import Entity, EntityConfig
from dnd.encounter import Encounter
from dnd.items.environment import DirectionalDoor
from dnd.items.environment_content import directional_door_recipe
from dnd.items.weapons import DAGGER_RECIPE
from dnd.runtime_reset import reset_engine_runtime
from server.api_models import (
    ActionResult,
    AdvanceEncounterResult,
    EquipmentMutationResult,
    EquipRequest,
    ExecuteByIndexRequest,
    GameCreationStartResponse,
    GameCreationEntityAssignment,
    GameCreationSideResult,
    JoinGameRequest,
    ToggleHandlerRequest,
    UnequipRequest,
)
from server.event_server import (
    _action_error_detail,
    _equipment_context,
    app,
    clear_subjective_projection_state,
    get_replication_bootstrap,
    get_replication_combat_log,
    get_replication_frames,
    get_subjective_render_parity_diagnostics,
    join_game,
    sim,
    subscribe_replication,
)
from server.event_stream import event_stream
from server.player_replay_capture import subjective_replay_capture_store
from server.player_replication.journal import (
    SubjectiveJournalPartitionKey,
    SubjectiveSubscriptionClosedError,
    subjective_journal_store,
)
from server.player_replication.runtime import canonical_subjective_replication_runtime
from server.player_replication_contract import SubjectiveReplicationBootstrap
from server.session import PlayerSession, PlayerType
from server.timeline_contracts import CombatLogProjection


@dataclass(frozen=True)
class CanonicalRouteScene:
    observer: Entity
    encounter: Encounter
    session: PlayerSession
    door: DirectionalDoor


def _request(path: str) -> Request:
    """Build one header-free direct standalone request."""
    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
    }, receive=receive)


@pytest.fixture
def canonical_route_scene(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[CanonicalRouteScene]:
    """Install one standalone participant with a renderer-complete perspective."""
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)
    monkeypatch.delenv("DND_HOSTED_GAME_ID", raising=False)
    sim.reset()
    grid = reset_engine_runtime(grid_size=(3, 1))
    event_stream.ensure_attached()
    event_stream._clear_source_journal()
    clear_subjective_projection_state()

    observer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Route observer",
        config=EntityConfig(position=(0, 0), faction="heroes"),
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}
    observer.senses.entities = {}
    observer.senses.objects = {}
    assert grid.get_tile(0, 0) is not None
    hidden_door = materialize_item(
        directional_door_recipe(
            display_name="Route Parity Door",
            blocked_directions=("west",),
            blocked_channels=("movement", "vision"),
        ),
        observer.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalDoor,
    )
    grid.place_object(hidden_door.uuid, (2, 0))

    encounter = Encounter(name="Canonical route encounter", source_entity_uuid=observer.uuid)
    EventQueue.set_combat_log_callback(encounter._on_event_combat_log)
    sim.encounter = encounter
    game = sim.create_game_session(encounter)
    session = sim.get_session_manager().create_session(PlayerType.HUMAN, "Route player")
    game.add_player(session)
    assert game.assign_entity(observer.uuid, session.session_id)

    try:
        yield CanonicalRouteScene(
            observer=observer,
            encounter=encounter,
            session=session,
            door=hidden_door,
        )
    finally:
        sim.reset()
        reset_engine_runtime(grid_size=(3, 1))
        event_stream.ensure_attached()


def _bootstrap(scene: CanonicalRouteScene) -> SubjectiveReplicationBootstrap:
    response = Response()
    bootstrap = asyncio.run(get_replication_bootstrap(
        request=_request("/replication/bootstrap"),
        response=response,
        session_id=str(scene.session.session_id),
    ))
    assert response.headers["cache-control"] == "private, no-store"
    return bootstrap


def _identity(bootstrap: SubjectiveReplicationBootstrap) -> tuple[str, str, str]:
    protocol = bootstrap.protocol
    perspective = bootstrap.perspective
    return (
        protocol.source_stream_id,
        protocol.generation_id,
        perspective.perspective_epoch_id,
    )


def _publish_observed_action(scene: CanonicalRouteScene) -> None:
    entry = CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name=scene.observer.name,
        source_uuid=str(scene.observer.uuid),
        compact="Route observer acts",
        verbose="Route observer acts",
        detailed="Route observer acts",
        perceiver_uuids={str(scene.observer.uuid)},
    )
    with EventQueue.batch_on_event_callbacks():
        declaration = Event(
            event_type=EventType.BASE_ACTION,
            source_entity_uuid=scene.observer.uuid,
            combat_log=entry,
        )
        declaration.phase_to(EventPhase.COMPLETION)


def test_canonical_http_routes_share_one_subjective_partition(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """Bootstrap, reducer frames, and logs expose one exact private identity."""
    bootstrap = _bootstrap(canonical_route_scene)
    source_stream_id, generation_id, perspective_epoch_id = _identity(bootstrap)
    frames_response = Response()
    logs_response = Response()

    frames = asyncio.run(get_replication_frames(
        request=_request("/replication/frames"),
        response=frames_response,
        session_id=str(canonical_route_scene.session.session_id),
        expected_source_stream_id=source_stream_id,
        expected_generation_id=generation_id,
        expected_perspective_epoch_id=perspective_epoch_id,
        from_observation_cursor=0,
        limit=None,
    ))
    logs = asyncio.run(get_replication_combat_log(
        request=_request("/replication/combat-log"),
        response=logs_response,
        session_id=str(canonical_route_scene.session.session_id),
        expected_source_stream_id=source_stream_id,
        expected_generation_id=generation_id,
        expected_perspective_epoch_id=perspective_epoch_id,
        from_combat_log_cursor=0,
        limit=None,
    ))

    observer_uuid = str(canonical_route_scene.observer.uuid)
    payload = bootstrap.model_dump(mode="json")
    assert bootstrap.protocol.source_stream_id == str(canonical_route_scene.encounter.uuid)
    assert bootstrap.world.visibility.root.keys() == {observer_uuid}
    assert set(bootstrap.world.equipment_by_entity) == {observer_uuid}
    assert any(entity.uuid == observer_uuid for entity in bootstrap.world.state.entities)
    assert bootstrap.combat_log_frames.projection is CombatLogProjection.SUBJECTIVE
    assert frames.source_stream_id == logs.source_stream_id == source_stream_id
    assert frames.generation_id == logs.generation_id == generation_id
    assert frames.perspective_epoch_id == logs.perspective_epoch_id == perspective_epoch_id
    assert frames_response.headers["cache-control"] == "private, no-store"
    assert logs_response.headers["cache-control"] == "private, no-store"
    assert "state" not in payload
    assert "visibility" not in payload
    assert "combat_log" not in payload
    assert "session" not in payload


def test_live_subjective_parity_matches_independent_objective_censorship(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """The ADMINISTER diagnostic compares a non-empty edge at one source cursor."""

    bootstrap = _bootstrap(canonical_route_scene)
    response = Response()
    report = asyncio.run(get_subjective_render_parity_diagnostics(
        request=_request("/diagnostics/subjective-parity"),
        response=response,
        session_id=str(canonical_route_scene.session.session_id),
    ))

    assert report.source_stream_id == bootstrap.protocol.source_stream_id
    assert report.generation_id == bootstrap.protocol.generation_id
    assert report.perspective_epoch_id == bootstrap.perspective.perspective_epoch_id
    assert report.source_event_cursor == bootstrap.watermarks.source_event_cursor
    assert report.matches is True
    assert report.mismatches == ()
    assert report.compared_path_count > 1
    assert report.visible_tile_count == 2
    assert report.structural_edge_count >= 1
    assert report.door_edge_count >= 1
    assert report.non_empty_structural_edges is True
    assert response.headers["cache-control"] == "private, no-store"


def test_live_subjective_parity_never_bootstraps_a_missing_player_partition(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """A diagnostic read cannot create the runtime state it is meant to audit."""

    assert canonical_subjective_replication_runtime._contexts == {}
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(get_subjective_render_parity_diagnostics(
            request=_request("/diagnostics/subjective-parity"),
            response=Response(),
            session_id=str(canonical_route_scene.session.session_id),
        ))

    assert rejected.value.status_code == 409
    detail = cast(dict[str, object], rejected.value.detail)
    assert detail["code"] == "subjective_parity_partition_unavailable"
    assert canonical_subjective_replication_runtime._contexts == {}


def test_live_subjective_parity_stays_green_across_door_and_equipment_frames(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """Polling audits successive reducer boundaries rather than one static seed."""

    _bootstrap(canonical_route_scene)

    def poll():
        return asyncio.run(get_subjective_render_parity_diagnostics(
            request=_request("/diagnostics/subjective-parity"),
            response=Response(),
            session_id=str(canonical_route_scene.session.session_id),
        ))

    initial = poll()
    assert initial.matches is True
    assert initial.door_edge_count >= 1

    canonical_route_scene.observer.move((1, 0))
    moved = poll()
    assert moved.matches is True
    assert moved.source_event_cursor > initial.source_event_cursor
    assert moved.observation_cursor > initial.observation_cursor

    canonical_route_scene.door.open()
    opened = poll()
    assert opened.matches is True
    assert opened.source_event_cursor > moved.source_event_cursor
    assert opened.observation_cursor > moved.observation_cursor

    dagger = materialize_item(
        DAGGER_RECIPE,
        canonical_route_scene.observer.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert canonical_route_scene.observer.loot_item(dagger)
    assert canonical_route_scene.observer.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
    equipped = poll()
    assert equipped.matches is True
    assert equipped.source_event_cursor > opened.source_event_cursor
    assert equipped.observation_cursor > opened.observation_cursor
    assert equipped.expected_digest != opened.expected_digest


def _parse_sse(frame: str) -> tuple[str, dict[str, object]]:
    event = next(
        line.removeprefix("event: ")
        for line in frame.splitlines()
        if line.startswith("event: ")
    )
    data = "\n".join(
        line.removeprefix("data: ")
        for line in frame.splitlines()
        if line.startswith("data: ")
    )
    return event, json.loads(data)


def test_canonical_sse_emits_only_typed_safe_delivery_envelopes(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """Catch-up and live delivery never expose raw events or legacy side channels."""
    bootstrap = _bootstrap(canonical_route_scene)
    source_stream_id, generation_id, perspective_epoch_id = _identity(bootstrap)
    _publish_observed_action(canonical_route_scene)

    async def collect_initial() -> tuple[Response, list[str]]:
        response = await subscribe_replication(
            request=_request("/replication/subscribe"),
            session_id=str(canonical_route_scene.session.session_id),
            expected_source_stream_id=source_stream_id,
            expected_generation_id=generation_id,
            expected_perspective_epoch_id=perspective_epoch_id,
            from_observation_cursor=0,
            from_combat_log_cursor=0,
        )
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        frames: list[str] = []
        try:
            for _ in range(3):
                frames.append(await anext(iterator))
        finally:
            await iterator.aclose()
        return response, frames

    response, raw_frames = asyncio.run(collect_initial())
    parsed = [_parse_sse(frame) for frame in raw_frames]

    assert response.headers["cache-control"] == "private, no-store"
    assert [event for event, _payload in parsed] == [
        "sync",
        "frame",
        "combat_log",
    ]
    assert [payload["kind"] for _event, payload in parsed] == [
        "sync",
        "frame",
        "combat_log",
    ]
    assert "event" not in cast(dict[str, object], parsed[1][1]["frame"])
    assert cast(dict[str, object], parsed[2][1]["frame"])["projection"] == "subjective"
    serialized = "\n".join(raw_frames)
    for forbidden_event in (
        "event: game_event",
        "event: session",
        "event: heartbeat",
        "event: evicted",
    ):
        assert forbidden_event not in serialized


def test_sse_backfill_barrier_does_not_duplicate_interleaved_live_delivery(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """A post-subscribe append queues strictly after the bounded backfill barrier."""
    bootstrap = _bootstrap(canonical_route_scene)
    source_stream_id, generation_id, perspective_epoch_id = _identity(bootstrap)
    _publish_observed_action(canonical_route_scene)

    async def subscribe_then_interleave() -> list[tuple[str, dict[str, object]]]:
        response = await subscribe_replication(
            request=_request("/replication/subscribe"),
            session_id=str(canonical_route_scene.session.session_id),
            expected_source_stream_id=source_stream_id,
            expected_generation_id=generation_id,
            expected_perspective_epoch_id=perspective_epoch_id,
            from_observation_cursor=0,
            from_combat_log_cursor=0,
        )
        _publish_observed_action(canonical_route_scene)
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        frames: list[str] = []
        try:
            for _ in range(5):
                frames.append(await anext(iterator))
        finally:
            await iterator.aclose()
        return [_parse_sse(frame) for frame in frames]

    parsed = asyncio.run(subscribe_then_interleave())

    assert [event for event, _payload in parsed] == [
        "sync",
        "frame",
        "combat_log",
        "frame",
        "combat_log",
    ]
    sync_watermarks = cast(dict[str, object], parsed[0][1]["watermarks"])
    assert sync_watermarks["observation_cursor"] == 1
    assert sync_watermarks["combat_log_cursor"] == 1
    observation_cursors = [
        cast(
            dict[str, object],
            cast(dict[str, object], payload["frame"])["watermarks"],
        )["observation_cursor"]
        for event, payload in parsed
        if event == "frame"
    ]
    combat_log_cursors = [
        cast(dict[str, object], payload["frame"])["combat_log_cursor"]
        for event, payload in parsed
        if event == "combat_log"
    ]
    assert observation_cursors == [1, 2]
    assert combat_log_cursors == [1, 2]


def test_sse_reconnect_backfill_preserves_original_cross_channel_order(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """Multiple missed actions replay with each log's causal commit watermark."""

    bootstrap = _bootstrap(canonical_route_scene)
    source_stream_id, generation_id, perspective_epoch_id = _identity(bootstrap)
    _publish_observed_action(canonical_route_scene)
    _publish_observed_action(canonical_route_scene)

    async def collect_backfill() -> list[tuple[str, dict[str, object]]]:
        response = await subscribe_replication(
            request=_request("/replication/subscribe"),
            session_id=str(canonical_route_scene.session.session_id),
            expected_source_stream_id=source_stream_id,
            expected_generation_id=generation_id,
            expected_perspective_epoch_id=perspective_epoch_id,
            from_observation_cursor=0,
            from_combat_log_cursor=0,
        )
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        frames: list[str] = []
        try:
            for _ in range(5):
                frames.append(await anext(iterator))
        finally:
            await iterator.aclose()
        return [_parse_sse(frame) for frame in frames]

    parsed = asyncio.run(collect_backfill())

    assert [event for event, _payload in parsed] == [
        "sync",
        "frame",
        "combat_log",
        "frame",
        "combat_log",
    ]
    delivery_watermarks = [
        cast(
            dict[str, object],
            cast(dict[str, object], payload["frame"])["watermarks"],
        )
        if event == "frame"
        else cast(dict[str, object], payload["watermarks"])
        for event, payload in parsed[1:]
    ]
    assert [
        (
            watermark["observation_cursor"],
            watermark["combat_log_cursor"],
        )
        for watermark in delivery_watermarks
    ] == [(1, 0), (1, 1), (2, 1), (2, 2)]


def test_recovery_routes_require_all_three_optimistic_identities() -> None:
    """Only bootstrap may bind without a caller-supplied partition identity."""

    async def request_missing_identities() -> list[int]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            responses = [
                await client.get("/replication/frames", params={"session_id": str(uuid4())}),
                await client.get("/replication/combat-log", params={"session_id": str(uuid4())}),
                await client.get("/replication/subscribe", params={"session_id": str(uuid4())}),
            ]
        return [response.status_code for response in responses]

    assert asyncio.run(request_missing_identities()) == [422, 422, 422]


def test_identity_mismatch_and_generation_reset_fail_closed(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """Recovery never silently rebinds stale generation or perspective values."""
    bootstrap = _bootstrap(canonical_route_scene)
    source_stream_id, generation_id, perspective_epoch_id = _identity(bootstrap)

    with pytest.raises(HTTPException) as mismatch:
        asyncio.run(get_replication_frames(
            request=_request("/replication/frames"),
            response=Response(),
            session_id=str(canonical_route_scene.session.session_id),
            expected_source_stream_id=source_stream_id,
            expected_generation_id="stale-generation",
            expected_perspective_epoch_id=perspective_epoch_id,
            from_observation_cursor=0,
            limit=None,
        ))
    assert mismatch.value.status_code == 409
    mismatch_detail = cast(dict[str, object], mismatch.value.detail)
    assert mismatch_detail["code"] == "replication_identity_changed"

    EventQueue.reset()
    EventQueue.set_combat_log_callback(canonical_route_scene.encounter._on_event_combat_log)
    with pytest.raises(HTTPException) as reset_mismatch:
        asyncio.run(get_replication_combat_log(
            request=_request("/replication/combat-log"),
            response=Response(),
            session_id=str(canonical_route_scene.session.session_id),
            expected_source_stream_id=source_stream_id,
            expected_generation_id=generation_id,
            expected_perspective_epoch_id=perspective_epoch_id,
            from_combat_log_cursor=0,
            limit=None,
        ))
    assert reset_mismatch.value.status_code == 409
    reset_detail = cast(dict[str, object], reset_mismatch.value.detail)
    assert reset_detail["code"] == "replication_identity_changed"


def test_projection_reset_clears_replay_capture_and_releases_journal_identity(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """One teardown seam closes streams and discards all process-local identity state."""
    bootstrap = _bootstrap(canonical_route_scene)
    source_stream_id, generation_id, perspective_epoch_id = _identity(bootstrap)
    key = SubjectiveJournalPartitionKey(
        source_stream_id=source_stream_id,
        generation_id=generation_id,
        perspective_epoch_id=perspective_epoch_id,
    )
    context = canonical_subjective_replication_runtime.get(key)
    subscription = context.subscribe()
    asyncio.run(subscription.get())
    membership_id = f"standalone:{canonical_route_scene.session.session_id}"
    assert subjective_replay_capture_store.memberships(
        encounter_uuid=source_stream_id,
    ) == (membership_id,)

    clear_subjective_projection_state()

    assert subjective_replay_capture_store.memberships(
        encounter_uuid=source_stream_id,
    ) == ()
    with pytest.raises(SubjectiveSubscriptionClosedError):
        asyncio.run(subscription.get())
    reopened = subjective_journal_store.open(
        protocol=bootstrap.protocol,
        perspective=bootstrap.perspective,
        initial_source_event_cursor=bootstrap.watermarks.source_event_cursor,
    )
    assert reopened.partition_key == key
    clear_subjective_projection_state()


def test_authority_mutation_immediately_closes_existing_partition(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """A control-set change retires an already-open stream before a later bind."""
    bootstrap = _bootstrap(canonical_route_scene)
    source_stream_id, generation_id, perspective_epoch_id = _identity(bootstrap)
    key = SubjectiveJournalPartitionKey(
        source_stream_id=source_stream_id,
        generation_id=generation_id,
        perspective_epoch_id=perspective_epoch_id,
    )
    context = canonical_subjective_replication_runtime.get(key)
    subscription = context.subscribe()
    asyncio.run(subscription.get())

    second = Entity.create(
        source_entity_uuid=uuid4(),
        name="Second controlled actor",
        config=EntityConfig(position=(1, 0), faction="heroes"),
    )
    second.senses.visible = {(0, 0): True, (1, 0): True}
    second.senses.seen = {(0, 0), (1, 0)}
    response = asyncio.run(join_game(JoinGameRequest(
        session_id=str(canonical_route_scene.session.session_id),
        entity_uuids=[str(second.uuid)],
    )))

    assert response.success is True
    assert context.healthy is False
    with pytest.raises(SubjectiveSubscriptionClosedError):
        asyncio.run(subscription.get())

    rotated = _bootstrap(canonical_route_scene)
    assert rotated.perspective.perspective_epoch_id != perspective_epoch_id
    assert set(rotated.perspective.controlled_entity_uuids) == {
        str(canonical_route_scene.observer.uuid),
        str(second.uuid),
    }


def test_hosted_worker_rejects_missing_private_authority(
    canonical_route_scene: CanonicalRouteScene,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A worker never treats a query-string session as subjective authority."""
    monkeypatch.setenv("DND_GAME_WORKER", "1")
    monkeypatch.setenv("DND_HOSTED_GAME_ID", str(uuid4()))

    with pytest.raises(HTTPException) as rejected:
        asyncio.run(get_replication_bootstrap(
            request=_request("/replication/bootstrap"),
            response=Response(),
            session_id=str(canonical_route_scene.session.session_id),
        ))
    assert rejected.value.status_code == 403
    rejected_detail = cast(dict[str, object], rejected.value.detail)
    assert rejected_detail["code"] == "replication_authority_rejected"


def test_openapi_has_exactly_one_player_replication_route_family() -> None:
    """No V2 alias or raw player event/history surface survives the hard cut."""
    paths = app.openapi()["paths"]
    canonical = {
        "/replication/bootstrap",
        "/replication/frames",
        "/replication/combat-log",
        "/replication/subscribe",
    }
    assert canonical <= set(paths)
    assert {path for path in paths if path.startswith("/replication/")} == canonical
    for forbidden in (
        "/replication/v2/bootstrap",
        "/replication/v2/combat-log",
        "/replication/v2/events/history",
        "/replication/v2/events/subscribe",
        "/events",
        "/events/history",
        "/events/subscribe",
        "/combat-log",
        "/state",
        "/visibility",
        "/entities",
        "/entity/{entity_uuid}",
        "/entity/{entity_uuid}/equipment",
        "/entity/{entity_uuid}/equipment/item/{item_uuid}",
        "/grid",
        "/tile/{x}/{y}",
        "/encounter",
        "/encounter/current-turn",
        "/simulation/status",
        "/session/{session_id}/entities",
        "/event-types",
        "/pvp/status",
        "/action/self",
        "/action/entity",
        "/action/position",
    ):
        assert forbidden not in paths
    assert all(getattr(route, "path", None) != "/ws" for route in app.routes)

    for path in (
        "/entity/{entity_uuid}/available-actions",
        "/entity/{entity_uuid}/equippable-items",
        "/entity/{entity_uuid}/handlers",
    ):
        parameters = {
            parameter["name"]: parameter
            for parameter in paths[path]["get"]["parameters"]
        }
        assert parameters["session_id"]["required"] is True

    bootstrap_parameters = {
        parameter["name"]: parameter
        for parameter in paths["/replication/bootstrap"]["get"]["parameters"]
    }
    assert bootstrap_parameters["session_id"]["required"] is True
    for path in canonical - {"/replication/bootstrap"}:
        parameters = {
            parameter["name"]: parameter
            for parameter in paths[path]["get"]["parameters"]
        }
        assert parameters["session_id"]["required"] is True
        for identity_name in (
            "expected_source_stream_id",
            "expected_generation_id",
            "expected_perspective_epoch_id",
        ):
            assert parameters[identity_name]["required"] is True


def test_command_ack_models_do_not_duplicate_replica_or_diagnostics_facts() -> None:
    """Commands acknowledge outcomes; state, events, and logs use canonical journals."""
    assert "include_state" not in ExecuteByIndexRequest.model_fields
    assert set(ActionResult.model_fields) == {
        "success",
        "message",
        "event_type",
        "outcome_code",
        "turn_continues",
        "encounter_ended",
        "available_actions",
        "server_timing",
        "event_cursor_after",
        "combat_log_cursor_after",
    }
    assert "ai_actions" not in AdvanceEncounterResult.model_fields
    assert "ai_actions" not in GameCreationStartResponse.model_fields
    assert set(EquipmentMutationResult.model_fields) == {
        "success",
        "message",
        "event_cursor_after",
        "combat_log_cursor_after",
    }
    assert set(EquipRequest.model_fields) == {"session_id", "item_uuid", "slot"}
    assert set(UnequipRequest.model_fields) == {"session_id", "slot"}
    assert set(ToggleHandlerRequest.model_fields) == {"session_id", "enabled"}
    assert "entities" not in GameCreationSideResult.model_fields
    assert "human_entity_uuids" not in GameCreationSideResult.model_fields
    assert "entity_assignments" in GameCreationSideResult.model_fields
    assert set(GameCreationEntityAssignment.model_fields) == {
        "entity_uuid",
        "entity_name",
        "faction",
    }


def test_action_errors_do_not_embed_objective_state_or_replica_rows(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """Rejected commands expose correction metadata, never world snapshots."""
    detail = _action_error_detail(
        entity=canonical_route_scene.observer,
        available=get_available_actions(canonical_route_scene.observer),
        code="invalid_action_target",
        message="Target is no longer valid",
    )
    assert {
        "known_entities",
        "action_economy",
        "available_actions",
        "state",
        "visibility",
        "combat_log_entries",
    }.isdisjoint(detail)


def test_equipment_error_context_is_control_metadata_only(
    canonical_route_scene: CanonicalRouteScene,
) -> None:
    """Equipment rejection details never carry inventory or loadout snapshots."""
    context = _equipment_context(canonical_route_scene.observer)
    assert set(context) == {"entity_uuid", "entity_name", "valid_slots"}
