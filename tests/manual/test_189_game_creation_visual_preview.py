"""Isolated production-renderer previews for canonical side configurations."""

from collections.abc import Iterator

import pytest

from dnd.core.base_object import BaseObject
from dnd.core.events.events_registry import (
    EventQueue,
)
from dnd.entity import Entity
from server import event_server
from tests.manual.server_test_client import (
    ServerTestClient,
    reset_server_test_runtime,
)
from server.game_creation_preview import (
    clear_game_creation_preview_cache,
    game_creation_preview_worker_pid,
)
from tests.manual.game_creation_test_support import (
    authored_compose_request,
    compose_and_preview,
    start_composed_game,
)


@pytest.fixture(autouse=True)
def clean_runtime() -> Iterator[None]:
    """Keep preview isolation assertions independent from other manual tests."""
    reset_server_test_runtime()
    yield
    reset_server_test_runtime()


@pytest.fixture
def client() -> Iterator[ServerTestClient]:
    """Expose the standalone ASGI surface without opening a socket."""
    with ServerTestClient() as api_client:
        yield api_client


def _start_live_game(client: ServerTestClient) -> None:
    start_composed_game(client)


def test_encounter_preview_is_exact_and_parent_runtime_is_untouched(
    client: ServerTestClient,
) -> None:
    """An exact recipe preview uses production DTOs without replacing runtime."""
    _start_live_game(client)
    encounter_before = event_server.sim.encounter
    game_before = event_server.sim.game
    entity_uuids_before = tuple(entity.uuid for entity in Entity.get_all_entities())
    base_objects_before = {
        object_uuid: id(value)
        for object_uuid, value in BaseObject._registry.items()
    }
    event_handlers_before = {
        handler_uuid: id(value)
        for handler_uuid, value in EventQueue._event_handlers.items()
    }

    composition = compose_and_preview(
        client,
        encounter_id="encounter.goblin_water_skirmish",
    )
    response_payload = composition["preview"]
    cached_response = client.post(
        "/game-creation/preview",
        json=composition["exact_start_request"],
    )

    assert cached_response.status_code == 200
    assert cached_response.json() == response_payload
    payload = response_payload
    assert payload["schema_version"] == 2
    assert len(payload["content_set_digest"]) == 64
    assert (
        payload["encounter_recipe_digest"]
        == composition["recipe"]["recipe_digest"]
    )
    monster_roster = next(
        roster
        for roster in payload["rosters"]
        if roster["roster_id"] == "monsters.goblin_water_cell"
    )
    assert len(monster_roster["members"]) == 3
    assert [
        row["member_id"] for row in monster_roster["members"]
    ] == [
        "monster_1",
        "monster_2",
        "monster_3",
    ]
    assert all(
        row["entity"]["uuid"] == row["visual_loadout"]["entity_uuid"]
        for row in monster_roster["members"]
    )
    assert all(
        row["entity"]["content_ref"]
        for row in monster_roster["members"]
    )
    caster = monster_roster["members"][2]
    assert caster["entity"]["content_ref"]["content_id"] == "creature.goblin_caster"
    assert {
        layer["slot"]
        for layer in caster["visual_loadout"]["layers"]
    } >= {"body_armor", "boots"}

    assert event_server.sim.encounter is encounter_before
    assert event_server.sim.game is game_before
    assert tuple(entity.uuid for entity in Entity.get_all_entities()) == entity_uuids_before
    assert {
        object_uuid: id(value)
        for object_uuid, value in BaseObject._registry.items()
    } == base_objects_before
    assert {
        handler_uuid: id(value)
        for handler_uuid, value in EventQueue._event_handlers.items()
    } == event_handlers_before


def test_distinct_previews_reuse_the_lifespan_owned_isolated_worker(
    client: ServerTestClient,
) -> None:
    clear_game_creation_preview_cache()

    first = compose_and_preview(
        client,
        encounter_id="encounter.goblin_water_skirmish",
    )
    worker_pid = game_creation_preview_worker_pid()
    second = compose_and_preview(
        client,
        encounter_id="encounter.standard_skeleton_doors",
    )

    assert worker_pid is not None
    assert game_creation_preview_worker_pid() == worker_pid
    assert (
        first["recipe"]["recipe_digest"]
        != second["recipe"]["recipe_digest"]
    )


def test_composition_has_exact_unknown_roster_error(
    client: ServerTestClient,
) -> None:
    request = authored_compose_request()
    roster_slots = request["roster_slots"]
    assert isinstance(roster_slots, list)
    opposition = roster_slots[1]
    assert isinstance(opposition, dict)
    opposition["roster"] = {
        "kind": "authored_roster",
        "roster_id": "monster.not_registered",
    }
    response = client.post(
        "/game-creation/compose",
        json=request,
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "code": "game_creation_composition_invalid",
            "message": (
                "unknown authored roster 'monster.not_registered'"
            ),
        },
    }
