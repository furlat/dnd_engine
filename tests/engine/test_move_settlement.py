"""Focused owner regressions for voluntary Move-family settlement."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

import pytest

from dnd.actions.standard import (
    Attack,
    Move,
    MovementEvent,
)
from dnd.actions.operations import execute_use_action
from dnd.blocks.action_economy import RechargeType, Resource
from dnd.core.base_actions import (
    Cost,
)
from dnd.core.action_execution import (
    MovementContinuationDecision,
    MovementContinuationResult,
    MovementStepBoundary,
    MovementTerminationReason,
    movement_continuation_scope,
)
from dnd.types.equipment import WeaponSlot
from dnd.types.damage import DamageType
from dnd.types.world import CardinalDirection, MovementMode, WorldEdgeChannel
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.events.world_events import (
    ForcedMovementEvent,
    SpatialChangeEvent,
    StepMovementEvent,
)
from dnd.core.modifiers import NumericalModifier
from dnd.core.gridmap import get_map
from dnd.content.items.environment_item_builders import build_directional_door
from dnd.types.life import LifeState
from dnd.core.positioning import PositionPublicationError
from dnd.entities.creature_transforms import (
    apply_opportunity_attack_immunity_transform,
)
from dnd.entities.entity import Entity
from dnd.monsters.traits import AggressiveMoveAction
from dnd.actions.reactions import add_opportunity_attack_handler
from tests.engine.support import (
    force_attack_crit,
    force_attack_hit,
    remove_attack_modifier,
    set_hp,
)
from tests.manual.reactive_fixture_support import (
    DodgeRollFeature,
    PrepareIntercept,
)
from tests.engine.test_combat_actions import (
    fixed_dice,
    reset_core_action_state,
    strong_entity,
)


def _open_movement_world() -> Entity:
    """Build one disclosed floor lane with a fully configured mover."""
    reset_core_action_state()
    mover = strong_entity("Mover", (0, 0), "heroes")
    Entity.materialize_all_navigation(max_distance=20)
    return mover


def _movement_cost(event: MovementEvent) -> int:
    """Return the root's one exact settled movement cost."""
    movement_costs = [
        cost.cost for cost in event.costs if cost.cost_type == "movement"
    ]
    assert len(movement_costs) == 1
    return movement_costs[0]


def _step_versions(
    mover_uuid: UUID,
    phase: EventPhase,
) -> list[StepMovementEvent]:
    """Return exact stored Step versions for one mover and phase."""
    return [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if isinstance(event, StepMovementEvent)
        and event.source_entity_uuid == mover_uuid
        and event.phase is phase
    ]


def _add_movement_handler(
    owner: Entity,
    phase: EventPhase,
    processor: Callable[[Event, UUID], Event | None],
) -> None:
    """Register one exact root-movement handler owned by an entity."""
    owner.add_event_handler(EventHandler(
        name=f"Movement {phase.value} probe",
        source_entity_uuid=owner.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.MOVEMENT,
            event_phase=phase,
            event_source_entity_uuid=owner.uuid,
        )],
        event_processor=processor,
    ))


def _add_step_handler(
    owner: Entity,
    processor: Callable[[Event, UUID], Event | None],
) -> None:
    """Register one exact PATH-Step EFFECT handler owned by an entity."""
    owner.add_event_handler(EventHandler(
        name="PATH Step probe",
        source_entity_uuid=owner.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=owner.uuid,
        )],
        event_processor=processor,
    ))


class _InterruptWithoutReason:
    """Record the first committed boundary and interrupt without prose."""

    def __init__(self) -> None:
        self.boundaries: list[MovementStepBoundary] = []

    def after_committed_step(
        self,
        boundary: MovementStepBoundary,
    ) -> MovementContinuationResult:
        self.boundaries.append(boundary)
        return MovementContinuationResult(
            decision=MovementContinuationDecision.INTERRUPT,
            reason=None,
        )


def test_three_step_move_debits_and_reports_one_exact_settlement() -> None:
    """Committed Step costs, balance debit, and root truth have one owner."""
    mover = _open_movement_world()
    movement_before = mover.action_economy.movement.normalized_score

    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(3, 0),
    ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert not result.canceled
    assert result.start_position == (0, 0)
    assert result.requested_end_position == (3, 0)
    assert result.end_position == (3, 0)
    assert result.objective_end_position == (3, 0)
    assert result.path == ((0, 0), (1, 0), (2, 0), (3, 0))
    assert result.movement_mode is MovementMode.WALKING
    assert result.termination_reason is MovementTerminationReason.COMPLETED

    steps = _step_versions(mover.uuid, EventPhase.COMPLETION)
    assert len(steps) == 3
    assert all(step.committed for step in steps)
    assert [step.movement_cost for step in steps] == [5, 5, 5]
    assert _movement_cost(result) == sum(step.movement_cost for step in steps)
    assert mover.action_economy.movement.normalized_score == movement_before - 15


@pytest.mark.parametrize(
    "bad_position",
    (
        (True, 1),
        (1.5, 1),
        ("1", 1),
        (1,),
        (1, 2, 3),
    ),
)
def test_move_rejects_malformed_coordinates_before_execution(
    bad_position: object,
) -> None:
    """Unchecked coercions cannot admit malformed movement coordinates."""
    mover = _open_movement_world()

    with pytest.raises((TypeError, ValueError)):
        Move(
            source_entity_uuid=mover.uuid,
            end_position=bad_position,  # type: ignore[arg-type]
        )


def test_discontinuous_path_cancels_with_normalized_zero_settlement() -> None:
    """A disclosed endpoint does not authorize a skipped grid edge."""
    mover = _open_movement_world()
    movement_before = mover.action_economy.movement.normalized_score

    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(2, 0),
        path=((0, 0), (2, 0)),
    ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.CANCEL
    assert result.canceled_from_phase is EventPhase.DECLARATION
    assert result.termination_reason is MovementTerminationReason.INVALID_PATH
    assert result.end_position == (0, 0)
    assert result.objective_end_position == (0, 0)
    assert result.path == ((0, 0),)
    assert result.costs == []
    assert mover.position == (0, 0)
    assert mover.action_economy.movement.normalized_score == movement_before


def test_declaration_cancellation_is_normalized_before_settlement() -> None:
    """A declaration veto retains intent but reports no committed movement."""
    mover = _open_movement_world()

    def cancel(event: Event, _source_uuid: UUID) -> Event:
        return event.cancel(status_message="declaration veto")

    _add_movement_handler(mover, EventPhase.DECLARATION, cancel)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.CANCEL
    assert result.canceled_from_phase is EventPhase.DECLARATION
    assert result.termination_reason is MovementTerminationReason.CANCELED
    assert result.requested_end_position == (1, 0)
    assert result.end_position == (0, 0)
    assert result.objective_end_position == (0, 0)
    assert result.path == ((0, 0),)
    assert result.costs == []


def test_effect_cancellation_becomes_a_completed_zero_step_stop() -> None:
    """Published EFFECT cannot be rewound into a root cancellation."""
    mover = _open_movement_world()
    movement_before = mover.action_economy.movement.normalized_score

    def cancel(event: Event, _source_uuid: UUID) -> Event:
        return event.cancel(status_message="effect veto")

    _add_movement_handler(mover, EventPhase.EFFECT, cancel)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert not result.canceled
    assert result.termination_reason is MovementTerminationReason.CANCELED
    assert result.end_position == (0, 0)
    assert result.objective_end_position == (0, 0)
    assert result.path == ((0, 0),)
    assert _movement_cost(result) == 0
    assert _step_versions(mover.uuid, EventPhase.EFFECT) == []
    assert mover.action_economy.movement.normalized_score == movement_before


def test_premature_root_completion_is_stopped_before_completion_systems() -> None:
    """A handler cannot run root completion work before accepted settlement."""
    mover = _open_movement_world()

    def complete_early(event: Event, _source_uuid: UUID) -> Event:
        return event.phase_to(EventPhase.COMPLETION)

    _add_movement_handler(mover, EventPhase.EFFECT, complete_early)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.CANCELED
    lineage = EventQueue.get_event_history(result.uuid)
    assert [event.phase for event in lineage].count(EventPhase.COMPLETION) == 1


def test_root_nested_cost_mutation_cannot_alias_stored_declaration() -> None:
    """A guarded root proposal cannot rewrite a prior stored cost in place."""
    mover = _open_movement_world()

    def mutate(event: Event, _source_uuid: UUID) -> Event:
        movement = cast(MovementEvent, event)
        assert movement.costs
        movement.costs[0].cost = 999
        return movement

    _add_movement_handler(mover, EventPhase.DECLARATION, mutate)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.CANCEL
    assert result.termination_reason is MovementTerminationReason.CANCELED
    declaration = next(
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if isinstance(event, MovementEvent)
        and event.lineage_uuid == result.lineage_uuid
        and event.phase is EventPhase.DECLARATION
    )
    assert [cost.cost for cost in declaration.costs] == [5]


@pytest.mark.parametrize(
    ("field_name", "forged_value"),
    (
        ("uuid", 7),
        ("timestamp", 3),
        ("modified", 1),
        ("status_message", 99),
    ),
)
def test_root_rejects_malformed_queue_evidence_before_storage(
    field_name: str,
    forged_value: object,
) -> None:
    mover = _open_movement_world()

    def forge(event: Event, _source_uuid: UUID) -> Event:
        return event.model_copy(update={field_name: forged_value})

    _add_movement_handler(mover, EventPhase.DECLARATION, forge)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.CANCEL
    versions = EventQueue.get_event_history(result.uuid)
    assert all(type(event.uuid) is UUID for event in versions)
    assert all(type(event.timestamp) is datetime for event in versions)
    assert all(type(event.modified) is bool for event in versions)
    assert all(
        event.status_message is None or type(event.status_message) is str
        for event in versions
    )


def test_path_step_cost_rewrite_becomes_one_canonical_cancel() -> None:
    """A PATH handler cannot make the executor commit a rewritten edge."""
    mover = _open_movement_world()
    movement_before = mover.action_economy.movement.normalized_score

    def rewrite(event: Event, _source_uuid: UUID) -> Event:
        return event.model_copy(update={"movement_cost": 999})

    _add_step_handler(mover, rewrite)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.STEP_CANCELED
    assert result.path == ((0, 0),)
    assert _movement_cost(result) == 0
    assert mover.position == (0, 0)
    assert mover.action_economy.movement.normalized_score == movement_before
    canceled_steps = _step_versions(mover.uuid, EventPhase.CANCEL)
    assert len(canceled_steps) == 1
    assert _step_versions(mover.uuid, EventPhase.COMPLETION) == []


def test_path_step_premature_completion_becomes_canonical_cancel() -> None:
    """A PATH handler cannot publish completion callbacks or committed truth."""
    mover = _open_movement_world()

    def complete_early(event: Event, _source_uuid: UUID) -> Event:
        return event.phase_to(EventPhase.COMPLETION, committed=True)

    _add_step_handler(mover, complete_early)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.STEP_CANCELED
    assert len(_step_versions(mover.uuid, EventPhase.CANCEL)) == 1
    assert _step_versions(mover.uuid, EventPhase.COMPLETION) == []


@pytest.mark.parametrize(
    "publication_path",
    ("register", "publish_preflighted"),
)
@pytest.mark.parametrize("invalid_first", (True, False))
def test_public_storage_paths_cannot_publish_token_derived_forged_step(
    publication_path: str,
    invalid_first: bool,
) -> None:
    """Every public storage path detaches an active guarded proposal token."""
    mover = _open_movement_world()
    def forge_and_register(event: Event, _source_uuid: UUID) -> Event:
        step = cast(StepMovementEvent, event)
        forged = step.model_copy(update={
            "uuid": uuid4(),
            "lineage_uuid": uuid4(),
            "phase": EventPhase.COMPLETION,
            "committed": True,
            "to_position": (99, 99),
            "movement_cost": 999,
            "use_register": publication_path != "publish_preflighted",
        })
        def publish_forged() -> None:
            if publication_path == "register":
                EventQueue.register(forged)
            else:
                EventQueue.publish_preflighted(forged)

        if not invalid_first:
            EventQueue.register(step)
        publish_forged()
        if invalid_first:
            EventQueue.register(step)
        return step

    cursor = EventQueue.event_cursor()
    _add_step_handler(mover, forge_and_register)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    callback_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, StepMovementEvent)
    ]

    assert isinstance(result, MovementEvent)
    assert result.termination_reason is MovementTerminationReason.STEP_CANCELED
    stored_steps = [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if isinstance(event, StepMovementEvent)
    ]
    assert all(event.to_position != (99, 99) for event in stored_steps)
    assert all(event.to_position != (99, 99) for event in callback_events)
    assert not any(
        event.phase is EventPhase.COMPLETION and event.committed
        for event in stored_steps
    )


@pytest.mark.parametrize(
    "publication_path",
    ("register", "publish_preflighted"),
)
@pytest.mark.parametrize("invalid_first", (True, False))
def test_public_storage_paths_cannot_publish_token_derived_forged_root(
    publication_path: str,
    invalid_first: bool,
) -> None:
    """The centralized storage fence also terminates a forged Move root."""
    mover = _open_movement_world()
    def forge_and_publish(event: Event, _source_uuid: UUID) -> Event:
        movement = cast(MovementEvent, event)
        forged = movement.model_copy(update={
            "uuid": uuid4(),
            "lineage_uuid": uuid4(),
            "phase": EventPhase.COMPLETION,
            "end_position": (99, 99),
            "objective_end_position": (99, 99),
            "path": ((0, 0), (99, 99)),
            "use_register": publication_path != "publish_preflighted",
        })
        def publish_forged() -> None:
            if publication_path == "register":
                EventQueue.register(forged)
            else:
                EventQueue.publish_preflighted(forged)

        if not invalid_first:
            EventQueue.register(movement)
        publish_forged()
        if invalid_first:
            EventQueue.register(movement)
        return movement

    cursor = EventQueue.event_cursor()
    _add_movement_handler(mover, EventPhase.EFFECT, forge_and_publish)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    callback_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, MovementEvent)
    ]

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.CANCELED
    assert result.path == ((0, 0),)
    stored_roots = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if isinstance(event, MovementEvent)
    ]
    assert all(event.end_position != (99, 99) for event in stored_roots)
    assert all(event.end_position != (99, 99) for event in callback_events)


def test_lethal_opportunity_attack_leaves_a_free_logless_false_step() -> None:
    """A lethal pre-entry reaction stops without debit or a success log."""
    reset_core_action_state()
    watcher = strong_entity("Watcher", (0, 0), "monsters")
    mover = strong_entity("Fragile Mover", (0, 1), "heroes")
    add_opportunity_attack_handler(watcher)
    Entity.materialize_all_navigation(max_distance=20)
    set_hp(mover, 1)
    force_attack_hit(watcher)
    force_attack_crit(watcher)
    movement_cost_modifiers_before = {
        modifier.uuid
        for modifier in mover.action_economy.get_cost_modifiers("movement")
    }

    with fixed_dice(10, 6, 6):
        result = Move(
            source_entity_uuid=mover.uuid,
            end_position=(0, 3),
        ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.DEAD
    assert result.path == ((0, 1),)
    assert result.end_position == (0, 1)
    assert result.objective_end_position == (0, 1)
    assert _movement_cost(result) == 0
    assert mover.position == (0, 1)
    assert {
        modifier.uuid
        for modifier in mover.action_economy.get_cost_modifiers("movement")
    } == movement_cost_modifiers_before
    false_steps = _step_versions(mover.uuid, EventPhase.COMPLETION)
    assert len(false_steps) == 1
    assert false_steps[0].committed is False
    assert false_steps[0].combat_log is None


def test_committed_step_and_root_logs_retain_opportunity_attack_child() -> None:
    """Guard validation preserves queue-authored reaction child lineages."""
    reset_core_action_state()
    watcher = strong_entity("Watcher", (0, 0), "monsters")
    mover = strong_entity("Mover", (0, 1), "heroes")
    add_opportunity_attack_handler(watcher)
    Entity.materialize_all_navigation(max_distance=20)
    force_attack_hit(watcher)

    with fixed_dice(10, 1):
        result = Move(
            source_entity_uuid=mover.uuid,
            end_position=(0, 2),
        ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.combat_log is not None
    completed_step = _step_versions(mover.uuid, EventPhase.COMPLETION)[0]
    assert completed_step.committed is True
    assert completed_step.combat_log is not None
    assert any(
        child.entry_type.value == "attack"
        for child in completed_step.combat_log.sub_entries
    )
    step_root = next(
        child
        for child in result.combat_log.sub_entries
        if child.data.get("type") == "step_movement"
    )
    assert any(
        child.entry_type.value == "attack"
        for child in step_root.sub_entries
    )


def test_later_opportunity_attack_skips_after_first_reactor_kills_mover() -> None:
    """Ordered reactors re-read mover life before each opportunity attack."""
    reset_core_action_state()
    first = strong_entity("First Watcher", (0, 0), "monsters")
    second = strong_entity("Second Watcher", (1, 0), "monsters")
    mover = strong_entity("Fragile Mover", (0, 1), "heroes")
    add_opportunity_attack_handler(first)
    add_opportunity_attack_handler(second)
    Entity.materialize_all_navigation(max_distance=20)
    set_hp(mover, 1)
    force_attack_hit(first)
    force_attack_crit(first)
    force_attack_hit(second)

    with fixed_dice(10, 6, 6):
        result = Move(
            source_entity_uuid=mover.uuid,
            end_position=(0, 2),
        ).apply()

    assert isinstance(result, MovementEvent)
    assert result.termination_reason is MovementTerminationReason.DEAD
    opportunity_attacks = [
        event
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
        if event.name == "Opportunity Attack"
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(opportunity_attacks) == 1
    assert opportunity_attacks[0].source_entity_uuid == first.uuid
    assert first.action_economy.reactions.normalized_score == 0
    assert second.action_economy.reactions.normalized_score == 1


def test_aggressive_instantiation_and_retarget_preserve_fixed_cost() -> None:
    """Generated movement estimates cannot erase Aggressive's bonus action."""
    reset_core_action_state()
    actor = strong_entity("Aggressive Actor", (0, 0), "monsters")
    strong_entity("Visible Enemy", (4, 0), "heroes")
    Entity.materialize_all_navigation(max_distance=20)
    template = AggressiveMoveAction(
        source_entity_uuid=actor.uuid,
        template=True,
    )

    action = template.instantiate(end_position=(1, 0))
    assert [cost.cost_type for cost in action.costs].count("bonus_actions") == 1
    assert [cost.cost_type for cost in action.costs].count("movement") == 1

    action.set_target_position((2, 0))
    assert [cost.cost_type for cost in action.costs].count("bonus_actions") == 1
    assert [cost.cost_type for cost in action.costs].count("movement") == 1
    result = action.apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert actor.position == (2, 0)
    assert actor.action_economy.bonus_actions.normalized_score == 0
    assert [cost.cost_type for cost in result.costs].count("bonus_actions") == 1


def test_closed_boundary_door_invalidates_prepared_intercept_path() -> None:
    """A close after preparation makes the reaction use current path truth."""
    reset_core_action_state()
    interceptor = strong_entity("Interceptor", (2, 2), "heroes")
    door_closer = strong_entity("Door Closer", (4, 3), "neutral")
    enemy = strong_entity("Enemy", (9, 2), "monsters")
    door = build_directional_door(
        blocked_channels=tuple(WorldEdgeChannel),
        is_open=True,
    )
    grid = get_map()
    grid.place_object(door.uuid, (4, 2), boundary_direction=CardinalDirection.WEST)

    prepare = PrepareIntercept(source_entity_uuid=interceptor.uuid)
    prepare.set_target_position((6, 2))
    prepared = prepare.apply()
    assert prepared is not None and not prepared.canceled
    Entity.materialize_all_navigation(max_distance=20)

    closed = execute_use_action(door_closer, door.uuid, "Close Door")
    assert closed is not None and not closed.canceled
    assert door.is_open is False
    Entity.materialize_all_navigation(max_distance=20)

    movement = Move(source_entity_uuid=enemy.uuid, end_position=(5, 2)).apply()
    assert isinstance(movement, MovementEvent)
    assert not movement.canceled
    assert enemy.position == (5, 2)
    assert interceptor.position == (2, 2)
    assert interceptor.action_economy.reactions.normalized_score == 1


def test_open_boundary_door_is_authoritative_for_reaction_displacement() -> None:
    """A newly opened boundary door is used by reaction displacement."""
    reset_core_action_state()
    attacker = strong_entity("Attacker", (3, 2), "monsters")
    defender = strong_entity("Defender", (4, 2), "heroes")
    opener = strong_entity("Door Opener", (5, 3), "heroes")
    door = build_directional_door(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid = get_map()
    grid.place_object(door.uuid, (5, 2), boundary_direction=CardinalDirection.WEST)
    defender.add_condition(
        DodgeRollFeature(
            source_entity_uuid=defender.uuid,
            target_entity_uuid=defender.uuid,
        )
    )
    Entity.materialize_all_navigation(max_distance=20)

    opened = execute_use_action(opener, door.uuid, "Open Door")
    assert opened is not None and not opened.canceled
    assert door.is_open

    hit_modifier = force_attack_hit(attacker)
    try:
        result = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=defender.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    finally:
        remove_attack_modifier(attacker, hit_modifier)

    assert result is not None and not result.canceled
    assert defender.position == (6, 2)


def test_no_reason_interrupt_records_exact_committed_boundary() -> None:
    """INTERRUPT is semantic even when its optional reason is absent."""
    mover = _open_movement_world()
    guard = _InterruptWithoutReason()

    with movement_continuation_scope(guard):
        result = Move(
            source_entity_uuid=mover.uuid,
            end_position=(2, 0),
        ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.end_position == (1, 0)
    assert result.objective_end_position == (1, 0)
    assert result.path == ((0, 0), (1, 0))
    assert result.termination_reason is (
        MovementTerminationReason.SUBJECTIVE_REVALIDATION
    )
    assert result.controller_revalidation is True
    assert result.controller_revalidation_reason is None
    assert len(guard.boundaries) == 1
    boundary = guard.boundaries[0]
    assert boundary.objective_position == (1, 0)
    assert boundary.step_movement_cost == 5
    stored_step = EventQueue.get_event_by_uuid(boundary.step_event_uuid)
    assert isinstance(stored_step, StepMovementEvent)
    assert stored_step.phase is EventPhase.COMPLETION
    assert stored_step.committed is True
    assert stored_step.movement_cost == boundary.step_movement_cost


def test_differently_named_neutral_suppression_blocks_opportunity_attack() -> None:
    """OA execution reads the neutral provocation value, not a condition name."""
    reset_core_action_state()
    watcher = strong_entity("Watcher", (0, 0), "monsters")
    mover = strong_entity("Suppressed Mover", (0, 1), "heroes")
    add_opportunity_attack_handler(watcher)
    apply_opportunity_attack_immunity_transform(
        mover,
        name="Ethereal Withdrawal",
        effect_source_uuid=mover.uuid,
    )
    Entity.materialize_all_navigation(max_distance=20)

    result = Move(source_entity_uuid=mover.uuid, end_position=(0, 3)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert watcher.action_economy.reactions.normalized_score == 1
    assert not any(
        event.name == "Opportunity Attack"
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
    )


def test_opportunity_attack_capability_uses_life_and_reaction_only() -> None:
    """A spent turn may react, while spent reactions and death may not."""
    capability = getattr(Entity, "can_execute_opportunity_attack", None)
    assert callable(capability)
    reactor = _open_movement_world()

    assert capability(reactor) is True
    reactor.action_economy.action_permission.self_static.add_max_constraint(
        NumericalModifier.create(
            source_entity_uuid=reactor.uuid,
            name="Turn already spent",
            value=0,
        )
    )
    assert reactor.can_take_actions() is False
    assert capability(reactor) is True
    reactor.action_economy.consume("reactions", 1)
    assert capability(reactor) is False

    reactor.action_economy.reset_all_costs()
    assert capability(reactor) is True
    set_hp(reactor, 0)
    assert capability(reactor) is False


def test_use_movement_cost_false_still_debits_and_reports_committed_edge() -> None:
    """The legacy request flag cannot make committed movement free."""
    mover = _open_movement_world()
    movement_before = mover.action_economy.movement.normalized_score

    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(1, 0),
        use_movement_cost=False,
    ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.path == ((0, 0), (1, 0))
    assert _movement_cost(result) == 5
    assert mover.action_economy.movement.normalized_score == movement_before - 5


def test_fixed_costs_are_aggregate_readmitted_before_any_consumption() -> None:
    """Individually affordable duplicate facts cannot overdraw one bucket."""
    mover = _open_movement_world()

    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(1, 0),
        costs=[
            Cost(name="First", cost_type="bonus_actions", cost=1),
            Cost(name="Second", cost_type="bonus_actions", cost=1),
        ],
    ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.INVALID_COST
    assert result.path == ((0, 0),)
    assert _movement_cost(result) == 0
    assert all(cost.cost_type != "bonus_actions" for cost in result.costs)
    assert mover.action_economy.bonus_actions.normalized_score == 1
    assert mover.position == (0, 0)


def test_fixed_resource_cost_requires_an_exact_named_resource() -> None:
    """A nonzero resource claim cannot settle without a resource identity."""
    mover = _open_movement_world()
    movement_before = mover.action_economy.movement.normalized_score

    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(1, 0),
        costs=[
            Cost(
                name="Malformed resource",
                cost_type="bonus_actions",
                cost=0,
                resource_name=None,
                resource_cost=1,
            ),
        ],
    ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.CANCEL
    assert result.termination_reason is MovementTerminationReason.INVALID_COST
    assert result.costs == []
    assert mover.position == (0, 0)
    assert mover.action_economy.movement.normalized_score == movement_before


def test_move_fixed_resource_failure_restores_channel_and_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mover = _open_movement_world()
    economy = mover.action_economy
    economy.add_resource_contribution(
        "Focus",
        uuid4(),
        maximum=1,
        recharge_type=RechargeType.SHORT_REST,
    )
    original_consume = Resource.consume

    def decrement_then_raise(resource: Resource, amount: int = 1) -> bool:
        result = original_consume(resource, amount)
        if resource.name == "Focus":
            raise RuntimeError("injected Move resource failure")
        return result

    monkeypatch.setattr(Resource, "consume", decrement_then_raise)
    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(1, 0),
        costs=[Cost(
            name="Move focus",
            cost_type="bonus_actions",
            cost=1,
            resource_name="Focus",
            resource_cost=1,
        )],
    ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.INVALID_COST
    assert mover.position == (0, 0)
    assert economy.bonus_actions.normalized_score == 1
    assert economy.get_resource_current("Focus") == 1


def test_post_reaction_edge_cost_owns_debit_step_boundary_and_root() -> None:
    """One recomputed edge value settles every post-reaction cost fact."""
    mover = _open_movement_world()
    tile = get_map().get_tile(1, 0)
    assert tile is not None
    guard = _InterruptWithoutReason()

    def make_difficult(event: Event, _source_uuid: UUID) -> Event:
        tile.walking_cost.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=mover.uuid,
                name="Reaction terrain cost",
                value=1,
            )
        )
        return event

    _add_step_handler(mover, make_difficult)
    movement_before = mover.action_economy.movement.normalized_score
    with movement_continuation_scope(guard):
        result = Move(
            source_entity_uuid=mover.uuid,
            end_position=(1, 0),
        ).apply()

    assert isinstance(result, MovementEvent)
    completion = _step_versions(mover.uuid, EventPhase.COMPLETION)
    assert len(completion) == 1
    assert completion[0].movement_cost == 10
    assert _movement_cost(result) == 10
    assert mover.action_economy.movement.normalized_score == movement_before - 10
    assert guard.boundaries[0].step_movement_cost == 10


def test_step_handler_cannot_rewrite_move_mode_to_underpay_edge() -> None:
    """Accepted WALKING truth remains authoritative after Step reactions."""
    mover = _open_movement_world()
    tile = get_map().get_tile(1, 0)
    assert tile is not None
    tile.walking_cost.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=mover.uuid,
            name="Authored difficult terrain",
            value=1,
        )
    )

    def rewrite_parent_mode(event: Event, _source_uuid: UUID) -> Event:
        if event.parent_event is not None:
            stored_root = EventQueue.get_event_by_uuid(event.parent_event)
            if type(stored_root) is MovementEvent:
                stored_root.movement_mode = MovementMode.FLYING
        return event

    _add_step_handler(mover, rewrite_parent_mode)
    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(1, 0),
    ).apply()

    assert type(result) is MovementEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.movement_mode is MovementMode.WALKING
    assert mover.position == (1, 0)
    assert mover.action_economy.movement.normalized_score == 20
    assert _movement_cost(result) == 10
    completed_steps = _step_versions(mover.uuid, EventPhase.COMPLETION)
    assert len(completed_steps) == 1
    assert completed_steps[0].movement_cost == 10


def test_effect_stop_marker_yields_to_later_objective_death() -> None:
    """Ordered EFFECT mechanics survive a veto and objective death wins."""
    mover = _open_movement_world()

    def veto(event: Event, _source_uuid: UUID) -> Event:
        return event.cancel(status_message="stop after prior effects")

    def kill(event: Event, _source_uuid: UUID) -> Event:
        mover.receive_damage(
            mover.get_hp(),
            DamageType.FORCE,
            mover.uuid,
            parent_event=event.uuid,
        )
        return event

    _add_movement_handler(mover, EventPhase.EFFECT, veto)
    _add_movement_handler(mover, EventPhase.EFFECT, kill)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.DEAD
    assert result.path == ((0, 0),)
    assert _movement_cost(result) == 0
    assert _step_versions(mover.uuid, EventPhase.EFFECT) == []


def test_pre_entry_displacement_precedes_concurrent_death() -> None:
    """A missing frozen from-position wins before any voluntary edge exists."""
    mover = _open_movement_world()

    def displace_and_kill(event: Event, _source_uuid: UUID) -> Event:
        Entity.update_entity_position(
            mover,
            (0, 1),
            parent_event=event.uuid,
        )
        mover.receive_damage(
            mover.get_hp(),
            DamageType.FORCE,
            mover.uuid,
            parent_event=event.uuid,
        )
        return event

    _add_movement_handler(mover, EventPhase.EFFECT, displace_and_kill)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is (
        MovementTerminationReason.POSITION_DIVERGED
    )
    assert result.path == ((0, 0),)
    assert result.end_position == (0, 0)
    assert result.objective_end_position == (0, 1)
    assert _movement_cost(result) == 0
    assert _step_versions(mover.uuid, EventPhase.EFFECT) == []


def test_arrival_child_displacement_preserves_voluntary_and_objective_ends() -> None:
    """A synchronous child owns displacement beyond the paid voluntary cell."""
    mover = _open_movement_world()

    def displace_after_arrival(event: Event, _source_uuid: UUID) -> Event:
        if (
            not isinstance(event, SpatialChangeEvent)
            or event.position != (1, 0)
            or mover.position != (1, 0)
        ):
            return event
        declaration = ForcedMovementEvent(
            source_entity_uuid=mover.uuid,
            target_entity_uuid=mover.uuid,
            start_position=(1, 0),
            end_position=(1, 1),
            direction=(0, 1),
            intended_distance=5,
            parent_event=event.uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
        forced = EventQueue.publish_declaration(declaration)
        forced = forced.phase_to(EventPhase.EXECUTION)
        forced = forced.phase_to(EventPhase.EFFECT)
        Entity.update_entity_position(
            mover,
            (1, 1),
            parent_event=forced.uuid,
        )
        forced.phase_to(
            EventPhase.COMPLETION,
            actual_distance=5,
        )
        return event

    mover.add_event_handler(EventHandler(
        name="Arrival displacement probe",
        source_entity_uuid=mover.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=mover.uuid,
        )],
        event_processor=displace_after_arrival,
    ))
    result = Move(source_entity_uuid=mover.uuid, end_position=(2, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is (
        MovementTerminationReason.POSITION_DIVERGED
    )
    assert result.path == ((0, 0), (1, 0))
    assert result.end_position == (1, 0)
    assert result.objective_end_position == (1, 1)
    assert mover.position == (1, 1)
    assert _movement_cost(result) == 5


def test_arrival_handler_cannot_mutate_stored_step_or_root_effect_geometry() -> None:
    """Landing children cannot rewrite the already accepted Move transaction."""
    mover = _open_movement_world()

    def mutate_stored_effects(event: Event, _source_uuid: UUID) -> Event:
        if event.parent_event is None:
            return event
        stored_step = EventQueue.get_event_by_uuid(event.parent_event)
        if type(stored_step) is not StepMovementEvent:
            return event
        stored_root = (
            EventQueue.get_event_by_uuid(stored_step.parent_event)
            if stored_step.parent_event is not None
            else None
        )
        stored_step.to_position = (99, 99)
        stored_step.to_elevation_feet = 999
        stored_step.movement_cost = 999
        stored_step.disclosed_path = ((0, 0), (99, 99))
        if type(stored_root) is MovementEvent:
            stored_root.end_position = (99, 99)
            stored_root.objective_end_position = (99, 99)
            stored_root.path = ((0, 0), (99, 99))
        return event

    mover.add_event_handler(EventHandler(
        name="Mutate stored Move effects during arrival",
        source_entity_uuid=mover.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=mover.uuid,
        )],
        event_processor=mutate_stored_effects,
    ))

    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert type(result) is MovementEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.path == ((0, 0), (1, 0))
    assert result.end_position == (1, 0)
    assert result.objective_end_position == (1, 0)
    assert _movement_cost(result) == 5
    assert result.combat_log is not None
    assert result.combat_log.data["path"] == [(0, 0), (1, 0)]
    assert result.combat_log.data["distance_feet"] == 5
    step_versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if type(event) is StepMovementEvent
        and event.source_entity_uuid == mover.uuid
    ]
    assert step_versions
    assert all(step.to_position == (1, 0) for step in step_versions)
    assert all(step.to_elevation_feet == 0 for step in step_versions)
    assert all(step.movement_cost == 5 for step in step_versions)
    assert all((99, 99) not in step.disclosed_path for step in step_versions)


def test_move_arrival_mutation_is_restored_before_publication_error_escapes() -> None:
    """A committed arrival failure cannot leave forged Step/root history."""
    mover = _open_movement_world()

    def mutate_effects_then_raise(event: Event, _source_uuid: UUID) -> Event:
        if event.parent_event is None:
            return event
        stored_step = EventQueue.get_event_by_uuid(event.parent_event)
        if type(stored_step) is not StepMovementEvent:
            return event
        stored_root = (
            EventQueue.get_event_by_uuid(stored_step.parent_event)
            if stored_step.parent_event is not None
            else None
        )
        stored_step.uuid = uuid4()
        stored_step.to_position = (99, 99)
        stored_step.to_elevation_feet = 999
        stored_step.movement_cost = 999
        if type(stored_root) is MovementEvent:
            stored_root.uuid = uuid4()
            stored_root.requested_end_position = (99, 99)
            stored_root.end_position = (99, 99)
            stored_root.path = ((0, 0), (99, 99))
        raise RuntimeError("injected Move arrival publication failure")

    mover.add_event_handler(EventHandler(
        name="Mutate and fail Move arrival publication",
        source_entity_uuid=mover.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=mover.uuid,
        )],
        event_processor=mutate_effects_then_raise,
    ))

    with pytest.raises(PositionPublicationError):
        Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert mover.position == (1, 0)
    assert mover.action_economy.movement.normalized_score == 25
    roots = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is MovementEvent
        and event.source_entity_uuid == mover.uuid
        and event.phase is EventPhase.EFFECT
    ]
    steps = _step_versions(mover.uuid, EventPhase.EFFECT)
    assert len(roots) == 1
    assert len(steps) == 1
    assert EventQueue.get_event_by_uuid(roots[0].uuid) is roots[0]
    assert EventQueue.get_event_by_uuid(steps[0].uuid) is steps[0]
    assert roots[0].requested_end_position == (1, 0)
    assert roots[0].end_position == (1, 0)
    assert roots[0].path == ((0, 0), (1, 0))
    assert steps[0].to_position == (1, 0)
    assert steps[0].to_elevation_feet == 0
    assert steps[0].movement_cost == 5
    assert not _step_versions(mover.uuid, EventPhase.COMPLETION)


def test_move_restores_parent_between_step_handlers_and_when_later_handler_raises() -> None:
    """A Step handler cannot lend forged root mechanics to the next handler."""
    mover = _open_movement_world()
    seen_modes: list[MovementMode] = []

    def forge_parent(event: Event, _source_uuid: UUID) -> Event:
        if type(event) is StepMovementEvent and event.parent_event is not None:
            parent = EventQueue.get_event_by_uuid(event.parent_event)
            if type(parent) is MovementEvent:
                parent.uuid = uuid4()
                parent.movement_mode = MovementMode.FLYING
                parent.requested_end_position = (99, 99)
        return event

    def observe_reforge_and_raise(event: Event, _source_uuid: UUID) -> Event:
        if type(event) is StepMovementEvent and event.parent_event is not None:
            parent = EventQueue.get_event_by_uuid(event.parent_event)
            if type(parent) is MovementEvent:
                seen_modes.append(parent.movement_mode)
                if parent.movement_mode is MovementMode.FLYING:
                    set_hp(mover, 0)
                parent.uuid = uuid4()
                parent.requested_end_position = (88, 88)
        raise RuntimeError("injected Move Step handler failure")

    for name, processor in (
        ("Forge Move parent in first Step handler", forge_parent),
        ("Observe Move parent in second Step handler", observe_reforge_and_raise),
    ):
        mover.add_event_handler(EventHandler(
            name=name,
            source_entity_uuid=mover.uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.STEP_MOVEMENT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=mover.uuid,
            )],
            event_processor=processor,
        ))

    with pytest.raises(RuntimeError, match="injected Move Step handler failure"):
        Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert seen_modes == [MovementMode.WALKING]
    assert mover.health.life_state is LifeState.ALIVE
    assert mover.position == (0, 0)
    assert mover.action_economy.movement.normalized_score == 30
    roots = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is MovementEvent
        and event.source_entity_uuid == mover.uuid
        and event.phase is EventPhase.EFFECT
    ]
    assert len(roots) == 1
    assert EventQueue.get_event_by_uuid(roots[0].uuid) is roots[0]
    assert roots[0].movement_mode is MovementMode.WALKING
    assert roots[0].requested_end_position == (1, 0)
