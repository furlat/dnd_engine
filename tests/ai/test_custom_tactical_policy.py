"""Canonical registration and behavior tests for the custom tactical example."""

from __future__ import annotations

from typing import cast

from custom_ai.tactical import (
    TACTICAL_POLICY_DESCRIPTOR,
    TACTICAL_POLICY_ID,
    TacticalPolicyMemory,
    register_tactical_policy,
)
from dnd.ai.contracts.control import (
    ActionAffordance,
    ActionCostProfile,
    ActionEconomyState,
    ActionSourceDefinition,
    ActionTarget,
    AffordanceSet,
    DecisionEpoch,
    DecisionEpochReason,
)
from dnd.ai.contracts.decision import ExecuteIntent, PolicyIntent
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationSessionState,
    SubjectiveWorldState,
)
from dnd.ai.contracts.semantics import ActionSemantics, ActionTag
from dnd.ai.feedback import NativeAIDecisionFeedback, NativeAIDecisionOutcome
from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    AIInstrumentationContext,
    BoundedAIInstrumentationSink,
)
from dnd.ai.registry import PolicyRegistry
from dnd.ai.runner import InstrumentedPolicyRunner


def _attack_row(target_uuid: str, *, order: int) -> ActionAffordance:
    source = ActionSourceDefinition(
        source_action_id=f"source:attack:{order}",
        bucket="entity_actions",
        template_name="Attack",
        display_name="Attack",
        action_category="attack",
        target_type="entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        semantic_key="action.attack",
        semantic_id="attack.weapon",
        semantics_ref="attack-semantics",
    )
    return ActionAffordance(
        row_id=f"row:attack:{target_uuid}",
        source=source,
        targets=(
            ActionTarget(
                index=order,
                target_uuid=target_uuid,
                target_name=target_uuid,
                position=(order + 1, 0),
                distance=(order + 1) * 5,
            ),
        ),
    )


def _world(
    *,
    epoch_id: str,
    enemy_a_hp: int,
    enemy_b_hp: int,
    row_order: tuple[str, str] = ("enemy-b", "enemy-a"),
) -> SubjectiveWorldState:
    semantics = ActionSemantics(
        semantic_id="attack.weapon",
        tags=frozenset(
            {ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}
        ),
    )
    rows_by_target = {
        target_uuid: _attack_row(target_uuid, order=index)
        for index, target_uuid in enumerate(row_order)
    }
    affordances = AffordanceSet(
        actor_uuid="actor",
        computed_at_observation_cursor=1,
        entity_actions=tuple(rows_by_target.values()),
        semantic_catalog={"attack-semantics": semantics},
    )
    epoch = DecisionEpoch(
        epoch_id=epoch_id,
        epoch_index=1,
        basis_observation_cursor=1,
        reason=DecisionEpochReason.TURN_START,
        actor_uuid="actor",
        round_number=1,
        turn_index=0,
        economy=ActionEconomyState(
            actor_uuid="actor",
            actions=1,
            meaningful_commands_remaining=True,
        ),
        affordances=affordances,
    )
    return SubjectiveWorldState(
        observation_cursor=1,
        session=ObservationSessionState(
            session_id="session",
            player_type="native_ai",
            name="Tactical AI",
            connection_status="connected",
            controlled_entity_uuids=["actor"],
            active_entity_uuid="actor",
            active_entity_name="Actor",
            is_my_turn=True,
        ),
        known_entities={
            "actor": ObservationEntityFact(
                uuid="actor",
                name="Actor",
                knowledge_state=KnowledgeState.VISIBLE,
                controlled=True,
                position=(0, 0),
                normal_hp=20,
                max_hp=20,
                healing_blocked=False,
                faction="heroes",
            ),
            "enemy-a": ObservationEntityFact(
                uuid="enemy-a",
                name="Enemy A",
                knowledge_state=KnowledgeState.VISIBLE,
                position=(1, 0),
                normal_hp=enemy_a_hp,
                hp=enemy_a_hp,
                max_hp=20,
                faction="monsters",
                is_dead=False,
            ),
            "enemy-b": ObservationEntityFact(
                uuid="enemy-b",
                name="Enemy B",
                knowledge_state=KnowledgeState.VISIBLE,
                position=(2, 0),
                normal_hp=enemy_b_hp,
                hp=enemy_b_hp,
                max_hp=20,
                faction="monsters",
                is_dead=False,
            ),
        },
        current_epoch=epoch,
        epoch_cursor=1,
    )


def _registry() -> PolicyRegistry[SubjectiveWorldState, PolicyIntent]:
    registry: PolicyRegistry[SubjectiveWorldState, PolicyIntent] = (
        PolicyRegistry()
    )
    register_tactical_policy(registry)
    return registry


def _context(decision_id: str) -> AIInstrumentationContext:
    return AIInstrumentationContext(
        game_id="game",
        assignment_id="side",
        actor_uuid="actor",
        decision_id=decision_id,
        policy=TACTICAL_POLICY_DESCRIPTOR,
    )


def test_custom_tactical_registration_creates_fresh_typed_assignment_memory() -> None:
    registry = _registry()
    instrumentation = AIInstrumentation()

    first = registry.create_binding(
        TACTICAL_POLICY_ID,
        instrumentation=instrumentation,
        instrumentation_context=_context("initialize-1"),
    )
    second = registry.create_binding(
        TACTICAL_POLICY_ID,
        instrumentation=instrumentation,
        instrumentation_context=_context("initialize-2"),
    )

    assert registry.require_descriptor(TACTICAL_POLICY_ID) == (
        TACTICAL_POLICY_DESCRIPTOR
    )
    assert first.policy is not second.policy
    assert isinstance(first.memory, TacticalPolicyMemory)
    assert isinstance(second.memory, TacticalPolicyMemory)
    assert first.memory is not second.memory


def test_custom_tactical_focus_is_stateful_deterministic_and_decide_is_pure() -> None:
    binding = _registry().create_binding(
        TACTICAL_POLICY_ID,
        instrumentation=AIInstrumentation(),
        instrumentation_context=_context("initialize"),
    )
    first_world = _world(
        epoch_id="epoch-1",
        enemy_a_hp=4,
        enemy_b_hp=8,
    )
    binding.reduce_state(first_world)
    memory = cast(TacticalPolicyMemory, binding.memory)
    before_decide = memory.snapshot()

    first = binding.decide(first_world)
    repeated = binding.decide(first_world)

    assert first == ExecuteIntent(row_id="row:attack:enemy-a")
    assert repeated == first
    assert memory.snapshot() == before_decide
    assert memory.actor("actor").focused_target_uuid == "enemy-a"

    second_world = _world(
        epoch_id="epoch-2",
        enemy_a_hp=10,
        enemy_b_hp=1,
        row_order=("enemy-a", "enemy-b"),
    )
    binding.reduce_state(second_world)

    assert binding.decide(second_world) == ExecuteIntent(
        row_id="row:attack:enemy-a"
    )

    fresh = _registry().create_binding(
        TACTICAL_POLICY_ID,
        instrumentation=AIInstrumentation(),
        instrumentation_context=_context("fresh-initialize"),
    )
    fresh.reduce_state(second_world)
    assert fresh.decide(second_world) == ExecuteIntent(
        row_id="row:attack:enemy-b"
    )


def test_custom_tactical_feedback_reducer_blocks_failed_row_only_in_its_binding() -> None:
    binding = _registry().create_binding(
        TACTICAL_POLICY_ID,
        instrumentation=AIInstrumentation(),
        instrumentation_context=_context("initialize"),
    )
    world = _world(epoch_id="epoch", enemy_a_hp=4, enemy_b_hp=8)
    binding.reduce_state(world)
    selected = binding.decide(world)
    assert isinstance(selected, ExecuteIntent)
    binding.reduce_feedback(
        NativeAIDecisionFeedback(
            decision_id="decision",
            actor_uuid="actor",
            epoch_id="epoch",
            row_id=selected.row_id,
            outcome=NativeAIDecisionOutcome.CANCELED,
        )
    )

    assert binding.decide(world) == ExecuteIntent(
        row_id="row:attack:enemy-b"
    )


def test_core_instrumentation_measures_custom_policy_without_policy_timing_code() -> None:
    sink = BoundedAIInstrumentationSink()
    instrumentation = AIInstrumentation(sink=sink)
    binding = _registry().create_binding(
        TACTICAL_POLICY_ID,
        instrumentation=instrumentation,
        instrumentation_context=_context("initialize"),
    )
    world = _world(epoch_id="epoch", enemy_a_hp=4, enemy_b_hp=8)
    binding.reduce_state(world)
    runner: InstrumentedPolicyRunner[
        SubjectiveWorldState,
        PolicyIntent,
    ] = InstrumentedPolicyRunner(instrumentation)

    decision = runner.decide(
        binding=binding,
        state=world,
        context=_context("decision"),
    )

    assert decision == ExecuteIntent(row_id="row:attack:enemy-a")
    assert tuple(timing.phase for timing in sink.timing_snapshot()) == (
        AIExecutionPhase.POLICY_CONSTRUCTION,
        AIExecutionPhase.MEMORY_CONSTRUCTION,
        AIExecutionPhase.POLICY_DECISION,
    )
