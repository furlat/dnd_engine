"""Focused checks for the external melee AI subprocess integration."""

from typing import Any

from ai.external import AgentCommandType, choose_external_melee_command, reduce_external_agent_state
from ai.observation import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationMaterializedState,
    ObservationObjectFact,
    ObservationSessionState,
)
from dnd.entity import Entity
from server import event_server
from server.arena_mode import ArenaApiClient, reset_standard_arena_runtime


def make_materialized_state(
    *,
    visible_enemy: bool = True,
    dead_enemy: bool = False,
    closed_door: bool = True,
    my_turn: bool = True,
) -> ObservationMaterializedState:
    """Build a compact subjective state for external AI reducer tests."""
    active_uuid = "actor" if my_turn else "hero"
    state = ObservationMaterializedState(
        observation_cursor=12,
        session=ObservationSessionState(
            session_id="session-ai",
            player_type="ai",
            name="AI Monsters",
            connection_status="connected",
            controlled_entity_uuids=["actor"],
            active_entity_uuid=active_uuid,
            active_entity_name="Skeleton Warrior" if my_turn else "Hero",
            is_my_turn=my_turn,
        ),
        known_entities={
            "actor": ObservationEntityFact(
                uuid="actor",
                name="Skeleton Warrior",
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                controlled=True,
                position=(1, 1),
                hp=13,
                max_hp=13,
                faction="monsters",
                is_dead=False,
            ),
            "hero": ObservationEntityFact(
                uuid="hero",
                name="Hero",
                knowledge_state=KnowledgeState.VISIBLE if visible_enemy else KnowledgeState.REMEMBERED,
                observer_uuids=["actor"] if visible_enemy else [],
                controlled=False,
                position=(5, 1),
                hp=24,
                max_hp=24,
                faction="heroes",
                is_dead=dead_enemy,
            ),
            "ally": ObservationEntityFact(
                uuid="ally",
                name="Skeleton Archer",
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                controlled=True,
                position=(1, 2),
                hp=13,
                max_hp=13,
                faction="monsters",
                is_dead=False,
            ),
        },
        known_objects={
            "door": ObservationObjectFact(
                uuid="door",
                name="Door",
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                position=(4, 1),
                state={"is_open": False if closed_door else True},
            ),
            "lever": ObservationObjectFact(
                uuid="lever",
                name="Trap Lever",
                knowledge_state=KnowledgeState.VISIBLE,
                observer_uuids=["actor"],
                position=(2, 2),
                state={"activated": False},
            ),
        },
    )
    return state


def make_action(
    template_name: str,
    *,
    bucket_target_type: str,
    action_category: str,
    targets: list[dict[str, Any]] | None = None,
    display_name: str | None = None,
    can_afford: bool = True,
    is_item_use: bool = False,
    source_item_uuid: str | None = None,
) -> dict[str, Any]:
    """Create one serialized available-action row."""
    row = {
        "template_name": template_name,
        "display_name": display_name or template_name,
        "action_category": action_category,
        "target_type": bucket_target_type,
        "can_afford": can_afford,
        "valid_targets": targets or [],
    }
    if is_item_use:
        row["is_item_use"] = True
        row["source_item_uuid"] = source_item_uuid
    return row


def available_actions_payload(
    *,
    attacks: list[dict[str, Any]] | None = None,
    moves: list[dict[str, Any]] | None = None,
    self_actions: list[dict[str, Any]] | None = None,
    object_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create the serialized shape returned by AI available-actions."""
    return {
        "entity_actions": attacks or [],
        "position_actions": moves or [],
        "self_actions": self_actions or [],
        "object_actions": object_actions or [],
    }


def move_row(targets: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a legal move action row."""
    return make_action(
        "Move",
        bucket_target_type="position_path",
        action_category="movement",
        targets=targets,
    )


def attack_row(target_uuid: str = "hero") -> dict[str, Any]:
    """Create a legal melee attack row."""
    return make_action(
        "Attack_MELEE_MAIN",
        bucket_target_type="entity",
        action_category="attack",
        targets=[{"index": 0, "target_uuid": target_uuid, "target_name": "Hero"}],
    )


def spell_row(target_uuid: str = "hero") -> dict[str, Any]:
    """Create a legal entity-targeting spell row."""
    return make_action(
        "Eldritch Blast",
        bucket_target_type="entity",
        action_category="spell",
        targets=[{"index": 3, "target_uuid": target_uuid, "target_name": "Hero"}],
    )


def open_door_row(bucket_target_type: str = "self") -> dict[str, Any]:
    """Create an item-use row for an adjacent door."""
    return make_action(
        "Open Door",
        bucket_target_type=bucket_target_type,
        action_category="ability",
        display_name="Open Door",
        targets=[{"index": 0, "target_uuid": "door", "target_name": "Door"}],
        is_item_use=True,
        source_item_uuid="door",
    )


def test_reducer_extracts_actor_enemies_doors_and_action_rows() -> None:
    """Reduced external state keeps only behavior-tree decision facts."""
    materialized = make_materialized_state()
    payload = available_actions_payload(
        attacks=[attack_row()],
        moves=[move_row([{"index": 2, "position": [2, 1], "path": [[1, 1], [2, 1]]}])],
        self_actions=[open_door_row()],
    )

    state = reduce_external_agent_state(materialized, payload)

    assert state.observation_cursor == 12
    assert state.session_id == "session-ai"
    assert state.actor_uuid == "actor"
    assert state.actor_position == (1, 1)
    assert [enemy.uuid for enemy in state.visible_enemies] == ["hero"]
    assert state.visible_enemies[0].distance_feet == 20
    assert [door.uuid for door in state.known_closed_doors] == ["door"]
    assert state.self_actions[0].is_item_use is True
    assert state.self_actions[0].source_item_uuid == "door"
    assert state.position_actions[0].valid_targets[0].position == (2, 1)
    assert state.position_actions[0].valid_targets[0].path == [(1, 1), (2, 1)]


def test_reducer_excludes_dead_hidden_and_controlled_entities() -> None:
    """Visible enemies are living, non-controlled, currently visible facts."""
    hidden_state = reduce_external_agent_state(make_materialized_state(visible_enemy=False))
    dead_state = reduce_external_agent_state(make_materialized_state(dead_enemy=True))

    assert hidden_state.visible_enemies == []
    assert dead_state.visible_enemies == []


def test_behavior_tree_attacks_before_movement_or_doors() -> None:
    """The first external policy priority is a legal visible-enemy attack."""
    state = reduce_external_agent_state(
        make_materialized_state(),
        available_actions_payload(
            attacks=[attack_row()],
            moves=[move_row([{"index": 1, "position": [2, 1]}])],
            self_actions=[open_door_row()],
        ),
    )

    command = choose_external_melee_command(state)

    assert command.command_type == AgentCommandType.EXECUTE
    assert command.entity_uuid == "actor"
    assert command.template_name == "Attack_MELEE_MAIN"
    assert command.target_index == 0
    assert command.reason == "attack_visible_enemy"


def test_behavior_tree_casts_visible_enemy_spell_before_weapon_attack() -> None:
    """Casters use legal offensive spells before falling back to weapon attacks."""
    state = reduce_external_agent_state(
        make_materialized_state(),
        available_actions_payload(
            attacks=[attack_row(), spell_row()],
            moves=[move_row([{"index": 1, "position": [2, 1]}])],
        ),
    )

    command = choose_external_melee_command(state)

    assert command.command_type == AgentCommandType.EXECUTE
    assert command.entity_uuid == "actor"
    assert command.template_name == "Eldritch Blast"
    assert command.target_index == 3
    assert command.reason == "cast_visible_enemy_spell"


def test_behavior_tree_moves_toward_visible_enemy_when_attack_is_unavailable() -> None:
    """A visible enemy without an attack target makes movement chase the enemy."""
    state = reduce_external_agent_state(
        make_materialized_state(),
        available_actions_payload(
            moves=[move_row([
                {"index": 0, "position": [0, 1]},
                {"index": 1, "position": [2, 1]},
                {"index": 2, "position": [1, 2]},
            ])],
            self_actions=[open_door_row()],
        ),
    )

    command = choose_external_melee_command(state)

    assert command.command_type == AgentCommandType.EXECUTE
    assert command.template_name == "Move"
    assert command.target_index == 1
    assert command.reason == "move_toward_visible_enemy"


def test_behavior_tree_opens_adjacent_door_when_no_enemy_is_visible() -> None:
    """Open Door rows can come from any action bucket once the actor is adjacent."""
    state = reduce_external_agent_state(
        make_materialized_state(visible_enemy=False),
        available_actions_payload(
            self_actions=[open_door_row()],
            object_actions=[open_door_row(bucket_target_type="object")],
        ),
    )

    command = choose_external_melee_command(state)

    assert command.command_type == AgentCommandType.EXECUTE
    assert command.template_name == "Open Door"
    assert command.target_index == 0
    assert command.reason == "open_adjacent_door"


def test_behavior_tree_moves_toward_known_closed_door() -> None:
    """When no enemy is visible and no door action is legal, the AI approaches a closed door."""
    state = reduce_external_agent_state(
        make_materialized_state(visible_enemy=False),
        available_actions_payload(
            moves=[move_row([
                {"index": 0, "position": [0, 1]},
                {"index": 1, "position": [2, 1]},
                {"index": 2, "position": [1, 2]},
            ])],
        ),
    )

    command = choose_external_melee_command(state)

    assert command.command_type == AgentCommandType.EXECUTE
    assert command.template_name == "Move"
    assert command.target_index == 1
    assert command.reason == "move_toward_closed_door"


def test_behavior_tree_ends_turn_without_enemy_or_closed_door() -> None:
    """The final leaf ends the turn when the reduced state has no useful branch."""
    state = reduce_external_agent_state(
        make_materialized_state(visible_enemy=False, closed_door=False),
        available_actions_payload(
            moves=[move_row([{"index": 0, "position": [0, 1]}])],
        ),
    )

    command = choose_external_melee_command(state)

    assert command.command_type == AgentCommandType.END_TURN
    assert command.entity_uuid == "actor"
    assert command.reason == "end_turn"


def test_behavior_tree_waits_when_it_is_not_the_ai_turn() -> None:
    """The policy emits no command when the active actor is not controlled."""
    state = reduce_external_agent_state(make_materialized_state(my_turn=False))

    command = choose_external_melee_command(state)

    assert command.command_type == AgentCommandType.WAIT
    assert command.reason == "not_my_turn"


def test_start_human_external_mode_creates_ai_session_and_spawns_once(monkeypatch) -> None:
    """External monster mode wires monsters to external controllers and spawns one subprocess."""
    reset_standard_arena_runtime()
    starts: list[tuple[str, str]] = []

    def fake_start_external_melee_agent(session_id, base_url: str) -> None:
        starts.append((str(session_id), base_url))

    monkeypatch.setattr(
        event_server.ai_process_manager,
        "start_external_melee_agent",
        fake_start_external_melee_agent,
    )

    client = ArenaApiClient()
    response = client.post(
        "/simulation/start-human",
        params={"character_class": "fighter", "monster_ai": "external"},
    )
    payload = response.json()
    game_status = client.get("/game/status").json()
    monsters = [entity for entity in Entity.get_all_entities() if entity.faction == "monsters"]
    encounter = event_server.sim.encounter
    assert encounter is not None
    controller_types = set()
    for monster in monsters:
        controller = encounter.get_controller_for(monster.uuid)
        assert controller is not None
        controller_types.add(controller.controller_type)
    ai_sessions = [session for session in game_status["sessions"] if session["player_type"] == "ai"]

    assert response.status_code == 200
    assert payload["status"] == "waiting_for_human"
    assert payload["entity_uuid"] == payload["hero_uuid"]
    assert payload["monster_ai"] == "external"
    assert payload["ai_session_id"] == starts[0][0]
    assert starts == [(payload["ai_session_id"], "http://testserver")]
    assert controller_types == {"external_ai"}
    assert len(ai_sessions) == 1
    assert ai_sessions[0]["name"] == "AI Monsters"
    assert len(ai_sessions[0]["controlled_entities"]) == 3


def test_start_human_default_mode_uses_external_monster_ai(monkeypatch) -> None:
    """Default monster mode is the external behavior-tree controller path."""
    reset_standard_arena_runtime()
    starts: list[tuple[str, str]] = []

    def fake_start_external_melee_agent(session_id, base_url: str) -> None:
        starts.append((str(session_id), base_url))

    monkeypatch.setattr(
        event_server.ai_process_manager,
        "start_external_melee_agent",
        fake_start_external_melee_agent,
    )

    client = ArenaApiClient()
    response = client.post("/simulation/start-human", params={"character_class": "fighter"})
    monsters = [entity for entity in Entity.get_all_entities() if entity.faction == "monsters"]
    encounter = event_server.sim.encounter
    assert encounter is not None
    controller_types = set()
    for monster in monsters:
        controller = encounter.get_controller_for(monster.uuid)
        assert controller is not None
        controller_types.add(controller.controller_type)

    assert response.status_code == 200
    assert response.json()["monster_ai"] == "external"
    assert starts == [(response.json()["ai_session_id"], "http://testserver")]
    assert controller_types == {"external_ai"}


def test_start_human_rejects_unknown_monster_ai_mode() -> None:
    """The start endpoint rejects unknown monster AI modes instead of guessing."""
    reset_standard_arena_runtime()
    client = ArenaApiClient()

    response = client.post(
        "/simulation/start-human",
        params={"character_class": "fighter", "monster_ai": "bogus"},
    )
    detail = response.json()["detail"]

    assert response.status_code == 400
    assert detail["code"] == "invalid_monster_ai"
    assert detail["valid_monster_ai"] == ["external"]


def test_ai_process_diagnostics_and_reset_cleanup(monkeypatch) -> None:
    """AI process status is exposed and simulation reset stops tracked subprocesses."""
    reset_standard_arena_runtime()
    stop_calls: list[str] = []

    def fake_stop_all() -> None:
        stop_calls.append("stop")

    monkeypatch.setattr(event_server.ai_process_manager, "stop_all", fake_stop_all)

    client = ArenaApiClient()
    status_response = client.get("/ai/processes")
    reset_response = client.post("/simulation/reset")

    assert status_response.status_code == 200
    assert status_response.json() == {"processes": [], "running_session_ids": []}
    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "reset"
    assert stop_calls == ["stop"]
