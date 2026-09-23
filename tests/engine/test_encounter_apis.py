"""Native encounters and controllers, independent of the retired HTTP server.

The former HTTP/session assertions are preserved with their disposition in
agent_docs/retired_server_tests/2026-09-21/README.md.
"""

import json

from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field

from dnd.actions import Attack, Move
from dnd.controller import CodexController, Controller, HumanController, PassController, TurnContext
from dnd.core.base_actions import BaseAction
from dnd.core.creature_types import DamageType
from dnd.items.environment import DirectionalWall
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.entity import Entity
from dnd.game import Game
from dnd.monsters.bestiary import create_goblin as _create_goblin, create_skeleton as _create_skeleton
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_DECLARATIONS_BY_ID
from dnd.reactions import add_opportunity_attack_handler
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


def reset_chapter_18_state(width: int = 16, height: int = 10) -> None:
    """Start one clean native test world."""
    reset_engine_runtime(grid_size=(width, height))


class RecordingController(Controller):
    """Controller that records lifecycle callbacks for parity examples."""

    name: str = Field(default="Recording Controller")
    controller_type: str = Field(default="recording")
    encounter_start_names: list[str] = Field(default_factory=list)
    encounter_end_names: list[str] = Field(default_factory=list)
    turn_start_contexts: list[TurnContext] = Field(default_factory=list)
    turn_end_contexts: list[TurnContext] = Field(default_factory=list)

    def on_encounter_start(self, entities: list[Entity]) -> None:
        """Record encounter-start notification entities."""
        self.encounter_start_names.extend(entity.name for entity in entities)

    def on_encounter_end(self, entities: list[Entity]) -> None:
        """Record encounter-end notification entities."""
        self.encounter_end_names.extend(entity.name for entity in entities)

    def on_turn_start(self, entity: Entity, context: TurnContext) -> None:
        """Record turn-start context."""
        self.turn_start_contexts.append(context)

    def on_turn_end(self, entity: Entity, context: TurnContext) -> None:
        """Record turn-end context."""
        self.turn_end_contexts.append(context)


class OneAttackController(Controller):
    """Controller that returns one melee attack, then stops."""

    name: str = Field(default="One Attack Controller")
    controller_type: str = Field(default="one_attack")
    target_uuid: UUID = Field(description="Target UUID for the one scripted attack")
    used: bool = Field(default=False)

    def get_next_action(self, entity: Entity, context: TurnContext) -> Optional[BaseAction]:
        """Return one attack action, then end the turn."""
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
        """Continue only until the scripted attack is used."""
        return not self.used


def create_book_pair() -> tuple[Entity, Entity]:
    """Create two opposing combatants for Chapter 18 examples."""
    hero = create_goblin(
        name="Book Hero",
        position=(1, 1),
        faction="heroes",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["goblin"].ref,
    )
    monster = create_skeleton(
        name="Book Skeleton",
        position=(2, 1),
        faction="monsters",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["skeleton"].ref,
    )
    Entity.update_all_entities_senses()
    return hero, monster


def create_melee_only_skeleton(
    name: str,
    position: tuple[int, int],
    faction: Optional[str],
) -> Entity:
    """Create a skeleton fixture whose controller choices are melee-only.

    Args:
        name: Entity name.
        position: Starting grid position.
        faction: Optional faction identifier.

    Returns:
        Skeleton with its ranged-main weapon removed.
    """
    skeleton = create_skeleton(
        name=name,
        position=position,
        faction=faction,
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["skeleton"].ref,
    )
    removed = skeleton.equipment.unequip(WeaponSlot.RANGED_MAIN)

    assert removed is not None
    assert skeleton.get_action_template("Attack_RANGED_MAIN") is None
    return skeleton


def start_ordered_encounter(
    hero: Entity,
    monster: Entity,
    hero_controller: Controller,
    monster_controller: Controller,
    first: Entity,
) -> Encounter:
    """Create an active encounter with deterministic initiative order."""
    encounter = Encounter(name="Book Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, hero_controller)
    encounter.add_combatant(monster, monster_controller)
    encounter.roll_initiative()
    second = monster if first.uuid == hero.uuid else hero
    encounter.initiative_order = [first.uuid, second.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    return encounter


def test_eb_18_001_encounter_start_sets_active_state_callbacks_and_round() -> None:
    """EB-18-001: encounter start wires active state, initiative, and callbacks."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    hero_controller = RecordingController(source_entity_uuid=hero.uuid)
    monster_controller = RecordingController(source_entity_uuid=monster.uuid)

    encounter = start_ordered_encounter(hero, monster, hero_controller, monster_controller, hero)

    assert encounter.state == EncounterState.ACTIVE
    assert Encounter.get_active() is encounter
    assert encounter.round_number == 1
    assert encounter.turn_state == TurnState.NOT_STARTED
    assert encounter.initiative_order == [hero.uuid, monster.uuid]
    assert hero_controller.encounter_start_names == ["Book Hero"]
    assert monster_controller.encounter_start_names == ["Book Skeleton"]
    assert EventQueue._combat_log_callback == encounter._on_event_combat_log
    assert EventQueue._perceiver_computer is not None
    assert EventQueue._revealed_computer is not None

    end_event = encounter.end_encounter("chapter test complete")

    assert end_event.reason == "chapter test complete"
    assert encounter.state == EncounterState.ENDED
    assert Encounter.get_active() is None
    assert hero_controller.encounter_end_names == ["Book Hero"]
    assert monster_controller.encounter_end_names == ["Book Skeleton"]
    assert EventQueue._combat_log_callback is None
    assert EventQueue._perceiver_computer is None
    assert EventQueue._revealed_computer is None


def test_eb_18_002_turn_lifecycle_builds_context_and_advances_rounds() -> None:
    """EB-18-002: start/end/next turn updates context, counters, and rounds."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
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


def test_eb_18_003_run_turn_and_advance_until_player_respect_controller_types() -> None:
    """EB-18-003: controller types drive autonomous turns and player stops."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    human_controller = HumanController(source_entity_uuid=hero.uuid)
    pass_controller = PassController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_encounter(hero, monster, human_controller, pass_controller, monster)

    result = encounter.advance_until_player()

    assert result.status == "waiting_for_human"
    assert result.entity_uuid == hero.uuid
    assert result.entity_name == "Book Hero"
    assert result.round_number == 1
    assert result.turn_index == 1
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 1


def test_eb_18_019_surprise_blocks_reactions_until_skipped_turn_ends() -> None:
    """EB-18-019: surprise prevents reactions until the skipped first turn ends."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    add_opportunity_attack_handler(monster)
    encounter = Encounter(name="Book Surprise Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, HumanController(source_entity_uuid=hero.uuid))
    encounter.add_combatant(monster, PassController(source_entity_uuid=monster.uuid), surprised=True)
    encounter.roll_initiative()
    encounter.initiative_order = [hero.uuid, monster.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()

    assert monster.action_economy.reactions.normalized_score == 0

    encounter.start_turn()
    initial_hero_hp = get_hp(hero)
    move_event = Move(source_entity_uuid=hero.uuid, end_position=(1, 3)).apply()

    assert move_event is not None
    assert not move_event.canceled
    assert get_hp(hero) == initial_hero_hp
    assert monster.action_economy.reactions.normalized_score == 0

    encounter.end_turn()
    encounter.next_turn()

    assert encounter.round_number == 2
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 1
    assert monster.action_economy.reactions.normalized_score == 1


def test_eb_18_020_codex_controller_stops_as_external_input_turn() -> None:
    """EB-18-020: Codex-controlled turns stop for external input."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    codex_controller = CodexController(source_entity_uuid=hero.uuid)
    pass_controller = PassController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_encounter(hero, monster, codex_controller, pass_controller, monster)

    result = encounter.advance_until_player()
    context = encounter._build_turn_context(hero)

    assert result.status == "waiting_for_codex"
    assert result.entity_uuid == hero.uuid
    assert result.entity_name == "Book Hero"
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 1
    assert not codex_controller.can_continue_turn(hero, context)
    assert codex_controller.get_next_action(hero, context) is None


def test_eb_18_034_available_move_paths_preserve_directional_blockers() -> None:
    """EB-18-034: Available Move rows carry legal paths around directional blockers."""
    reset_chapter_18_state(width=8, height=5)
    grid = get_map()
    melee_actor = create_melee_only_skeleton(name="Book AI Skeleton", position=(1, 1), faction="monsters")
    distant_target = create_goblin(
        name="Distant Hero",
        position=(5, 1),
        faction="heroes",
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["goblin"].ref,
    )

    barrier = DirectionalWall(item_id="test.encounter.movement_boundary",
        source_entity_uuid=uuid4(), name="Movement boundary", include_in_senses_objects=True,
        blocked_channels=(WorldEdgeChannel.MOVEMENT,))
    barrier.place_on_grid((1, 1), boundary_direction=CardinalDirection.EAST)
    Entity.update_all_entities_senses()

    assert not grid.can_transition((1, 1), (2, 1))
    assert barrier.uuid in melee_actor.senses.objects

    assert distant_target.uuid in melee_actor.get_visible_enemies()

    move_info = next(
        action_info
        for action_info in melee_actor.get_available_actions().position_actions
        if action_info.template_name == "Move"
    )
    legal_move_targets = {
        target.position: target
        for target in move_info.valid_targets
        if target.position is not None
    }

    improving_targets = [
        target
        for target in legal_move_targets.values()
        if target.position is not None
        and abs(target.position[0] - distant_target.position[0])
        + abs(target.position[1] - distant_target.position[1])
        < abs(melee_actor.position[0] - distant_target.position[0])
        + abs(melee_actor.position[1] - distant_target.position[1])
    ]
    chosen_target = min(
        improving_targets,
        key=lambda target: len(target.path or []),
    )

    assert chosen_target.position is not None
    assert chosen_target.path is not None
    assert chosen_target.path[0] == melee_actor.position
    assert chosen_target.path[-1] == chosen_target.position
    assert ((1, 1), (2, 1)) not in zip(chosen_target.path, chosen_target.path[1:])

    for start, end in zip(chosen_target.path, chosen_target.path[1:]):
        assert grid.can_transition(start, end)

    current_distance = abs(melee_actor.position[0] - distant_target.position[0]) + abs(
        melee_actor.position[1] - distant_target.position[1]
    )
    moved_distance = abs(chosen_target.position[0] - distant_target.position[0]) + abs(
        chosen_target.position[1] - distant_target.position[1]
    )
    assert moved_distance < current_distance


def test_eb_18_004_execute_action_captures_combat_log_and_listener_payload() -> None:
    """EB-18-004: API-style action execution appends combat log entries."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    hero_controller = HumanController(source_entity_uuid=hero.uuid)
    monster_controller = PassController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_encounter(hero, monster, hero_controller, monster_controller, hero)
    encounter.start_turn()

    listener_calls: list[tuple[int, str]] = []

    def listener(active: Encounter, index: int, entry, event) -> None:
        listener_calls.append((index, entry.entry_type.value))

    Encounter.add_combat_log_listener(listener)
    force_uuid = force_attack_hit(hero)
    initial_hp = get_hp(monster)
    try:
        event = encounter.execute_action(hero.uuid, "Attack_MELEE_MAIN", 0)
    finally:
        remove_attack_modifier(hero, force_uuid)
        Encounter.remove_combat_log_listener(listener)

    assert event is not None
    assert not event.canceled
    assert get_hp(monster) < initial_hp
    assert encounter.combat_log
    assert listener_calls
    assert listener_calls[-1][0] == len(encounter.combat_log) - 1
    assert encounter.get_combat_log(
        requested_generation=EventQueue.generation_id(),
        since=listener_calls[-1][0],
    )[0] is encounter.combat_log[-1]


def test_eb_18_005_check_deaths_marks_dead_and_ends_single_faction_encounter() -> None:
    """EB-18-005: encounter death checks mark dead combatants and end combat."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
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


def test_check_deaths_ends_encounter_after_entity_already_committed_death() -> None:
    """An authoritative death still triggers encounter-end reconciliation."""
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        hero,
    )

    monster.receive_damage(
        monster.get_normal_hp(),
        DamageType.SLASHING,
        hero.uuid,
    )
    assert monster.health.life_state is LifeState.DEAD

    assert encounter.check_deaths() == []
    assert encounter.state is EncounterState.ENDED
    assert Encounter.get_active() is None


def test_entity_and_encounter_serialization_are_json_safe() -> None:
    reset_chapter_18_state()
    hero, monster = create_book_pair()
    encounter = start_ordered_encounter(hero, monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid), hero)
    cursor = EventQueue.event_cursor()
    entity_dump = hero.model_dump(mode="json")
    encounter_dump = encounter.model_dump(mode="json")
    json.dumps(entity_dump)
    json.dumps(encounter_dump)
    assert "registered_actions" in entity_dump
    assert "combatants" in encounter_dump
    assert "initiative_order" in encounter_dump
    assert EventQueue.event_cursor() == cursor
