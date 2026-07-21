"""Manual Chapter 21 checks for arena game sessions and client state."""

import warnings

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient
import pytest

from dnd.controller import Controller
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue, WeaponSlot
from dnd.core.values import BaseValue
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.entity import Entity
from dnd.utils import reset_combat_state
from server import event_server
from server.event_server import (
    _available_actions_cache,
    app,
    setup_arena_combat,
    sim,
)


@pytest.fixture(autouse=True)
def stub_external_ai_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep arena-session tutorial checks from spawning real AI subprocesses."""
    monkeypatch.setattr(event_server.ai_process_manager, "start_external_agent", lambda *_args: None)
    monkeypatch.setattr(event_server.ai_process_manager, "stop_all", lambda: None)


def reset_live_game_tutorial_state() -> None:
    """Clear global state used by arena-game tutorial examples."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    EventQueue.set_perceiver_computer(None)
    EventQueue.set_revealed_computer(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    Encounter._combat_log_listeners.clear()
    _available_actions_cache.clear()

    manager = sim.get_session_manager()
    manager.sessions.clear()
    manager.games.clear()
    manager.active_game = None
    sim.encounter = None
    sim._game_session = None
    sim.combat_task = None
    sim.paused = True


def entity_by_name(name: str) -> Entity:
    """Return the currently registered entity with a display name."""
    entity = next((candidate for candidate in Entity.get_all_entities() if candidate.name == name), None)
    assert entity is not None
    return entity


def state_floor_object_names(client: TestClient) -> list[str]:
    """Return floor-object names from the public game-state payload."""
    return [obj["name"] for obj in client.get("/state").json()["floor_objects"]]


def action_template_names(entity: Entity) -> set[str]:
    """Return registered action-template names for an entity."""
    return {action.name for action in entity.registered_actions if action.name is not None}


def equipped_item_name(entity: Entity, slot: WeaponSlot) -> str:
    """Return the name of an item equipped in a weapon slot."""
    item = entity.equipment.get_item_by_slot(slot)
    assert item is not None
    assert item.name is not None
    return item.name


def start_joined_human_arena() -> tuple[TestClient, str, str]:
    """Start the human arena mode and join a player session to the Hero."""
    reset_live_game_tutorial_state()
    client = TestClient(app)
    start_response = client.post("/simulation/start-human", params={"character_class": "fighter"})

    assert start_response.status_code == 200
    start_payload = start_response.json()
    hero_uuid = start_payload["hero_uuid"]

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

    return client, session_id, hero_uuid


def test_standard_arena_composes_map_hero_monsters_environment_and_controllers() -> None:
    """The standard arena fixture composes the playable game scene."""
    reset_live_game_tutorial_state()

    encounter = setup_arena_combat(pvp_mode=False, character_class="fighter")
    sim.encounter = encounter
    client = TestClient(app)
    hero = entity_by_name("Hero")
    warrior = entity_by_name("Skeleton Warrior")
    archer = entity_by_name("Skeleton Archer")
    warlock = entity_by_name("Skeleton Warlock")
    object_names = state_floor_object_names(client)

    assert encounter.name == "Arena Combat"
    assert encounter.state == EncounterState.NOT_STARTED
    assert len(encounter.combatants) == 4
    assert hero.faction == "heroes"
    assert {warrior.faction, archer.faction, warlock.faction} == {"monsters"}
    assert hero.position == (2, 7)
    assert warrior.position == (12, 5)
    assert archer.position == (12, 7)
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
    assert warrior_controller.controller_type == "external_ai"
    assert archer_controller.controller_type == "external_ai"
    assert warlock_controller.controller_type == "external_ai"

    assert equipped_item_name(hero, WeaponSlot.MELEE_MAIN) == "Shortsword"
    assert equipped_item_name(hero, WeaponSlot.MELEE_OFF) == "Dagger"
    assert equipped_item_name(hero, WeaponSlot.RANGED_MAIN) == "Longbow"
    assert {"Dash", "Dodge", "Disengage", "Action Surge"} <= action_template_names(hero)
    assert hero.get_event_handler_by_name("Opportunity Attack Handler") is not None
    assert warrior.get_event_handler_by_name("Opportunity Attack Handler") is not None

    assert object_names.count("Directional Wall") == 8
    assert object_names.count("Door") == 1
    assert object_names.count("Potion of Healing") == 2
    assert object_names.count("Wall Torch") == 2
    assert object_names.count("Trap Lever") == 1


def test_pvp_arena_uses_codex_controllers_for_monster_side() -> None:
    """PvP arena mode keeps the same scene and swaps monster-side controllers."""
    reset_live_game_tutorial_state()

    encounter = setup_arena_combat(pvp_mode=True, character_class="fighter")
    hero = entity_by_name("Hero")
    monsters = [entity for entity in Entity.get_all_entities() if entity.faction == "monsters"]

    assert encounter.name == "PvP Arena"
    hero_controller = encounter.get_controller_for(hero.uuid)
    monster_controllers = [encounter.get_controller_for(monster.uuid) for monster in monsters]
    assert hero_controller is not None
    assert all(controller is not None for controller in monster_controllers)
    assert hero_controller.controller_type == "human"
    assert len(monsters) == 3
    assert {controller.controller_type for controller in monster_controllers if controller is not None} == {"codex"}


def test_start_human_mode_creates_ai_session_and_waits_for_player_join() -> None:
    """The human arena endpoint starts the game and assigns monsters to AI."""
    reset_live_game_tutorial_state()
    client = TestClient(app)

    response = client.post("/simulation/start-human", params={"character_class": "fighter"})
    payload = response.json()
    hero_uuid = payload["hero_uuid"]
    game_status = client.get("/game/status").json()

    assert response.status_code == 200
    assert payload["status"] == "waiting_for_human"
    assert payload["entity_uuid"] == hero_uuid
    assert payload["entity_name"] == "Hero"
    assert payload["combat_log_cursor_after"] >= 1
    assert sim.encounter is not None
    assert sim.encounter.name == "Arena Combat"
    assert sim.encounter.state == EncounterState.ACTIVE
    assert sim.encounter.turn_state == TurnState.IN_PROGRESS

    assert game_status["active"] is True
    assert game_status["encounter_active"] is True
    assert game_status["active_entity_uuid"] == hero_uuid
    ai_sessions = [session for session in game_status["sessions"] if session["player_type"] == "ai"]
    assert len(ai_sessions) == 1
    assert ai_sessions[0]["name"] == "AI Monsters"
    assert len(ai_sessions[0]["controlled_entities"]) == 3

    session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Tutorial Player"},
    )
    session_id = session_response.json()["session_id"]
    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [hero_uuid]},
    )
    ping_response = client.post(f"/session/{session_id}/ping")

    assert session_response.status_code == 200
    assert join_response.status_code == 200
    assert join_response.json()["controlled_entities"] == [hero_uuid]
    assert ping_response.status_code == 200
    assert ping_response.json()["is_my_turn"] is True
    assert ping_response.json()["active_entity_name"] == "Hero"


def test_state_visibility_and_session_entity_payloads_describe_the_live_arena() -> None:
    """Client-facing payloads describe map, entities, encounter, and vision."""
    client, session_id, hero_uuid = start_joined_human_arena()

    state = client.get("/state").json()
    visibility = client.get("/visibility").json()
    controlled = client.get(f"/session/{session_id}/entities").json()
    hero_detail = client.get(f"/entity/{hero_uuid}").json()

    assert state["grid"]["min_x"] == 0
    assert state["grid"]["min_y"] == 0
    assert state["grid"]["max_x"] == 14
    assert state["grid"]["max_y"] == 14
    assert len(state["grid"]["tiles"]) == 225
    assert {entity["name"] for entity in state["entities"]} == {
        "Hero",
        "Skeleton Warrior",
        "Skeleton Archer",
        "Skeleton Warlock",
    }
    assert state["encounter"]["name"] == "Arena Combat"
    assert state["encounter"]["state"] == "active"
    assert {obj["name"] for obj in state["floor_objects"]} >= {"Door", "Trap Lever", "Potion of Healing"}

    assert hero_uuid in visibility
    assert visibility[hero_uuid]["name"] == "Hero"
    assert visibility[hero_uuid]["position"] == [2, 7]
    assert visibility[hero_uuid]["visible_cells"]
    assert isinstance(visibility[hero_uuid]["sense_modes"], list)

    assert controlled["controlled_entities"][0]["uuid"] == hero_uuid
    assert controlled["controlled_entities"][0]["name"] == "Hero"
    assert hero_detail["name"] == "Hero"
    assert hero_detail["equipment"]["ac"] == hero_detail["ac"]
    assert hero_detail["action_economy"]["actions"] == 1


def test_available_actions_action_results_and_log_cursors_drive_the_client_loop() -> None:
    """Available actions, execution results, and log cursors form the client loop."""
    client, session_id, hero_uuid = start_joined_human_arena()

    actions_response = client.get(f"/entity/{hero_uuid}/available-actions")
    actions = actions_response.json()
    before_log = client.get("/combat-log").json()
    before_event_total = client.get("/events", params={"since": 0, "limit": 0}).json()["total"]

    assert actions_response.status_code == 200
    assert actions["entity_uuid"] == hero_uuid
    assert actions["actions_remaining"] == 1
    assert actions["bonus_actions_remaining"] == 1
    assert actions["position_actions"]
    assert {"Dash", "Dodge", "Disengage", "Action Surge"} <= {
        action["template_name"] for action in actions["self_actions"]
    }
    assert any(action["template_name"].startswith("Drink Greater Invisibility Potion") for action in actions["self_actions"])

    dash_response = client.post(
        "/action/self",
        json={"session_id": session_id, "entity_uuid": hero_uuid, "action_name": "Dash"},
    )
    dash_payload = dash_response.json()
    new_logs = client.get("/combat-log", params={"since": before_log["total"]}).json()
    new_events = client.get("/events", params={"since": before_event_total, "limit": 0}).json()

    assert dash_response.status_code == 200
    assert dash_payload["success"] is True
    assert dash_payload["message"] == "Applied Dashing - gained 30ft extra movement"
    assert dash_payload["combat_log_entries"][0]["entry_type"] == "action"
    assert dash_payload["combat_log_entries"][0]["data"]["action_name"] == "Dash"
    assert dash_payload["combat_log_cursor_after"] == before_log["total"] + 1
    assert new_logs["count"] == 1
    assert new_logs["entries"][0]["entry_type"] == "action"
    assert new_events["total"] > before_event_total


def test_aoe_test_mode_builds_a_sorcerer_and_clustered_targets() -> None:
    """The AoE test mode is a purpose-built game scenario for spell play."""
    reset_live_game_tutorial_state()
    client = TestClient(app)

    response = client.post("/simulation/start-aoe-test")
    payload = response.json()
    hero_uuid = payload["hero_uuid"]
    entities = {entity.name: entity for entity in Entity.get_all_entities()}

    assert response.status_code == 200
    assert payload["status"] == "waiting_for_human"
    assert payload["test_type"] == "aoe"
    assert payload["entity_uuid"] == hero_uuid
    assert sim.encounter is not None
    assert sim.encounter.name == "AoE Test Arena"

    assert set(entities) == {"Hero", "Goblin 1", "Goblin 2", "Goblin 3"}
    assert entities["Goblin 1"].position == (12, 4)
    assert entities["Goblin 2"].position == (12, 5)
    assert entities["Goblin 3"].position == (12, 6)
    hero = entities["Hero"]
    assert hero.is_spellcaster
    assert {"Fireball", "Magic Missile", "Lightning Bolt"} <= action_template_names(hero)
    assert hero.action_economy.spell_slot_3.normalized_score > 0
