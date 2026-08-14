"""Focused API checks for composed games and participant assignment."""

import asyncio
from collections.abc import Iterator
from uuid import UUID

import pytest

from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS,
    AUTHORED_ENCOUNTER_RECIPES,
    AUTHORED_ROSTER_RECIPES,
)
from dnd.scenarios.battlefield_catalog import BATTLEFIELDS
from server import event_server
from server.event_stream import event_stream
from tests.manual.live_replication_support import drain_subscription
from tests.manual.game_creation_test_support import (
    authored_compose_request,
    compose_and_preview,
    roster_result,
    start_composed_game,
)
from tests.manual.server_test_client import (
    ServerTestClient,
    reset_server_test_runtime,
)


@pytest.fixture(autouse=True)
def clean_game_creation_runtime() -> Iterator[None]:
    """Isolate global engine, controller, and session state per test."""
    reset_server_test_runtime()
    yield
    reset_server_test_runtime()


@pytest.fixture
def client() -> Iterator[ServerTestClient]:
    """Provide one persistent in-process API client per test."""
    with ServerTestClient() as api_client:
        yield api_client


def _controller_types(assignment_rows: list[dict[str, object]]) -> set[str]:
    """Resolve encounter controller kinds for control-plane assignment rows."""
    encounter = event_server.sim.encounter
    assert encounter is not None
    result = set()
    for row in assignment_rows:
        entity = Entity.get(UUID(str(row["entity_uuid"])))
        assert entity is not None
        controller = encounter.get_controller_for(entity.uuid)
        assert controller is not None
        result.add(controller.controller_type)
    return result


def test_catalog_is_a_lossless_projection_of_canonical_content(
    client: ServerTestClient,
) -> None:
    """The setup UI receives every canonical composition and historical recipe."""
    response = client.get("/game-creation/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == 4
    assert "controllers" not in payload
    assert "ai_policies" not in payload
    assert payload["roster_recipes"] == [
        recipe.model_dump(mode="json")
        for recipe in AUTHORED_ROSTER_RECIPES
    ]
    assert payload["encounter_recipes"] == [
        recipe.model_dump(mode="json")
        for recipe in AUTHORED_ENCOUNTER_RECIPES
    ]
    assert [row["battlefield_id"] for row in payload["battlefields"]] == [
        spec.battlefield_id for spec in BATTLEFIELDS
    ]
    assert all(row["preview"] is not None for row in payload["battlefields"])
    closed = next(
        row
        for row in payload["battlefields"]
        if row["battlefield_id"] == "battlefield.standard_hazards_closed"
    )
    assert any(
        obj["kind"] == "door" and obj["position"] == [7, 7] and obj["is_open"] is False
        for obj in closed["preview"]["objects"]
    )
    assert payload["deployments"] == [
        deployment.model_dump(mode="json")
        for deployment in AUTHORED_DEPLOYMENTS
    ]


def test_openapi_has_one_game_creation_path_and_no_automation_routes(
    client: ServerTestClient,
) -> None:
    """Deleted managed-service and scenario-start aliases cannot return."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert {
        "/game-creation/catalog",
        "/game-creation/compose",
        "/game-creation/preview",
        "/game-creation/start",
        "/game-creation/activate",
    }.issubset(paths)
    assert "/game-creation/preflight" not in paths
    assert not any(
        path.startswith("/game-creation/preview/configurations/")
        for path in paths
    )
    assert not any(path.startswith("/ai/") for path in paths)
    assert not {
        "/simulation/start-human",
        "/simulation/start-ai-validation",
        "/simulation/start-codex-monsters",
        "/simulation/start-aoe-test",
        "/simulation/start-pvp",
        "/simulation/start",
        "/simulation/reset",
    }.intersection(paths)


def test_compose_rejects_an_explicit_empty_owned_character_roster(
    client: ServerTestClient,
) -> None:
    """The authoritative route never normalizes an empty owned party."""
    assert event_server.sim.encounter is None
    assert event_server.sim.game is None
    request = authored_compose_request()
    roster_slots = request["roster_slots"]
    assert isinstance(roster_slots, list)
    first_slot = roster_slots[0]
    assert isinstance(first_slot, dict)
    first_slot["roster"] = {
        "kind": "owned_characters",
        "title": "Empty owned party",
        "character_ids": [],
    }

    response = client.post("/game-creation/compose", json=request)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "character_ids"
    assert event_server.sim.encounter is None
    assert event_server.sim.game is None


def test_compose_and_preview_are_pure_and_preserve_the_live_game(
    client: ServerTestClient,
) -> None:
    """Cold normalization and preview never replace the prepared encounter."""
    _composition, _started = start_composed_game(client)
    encounter = event_server.sim.encounter
    game = event_server.sim.game
    entities_before = tuple(entity.uuid for entity in Entity.get_all_entities())

    composition = compose_and_preview(
        client,
        encounter_id="encounter.goblin_water_skirmish",
    )

    assert composition["compatibility"]["admitted"] is True
    assert event_server.sim.encounter is encounter
    assert event_server.sim.game is game
    assert tuple(entity.uuid for entity in Entity.get_all_entities()) == entities_before


def test_prepared_start_wires_exact_rosters_and_join_authority(
    client: ServerTestClient,
) -> None:
    """Preparation is passive until a human claims one exact roster."""
    composition, payload = start_composed_game(client)
    player_roster = roster_result(payload, "roster_1")
    opposition_roster = roster_result(payload, "roster_2")
    player_assignments = player_roster["entity_assignments"]
    opposition_assignments = opposition_roster["entity_assignments"]
    human_entity_uuids = [row["entity_uuid"] for row in player_assignments]
    assert payload["status"] == "prepared"
    assert _controller_types(player_assignments) == {"pass"}
    assert _controller_types(opposition_assignments) == {"pass"}
    retired_assignment_fields = {
        "controller",
        "policy_id",
        "policy_execution",
        "provider_id",
        "codex_session_id",
        "takeover_claim_id",
    }
    assert all(
        retired_assignment_fields.isdisjoint(assignment)
        for assignment in player_assignments + opposition_assignments
    )
    assert event_server.sim.get_session_manager().sessions == {}
    objective_entities = client.get("/diagnostics/objective/bootstrap").json()["world"]["state"]["entities"]
    objective_by_uuid = {row["uuid"]: row for row in objective_entities}
    preview_members = {
        member["member_id"]: member["entity"]
        for roster in composition["preview"]["rosters"]
        for member in roster["members"]
    }
    for assignment in player_assignments + opposition_assignments:
        objective = objective_by_uuid[assignment["entity_uuid"]]
        preview = preview_members[assignment["member_id"]]
        assert objective["content_ref"] == preview["content_ref"]
        assert objective["appearance"] == preview["appearance"]

    session = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Local Player"},
    )
    join = client.post(
        "/game/join",
        json={
            "session_id": session.json()["session_id"],
            "entity_uuids": human_entity_uuids,
        },
    )
    assert session.status_code == 200
    assert join.status_code == 200
    assert join.json()["controlled_entities"] == human_entity_uuids
    assert _controller_types(player_assignments) == {"human"}
    assert _controller_types(opposition_assignments) == {"pass"}


def test_live_stream_preserves_cursor_order_during_recursive_movement(
    client: ServerTestClient,
) -> None:
    """Movement and its sensory children reach clients in storage order."""
    _composition, payload = start_composed_game(client)
    hero_uuid = roster_result(
        payload,
        "roster_1",
    )["entity_assignments"][0]["entity_uuid"]

    session = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Movement Stream Test"},
    )
    session_id = session.json()["session_id"]
    joined = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [hero_uuid]},
    )
    assert joined.status_code == 200
    bootstrap_response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert bootstrap_response.status_code == 200
    bootstrap = bootstrap_response.json()
    activation = client.post(
        "/game-creation/activate",
        json={
            "session_id": session_id,
            "expected_source_stream_id": bootstrap["protocol"][
                "source_stream_id"
            ],
            "expected_generation_id": bootstrap["protocol"]["generation_id"],
            "expected_perspective_epoch_id": bootstrap["perspective"][
                "perspective_epoch_id"
            ],
        },
    )
    assert activation.status_code == 200

    available = client.get(
        f"/entity/{hero_uuid}/available-actions",
        params={"session_id": session_id},
    ).json()
    move = next(
        row for row in available["position_actions"]
        if row["template_name"] == "Move"
    )
    target = move["valid_targets"][0]

    event_stream.ensure_attached()
    event_cursor_before = EventQueue.event_cursor()
    subscription = event_stream.subscribe(max_depth=256)
    try:
        result = client.post(
            "/action/execute",
            json={
                "session_id": session_id,
                "entity_uuid": hero_uuid,
                "template_name": "Move",
                "target_index": target["index"],
                "return_available_actions": False,
            },
        )
        assert result.status_code == 200
        envelopes = asyncio.run(drain_subscription(subscription, limit=256))
    finally:
        event_stream.unsubscribe(subscription)

    live_cursors = [
        envelope["data"].event_cursor
        for envelope in envelopes
        if envelope["event"] == "game_event"
    ]
    assert live_cursors == list(
        range(event_cursor_before + 1, EventQueue.event_cursor() + 1)
    )


def test_observer_join_has_no_entity_authority(
    client: ServerTestClient,
) -> None:
    """Spectator identity can join the game but can never claim a combatant."""
    _composition, payload = start_composed_game(client)
    entity_uuid = roster_result(
        payload,
        "roster_1",
    )["entity_assignments"][0]["entity_uuid"]
    session = client.post(
        "/session/create",
        json={"player_type": "observer", "name": "Match Observer"},
    )
    assert session.status_code == 200

    joined = client.post(
        "/game/join",
        json={
            "session_id": session.json()["session_id"],
            "observer_entity_uuids": [entity_uuid],
            "active_observer_uuid": entity_uuid,
        },
    )
    rejected = client.post(
        "/game/join",
        json={
            "session_id": session.json()["session_id"],
            "entity_uuids": [entity_uuid],
        },
    )

    assert joined.status_code == 200
    assert joined.json()["success"] is True
    assert joined.json()["controlled_entities"] == []
    assert joined.json()["observer_entities"] == [entity_uuid]
    assert joined.json()["active_observer_uuid"] == entity_uuid
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["code"] == "observer_cannot_control_entities"
