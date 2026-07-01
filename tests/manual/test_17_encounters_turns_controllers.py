"""Manual Chapter 17 checks for encounters, turns, and controllers."""

from uuid import UUID, uuid4

from pydantic import Field

from dnd.controller import Controller, HumanController, PassController, TurnContext
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import AutoHitModifier, AutoHitStatus, DamageType
from dnd.core.values import BaseValue
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton


class RecordingController(Controller):
    """Controller that records encounter and turn callbacks."""

    name: str = Field(default="Recording Controller", description="Display name.")
    controller_type: str = Field(default="recording", description="Controller type.")
    encounter_start_names: list[str] = Field(
        default_factory=list,
        description="Names received at encounter start.",
    )
    encounter_end_names: list[str] = Field(
        default_factory=list,
        description="Names received at encounter end.",
    )
    turn_start_contexts: list[TurnContext] = Field(
        default_factory=list,
        description="Turn contexts received at turn start.",
    )
    turn_end_contexts: list[TurnContext] = Field(
        default_factory=list,
        description="Turn contexts received at turn end.",
    )

    def on_encounter_start(self, entities: list[Entity]) -> None:
        """Record entities controlled by this controller when combat begins."""
        self.encounter_start_names.extend(entity.name for entity in entities)

    def on_encounter_end(self, entities: list[Entity]) -> None:
        """Record entities controlled by this controller when combat ends."""
        self.encounter_end_names.extend(entity.name for entity in entities)

    def on_turn_start(self, entity: Entity, context: TurnContext) -> None:
        """Record the turn-start context for later inspection."""
        self.turn_start_contexts.append(context)

    def on_turn_end(self, entity: Entity, context: TurnContext) -> None:
        """Record the turn-end context for later inspection."""
        self.turn_end_contexts.append(context)


def reset_encounter_tutorial_state(width: int = 16, height: int = 10) -> None:
    """Clear global runtime state and create a rectangular encounter arena."""
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


def create_encounter_pair() -> tuple[Entity, Entity]:
    """Create a nearby hero and monster with opposing factions."""
    hero = create_goblin(name="Manual Hero", position=(1, 1), faction="heroes")
    monster = create_skeleton(name="Manual Skeleton", position=(2, 1), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)
    return hero, monster


def start_ordered_encounter(
    hero: Entity,
    monster: Entity,
    hero_controller: Controller,
    monster_controller: Controller,
    first_actor: Entity,
) -> Encounter:
    """Create and start an encounter with a deterministic initiative order."""
    encounter = Encounter(name="Manual Encounter", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, hero_controller)
    encounter.add_combatant(monster, monster_controller)
    encounter.roll_initiative()

    second_actor = monster if first_actor.uuid == hero.uuid else hero
    encounter.initiative_order = [first_actor.uuid, second_actor.uuid]
    encounter.current_turn_index = 0
    encounter.start_encounter()
    return encounter


def make_melee_attack_auto_hit(entity: Entity) -> UUID:
    """Add an explicit auto-hit modifier to the entity's melee attack bonus."""
    modifier = AutoHitModifier(
        name="Manual Auto Hit",
        value=AutoHitStatus.AUTOHIT,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    return entity.equipment.melee_attack_bonus.self_static.add_auto_hit_modifier(modifier)


def clear_melee_attack_modifier(entity: Entity, modifier_uuid: UUID) -> None:
    """Remove an explicit melee attack modifier from an entity."""
    entity.equipment.melee_attack_bonus.self_static.remove_modifier(modifier_uuid)


def test_first_encounter_example_prints_turn_and_combat_log(capsys) -> None:
    """The opening encounter example prints turn context and combat-log capture."""
    reset_encounter_tutorial_state()
    hero, monster = create_encounter_pair()
    hero_controller = RecordingController(source_entity_uuid=hero.uuid)
    monster_controller = PassController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_encounter(
        hero,
        monster,
        hero_controller,
        monster_controller,
        first_actor=hero,
    )

    encounter.start_turn()
    context = hero_controller.turn_start_contexts[-1]

    modifier_uuid = make_melee_attack_auto_hit(hero)
    hp_before = monster.get_hp()
    try:
        with fixed_dice_faces(12, 4):
            event = encounter.execute_action(hero.uuid, "Attack_MELEE_MAIN", 0)
    finally:
        clear_melee_attack_modifier(hero, modifier_uuid)

    assert event is not None
    assert event.damage_rolls is not None
    log_entry = encounter.combat_log[-1]

    readout_lines = [
        (
            f"encounter: {encounter.name}, "
            f"state={encounter.state.value}, "
            f"active={Encounter.get_active() is encounter}"
        ),
        (
            "initiative order: "
            f"{[Entity.get(entity_uuid).name for entity_uuid in encounter.initiative_order]}"
        ),
        (
            f"turn: round={context.round_number}, "
            f"index={context.turn_index}, "
            f"actor={hero.name}, "
            f"state={encounter.turn_state.value}"
        ),
        (
            f"turn budgets: actions={context.actions_remaining}, "
            f"bonus={context.bonus_actions_remaining}, "
            f"movement={context.movement_remaining}"
        ),
        (
            "visible enemies: "
            f"{[Entity.get(entity_uuid).name for entity_uuid in context.visible_enemies]}"
        ),
        (
            f"attack event: type={event.event_type.value}, "
            f"phase={event.phase.value}, "
            f"outcome={event.attack_outcome.value}"
        ),
        (
            f"damage: rolls={event.damage_rolls[0].results}, "
            f"total={event.damage_rolls[0].total}, "
            f"hp={hp_before}->{monster.get_hp()}"
        ),
        (
            f"combat log: entries={len(encounter.combat_log)}, "
            f"last_type={log_entry.entry_type.value}"
        ),
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "encounter: Manual Encounter, state=active, active=True",
        "initiative order: ['Manual Hero', 'Manual Skeleton']",
        "turn: round=1, index=0, actor=Manual Hero, state=in_progress",
        "turn budgets: actions=1, bonus=1, movement=30",
        "visible enemies: ['Manual Skeleton']",
        "attack event: type=attack, phase=completion, outcome=Hit",
        "damage: rolls=[4], total=6, hp=17->11",
        "combat log: entries=2, last_type=attack",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_encounter_start_and_end_set_active_table_state(capsys) -> None:
    """Starting and ending an encounter updates active state and controllers."""
    reset_encounter_tutorial_state()
    hero, monster = create_encounter_pair()
    hero_controller = RecordingController(source_entity_uuid=hero.uuid)
    monster_controller = RecordingController(source_entity_uuid=monster.uuid)

    encounter = start_ordered_encounter(
        hero,
        monster,
        hero_controller,
        monster_controller,
        first_actor=hero,
    )

    assert encounter.state == EncounterState.ACTIVE
    assert Encounter.get_active() is encounter
    assert encounter.round_number == 1
    assert encounter.turn_state == TurnState.NOT_STARTED
    assert encounter.initiative_order == [hero.uuid, monster.uuid]
    assert hero_controller.encounter_start_names == ["Manual Hero"]
    assert monster_controller.encounter_start_names == ["Manual Skeleton"]
    readout_lines = [
        (
            f"started: state={encounter.state.value}, "
            f"active={Encounter.get_active() is encounter}, "
            f"round={encounter.round_number}, "
            f"turn_state={encounter.turn_state.value}, "
            "order="
            f"{[Entity.get(entity_uuid).name for entity_uuid in encounter.initiative_order]}"
        ),
        (
            f"start callbacks: hero={hero_controller.encounter_start_names}, "
            f"monster={monster_controller.encounter_start_names}"
        ),
    ]

    end_event = encounter.end_encounter("manual scene complete")

    assert end_event.reason == "manual scene complete"
    assert encounter.state == EncounterState.ENDED
    assert Encounter.get_active() is None
    assert hero_controller.encounter_end_names == ["Manual Hero"]
    assert monster_controller.encounter_end_names == ["Manual Skeleton"]
    readout_lines.extend(
        [
            (
                f"ended: reason={end_event.reason}, "
                f"state={encounter.state.value}, "
                f"active={Encounter.get_active() is encounter}"
            ),
            (
                f"end callbacks: hero={hero_controller.encounter_end_names}, "
                f"monster={monster_controller.encounter_end_names}"
            ),
        ]
    )
    print("\n".join(readout_lines))

    expected_lines = [
        (
            "started: state=active, active=True, round=1, "
            "turn_state=not_started, order=['Manual Hero', 'Manual Skeleton']"
        ),
        "start callbacks: hero=['Manual Hero'], monster=['Manual Skeleton']",
        "ended: reason=manual scene complete, state=ended, active=False",
        "end callbacks: hero=['Manual Hero'], monster=['Manual Skeleton']",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_turn_lifecycle_builds_context_and_advances_rounds(capsys) -> None:
    """Turn start/end builds controller context and advances the round clock."""
    reset_encounter_tutorial_state()
    hero, monster = create_encounter_pair()
    hero_controller = RecordingController(source_entity_uuid=hero.uuid)
    monster_controller = RecordingController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_encounter(
        hero,
        monster,
        hero_controller,
        monster_controller,
        first_actor=hero,
    )

    start_event = encounter.start_turn()

    assert start_event is not None
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.get_current_entity() is hero

    start_context = hero_controller.turn_start_contexts[-1]
    assert start_context.entity_uuid == hero.uuid
    assert start_context.round_number == 1
    assert start_context.turn_index == 0
    assert start_context.actions_remaining == 1
    assert start_context.bonus_actions_remaining == 1
    assert start_context.movement_remaining == 30
    assert monster.uuid in start_context.visible_enemies
    readout_lines = [
        (
            f"hero turn start: event={start_event.name}, "
            f"state={encounter.turn_state.value}, "
            f"actor={encounter.get_current_entity().name}, "
            f"round={start_context.round_number}, "
            f"index={start_context.turn_index}, "
            "budgets="
            f"{start_context.actions_remaining}/{start_context.bonus_actions_remaining}/"
            f"{start_context.movement_remaining}, "
            "visible="
            f"{[Entity.get(entity_uuid).name for entity_uuid in start_context.visible_enemies]}"
        )
    ]

    end_event = encounter.end_turn()

    assert end_event is not None
    assert encounter.turn_state == TurnState.ENDED
    assert encounter.combatants[hero.uuid].has_acted_this_round
    assert encounter.combatants[hero.uuid].turn_count == 1
    assert hero_controller.turn_end_contexts[-1].entity_uuid == hero.uuid
    readout_lines.append(
        (
            f"hero turn end: event={end_event.name}, "
            f"state={encounter.turn_state.value}, "
            f"acted={encounter.combatants[hero.uuid].has_acted_this_round}, "
            f"turn_count={encounter.combatants[hero.uuid].turn_count}, "
            "callback_actor="
            f"{Entity.get(hero_controller.turn_end_contexts[-1].entity_uuid).name}"
        )
    )

    encounter.next_turn()

    assert encounter.get_current_entity() is monster
    assert encounter.current_turn_index == 1
    assert encounter.round_number == 1
    readout_lines.append(
        (
            f"next actor: actor={encounter.get_current_entity().name}, "
            f"index={encounter.current_turn_index}, "
            f"round={encounter.round_number}"
        )
    )

    encounter.end_turn()
    encounter.next_turn()

    assert encounter.get_current_entity() is hero
    assert encounter.current_turn_index == 0
    assert encounter.round_number == 2
    assert not encounter.combatants[hero.uuid].has_acted_this_round
    assert not encounter.combatants[monster.uuid].has_acted_this_round
    readout_lines.append(
        (
            f"new round: actor={encounter.get_current_entity().name}, "
            f"index={encounter.current_turn_index}, "
            f"round={encounter.round_number}, "
            f"hero_acted={encounter.combatants[hero.uuid].has_acted_this_round}, "
            f"monster_acted={encounter.combatants[monster.uuid].has_acted_this_round}"
        )
    )
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        (
            "hero turn start: event=Turn Start, state=in_progress, "
            "actor=Manual Hero, round=1, index=0, budgets=1/1/30, "
            "visible=['Manual Skeleton']"
        ),
        (
            "hero turn end: event=Turn End, state=ended, acted=yes, "
            "turn_count=1, callback_actor=Manual Hero"
        ),
        "next actor: actor=Manual Skeleton, index=1, round=1",
        "new round: actor=Manual Hero, index=0, round=2, hero_acted=no, monster_acted=no",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_automated_advance_stops_for_human_controller(capsys) -> None:
    """AI/pass turns can run forward until an external-input turn begins."""
    reset_encounter_tutorial_state()
    hero, monster = create_encounter_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        first_actor=monster,
    )

    result = encounter.advance_until_player()

    assert result.status == "waiting_for_human"
    assert result.entity_uuid == hero.uuid
    assert result.entity_name == "Manual Hero"
    assert result.round_number == 1
    assert result.turn_index == 1
    assert encounter.get_current_entity() is hero
    assert encounter.turn_state == TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 1
    readout_lines = [
        (
            f"advance result: status={result.status}, "
            f"entity={result.entity_name}, "
            f"round={result.round_number}, "
            f"index={result.turn_index}"
        ),
        (
            f"encounter state: current={encounter.get_current_entity().name}, "
            f"turn_state={encounter.turn_state.value}, "
            f"monster_turns={encounter.combatants[monster.uuid].turn_count}, "
            f"hero_turns={encounter.combatants[hero.uuid].turn_count}"
        ),
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "advance result: status=waiting_for_human, entity=Manual Hero, round=1, index=1",
        (
            "encounter state: current=Manual Hero, turn_state=in_progress, "
            "monster_turns=1, hero_turns=0"
        ),
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_execute_action_captures_combat_log_and_notifies_listener(capsys) -> None:
    """Encounter action execution records completed event logs."""
    reset_encounter_tutorial_state()
    hero, monster = create_encounter_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        first_actor=hero,
    )
    encounter.start_turn()

    listener_calls: list[tuple[int, str]] = []

    def listener(active_encounter: Encounter, index: int, entry, event) -> None:
        listener_calls.append((index, entry.entry_type.value))

    Encounter.add_combat_log_listener(listener)
    modifier_uuid = make_melee_attack_auto_hit(hero)
    initial_monster_hp = monster.get_hp()
    try:
        with fixed_dice_faces(12, 4):
            event = encounter.execute_action(hero.uuid, "Attack_MELEE_MAIN", 0)
    finally:
        clear_melee_attack_modifier(hero, modifier_uuid)
        Encounter.remove_combat_log_listener(listener)

    assert event is not None
    assert not event.canceled
    assert monster.get_hp() < initial_monster_hp
    assert encounter.combat_log
    assert listener_calls
    assert listener_calls[-1][0] == len(encounter.combat_log) - 1
    assert encounter.get_combat_log(since=listener_calls[-1][0])[0] is encounter.combat_log[-1]
    latest = encounter.combat_log[-1]
    since_entries = encounter.get_combat_log(since=listener_calls[-1][0])
    assert event.damage_rolls is not None
    readout_lines = [
        (
            f"executed attack: canceled={event.canceled}, "
            f"outcome={event.attack_outcome.value}, "
            f"damage={event.damage_rolls[0].total}, "
            f"hp={initial_monster_hp}->{monster.get_hp()}"
        ),
        (
            f"combat log capture: entries={len(encounter.combat_log)}, "
            f"latest={latest.entry_type.value}, "
            f"listener={listener_calls[-1]}, "
            f"since_count={len(since_entries)}, "
            f"since_latest={since_entries[0] is latest}"
        ),
    ]
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "executed attack: canceled=no, outcome=Hit, damage=6, hp=17->11",
        (
            "combat log capture: entries=2, latest=attack, "
            "listener=(1, 'attack'), since_count=1, since_latest=yes"
        ),
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_death_checks_end_encounter_by_faction_survival(capsys) -> None:
    """The encounter ends when only one faction has living combatants."""
    reset_encounter_tutorial_state()
    hero, monster = create_encounter_pair()
    encounter = start_ordered_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        first_actor=hero,
    )

    hp_before = monster.get_hp()
    monster.health.take_damage(monster.get_hp(), DamageType.FORCE, hero.uuid)
    death_events = encounter.check_deaths()

    assert death_events
    assert encounter.combatants[monster.uuid].is_dead
    assert "Dead" in monster.active_conditions
    assert encounter.state == EncounterState.ENDED
    assert Encounter.get_active() is None
    assert len(encounter.get_alive_combatants()) == 1
    assert encounter.get_alive_combatants()[0].entity_uuid == hero.uuid
    assert encounter.get_dead_combatants()[0].entity_uuid == monster.uuid
    readout_lines = [
        (
            f"death check: hp={hp_before}->{monster.get_hp()}, "
            f"events={len(death_events)}, "
            f"monster_dead={encounter.combatants[monster.uuid].is_dead}, "
            f"condition={'Dead' in monster.active_conditions}"
        ),
        (
            f"encounter end: state={encounter.state.value}, "
            f"active={Encounter.get_active() is encounter}, "
            "alive="
            f"{[Entity.get(combatant.entity_uuid).name for combatant in encounter.get_alive_combatants()]}, "
            "dead="
            f"{[Entity.get(combatant.entity_uuid).name for combatant in encounter.get_dead_combatants()]}"
        ),
    ]
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "death check: hp=17->0, events=1, monster_dead=yes, condition=yes",
        "encounter end: state=ended, active=no, alive=['Manual Hero'], dead=['Manual Skeleton']",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
