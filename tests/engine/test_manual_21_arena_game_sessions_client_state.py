"""Focused checks for arena game sessions and client state."""

import warnings
from uuid import UUID

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient
import pytest

from dnd.conditions import Dashing
from dnd.core.base_block import BaseBlock
from dnd.core.content.registration import get_content_declaration
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.encounter import EncounterState, TurnState
from dnd.entity import Entity
from tests.manual.server_test_client import reset_server_test_runtime
from server.event_server import (
    app,
    sim,
)


STANDARD_ROSTER_SLOTS: list[dict[str, object]] = [
    {
        "roster_slot_id": "players",
        "roster": {
            "kind": "authored_roster",
            "roster_id": "hero.fighter_l5_archer_torch",
        },
        "faction_id": "heroes",
        "deployment_zone_id": "zone_1",
        "controller_defaults": {
            "controller": "human",
            "participant_name": "Tutorial Player",
            "policy_id": None,
            "member_overrides": [],
        },
    },
    {
        "roster_slot_id": "opposition",
        "roster": {
            "kind": "authored_roster",
            "roster_id": "monsters.skeleton_trio",
        },
        "faction_id": "monsters",
        "deployment_zone_id": "zone_2",
        "controller_defaults": {
            "controller": "ai",
            "participant_name": "Native AI",
            "policy_id": "builtin.basic",
            "member_overrides": [],
        },
    },
]

STANDARD_SCENARIO: dict[str, object] = {
    "title": "Tutorial Standard Arena",
    "roster_slots": STANDARD_ROSTER_SLOTS,
    "battlefield_id": "battlefield.standard_hazards_closed",
    "deployment_id": "neutral.battlefield.standard_hazards_closed",
    "opening_policy": {
        "kind": "fixed_roster",
        "roster_slot_id": "players",
    },
}

AOE_SCENARIO: dict[str, object] = {
    **STANDARD_SCENARIO,
    "title": "Tutorial Area-Effect Arena",
    "roster_slots": [
        {
            **STANDARD_ROSTER_SLOTS[0],
            "roster": {
                "kind": "authored_roster",
                "roster_id": "hero.sorcerer_l5_standard_torch",
            },
        },
        {
            **STANDARD_ROSTER_SLOTS[1],
            "roster": {
                "kind": "authored_roster",
                "roster_id": "monsters.goblin_water_cell",
            },
        },
    ],
    "battlefield_id": "battlefield.open_floor_bright",
    "deployment_id": "neutral.battlefield.open_floor_bright",
}


@pytest.fixture(autouse=True)
def isolate_live_game_tutorial_state():
    """Close native assignments and isolate global state around each check."""
    reset_live_game_tutorial_state()
    yield
    reset_live_game_tutorial_state()


def reset_live_game_tutorial_state() -> None:
    """Clear global state used by arena-game tutorial examples."""
    reset_server_test_runtime()


def prepare_canonical_game(
    client: TestClient,
    scenario: dict[str, object],
) -> dict:
    """Compose once, then start only the returned normalized recipe."""
    compose_response = client.post(
        "/game-creation/compose",
        json=scenario,
    )
    assert compose_response.status_code == 200, compose_response.text
    composition = compose_response.json()
    response = client.post(
        "/game-creation/start",
        json={
            "expected_content_set_digest": composition[
                "content_set_digest"
            ],
            "expected_ruleset_digest": composition["ruleset_digest"],
            "recipe": composition["recipe"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "prepared"
    assert (
        payload["recipe_digest"]
        == composition["recipe"]["recipe_digest"]
    )
    return payload


def roster_assignments(
    creation: dict,
    roster_slot_id: str,
) -> list[dict]:
    """Return assignments from one exact roster result."""
    return next(
        roster["entity_assignments"]
        for roster in creation["rosters"]
        if roster["roster_slot_id"] == roster_slot_id
    )


def arena_floor_object_names() -> list[str]:
    """Return names of blocks registered as floor objects in the arena grid."""
    grid = get_map()
    return [
        block.name
        for block in BaseBlock._registry.values()
        if block.name is not None and grid.get_object_position(block.uuid) is not None
    ]


def player_replication_seed(client: TestClient, session_id: str) -> dict:
    """Open the sole expectation-free player replication entry point."""
    response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert response.status_code == 200
    return response.json()


def player_replication_after(
    client: TestClient,
    session_id: str,
    bootstrap: dict,
) -> tuple[dict, dict, dict]:
    """Read exact reducer and combat-log windows after one player seed."""
    identity = {
        "session_id": session_id,
        "expected_source_stream_id": bootstrap["protocol"]["source_stream_id"],
        "expected_generation_id": bootstrap["protocol"]["generation_id"],
        "expected_perspective_epoch_id": bootstrap["perspective"]["perspective_epoch_id"],
    }
    frames_response = client.get(
        "/replication/frames",
        params={
            **identity,
            "from_observation_cursor": bootstrap["watermarks"]["observation_cursor"],
        },
    )
    logs_response = client.get(
        "/replication/combat-log",
        params={
            **identity,
            "from_combat_log_cursor": bootstrap["watermarks"]["combat_log_cursor"],
        },
    )
    current_response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert frames_response.status_code == 200
    assert logs_response.status_code == 200
    assert current_response.status_code == 200
    return current_response.json(), frames_response.json(), logs_response.json()


def action_template_names(entity: Entity) -> set[str]:
    """Return registered action-template names for an entity."""
    return {action.name for action in entity.registered_actions if action.name is not None}


def equipped_item_name(entity: Entity, slot: WeaponSlot) -> str:
    """Return the name of an item equipped in a weapon slot."""
    item = entity.equipment.get_item_by_slot(slot)
    assert item is not None
    assert item.name is not None
    return item.name


def start_joined_human_arena(
    scenario: dict[str, object] = STANDARD_SCENARIO,
) -> tuple[TestClient, str, str]:
    """Prepare, join, bootstrap, and activate one canonical human game."""
    reset_live_game_tutorial_state()
    client = TestClient(app)
    start_payload = prepare_canonical_game(client, scenario)
    hero_uuid = roster_assignments(
        start_payload,
        "players",
    )[0]["entity_uuid"]

    session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Tutorial Player"},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [hero_uuid]},
    )
    assert join_response.status_code == 200
    assert join_response.json()["controlled_entities"] == [hero_uuid]

    bootstrap = player_replication_seed(client, session_id)
    activation_response = client.post(
        "/game-creation/activate",
        json={
            "session_id": session_id,
            "expected_source_stream_id": bootstrap["protocol"]["source_stream_id"],
            "expected_generation_id": bootstrap["protocol"]["generation_id"],
            "expected_perspective_epoch_id": bootstrap["perspective"][
                "perspective_epoch_id"
            ],
        },
    )
    assert activation_response.status_code == 200
    assert activation_response.json()["status"] == "activated"

    return client, session_id, hero_uuid


def test_standard_arena_composes_map_hero_monsters_environment_and_controllers() -> None:
    """Canonical creation composes the detailed standard playable scene."""
    reset_live_game_tutorial_state()
    client = TestClient(app)
    payload = prepare_canonical_game(client, STANDARD_SCENARIO)
    encounter = sim.encounter
    assert encounter is not None
    hero = Entity.get(
        UUID(roster_assignments(payload, "players")[0]["entity_uuid"])
    )
    monsters = [
        Entity.get(UUID(row["entity_uuid"]))
        for row in roster_assignments(payload, "opposition")
    ]
    assert hero is not None
    assert all(monster is not None for monster in monsters)
    warrior, archer, warlock = monsters
    assert warrior is not None
    assert archer is not None
    assert warlock is not None
    object_names = arena_floor_object_names()

    assert encounter.name == payload["encounter_name"]
    assert encounter.state == EncounterState.NOT_STARTED
    assert encounter.turn_state == TurnState.NOT_STARTED
    assert len(encounter.combatants) == 4
    assert hero.faction == "heroes"
    assert {warrior.faction, archer.faction, warlock.faction} == {"monsters"}
    assert hero.position == (2, 7)
    assert warrior.position == (12, 7)
    assert archer.position == (12, 5)
    assert warlock.position == (12, 9)

    hero_controller = encounter.get_controller_for(hero.uuid)
    warrior_controller = encounter.get_controller_for(warrior.uuid)
    archer_controller = encounter.get_controller_for(archer.uuid)
    warlock_controller = encounter.get_controller_for(warlock.uuid)
    assert hero_controller is not None
    assert warrior_controller is not None
    assert archer_controller is not None
    assert warlock_controller is not None
    assert hero_controller.controller_type == "human"
    assert warrior_controller.controller_type == "native_ai"
    assert archer_controller.controller_type == "native_ai"
    assert warlock_controller.controller_type == "native_ai"

    assert equipped_item_name(hero, WeaponSlot.MELEE_MAIN) == "Shortsword"
    assert equipped_item_name(hero, WeaponSlot.RANGED_MAIN) == "Longbow"
    assert {"Dash", "Dodge", "Disengage", "Action Surge"} <= action_template_names(hero)
    assert hero.get_event_handler_by_name("Opportunity Attack Handler") is not None
    assert warrior.get_event_handler_by_name("Opportunity Attack Handler") is not None

    assert object_names.count("Directional Wall") == 8
    assert object_names.count("Door") == 1
    assert object_names.count("Potion of Healing") == 2
    assert object_names.count("Wall Torch") == 2
    assert object_names.count("Trap Lever") == 1


def test_player_replication_describes_the_subjective_live_arena() -> None:
    """The player seed contains only the controlled hero's observed arena."""
    client, session_id, hero_uuid = start_joined_human_arena()
    hero = Entity.get(UUID(hero_uuid))
    assert hero is not None

    bootstrap = player_replication_seed(client, session_id)
    state = bootstrap["world"]["state"]
    visibility = bootstrap["world"]["visibility"]
    controlled = bootstrap["perspective"]["controlled_entity_uuids"]
    hero_detail = next(
        entity for entity in state["entities"] if entity["uuid"] == hero_uuid
    )
    hero_equipment = bootstrap["world"]["equipment_by_entity"][hero_uuid]
    actions_response = client.get(
        f"/entity/{hero_uuid}/available-actions",
        params={"session_id": session_id},
    )
    actions = actions_response.json()

    assert state["grid"]["min_x"] == 0
    assert state["grid"]["min_y"] == 0
    assert state["grid"]["max_x"] == 14
    assert state["grid"]["max_y"] == 14
    assert {
        (tile["x"], tile["y"])
        for tile in state["grid"]["tiles"]
    } == {
        tuple(position)
        for position in visibility[hero_uuid]["seen_cells"]
    }
    assert {entity["uuid"] for entity in state["entities"]} == {hero_uuid}
    assert sim.encounter is not None
    assert state["encounter"]["name"] == sim.encounter.name
    assert state["encounter"]["state"] == "active"
    assert {obj["name"] for obj in state["floor_objects"]} >= {
        "Trap Lever",
        "Potion of Healing",
    }
    assert "Door" not in {obj["name"] for obj in state["floor_objects"]}

    assert hero_uuid in visibility
    assert visibility[hero_uuid]["name"] == hero.name
    assert visibility[hero_uuid]["position"] == [2, 7]
    assert visibility[hero_uuid]["visible_cells"]
    assert isinstance(visibility[hero_uuid]["sense_modes"], list)

    assert controlled == [hero_uuid]
    assert hero_detail["name"] == hero.name
    assert hero_equipment["ac"] == hero_detail["ac"]
    assert actions_response.status_code == 200
    assert actions["actions_remaining"] == 1


def test_available_actions_action_results_and_log_cursors_drive_the_client_loop() -> None:
    """Available actions, execution results, and log cursors form the client loop."""
    client, session_id, hero_uuid = start_joined_human_arena()

    before = player_replication_seed(client, session_id)
    actions_response = client.get(
        f"/entity/{hero_uuid}/available-actions",
        params={"session_id": session_id},
    )
    actions = actions_response.json()

    assert actions_response.status_code == 200
    assert actions["entity_uuid"] == hero_uuid
    assert actions["actions_remaining"] == 1
    assert actions["bonus_actions_remaining"] == 1
    assert actions["position_actions"]
    assert {"Dash", "Dodge", "Disengage", "Action Surge"} <= {
        action["template_name"] for action in actions["self_actions"]
    }
    assert any(
        action["template_name"].startswith("Drink ")
        for action in actions["self_actions"]
    )

    dash = next(
        action for action in actions["self_actions"] if action["template_name"] == "Dash"
    )
    dash_response = client.post(
        "/action/execute",
        json={
            "session_id": session_id,
            "entity_uuid": hero_uuid,
            "template_name": dash["template_name"],
            "target_index": dash["valid_targets"][0]["index"],
        },
    )
    dash_payload = dash_response.json()
    current, frame_window, log_window = player_replication_after(
        client,
        session_id,
        before,
    )
    log_entries = [
        frame["entry"]
        for frame in log_window["frames"]
        if frame["entry"] is not None
    ]
    presentation = [
        cue
        for frame in frame_window["frames"]
        for cue in frame["presentation"]
    ]

    assert dash_response.status_code == 200
    assert dash_payload["success"] is True
    assert dash_payload["message"] == "Applied Dashing - gained 30ft extra movement"
    assert "combat_log_entries" not in dash_payload
    assert dash_payload["event_cursor_after"] > before["watermarks"]["source_event_cursor"]
    assert dash_payload["combat_log_cursor_after"] == (
        before["watermarks"]["combat_log_cursor"] + 1
    )
    assert current["watermarks"]["source_event_cursor"] == dash_payload["event_cursor_after"]
    assert current["watermarks"]["combat_log_cursor"] == dash_payload["combat_log_cursor_after"]
    assert log_entries[0]["entry_type"] == "action"
    assert log_entries[0]["data"]["action_name"] == "Dash"
    assert any(
        cue["kind"] == "condition"
        and cue["condition_semantic_key"]
        == get_content_declaration(Dashing).ref.identity_key
        and cue["operation"] == "applied"
        for cue in presentation
    )


def test_aoe_test_mode_builds_a_sorcerer_and_clustered_targets() -> None:
    """Canonical composition can prepare a sorcerer and clustered targets."""
    reset_live_game_tutorial_state()
    client = TestClient(app)
    payload = prepare_canonical_game(client, AOE_SCENARIO)
    hero_uuid = roster_assignments(
        payload,
        "players",
    )[0]["entity_uuid"]
    hero = Entity.get(UUID(hero_uuid))
    goblins = [
        Entity.get(UUID(row["entity_uuid"]))
        for row in roster_assignments(payload, "opposition")
    ]

    assert hero is not None
    assert all(goblin is not None for goblin in goblins)
    assert sim.encounter is not None
    assert sim.encounter.name == payload["encounter_name"]
    assert sim.encounter.state == EncounterState.NOT_STARTED

    assert len(goblins) == 3
    assert {goblin.position for goblin in goblins if goblin is not None} == {
        (12, 5),
        (12, 7),
        (12, 9),
    }
    assert hero.is_spellcaster
    assert {"Fireball", "Magic Missile"} <= action_template_names(hero)
    assert hero.action_economy.spell_slot_3.normalized_score > 0


def test_aoe_spell_executes_through_canonical_action_and_replication_routes() -> None:
    """Fireball executes through one action route and one player journal."""
    client, session_id, hero_uuid = start_joined_human_arena(AOE_SCENARIO)

    before = player_replication_seed(client, session_id)
    actions_response = client.get(
        f"/entity/{hero_uuid}/available-actions",
        params={"session_id": session_id},
    )
    assert actions_response.status_code == 200
    fireball = next(
        action
        for action in actions_response.json()["position_actions"]
        if action["template_name"] == "Fireball__slot_3"
    )
    target = max(
        fireball["valid_targets"],
        key=lambda candidate: candidate["affected_count"],
    )
    goblins = [
        entity
        for entity in Entity.get_all_entities()
        if entity.faction == "monsters"
    ]
    assert len(goblins) == 3
    assert target["affected_count"] == len(goblins)
    assert set(target["affected_entity_names"]) == {
        goblin.name for goblin in goblins
    }
    hp_before = {goblin.uuid: goblin.get_hp() for goblin in goblins}

    with fixed_dice_faces(*([1] * 64)):
        execute_response = client.post(
            "/action/execute",
            json={
                "session_id": session_id,
                "entity_uuid": hero_uuid,
                "template_name": fireball["template_name"],
                "target_index": target["index"],
            },
        )

    assert execute_response.status_code == 200
    result = execute_response.json()
    assert result["success"] is True
    assert "state" not in result
    assert "combat_log_entries" not in result
    assert all(goblin.get_hp() < hp_before[goblin.uuid] for goblin in goblins)

    current, frame_window, log_window = player_replication_after(
        client,
        session_id,
        before,
    )
    presentation = [
        cue
        for frame in frame_window["frames"]
        for cue in frame["presentation"]
    ]
    logs = [
        frame["entry"]
        for frame in log_window["frames"]
        if frame["entry"] is not None
    ]
    assert current["watermarks"]["source_event_cursor"] == result["event_cursor_after"]
    assert current["watermarks"]["combat_log_cursor"] == (
        result["combat_log_cursor_after"]
    )
    assert any(
        cue["kind"] == "spell"
        and cue["spell_id"] == "fireball"
        and len(cue["targets"]) == 3
        for cue in presentation
    )
    assert sum(cue["kind"] == "damage" for cue in presentation) == 3
    assert len(logs) == 1
    assert logs[0]["entry_type"] == "multi_entity_action"
    assert logs[0]["data"]["total_targets"] == 3


def test_jump_executes_through_canonical_action_and_replication_routes() -> None:
    """Jump moves the controlled actor through action execution and patches."""
    client, session_id, hero_uuid = start_joined_human_arena()
    hero = Entity.get(UUID(hero_uuid))
    assert hero is not None
    initial_position = hero.position
    initial_movement = hero.action_economy.movement.normalized_score
    before = player_replication_seed(client, session_id)

    actions_response = client.get(
        f"/entity/{hero_uuid}/available-actions",
        params={"session_id": session_id},
    )
    assert actions_response.status_code == 200
    jump = next(
        action
        for action in actions_response.json()["position_actions"]
        if action["template_name"] == "Jump"
    )
    target = next(
        candidate
        for candidate in jump["valid_targets"]
        if tuple(candidate["position"]) != initial_position
    )

    execute_response = client.post(
        "/action/execute",
        json={
            "session_id": session_id,
            "entity_uuid": hero_uuid,
            "template_name": jump["template_name"],
            "target_index": target["index"],
        },
    )
    assert execute_response.status_code == 200
    result = execute_response.json()
    assert result["success"] is True
    assert hero.position == tuple(target["position"])
    assert hero.action_economy.movement.normalized_score < initial_movement

    current, frame_window, log_window = player_replication_after(
        client,
        session_id,
        before,
    )
    replicated_hero = next(
        entity
        for entity in current["world"]["state"]["entities"]
        if entity["uuid"] == hero_uuid
    )
    presentation = [
        cue
        for frame in frame_window["frames"]
        for cue in frame["presentation"]
    ]
    logs = [
        frame["entry"]
        for frame in log_window["frames"]
        if frame["entry"] is not None
    ]
    assert replicated_hero["position"] == target["position"]
    assert any(
        cue["kind"] == "movement"
        and cue["entity_uuid"] == hero_uuid
        and cue["trajectory"][0] == list(initial_position)
        and cue["trajectory"][-1] == target["position"]
        for cue in presentation
    )
    assert len(logs) == 1
    assert logs[0]["entry_type"] == "movement"
