"""Manual Chapter 21 checks for arena game sessions and client state."""

import warnings
from uuid import UUID

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient
import pytest
from pathlib import Path

from dnd.controller import Controller
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.values import BaseValue
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.entity import Entity
from dnd.utils import reset_combat_state
from server import event_server
from server.agent_runtime.service import AgentLaunchRequest
from server.agent_runtime.subprocess_service import AgentProcessSpec, SubprocessAgentService
from server.event_server import (
    _available_actions_cache,
    app,
    setup_arena_combat,
    sim,
)
from server.event_stream import event_stream


class _TutorialAgentLauncher:
    """Registered managed-agent capability for in-process tutorial checks."""

    service_id = "tests.tutorial-agent"

    def preflight(self, required_agents: int) -> None:
        _ = required_agents
        return None

    def build_process_spec(self, request: AgentLaunchRequest) -> AgentProcessSpec:
        return AgentProcessSpec(
            argv=("unused-tutorial-agent", request.session_id),
            cwd=Path(__file__).resolve().parents[2],
        )


@pytest.fixture(autouse=True)
def stub_external_ai_processes(monkeypatch: pytest.MonkeyPatch):
    """Keep arena-session tutorial checks from spawning real AI subprocesses."""
    service_id = event_server.agent_service_manager.service_id
    if service_id is not None:
        event_server.agent_service_manager.unregister_service(service_id)
    event_server.agent_service_manager.register_service(SubprocessAgentService(_TutorialAgentLauncher()))

    async def accept_batch(
        _requests: tuple[AgentLaunchRequest, ...],
    ) -> tuple[object, ...]:
        return ()

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "start_agents",
        accept_batch,
    )
    yield
    event_server.agent_service_manager.stop_all_blocking()
    service_id = event_server.agent_service_manager.service_id
    if service_id is not None:
        event_server.agent_service_manager.unregister_service(service_id)


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
    event_stream.ensure_attached()
    event_stream._clear_source_journal()
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
    hero = entity_by_name("Hero")
    warrior = entity_by_name("Skeleton Warrior")
    archer = entity_by_name("Skeleton Archer")
    warlock = entity_by_name("Skeleton Warlock")
    object_names = arena_floor_object_names()

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


def test_player_replication_describes_the_subjective_live_arena() -> None:
    """The player seed contains only the controlled hero's observed arena."""
    client, session_id, hero_uuid = start_joined_human_arena()

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
    assert {entity["name"] for entity in state["entities"]} == {"Hero"}
    assert state["encounter"]["name"] == "Arena Combat"
    assert state["encounter"]["state"] == "active"
    assert {obj["name"] for obj in state["floor_objects"]} >= {
        "Trap Lever",
        "Potion of Healing",
    }
    assert "Door" not in {obj["name"] for obj in state["floor_objects"]}

    assert hero_uuid in visibility
    assert visibility[hero_uuid]["name"] == "Hero"
    assert visibility[hero_uuid]["position"] == [2, 7]
    assert visibility[hero_uuid]["visible_cells"]
    assert isinstance(visibility[hero_uuid]["sense_modes"], list)

    assert controlled == [hero_uuid]
    assert hero_detail["name"] == "Hero"
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
    assert any(action["template_name"].startswith("Drink Greater Invisibility Potion") for action in actions["self_actions"])

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
        and cue["condition_semantic_key"] == "dnd.conditions.Dashing"
        and cue["operation"] == "applied"
        for cue in presentation
    )


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


def test_aoe_spell_executes_through_canonical_action_and_replication_routes() -> None:
    """Fireball executes through one action route and one player journal."""
    reset_live_game_tutorial_state()
    client = TestClient(app)
    start_response = client.post("/simulation/start-aoe-test")
    assert start_response.status_code == 200
    hero_uuid = start_response.json()["hero_uuid"]

    session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "AoE Player"},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]
    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [hero_uuid]},
    )
    assert join_response.status_code == 200

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
    assert target["affected_count"] == 3
    assert set(target["affected_entity_names"]) == {
        "Goblin 1",
        "Goblin 2",
        "Goblin 3",
    }
    goblins = [
        entity
        for entity in Entity.get_all_entities()
        if entity.name is not None and entity.name.startswith("Goblin ")
    ]
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
