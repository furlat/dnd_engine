"""Deterministic behavior tests for the bundled basic policy."""

from __future__ import annotations

from dnd.ai.contracts.control import (
    ActionBucket,
    ActionAffordance,
    ActionCostProfile,
    ActionEconomyState,
    ActionSourceDefinition,
    ActionTarget,
    AffordanceSet,
    DecisionEpoch,
    DecisionEpochReason,
)
from dnd.ai.contracts.decision import EndTurnIntent, ExecuteIntent, PolicyIntent
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationSessionState,
    SubjectiveWorldState,
)
from dnd.ai.contracts.semantics import (
    ActionSemantics,
    ActionTag,
    EffectOperation,
    LogicalEffect,
    SelfSetupDuration,
    SelfSetupSemantics,
)
from dnd.ai.feedback import NativeAIDecisionFeedback, NativeAIDecisionOutcome
from dnd.ai.policies.basic import (
    BASIC_POLICY_DESCRIPTOR,
    BASIC_POLICY_ID,
    BasicPolicy,
    register_basic_policy,
)
from dnd.ai.instrumentation import AIInstrumentation, AIInstrumentationContext
from dnd.ai.policy import StatelessPolicyMemory
from dnd.ai.registry import PolicyRegistry
from dnd.ai.specification import (
    PolicyCandidate,
    PolicyMetric,
    PolicyMetricValue,
)


def _metric(metric: PolicyMetric, value: float) -> PolicyMetricValue:
    return PolicyMetricValue(metric=metric, value=value)


def test_basic_policy_prioritizes_urgent_recovery_before_pressure() -> None:
    candidates = (
        PolicyCandidate(
            candidate_id="attack",
            decision="execute:attack",
            semantic_tags=frozenset({ActionTag.DAMAGE_SINGLE_TARGET}),
            metrics=(_metric(PolicyMetric.EXPECTED_DAMAGE, 100.0),),
        ),
        PolicyCandidate(
            candidate_id="heal",
            decision="execute:heal",
            semantic_tags=frozenset({ActionTag.SUPPORT_HEAL}),
            metrics=(
                _metric(PolicyMetric.URGENCY, 0.5),
                _metric(PolicyMetric.EXPECTED_HEALING, 8.0),
            ),
        ),
    )
    policy = BasicPolicy[
        tuple[PolicyCandidate[str], ...],
        StatelessPolicyMemory,
        str,
    ](
        candidate_provider=lambda state, _memory: state,
        end_turn_factory=lambda _state: "end_turn",
    )

    assert policy.descriptor.policy_id == BASIC_POLICY_ID
    assert policy.decide(candidates, StatelessPolicyMemory()) == "execute:heal"


def test_basic_policy_scores_pressure_and_uses_stable_replay_ties() -> None:
    weaker = PolicyCandidate(
        candidate_id="weak",
        decision="execute:weak",
        semantic_tags=frozenset({ActionTag.DAMAGE_SINGLE_TARGET}),
        metrics=(_metric(PolicyMetric.EXPECTED_DAMAGE, 3.0),),
    )
    stronger_late_id = PolicyCandidate(
        candidate_id="z-strong",
        decision="execute:z",
        semantic_tags=frozenset({ActionTag.DAMAGE_SINGLE_TARGET}),
        metrics=(_metric(PolicyMetric.EXPECTED_DAMAGE, 9.0),),
        replay_key=("b",),
    )
    stronger_early_key = PolicyCandidate(
        candidate_id="a-strong",
        decision="execute:a",
        semantic_tags=frozenset({ActionTag.DAMAGE_SINGLE_TARGET}),
        metrics=(_metric(PolicyMetric.EXPECTED_DAMAGE, 9.0),),
        replay_key=("a",),
    )
    policy = BasicPolicy[
        tuple[PolicyCandidate[str], ...],
        StatelessPolicyMemory,
        str,
    ](
        candidate_provider=lambda state, _memory: state,
        end_turn_factory=lambda _state: "end_turn",
    )

    assert (
        policy.decide(
            (stronger_late_id, weaker, stronger_early_key),
            StatelessPolicyMemory(),
        )
        == "execute:a"
    )
    assert (
        policy.decide(
            (stronger_early_key, stronger_late_id, weaker),
            StatelessPolicyMemory(),
        )
        == "execute:a"
    )


def test_basic_policy_ends_turn_when_no_affordable_candidate_matches() -> None:
    unavailable = PolicyCandidate(
        candidate_id="unavailable",
        decision="execute:unavailable",
        semantic_tags=frozenset({ActionTag.DAMAGE_SINGLE_TARGET}),
        affordable=False,
    )
    policy = BasicPolicy[
        tuple[PolicyCandidate[str], ...],
        StatelessPolicyMemory,
        str,
    ](
        candidate_provider=lambda state, _memory: state,
        end_turn_factory=lambda _state: "end_turn",
    )

    assert policy.decide((unavailable,), StatelessPolicyMemory()) == "end_turn"
    assert policy.decide((), StatelessPolicyMemory()) == "end_turn"


def test_registered_basic_policy_consumes_canonical_world_and_intent_contracts() -> None:
    semantics = ActionSemantics(
        semantic_id="attack.weapon",
        tags=frozenset(
            {ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}
        ),
    )
    source = ActionSourceDefinition(
        source_action_id="source:attack",
        bucket="entity_actions",
        template_name="Attack",
        display_name="Attack",
        action_category="attack",
        target_type="entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        semantic_key="action.attack",
        semantic_id=semantics.semantic_id,
        semantics_ref="attack-semantics",
    )
    row = ActionAffordance(
        row_id="row:attack:enemy",
        source=source,
        targets=(
            ActionTarget(
                index=0,
                target_uuid="enemy",
                target_name="Enemy",
                position=(1, 0),
                distance=5,
            ),
        ),
    )
    affordances = AffordanceSet(
        actor_uuid="actor",
        computed_at_observation_cursor=1,
        entity_actions=(row,),
        semantic_catalog={"attack-semantics": semantics},
    )
    epoch = DecisionEpoch(
        epoch_id="epoch",
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
    world = SubjectiveWorldState(
        observation_cursor=1,
        session=ObservationSessionState(
            session_id="session",
            player_type="native_ai",
            name="AI",
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
                faction="heroes",
            ),
            "enemy": ObservationEntityFact(
                uuid="enemy",
                name="Enemy",
                knowledge_state=KnowledgeState.VISIBLE,
                position=(1, 0),
                faction="monsters",
                is_dead=False,
            ),
        },
        current_epoch=epoch,
        epoch_cursor=1,
    )
    registry: PolicyRegistry[SubjectiveWorldState, PolicyIntent] = PolicyRegistry()
    register_basic_policy(registry)

    assert registry.require_descriptor(BASIC_POLICY_ID) == BASIC_POLICY_DESCRIPTOR
    binding = registry.create_binding(
        BASIC_POLICY_ID,
        instrumentation=AIInstrumentation(),
        instrumentation_context=AIInstrumentationContext(
            game_id="game",
            assignment_id="assignment",
            actor_uuid="actor",
            decision_id="assignment-initialization",
            policy=BASIC_POLICY_DESCRIPTOR,
        ),
    )
    decision = binding.decide(world)

    assert decision == ExecuteIntent(row_id="row:attack:enemy")

    friendly_world = world.model_copy(
        update={
            "known_entities": {
                **world.known_entities,
                "enemy": world.known_entities["enemy"].model_copy(
                    update={"faction": "heroes"}
                ),
            }
        },
    )
    assert binding.decide(friendly_world) == EndTurnIntent()


def _canonical_binding():
    registry: PolicyRegistry[SubjectiveWorldState, PolicyIntent] = (
        PolicyRegistry()
    )
    register_basic_policy(registry)
    return registry.create_binding(
        BASIC_POLICY_ID,
        instrumentation=AIInstrumentation(),
        instrumentation_context=AIInstrumentationContext(
            game_id="game",
            assignment_id="assignment",
            actor_uuid="actor",
            decision_id="assignment-initialization",
            policy=BASIC_POLICY_DESCRIPTOR,
        ),
    )


def _policy_row(
    *,
    row_id: str,
    bucket: ActionBucket,
    semantics: ActionSemantics,
    target_position: tuple[int, int] | None = None,
    path: tuple[tuple[int, int], ...] = (),
) -> ActionAffordance:
    source = ActionSourceDefinition(
        source_action_id=f"source:{row_id}",
        bucket=bucket,
        template_name="Policy Fixture",
        display_name="Policy Fixture",
        action_category=(
            "movement"
            if ActionTag.MOVEMENT_VOLUNTARY in semantics.tags
            else "attack"
            if ActionTag.ATTACK_WEAPON in semantics.tags
            else "ability"
        ),
        target_type="position" if target_position is not None else "self",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        semantic_key=f"fixture.{semantics.semantic_id}",
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics.semantic_id,
    )
    targets = (
        (
            ActionTarget(
                index=0,
                target_uuid=(
                    "enemy"
                    if ActionTag.ATTACK_WEAPON in semantics.tags
                    else None
                ),
                target_name=(
                    "Enemy"
                    if ActionTag.ATTACK_WEAPON in semantics.tags
                    else None
                ),
                position=target_position,
                path=path,
            ),
        )
        if target_position is not None
        else ()
    )
    return ActionAffordance(
        row_id=row_id,
        source=source,
        targets=targets,
    )


def _policy_world(
    *,
    rows: tuple[ActionAffordance, ...],
    semantics: tuple[ActionSemantics, ...],
    actor_position: tuple[int, int],
    epoch_id: str,
    epoch_index: int,
    actor_is_concentrating: bool = False,
) -> SubjectiveWorldState:
    affordances = AffordanceSet(
        actor_uuid="actor",
        computed_at_observation_cursor=epoch_index,
        entity_actions=tuple(
            row for row in rows if row.source.bucket == "entity_actions"
        ),
        position_actions=tuple(
            row for row in rows if row.source.bucket == "position_actions"
        ),
        self_actions=tuple(
            row for row in rows if row.source.bucket == "self_actions"
        ),
        semantic_catalog={
            semantic.semantic_id: semantic
            for semantic in semantics
        },
    )
    return SubjectiveWorldState(
        observation_cursor=epoch_index,
        session=ObservationSessionState(
            session_id="assignment",
            player_type="native_ai",
            name="AI",
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
                position=actor_position,
                normal_hp=20,
                max_hp=20,
                faction="heroes",
                is_concentrating=actor_is_concentrating,
            ),
            "enemy": ObservationEntityFact(
                uuid="enemy",
                name="Enemy",
                knowledge_state=KnowledgeState.VISIBLE,
                position=(5, 0),
                normal_hp=20,
                max_hp=20,
                faction="monsters",
                is_dead=False,
            ),
        },
        current_epoch=DecisionEpoch(
            epoch_id=epoch_id,
            epoch_index=epoch_index,
            basis_observation_cursor=epoch_index,
            reason=(
                DecisionEpochReason.TURN_START
                if epoch_index == 1
                else DecisionEpochReason.ACTION_COMPLETED
            ),
            actor_uuid="actor",
            round_number=1,
            turn_index=0,
            economy=ActionEconomyState(
                actor_uuid="actor",
                actions=4,
                movement_remaining=30,
                extra_attacks=2,
                meaningful_commands_remaining=True,
            ),
            affordances=affordances,
        ),
        epoch_cursor=epoch_index,
    )


def _executed(row_id: str, decision_id: str) -> NativeAIDecisionFeedback:
    return NativeAIDecisionFeedback(
        decision_id=decision_id,
        actor_uuid="actor",
        epoch_id=f"epoch:{decision_id}",
        row_id=row_id,
        outcome=NativeAIDecisionOutcome.EXECUTED,
    )


def test_basic_policy_rejects_zero_value_defense_and_does_not_repeat_setup() -> None:
    zero_value_defense = ActionSemantics(
        semantic_id="defense.zero_value",
        tags=frozenset({ActionTag.DEFENSE_SELF}),
    )
    useful_setup = ActionSemantics(
        semantic_id="setup.useful",
        tags=frozenset({ActionTag.SETUP_SELF, ActionTag.DEFENSE_SELF}),
        self_setup=SelfSetupSemantics(
            duration=SelfSetupDuration.CURRENT_TURN,
            armor_class_bonus=2,
        ),
    )
    zero_row = _policy_row(
        row_id="row:defense",
        bucket="self_actions",
        semantics=zero_value_defense,
    )
    setup_row = _policy_row(
        row_id="row:setup",
        bucket="self_actions",
        semantics=useful_setup,
    )
    binding = _canonical_binding()
    only_zero = _policy_world(
        rows=(zero_row,),
        semantics=(zero_value_defense,),
        actor_position=(0, 0),
        epoch_id="epoch-zero",
        epoch_index=1,
    )
    binding.reduce_state(only_zero)
    assert binding.decide(only_zero) == EndTurnIntent()

    first = _policy_world(
        rows=(setup_row,),
        semantics=(useful_setup,),
        actor_position=(0, 0),
        epoch_id="epoch-setup-1",
        epoch_index=1,
    )
    binding.reduce_state(first)
    assert binding.decide(first) == ExecuteIntent(row_id="row:setup")
    binding.reduce_feedback(_executed("row:setup", "1"))

    repeated = _policy_world(
        rows=(setup_row,),
        semantics=(useful_setup,),
        actor_position=(0, 0),
        epoch_id="epoch-setup-2",
        epoch_index=2,
    )
    binding.reduce_state(repeated)
    assert binding.decide(repeated) == EndTurnIntent()


def test_basic_policy_uses_one_full_advance_and_never_revisits_turn_positions() -> None:
    movement = ActionSemantics(
        semantic_id="movement.advance",
        tags=frozenset(
            {
                ActionTag.MOVEMENT_VOLUNTARY,
                ActionTag.INFORMATION_EXPLORE,
            }
        ),
    )
    short = _policy_row(
        row_id="row:move:short",
        bucket="position_actions",
        semantics=movement,
        target_position=(1, 0),
        path=((0, 0), (1, 0)),
    )
    full = _policy_row(
        row_id="row:move:full",
        bucket="position_actions",
        semantics=movement,
        target_position=(4, 0),
        path=((0, 0), (1, 0), (2, 0), (3, 0), (4, 0)),
    )
    binding = _canonical_binding()
    first = _policy_world(
        rows=(short, full),
        semantics=(movement,),
        actor_position=(0, 0),
        epoch_id="epoch-move-1",
        epoch_index=1,
    )
    binding.reduce_state(first)

    selected = binding.decide(first)
    assert selected == ExecuteIntent(row_id="row:move:full")
    binding.reduce_feedback(_executed("row:move:full", "1"))

    back = _policy_row(
        row_id="row:move:back",
        bucket="position_actions",
        semantics=movement,
        target_position=(0, 0),
        path=((4, 0), (3, 0), (2, 0), (1, 0), (0, 0)),
    )
    zero = _policy_row(
        row_id="row:move:zero",
        bucket="position_actions",
        semantics=movement,
        target_position=(4, 0),
        path=((4, 0),),
    )
    second = _policy_world(
        rows=(back, zero),
        semantics=(movement,),
        actor_position=(4, 0),
        epoch_id="epoch-move-2",
        epoch_index=2,
    )
    binding.reduce_state(second)

    assert binding.decide(second) == EndTurnIntent()


def test_basic_policy_memory_preserves_multiple_useful_attacks_in_one_turn() -> None:
    attack = ActionSemantics(
        semantic_id="attack.weapon",
        tags=frozenset(
            {ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}
        ),
    )
    first_row = _policy_row(
        row_id="row:attack:first",
        bucket="entity_actions",
        semantics=attack,
        target_position=(5, 0),
    )
    second_row = _policy_row(
        row_id="row:attack:second",
        bucket="entity_actions",
        semantics=attack,
        target_position=(5, 0),
    )
    binding = _canonical_binding()
    first = _policy_world(
        rows=(first_row,),
        semantics=(attack,),
        actor_position=(4, 0),
        epoch_id="epoch-attack-1",
        epoch_index=1,
    )
    binding.reduce_state(first)
    assert binding.decide(first) == ExecuteIntent(
        row_id="row:attack:first"
    )
    binding.reduce_feedback(_executed("row:attack:first", "1"))

    second = _policy_world(
        rows=(second_row,),
        semantics=(attack,),
        actor_position=(4, 0),
        epoch_id="epoch-attack-2",
        epoch_index=2,
    )
    binding.reduce_state(second)
    assert binding.decide(second) == ExecuteIntent(
        row_id="row:attack:second"
    )


def test_basic_policy_rejects_zero_utility_inverse_object_toggles() -> None:
    activate = ActionSemantics(
        semantic_id="interaction.fixture.activate",
        tags=frozenset({ActionTag.INTERACTION_OBJECT}),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="selected_object.active",
                operation=EffectOperation.SET,
                value=True,
            ),
        ),
    )
    deactivate = ActionSemantics(
        semantic_id="interaction.fixture.deactivate",
        tags=frozenset({ActionTag.INTERACTION_OBJECT}),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="selected_object.active",
                operation=EffectOperation.SET,
                value=False,
            ),
        ),
    )
    activate_row = _policy_row(
        row_id="row:activate",
        bucket="self_actions",
        semantics=activate,
    )
    deactivate_row = _policy_row(
        row_id="row:deactivate",
        bucket="self_actions",
        semantics=deactivate,
    )
    binding = _canonical_binding()
    first = _policy_world(
        rows=(activate_row,),
        semantics=(activate,),
        actor_position=(0, 0),
        epoch_id="epoch-toggle-1",
        epoch_index=1,
    )
    binding.reduce_state(first)
    first_decision = binding.decide(first)

    second = _policy_world(
        rows=(deactivate_row,),
        semantics=(deactivate,),
        actor_position=(0, 0),
        epoch_id="epoch-toggle-2",
        epoch_index=2,
    )
    binding.reduce_state(second)
    second_decision = binding.decide(second)

    assert (first_decision, second_decision) == (
        EndTurnIntent(),
        EndTurnIntent(),
    )


def test_basic_policy_does_not_voluntarily_tear_down_useful_concentration() -> None:
    concentration_drop = ActionSemantics(
        semantic_id="concentration.end",
        tags=frozenset({ActionTag.CONCENTRATION_END}),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.concentration",
                operation=EffectOperation.REMOVE,
            ),
        ),
    )
    row = _policy_row(
        row_id="row:drop-concentration",
        bucket="self_actions",
        semantics=concentration_drop,
    )
    binding = _canonical_binding()
    world = _policy_world(
        rows=(row,),
        semantics=(concentration_drop,),
        actor_position=(0, 0),
        actor_is_concentrating=True,
        epoch_id="epoch-concentration",
        epoch_index=1,
    )
    binding.reduce_state(world)

    assert binding.decide(world) == EndTurnIntent()
