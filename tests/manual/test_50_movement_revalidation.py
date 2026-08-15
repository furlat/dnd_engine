"""Committed movement-step continuation contracts."""

from typing import cast

from dnd.actions.standard import (
    MovementEvent,
)
from dnd.actions.operations import execute_by_index, get_available_actions
from dnd.core.action_execution import (
    MovementContinuationDecision,
    MovementContinuationResult,
    MovementStepBoundary,
    MovementTerminationReason,
    movement_continuation_scope,
)
from dnd.entity import Entity
from tests.manual.test_09_action_discovery_and_costs import (
    create_tutorial_actor,
    reset_action_state,
)


class _InterruptAfterFirstCommittedStep:
    """Record and interrupt after the first fully committed movement step."""

    def __init__(self) -> None:
        self.boundaries: list[MovementStepBoundary] = []

    def after_committed_step(
        self,
        boundary: MovementStepBoundary,
    ) -> MovementContinuationResult:
        """Return one deterministic external interruption decision."""
        self.boundaries.append(boundary)
        return MovementContinuationResult(
            decision=MovementContinuationDecision.INTERRUPT,
            reason="newly_visible_hostile",
            observation_cursor=17,
        )


def test_voluntary_move_interrupts_only_after_one_committed_paid_step() -> None:
    """An interruption preserves the exact paid and traversed movement."""
    reset_action_state()
    actor = create_tutorial_actor(name="Scout", position=(0, 5))
    Entity.update_all_entities_senses()
    available = get_available_actions(actor)
    move = next(
        action
        for action in available.position_actions
        if action.template_name == "Move"
    )
    target = next(
        candidate
        for candidate in move.valid_targets
        if candidate.position == (3, 5)
    )
    assert target.path is not None
    requested_path = list(target.path)
    guard = _InterruptAfterFirstCommittedStep()

    with movement_continuation_scope(guard):
        result = execute_by_index(
            actor,
            "Move",
            target.index,
            available=available,
            prefer_safe=False,
        )

    assert result is not None
    movement = cast(MovementEvent, result)
    assert not movement.canceled
    assert movement.requested_end_position == (3, 5)
    assert movement.end_position == requested_path[1]
    assert movement.path == tuple(requested_path[:2])
    assert (
        movement.termination_reason
        is MovementTerminationReason.SUBJECTIVE_REVALIDATION
    )
    assert movement.controller_revalidation is True
    assert movement.controller_revalidation_reason == "newly_visible_hostile"
    assert movement.outcome_code == "movement.subjective_revalidation"
    assert actor.position == requested_path[1]
    assert actor.action_economy.movement.normalized_score == 25

    assert len(guard.boundaries) == 1
    boundary = guard.boundaries[0]
    assert boundary.from_position == requested_path[0]
    assert boundary.to_position == requested_path[1]
    assert boundary.traversed_path == tuple(requested_path[:2])
    assert boundary.movement_spent == 5
    assert boundary.movement_remaining == 25
    assert boundary.source_event_cursor_end >= boundary.source_event_cursor_start


def test_voluntary_move_reaches_destination_before_continuation_check() -> None:
    """A final-step interruption cannot undo already completed movement."""
    reset_action_state()
    actor = create_tutorial_actor(name="Scout", position=(0, 5))
    Entity.update_all_entities_senses()
    available = get_available_actions(actor)
    move = next(
        action
        for action in available.position_actions
        if action.template_name == "Move"
    )
    target = next(
        candidate
        for candidate in move.valid_targets
        if candidate.position == (1, 5)
    )
    guard = _InterruptAfterFirstCommittedStep()

    with movement_continuation_scope(guard):
        result = execute_by_index(
            actor,
            "Move",
            target.index,
            available=available,
            prefer_safe=False,
        )

    assert result is not None
    movement = cast(MovementEvent, result)
    assert movement.end_position == (1, 5)
    assert movement.requested_end_position == (1, 5)
    assert movement.termination_reason is MovementTerminationReason.COMPLETED
    assert movement.controller_revalidation is True
    assert movement.controller_revalidation_reason == "newly_visible_hostile"
    assert movement.outcome_code == "movement.completed"
