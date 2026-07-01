"""Manual checks for strict session-subjective AI observation streams."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from ai.observation import apply_observation_frame, materialize_snapshot
from dnd.conditions import Invisible
from dnd.controller import Controller, HumanController, PassController
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, SensoryUpdateEvent, SensoryUpdateReason
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import AutoHitModifier, AutoHitStatus
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from server.event_server import app, sim
from server.event_stream import event_stream
from server.session import PlayerType


def reset_observation_state(width: int = 16, height: int = 10) -> None:
    """Clear runtime state for one observation-stream scenario."""
    event_stream.stop()
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    EventQueue.set_perceiver_computer(None)
    EventQueue.set_revealed_computer(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    Encounter._combat_log_listeners.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, width, height)
    sim.reset()


def create_observation_game(
    hidden_monster: bool = False,
    second_hero: bool = False,
) -> tuple[TestClient, str, Entity, Entity, Encounter]:
    """Create an active game with one session controlling the hero side."""
    reset_observation_state()
    hero = create_goblin(name="Observation Hero", position=(1, 1), faction="heroes")
    monster = create_skeleton(name="Observation Skeleton", position=(2, 1), faction="monsters")
    extra_hero = None
    if second_hero:
        extra_hero = create_goblin(name="Observation Ally", position=(1, 2), faction="heroes")
    if hidden_monster:
        monster.add_condition(Invisible(source_entity_uuid=monster.uuid, target_entity_uuid=monster.uuid))

    Entity.update_all_entities_senses(max_distance=20)

    encounter = Encounter(name="Observation Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, HumanController(source_entity_uuid=hero.uuid))
    if extra_hero is not None:
        encounter.add_combatant(extra_hero, HumanController(source_entity_uuid=extra_hero.uuid))
    encounter.add_combatant(monster, PassController(source_entity_uuid=monster.uuid))
    encounter.roll_initiative()
    encounter.initiative_order = [hero.uuid] + ([extra_hero.uuid] if extra_hero else []) + [monster.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    encounter.start_turn()
    sim.encounter = encounter
    game = sim.create_game_session(encounter)

    manager = sim.get_session_manager()
    session = manager.create_session(PlayerType.AI, "Observation Agent")
    game.add_player(session)
    game.assign_entity(hero.uuid, session.session_id)
    if extra_hero is not None:
        game.assign_entity(extra_hero.uuid, session.session_id)

    return TestClient(app), str(session.session_id), hero, monster, encounter


def add_auto_hit(entity: Entity) -> UUID:
    """Add an auto-hit attack modifier for deterministic replay checks."""
    modifier = AutoHitModifier(
        name="Observation Auto Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    return entity.equipment.melee_attack_bonus.self_static.add_auto_hit_modifier(modifier)


def attack_target_index(actions: dict, target_uuid: UUID) -> int:
    """Return the target index for a visible melee target."""
    for action in actions["entity_actions"]:
        if action["template_name"] != "Attack_MELEE_MAIN":
            continue
        for target in action["valid_targets"]:
            if target.get("target_uuid") == str(target_uuid):
                return target["index"]
    raise AssertionError("Target was not present in available melee attacks")


def complete_event(event):
    """Register an event through the normal lifecycle."""
    current = EventQueue.register(event)
    current = EventQueue.register(current.phase_to(EventPhase.EXECUTION))
    current = EventQueue.register(current.phase_to(EventPhase.EFFECT))
    EventQueue.register(current.phase_to(EventPhase.COMPLETION))


def test_ai_observation_snapshot_contains_subjective_data() -> None:
    """A session snapshot contains controlled observers and visible facts."""
    client, session_id, hero, monster, encounter = create_observation_game()

    response = client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    payload = response.json()
    known_names = {entity["name"] for entity in payload["known_entities"]}
    observer = payload["observers"][0]

    assert response.status_code == 200
    assert payload["session"]["session_id"] == session_id
    assert payload["session"]["controlled_entity_uuids"] == [str(hero.uuid)]
    assert payload["session"]["is_my_turn"] is True
    assert payload["encounter"]["uuid"] == str(encounter.uuid)
    assert observer["observer_uuid"] == str(hero.uuid)
    assert observer["visible_cells"]
    assert observer["seen_cells"]
    assert str(monster.uuid) in observer["visible_entity_uuids"]
    assert {"Observation Hero", "Observation Skeleton"} <= known_names
    assert payload["observation_cursor"] >= 1


def test_hidden_enemy_is_not_leaked_in_strict_snapshot() -> None:
    """Unperceived invisible enemies are absent from known entity facts."""
    client, session_id, _hero, monster, _encounter = create_observation_game(hidden_monster=True)

    response = client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    payload = response.json()
    known_names = {entity["name"] for entity in payload["known_entities"]}
    initiative_names = [row["name"] for row in payload["encounter"]["initiative_order"]]

    assert response.status_code == 200
    assert "Observation Skeleton" not in known_names
    assert str(monster.uuid) not in {
        entity["uuid"] for entity in payload["known_entities"]
    }
    assert "Unknown Combatant" in initiative_names


def test_multi_entity_session_uses_one_stream_with_observer_tags() -> None:
    """A multi-entity controller receives one stream tagged by observer."""
    client, session_id, hero, monster, _encounter = create_observation_game(second_hero=True)

    response = client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    payload = response.json()
    observer_ids = {observer["observer_uuid"] for observer in payload["observers"]}
    skeleton_fact = next(
        entity for entity in payload["known_entities"]
        if entity["uuid"] == str(monster.uuid)
    )

    assert response.status_code == 200
    assert len(payload["session"]["controlled_entity_uuids"]) == 2
    assert str(hero.uuid) in observer_ids
    assert len(observer_ids) == 2
    assert set(skeleton_fact["observer_uuids"]) <= observer_ids
    assert skeleton_fact["observer_uuids"]


def test_sensory_updates_project_only_for_the_matching_session() -> None:
    """Observer-specific sensory events are filtered by controlled entity."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    before = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()

    visible_event = SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(3, 3)],
        seen_cells_added=[(3, 3)],
        visible_entities_added={monster.uuid: monster.position},
        phase=EventPhase.DECLARATION,
    )
    complete_event(visible_event)

    unrelated_event = SensoryUpdateEvent(
        source_entity_uuid=monster.uuid,
        target_entity_uuid=monster.uuid,
        observer_uuid=monster.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(4, 4)],
        seen_cells_added=[(4, 4)],
        phase=EventPhase.DECLARATION,
    )
    complete_event(unrelated_event)

    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before["observation_cursor"], "limit": 0},
    ).json()["frames"]
    observer_frames = [
        frame for frame in frames
        if any(patch["patch_type"] == "observer" for patch in frame["patches"])
    ]

    assert observer_frames
    assert all(
        patch.get("observer_uuid") == str(hero.uuid)
        for frame in observer_frames
        for patch in frame["patches"]
        if patch["patch_type"] == "observer"
    )
    assert all(
        patch.get("observer_uuid") != str(monster.uuid)
        for frame in frames
        for patch in frame["patches"]
    )


def test_snapshot_plus_frames_replays_to_fresh_subjective_state() -> None:
    """Snapshot plus frames rebuilds the same known HP as a fresh snapshot."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    before_snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    state = materialize_snapshot(before_snapshot)
    actions = client.get(
        f"/ai/sessions/{session_id}/entities/{hero.uuid}/available-actions",
        params={"basis_cursor": before_snapshot["observation_cursor"]},
    ).json()
    target_index = attack_target_index(actions, monster.uuid)
    modifier_uuid = add_auto_hit(hero)
    try:
        with fixed_dice_faces(12, 4):
            execute = client.post(
                "/action/execute",
                json={
                    "session_id": session_id,
                    "entity_uuid": str(hero.uuid),
                    "template_name": "Attack_MELEE_MAIN",
                    "target_index": target_index,
                },
            )
    finally:
        hero.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)

    assert execute.status_code == 200

    frames_payload = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before_snapshot["observation_cursor"], "limit": 0},
    ).json()
    for frame in frames_payload["frames"]:
        state = apply_observation_frame(state, frame)
        state = apply_observation_frame(state, frame)

    fresh_snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    fresh_state = materialize_snapshot(fresh_snapshot)

    assert frames_payload["frames"]
    assert state.known_entities[str(monster.uuid)].hp == fresh_state.known_entities[str(monster.uuid)].hp
    assert state.observation_cursor == frames_payload["next_observation_cursor"]
    assert state.combat_logs


def test_ai_available_actions_are_session_authorized() -> None:
    """The AI affordance endpoint rejects uncontrolled or inactive entities."""
    client, session_id, _hero, monster, _encounter = create_observation_game()
    manager = sim.get_session_manager()
    monster_session = manager.create_session(PlayerType.AI, "Monster Agent")
    assert sim.game is not None
    sim.game.add_player(monster_session)
    sim.game.assign_entity(monster.uuid, monster_session.session_id)

    uncontrolled = client.get(
        f"/ai/sessions/{session_id}/entities/{monster.uuid}/available-actions"
    )
    inactive = client.get(
        f"/ai/sessions/{monster_session.session_id}/entities/{monster.uuid}/available-actions"
    )

    assert uncontrolled.status_code == 403
    assert uncontrolled.json()["detail"]["code"] == "entity_not_controlled"
    assert inactive.status_code == 403
    assert inactive.json()["detail"]["code"] == "not_entity_turn"
