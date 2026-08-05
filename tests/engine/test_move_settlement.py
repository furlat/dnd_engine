"""Focused owner regressions for voluntary Move-family settlement."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

import pytest

from dnd.actions import Move, MovementEvent
from dnd.core.base_actions import Cost
from dnd.core.action_execution import (
    MovementContinuationDecision,
    MovementContinuationResult,
    MovementStepBoundary,
    MovementTerminationReason,
    movement_continuation_scope,
)
from dnd.core.base_block import MovementMode
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    ForcedMovementEvent,
    SpatialChangeEvent,
    StepMovementEvent,
    Trigger,
)
from dnd.core.modifiers import NumericalModifier
from dnd.core.gridmap import get_map
from dnd.creature_transforms import (
    apply_opportunity_attack_immunity_transform,
)
from dnd.entity import Entity
from dnd.monsters.traits import AggressiveMoveAction
from dnd.reactions import add_opportunity_attack_handler
from tests.engine.support import force_attack_crit, force_attack_hit, set_hp
from tests.engine.test_combat_actions import (
    fixed_dice,
    reset_core_action_state,
    strong_entity,
)


def _open_movement_world() -> Entity:
    """Build one disclosed floor lane with a fully configured mover."""
    reset_core_action_state()
    mover = strong_entity("Mover", (0, 0), "heroes")
    Entity.update_all_entities_senses(max_distance=20)
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
    completion_inputs: list[UUID] = []

    def observe_completion_input(event: Event) -> None:
        if event.event_type is EventType.MOVEMENT:
            completion_inputs.append(event.uuid)

    def complete_early(event: Event, _source_uuid: UUID) -> Event:
        return event.phase_to(EventPhase.COMPLETION)

    EventQueue.add_pre_completion_callback(observe_completion_input)
    _add_movement_handler(mover, EventPhase.EFFECT, complete_early)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.CANCELED
    assert len(completion_inputs) == 1
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
    ("register", "publish_preflighted", "completion_sequence"),
)
@pytest.mark.parametrize("invalid_first", (True, False))
def test_public_storage_paths_cannot_publish_token_derived_forged_step(
    publication_path: str,
    invalid_first: bool,
) -> None:
    """Every public storage path detaches an active guarded proposal token."""
    mover = _open_movement_world()
    callback_events: list[StepMovementEvent] = []

    def observe(event: Event) -> None:
        if isinstance(event, StepMovementEvent):
            callback_events.append(event)

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
            elif publication_path == "publish_preflighted":
                EventQueue.publish_preflighted(forged)
            else:
                EventQueue.register_completion_sequence((forged,))

        if not invalid_first:
            EventQueue.register(step)
        publish_forged()
        if invalid_first:
            EventQueue.register(step)
        return step

    EventQueue.add_on_event_callback(observe)
    _add_step_handler(mover, forge_and_register)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

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
    ("register", "publish_preflighted", "completion_sequence"),
)
@pytest.mark.parametrize("invalid_first", (True, False))
def test_public_storage_paths_cannot_publish_token_derived_forged_root(
    publication_path: str,
    invalid_first: bool,
) -> None:
    """The centralized storage fence also terminates a forged Move root."""
    mover = _open_movement_world()
    callback_events: list[MovementEvent] = []

    def observe(event: Event) -> None:
        if isinstance(event, MovementEvent):
            callback_events.append(event)

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
            elif publication_path == "publish_preflighted":
                EventQueue.publish_preflighted(forged)
            else:
                EventQueue.register_completion_sequence((forged,))

        if not invalid_first:
            EventQueue.register(movement)
        publish_forged()
        if invalid_first:
            EventQueue.register(movement)
        return movement

    EventQueue.add_on_event_callback(observe)
    _add_movement_handler(mover, EventPhase.EFFECT, forge_and_publish)
    result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0)).apply()

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
    Entity.update_all_entities_senses(max_distance=20)
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


def test_later_opportunity_attack_skips_after_first_reactor_kills_mover() -> None:
    """Ordered reactors re-read mover life before each opportunity attack."""
    reset_core_action_state()
    first = strong_entity("First Watcher", (0, 0), "monsters")
    second = strong_entity("Second Watcher", (1, 0), "monsters")
    mover = strong_entity("Fragile Mover", (0, 1), "heroes")
    add_opportunity_attack_handler(first)
    add_opportunity_attack_handler(second)
    Entity.update_all_entities_senses(max_distance=20)
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
    Entity.update_all_entities_senses(max_distance=20)
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
    Entity.update_all_entities_senses(max_distance=20)

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


def test_effect_stop_marker_yields_to_later_objective_death() -> None:
    """Ordered EFFECT mechanics survive a veto and objective death wins."""
    mover = _open_movement_world()

    def veto(event: Event, _source_uuid: UUID) -> Event:
        return event.cancel(status_message="stop after prior effects")

    def kill(event: Event, _source_uuid: UUID) -> Event:
        set_hp(mover, 0)
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
        set_hp(mover, 0)
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
