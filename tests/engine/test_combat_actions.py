"""Engine semantic tests for core actions and combat flow."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast
from uuid import UUID, uuid4

import pytest
from dnd.actions import (
    Attack,
    AttackEvent,
    Dash,
    Disengage,
    Jump,
    JumpEvent,
    Move,
    MovementEvent,
    Shove,
    ShoveEvent,
)
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import EquipmentConfig, Weapon
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core import dice as dice_module
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.combat_log import CombatLogEntryType
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.action_execution import MovementTerminationReason
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    AbilityName,
    DeathSaveEvent,
    DeathEvent,
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    ForcedMovementEvent,
    MovementTrajectory,
    RangeType,
    SpatialChangeEvent,
    StepMovementEvent,
    TakeDamageEvent,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.environmental_effect_runtime import materialize_spike_trap_effect
from dnd.core.life_types import LifeState
from dnd.core.creature_types import DamageType, Size
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import AdvantageStatus, BaseValue, ModifiableValue
from dnd.entity import Entity, EntityConfig
from dnd.monsters.bestiary import create_goblin, create_goblin_archer, create_skeleton
from dnd.reactions import add_opportunity_attack_handler
from tests.engine.support import (
    force_attack_crit,
    force_attack_hit,
    force_attack_miss,
    remove_attack_modifier,
    reset_combat_state,
)


def reset_core_action_state() -> None:
    """Clear global state touched by these examples."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(0, 0, 20, 20)


@contextmanager
def fixed_dice(*values: int) -> Iterator[None]:
    """Replace random dice results with a deterministic sequence.

    Args:
        *values: Values returned by successive calls to ``random.randint``. The
            final value repeats if more rolls occur than values were provided.
    """
    if not values:
        raise ValueError("fixed_dice requires at least one value")

    original_randint = dice_module.random.randint
    remaining = list(values)

    def fake_randint(_: int, __: int) -> int:
        if len(remaining) > 1:
            return remaining.pop(0)
        return remaining[0]

    dice_module.random.randint = fake_randint
    try:
        yield
    finally:
        dice_module.random.randint = original_randint


def validate_attack_declaration(attack: Attack) -> AttackEvent | None:
    """Create and validate an attack declaration event.

    Args:
        attack: Attack action being inspected before full application.

    Returns:
        Validated attack event, or ``None`` if declaration creation failed.
    """
    declaration = attack._create_declaration_event(use_register=False)
    if declaration is None:
        return None
    assert isinstance(declaration, AttackEvent)
    return attack._validate(declaration)


def strong_entity(
    name: str,
    position: tuple[int, int],
    faction: str | None,
    strength: int = 18,
    weight: int = 120,
    size: Size = Size.MEDIUM,
    uses_death_saves: bool = False,
    setup_actions: bool = True,
) -> Entity:
    """Create a deterministic configured entity for movement and shove cases."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=strength),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=14),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=3, mode="maximums")]
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight,
        size=size,
        uses_death_saves=uses_death_saves,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    if setup_actions:
        setup_standard_actions(entity)
    return entity


def test_eb_10_001_invalid_attack_cancels_before_costs() -> None:
    """EB-10-001: attack validation cancellation preserves action economy."""
    reset_core_action_state()
    attacker = create_goblin(name="Attacker", position=(2, 2), faction="heroes")
    target = create_skeleton(name="Too Far", position=(12, 2), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    starting_actions = attacker.action_economy.actions.normalized_score
    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    event = attack.apply()

    assert event is not None
    assert event.canceled is True
    assert "reach" in (event.status_message or "").lower()
    assert attacker.action_economy.actions.normalized_score == starting_actions


def test_eb_10_015_melee_reach_validation_uses_weapon_range() -> None:
    """EB-10-015: melee attack validation respects weapon reach boundaries."""
    reset_core_action_state()
    attacker = create_goblin(name="Melee Attacker", position=(5, 5), faction="heroes")
    adjacent_target = create_skeleton(name="Adjacent Target", position=(6, 5), faction="monsters")
    far_target = create_skeleton(name="Far Target", position=(7, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    adjacent_attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=adjacent_target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    adjacent_event = validate_attack_declaration(adjacent_attack)

    assert adjacent_event is not None
    assert adjacent_event.canceled is False
    assert adjacent_event.phase == EventPhase.EXECUTION
    assert adjacent_event.range is not None
    assert adjacent_event.range.type == RangeType.REACH
    assert adjacent_event.range.normal == 5
    assert adjacent_event.is_long_range is False

    actions_before = attacker.action_economy.actions.normalized_score
    far_attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=far_target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    far_event = validate_attack_declaration(far_attack)

    assert far_event is not None
    assert far_event.canceled is True
    assert "reach" in (far_event.status_message or "").lower()
    assert attacker.action_economy.actions.normalized_score == actions_before


def test_eb_10_020_diagonal_adjacency_counts_as_five_foot_threat() -> None:
    """EB-10-020: diagonal adjacency is melee reach and threat."""
    reset_core_action_state()
    watcher = create_skeleton(name="Watcher", position=(5, 5), faction="monsters")
    diagonal_mover = create_goblin(name="Diagonal Mover", position=(6, 6), faction="heroes")
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)

    assert watcher.senses.get_feet_distance(diagonal_mover.position) == 5
    assert diagonal_mover.position in watcher.senses.get_threathened_positions()
    assert diagonal_mover.is_threatened() is True

    diagonal_attack = Attack(
        source_entity_uuid=watcher.uuid,
        target_entity_uuid=diagonal_mover.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )
    validated = validate_attack_declaration(diagonal_attack)

    assert validated is not None
    assert validated.canceled is False
    assert validated.range is not None
    assert validated.range.type == RangeType.REACH
    assert validated.range.normal == 5

    hp_before = diagonal_mover.get_hp()
    hit_modifier = force_attack_hit(watcher)

    with fixed_dice(10, 4):
        move_event = Move(source_entity_uuid=diagonal_mover.uuid, end_position=(8, 8)).apply()

    remove_attack_modifier(watcher, hit_modifier)

    assert move_event is not None
    assert diagonal_mover.position == (8, 8)
    assert diagonal_mover.get_hp() < hp_before
    assert watcher.action_economy.reactions.normalized_score == 0
    assert any(
        event.name == "Opportunity Attack"
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
    )


def test_eb_10_002_attack_hit_rolls_damage_and_consumes_action() -> None:
    """EB-10-002: a successful weapon attack rolls damage and spends the action."""
    reset_core_action_state()
    attacker = create_goblin(name="Attacker", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Target", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    target_hp_before = target.get_hp()
    hit_modifier = force_attack_hit(attacker)

    with fixed_dice(10, 4):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    remove_attack_modifier(attacker, hit_modifier)

    assert event is not None
    assert event.phase == EventPhase.COMPLETION
    assert event.attack_outcome is not None
    assert event.damage_rolls
    assert target.get_hp() < target_hp_before
    assert attacker.action_economy.actions.normalized_score == 0
    assert EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
    assert EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)


def test_attack_declaration_handlers_dispatch_once_per_attack() -> None:
    """Validation updates must not republish the attack declaration phase."""
    reset_core_action_state()
    attacker = create_goblin(name="Attacker", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Target", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)
    declaration_calls = 0

    def count_declaration(event: Event, _: UUID) -> Event:
        nonlocal declaration_calls
        declaration_calls += 1
        return event

    attacker.add_event_handler(
        EventHandler(
            source_entity_uuid=attacker.uuid,
            name="Count attack declarations",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.DECLARATION,
                    event_source_entity_uuid=attacker.uuid,
                )
            ],
            event_processor=count_declaration,
        )
    )
    miss_modifier = force_attack_miss(attacker)

    with fixed_dice(10):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    remove_attack_modifier(attacker, miss_modifier)

    assert event is not None
    assert event.phase == EventPhase.COMPLETION
    assert declaration_calls == 1


def test_damage_declaration_cancellation_prevents_application() -> None:
    """A declaration veto must stop the authoritative damage operation."""
    reset_core_action_state()
    source = create_goblin(
        name="Damage Source",
        position=(5, 5),
        faction="heroes",
    )
    target = create_skeleton(
        name="Damage Target",
        position=(6, 5),
        faction="monsters",
    )
    hp_before = target.get_hp()

    def cancel_damage(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="Damage vetoed at declaration")

    target.add_event_handler(
        EventHandler(
            source_entity_uuid=target.uuid,
            name="Veto damage declaration",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.DECLARATION,
                    event_target_entity_uuid=target.uuid,
                )
            ],
            event_processor=cancel_damage,
        )
    )

    applied = target.receive_damage(
        5,
        DamageType.SLASHING,
        source.uuid,
    )

    assert applied == 0
    assert target.get_hp() == hp_before


def test_movement_declaration_handlers_dispatch_once_per_move() -> None:
    """Path validation must not republish the movement declaration phase."""
    reset_core_action_state()
    mover = strong_entity(
        name="Mover",
        position=(5, 5),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)
    declaration_calls = 0
    execution_calls = 0

    def count_declaration(event: Event, _: UUID) -> Event:
        nonlocal declaration_calls
        declaration_calls += 1
        return event

    def count_execution(event: Event, _: UUID) -> Event:
        nonlocal execution_calls
        execution_calls += 1
        return event

    mover.add_event_handler(
        EventHandler(
            source_entity_uuid=mover.uuid,
            name="Count movement declarations",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.MOVEMENT,
                    event_phase=EventPhase.DECLARATION,
                    event_source_entity_uuid=mover.uuid,
                )
            ],
            event_processor=count_declaration,
        )
    )
    mover.add_event_handler(
        EventHandler(
            source_entity_uuid=mover.uuid,
            name="Count movement executions",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.MOVEMENT,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=mover.uuid,
                )
            ],
            event_processor=count_execution,
        )
    )

    event = Move(
        source_entity_uuid=mover.uuid,
        end_position=(6, 5),
    ).apply()

    assert event is not None
    assert event.phase is EventPhase.COMPLETION
    assert declaration_calls == 1
    assert execution_calls == 1


def test_eb_10_003_critical_hit_doubles_weapon_damage_dice() -> None:
    """EB-10-003: critical weapon hits roll the weapon damage dice twice."""
    reset_core_action_state()
    attacker = create_goblin(name="Attacker", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Target", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    hit_modifier = force_attack_hit(attacker)
    crit_modifier = force_attack_crit(attacker)

    with fixed_dice(10, 3, 4):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    remove_attack_modifier(attacker, hit_modifier)
    remove_attack_modifier(attacker, crit_modifier)

    assert event is not None
    assert event.attack_outcome is not None
    assert event.attack_outcome.value == "Crit"
    assert event.damage_rolls
    assert event.damage_rolls[0].results == [3, 4]


def test_eb_10_004_move_consumes_movement_per_step_and_records_step_events() -> None:
    """EB-10-004: movement walks cell by cell and emits STEP_MOVEMENT events."""
    reset_core_action_state()
    mover = create_goblin(name="Mover", position=(5, 5), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)

    movement_before = mover.action_economy.movement.normalized_score
    event = Move(source_entity_uuid=mover.uuid, end_position=(5, 8)).apply()

    assert isinstance(event, MovementEvent)
    assert event.phase == EventPhase.COMPLETION
    assert mover.position == (5, 8)
    assert mover.action_economy.movement.normalized_score == movement_before - 15
    completed_steps = [
        step
        for step in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if (
            isinstance(step, StepMovementEvent)
            and step.source_entity_uuid == mover.uuid
            and step.phase == EventPhase.COMPLETION
        )
    ]
    assert len(completed_steps) == 3
    assert event.trajectory is MovementTrajectory.PATH
    assert all(step.trajectory is MovementTrajectory.PATH for step in completed_steps)


def test_eb_10_005_opportunity_attack_uses_reaction_on_step_movement() -> None:
    """EB-10-005: leaving hostile reach triggers a reaction melee attack."""
    reset_core_action_state()
    attacker = create_skeleton(name="Watcher", position=(5, 5), faction="monsters")
    mover = create_goblin(name="Mover", position=(5, 6), faction="heroes")
    add_opportunity_attack_handler(attacker)
    Entity.update_all_entities_senses(max_distance=20)

    mover_hp_before = mover.get_hp()
    hit_modifier = force_attack_hit(attacker)

    with fixed_dice(10, 4):
        move_event = Move(source_entity_uuid=mover.uuid, end_position=(5, 10)).apply()

    remove_attack_modifier(attacker, hit_modifier)

    assert move_event is not None
    assert mover.get_hp() < mover_hp_before
    assert attacker.action_economy.reactions.normalized_score == 0
    attack_events = EventQueue.get_events_by_type(EventType.ATTACK)
    assert any(event.name == "Opportunity Attack" for event in attack_events)


def test_eb_10_017_lethal_opportunity_attack_stops_before_leaving_reach() -> None:
    """EB-10-017: lethal OA stops movement before the provoking step completes."""
    reset_core_action_state()
    watcher = create_skeleton(name="Watcher", position=(5, 5), faction="monsters")
    mover = create_goblin(name="Fragile Mover", position=(5, 6), faction="heroes")
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)

    hp_before = mover.get_hp()
    hit_modifier = force_attack_hit(watcher)
    crit_modifier = force_attack_crit(watcher)

    with fixed_dice(10, 6, 6):
        move_event = Move(source_entity_uuid=mover.uuid, end_position=(5, 10)).apply()

    remove_attack_modifier(watcher, hit_modifier)
    remove_attack_modifier(watcher, crit_modifier)

    assert move_event is not None
    assert move_event.phase == EventPhase.COMPLETION
    assert mover.health.life_state is LifeState.DEAD
    assert mover.get_hp() <= 0
    assert hp_before - mover.get_hp() >= hp_before
    assert mover.position == (5, 6)
    assert move_event.end_position == (5, 6)
    assert "partial" in (move_event.status_message or "").lower()
    assert watcher.action_economy.reactions.normalized_score == 0

    effect_steps = [
        step
        for step in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if isinstance(step, StepMovementEvent)
        and step.source_entity_uuid == mover.uuid
        and step.phase == EventPhase.EFFECT
    ]
    completed_steps = [
        step
        for step in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if isinstance(step, StepMovementEvent)
        and step.source_entity_uuid == mover.uuid
        and step.phase == EventPhase.COMPLETION
    ]
    assert len({step.lineage_uuid for step in effect_steps}) == 1
    assert all(step.from_position == (5, 6) for step in effect_steps)
    assert all(step.to_position == (5, 7) for step in effect_steps)
    assert len(completed_steps) == 1
    assert completed_steps[0].committed is False


def test_eb_10_006_disengage_prevents_opportunity_attack() -> None:
    """EB-10-006: Disengage applies a condition that suppresses OA handlers."""
    reset_core_action_state()
    attacker = create_skeleton(name="Watcher", position=(5, 5), faction="monsters")
    mover = create_goblin(name="Mover", position=(5, 6), faction="heroes")
    add_opportunity_attack_handler(attacker)
    Entity.update_all_entities_senses(max_distance=20)

    disengage_event = Disengage(source_entity_uuid=mover.uuid).apply()
    mover_hp_before = mover.get_hp()
    hit_modifier = force_attack_hit(attacker)

    with fixed_dice(10, 4):
        move_event = Move(source_entity_uuid=mover.uuid, end_position=(5, 10)).apply()

    remove_attack_modifier(attacker, hit_modifier)

    assert disengage_event is not None
    assert "Disengaging" in mover.active_conditions
    assert move_event is not None
    assert mover.get_hp() == mover_hp_before
    assert attacker.action_economy.reactions.normalized_score == 1


def test_eb_10_014_opportunity_attack_reaction_limits_repeat_triggers() -> None:
    """EB-10-014: one reaction only pays for one opportunity attack."""
    reset_core_action_state()
    watcher = create_skeleton(name="Watcher", position=(5, 5), faction="monsters")
    first_mover = create_goblin(name="First Mover", position=(5, 6), faction="heroes")
    second_mover = create_goblin(name="Second Mover", position=(6, 5), faction="heroes")
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)

    first_hp_before = first_mover.get_hp()
    second_hp_before = second_mover.get_hp()
    hit_modifier = force_attack_hit(watcher)

    with fixed_dice(10, 4, 10, 4):
        first_move = Move(source_entity_uuid=first_mover.uuid, end_position=(5, 10)).apply()
        second_move = Move(source_entity_uuid=second_mover.uuid, end_position=(10, 5)).apply()

    remove_attack_modifier(watcher, hit_modifier)

    assert first_move is not None
    assert second_move is not None
    assert first_mover.get_hp() < first_hp_before
    assert second_mover.get_hp() == second_hp_before
    assert watcher.action_economy.reactions.normalized_score == 0

    completed_oas = [
        event
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
        if event.name == "Opportunity Attack" and event.phase == EventPhase.COMPLETION
    ]
    assert len(completed_oas) == 1


def test_eb_10_007_shove_forced_movement_does_not_trigger_opportunity_attack() -> None:
    """EB-10-007: shove push uses FORCED_MOVEMENT, not STEP_MOVEMENT."""
    reset_core_action_state()
    shover = strong_entity("Shover", (2, 2), "heroes", strength=18)
    target = strong_entity("Ally", (3, 2), "heroes", strength=12, weight=100)
    watcher = create_skeleton(name="Watcher", position=(4, 3), faction="monsters")
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)

    target_hp_before = target.get_hp()
    hit_modifier = force_attack_hit(watcher)

    with fixed_dice(10, 4):
        event = Shove(
            source_entity_uuid=shover.uuid,
            target_entity_uuid=target.uuid,
        ).apply()

    remove_attack_modifier(watcher, hit_modifier)

    assert isinstance(event, ShoveEvent)
    assert event.contest_success is True
    assert target.position != (3, 2)
    assert target.get_hp() == target_hp_before
    assert watcher.action_economy.reactions.normalized_score == 1
    assert EventQueue.get_events_by_type(EventType.FORCED_MOVEMENT)

    assert event.combat_log is not None
    forced_movement_logs = [
        entry
        for entry in event.combat_log.sub_entries
        if entry.data.get("type") == "forced_movement"
    ]
    assert len(forced_movement_logs) == 1
    forced_log = forced_movement_logs[0]
    assert forced_log.data["cause"] == "shove"
    assert forced_log.data["start_position"] == [3, 2]
    assert forced_log.data["end_position"] == list(target.position)
    assert "(3, 2) →" in forced_log.verbose
    assert f"→ {target.position}" in forced_log.verbose


def test_forced_movement_declaration_cancellation_prevents_displacement() -> None:
    """A declaration veto must stop the authoritative forced movement."""
    reset_core_action_state()
    shover = strong_entity(
        name="Shove Source",
        position=(5, 5),
        faction="heroes",
        strength=18,
    )
    target = strong_entity(
        name="Shove Target",
        position=(6, 5),
        faction="heroes",
        strength=10,
        weight=100,
    )
    Entity.update_all_entities_senses(max_distance=20)
    start_position = target.position

    def cancel_forced_movement(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="Forced movement vetoed at declaration")

    target.add_event_handler(
        EventHandler(
            source_entity_uuid=target.uuid,
            name="Veto forced movement declaration",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.FORCED_MOVEMENT,
                    event_phase=EventPhase.DECLARATION,
                    event_target_entity_uuid=target.uuid,
                )
            ],
            event_processor=cancel_forced_movement,
        )
    )

    shove_event = Shove(
        source_entity_uuid=shover.uuid,
        target_entity_uuid=target.uuid,
    ).apply()

    assert isinstance(shove_event, ShoveEvent)
    assert shove_event.contest_success is True
    assert target.position == start_position


def test_eb_10_021_forced_movement_traverses_terrain_without_step_costs() -> None:
    """EB-10-021: forced movement traverses terrain without voluntary steps."""
    reset_core_action_state()
    shover = strong_entity(name="Shove Ally", position=(5, 5), faction="heroes", strength=18)
    target = strong_entity(name="Pushed Ally", position=(6, 5), faction="heroes", strength=10)
    Entity.update_all_entities_senses(max_distance=20)

    materialize_spike_trap_effect({(7, 5), (8, 5)})
    cursor = EventQueue.event_cursor()
    hp_before = target.get_hp()
    target_movement_before = target.action_economy.movement.normalized_score

    with fixed_dice_faces(2, 2, 2, 2):
        shove_event = Shove(source_entity_uuid=shover.uuid, target_entity_uuid=target.uuid).apply()

    indexed_events = list(EventQueue.iter_events_since(cursor))
    new_events = [event for _, event in indexed_events]
    forced_completions = [
        event
        for event in new_events
        if isinstance(event, ForcedMovementEvent)
        and event.phase == EventPhase.COMPLETION
    ]
    entered_effects = [
        event
        for event in new_events
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_ENTITY_ENTERED
        and event.phase == EventPhase.EFFECT
        and event.entity_uuid == target.uuid
    ]
    entered_effect_positions = [event.position for event in entered_effects]
    damage_completions = [
        event
        for event in new_events
        if isinstance(event, TakeDamageEvent)
        and event.phase == EventPhase.COMPLETION
    ]

    assert isinstance(shove_event, ShoveEvent)
    assert shove_event.canceled is False
    assert shove_event.push_distance == 10
    assert shove_event.end_position == (8, 5)
    assert target.position == (8, 5)
    assert shover.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == target_movement_before

    assert len(forced_completions) == 1
    forced_event = forced_completions[0]
    assert forced_event.start_position == (6, 5)
    assert forced_event.end_position == (8, 5)
    assert forced_event.actual_distance == 10
    assert not any(event.event_type == EventType.STEP_MOVEMENT for event in new_events)
    assert entered_effect_positions == [(7, 5), (8, 5)]

    assert len(damage_completions) == 2
    forced_completion_index = next(
        index for index, event in indexed_events if event.uuid == forced_event.uuid
    )
    damage_event_uuids = {damage_event.uuid for damage_event in damage_completions}
    damage_indexes = [
        index for index, event in indexed_events if event.uuid in damage_event_uuids
    ]
    assert max(damage_indexes) < forced_completion_index

    assert [damage_event.total_damage for damage_event in damage_completions] == [4, 4]
    assert [damage_event.final_damage for damage_event in damage_completions] == [4, 4]
    entered_parents = [
        EventQueue.get_event_by_uuid(entered_event.parent_event)
        if entered_event.parent_event is not None
        else None
        for entered_event in entered_effects
    ]
    assert all(
        parent is not None
        and parent.lineage_uuid == forced_event.lineage_uuid
        for parent in entered_parents
    )
    assert {
        damage_event.parent_lineage
        for damage_event in damage_completions
    } == {
        entered_event.lineage_uuid
        for entered_event in entered_effects
    }
    assert forced_event.combat_log is not None
    assert len(forced_event.combat_log.sub_entries) == 2
    assert target.get_hp() == hp_before - 8


def test_eb_10_022_shove_uses_videogame_bonus_action_forced_movement() -> None:
    """EB-10-022: Shove is a bonus-action videogame forced movement."""
    reset_core_action_state()
    shover = strong_entity(name="BG3 Shove Actor", position=(5, 5), faction="heroes", strength=18)
    target = strong_entity(name="BG3 Shove Target", position=(6, 5), faction="monsters", strength=10)
    Entity.update_all_entities_senses(max_distance=20)

    actions_before = shover.action_economy.actions.normalized_score
    bonus_actions_before = shover.action_economy.bonus_actions.normalized_score
    target_passive = max(target.passive_skill("athletics"), target.passive_skill("acrobatics"))

    with fixed_dice(15):
        event = cast(
            ShoveEvent,
            Shove(source_entity_uuid=shover.uuid, target_entity_uuid=target.uuid).apply(),
        )

    assert event is not None
    assert event.canceled is False
    assert event.is_ally is False
    assert event.dice_roll is not None
    assert event.dice_roll.total >= target_passive
    assert event.target_passive == target_passive
    assert event.target_resistance_skill == "acrobatics"
    assert event.contest_success is True
    assert event.push_distance == 10
    assert event.end_position == (8, 5)
    assert target.position == (8, 5)
    assert "Prone" not in target.active_conditions
    assert shover.action_economy.actions.normalized_score == actions_before
    assert shover.action_economy.bonus_actions.normalized_score == bonus_actions_before - 1


def test_eb_10_024_bg3_shove_range_uses_strength_and_target_weight() -> None:
    """EB-10-024: BG3 shove capacity and range use kilograms internally."""
    reset_core_action_state()
    shover = strong_entity(
        name="Strength 14 Shove Actor",
        position=(5, 5),
        faction="heroes",
        strength=14,
    )
    light_target = strong_entity(
        name="Light Target",
        position=(6, 5),
        faction="monsters",
        weight=40,
    )
    humanoid_target = strong_entity(
        name="Humanoid Target",
        position=(6, 6),
        faction="monsters",
        weight=150,
    )
    stronger_shover = strong_entity(
        name="Strength 18 Shove Actor",
        position=(5, 6),
        faction="heroes",
        strength=18,
    )

    assert Shove.get_max_shove_weight(shover) == 370
    assert Shove.get_push_distance(shover, light_target) == 10
    assert Shove.get_push_distance(shover, humanoid_target) == 5
    assert Shove.get_push_distance(stronger_shover, humanoid_target) == 10


def test_eb_10_008_dash_damage_healing_and_death_use_events() -> None:
    """EB-10-008: core HP changes and Dash are event-backed state changes."""
    reset_core_action_state()
    hero = strong_entity("Hero", (5, 5), "heroes")
    enemy = create_skeleton(name="Enemy", position=(6, 5), faction="monsters")

    movement_before = hero.action_economy.movement.normalized_score
    dash_event = Dash(source_entity_uuid=hero.uuid).apply()

    assert dash_event is not None
    assert "Dashing" in hero.active_conditions
    assert hero.action_economy.actions.normalized_score == 0
    assert hero.action_economy.movement.normalized_score > movement_before

    hp_before_damage = hero.get_hp()
    damage_taken = hero.receive_damage(
        amount=7,
        damage_type=DamageType.SLASHING,
        source_entity_uuid=enemy.uuid,
    )
    healing_done = hero.receive_healing(amount=3, source_entity_uuid=hero.uuid)

    assert damage_taken == 7
    assert healing_done == 3
    assert hero.get_hp() == hp_before_damage - 4
    assert EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
    assert EventQueue.get_events_by_type(EventType.HEAL)

    fatal_target = create_goblin(name="Fatal Target", position=(8, 8), faction="monsters")
    fatal_target.receive_damage(
        amount=fatal_target.get_hp() + 5,
        damage_type=DamageType.SLASHING,
        source_entity_uuid=hero.uuid,
    )

    assert fatal_target.health.life_state is LifeState.DEAD
    assert EventQueue.get_events_by_type(EventType.DEATH)


def test_eb_10_023_default_zero_hp_uses_monster_style_death() -> None:
    """EB-10-023: default 0 HP still uses monster-style immediate death."""
    reset_core_action_state()
    monster_style = strong_entity("Monster-Style Hero", (5, 5), "heroes")
    enemy = create_skeleton(name="Enemy", position=(6, 5), faction="monsters")

    hp_before = monster_style.get_normal_hp()
    d20_events_before = len(EventQueue.get_events_by_type(EventType.D20_ROLL_RESULT))
    damage_taken = monster_style.receive_damage(
        amount=hp_before,
        damage_type=DamageType.SLASHING,
        source_entity_uuid=enemy.uuid,
    )
    death_events = [
        event for event in EventQueue.get_events_by_type(EventType.DEATH)
        if isinstance(event, DeathEvent)
        and event.target_entity_uuid == monster_style.uuid
        and event.phase == EventPhase.COMPLETION
    ]

    assert damage_taken == hp_before
    assert monster_style.get_normal_hp() == 0
    assert monster_style.health.life_state is LifeState.DEAD
    assert "Incapacitated" not in monster_style.active_conditions
    assert "Unconscious" not in monster_style.active_conditions
    assert monster_style.action_economy.action_permission.normalized_score == 0
    assert death_events
    assert death_events[-1].final_hp == 0
    assert not monster_style.uses_death_saves
    assert monster_style.death_save_successes == 0
    assert monster_style.death_save_failures == 0
    assert not monster_style.is_stable

    with fixed_dice(20):
        turn_start = monster_style.on_turn_start()

    assert turn_start.phase == EventPhase.COMPLETION
    assert len(EventQueue.get_events_by_type(EventType.D20_ROLL_RESULT)) == d20_events_before
    assert monster_style.get_normal_hp() == 0
    assert monster_style.health.life_state is LifeState.DEAD


def test_eb_10_025_player_style_death_saves_roll_at_turn_start() -> None:
    """EB-10-025: opted-in entities follow SRD death-save turn flow."""
    reset_core_action_state()
    hero = strong_entity("Dying Hero", (5, 5), "heroes", uses_death_saves=True)
    enemy = create_skeleton(name="Enemy", position=(6, 5), faction="monsters")

    hp_before = hero.get_normal_hp()
    damage_taken = hero.receive_damage(
        amount=hp_before,
        damage_type=DamageType.SLASHING,
        source_entity_uuid=enemy.uuid,
    )

    assert damage_taken == hp_before
    assert hero.get_normal_hp() == 0
    assert not hero.has_hp
    assert hero.is_dying
    assert hero.health.life_state is LifeState.DYING
    assert "Unconscious" not in hero.active_conditions
    assert "Incapacitated" not in hero.active_conditions
    assert hero.action_economy.action_permission.normalized_score == 0
    assert hero.senses.visual_access.normalized_score == 0
    assert not hero.is_stable

    with fixed_dice(9):
        hero.on_turn_start(round_number=1, turn_index=0)

    assert hero.death_save_failures == 1
    assert hero.death_save_successes == 0
    assert hero.health.life_state is LifeState.DYING

    with fixed_dice(10):
        hero.on_turn_start(round_number=2, turn_index=0)

    assert hero.death_save_failures == 1
    assert hero.death_save_successes == 1
    assert hero.health.life_state is LifeState.DYING

    with fixed_dice(1):
        hero.on_turn_start(round_number=3, turn_index=0)

    death_save_events = [
        event for event in EventQueue.get_events_by_type(EventType.DEATH_SAVE)
        if isinstance(event, DeathSaveEvent)
        and event.entity_uuid == hero.uuid
        and event.phase == EventPhase.COMPLETION
    ]
    assert len(death_save_events) == 3
    assert death_save_events[-1].natural_roll == 1
    assert death_save_events[-1].failures == 3
    assert death_save_events[-1].died
    assert death_save_events[-1].combat_log is not None
    assert (
        death_save_events[-1].combat_log.entry_type
        is CombatLogEntryType.DEATH_SAVE
    )
    assert death_save_events[-1].combat_log.data["save_kind"] == "death"
    assert hero.health.life_state is LifeState.DEAD
    assert "Unconscious" not in hero.active_conditions


def test_eb_10_026_player_style_stabilization_healing_and_massive_damage() -> None:
    """EB-10-026: player-style death saves stabilize, heal, and still die outright."""
    reset_core_action_state()
    enemy = create_skeleton(name="Enemy", position=(6, 5), faction="monsters")

    natural_twenty = strong_entity("Natural Twenty Hero", (5, 5), "heroes", uses_death_saves=True)
    natural_twenty.receive_damage(
        amount=natural_twenty.get_normal_hp(),
        damage_type=DamageType.SLASHING,
        source_entity_uuid=enemy.uuid,
    )
    with fixed_dice(20):
        natural_twenty.on_turn_start(round_number=1, turn_index=0)
    assert natural_twenty.get_normal_hp() == 1
    assert natural_twenty.has_hp
    assert natural_twenty.health.life_state is LifeState.ALIVE
    assert "Unconscious" not in natural_twenty.active_conditions
    assert natural_twenty.death_save_successes == 0
    assert natural_twenty.death_save_failures == 0

    stable_hero = strong_entity("Stable Hero", (7, 5), "heroes", uses_death_saves=True)
    stable_hero.receive_damage(
        amount=stable_hero.get_normal_hp(),
        damage_type=DamageType.SLASHING,
        source_entity_uuid=enemy.uuid,
    )
    with fixed_dice(10):
        stable_hero.on_turn_start(round_number=1, turn_index=0)
        stable_hero.on_turn_start(round_number=2, turn_index=0)
        stable_hero.on_turn_start(round_number=3, turn_index=0)
    assert stable_hero.is_stable
    assert stable_hero.death_save_successes == 0
    assert stable_hero.death_save_failures == 0
    assert stable_hero.health.life_state is LifeState.STABLE
    assert "Unconscious" not in stable_hero.active_conditions
    assert stable_hero.action_economy.action_permission.normalized_score == 0

    death_save_count = len(EventQueue.get_events_by_type(EventType.DEATH_SAVE))
    with fixed_dice(1):
        stable_hero.on_turn_start(round_number=4, turn_index=0)
    assert len(EventQueue.get_events_by_type(EventType.DEATH_SAVE)) == death_save_count

    stable_hero.receive_damage(
        amount=1,
        damage_type=DamageType.SLASHING,
        source_entity_uuid=enemy.uuid,
        critical_hit=True,
    )
    assert not stable_hero.is_stable
    assert stable_hero.death_save_failures == 2
    assert stable_hero.health.life_state is LifeState.DYING

    healed = stable_hero.receive_healing(1, source_entity_uuid=stable_hero.uuid)
    assert healed == 1
    assert stable_hero.get_normal_hp() == 1
    assert stable_hero.health.life_state is LifeState.ALIVE
    assert "Unconscious" not in stable_hero.active_conditions
    assert stable_hero.death_save_successes == 0
    assert stable_hero.death_save_failures == 0

    massive_target = strong_entity("Massive Damage Hero", (9, 5), "heroes", uses_death_saves=True)
    massive_target.receive_damage(
        amount=massive_target.get_normal_hp() + massive_target.get_max_hp(),
        damage_type=DamageType.SLASHING,
        source_entity_uuid=enemy.uuid,
    )
    assert massive_target.health.life_state is LifeState.DEAD
    assert "Unconscious" not in massive_target.active_conditions


def test_eb_10_016_mixed_weapon_damage_applies_resistance_per_component() -> None:
    """EB-10-016: mixed attack damage applies resistance per damage type."""
    reset_core_action_state()
    attacker = create_goblin(name="Elemental Attacker", position=(5, 5), faction="heroes")
    target_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=10),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")],
            resistances=[DamageType.SLASHING],
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=(6, 5),
        faction="monsters",
    )
    target = Entity.create(source_entity_uuid=uuid4(), name="Slash Resistant Target", config=target_config)
    setup_standard_actions(target)

    weapon = attacker.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    assert isinstance(weapon, Weapon)
    weapon.extra_damage_dices.append(6)
    weapon.extra_damage_dices_numbers.append(1)
    weapon.extra_damage_bonus.append(
        ModifiableValue.create(source_entity_uuid=attacker.uuid, value_name="Fire Bonus", base_value=0)
    )
    weapon.extra_damage_type.append(DamageType.FIRE)
    Entity.update_all_entities_senses(max_distance=20)

    hp_before = target.get_hp()
    hit_modifier = force_attack_hit(attacker)

    with fixed_dice(10, 4, 6):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    remove_attack_modifier(attacker, hit_modifier)

    assert event is not None
    assert event.damage_rolls is not None
    assert len(event.damage_rolls) == 2
    assert [roll.total for roll in event.damage_rolls] == [6, 6]
    assert [damage.damage_type for damage in event.damages or []] == [
        DamageType.SLASHING,
        DamageType.FIRE,
    ]
    assert hp_before - target.get_hp() == 9
    assert event.total_damage == 9
    assert event.combat_log is not None
    assert event.combat_log.data["total_damage"] == 9
    assert "{red:9} damage" in event.combat_log.compact
    take_damage_events = [
        event
        for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
        if isinstance(event, TakeDamageEvent)
    ]
    assert take_damage_events[-1].final_damage == 9


def test_eb_10_019_mixed_weapon_damage_applies_vulnerability_and_immunity_per_component() -> None:
    """EB-10-019: mixed damage vulnerability and immunity apply per damage type."""

    def run_mixed_attack(
        name: str,
        vulnerabilities: list[DamageType] | None = None,
        immunities: list[DamageType] | None = None,
    ) -> tuple[int, AttackOutcome, list[int]]:
        reset_core_action_state()
        attacker = create_goblin(name="Elemental Attacker", position=(5, 5), faction="heroes")
        target_config = EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=10),
                constitution=AbilityConfig(ability_score=10),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=10),
                charisma=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(
                hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")],
                vulnerabilities=vulnerabilities or [],
                immunities=immunities or [],
            ),
            equipment=EquipmentConfig(),
            action_economy=ActionEconomyConfig(),
            proficiency_bonus=2,
            position=(6, 5),
            faction="monsters",
        )
        target = Entity.create(source_entity_uuid=uuid4(), name=name, config=target_config)
        setup_standard_actions(target)

        weapon = attacker.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
        assert isinstance(weapon, Weapon)
        weapon.extra_damage_dices.append(6)
        weapon.extra_damage_dices_numbers.append(1)
        weapon.extra_damage_bonus.append(
            ModifiableValue.create(source_entity_uuid=attacker.uuid, value_name="Fire Bonus", base_value=0)
        )
        weapon.extra_damage_type.append(DamageType.FIRE)
        Entity.update_all_entities_senses(max_distance=20)

        hp_before = target.get_hp()
        hit_modifier = force_attack_hit(attacker)

        with fixed_dice(10, 4, 6):
            event = Attack(
                source_entity_uuid=attacker.uuid,
                target_entity_uuid=target.uuid,
                weapon_slot=WeaponSlot.MELEE_MAIN,
            ).apply()

        remove_attack_modifier(attacker, hit_modifier)

        assert event is not None
        assert event.attack_outcome is not None
        assert event.damage_rolls is not None
        assert [roll.total for roll in event.damage_rolls] == [6, 6]
        assert [damage.damage_type for damage in event.damages or []] == [
            DamageType.SLASHING,
            DamageType.FIRE,
        ]
        return hp_before - target.get_hp(), event.attack_outcome, [roll.total for roll in event.damage_rolls]

    vulnerable_damage, vulnerable_outcome, vulnerable_rolls = run_mixed_attack(
        "Slash Vulnerable Target",
        vulnerabilities=[DamageType.SLASHING],
    )
    assert vulnerable_outcome == AttackOutcome.HIT
    assert vulnerable_rolls == [6, 6]
    assert vulnerable_damage == 18

    immune_damage, immune_outcome, immune_rolls = run_mixed_attack(
        "Slash Immune Target",
        immunities=[DamageType.SLASHING],
    )
    assert immune_outcome == AttackOutcome.HIT
    assert immune_rolls == [6, 6]
    assert immune_damage == 6


def test_eb_10_009_attack_target_context_is_temporary_on_miss() -> None:
    """EB-10-009: attack cross-target context is cleaned even without damage."""
    reset_core_action_state()
    attacker = create_goblin(name="Attacker", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Target", position=(6, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    miss_modifier = force_attack_miss(attacker)

    with fixed_dice(10):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    remove_attack_modifier(attacker, miss_modifier)

    assert event is not None
    assert event.attack_outcome is not None
    assert event.attack_outcome.value == "Miss"
    assert attacker.target_entity_uuid is None
    assert target.target_entity_uuid is None


def test_attack_restores_preexisting_cross_target_context() -> None:
    """Attack resolution restores both entities' prior contextual targets."""
    reset_core_action_state()
    attacker = create_goblin(name="Attacker", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Target", position=(6, 5), faction="monsters")
    prior_attacker_target = create_skeleton(
        name="Prior attacker target",
        position=(7, 5),
        faction="monsters",
    )
    prior_target_target = create_goblin(
        name="Prior target target",
        position=(5, 6),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)
    attacker.set_target_entity(prior_attacker_target.uuid)
    target.set_target_entity(prior_target_target.uuid)
    miss_modifier = force_attack_miss(attacker)

    with fixed_dice(10):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    remove_attack_modifier(attacker, miss_modifier)

    assert event is not None
    assert event.attack_outcome is AttackOutcome.MISS
    assert attacker.target_entity_uuid == prior_attacker_target.uuid
    assert target.target_entity_uuid == prior_target_target.uuid


def test_get_damages_restores_preexisting_target_context() -> None:
    """Direct damage construction must not erase an outer target binding."""
    reset_core_action_state()
    attacker = create_goblin(name="Attacker", position=(5, 5), faction="heroes")
    requested_target = create_skeleton(
        name="Requested target",
        position=(6, 5),
        faction="monsters",
    )
    prior_target = create_skeleton(
        name="Prior target",
        position=(7, 5),
        faction="monsters",
    )
    attacker.set_target_entity(prior_target.uuid)

    damages = attacker.get_damages(
        WeaponSlot.MELEE_MAIN,
        requested_target.uuid,
    )

    assert damages
    assert attacker.target_entity_uuid == prior_target.uuid


def test_attack_restores_preexisting_context_when_resolution_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Context restoration is exception-safe, not tied to individual returns."""
    reset_core_action_state()
    attacker = create_goblin(name="Attacker", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Target", position=(6, 5), faction="monsters")
    prior_attacker_target = create_skeleton(
        name="Prior attacker target",
        position=(7, 5),
        faction="monsters",
    )
    prior_target_target = create_goblin(
        name="Prior target target",
        position=(5, 6),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)
    attacker.set_target_entity(prior_attacker_target.uuid)
    target.set_target_entity(prior_target_target.uuid)

    original_attack_bonus = Entity.attack_bonus

    def fail_attack_bonus(
        entity: Entity,
        weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN,
        target_entity_uuid: UUID | None = None,
        override_ability: AbilityName | None = None,
    ) -> ModifiableValue:
        if entity.uuid == attacker.uuid:
            raise RuntimeError("deterministic target-context failure")
        return original_attack_bonus(
            entity,
            weapon_slot,
            target_entity_uuid,
            override_ability,
        )

    monkeypatch.setattr(Entity, "attack_bonus", fail_attack_bonus)

    with pytest.raises(RuntimeError, match="deterministic target-context failure"):
        Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert attacker.target_entity_uuid == prior_attacker_target.uuid
    assert target.target_entity_uuid == prior_target_target.uuid


def test_eb_10_010_natural_rolls_drive_crit_and_crit_miss_outcomes() -> None:
    """EB-10-010: natural d20 values are read from the attack roll."""
    reset_core_action_state()
    attacker = create_goblin(name="Nat 20 Attacker", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Unreachable AC", position=(6, 5), faction="monsters")
    target.equipment.ac_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            name="Unreachable AC",
            value=100,
        )
    )
    Entity.update_all_entities_senses(max_distance=20)

    with fixed_dice(20):
        high_ac_event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert high_ac_event is not None
    assert high_ac_event.dice_roll is not None
    assert high_ac_event.dice_roll.results == [20]
    assert high_ac_event.attack_outcome == AttackOutcome.CRIT
    assert EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)

    reset_core_action_state()
    attacker = create_goblin(name="Nat 1 Attacker", position=(5, 5), faction="heroes")
    target = create_skeleton(name="Low AC", position=(6, 5), faction="monsters")
    target.equipment.ac_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            name="Low AC",
            value=-100,
        )
    )
    Entity.update_all_entities_senses(max_distance=20)

    with fixed_dice(1):
        low_ac_event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert low_ac_event is not None
    assert low_ac_event.dice_roll is not None
    assert low_ac_event.dice_roll.results == [1]
    assert low_ac_event.attack_outcome == AttackOutcome.CRIT_MISS
    assert not EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)


def test_eb_10_011_ranged_range_flags_and_disadvantage() -> None:
    """EB-10-011: ranged weapons distinguish normal, long, and impossible range."""
    reset_core_action_state()
    get_map().create_rectangle(0, 0, 80, 5)

    archer = create_goblin_archer(name="Archer", position=(0, 0), faction="heroes")
    normal_target = create_skeleton(name="Normal Target", position=(16, 0), faction="monsters")
    long_target = create_skeleton(name="Long Target", position=(17, 0), faction="monsters")
    beyond_target = create_skeleton(name="Beyond Target", position=(65, 0), faction="monsters")
    Entity.update_all_entities_senses(max_distance=80)

    normal_attack = Attack(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=normal_target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
    )
    normal_event = validate_attack_declaration(normal_attack)

    assert normal_event is not None
    assert normal_event.canceled is False
    assert normal_event.is_long_range is False
    assert normal_event.range is not None
    assert normal_event.range.normal == 80
    assert normal_event.range.long == 320

    actions_before = archer.action_economy.actions.normalized_score
    beyond_event = Attack(
        source_entity_uuid=archer.uuid,
        target_entity_uuid=beyond_target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN,
    ).apply()

    assert beyond_event is not None
    assert beyond_event.canceled is True
    assert "range" in (beyond_event.status_message or "").lower()
    assert archer.action_economy.actions.normalized_score == actions_before

    with fixed_dice(19, 2):
        long_event = Attack(
            source_entity_uuid=archer.uuid,
            target_entity_uuid=long_target.uuid,
            weapon_slot=WeaponSlot.RANGED_MAIN,
        ).apply()

    assert long_event is not None
    assert long_event.canceled is False
    assert long_event.is_long_range is True
    assert long_event.dice_roll is not None
    assert long_event.dice_roll.results == [19, 2]
    assert long_event.dice_roll.advantage_status == AdvantageStatus.DISADVANTAGE
    assert long_event.attack_outcome in {AttackOutcome.MISS, AttackOutcome.CRIT_MISS}


def test_eb_10_013_threatened_ranged_attacks_roll_with_disadvantage() -> None:
    """EB-10-013: adjacent visible enemies impose ranged-attack disadvantage."""
    reset_core_action_state()
    get_map().create_rectangle(0, 0, 30, 10)

    archer = create_goblin_archer(name="Threatened Archer", position=(5, 5), faction="heroes")
    create_goblin(name="Adjacent Enemy", position=(5, 6), faction="monsters")
    target = create_skeleton(name="Normal Target", position=(15, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=30)

    assert archer.is_threatened() is True

    with fixed_dice(18, 3):
        threatened_event = Attack(
            source_entity_uuid=archer.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.RANGED_MAIN,
        ).apply()

    assert threatened_event is not None
    assert threatened_event.canceled is False
    assert threatened_event.is_long_range is False
    assert threatened_event.is_threatened is True
    assert threatened_event.dice_roll is not None
    assert threatened_event.dice_roll.results == [18, 3]
    assert threatened_event.dice_roll.advantage_status == AdvantageStatus.DISADVANTAGE
    assert threatened_event.attack_outcome in {AttackOutcome.MISS, AttackOutcome.CRIT_MISS}

    reset_core_action_state()
    get_map().create_rectangle(0, 0, 30, 10)

    archer = create_goblin_archer(name="Long Threatened Archer", position=(5, 5), faction="heroes")
    create_goblin(name="Adjacent Enemy", position=(5, 6), faction="monsters")
    target = create_skeleton(name="Long Target", position=(22, 5), faction="monsters")
    Entity.update_all_entities_senses(max_distance=30)

    with fixed_dice(18, 3):
        combined_event = Attack(
            source_entity_uuid=archer.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.RANGED_MAIN,
        ).apply()

    assert combined_event is not None
    assert combined_event.canceled is False
    assert combined_event.is_long_range is True
    assert combined_event.is_threatened is True
    assert combined_event.dice_roll is not None
    assert combined_event.dice_roll.results == [18, 3]
    assert combined_event.dice_roll.advantage_status == AdvantageStatus.DISADVANTAGE
    assert combined_event.attack_outcome in {AttackOutcome.MISS, AttackOutcome.CRIT_MISS}


def test_eb_10_012_jump_uses_step_events_and_opportunity_attacks() -> None:
    """EB-10-012: jump movement emits steps and can provoke opportunity attacks."""
    reset_core_action_state()
    jumper = strong_entity("Jumper", (5, 5), "heroes", strength=16)
    watcher = create_skeleton(name="Watcher", position=(6, 5), faction="monsters")
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)

    hp_before = jumper.get_hp()
    hit_modifier = force_attack_hit(watcher)

    with fixed_dice(10, 4):
        jump_event = Jump(source_entity_uuid=jumper.uuid, end_position=(5, 8)).apply()

    remove_attack_modifier(watcher, hit_modifier)

    assert isinstance(jump_event, JumpEvent)
    assert jump_event.phase == EventPhase.COMPLETION
    assert jumper.position == (5, 8)
    assert jumper.get_hp() < hp_before
    assert watcher.action_economy.reactions.normalized_score == 0
    completed_steps = [
        step
        for step in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if (
            isinstance(step, StepMovementEvent)
            and step.source_entity_uuid == jumper.uuid
            and step.phase == EventPhase.COMPLETION
        )
    ]
    assert len(completed_steps) == 1
    assert jump_event.trajectory is MovementTrajectory.DIRECT_ARC
    assert completed_steps[0].trajectory is MovementTrajectory.DIRECT_ARC
    assert completed_steps[0].from_position == (5, 5)
    assert completed_steps[0].to_position == (5, 8)
    assert completed_steps[0].disclosed_path == (
        (5, 5),
        (5, 6),
        (5, 7),
        (5, 8),
    )
    assert any(event.name == "Opportunity Attack" for event in EventQueue.get_events_by_type(EventType.ATTACK))

    reset_core_action_state()
    jumper = strong_entity("Disengaging Jumper", (5, 5), "heroes", strength=16)
    watcher = create_skeleton(name="Patient Watcher", position=(6, 5), faction="monsters")
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)

    disengage_event = Disengage(source_entity_uuid=jumper.uuid).apply()
    hp_before = jumper.get_hp()
    hit_modifier = force_attack_hit(watcher)

    with fixed_dice(10, 4):
        jump_event = Jump(source_entity_uuid=jumper.uuid, end_position=(5, 8)).apply()

    remove_attack_modifier(watcher, hit_modifier)

    assert disengage_event is not None
    assert jump_event is not None
    assert jumper.position == (5, 8)
    assert jumper.get_hp() == hp_before
    assert watcher.action_economy.reactions.normalized_score == 1
    assert not any(
        event.name == "Opportunity Attack"
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
    )


def test_eb_10_018_lethal_jump_opportunity_attack_completes_without_cost_error() -> None:
    """EB-10-018: lethal OA interrupts Jump before leaving reach."""
    reset_core_action_state()
    jumper_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=10),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=6, hit_dice_count=1, mode="maximums")]
        ),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=(5, 6),
        faction="heroes",
    )
    jumper = Entity.create(source_entity_uuid=uuid4(), name="Fragile Jumper", config=jumper_config)
    setup_standard_actions(jumper)
    watcher = create_skeleton(name="Watcher", position=(5, 5), faction="monsters")
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)

    hp_before = jumper.get_hp()
    hit_modifier = force_attack_hit(watcher)
    crit_modifier = force_attack_crit(watcher)

    with fixed_dice(10, 6, 6):
        jump_event = Jump(source_entity_uuid=jumper.uuid, end_position=(5, 9)).apply()

    remove_attack_modifier(watcher, hit_modifier)
    remove_attack_modifier(watcher, crit_modifier)

    assert isinstance(jump_event, JumpEvent)
    assert jump_event.phase == EventPhase.COMPLETION
    assert jump_event.termination_reason is MovementTerminationReason.DEAD
    assert jumper.health.life_state is LifeState.DEAD
    assert jumper.get_hp() <= 0
    assert hp_before - jumper.get_hp() >= hp_before
    assert jumper.position == (5, 6)
    assert jump_event.end_position == (5, 6)
    assert watcher.action_economy.reactions.normalized_score == 0

    effect_steps = [
        step
        for step in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if isinstance(step, StepMovementEvent)
        and step.source_entity_uuid == jumper.uuid
        and step.phase == EventPhase.EFFECT
    ]
    completed_steps = [
        step
        for step in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if isinstance(step, StepMovementEvent)
        and step.source_entity_uuid == jumper.uuid
        and step.phase == EventPhase.COMPLETION
    ]
    assert len({step.lineage_uuid for step in effect_steps}) == 1
    assert all(step.from_position == (5, 6) for step in effect_steps)
    assert all(step.to_position == (5, 9) for step in effect_steps)
    assert len(completed_steps) == 1
    assert completed_steps[0].committed is False
    assert completed_steps[0].trajectory is MovementTrajectory.DIRECT_ARC


if __name__ == "__main__":
    tests = [
        test_eb_10_001_invalid_attack_cancels_before_costs,
        test_eb_10_015_melee_reach_validation_uses_weapon_range,
        test_eb_10_020_diagonal_adjacency_counts_as_five_foot_threat,
        test_eb_10_002_attack_hit_rolls_damage_and_consumes_action,
        test_eb_10_003_critical_hit_doubles_weapon_damage_dice,
        test_eb_10_004_move_consumes_movement_per_step_and_records_step_events,
        test_eb_10_005_opportunity_attack_uses_reaction_on_step_movement,
        test_eb_10_017_lethal_opportunity_attack_stops_before_leaving_reach,
        test_eb_10_006_disengage_prevents_opportunity_attack,
        test_eb_10_014_opportunity_attack_reaction_limits_repeat_triggers,
        test_eb_10_007_shove_forced_movement_does_not_trigger_opportunity_attack,
        test_eb_10_021_forced_movement_traverses_terrain_without_step_costs,
        test_eb_10_022_shove_uses_videogame_bonus_action_forced_movement,
        test_eb_10_008_dash_damage_healing_and_death_use_events,
        test_eb_10_023_default_zero_hp_uses_monster_style_death,
        test_eb_10_025_player_style_death_saves_roll_at_turn_start,
        test_eb_10_026_player_style_stabilization_healing_and_massive_damage,
        test_eb_10_016_mixed_weapon_damage_applies_resistance_per_component,
        test_eb_10_019_mixed_weapon_damage_applies_vulnerability_and_immunity_per_component,
        test_eb_10_009_attack_target_context_is_temporary_on_miss,
        test_eb_10_010_natural_rolls_drive_crit_and_crit_miss_outcomes,
        test_eb_10_011_ranged_range_flags_and_disadvantage,
        test_eb_10_012_jump_uses_step_events_and_opportunity_attacks,
        test_eb_10_018_lethal_jump_opportunity_attack_completes_without_cost_error,
        test_eb_10_013_threatened_ranged_attacks_roll_with_disadvantage,
    ]

    for test in tests:
        test()
        print(f"{test.__name__}: PASS")
