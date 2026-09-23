"""Native encounters and controllers, independent of the retired HTTP server.

The former HTTP/session assertions are preserved with their disposition in
agent_docs/retired_server_tests/2026-09-21/README.md.
"""

from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field

from dnd.actions import Attack
from dnd.controller import Controller, HumanController, PassController, TurnContext
from dnd.core.base_actions import BaseAction
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.life_types import LifeState
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.entity import Entity
from dnd.game import Game
from dnd.monsters.bestiary import create_goblin as _create_goblin, create_skeleton as _create_skeleton
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_DECLARATIONS_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from tests.engine.support import force_attack_hit, get_hp, remove_attack_modifier, set_hp


def create_goblin(**kwargs) -> Entity:
    entity = _create_goblin(**kwargs)
    entity.compose_entity()
    Game().deploy_entity(entity, entity.position)
    return entity


def create_skeleton(**kwargs) -> Entity:
    entity = _create_skeleton(**kwargs)
    entity.compose_entity()
    Game().deploy_entity(entity, entity.position)
    return entity


def reset_runtime_tutorial_state(width: int = 16, height: int = 10) -> None:
    """Start one clean native test world."""
    reset_engine_runtime(grid_size=(width, height))


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


def create_runtime_pair() -> tuple[Entity, Entity]:
    """Create two opposing tutorial combatants."""
    hero = create_goblin(
        name="Runtime Hero",
        position=(1, 1),
        faction="heroes",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["goblin"].ref,
    )
    monster = create_skeleton(
        name="Runtime Skeleton",
        position=(2, 1),
        faction="monsters",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["skeleton"].ref,
    )
    Entity.update_all_entities_senses()
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


def test_encounter_start_and_end_own_runtime_callbacks() -> None:
    """Encounter start and end own active state, callbacks, and controller notices."""
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
    assert EventQueue._combat_log_callback == encounter._on_event_combat_log
    assert EventQueue._perceiver_computer is not None
    assert EventQueue._revealed_computer is not None

    end_event = encounter.end_encounter("tutorial complete")

    assert end_event.reason == "tutorial complete"
    assert encounter.state == EncounterState.ENDED
    assert Encounter.get_active() is None
    assert hero_controller.encounter_end_names == ["Runtime Hero"]
    assert monster_controller.encounter_end_names == ["Runtime Skeleton"]
    assert EventQueue._combat_log_callback is None
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


def test_advance_until_player_runs_automated_turns_and_stops_for_input() -> None:
    """Automated controllers run until a human-controlled turn needs input."""
    reset_runtime_tutorial_state()
    hero, monster = create_runtime_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        monster,
    )

    result = encounter.advance_until_player()

    assert result.status == "waiting_for_human"
    assert result.entity_uuid == hero.uuid
    assert result.entity_name == "Runtime Hero"
    assert result.round_number == 1
    assert result.turn_index == 1
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 1


def test_controller_run_turn_executes_actions_and_combat_log_listeners() -> None:
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
    listener_calls: list[tuple[int, str]] = []

    def listener(active: Encounter, index: int, entry, event) -> None:
        listener_calls.append((index, entry.entry_type.value))

    force_uuid = force_attack_hit(hero)
    starting_hp = get_hp(monster)
    Encounter.add_combat_log_listener(listener)
    try:
        end_event = encounter.run_turn()
    finally:
        remove_attack_modifier(hero, force_uuid)
        Encounter.remove_combat_log_listener(listener)

    assert end_event is not None
    assert controller.used
    assert get_hp(monster) < starting_hp
    assert encounter.combat_log
    assert listener_calls
    assert listener_calls[-1][0] == len(encounter.combat_log) - 1
    assert encounter.get_combat_log(
        requested_generation=EventQueue.generation_id(),
        since=listener_calls[-1][0],
    )[0] is encounter.combat_log[-1]


def test_death_checks_mark_dead_combatants_and_end_by_faction_survival() -> None:
    """Encounter death checks mark dead actors and end when one faction survives."""
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
    death_events = encounter.check_deaths()

    assert death_events
    assert encounter.combatants[monster.uuid].is_dead
    assert monster.health.life_state is LifeState.DEAD
    assert encounter.state == EncounterState.ENDED
    assert Encounter.get_active() is None
    assert len(encounter.get_alive_combatants()) == 1
    assert encounter.get_dead_combatants()[0].entity_uuid == monster.uuid
