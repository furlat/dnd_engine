"""Focused regressions for the single in-process native AI execution path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

import pytest

from dnd.action_dispatch import ActionDispatchError, dispatch_available_action
from dnd.actions_functional import get_available_actions
from dnd.ai.contracts.decision import EndTurnIntent, ExecuteIntent, PolicyIntent
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    BoundedAIInstrumentationSink,
)
from dnd.ai.feedback import NativeAIDecisionFeedback, NativeAIDecisionOutcome
from dnd.ai.policy import PolicyDescriptor
from dnd.ai.registry import PolicyRegistry
from dnd.ai.runtime.assignment_lifecycle import AIAssignmentState
from dnd.ai.runtime.controller import NativeAIController
from dnd.ai.runtime.decision_epoch import (
    _build_affordance_set_and_execution_authority_from_actions,
)
from dnd.controller import Controller, TurnContext
from dnd.core.base_actions import (
    ActionAvailabilityStatus,
    ActionCategory,
    AvailableActionInfo,
    AvailableActionsResult,
    TargetType,
)
from tests.content_identity import synthetic_action_attribution
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from tests.manual.test_09_action_discovery_and_costs import (
    create_tutorial_actor,
    reset_action_state,
)


STATEFUL_DESCRIPTOR = PolicyDescriptor(
    policy_id="test.stateful",
    version="1",
    display_name="Stateful test policy",
)
END_DESCRIPTOR = PolicyDescriptor(
    policy_id="test.end",
    version="1",
    display_name="End test policy",
)
FORGED_DESCRIPTOR = PolicyDescriptor(
    policy_id="test.forged",
    version="1",
    display_name="Forged-row test policy",
)


@dataclass
class _StatefulMemory:
    projected_states: int = 0
    feedback_outcomes: tuple[NativeAIDecisionOutcome, ...] = ()


class _DashThenEndPolicy:
    descriptor = STATEFUL_DESCRIPTOR

    def decide(
        self,
        state: SubjectiveWorldState,
        memory: _StatefulMemory,
    ) -> PolicyIntent:
        if memory.projected_states > 1:
            return EndTurnIntent()
        epoch = state.current_epoch
        assert epoch is not None
        dash = next(
            row
            for row in epoch.affordances.all_rows
            if row.template_name == "Dash"
        )
        return ExecuteIntent(row_id=dash.row_id)


class _EndPolicy:
    descriptor = END_DESCRIPTOR

    def decide(
        self,
        state: SubjectiveWorldState,
        memory: _StatefulMemory,
    ) -> PolicyIntent:
        del state
        return EndTurnIntent()


class _ForgedRowPolicy:
    descriptor = FORGED_DESCRIPTOR

    def decide(
        self,
        state: SubjectiveWorldState,
        memory: _StatefulMemory,
    ) -> PolicyIntent:
        del state
        return ExecuteIntent(row_id="forged|not-in-current-epoch")


def _reduce_state(
    memory: _StatefulMemory,
    state: SubjectiveWorldState,
) -> None:
    assert state.current_epoch is not None
    memory.projected_states += 1


def _reduce_feedback(
    memory: _StatefulMemory,
    feedback: NativeAIDecisionFeedback,
) -> None:
    memory.feedback_outcomes = (
        *memory.feedback_outcomes,
        feedback.outcome,
    )


def _registry(
    descriptor: PolicyDescriptor,
    policy_factory: type[_DashThenEndPolicy]
    | type[_EndPolicy]
    | type[_ForgedRowPolicy],
) -> PolicyRegistry[SubjectiveWorldState, PolicyIntent]:
    registry: PolicyRegistry[SubjectiveWorldState, PolicyIntent] = (
        PolicyRegistry()
    )
    registry.register(
        descriptor=descriptor,
        policy_factory=policy_factory,
        memory_factory=_StatefulMemory,
        reduce_state=_reduce_state,
        reduce_feedback=_reduce_feedback,
    )
    return registry


def _context(
    actor: Entity,
    *,
    turn_index: int = 0,
    initiative_order: tuple[UUID, ...] = (),
) -> TurnContext:
    economy = actor.action_economy
    return TurnContext(
        source_entity_uuid=actor.uuid,
        entity_uuid=actor.uuid,
        round_number=1,
        turn_index=turn_index,
        actions_remaining=economy.actions.normalized_score,
        bonus_actions_remaining=economy.bonus_actions.normalized_score,
        reactions_remaining=economy.reactions.normalized_score,
        movement_remaining=economy.movement.normalized_score,
        initiative_order=list(initiative_order),
    )


def _reset() -> None:
    reset_action_state()
    Controller.clear_registry()


def test_native_assignment_executes_stateful_custom_policy_without_timing_code() -> None:
    """Core timing wraps logic-only custom policy and exact action dispatch."""
    _reset()
    actor = create_tutorial_actor(name="Native actor", position=(2, 2))
    Entity.update_all_entities_senses()
    sink = BoundedAIInstrumentationSink()
    instrumentation = AIInstrumentation(sink=sink)
    controller = NativeAIController.create(
        source_entity_uuid=actor.uuid,
        game_id="game",
        assignment_id="side-a",
        controlled_entity_uuids=(actor.uuid,),
        policy_id=STATEFUL_DESCRIPTOR.policy_id,
        registry=_registry(STATEFUL_DESCRIPTOR, _DashThenEndPolicy),
        instrumentation=instrumentation,
    )
    controller.start([actor])

    first = controller.execute_next_action(actor, _context(actor))
    second = controller.execute_next_action(actor, _context(actor))

    assert first.event is not None
    assert first.event.canceled is False
    assert first.end_turn is False
    assert second.event is None
    assert second.end_turn is True
    memory = cast(_StatefulMemory, controller.assignment.policy_binding.memory)
    assert memory.projected_states == 2
    assert memory.feedback_outcomes == (
        NativeAIDecisionOutcome.EXECUTED,
        NativeAIDecisionOutcome.END_TURN,
    )
    assert not hasattr(controller.assignment.policy_binding.policy, "instrumentation")
    assert [feedback.outcome for feedback in controller.assignment.feedback] == [
        NativeAIDecisionOutcome.EXECUTED,
        NativeAIDecisionOutcome.END_TURN,
    ]

    controller.close()
    phases = {timing.phase for timing in sink.timing_snapshot()}
    assert {
        AIExecutionPhase.ASSIGNMENT_INITIALIZATION,
        AIExecutionPhase.POLICY_CONSTRUCTION,
        AIExecutionPhase.MEMORY_CONSTRUCTION,
        AIExecutionPhase.DECISION_TOTAL,
        AIExecutionPhase.STATE_PROJECTION,
        AIExecutionPhase.MEMORY_REDUCTION,
        AIExecutionPhase.POLICY_DECISION,
        AIExecutionPhase.DECISION_VALIDATION,
        AIExecutionPhase.ACTION_EXECUTION,
        AIExecutionPhase.FEEDBACK_REDUCTION,
        AIExecutionPhase.ASSIGNMENT_TEARDOWN,
    }.issubset(phases)
    assert sum(
        timing.phase is AIExecutionPhase.MEMORY_REDUCTION
        for timing in sink.timing_snapshot()
    ) == 2
    assert sum(
        timing.phase is AIExecutionPhase.FEEDBACK_REDUCTION
        for timing in sink.timing_snapshot()
    ) == 2


def test_native_controller_shares_one_side_assignment_but_not_opponent_memory() -> None:
    """All same-side actors share state; independently created sides do not."""
    _reset()
    first = create_tutorial_actor(name="First", position=(2, 2))
    second = create_tutorial_actor(name="Second", position=(3, 2))
    opponent = create_tutorial_actor(
        name="Opponent",
        position=(8, 8),
        faction="monsters",
    )
    Entity.update_all_entities_senses()
    registry = _registry(END_DESCRIPTOR, _EndPolicy)
    side = NativeAIController.create(
        source_entity_uuid=first.uuid,
        game_id="game",
        assignment_id="heroes",
        controlled_entity_uuids=(first.uuid, second.uuid),
        policy_id=END_DESCRIPTOR.policy_id,
        registry=registry,
    )
    enemy = NativeAIController.create(
        source_entity_uuid=opponent.uuid,
        game_id="game",
        assignment_id="monsters",
        controlled_entity_uuids=(opponent.uuid,),
        policy_id=END_DESCRIPTOR.policy_id,
        registry=registry,
    )
    side.start([first, second])
    side_assignment = side.assignment
    side.execute_next_action(
        first,
        _context(first, turn_index=0, initiative_order=(first.uuid, second.uuid)),
    )
    side.execute_next_action(
        second,
        _context(second, turn_index=1, initiative_order=(first.uuid, second.uuid)),
    )
    enemy.start([opponent])
    enemy.execute_next_action(opponent, _context(opponent))

    assert side.assignment is side_assignment
    assert cast(
        _StatefulMemory,
        side.assignment.policy_binding.memory,
    ).projected_states == 2
    assert cast(
        _StatefulMemory,
        enemy.assignment.policy_binding.memory,
    ).projected_states == 1
    assert side.assignment.world is not enemy.assignment.world
    assert side.assignment.state is AIAssignmentState.STARTED
    side.close()
    side.close()
    assert side.assignment.state is AIAssignmentState.CLOSED


def test_native_policy_cannot_execute_a_forged_epoch_row() -> None:
    """A custom policy receives no authority beyond current public row ids."""
    _reset()
    actor = create_tutorial_actor(name="Actor", position=(2, 2))
    Entity.update_all_entities_senses()
    controller = NativeAIController.create(
        source_entity_uuid=actor.uuid,
        game_id="game",
        assignment_id="forged",
        controlled_entity_uuids=(actor.uuid,),
        policy_id=FORGED_DESCRIPTOR.policy_id,
        registry=_registry(FORGED_DESCRIPTOR, _ForgedRowPolicy),
    )
    controller.start([actor])
    actions_before = actor.action_economy.actions.normalized_score

    step = controller.execute_next_action(actor, _context(actor))

    assert step.end_turn is True
    assert step.event is None
    assert actor.action_economy.actions.normalized_score == actions_before
    assert controller.assignment.feedback[-1].outcome is (
        NativeAIDecisionOutcome.REJECTED
    )


def test_shared_dispatcher_rejects_equal_but_non_authoritative_target() -> None:
    """Action dispatch requires the exact target object discovered in one row."""
    _reset()
    actor = create_tutorial_actor(name="Actor", position=(2, 2))
    Entity.update_all_entities_senses()
    available = get_available_actions(actor)
    dash = next(
        row for row in available.self_actions if row.template_name == "Dash"
    )
    target = dash.valid_targets[0]
    copied_target = target.model_copy(deep=True)

    with pytest.raises(ActionDispatchError, match="exact target"):
        dispatch_available_action(
            actor,
            action_info=dash,
            target=copied_target,
        )


def test_bundled_basic_policy_executes_natively_without_transport() -> None:
    """The vendored policy performs an adjacent attack entirely in process."""
    _reset()
    actor = create_goblin(name="Native Goblin", position=(5, 5), faction="a")
    create_skeleton(name="Target", position=(6, 5), faction="b")
    Entity.update_all_entities_senses()
    controller = NativeAIController.create(
        source_entity_uuid=actor.uuid,
        game_id="game",
        assignment_id="basic",
        controlled_entity_uuids=(actor.uuid,),
    )
    controller.start([actor])

    step = controller.execute_next_action(actor, _context(actor))

    assert step.event is not None
    assert step.event.canceled is False
    assert controller.assignment.feedback[-1].outcome is (
        NativeAIDecisionOutcome.EXECUTED
    )


def test_native_epoch_omits_affordable_action_without_exact_target_binding() -> None:
    """A public executable row cannot outlive an empty engine target set."""
    _reset()
    actor = create_tutorial_actor(name="Actor", position=(2, 2))
    targetless_spell = AvailableActionInfo(
        template_name="Targetless__slot_3",
        semantic_key="test.targetless",
        behavior_attribution=synthetic_action_attribution(
            "action.targetless_spell",
        ),
        target_type=TargetType.POSITION_AOE,
        availability_status=ActionAvailabilityStatus.NO_VALID_TARGETS,
        valid_targets=[],
        can_afford=True,
        display_name="Targetless",
        cost_type="spell_slot_3",
        cost_amount=1,
        action_category=ActionCategory.SPELL,
        damage_types=["lightning"],
    )
    actions = AvailableActionsResult(
        entity_uuid=actor.uuid,
        position_actions=[targetless_spell],
    )

    affordances, authority = (
        _build_affordance_set_and_execution_authority_from_actions(
            actor,
            actions,
            observation_cursor=1,
        )
    )

    assert affordances.position_actions == []
    bindings = tuple(
        authority.binding_for(row)
        for row in (
            *affordances.entity_actions,
            *affordances.position_actions,
            *affordances.self_actions,
            *affordances.object_actions,
        )
    )
    assert all(
        binding is not None and binding.target is not None
        for binding in bindings
    )
