"""Focused checks for encounters, turns, controllers, and APIs."""
from dnd.types.materials import Material, TileSurface

import warnings
from typing import Optional
from uuid import UUID, uuid4

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient
from pydantic import Field

from dnd.actions.standard import (
    Attack,
)
from dnd.encounters.controllers import (
    Controller,
    HumanController,
    PassController,
    TurnContext,
)
from dnd.core.base_actions import (
    BaseAction,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.types.equipment import WeaponSlot
from dnd.core.events.events_registry import (
    EventQueue,
)
from dnd.core.gridmap import get_map
from dnd.types.life import LifeState
from dnd.core.values import BaseValue
from dnd.encounters.encounter import Encounter
from dnd.types.encounter_state import EncounterState, TurnState
from dnd.entities.entity import Entity
from tests.engine.support import create_test_monster
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_DECLARATIONS_BY_ID,
)
from tests.engine.support import force_attack_hit, get_hp, remove_attack_modifier, reset_combat_state, set_hp
from server.event_server import app, sim
from server.event_stream import event_stream


class RecordingController(Controller):
    """Record encounter and turn callbacks for tutorial assertions."""

    name: str = Field(default="Recording Controller")
    controller_type: str = Field(default="recording")
    encounter_start_names: list[str] = Field(default_factory=list)
    encounter_end_names: list[str] = Field(default_factory=list)
    turn_start_contexts: list[TurnContext] = Field(default_factory=list)
    turn_end_contexts: list[TurnContext] = Field(default_factory=list)

    def on_encounter_start(self, entities: list[Entity]) -> None:
        """Record the entities assigned to this controller at encounter start."""
        self.encounter_start_names.extend(entity.name for entity in entities)

    def on_encounter_end(self, entities: list[Entity]) -> None:
        """Record the entities assigned to this controller at encounter end."""
        self.encounter_end_names.extend(entity.name for entity in entities)

    def on_turn_start(self, entity: Entity, context: TurnContext) -> None:
        """Record the context available at turn start."""
        self.turn_start_contexts.append(context)

    def on_turn_end(self, entity: Entity, context: TurnContext) -> None:
        """Record the context available at turn end."""
        self.turn_end_contexts.append(context)


class OneAttackController(Controller):
    """Return one melee attack, then stop asking to continue the turn."""

    name: str = Field(default="One Attack Controller")
    controller_type: str = Field(default="one_attack")
    target_uuid: UUID = Field(description="Target UUID for the scripted attack.")
    used: bool = Field(default=False)

    def get_next_action(self, entity: Entity, context: TurnContext) -> Optional[BaseAction]:
        """Return the scripted attack once."""
        if self.used:
            return None
        self.used = True
        return Attack(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=self.target_uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            template=False,
        )

    def can_continue_turn(self, entity: Entity, context: TurnContext) -> bool:
        """Continue until the scripted attack has been returned."""
        return not self.used


def reset_runtime_tutorial_state(width: int = 16, height: int = 10) -> None:
    """Clear global runtime state and create a rectangular tutorial arena."""
    reset_combat_state()
    EventQueue.set_perceiver_computer(None)
    EventQueue.set_revealed_computer(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    event_stream.ensure_attached()
    event_stream._clear_source_journal()
    sim.reset()

    get_map().create_rectangle(0, 0, width, height, surface=TileSurface(base_material=Material.STONE))


def create_runtime_pair() -> tuple[Entity, Entity]:
    """Create two opposing tutorial combatants."""
    hero = create_test_monster("monster.goblin", 
        name="Runtime Hero",
        position=(1, 1),
        faction="heroes",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["goblin"].ref,
    )
    monster = create_test_monster("monster.skeleton", 
        name="Runtime Skeleton",
        position=(2, 1),
        faction="monsters",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["skeleton"].ref,
    )
    Entity.materialize_all_navigation()
    return hero, monster


def start_ordered_encounter(
    hero: Entity,
    monster: Entity,
    hero_controller: Controller,
    monster_controller: Controller,
    first: Entity,
) -> Encounter:
    """Create an active encounter with deterministic initiative order."""
    encounter = Encounter(name="Runtime Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, hero_controller)
    encounter.add_combatant(monster, monster_controller)
    encounter.roll_initiative()
    second = monster if first.uuid == hero.uuid else hero
    encounter.initiative_order = [first.uuid, second.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    return encounter


def create_session_controlled_turn() -> tuple[TestClient, str, Entity, Entity, Encounter]:
    """Create an in-process API session that controls the active hero turn."""
    reset_runtime_tutorial_state()
    hero, monster = create_runtime_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        hero,
    )
    encounter.start_turn()
    sim.encounter = encounter
    sim.create_game_session(encounter)

    client = TestClient(app)
    session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Runtime Player"},
    )
    assert session_response.status_code == 200
    assert session_response.json()["player_type"] == "human"
    session_id = session_response.json()["session_id"]

    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [str(hero.uuid)]},
    )
    assert join_response.status_code == 200
    assert join_response.json()["controlled_entities"] == [str(hero.uuid)]

    return client, session_id, hero, monster, encounter


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
    """Read exact player reducer and log windows after a captured seed."""
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


def test_encounter_start_and_end_own_runtime_state() -> None:
    """Encounter start and end own active state and controller notices."""
    reset_runtime_tutorial_state()
    hero, monster = create_runtime_pair()
    hero_controller = RecordingController(source_entity_uuid=hero.uuid)
    monster_controller = RecordingController(source_entity_uuid=monster.uuid)

    encounter = start_ordered_encounter(hero, monster, hero_controller, monster_controller, hero)

    assert encounter.state == EncounterState.ACTIVE
    assert Encounter.get_active() is encounter
    assert encounter.round_number == 1
    assert encounter.turn_state == TurnState.NOT_STARTED
    assert encounter.initiative_order == [hero.uuid, monster.uuid]
    assert hero_controller.encounter_start_names == ["Runtime Hero"]
    assert monster_controller.encounter_start_names == ["Runtime Skeleton"]
    assert EventQueue._perceiver_computer is not None
    assert EventQueue._revealed_computer is not None

    end_event = encounter.end_encounter("tutorial complete")

    assert end_event.reason == "tutorial complete"
    assert encounter.state == EncounterState.ENDED
    assert Encounter.get_active() is None
    assert hero_controller.encounter_end_names == ["Runtime Hero"]
    assert monster_controller.encounter_end_names == ["Runtime Skeleton"]
    assert EventQueue._perceiver_computer is None
    assert EventQueue._revealed_computer is None


def test_turn_lifecycle_builds_controller_context_and_advances_rounds() -> None:
    """Turn boundaries create controller context and advance rounds."""
    reset_runtime_tutorial_state()
    hero, monster = create_runtime_pair()
    hero_controller = RecordingController(source_entity_uuid=hero.uuid)
    monster_controller = RecordingController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_encounter(hero, monster, hero_controller, monster_controller, hero)

    start_event = encounter.start_turn()

    assert start_event is not None
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.get_current_entity() is hero
    assert hero_controller.turn_start_contexts
    start_context = hero_controller.turn_start_contexts[-1]
    assert start_context.entity_uuid == hero.uuid
    assert start_context.round_number == 1
    assert start_context.actions_remaining == 1
    assert monster.uuid in start_context.visible_enemies

    end_event = encounter.end_turn()

    assert end_event is not None
    assert encounter.turn_state == TurnState.ENDED
    assert encounter.combatants[hero.uuid].has_acted_this_round
    assert encounter.combatants[hero.uuid].turn_count == 1
    assert hero_controller.turn_end_contexts[-1].entity_uuid == hero.uuid

    next_event = encounter.next_turn()

    assert next_event is not None
    assert encounter.get_current_entity() is monster
    assert encounter.current_turn_index == 1
    assert encounter.round_number == 1

    encounter.end_turn()
    encounter.next_turn()

    assert encounter.get_current_entity() is hero
    assert encounter.current_turn_index == 0
    assert encounter.round_number == 2
    assert not encounter.combatants[hero.uuid].has_acted_this_round
    assert not encounter.combatants[monster.uuid].has_acted_this_round


def test_advance_until_external_boundary_runs_autonomous_turns() -> None:
    """Autonomous controllers run until an external turn needs input."""
    reset_runtime_tutorial_state()
    hero, monster = create_runtime_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        monster,
    )

    result = encounter.advance_until_external_boundary()

    assert result.status == "waiting_for_human"
    assert result.entity_uuid == hero.uuid
    assert result.entity_name == "Runtime Hero"
    assert result.round_number == 1
    assert result.turn_index == 1
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 1


def test_controller_run_turn_projects_combat_log_from_terminal_facts() -> None:
    """Encounter-run controller actions are captured in the combat log."""
    reset_runtime_tutorial_state()
    hero, monster = create_runtime_pair()
    controller = OneAttackController(source_entity_uuid=hero.uuid, target_uuid=monster.uuid)
    encounter = start_ordered_encounter(
        hero,
        monster,
        controller,
        PassController(source_entity_uuid=monster.uuid),
        hero,
    )
    force_uuid = force_attack_hit(hero)
    starting_hp = get_hp(monster)
    try:
        end_event = encounter.run_turn()
    finally:
        remove_attack_modifier(hero, force_uuid)

    assert end_event is not None
    assert controller.used
    assert get_hp(monster) < starting_hp
    assert encounter.combat_log
    assert encounter.get_combat_log(since=len(encounter.combat_log) - 1)[0] is encounter.combat_log[-1]


def test_lethal_damage_commits_death_and_ends_by_faction_survival() -> None:
    """Lethal damage commits death before encounter-end reconciliation."""
    reset_runtime_tutorial_state()
    hero, monster = create_runtime_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        hero,
    )

    set_hp(monster, 0)
    assert monster.health.life_state is LifeState.DEAD
    death_events = encounter.check_deaths()

    assert death_events == []
    assert encounter.combatants[monster.uuid].is_dead
    assert monster.health.life_state is LifeState.DEAD
    assert encounter.state == EncounterState.ENDED
    assert Encounter.get_active() is None
    assert len(encounter.get_alive_combatants()) == 1
    assert encounter.get_dead_combatants()[0].entity_uuid == monster.uuid


def test_session_api_exposes_authoritative_turn_actions_and_results() -> None:
    """The API boundary gates actions by session ownership and active turn."""
    client, session_id, hero, monster, encounter = create_session_controlled_turn()

    before = player_replication_seed(client, session_id)
    turn_payload = before["world"]["state"]["encounter"]
    ping_response = client.post(f"/session/{session_id}/ping")
    ping_payload = ping_response.json()
    current_entity = next(
        entity
        for entity in before["world"]["state"]["entities"]
        if entity["uuid"] == turn_payload["current_entity_uuid"]
    )

    assert turn_payload["state"] == "active"
    assert turn_payload["current_entity_uuid"] == str(hero.uuid)
    assert current_entity["name"] == "Runtime Hero"
    assert ping_response.status_code == 200
    assert ping_payload["is_my_turn"] is True
    assert ping_payload["active_entity_uuid"] == str(hero.uuid)
    assert before["perspective"]["controlled_entity_uuids"] == [str(hero.uuid)]

    actions_response = client.get(
        f"/entity/{hero.uuid}/available-actions",
        params={"session_id": session_id},
    )
    actions_payload = actions_response.json()

    assert actions_response.status_code == 200
    assert actions_payload["entity_uuid"] == str(hero.uuid)
    attack_rows = [
        action for action in actions_payload["entity_actions"]
        if action["template_name"] == "Attack_MELEE_MAIN"
    ]
    assert attack_rows
    assert any(
        target.get("target_uuid") == str(monster.uuid)
        for target in attack_rows[0]["valid_targets"]
    )

    force_uuid = force_attack_hit(hero)
    starting_hp = get_hp(monster)
    try:
        action_response = client.post(
            "/action/execute",
            json={
                "session_id": session_id,
                "entity_uuid": str(hero.uuid),
                "template_name": "Attack_MELEE_MAIN",
                "target_index": 0,
            },
        )
    finally:
        remove_attack_modifier(hero, force_uuid)

    action_payload = action_response.json()
    current, frame_window, log_window = player_replication_after(
        client,
        session_id,
        before,
    )
    replicated_monster = next(
        row
        for row in current["world"]["state"]["entities"]
        if row["uuid"] == str(monster.uuid)
    )

    assert action_response.status_code == 200
    assert action_payload["success"] is True
    assert replicated_monster["hp"] < starting_hp
    assert frame_window["frames"]
    assert log_window["frames"]
    assert "target_hp" not in action_payload
    assert "combat_log_entries" not in action_payload
    assert encounter.combat_log

    denied_response = client.post(
        "/action/execute",
        json={
            "session_id": session_id,
            "entity_uuid": str(monster.uuid),
            "template_name": "Attack_MELEE_MAIN",
            "target_index": 0,
        },
    )

    assert denied_response.status_code == 403
    assert denied_response.json()["detail"]["code"] == "entity_not_controlled"


def test_lethal_multi_entity_command_reports_causal_death_and_primary_hp() -> None:
    """Lethal Magic Missile reports its nested death without fallback duplication."""
    reset_runtime_tutorial_state()
    caster = create_test_monster("monster.generic_caster", 
        name="Runtime Caster",
        position=(1, 1),
        faction="heroes",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID[
            "generic_caster"
        ].ref,
    )
    monster = create_test_monster("monster.skeleton", 
        name="Runtime Target",
        position=(2, 1),
        faction="monsters",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["skeleton"].ref,
    )
    Entity.materialize_all_navigation()
    encounter = start_ordered_encounter(
        caster,
        monster,
        HumanController(source_entity_uuid=caster.uuid),
        PassController(source_entity_uuid=monster.uuid),
        caster,
    )
    encounter.start_turn()
    sim.encounter = encounter
    sim.create_game_session(encounter)
    client = TestClient(app)
    session_response = client.post(
        "/session/create",
        json={"player_type": "human", "name": "Runtime Caster Player"},
    )
    session_id = session_response.json()["session_id"]
    join_response = client.post(
        "/game/join",
        json={"session_id": session_id, "entity_uuids": [str(caster.uuid)]},
    )
    assert join_response.status_code == 200
    set_hp(monster, 1)
    before = player_replication_seed(client, session_id)

    available_response = client.get(
        f"/entity/{caster.uuid}/available-actions",
        params={"session_id": session_id},
    )
    assert available_response.status_code == 200
    available = available_response.json()
    missile = next(
        row
        for row in available["entity_actions"]
        if row.get("base_template_name") == "Magic Missile"
        and row.get("cast_at_level") == 1
    )
    target_index = next(
        target["index"]
        for target in missile["valid_targets"]
        if target.get("target_uuid") == str(monster.uuid)
    )

    response = client.post(
        "/action/execute",
        json={
            "session_id": session_id,
            "entity_uuid": str(caster.uuid),
            "template_name": missile["template_name"],
            "target_index": target_index,
            "extra_target_uuids": [str(monster.uuid), str(monster.uuid)],
        },
    )
    payload = response.json()
    current, frame_window, log_window = player_replication_after(
        client,
        session_id,
        before,
    )
    patches = [patch for frame in frame_window["frames"] for patch in frame["patches"]]
    cues = [cue for frame in frame_window["frames"] for cue in frame["presentation"]]
    damage_cues = [
        cue
        for cue in cues
        if cue["kind"] == "damage" and cue["target_uuid"] == str(monster.uuid)
    ]
    life_cues = [
        cue
        for cue in cues
        if cue["kind"] == "life_state" and cue["entity_uuid"] == str(monster.uuid)
    ]

    assert response.status_code == 200
    assert damage_cues[-1]["resulting_hp"] == monster.get_hp()
    assert life_cues[-1]["current"] == LifeState.DEAD.value
    assert life_cues[-1]["causing_effect_presentation_id"] in {
        cue["presentation_id"] for cue in damage_cues
    }
    assert not any(
        patch["kind"] == "entity_remove"
        and patch["entity_uuid"] == str(monster.uuid)
        for patch in patches
    )
    replicated_corpse = next(
        row
        for row in current["world"]["state"]["entities"]
        if row["uuid"] == str(monster.uuid)
    )
    assert replicated_corpse["life_state"] == LifeState.DEAD.value
    assert frame_window["frames"]
    assert payload["encounter_ended"] is True
    death_entries = [
        entry
        for frame in log_window["frames"]
        for root in [frame["entry"]]
        for entry in _walk_combat_log_entries(root)
        if entry["entry_type"] == "death"
    ]
    assert len(death_entries) == 1
    assert {"deaths", "target_hp", "combat_log_entries"}.isdisjoint(payload)


def _walk_combat_log_entries(entry: dict) -> list[dict]:
    """Return one combat-log subtree in depth-first order."""
    descendants = [entry]
    for child in entry.get("sub_entries", []):
        descendants.extend(_walk_combat_log_entries(child))
    return descendants
