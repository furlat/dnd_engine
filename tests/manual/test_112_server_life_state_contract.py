"""Focused server contracts for authoritative creature lifecycle projection."""

from fastapi.testclient import TestClient

from dnd.controller import HumanController, PassController
from dnd.core.gridmap import get_map
from dnd.types.life import LifeState
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_DECLARATIONS_BY_ID,
)
from server import event_server
from server.player_replication_contract import SubjectiveReplicationBootstrap
from server.world_projection import (
    project_encounter,
    project_entity_summary,
)
from tests.manual.server_test_client import reset_server_test_runtime
from server.session import PlayerType


def _create_life_state_game() -> tuple[TestClient, str, Entity, Entity, Encounter]:
    """Create one visible controlled actor and an opposing observer target."""
    reset_server_test_runtime()
    get_map().create_rectangle(0, 0, 6, 4)

    hero = create_goblin(
        name="Lifecycle Hero",
        position=(1, 1),
        faction="heroes",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["goblin"].ref,
    )
    hero.uses_death_saves = True
    monster = create_skeleton(
        name="Lifecycle Skeleton",
        position=(2, 1),
        faction="monsters",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["skeleton"].ref,
    )
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
        PlayerType.HUMAN,
        "Lifecycle Player",
    )
    game.add_player(session)
    game.assign_entity(hero.uuid, session.session_id)
    return TestClient(event_server.app), str(session.session_id), hero, monster, encounter


def _replicated_entity_after(
    client: TestClient,
    session_id: str,
    bootstrap: dict,
    from_cursor: int,
    entity_uuid: str,
) -> tuple[dict, int]:
    """Return the latest public entity projection after one reducer cursor."""
    response = client.get(
        "/replication/frames",
        params={
            "session_id": session_id,
            "expected_source_stream_id": bootstrap["protocol"]["source_stream_id"],
            "expected_generation_id": bootstrap["protocol"]["generation_id"],
            "expected_perspective_epoch_id": bootstrap["perspective"][
                "perspective_epoch_id"
            ],
            "from_observation_cursor": from_cursor,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    entities = [
        patch["entity"]
        for frame in payload["frames"]
        for patch in frame["patches"]
        if patch["kind"] == "entity_upsert"
        and patch["entity"]["uuid"] == entity_uuid
    ]
    assert entities
    return entities[-1], payload["through_watermarks"]["observation_cursor"]


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
    assert encounter_row.life_state is LifeState.DYING
    assert replica_row.life_state is LifeState.DYING


def test_player_replication_follows_life_state_change_and_revive() -> None:
    """Lifecycle changes reach the player reducer without inferring death from HP."""
    client, session_id, hero, monster, _encounter = _create_life_state_game()
    bootstrap_response = client.get(
        "/replication/bootstrap",
        params={"session_id": session_id},
    )
    assert bootstrap_response.status_code == 200
    bootstrap = bootstrap_response.json()
    cursor = bootstrap["watermarks"]["observation_cursor"]

    hero.enter_dying_state()
    fact, cursor = _replicated_entity_after(
        client,
        session_id,
        bootstrap,
        cursor,
        str(hero.uuid),
    )
    assert fact["hp"] == 0
    assert fact["life_state"] == LifeState.DYING.value

    assert hero.stabilize()
    fact, cursor = _replicated_entity_after(
        client,
        session_id,
        bootstrap,
        cursor,
        str(hero.uuid),
    )
    assert fact["life_state"] == LifeState.STABLE.value

    hero.receive_instant_death(monster.uuid, source_description="contract test")
    fact, cursor = _replicated_entity_after(
        client,
        session_id,
        bootstrap,
        cursor,
        str(hero.uuid),
    )
    assert fact["life_state"] == LifeState.DEAD.value

    assert hero.revive(hit_points=1)
    fact, _cursor = _replicated_entity_after(
        client,
        session_id,
        bootstrap,
        cursor,
        str(hero.uuid),
    )
    assert fact["hp"] == 1
    assert fact["life_state"] == LifeState.ALIVE.value
