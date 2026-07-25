"""Focused server contracts for authoritative creature lifecycle projection."""

from fastapi.testclient import TestClient

from dnd.controller import HumanController, PassController
from dnd.core.events import EventType
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from server import event_server
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.contracts.observation_replay import (
    apply_observation_frame,
    materialize_snapshot,
)
from server.agent_runtime.observation_projector import (
    _event_should_patch_entity_hit_points,
    _event_should_patch_referenced_entities,
)
from server.player_replication_contract import SubjectiveReplicationBootstrap
from server.world_projection import (
    project_encounter,
    project_entity_summary,
)
from server.arena_mode import reset_standard_arena_runtime
from server.session import PlayerType


def _create_life_state_game() -> tuple[TestClient, str, Entity, Entity, Encounter]:
    """Create one visible controlled actor and an opposing observer target."""
    reset_standard_arena_runtime()
    get_map().create_rectangle(0, 0, 6, 4)

    hero = create_goblin(name="Lifecycle Hero", position=(1, 1), faction="heroes")
    hero.uses_death_saves = True
    monster = create_skeleton(name="Lifecycle Skeleton", position=(2, 1), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    encounter = Encounter(name="Lifecycle Contract", source_entity_uuid=hero.uuid)
    encounter.add_combatant(hero, HumanController(source_entity_uuid=hero.uuid))
    encounter.add_combatant(monster, PassController(source_entity_uuid=monster.uuid))
    encounter.roll_initiative()
    encounter.initiative_order = [hero.uuid, monster.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    encounter.start_turn()
    event_server.sim.encounter = encounter

    game = event_server.sim.create_game_session(encounter)
    session = event_server.sim.get_session_manager().create_session(
        PlayerType.AI,
        "Lifecycle Observer",
    )
    game.add_player(session)
    game.assign_entity(hero.uuid, session.session_id)
    return TestClient(event_server.app), str(session.session_id), hero, monster, encounter


def _apply_new_frames(
    client: TestClient,
    session_id: str,
    world: SubjectiveWorldState,
) -> tuple[SubjectiveWorldState, set[str]]:
    """Apply every subjective frame after the supplied materialized cursor."""
    payload = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": world.observation_cursor, "limit": 0},
    ).json()
    event_types = {
        frame["event_type"]
        for frame in payload["frames"]
        if frame.get("event_type") is not None
    }
    for frame in payload["frames"]:
        world = apply_observation_frame(world, frame)
    return world, event_types


def test_player_replica_exposes_life_state_and_does_not_treat_zero_hp_as_dead() -> None:
    """Dying is a zero-HP state, not a synonym for death, on canonical views."""
    client, session_id, hero, _monster, encounter = _create_life_state_game()

    hero.enter_dying_state()
    summary = project_entity_summary(hero)
    encounter_row = next(
        row for row in project_encounter(encounter).initiative_order
        if row.uuid == str(hero.uuid)
    )
    bootstrap_response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert bootstrap_response.status_code == 200
    bootstrap = SubjectiveReplicationBootstrap.model_validate(
        bootstrap_response.json()
    )
    replica_row = next(
        row for row in bootstrap.world.state.entities
        if row.uuid == str(hero.uuid)
    )

    assert hero.get_normal_hp() == 0
    assert summary.life_state is LifeState.DYING
    assert summary.is_dead is False
    assert encounter_row.life_state is LifeState.DYING
    assert encounter_row.is_dead is False
    assert replica_row.life_state is LifeState.DYING
    assert replica_row.is_dead is False


def test_subjective_lifecycle_patches_follow_life_state_change_and_revive() -> None:
    """Lifecycle events patch typed state without inferring death from HP."""
    client, session_id, hero, monster, _encounter = _create_life_state_game()
    world = materialize_snapshot(
        client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    )

    assert _event_should_patch_entity_hit_points(EventType.LIFE_STATE_CHANGE)
    assert _event_should_patch_entity_hit_points(EventType.REVIVE)
    assert _event_should_patch_referenced_entities(EventType.LIFE_STATE_CHANGE)
    assert _event_should_patch_referenced_entities(EventType.REVIVE)

    hero.enter_dying_state()
    world, event_types = _apply_new_frames(client, session_id, world)
    fact = world.known_entities[str(hero.uuid)]
    assert EventType.LIFE_STATE_CHANGE.value in event_types
    assert fact.normal_hp == 0
    assert fact.life_state is LifeState.DYING
    assert fact.is_dead is False

    assert hero.stabilize()
    world, event_types = _apply_new_frames(client, session_id, world)
    fact = world.known_entities[str(hero.uuid)]
    assert EventType.LIFE_STATE_CHANGE.value in event_types
    assert fact.life_state is LifeState.STABLE
    assert fact.is_dead is False

    hero.receive_instant_death(monster.uuid, source_description="contract test")
    world, event_types = _apply_new_frames(client, session_id, world)
    fact = world.known_entities[str(hero.uuid)]
    assert EventType.LIFE_STATE_CHANGE.value in event_types
    assert fact.life_state is LifeState.DEAD
    assert fact.is_dead is True

    assert hero.revive(hit_points=1)
    world, event_types = _apply_new_frames(client, session_id, world)
    fact = world.known_entities[str(hero.uuid)]
    assert EventType.LIFE_STATE_CHANGE.value in event_types
    assert EventType.REVIVE.value in event_types
    assert fact.normal_hp == 1
    assert fact.life_state is LifeState.ALIVE
    assert fact.is_dead is False
