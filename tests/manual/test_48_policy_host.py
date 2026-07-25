"""Transport-free lifecycle checks for the shared typed policy host."""

from __future__ import annotations

from typing import AbstractSet

import pytest

import ai.policy.host as policy_host_module
import ai.policy.routines as policy_routines

from ai.policy import (
    AgentCommandType,
    PolicyLogicalTag,
    command_from_policy_decision,
)
from ai.knowledge import derive_agent_facts
from dnd.ai.contracts.observation import (
    AdjacentOffset,
    KnowledgeState,
    ObservationEffectProtection,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationSessionState,
    ObservationTileFact,
    SubjectiveWorldState,
    SpatialDomainKnowledge,
)
from ai.policy import (
    AUGMENT_THEN_ACT,
    APPROACH_OPEN_REASSESS,
    ENABLE_THEN_ACT,
    TRANSFORM_THEN_ACT,
    DuplicateEpochSubmissionError,
    PolicyContextAlignmentError,
    PolicyExecutionConstraints,
    PolicyHost,
    PolicyDecisionTelemetry,
    PolicyResultDisposition,
    PolicyResultRecord,
)
from ai.policy.contracts import (
    CapabilityModelStatus,
    PolicyDecision,
    PolicyEvidence,
    PolicyGoal,
    PolicyProposal,
    SpacingEvidence,
)
from dnd.ai.contracts.decision import EndTurnIntent, ExecuteIntent
from ai.policy.candidates import build_policy_candidate_set
from ai.policy.generations import (
    BASELINE_GENERATION_ID,
    CANDIDATE_GENERATION_ID,
    get_policy_implementation,
    list_policy_generations,
)
from ai.policy.generations.registry import EXPECTED_V31_BEHAVIOR_SHA256
from dnd.ai.contracts.control import (
    ActionAffordance,
    ActionCapability,
    ActionCostProfile,
    ActionEconomyState,
    ActionOutcomeProfile,
    ActionResolutionStatus,
    ActionTarget,
    AffordanceSet,
    CommandResult,
    CommandResultStatus,
    DamageRollProfile,
    DecisionEpoch,
    DecisionEpochReason,
    END_TURN_ROW_ID,
    OutcomeAdvantage,
    OutcomeResolution,
    ResourcePool,
)
from dnd.ai.contracts.semantics import (
    ActionSemantics,
    ActionTag,
    CapabilityOutcomeAdjustment,
    CapabilityAmountFormula,
    CapabilityAmountSource,
    CapabilityCostOperation,
    CapabilityCostRewrite,
    CapabilitySelector,
    CapabilityTargetingRewrite,
    CapabilityTransformation,
    SelfSetupDuration,
    SelfSetupSemantics,
    TargetAllocation,
    TargetingSemantics,
    TruthValue,
    action_semantics_ref,
)


def test_policy_host_builds_and_validates_one_aligned_subjective_context() -> None:
    """World, derived facts, session authority, actor, and epoch must agree."""
    world = _door_world()
    host = PolicyHost()

    context = host.build_context(world)

    assert context.world is world
    assert context.facts.actor.session_id == "session"
    assert context.facts.actor.actor_uuid == "actor"
    assert context.facts.epoch_id == "epoch-1"

    stale_facts = derive_agent_facts(
        world.model_copy(update={"observation_cursor": world.observation_cursor + 1})
    ).facts
    with pytest.raises(PolicyContextAlignmentError, match="world cursor"):
        host.build_context(world, facts=stale_facts)

    wrong_actor_epoch = world.current_epoch.model_copy(update={"actor_uuid": "other"})  # type: ignore[union-attr]
    wrong_actor_world = world.model_copy(update={"current_epoch": wrong_actor_epoch})
    with pytest.raises(PolicyContextAlignmentError, match="controlled actor"):
        host.build_context(wrong_actor_world)


def test_policy_host_models_are_complete_before_the_decision_hot_path() -> None:
    """Host records must not trigger lazy Pydantic schema work in ``decide``."""
    assert policy_host_module.PolicyDecisionBinding.__pydantic_complete__


def test_policy_generations_are_executable_and_select_host_behavior() -> None:
    """Baseline and candidate are authenticated implementations, not labels."""
    identities = {row.generation_id: row for row in list_policy_generations()}
    assert set(identities) == {BASELINE_GENERATION_ID, CANDIDATE_GENERATION_ID}
    assert identities[BASELINE_GENERATION_ID].executable_sha256 != identities[CANDIDATE_GENERATION_ID].executable_sha256
    assert identities[BASELINE_GENERATION_ID].implementation_sha256 == EXPECTED_V31_BEHAVIOR_SHA256
    assert len(identities[BASELINE_GENERATION_ID].implementation_paths) == 8

    world = _door_world()
    baseline = get_policy_implementation(BASELINE_GENERATION_ID)
    candidate = get_policy_implementation(CANDIDATE_GENERATION_ID)
    baseline_host = PolicyHost(implementation=baseline)
    candidate_host = PolicyHost(implementation=candidate)

    baseline_decision = baseline_host.decide(world)
    candidate_decision = candidate_host.decide(world)

    assert baseline_host.policy_id == BASELINE_GENERATION_ID
    assert candidate_host.policy_id == CANDIDATE_GENERATION_ID
    assert baseline_decision.selected.intent == candidate_decision.selected.intent
    assert baseline_host.binding_for("session", "actor", "epoch-1").policy_id == BASELINE_GENERATION_ID
    assert candidate_host.binding_for("session", "actor", "epoch-1").policy_id == CANDIDATE_GENERATION_ID


def test_policy_host_exposes_one_identical_decision_and_trace_to_every_consumer() -> None:
    """External and Codex adapters can read the same immutable host decision."""
    world = _door_world()
    host = PolicyHost()

    planned = host.decide(world)
    external_view = host.decision_for("session", "actor", "epoch-1")
    codex_view = host.decision_for("session", "actor", "epoch-1")

    assert external_view is planned
    assert codex_view is planned
    assert external_view == codex_view
    assert external_view.selected == codex_view.selected
    assert external_view.trace == codex_view.trace
    assert isinstance(planned.selected.intent, ExecuteIntent)
    assert planned.selected.intent.row_id == "move-row"
    assert [step.node_path for step in planned.trace] == [
        "PolicyHost/ExecutionConstraints",
        "PolicyHost/RoutineMemory/RegisteredRoutines/Revalidate",
        "ReactiveRoot/TacticalGoalUtility/SurvivalRecovery",
        "ReactiveRoot/TacticalGoalUtility/ConditionalTargetEffects",
            "ReactiveRoot/TacticalGoalUtility/Control/HasVisibleHostiles",
            "ReactiveRoot/TacticalGoalUtility/Control",
            "ReactiveRoot/TacticalGoalUtility/PreserveNewControl",
            "ReactiveRoot/TacticalGoalUtility/Pressure/HasVisibleHostiles",
        "ReactiveRoot/TacticalGoalUtility/Pressure",
        "ReactiveRoot/TacticalGoalUtility/Preparation/HasVisibleHostiles",
        "ReactiveRoot/TacticalGoalUtility/Preparation",
        "ReactiveRoot/TacticalGoalUtility/PositionAndSurvival",
        "ReactiveRoot/TacticalGoalUtility/InformationGathering",
        "ReactiveRoot/TacticalGoalUtility/Routines/ApproachOpenReassess",
        "ReactiveRoot/TacticalGoalUtility/Routines/AugmentThenAct",
            "ReactiveRoot/TacticalGoalUtility/Routines/TransformThenAct",
            "ReactiveRoot/TacticalGoalUtility/Routines/EnableThenAct",
            "ReactiveRoot/TacticalGoalUtility/Routines/PursueCapability",
            "ReactiveRoot/TacticalGoalUtility/Routines",
        "ReactiveRoot/TacticalGoalUtility",
        "ReactiveRoot",
    ]


def test_policy_host_emits_one_canonical_decision_event_per_binding() -> None:
    """A fresh epoch emits once while cached readers reuse the same identity."""
    world = _door_world()
    telemetry: list[PolicyDecisionTelemetry] = []
    host = PolicyHost(
        policy_id="shared.test",
        controller_mode="direct_codex",
        telemetry_sink=_RecordingPolicyTelemetrySink(telemetry),
    )

    first = host.decide(world)
    second = host.decide(world)
    binding = host.binding_for("session", "actor", "epoch-1")

    assert first is second
    assert len(telemetry) == 1
    event = telemetry[0]
    assert event.event_id == f"policy-decision:{event.decision_id}"
    assert event.schema_version == 2
    assert event.decision_id == binding.decision_id
    assert event.policy_id == "shared.test"
    assert event.controller_mode == "direct_codex"
    assert event.correlation.session_id == "session"
    assert event.correlation.actor_uuid == "actor"
    assert event.correlation.epoch_id == "epoch-1"
    assert event.correlation.observation_cursor == world.observation_cursor
    assert event.decision == first
    assert PolicyDecisionTelemetry.model_validate(
        event.model_dump(mode="json")
    ) == event


def test_policy_telemetry_does_not_revalidate_the_typed_decision_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonical emission reuses the host's already-validated typed models."""
    world = _door_world()
    telemetry: list[PolicyDecisionTelemetry] = []

    def reject_revalidation(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("policy telemetry revalidated the complete decision")

    monkeypatch.setattr(PolicyDecisionTelemetry, "__init__", reject_revalidation)

    decision = PolicyHost(
        telemetry_sink=_RecordingPolicyTelemetrySink(telemetry),
    ).decide(world)

    assert len(telemetry) == 1
    assert telemetry[0].decision == decision


def test_policy_telemetry_retains_target_bound_capability_projection() -> None:
    """Canonical telemetry preserves the subjective target used for spacing."""
    world = _same_turn_spacing_world()
    telemetry: list[PolicyDecisionTelemetry] = []
    host = PolicyHost(
        policy_id="shared.test",
        controller_mode="direct_codex",
        telemetry_sink=_RecordingPolicyTelemetrySink(telemetry),
    )

    decision = host.decide(world)

    assert decision.selected.intent == ExecuteIntent(
        row_id="retreat-floor",
        prefer_safe=True,
    )
    assert len(telemetry) == 1
    spacing = telemetry[0].decision.selected.evidence.spacing
    assert spacing is not None
    projection = spacing.capability_target_projection
    assert projection is not None
    assert projection.target_entity_uuid == spacing.reference_entity_uuid
    assert projection.target_entity_uuid == "spacing-target"
    assert projection.target_entity_uuid in world.known_entities
    assert world.known_entities[projection.target_entity_uuid].knowledge_state is KnowledgeState.VISIBLE
    assert projection.model_status is CapabilityModelStatus.MODELED
    assert projection.model_scope is not None


class _RecordingPolicyTelemetrySink:
    """Append-only policy telemetry sink for host lifecycle tests."""

    def __init__(self, events: list[PolicyDecisionTelemetry]) -> None:
        self.events = events

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        self.events.append(event)


def test_shared_decision_adapts_directly_from_canonical_subjective_context() -> None:
    """The normal command adapter must not require a copied compatibility state."""
    world = _door_world()
    host = PolicyHost()
    context = host.build_context(world)
    decision = host.decide(world, facts=context.facts)
    binding = host.binding_for("session", "actor", "epoch-1")

    command = command_from_policy_decision(
        context,
        decision,
        binding.routine_plan,
    )

    assert command is not None
    assert command.command_type is AgentCommandType.EXECUTE
    assert command.row_id == "move-row"
    assert command.entity_uuid == "actor"
    assert command.target_index == 7
    assert command.target_position == (2, 0)
    assert command.target_path == [(0, 0), (1, 0), (2, 0)]
    assert command.routine_id == APPROACH_OPEN_REASSESS.routine_id
    assert command.routine_step_id == "approach"
    assert decision.selected.goal is PolicyGoal.ROUTINE
    assert PolicyLogicalTag.INFORMATION_GAIN in command.logical_tags
    assert PolicyLogicalTag.REVEAL_BOUNDARY in command.logical_tags
    assert PolicyLogicalTag.ROUTE_PROGRESS in command.logical_tags
    assert PolicyLogicalTag.PRESERVE_ACTION_ECONOMY in command.logical_tags


def test_shared_decision_telemetry_uses_only_subjective_rows_and_entities() -> None:
    """Affected and additional targets resolve through the subjective world."""
    world = _combat_world()
    epoch = world.current_epoch
    assert epoch is not None
    multi_semantics = ActionSemantics(
        semantic_id="spell.multi_target",
        tags=frozenset({
            ActionTag.ATTACK_SPELL,
            ActionTag.DAMAGE_MULTI_TARGET,
            ActionTag.TARGET_MULTI,
            ActionTag.TARGET_REPEAT,
        }),
    )
    multi_ref = action_semantics_ref(multi_semantics)
    primary = epoch.affordances.entity_actions[0].targets[0]
    secondary = ActionTarget(
        index=1,
        target_uuid="second-hostile",
        target_name="Scout",
        position=(2, 0),
        distance=10,
    )
    multi_attack = epoch.affordances.entity_actions[0].model_copy(update={
        "target_type": "multi_entity",
        "targets": [primary],
        "target_options": [primary, secondary],
        "num_projectiles": 3,
        "allow_same_target": True,
        "semantic_id": multi_semantics.semantic_id,
        "semantics_ref": multi_ref,
        "tags": sorted(tag.value for tag in multi_semantics.tags),
    })
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": [multi_attack],
        "semantic_catalog": {multi_ref: multi_semantics},
    })
    entities = dict(world.known_entities)
    entities["second-hostile"] = ObservationEntityFact(
        uuid="second-hostile",
        name="Scout",
        knowledge_state=KnowledgeState.VISIBLE,
        controlled=False,
        position=(2, 0),
        hp=8,
        max_hp=8,
        faction="heroes",
    )
    world = world.model_copy(update={
        "known_entities": entities,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    host = PolicyHost()
    context = host.build_context(world)
    decision = host.decide(world, facts=context.facts)
    selected = decision.selected.model_copy(
        update={
            "intent": ExecuteIntent(
                row_id="melee-attack",
                extra_target_uuids=("second-hostile", "second-hostile"),
            )
        }
    )
    decision = decision.model_copy(update={"selected": selected})

    command = command_from_policy_decision(context, decision)

    assert command is not None
    assert command.target_uuid == "visible-hostile"
    assert command.target_name == "Barbarian"
    assert command.affected_entity_uuids == ["visible-hostile", "second-hostile"]
    assert command.affected_entity_names == ["Barbarian", "Scout"]
    assert command.extra_target_uuids == ["second-hostile", "second-hostile"]
    assert command.extra_target_names == ["Scout", "Scout"]
    assert command.affected_enemy_count == 2
    assert PolicyLogicalTag.PRESSURE in command.logical_tags
    assert PolicyLogicalTag.TARGET_ALLOCATION in command.logical_tags


def test_shared_end_turn_adapter_projects_typed_spacing_evidence() -> None:
    """Spacing telemetry follows typed evidence and ignores rationale wording."""
    world = _combat_world()
    host = PolicyHost()
    context = host.build_context(world)
    proposal = PolicyProposal(
        intent=EndTurnIntent(),
        goal=PolicyGoal.POSITION_AND_SURVIVAL,
        source_node="PositionAndSurvival/Test",
        reason="arbitrary human explanation",
        evidence=PolicyEvidence(spacing=SpacingEvidence(
            reference_entity_uuid="visible-hostile",
            reference_position=(1, 0),
            current_distance_cells=7,
            selected_distance_cells=7,
            spacing_floor_cells=6,
            anchor_position=(0, 0),
            nearest_controlled_ally_distance_cells=8,
            ally_spacing_floor_cells=5,
        )),
    )
    decision = PolicyDecision(selected=proposal, candidates=(proposal,))

    command = command_from_policy_decision(context, decision)

    assert command is not None
    assert command.command_type is AgentCommandType.END_TURN
    assert command.reference_entity_uuid == "visible-hostile"
    assert command.reference_entity_name == "Barbarian"
    assert command.reference_entity_position == (1, 0)
    assert command.reference_entity_distance_cells == 7
    assert command.spacing_floor_cells == 6
    assert command.spacing_anchor_position == (0, 0)
    assert command.nearest_controlled_ally_distance_cells == 8
    assert command.ally_spacing_floor_cells == 5
    assert PolicyLogicalTag.SPACING_CONTROL in command.logical_tags
    assert PolicyLogicalTag.ANTI_AOE_SPACING in command.logical_tags


def test_policy_host_allows_only_one_prepared_submission_per_epoch() -> None:
    """The host is the one-command writer even before transport is connected."""
    host = PolicyHost()
    host.decide(_door_world())

    prepared = host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="command-1",
    )

    assert prepared.command_id == "command-1"
    assert prepared.intent.kind == "execute"
    assert prepared.intent.row_id == "move-row"  # type: ignore[union-attr]
    assert prepared.routine_plan is not None
    assert prepared.routine_plan.routine_id == APPROACH_OPEN_REASSESS.routine_id
    assert host.pending_submission("command-1") is prepared

    with pytest.raises(DuplicateEpochSubmissionError, match="already has command"):
        host.prepare_submission(
            session_id="session",
            actor_uuid="actor",
            epoch_id="epoch-1",
            command_id="command-2",
        )


def test_policy_host_ignores_mismatched_results_and_retains_pending_plan() -> None:
    """An unrelated result cannot consume or advance a retained routine plan."""
    host = PolicyHost()
    host.decide(_door_world())
    prepared = host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="command-1",
    )

    outcome = host.record_result(
        _result(
            CommandResultStatus.ACCEPTED,
            command_id="command-1",
            actor_uuid="other",
        )
    )

    assert outcome.disposition is PolicyResultDisposition.UNMATCHED
    assert outcome.memory_advanced is False
    assert host.pending_submission("command-1") is prepared
    assert host.memory_for("session", "actor").active_routine is None


@pytest.mark.parametrize(
    ("status", "expected_disposition"),
    [
        (CommandResultStatus.REJECTED, PolicyResultDisposition.REJECTED),
        (CommandResultStatus.STALE, PolicyResultDisposition.STALE),
    ],
)
def test_policy_host_does_not_advance_rejected_or_stale_routine_commands(
    status: CommandResultStatus,
    expected_disposition: PolicyResultDisposition,
) -> None:
    """Only authoritative acceptance commits acceptance-gated routine progress."""
    host = PolicyHost()
    host.decide(_door_world())
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="command-1",
    )

    outcome = host.record_result(_result(status))

    assert outcome.disposition is expected_disposition
    assert outcome.memory_advanced is False
    assert host.pending_submission("command-1") is None
    assert host.memory_for("session", "actor").active_routine is None


def test_policy_host_advances_only_the_matching_accepted_routine_plan() -> None:
    """A correlated accepted result commits the retained typed plan exactly once."""
    host = PolicyHost()
    host.decide(_door_world())
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="command-1",
    )

    outcome = host.record_result(_result(CommandResultStatus.ACCEPTED))

    memory = host.memory_for("session", "actor")
    assert outcome.disposition is PolicyResultDisposition.ACCEPTED
    assert outcome.memory_advanced is True
    assert memory.active_routine is not None
    assert memory.active_routine.routine_id == APPROACH_OPEN_REASSESS.routine_id
    assert memory.active_routine.step_id == "approach"
    assert memory.active_routine.target_uuid == "door"
    assert host.pending_submission("command-1") is None

    duplicate = host.record_result(_result(CommandResultStatus.ACCEPTED))
    assert duplicate.disposition is PolicyResultDisposition.ALREADY_RECORDED
    assert duplicate.memory_advanced is False


def test_policy_host_does_not_advance_memory_for_accepted_canceled_action() -> None:
    """Protocol acceptance does not claim a canceled gameplay effect occurred."""
    host = PolicyHost()
    host.decide(_door_world())
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="command-1",
    )

    outcome = host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        action_resolution=ActionResolutionStatus.CANCELED,
    ))

    assert outcome.disposition is PolicyResultDisposition.ACCEPTED
    assert outcome.memory_advanced is False
    assert outcome.reason == "matched_accepted_canceled_command_result"
    assert host.pending_submission("command-1") is None
    memory = host.memory_for("session", "actor")
    assert memory.active_routine is None
    assert memory.canceled_row_ids == {"move-row"}
    assert outcome.submission is not None
    assert outcome.submission.selected_action_shape is not None
    assert memory.canceled_semantic_counts == {
        outcome.submission.selected_action_shape.semantic_key: 1
    }


def test_policy_host_fails_closed_for_accepted_execute_without_resolution() -> None:
    """Protocol admission without explicit execute completion cannot advance intent."""
    host = PolicyHost()
    host.decide(_door_world())
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="command-1",
    )

    outcome = host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        action_resolution=None,
    ))

    assert outcome.disposition is PolicyResultDisposition.ACCEPTED
    assert outcome.memory_advanced is False
    assert outcome.reason == "matched_accepted_unresolved_command_result"
    assert host.memory_for("session", "actor").active_routine is None


@pytest.mark.parametrize(
    ("status", "resolution", "commits"),
    [
        (CommandResultStatus.ACCEPTED, ActionResolutionStatus.COMPLETED, True),
        (CommandResultStatus.ACCEPTED, ActionResolutionStatus.INTERRUPTED, True),
        (CommandResultStatus.REJECTED, ActionResolutionStatus.COMPLETED, False),
        (CommandResultStatus.STALE, ActionResolutionStatus.COMPLETED, False),
    ],
)
def test_policy_host_commits_spacing_intention_only_after_acceptance(
    status: CommandResultStatus,
    resolution: ActionResolutionStatus,
    commits: bool,
) -> None:
    """A selected retreat becomes memory only after its movement effect commits."""
    world = _same_turn_spacing_world()
    host = PolicyHost()

    decision = host.decide(world)
    assert decision.selected.intent == ExecuteIntent(row_id="retreat-floor", prefer_safe=True)
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="spacing-command",
    )

    outcome = host.record_result(_result(
        status,
        command_id="spacing-command",
        row_id="retreat-floor",
        action_resolution=resolution,
    ))

    intention = host.memory_for("session", "actor").same_turn_spacing_intention
    if commits:
        assert outcome.memory_advanced is True
        assert intention is not None
        assert intention.target_uuid == "spacing-target"
        assert intention.target_position == (2, 0)
        assert intention.minimum_distance_cells == 6
        assert intention.started_round_number == 1
        assert intention.started_turn_index == 0
    else:
        assert outcome.memory_advanced is False
        assert intention is None


def test_policy_host_preserves_spacing_after_interrupted_committed_move() -> None:
    """A hazard interruption cannot erase intent and admit a contradictory reversal."""
    world = _same_turn_spacing_world()
    host = PolicyHost()
    host.decide(world)
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="spacing-command",
    )
    host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        command_id="spacing-command",
        row_id="retreat-floor",
        action_resolution=ActionResolutionStatus.INTERRUPTED,
    ))
    followup = _same_turn_spacing_followup_world(
        world,
        target_position=(0, 0),
        movement_positions=((-5, 0), (-6, 0)),
    )

    decision = host.decide(followup)

    candidate_row_ids = {
        proposal.intent.row_id
        for proposal in decision.candidates
        if isinstance(proposal.intent, ExecuteIntent)
    }
    assert "followup-move:-5,0" not in candidate_row_ids
    assert "followup-move:-6,0" in candidate_row_ids


def test_policy_host_revalidates_and_enforces_same_turn_spacing_before_arbitration() -> None:
    """Remembered target movement is applied before spatial proposals are ranked."""
    world = _same_turn_spacing_world()
    host = PolicyHost()
    _accept_spacing_retreat(host, world)
    followup = _same_turn_spacing_followup_world(
        world,
        target_position=(0, 0),
        movement_positions=((-5, 0), (-6, 0)),
    )

    decision = host.decide(followup)

    intention = host.memory_for("session", "actor").same_turn_spacing_intention
    assert intention is not None
    assert intention.target_position == (0, 0)
    candidate_row_ids = {
        proposal.intent.row_id
        for proposal in decision.candidates
        if isinstance(proposal.intent, ExecuteIntent)
    }
    assert "followup-move:-5,0" not in candidate_row_ids
    assert "followup-move:-6,0" in candidate_row_ids
    assert decision.selected.intent == ExecuteIntent(
        row_id="followup-move:-6,0",
        prefer_safe=True,
    )


@pytest.mark.parametrize("expiration", ["turn", "death", "loss"])
def test_policy_host_expires_same_turn_spacing_intention(
    expiration: str,
) -> None:
    """Turn transition and subjective target death or loss release the floor."""
    world = _same_turn_spacing_world()
    host = PolicyHost()
    _accept_spacing_retreat(host, world)
    followup = _same_turn_spacing_followup_world(
        world,
        target_position=(2, 0),
        movement_positions=((0, 0), (-5, 0)),
    )
    epoch = followup.current_epoch
    assert epoch is not None
    entities = dict(followup.known_entities)
    if expiration == "turn":
        followup = followup.model_copy(update={
            "current_epoch": epoch.model_copy(update={"turn_index": 1}),
        })
    elif expiration == "death":
        entities["spacing-target"] = entities["spacing-target"].model_copy(
            update={"is_dead": True}
        )
        followup = followup.model_copy(update={"known_entities": entities})
    else:
        entities.pop("spacing-target")
        followup = followup.model_copy(update={"known_entities": entities})

    decision = host.decide(followup)

    assert host.memory_for("session", "actor").same_turn_spacing_intention is None
    assert "followup-move:0,0" in {
        proposal.intent.row_id
        for proposal in decision.candidates
        if isinstance(proposal.intent, ExecuteIntent)
    }


def test_policy_host_explicitly_invalidates_same_turn_spacing_intention() -> None:
    """Controller lifecycle code can explicitly release retained spatial intent."""
    world = _same_turn_spacing_world()
    host = PolicyHost()
    _accept_spacing_retreat(host, world)

    invalidated = host.invalidate_same_turn_spacing_intention("session", "actor")

    assert invalidated is True
    assert host.memory_for("session", "actor").same_turn_spacing_intention is None


def test_policy_host_selects_adjacent_semantic_damage_without_routine_memory() -> None:
    """Visible combat is owned by the shared host rather than the door fallback."""
    world = _combat_world()
    host = PolicyHost()

    decision = host.decide(world)
    binding = host.binding_for("session", "actor", "epoch-1")

    assert isinstance(decision.selected.intent, ExecuteIntent)
    assert decision.selected.intent.row_id == "melee-attack"
    assert decision.selected.semantic_tags == frozenset(
        {ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}
    )
    assert decision.selected.utility_components
    assert sum(
        component.contribution for component in decision.selected.utility_components
    ) == decision.selected.score
    assert binding.routine_plan is None
    assert any(
        step.node_path == "ReactiveRoot/TacticalGoalUtility/Pressure/DirectDamage"
        for step in decision.trace
    )
    assert any(
        step.node_path == "ReactiveRoot/TacticalGoalUtility/Routines/ApproachOpenReassess"
        for step in decision.trace
    )

    prepared = host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="combat-command",
    )
    outcome = host.record_result(
        _result(
            CommandResultStatus.ACCEPTED,
            command_id="combat-command",
            row_id="melee-attack",
        )
    )

    assert prepared.routine_plan is None
    assert outcome.disposition is PolicyResultDisposition.ACCEPTED
    assert outcome.memory_advanced is False
    assert host.memory_for("session", "actor").active_routine is None


def test_policy_host_reranks_the_same_epoch_after_an_exact_row_rejection() -> None:
    """One rejected row leaves equivalent legal choices inside the shared host."""
    world = _combat_world()
    epoch = world.current_epoch
    assert epoch is not None
    primary = epoch.affordances.entity_actions[0]
    backup = primary.model_copy(update={"row_id": "zz-backup-attack"})
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "affordances": epoch.affordances.model_copy(update={
                "entity_actions": [primary, backup],
            }),
        }),
    })
    host = PolicyHost()

    first = host.decide(world)
    second = host.decide(
        world,
        execution_constraints=PolicyExecutionConstraints(
            blocked_row_ids=frozenset({"melee-attack"}),
        ),
    )

    assert isinstance(first.selected.intent, ExecuteIntent)
    assert first.selected.intent.row_id == "melee-attack"
    assert isinstance(second.selected.intent, ExecuteIntent)
    assert second.selected.intent.row_id == "zz-backup-attack"
    assert second is host.binding_for("session", "actor", "epoch-1").decision
    assert second.trace[0].node_path == "PolicyHost/ExecutionConstraints"
    assert second.trace[0].detail == "applied:row:melee-attack"


def test_rejected_result_releases_the_epoch_for_constrained_resubmission() -> None:
    """Authoritative rejection permits one newly ranked writer for the same epoch."""
    world = _combat_world()
    epoch = world.current_epoch
    assert epoch is not None
    primary = epoch.affordances.entity_actions[0]
    backup = primary.model_copy(update={"row_id": "zz-backup-attack"})
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "affordances": epoch.affordances.model_copy(update={
                "entity_actions": [primary, backup],
            }),
        }),
    })
    host = PolicyHost()
    host.decide(world)
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="first-command",
    )

    result = host.record_result(_result(
        CommandResultStatus.REJECTED,
        command_id="first-command",
        row_id="melee-attack",
    ))
    decision = host.decide(
        world,
        execution_constraints=PolicyExecutionConstraints(
            blocked_row_ids=frozenset({"melee-attack"}),
        ),
    )
    prepared = host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="second-command",
    )

    assert result.disposition is PolicyResultDisposition.REJECTED
    assert isinstance(decision.selected.intent, ExecuteIntent)
    assert decision.selected.intent.row_id == "zz-backup-attack"
    assert isinstance(prepared.intent, ExecuteIntent)
    assert prepared.intent.row_id == "zz-backup-attack"


def test_policy_host_revalidates_one_move_then_resolves_fresh_attack_row() -> None:
    """An enabling routine stores a semantic goal, never a future legal row."""
    host = PolicyHost()
    first_world = _approach_combat_world()
    first_context = host.build_context(first_world)

    first_decision = host.decide(first_world, facts=first_context.facts)
    assert isinstance(first_decision.selected.intent, ExecuteIntent)
    assert first_decision.selected.intent.row_id == "approach-hostile"
    assert first_decision.selected.goal is PolicyGoal.ROUTINE
    first_binding = host.binding_for("session", "actor", "epoch-1")
    first_command = command_from_policy_decision(
        first_context,
        first_decision,
        first_binding.routine_plan,
    )
    assert first_command is not None
    assert first_command.routine_id == ENABLE_THEN_ACT.routine_id
    assert first_command.routine_step_id == "enable"
    assert PolicyLogicalTag.PRESSURE in first_command.logical_tags
    assert PolicyLogicalTag.ROUTE_PROGRESS in first_command.logical_tags
    assert PolicyLogicalTag.PRESERVE_ACTION_ECONOMY in first_command.logical_tags
    assert PolicyLogicalTag.INFORMATION_GAIN not in first_command.logical_tags
    assert PolicyLogicalTag.REVEAL_BOUNDARY not in first_command.logical_tags
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="approach-command",
    )
    host.record_result(
        _result(
            CommandResultStatus.ACCEPTED,
            command_id="approach-command",
            row_id="approach-hostile",
        )
    )

    progress = host.memory_for("session", "actor").active_routine
    assert progress is not None
    assert progress.routine_id == ENABLE_THEN_ACT.routine_id
    assert progress.goal is not None
    assert progress.goal.target_uuid == "visible-hostile"
    assert progress.goal.required_tags == frozenset({ActionTag.DAMAGE_SINGLE_TARGET})
    assert "followup-attack" not in progress.model_dump_json()

    second_world = _approach_followup_world(first_world)
    second_decision = host.decide(second_world)
    assert isinstance(second_decision.selected.intent, ExecuteIntent)
    assert second_decision.selected.intent.row_id == "followup-attack"
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-2",
        command_id="attack-command",
    )
    host.record_result(
        CommandResult(
            status=CommandResultStatus.ACCEPTED,
            command_id="attack-command",
            session_id="session",
            actor_uuid="actor",
            requested_epoch_id="epoch-2",
                current_epoch_id="epoch-3",
                row_id="followup-attack",
                action_resolution=ActionResolutionStatus.COMPLETED,
            )
    )

    assert host.memory_for("session", "actor").active_routine is None


def test_policy_host_starts_bounded_pursuit_when_one_move_cannot_enable_damage() -> None:
    """A visible distant hostile starts semantic pursuit instead of ending turn."""
    host = PolicyHost()
    world = _distant_capability_pursuit_world()

    decision = host.decide(world)

    assert decision.selected.intent == ExecuteIntent(
        row_id="pursuit-advance",
        prefer_safe=True,
    )
    assert decision.selected.goal is PolicyGoal.ROUTINE
    assert decision.selected.source_node == "Pressure/PursueCapability/Approach"
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="pursuit-command",
    )
    host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        command_id="pursuit-command",
        row_id="pursuit-advance",
    ))

    progress = host.memory_for("session", "actor").active_routine
    assert progress is not None
    assert progress.routine_id == "routine.pursue_capability"
    assert progress.target_uuid == "visible-hostile"
    assert progress.goal is not None
    assert progress.goal.required_tags == frozenset({ActionTag.DAMAGE_SINGLE_TARGET})
    assert "pursuit-advance" not in progress.model_dump_json()


def test_policy_host_pursuit_revalidates_move_dash_yield_and_fresh_attack() -> None:
    """Pursuit consumes fresh rows, bounds Dash, and survives a turn boundary."""
    host = PolicyHost()
    first_world = _distant_capability_pursuit_world()
    first = host.decide(first_world)
    _accept_policy_decision(host, first_world, first, "pursuit-move-1")

    after_move = _pursuit_after_first_move_world(first_world)
    extend = host.decide(after_move)
    assert extend.selected.intent == ExecuteIntent(row_id="pursuit-dash")
    assert extend.selected.source_node == "Pressure/PursueCapability/ExtendMobility"
    _accept_policy_decision(host, after_move, extend, "pursuit-dash-1")

    after_dash = _pursuit_after_dash_world(after_move)
    second_move = host.decide(after_dash)
    assert second_move.selected.intent == ExecuteIntent(
        row_id="pursuit-final-advance",
        prefer_safe=True,
    )
    assert second_move.selected.source_node == "Pressure/PursueCapability/Approach"
    _accept_policy_decision(host, after_dash, second_move, "pursuit-move-2")

    exhausted = _pursuit_after_second_move_world(after_dash)
    yield_turn = host.decide(exhausted)
    assert isinstance(yield_turn.selected.intent, EndTurnIntent)
    assert yield_turn.selected.source_node == "Pressure/PursueCapability/YieldTurn"
    yield_result = _accept_policy_decision(
        host,
        exhausted,
        yield_turn,
        "pursuit-yield",
    )
    assert yield_result.submission is not None
    assert isinstance(yield_result.submission.intent, EndTurnIntent)
    assert yield_result.submission.routine_plan is not None
    assert yield_result.submission.routine_plan.step_id == "yield_turn"
    assert host.pending_submission("pursuit-yield") is None
    assert host.memory_for("session", "actor").active_routine is not None

    next_turn = _pursuit_next_turn_attack_world(exhausted)
    attack = host.decide(next_turn)
    assert attack.selected.intent == ExecuteIntent(row_id="pursuit-fresh-attack")
    _accept_policy_decision(host, next_turn, attack, "pursuit-attack")

    assert host.memory_for("session", "actor").active_routine is None


def test_policy_host_pursuit_bounds_mobility_extension_to_once_per_turn() -> None:
    """A fresh affordable Dash-like row cannot loop the active pursuit."""
    host = PolicyHost()
    first_world = _distant_capability_pursuit_world()
    first = host.decide(first_world)
    _accept_policy_decision(host, first_world, first, "bounded-move")
    after_move = _pursuit_after_first_move_world(first_world)
    extend = host.decide(after_move)
    _accept_policy_decision(host, after_move, extend, "bounded-dash")

    second_extension = _pursuit_second_extension_world(after_move)
    decision = host.decide(second_extension)

    assert isinstance(decision.selected.intent, EndTurnIntent)
    assert decision.selected.source_node == "Pressure/PursueCapability/YieldTurn"


def test_policy_host_pursuit_interrupts_when_target_becomes_remembered() -> None:
    """Loss of current perception hands the contact back to search policy."""
    host = PolicyHost()
    first_world = _distant_capability_pursuit_world()
    first = host.decide(first_world)
    _accept_policy_decision(host, first_world, first, "visibility-move")
    after_move = _pursuit_after_first_move_world(first_world)
    target = after_move.known_entities["visible-hostile"].model_copy(update={
        "knowledge_state": KnowledgeState.REMEMBERED,
    })
    after_loss = after_move.model_copy(update={
        "known_entities": {
            **after_move.known_entities,
            "visible-hostile": target,
        },
    })

    host.decide(after_loss)

    memory = host.memory_for("session", "actor")
    assert memory.active_routine is None
    assert memory.last_routine_revalidation_status == "interrupted"
    assert memory.last_routine_revalidation_reason == (
        "pursuit_target_no_longer_visible"
    )


def test_enable_then_act_does_not_restart_after_bounded_reassessment_fails() -> None:
    """A disproven enabler remains exhausted instead of reversing within the turn."""
    host = PolicyHost()
    first_world = _approach_combat_world()
    first_epoch = first_world.current_epoch
    assert first_epoch is not None
    capability = first_epoch.affordances.capabilities[0].model_copy(
        update={"normal_range_feet": 30}
    )
    first_world = first_world.model_copy(update={
        "current_epoch": first_epoch.model_copy(update={
            "affordances": first_epoch.affordances.model_copy(update={
                "capabilities": [capability]
            })
        })
    })

    first_decision = host.decide(first_world)
    assert isinstance(first_decision.selected.intent, ExecuteIntent)
    assert first_decision.selected.intent.row_id == "approach-hostile"
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="approach-command",
    )
    host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        command_id="approach-command",
        row_id="approach-hostile",
    ))

    second_world = _approach_failed_followup_world(first_world)
    second_decision = host.decide(second_world)

    assert isinstance(second_decision.selected.intent, EndTurnIntent)
    assert all(
        candidate.source_node != "Pressure/EnableThenAct/Enable"
        for candidate in second_decision.candidates
    )
    progress = host.memory_for("session", "actor").active_routine
    assert progress is not None
    assert progress.routine_id == ENABLE_THEN_ACT.routine_id
    assert progress.step_id == "reassess"
    assert any(
        step.node_path == "PolicyHost/RoutineMemory/EnableThenAct/Revalidate"
        and step.detail == "exhausted:bounded_enabler_exhausted_without_legal_followup"
        for step in second_decision.trace
    )

    third_epoch = first_world.current_epoch
    assert third_epoch is not None
    third_world = first_world.model_copy(update={
        "observation_cursor": 3,
        "epoch_cursor": 3,
        "current_epoch": third_epoch.model_copy(update={
            "epoch_id": "epoch-3",
            "epoch_index": 3,
            "basis_observation_cursor": 3,
            "round_number": 2,
            "reason": DecisionEpochReason.TURN_START,
            "affordances": third_epoch.affordances.model_copy(
                update={"computed_at_observation_cursor": 3}
            ),
        }),
    })
    third_decision = host.decide(third_world)

    assert isinstance(third_decision.selected.intent, ExecuteIntent)
    assert third_decision.selected.intent.row_id == "approach-hostile"
    assert host.memory_for("session", "actor").active_routine is None
    assert any(
        step.node_path == "PolicyHost/RoutineMemory/EnableThenAct/Revalidate"
        and step.detail == "interrupted:same_turn_routine_expired"
        for step in third_decision.trace
    )


def test_interrupted_enabler_does_not_commit_bounded_routine_progress() -> None:
    """A partial accepted move preserves engine truth without consuming intent."""
    host = PolicyHost()
    first_world = _approach_combat_world()
    first_decision = host.decide(first_world)
    assert isinstance(first_decision.selected.intent, ExecuteIntent)
    assert first_decision.selected.intent.row_id == "approach-hostile"
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="interrupted-approach",
    )

    record = host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="interrupted-approach",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-1",
        current_epoch_id="epoch-2",
        row_id="approach-hostile",
        action_resolution=ActionResolutionStatus.INTERRUPTED,
        outcome_code="movement.subjective_revalidation",
        revalidation_required=True,
        revalidation_reason="newly_visible_hostile",
    ))

    assert record.memory_advanced is False
    assert record.reason == "matched_accepted_interrupted_command_result"
    assert host.memory_for("session", "actor").active_routine is None

    second_world = _approach_interrupted_followup_world(first_world)
    second_decision = host.decide(second_world)

    assert isinstance(second_decision.selected.intent, ExecuteIntent)
    assert second_decision.selected.intent.row_id == "continue-approach"
    assert second_decision.selected.source_node == "Pressure/EnableThenAct/Enable"


def test_completed_enabler_advances_even_when_fresh_decision_is_required() -> None:
    """Final-step discovery is orthogonal to explicit action completion."""
    host = PolicyHost()
    host.decide(_door_world())
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="completed-revalidation",
    )

    outcome = host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="completed-revalidation",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-1",
        current_epoch_id="epoch-2",
        row_id="move-row",
        action_resolution=ActionResolutionStatus.COMPLETED,
        outcome_code="movement.subjective_revalidation",
        revalidation_required=True,
        revalidation_reason="newly_visible_hazard",
    ))

    assert outcome.memory_advanced is True
    assert host.memory_for("session", "actor").active_routine is not None


def test_policy_host_uses_zero_cost_transient_augmentation_before_direct_pressure() -> None:
    """A typed transient setup must beat the same legal attack only when it improves it."""
    host = PolicyHost()
    first_world = _transient_augmentation_world()

    first = host.decide(first_world)

    assert isinstance(first.selected.intent, ExecuteIntent)
    assert first.selected.intent.row_id == "transient-augmentation"
    assert first.selected.goal is PolicyGoal.ROUTINE
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="augment-command",
    )
    host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        command_id="augment-command",
        row_id="transient-augmentation",
    ))
    progress = host.memory_for("session", "actor").active_routine
    assert progress is not None
    assert progress.routine_id == AUGMENT_THEN_ACT.routine_id
    assert progress.goal is not None
    assert progress.goal.target_uuid == "visible-hostile"

    second_world = _transient_augmentation_world(augmented=True)
    second = host.decide(second_world)

    assert isinstance(second.selected.intent, ExecuteIntent)
    assert second.selected.intent.row_id == "melee-attack"
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-2",
        command_id="attack-command",
    )
    host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="attack-command",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-2",
            current_epoch_id="epoch-3",
            row_id="melee-attack",
            action_resolution=ActionResolutionStatus.COMPLETED,
        ))
    assert host.memory_for("session", "actor").active_routine is None


def test_transient_augmentation_values_every_matching_attack_this_turn() -> None:
    """A turn-duration setup must value the remaining matching attack slots."""
    world = _transient_augmentation_world()
    epoch = world.current_epoch
    assert epoch is not None
    attack = epoch.affordances.entity_actions[0]
    attack_semantics = epoch.affordances.semantic_catalog[attack.semantics_ref]
    extra_attack = ActionCapability(
        capability_id="extra-melee-attack",
        semantic_key=attack.semantic_key,
        action_category=attack.action_category,
        target_type=attack.target_type,
        cost=ActionCostProfile(consumes_attack_slot=True),
        range_type="Reach",
        normal_range_feet=5,
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        weapon_slot="MELEE_MAIN",
        outcome_profile=attack.outcome_profile,
        semantic_id=attack_semantics.semantic_id,
        semantics_ref=attack.semantics_ref,
        tags=sorted(tag.value for tag in attack_semantics.tags),
    )
    second_hostile = ObservationEntityFact(
        uuid="second-visible-hostile",
        name="Second Target",
        knowledge_state=KnowledgeState.VISIBLE,
        controlled=False,
        position=(0, 1),
        hp=20,
        max_hp=20,
        ac=15,
        faction="heroes",
    )
    world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            second_hostile.uuid: second_hostile,
        },
        "current_epoch": epoch.model_copy(update={
            "economy": epoch.economy.model_copy(update={"extra_attacks": 1}),
            "affordances": epoch.affordances.model_copy(update={
                "capabilities": (extra_attack,),
            }),
        }),
    })

    decision = PolicyHost().decide(world)

    assert decision.selected.intent == ExecuteIntent(row_id="transient-augmentation")
    assert decision.selected.source_node == "Pressure/AugmentThenAct/Augment"
    component = next(
        item
        for item in decision.selected.utility_components
        if item.name == "additional_matching_attack_marginal_utility"
    )
    assert component.raw_value == pytest.approx(1.0)
    assert component.contribution > 0


@pytest.mark.parametrize("actor_hp", [8, 4])
def test_transient_incoming_advantage_is_rejected_at_critical_actor_hp(
    actor_hp: int,
) -> None:
    """Known actor fragility must outweigh a marginal offensive augmentation."""
    world = _transient_augmentation_world()
    actor = world.known_entities["actor"].model_copy(update={
        "hp": actor_hp,
        "normal_hp": actor_hp,
        "max_hp": 50,
    })
    hostile = world.known_entities["visible-hostile"].model_copy(update={
        "hp": 10,
        "max_hp": 24,
        "ac": 13,
    })
    world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            actor.uuid: actor,
            hostile.uuid: hostile,
        },
    })

    decision = PolicyHost().decide(world)

    assert decision.selected.intent == ExecuteIntent(row_id="melee-attack")
    assert all(
        proposal.source_node != "Pressure/AugmentThenAct/Augment"
        for proposal in decision.candidates
    )


@pytest.mark.parametrize("actor_hp", [30, 25])
def test_current_generation_rejects_exposure_augmentation_before_critical_hp(
    actor_hp: int,
) -> None:
    """Current policy preserves health when offensive setup exposes a fragile actor."""
    world = _transient_augmentation_world()
    actor = world.known_entities["actor"].model_copy(update={
        "hp": actor_hp,
        "normal_hp": actor_hp,
        "max_hp": 50,
    })
    hostile = world.known_entities["visible-hostile"].model_copy(update={
        "hp": 10,
        "max_hp": 24,
        "ac": 13,
    })
    world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            actor.uuid: actor,
            hostile.uuid: hostile,
        },
    })

    host = PolicyHost(implementation=get_policy_implementation(CANDIDATE_GENERATION_ID))
    decision = host.decide(world)

    assert decision.selected.intent == ExecuteIntent(row_id="melee-attack")


def test_transient_augmentation_projects_only_direct_damage_candidates(monkeypatch) -> None:
    """Projected augmentation does not rebuild unrelated candidate families."""
    context = PolicyHost().build_context(_transient_augmentation_world())
    candidates = build_policy_candidate_set(context)

    def fail_full_candidate_rebuild(_context):
        raise AssertionError("projected augmentation rebuilt every candidate family")

    monkeypatch.setattr(
        policy_routines,
        "build_policy_candidate_set",
        fail_full_candidate_rebuild,
    )

    plan = policy_routines.plan_augment_then_act(context, None, candidates)

    assert plan.status is policy_routines.RoutinePlanStatus.PROPOSED
    assert plan.proposal is not None
    assert plan.proposal.intent == ExecuteIntent(row_id="transient-augmentation")


def test_policy_host_skips_transient_augmentation_without_positive_marginal_value() -> None:
    """A saturated outcome profile must retain the current direct attack."""
    world = _transient_augmentation_world()
    epoch = world.current_epoch
    assert epoch is not None
    attack = epoch.affordances.entity_actions[0]
    assert attack.outcome_profile is not None
    attack = attack.model_copy(update={
        "outcome_profile": attack.outcome_profile.model_copy(update={
            "advantage": OutcomeAdvantage.ADVANTAGE,
        }),
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "affordances": epoch.affordances.model_copy(update={
                "entity_actions": (attack,),
            }),
        }),
    })

    decision = PolicyHost().decide(world)

    assert decision.selected.intent == ExecuteIntent(row_id="melee-attack")
    assert all(
        proposal.source_node != "Pressure/AugmentThenAct/Augment"
        for proposal in decision.candidates
    )


def test_policy_host_quickened_transform_reassesses_fresh_bonus_action_spell_row() -> None:
    """A spent action can be repaired by typed transformation then fresh-row binding."""
    host = PolicyHost()
    first_world = _spell_transform_world("quickened")

    first = host.decide(first_world)
    assert isinstance(first.selected.intent, ExecuteIntent)
    assert first.selected.intent.row_id == "opaque-transform"
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="transform-command",
    )
    host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        command_id="transform-command",
        row_id="opaque-transform",
    ))

    progress = host.memory_for("session", "actor").active_routine
    assert progress is not None
    assert progress.routine_id == TRANSFORM_THEN_ACT.routine_id
    assert progress.goal is not None
    assert progress.goal.required_target_allocation is TargetAllocation.SINGLE_ENTITY
    assert "fresh-quickened-spell" not in progress.model_dump_json()

    second_world = _spell_transform_followup_world(first_world, "quickened")
    second = host.decide(second_world)

    assert isinstance(second.selected.intent, ExecuteIntent)
    assert second.selected.intent.row_id == "fresh-quickened-spell"


def test_policy_host_rejects_transform_when_projected_damage_is_visibly_blocked() -> None:
    """A transform cannot claim pressure from a disclosed nullified follow-up."""
    world = _spell_transform_world("quickened")
    epoch = world.current_epoch
    assert epoch is not None
    capability = epoch.affordances.capabilities[0]
    effect_id = "rules.damage.opaque_automatic_darts"
    capability = capability.model_copy(update={
        "outcome_profile": ActionOutcomeProfile(
            effect_id=effect_id,
            resolution=OutcomeResolution.AUTOMATIC,
            applications=3,
            damage_rolls=[DamageRollProfile(
                dice_count=1,
                die_size=4,
                flat_bonus=1,
                damage_type="force",
            )],
        ),
    })
    hostile = world.known_entities["visible-hostile"].model_copy(update={
        "effect_protections": [ObservationEffectProtection(
            protection_id="rules.protection.opaque_dart_barrier",
            blocked_effect_ids=[effect_id],
        )],
    })
    world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            hostile.uuid: hostile,
        },
        "current_epoch": epoch.model_copy(update={
            "affordances": epoch.affordances.model_copy(update={
                "capabilities": [capability],
            }),
        }),
    })

    decision = PolicyHost().decide(world)

    assert all(
        proposal.source_node != "Pressure/TransformThenAct/Transform"
        for proposal in decision.candidates
    )


def test_interrupted_transformed_followup_consumes_active_transformation() -> None:
    """Committed transformed execution clears memory without completing its plan."""
    host = PolicyHost()
    first_world = _spell_transform_world("quickened")
    host.decide(first_world)
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="transform-command",
    )
    host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        command_id="transform-command",
        row_id="opaque-transform",
    ))
    second_world = _spell_transform_followup_world(first_world, "quickened")
    second = host.decide(second_world)
    assert isinstance(second.selected.intent, ExecuteIntent)
    assert second.selected.intent.row_id == "fresh-quickened-spell"
    binding = host.binding_for("session", "actor", "epoch-2")
    assert binding.routine_plan is not None
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-2",
        command_id="interrupted-spell",
    )

    outcome = host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="interrupted-spell",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-2",
        current_epoch_id="epoch-3",
        row_id="fresh-quickened-spell",
        action_resolution=ActionResolutionStatus.INTERRUPTED,
        revalidation_required=True,
        revalidation_reason="actor_state_changed",
    ))

    assert outcome.memory_advanced is True
    assert outcome.reason == "matched_accepted_interrupted_command_result"
    assert host.memory_for("session", "actor").active_routine is None


def test_policy_host_twinned_transform_reassesses_fresh_multi_target_spell_row() -> None:
    """A targeting transform competes with an existing cast then binds fresh targets."""
    host = PolicyHost()
    first_world = _spell_transform_world("twinned")

    first = host.decide(first_world)

    assert isinstance(first.selected.intent, ExecuteIntent)
    assert first.selected.intent.row_id == "opaque-transform"
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="transform-command",
    )
    host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        command_id="transform-command",
        row_id="opaque-transform",
    ))

    progress = host.memory_for("session", "actor").active_routine
    assert progress is not None
    assert progress.goal is not None
    assert progress.goal.required_target_allocation is TargetAllocation.MULTI_ENTITY
    assert progress.goal.minimum_selected_targets == 2
    assert "fresh-twinned-spell" not in progress.model_dump_json()

    second_world = _spell_transform_followup_world(first_world, "twinned")
    second = host.decide(second_world)

    assert isinstance(second.selected.intent, ExecuteIntent)
    assert second.selected.intent.row_id == "fresh-twinned-spell"
    assert len(second.selected.intent.extra_target_uuids) == 1
    assert second.selected.intent.extra_target_uuids[0] in {
        "visible-hostile",
        "visible-hostile-2",
    }


def test_accepted_spell_clears_transform_progress_when_fresh_utility_preempts_goal() -> None:
    """Any accepted matching consumption shape ends temporary transform memory."""
    host = PolicyHost()
    first_world = _spell_transform_world("quickened")
    host.decide(first_world)
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="transform-command",
    )
    host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        command_id="transform-command",
        row_id="opaque-transform",
    ))
    second_world = _quickened_competing_area_world(
        _spell_transform_followup_world(first_world, "quickened")
    )

    decision = host.decide(second_world)
    assert isinstance(decision.selected.intent, ExecuteIntent)
    assert decision.selected.intent.row_id == "competing-area-spell"
    binding = host.binding_for("session", "actor", "epoch-2")
    assert binding.routine_plan is None
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-2",
        command_id="area-command",
    )
    host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="area-command",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-2",
        current_epoch_id="epoch-3",
        row_id="competing-area-spell",
        action_resolution=ActionResolutionStatus.COMPLETED,
    ))

    assert host.memory_for("session", "actor").active_routine is None


def test_enable_then_act_preserves_followup_action_economy() -> None:
    """An enabler cannot consume the same sole economy unit as its follow-up."""
    world = _approach_combat_world()
    epoch = world.current_epoch
    assert epoch is not None
    move = epoch.affordances.position_actions[0].model_copy(
        update={"cost": ActionCostProfile(bonus_action_cost=1, movement_cost=15)}
    )
    capability = epoch.affordances.capabilities[0].model_copy(
        update={"cost": ActionCostProfile(bonus_action_cost=1)}
    )
    affordances = epoch.affordances.model_copy(update={
        "position_actions": [move],
        "capabilities": [capability],
    })
    constrained_epoch = epoch.model_copy(update={
        "economy": epoch.economy.model_copy(update={"bonus_actions": 1}),
        "affordances": affordances,
    })
    world = world.model_copy(update={"current_epoch": constrained_epoch})

    decision = PolicyHost().decide(world)

    assert decision.selected.intent.kind == "end_turn"
    assert decision.selected.reason == "no_higher_value_legal_tactical_or_information_action"


def test_policy_host_ends_spent_no_contact_turn_with_opaque_row() -> None:
    """A spent actor receives the shared terminal command without legacy fallback."""
    world = _door_world()
    epoch = world.current_epoch
    assert epoch is not None
    opaque = ActionAffordance(
        row_id="self|opaque-action|index=0",
        bucket="self_actions",
        template_name="Opaque Action",
        display_name="Opaque Action",
        action_category="ability",
        target_type="self",
        can_afford=False,
        cost=ActionCostProfile(action_cost=1),
        targets=[ActionTarget(index=0, target_uuid="actor")],
    )
    spent_epoch = epoch.model_copy(update={
        "economy": epoch.economy.model_copy(update={
            "actions": 0,
            "bonus_actions": 0,
            "movement_remaining": 0,
            "meaningful_commands_remaining": False,
        }),
        "affordances": AffordanceSet(
            actor_uuid="actor",
            computed_at_observation_cursor=1,
            self_actions=[opaque],
        ),
    })
    world = world.model_copy(update={
        "known_objects": {},
        "current_epoch": spent_epoch,
    })
    host = PolicyHost()

    decision = host.decide(world)

    assert isinstance(decision.selected.intent, EndTurnIntent)
    assert decision.selected.goal is PolicyGoal.END_TURN
    assert host.binding_for("session", "actor", "epoch-1").routine_plan is None
    assert "ReactiveRoot/TerminalFallback/EndTurn" in {
        step.node_path for step in decision.trace
    }
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="terminal-end-turn",
    )
    missing_row = host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="terminal-end-turn",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-1",
        current_epoch_id="epoch-2",
        row_id=None,
    ))
    assert missing_row.disposition is PolicyResultDisposition.UNMATCHED
    assert missing_row.reason == "end_turn_result_row_mismatch"
    assert host.pending_submission("terminal-end-turn") is not None

    outcome = host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="terminal-end-turn",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-1",
        current_epoch_id="epoch-2",
        row_id=END_TURN_ROW_ID,
    ))
    assert outcome.disposition is PolicyResultDisposition.ACCEPTED
    assert outcome.reason == "matched_accepted_command_result"
    assert outcome.memory_advanced is False
    assert host.pending_submission("terminal-end-turn") is None


def test_enable_then_act_reuses_los_for_equivalent_subjective_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Counterfactual LOS work scales with geometry, not capability count."""
    world = _approach_combat_world()
    epoch = world.current_epoch
    assert epoch is not None
    base_move = epoch.affordances.position_actions[0]
    base_capability = epoch.affordances.capabilities[0]
    moves = [
        base_move.model_copy(update={"row_id": f"approach-{index}"})
        for index in range(20)
    ]
    capabilities = [
        base_capability.model_copy(update={"capability_id": f"melee-{index}"})
        for index in range(20)
    ]
    affordances = epoch.affordances.model_copy(
        update={"position_actions": moves, "capabilities": capabilities}
    )
    world = world.model_copy(
        update={"current_epoch": epoch.model_copy(update={"affordances": affordances})}
    )
    calls = 0
    original = policy_routines.known_line_of_sight

    def counted_line_of_sight(
        subjective_world: SubjectiveWorldState,
        origin: tuple[int, int],
        target: tuple[int, int],
        *,
        vision_blocker_positions: AbstractSet[tuple[int, int]] | None = None,
        workspace: policy_routines.KnownLineOfSightWorkspace | None = None,
    ) -> TruthValue:
        nonlocal calls
        calls += 1
        return original(
            subjective_world,
            origin,
            target,
            vision_blocker_positions=vision_blocker_positions,
            workspace=workspace,
        )

    monkeypatch.setattr(policy_routines, "known_line_of_sight", counted_line_of_sight)

    decision = PolicyHost().decide(world)

    assert isinstance(decision.selected.intent, ExecuteIntent)
    assert decision.selected.intent.row_id == "approach-0"
    assert calls == 1


def _accept_spacing_retreat(host: PolicyHost, world: SubjectiveWorldState) -> None:
    """Select and accept the first epoch's typed spacing movement."""
    decision = host.decide(world)
    assert decision.selected.intent == ExecuteIntent(row_id="retreat-floor", prefer_safe=True)
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="spacing-command",
    )
    outcome = host.record_result(_result(
        CommandResultStatus.ACCEPTED,
        command_id="spacing-command",
        row_id="retreat-floor",
    ))
    assert outcome.disposition is PolicyResultDisposition.ACCEPTED


def _same_turn_spacing_world() -> SubjectiveWorldState:
    """Build a spent ranged epoch whose best movement establishes six cells."""
    world = _door_world()
    epoch = world.current_epoch
    assert epoch is not None
    movement_semantics = ActionSemantics(
        semantic_id="movement.spacing.test",
        tags=frozenset({ActionTag.MOVEMENT_VOLUNTARY}),
    )
    movement_ref = action_semantics_ref(movement_semantics)
    damage_semantics = ActionSemantics(
        semantic_id="damage.ranged.test",
        tags=frozenset({ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}),
    )
    damage_ref = action_semantics_ref(damage_semantics)

    def movement_row(row_id: str, position: tuple[int, int]) -> ActionAffordance:
        movement_cost = abs(position[0]) * 5
        return ActionAffordance(
            row_id=row_id,
            bucket="position_actions",
            template_name="Relocate",
            semantic_key="movement.spacing.test",
            display_name="Relocate",
            action_category="movement",
            target_type="position_path",
            can_afford=True,
            cost=ActionCostProfile(movement_cost=movement_cost),
            targets=[ActionTarget(
                index=0,
                position=position,
                path_cost=movement_cost,
                safe_path_cost=movement_cost,
            )],
            semantic_id=movement_semantics.semantic_id,
            semantics_ref=movement_ref,
            tags=sorted(tag.value for tag in movement_semantics.tags),
        )

    capability = ActionCapability(
        capability_id="ranged-capability",
        semantic_key="damage.ranged.test",
        action_category="attack",
        target_type="entity",
        cost=ActionCostProfile(action_cost=1),
        range_type="Ranged",
        normal_range_feet=120,
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        semantic_id=damage_semantics.semantic_id,
        semantics_ref=damage_ref,
        tags=sorted(tag.value for tag in damage_semantics.tags),
        outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=5,
            damage_rolls=(DamageRollProfile(
                dice_count=1,
                die_size=8,
                flat_bonus=3,
                damage_type="piercing",
            ),),
        ),
    )
    affordances = AffordanceSet(
        actor_uuid="actor",
        computed_at_observation_cursor=1,
        position_actions=[
            movement_row("retreat-progress", (-2, 0)),
            movement_row("retreat-floor", (-4, 0)),
        ],
        capabilities=[capability],
        semantic_catalog={
            movement_ref: movement_semantics,
            damage_ref: damage_semantics,
        },
    )
    entities = dict(world.known_entities)
    entities["spacing-target"] = ObservationEntityFact(
        uuid="spacing-target",
        name="Spacing Target",
        knowledge_state=KnowledgeState.VISIBLE,
        controlled=False,
        position=(2, 0),
        hp=20,
        max_hp=20,
        ac=13,
        faction="heroes",
        is_dead=False,
    )
    spent_epoch = epoch.model_copy(update={
        "economy": epoch.economy.model_copy(update={
            "actions": 0,
            "extra_attacks": 0,
            "movement_remaining": 30,
        }),
        "affordances": affordances,
    })
    return world.model_copy(update={
        "known_entities": entities,
        "known_objects": {},
        "current_epoch": spent_epoch,
    })


def _same_turn_spacing_followup_world(
    first_world: SubjectiveWorldState,
    *,
    target_position: tuple[int, int],
    movement_positions: tuple[tuple[int, int], ...],
) -> SubjectiveWorldState:
    """Build a fresh same-turn epoch with a remembered spacing target."""
    first_epoch = first_world.current_epoch
    assert first_epoch is not None
    movement_semantics = ActionSemantics(
        semantic_id="movement.followup.test",
        tags=frozenset({
            ActionTag.MOVEMENT_VOLUNTARY,
            ActionTag.INFORMATION_REVEAL,
        }),
    )
    movement_ref = action_semantics_ref(movement_semantics)
    rows = []
    for index, position in enumerate(movement_positions):
        movement_cost = (abs(position[0] + 4) + abs(position[1])) * 5
        rows.append(ActionAffordance(
            row_id=f"followup-move:{position[0]},{position[1]}",
            bucket="position_actions",
            template_name="Investigate",
            semantic_key="movement.followup.test",
            display_name="Investigate",
            action_category="movement",
            target_type="position_path",
            can_afford=True,
            cost=ActionCostProfile(movement_cost=movement_cost),
            targets=[ActionTarget(
                index=index,
                position=position,
                path_cost=movement_cost,
                safe_path_cost=movement_cost,
            )],
            semantic_id=movement_semantics.semantic_id,
            semantics_ref=movement_ref,
            tags=sorted(tag.value for tag in movement_semantics.tags),
        ))
    catalog = dict(first_epoch.affordances.semantic_catalog)
    catalog[movement_ref] = movement_semantics
    affordances = AffordanceSet(
        actor_uuid="actor",
        computed_at_observation_cursor=2,
        position_actions=rows,
        capabilities=first_epoch.affordances.capabilities,
        semantic_catalog=catalog,
    )
    entities = dict(first_world.known_entities)
    entities["actor"] = entities["actor"].model_copy(update={"position": (-4, 0)})
    entities["spacing-target"] = entities["spacing-target"].model_copy(update={
        "knowledge_state": KnowledgeState.REMEMBERED,
        "position": target_position,
    })
    known_tiles = dict(first_world.known_tiles)
    for position in movement_positions:
        key = f"{position[0]},{position[1]}"
        known_tiles[key] = ObservationTileFact(
            key=key,
            position=position,
            knowledge_state=KnowledgeState.SEEN,
            walkable=True,
            walking_cost=5,
            is_hazardous=False,
            adjacent_domain={
                offset: SpatialDomainKnowledge.UNKNOWN
                for offset in AdjacentOffset
            },
        )
    second_epoch = first_epoch.model_copy(update={
        "epoch_id": "epoch-2",
        "epoch_index": 2,
        "basis_observation_cursor": 2,
        "reason": DecisionEpochReason.ACTION_COMPLETED,
        "economy": first_epoch.economy.model_copy(update={"movement_remaining": 30}),
        "affordances": affordances,
    })
    return first_world.model_copy(update={
        "observation_cursor": 2,
        "known_entities": entities,
        "known_tiles": known_tiles,
        "known_objects": {},
        "current_epoch": second_epoch,
        "epoch_cursor": 2,
    })


def _door_world() -> SubjectiveWorldState:
    """Build one no-contact subjective epoch with a legal door approach."""
    semantics = ActionSemantics(
        semantic_id="movement.voluntary",
        tags=frozenset({ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_REVEAL}),
    )
    semantics_ref = action_semantics_ref(semantics)
    move = ActionAffordance(
        row_id="move-row",
        bucket="position_actions",
        template_name="Traverse Quietly",
        display_name="Traverse Quietly",
        action_category="movement",
        target_type="position",
        can_afford=True,
        targets=[
            ActionTarget(
                index=7,
                position=(2, 0),
                path_cost=10,
                path=[(0, 0), (1, 0), (2, 0)],
            )
        ],
        target_options=[
            ActionTarget(
                index=7,
                position=(2, 0),
                path_cost=10,
                path=[(0, 0), (1, 0), (2, 0)],
            )
        ],
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
        tags=sorted(tag.value for tag in semantics.tags),
    )
    affordances = AffordanceSet(
        actor_uuid="actor",
        computed_at_observation_cursor=1,
        position_actions=[move],
        semantic_catalog={semantics_ref: semantics},
    )
    epoch = DecisionEpoch(
        epoch_id="epoch-1",
        epoch_index=1,
        basis_observation_cursor=1,
        reason=DecisionEpochReason.TURN_START,
        actor_uuid="actor",
        round_number=1,
        turn_index=0,
        economy=ActionEconomyState(
            actor_uuid="actor",
            actions=1,
            bonus_actions=1,
            reactions=1,
            movement_remaining=30,
            meaningful_commands_remaining=True,
        ),
        affordances=affordances,
    )
    return SubjectiveWorldState(
        observation_cursor=1,
        session=ObservationSessionState(
            session_id="session",
            player_type="ai",
            name="AI Monsters",
            connection_status="connected",
            controlled_entity_uuids=["actor"],
            active_entity_uuid="actor",
            active_entity_name="Skeleton",
            is_my_turn=True,
        ),
        known_entities={
            "actor": ObservationEntityFact(
                uuid="actor",
                name="Skeleton",
                knowledge_state=KnowledgeState.VISIBLE,
                controlled=True,
                position=(0, 0),
                hp=13,
                max_hp=13,
                faction="monsters",
            )
        },
        known_objects={
            "door": ObservationObjectFact(
                uuid="door",
                name="Boundary",
                knowledge_state=KnowledgeState.VISIBLE,
                position=(3, 0),
                state={"is_open": False},
            )
        },
        known_tiles={
            f"{x},0": ObservationTileFact(
                key=f"{x},0",
                position=(x, 0),
                knowledge_state=KnowledgeState.VISIBLE,
                walkable=True,
                walking_cost=5,
                is_hazardous=False,
            )
            for x in range(5)
        },
        current_epoch=epoch,
        epoch_cursor=1,
    )


def _combat_world() -> SubjectiveWorldState:
    """Build the rotation-03 adjacent-hostile decision shape."""
    world = _door_world()
    semantics = ActionSemantics(
        semantic_id="attack.weapon.melee",
        tags=frozenset({ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}),
    )
    semantics_ref = action_semantics_ref(semantics)
    attack = ActionAffordance(
        row_id="melee-attack",
        bucket="entity_actions",
        template_name="Attack_MELEE_MAIN",
        display_name="Melee Attack",
        action_category="attack",
        target_type="entity",
        can_afford=True,
        targets=[
            ActionTarget(
                index=0,
                target_uuid="visible-hostile",
                target_name="Barbarian",
                position=(1, 0),
                distance=5,
            )
        ],
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
        tags=sorted(tag.value for tag in semantics.tags),
    )
    epoch = world.current_epoch
    assert epoch is not None
    affordances = epoch.affordances.model_copy(
        update={
            "entity_actions": [attack],
            "semantic_catalog": {
                **epoch.affordances.semantic_catalog,
                semantics_ref: semantics,
            },
        }
    )
    entities = dict(world.known_entities)
    entities["visible-hostile"] = ObservationEntityFact(
        uuid="visible-hostile",
        name="Barbarian",
        knowledge_state=KnowledgeState.VISIBLE,
        controlled=False,
        position=(1, 0),
        hp=49,
        max_hp=55,
        faction="heroes",
    )
    return world.model_copy(
        update={
            "known_entities": entities,
            "current_epoch": epoch.model_copy(update={"affordances": affordances}),
        }
    )


def _transient_augmentation_world(*, augmented: bool = False) -> SubjectiveWorldState:
    """Build a melee epoch where a zero-cost setup improves attack reliability."""
    world = _combat_world()
    epoch = world.current_epoch
    assert epoch is not None
    attack = epoch.affordances.entity_actions[0]
    attack_semantics = epoch.affordances.semantic_catalog[attack.semantics_ref]
    attack = attack.model_copy(update={
        "cost": ActionCostProfile(action_cost=1),
        "weapon_slot": "MELEE_MAIN",
        "outcome_profile": ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=5,
            advantage=(
                OutcomeAdvantage.ADVANTAGE
                if augmented
                else OutcomeAdvantage.NONE
            ),
            damage_rolls=(DamageRollProfile(
                dice_count=1,
                die_size=8,
                flat_bonus=3,
                damage_type="slashing",
            ),),
        ),
    })
    setup_semantics = ActionSemantics(
        semantic_id="setup.transient.opaque",
        tags=frozenset({ActionTag.SETUP_SELF}),
        self_setup=SelfSetupSemantics(
            duration=SelfSetupDuration.UNTIL_NEXT_TURN,
            active_condition_semantic_keys=frozenset({"test.TransientAugmentation"}),
            grants_outgoing_attack_advantage=True,
            grants_incoming_attack_advantage=True,
            outcome_adjustments=(CapabilityOutcomeAdjustment(
                selector=CapabilitySelector(
                    action_categories=frozenset({"attack"}),
                    required_tags=frozenset({ActionTag.ATTACK_WEAPON}),
                    weapon_slots=frozenset({"MELEE_MAIN", "MELEE_OFF"}),
                ),
                advantage_step_delta=1,
            ),),
        ),
    )
    setup_ref = action_semantics_ref(setup_semantics)
    setup = ActionAffordance(
        row_id="transient-augmentation",
        bucket="self_actions",
        template_name="Opaque transient augmentation",
        semantic_key="setup.transient.opaque",
        display_name="Opaque transient augmentation",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(),
        semantic_id=setup_semantics.semantic_id,
        semantics_ref=setup_ref,
        tags=tuple(tag.value for tag in setup_semantics.tags),
    )
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": (attack,),
        "self_actions": tuple() if augmented else (setup,),
        "semantic_catalog": {
            attack.semantics_ref: attack_semantics,
            setup_ref: setup_semantics,
        },
    })
    actor = world.known_entities["actor"].model_copy(update={
        "condition_semantic_keys": (
            ("test.TransientAugmentation",) if augmented else tuple()
        ),
    })
    hostile = world.known_entities["visible-hostile"].model_copy(update={
        "ac": 15,
        "hp": 20,
        "max_hp": 20,
    })
    entities = dict(world.known_entities)
    entities[actor.uuid] = actor
    entities[hostile.uuid] = hostile
    if augmented:
        affordances = affordances.model_copy(update={
            "computed_at_observation_cursor": 2,
        })
    next_epoch = epoch.model_copy(update={
        "epoch_id": "epoch-2" if augmented else "epoch-1",
        "epoch_index": 2 if augmented else 1,
        "basis_observation_cursor": 2 if augmented else 1,
        "reason": (
            DecisionEpochReason.ACTION_COMPLETED
            if augmented
            else DecisionEpochReason.TURN_START
        ),
        "affordances": affordances,
    })
    return world.model_copy(update={
        "observation_cursor": 2 if augmented else 1,
        "known_entities": entities,
        "current_epoch": next_epoch,
        "epoch_cursor": 2 if augmented else 1,
    })


def _approach_combat_world() -> SubjectiveWorldState:
    """Build visible combat where movement can enable a known melee capability."""
    world = _door_world()
    epoch = world.current_epoch
    assert epoch is not None
    move_semantics = next(iter(epoch.affordances.semantic_catalog.values()))
    move_ref = action_semantics_ref(move_semantics)
    move = ActionAffordance(
        row_id="approach-hostile",
        bucket="position_actions",
        template_name="Traverse",
        semantic_key="movement.test",
        display_name="Traverse",
        action_category="movement",
        target_type="position_path",
        can_afford=True,
        cost=ActionCostProfile(movement_cost=15),
        targets=[
            ActionTarget(
                index=3,
                position=(3, 0),
                path_cost=15,
                path=[(0, 0), (1, 0), (2, 0), (3, 0)],
            )
        ],
        semantic_id=move_semantics.semantic_id,
        semantics_ref=move_ref,
        tags=sorted(tag.value for tag in move_semantics.tags),
    )
    damage_semantics = ActionSemantics(
        semantic_id="attack.weapon.melee",
        tags=frozenset({ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}),
    )
    damage_ref = action_semantics_ref(damage_semantics)
    capability = ActionCapability(
        capability_id="melee-capability",
        semantic_key="attack.test",
        action_category="attack",
        target_type="entity",
        cost=ActionCostProfile(action_cost=1),
        range_type="Reach",
        normal_range_feet=5,
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        weapon_slot="MELEE_MAIN",
        semantic_id=damage_semantics.semantic_id,
        semantics_ref=damage_ref,
        tags=sorted(tag.value for tag in damage_semantics.tags),
    )
    affordances = epoch.affordances.model_copy(
        update={
            "position_actions": [move],
            "entity_actions": [],
            "capabilities": [capability],
            "semantic_catalog": {
                move_ref: move_semantics,
                damage_ref: damage_semantics,
            },
        }
    )
    entities = dict(world.known_entities)
    entities["visible-hostile"] = ObservationEntityFact(
        uuid="visible-hostile",
        name="Target",
        knowledge_state=KnowledgeState.VISIBLE,
        controlled=False,
        position=(4, 0),
        hp=20,
        max_hp=20,
        faction="heroes",
    )
    return world.model_copy(
        update={
            "known_entities": entities,
            "known_objects": {},
            "current_epoch": epoch.model_copy(update={"affordances": affordances}),
        }
    )


def _distant_capability_pursuit_world() -> SubjectiveWorldState:
    """Build visible combat where one full move cannot enable melee damage."""
    world = _approach_combat_world()
    epoch = world.current_epoch
    assert epoch is not None
    movement = epoch.affordances.position_actions[0]
    advance = movement.model_copy(update={
        "row_id": "pursuit-advance",
        "cost": ActionCostProfile(movement_cost=40),
        "targets": [ActionTarget(
            index=8,
            position=(8, 0),
            path_cost=40,
            safe_path_cost=40,
            path=[(x, 0) for x in range(9)],
            safe_path=[(x, 0) for x in range(9)],
        )],
    })
    affordances = epoch.affordances.model_copy(update={
        "position_actions": [advance],
        "entity_actions": [],
    })
    entities = dict(world.known_entities)
    entities["visible-hostile"] = entities["visible-hostile"].model_copy(
        update={"position": (12, 0)}
    )
    known_tiles = {
        f"{x},0": ObservationTileFact(
            key=f"{x},0",
            position=(x, 0),
            knowledge_state=KnowledgeState.VISIBLE,
            walkable=True,
            walking_cost=5,
            is_hazardous=False,
        )
        for x in range(13)
    }
    return world.model_copy(update={
        "known_entities": entities,
        "known_tiles": known_tiles,
        "current_epoch": epoch.model_copy(update={
            "economy": epoch.economy.model_copy(update={
                "actions": 1,
                "movement_remaining": 40,
                "extra_attacks": 1,
                "meaningful_commands_remaining": True,
            }),
            "affordances": affordances,
        }),
    })


def _pursuit_after_first_move_world(
    first_world: SubjectiveWorldState,
) -> SubjectiveWorldState:
    """Materialize the same turn after ordinary movement is exhausted."""
    first_epoch = first_world.current_epoch
    assert first_epoch is not None
    dash_semantics = ActionSemantics(
        semantic_id="mobility.extend.test",
        tags=frozenset({ActionTag.MOBILITY_EXTEND}),
    )
    dash_ref = action_semantics_ref(dash_semantics)
    dash = ActionAffordance(
        row_id="pursuit-dash",
        bucket="self_actions",
        template_name="Extend Mobility",
        semantic_key="mobility.extend.test",
        display_name="Extend Mobility",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        semantic_id=dash_semantics.semantic_id,
        semantics_ref=dash_ref,
        tags=[ActionTag.MOBILITY_EXTEND.value],
    )
    actor = first_world.known_entities["actor"].model_copy(update={"position": (8, 0)})
    affordances = first_epoch.affordances.model_copy(update={
        "computed_at_observation_cursor": 2,
        "position_actions": [],
        "self_actions": [dash],
        "semantic_catalog": {
            **first_epoch.affordances.semantic_catalog,
            dash_ref: dash_semantics,
        },
    })
    return first_world.model_copy(update={
        "observation_cursor": 2,
        "known_entities": {**first_world.known_entities, "actor": actor},
        "current_epoch": first_epoch.model_copy(update={
            "epoch_id": "epoch-2",
            "epoch_index": 2,
            "basis_observation_cursor": 2,
            "reason": DecisionEpochReason.ACTION_COMPLETED,
            "economy": first_epoch.economy.model_copy(update={
                "actions": 1,
                "movement_remaining": 0,
                "extra_attacks": 1,
            }),
            "affordances": affordances,
        }),
        "epoch_cursor": 2,
    })


def _pursuit_after_dash_world(
    after_move: SubjectiveWorldState,
) -> SubjectiveWorldState:
    """Materialize fresh ordinary movement after typed mobility extension."""
    epoch = after_move.current_epoch
    assert epoch is not None
    movement_semantics = next(
        semantics
        for semantics in epoch.affordances.semantic_catalog.values()
        if ActionTag.MOVEMENT_VOLUNTARY in semantics.tags
    )
    movement_ref = action_semantics_ref(movement_semantics)
    move = ActionAffordance(
        row_id="pursuit-final-advance",
        bucket="position_actions",
        template_name="Traverse",
        semantic_key="movement.test",
        display_name="Traverse",
        action_category="movement",
        target_type="position_path",
        can_afford=True,
        cost=ActionCostProfile(movement_cost=15),
        targets=[ActionTarget(
            index=3,
            position=(11, 0),
            path_cost=15,
            safe_path_cost=15,
            path=[(8, 0), (9, 0), (10, 0), (11, 0)],
            safe_path=[(8, 0), (9, 0), (10, 0), (11, 0)],
        )],
        semantic_id=movement_semantics.semantic_id,
        semantics_ref=movement_ref,
        tags=sorted(tag.value for tag in movement_semantics.tags),
    )
    affordances = epoch.affordances.model_copy(update={
        "computed_at_observation_cursor": 3,
        "position_actions": [move],
        "self_actions": [],
    })
    return after_move.model_copy(update={
        "observation_cursor": 3,
        "current_epoch": epoch.model_copy(update={
            "epoch_id": "epoch-3",
            "epoch_index": 3,
            "basis_observation_cursor": 3,
            "economy": epoch.economy.model_copy(update={
                "actions": 0,
                "movement_remaining": 40,
                "extra_attacks": 0,
            }),
            "affordances": affordances,
        }),
        "epoch_cursor": 3,
    })


def _pursuit_second_extension_world(
    after_move: SubjectiveWorldState,
) -> SubjectiveWorldState:
    """Offer another same-turn mobility extension after one was accepted."""
    epoch = after_move.current_epoch
    assert epoch is not None
    first_dash = epoch.affordances.self_actions[0]
    second_dash = first_dash.model_copy(update={
        "row_id": "pursuit-second-dash",
        "cost": ActionCostProfile(bonus_action_cost=1),
    })
    affordances = epoch.affordances.model_copy(update={
        "computed_at_observation_cursor": 3,
        "position_actions": [],
        "self_actions": [second_dash],
    })
    return after_move.model_copy(update={
        "observation_cursor": 3,
        "current_epoch": epoch.model_copy(update={
            "epoch_id": "epoch-3-second-extension",
            "epoch_index": 3,
            "basis_observation_cursor": 3,
            "economy": epoch.economy.model_copy(update={
                "actions": 0,
                "bonus_actions": 1,
                "movement_remaining": 0,
            }),
            "affordances": affordances,
        }),
        "epoch_cursor": 3,
    })


def _pursuit_after_second_move_world(
    after_dash: SubjectiveWorldState,
) -> SubjectiveWorldState:
    """Materialize adjacent target contact with no attack economy remaining."""
    epoch = after_dash.current_epoch
    assert epoch is not None
    actor = after_dash.known_entities["actor"].model_copy(update={"position": (11, 0)})
    affordances = epoch.affordances.model_copy(update={
        "computed_at_observation_cursor": 4,
        "entity_actions": [],
        "position_actions": [],
        "self_actions": [],
    })
    return after_dash.model_copy(update={
        "observation_cursor": 4,
        "known_entities": {**after_dash.known_entities, "actor": actor},
        "current_epoch": epoch.model_copy(update={
            "epoch_id": "epoch-4",
            "epoch_index": 4,
            "basis_observation_cursor": 4,
            "economy": epoch.economy.model_copy(update={
                "actions": 0,
                "movement_remaining": 25,
                "extra_attacks": 0,
            }),
            "affordances": affordances,
        }),
        "epoch_cursor": 4,
    })


def _pursuit_next_turn_attack_world(
    exhausted: SubjectiveWorldState,
) -> SubjectiveWorldState:
    """Materialize the next turn with a fresh legal row satisfying the goal."""
    epoch = exhausted.current_epoch
    assert epoch is not None
    capability = epoch.affordances.capabilities[0]
    damage_semantics = epoch.affordances.semantic_catalog[capability.semantics_ref]
    attack = ActionAffordance(
        row_id="pursuit-fresh-attack",
        bucket="entity_actions",
        template_name="Strike",
        semantic_key=capability.semantic_key,
        display_name="Strike",
        action_category="attack",
        target_type="entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=[ActionTarget(
            index=0,
            target_uuid="visible-hostile",
            target_name="Target",
            position=(12, 0),
            distance=5,
        )],
        semantic_id=damage_semantics.semantic_id,
        semantics_ref=capability.semantics_ref,
        tags=sorted(tag.value for tag in damage_semantics.tags),
    )
    affordances = epoch.affordances.model_copy(update={
        "computed_at_observation_cursor": 5,
        "entity_actions": [attack],
        "position_actions": [],
    })
    return exhausted.model_copy(update={
        "observation_cursor": 5,
        "current_epoch": epoch.model_copy(update={
            "epoch_id": "epoch-5",
            "epoch_index": 5,
            "basis_observation_cursor": 5,
            "round_number": epoch.round_number + 1,
            "economy": epoch.economy.model_copy(update={
                "actions": 1,
                "movement_remaining": 40,
                "extra_attacks": 1,
            }),
            "affordances": affordances,
        }),
        "epoch_cursor": 5,
    })


def _approach_followup_world(first_world: SubjectiveWorldState) -> SubjectiveWorldState:
    """Materialize the fresh epoch where the semantic goal became executable."""
    first_epoch = first_world.current_epoch
    assert first_epoch is not None
    damage_capability = first_epoch.affordances.capabilities[0]
    damage_semantics = first_epoch.affordances.semantic_catalog[damage_capability.semantics_ref]
    attack = ActionAffordance(
        row_id="followup-attack",
        bucket="entity_actions",
        template_name="Strike",
        semantic_key=damage_capability.semantic_key,
        display_name="Strike",
        action_category="attack",
        target_type="entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=[
            ActionTarget(
                index=0,
                target_uuid="visible-hostile",
                target_name="Target",
                position=(4, 0),
                distance=5,
            )
        ],
        semantic_id=damage_semantics.semantic_id,
        semantics_ref=damage_capability.semantics_ref,
        tags=sorted(tag.value for tag in damage_semantics.tags),
    )
    affordances = first_epoch.affordances.model_copy(
        update={"entity_actions": [attack], "position_actions": []}
    )
    actor = first_world.known_entities["actor"].model_copy(update={"position": (3, 0)})
    entities = {**first_world.known_entities, "actor": actor}
    second_epoch = first_epoch.model_copy(
        update={
            "epoch_id": "epoch-2",
            "epoch_index": 2,
            "basis_observation_cursor": 2,
            "reason": DecisionEpochReason.ACTION_COMPLETED,
            "economy": first_epoch.economy.model_copy(update={"movement_remaining": 15}),
            "affordances": affordances.model_copy(update={"computed_at_observation_cursor": 2}),
        }
    )
    return first_world.model_copy(
        update={
            "observation_cursor": 2,
            "known_entities": entities,
            "current_epoch": second_epoch,
            "epoch_cursor": 2,
        }
    )


def _approach_failed_followup_world(first_world: SubjectiveWorldState) -> SubjectiveWorldState:
    """Materialize a fresh epoch where the accepted enabler produced no attack row."""
    first_epoch = first_world.current_epoch
    assert first_epoch is not None
    movement = first_epoch.affordances.position_actions[0]
    reverse = movement.model_copy(update={
        "row_id": "reverse-enabler",
        "targets": [ActionTarget(
            index=0,
            position=(0, 0),
            path_cost=15,
            path=[(3, 0), (2, 0), (1, 0), (0, 0)],
        )],
        "target_options": [ActionTarget(
            index=0,
            position=(0, 0),
            path_cost=15,
            path=[(3, 0), (2, 0), (1, 0), (0, 0)],
        )],
    })
    affordances = first_epoch.affordances.model_copy(update={
        "entity_actions": [],
        "position_actions": [reverse],
        "computed_at_observation_cursor": 2,
    })
    entities = dict(first_world.known_entities)
    entities["actor"] = entities["actor"].model_copy(update={"position": (3, 0)})
    second_epoch = first_epoch.model_copy(update={
        "epoch_id": "epoch-2",
        "epoch_index": 2,
        "basis_observation_cursor": 2,
        "reason": DecisionEpochReason.ACTION_COMPLETED,
        "economy": first_epoch.economy.model_copy(update={"movement_remaining": 15}),
        "affordances": affordances,
    })
    return first_world.model_copy(update={
        "observation_cursor": 2,
        "known_entities": entities,
        "current_epoch": second_epoch,
        "epoch_cursor": 2,
    })


def _approach_interrupted_followup_world(
    first_world: SubjectiveWorldState,
) -> SubjectiveWorldState:
    """Materialize a partial move with enough economy to continue the approach."""
    first_epoch = first_world.current_epoch
    assert first_epoch is not None
    movement = first_epoch.affordances.position_actions[0]
    continuation = movement.model_copy(update={
        "row_id": "continue-approach",
        "cost": ActionCostProfile(movement_cost=10),
        "targets": [ActionTarget(
            index=3,
            position=(3, 0),
            path_cost=10,
            path=[(1, 0), (2, 0), (3, 0)],
        )],
        "target_options": [ActionTarget(
            index=3,
            position=(3, 0),
            path_cost=10,
            path=[(1, 0), (2, 0), (3, 0)],
        )],
    })
    affordances = first_epoch.affordances.model_copy(update={
        "entity_actions": [],
        "position_actions": [continuation],
        "computed_at_observation_cursor": 2,
    })
    entities = dict(first_world.known_entities)
    entities["actor"] = entities["actor"].model_copy(update={"position": (1, 0)})
    second_epoch = first_epoch.model_copy(update={
        "epoch_id": "epoch-2",
        "epoch_index": 2,
        "basis_observation_cursor": 2,
        "reason": DecisionEpochReason.MOVEMENT_REVALIDATION,
        "economy": first_epoch.economy.model_copy(update={"movement_remaining": 25}),
        "affordances": affordances,
    })
    return first_world.model_copy(update={
        "observation_cursor": 2,
        "known_entities": entities,
        "current_epoch": second_epoch,
        "epoch_cursor": 2,
    })


def _spell_transform_world(kind: str) -> SubjectiveWorldState:
    """Build visible spell combat with one legal generic transform activation."""
    world = _approach_combat_world()
    epoch = world.current_epoch
    assert epoch is not None
    spell_semantics = ActionSemantics(
        semantic_id="damage.single_target",
        tags=frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_SINGLE_TARGET}),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.SINGLE_ENTITY,
            minimum_targets=1,
            maximum_targets=1,
            allows_repeated_targets=True,
        ),
    )
    spell_ref = action_semantics_ref(spell_semantics)
    capability = ActionCapability(
        capability_id="opaque-spell-capability",
        semantic_key="spell.opaque",
        action_category="spell",
        target_type="entity",
        cost=ActionCostProfile(
            action_cost=1,
            spell_slot_cost=1,
            affordability="unaffordable" if kind == "quickened" else "affordable",
            affordability_reasons=["actions"] if kind == "quickened" else [],
        ),
        range_type="Range",
        normal_range_feet=60,
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        base_spell_level=1,
        cast_at_level=1,
        semantic_id=spell_semantics.semantic_id,
        semantics_ref=spell_ref,
        tags=sorted(tag.value for tag in spell_semantics.tags),
    )
    if kind == "quickened":
        transformation = CapabilityTransformation(
            transformation_id="transform.test.quickened",
            selector=CapabilitySelector(
                action_categories=frozenset({"spell"}),
                required_cost_resource_ids=frozenset({"action_economy.actions"}),
            ),
            cost_rewrites=(CapabilityCostRewrite(
                operation=CapabilityCostOperation.REPLACE,
                source_resource_id="action_economy.actions",
                target_resource_id="action_economy.bonus_actions",
                amount=CapabilityAmountFormula(
                    source=CapabilityAmountSource.SOURCE_RESOURCE,
                ),
            ),),
            consumed_by=CapabilitySelector(action_categories=frozenset({"spell"})),
        )
        economy = ActionEconomyState(
            actor_uuid="actor",
            actions=0,
            bonus_actions=1,
            spell_slots={1: ResourcePool(current=1, max=1)},
            resources={"sorcery_points": ResourcePool(current=2, max=2)},
            meaningful_commands_remaining=True,
        )
        activation_cost = ActionCostProfile(resource_costs={"sorcery_points": 2})
    else:
        transformation = CapabilityTransformation(
            transformation_id="transform.test.twinned",
            selector=CapabilitySelector(
                action_categories=frozenset({"spell"}),
                target_allocations=frozenset({TargetAllocation.SINGLE_ENTITY}),
            ),
            cost_rewrites=(CapabilityCostRewrite(
                operation=CapabilityCostOperation.ADD,
                target_resource_id="resource.sorcery_points",
                amount=CapabilityAmountFormula(
                    source=CapabilityAmountSource.BASE_SPELL_LEVEL,
                    offset=-1,
                    minimum=0,
                ),
            ),),
            targeting_rewrite=CapabilityTargetingRewrite(
                allocation=TargetAllocation.MULTI_ENTITY,
                minimum_targets=2,
                maximum_targets=2,
            ),
            consumed_by=CapabilitySelector(action_categories=frozenset({"spell"})),
        )
        economy = ActionEconomyState(
            actor_uuid="actor",
            actions=1,
            bonus_actions=1,
            spell_slots={1: ResourcePool(current=1, max=1)},
            resources={"sorcery_points": ResourcePool(current=1, max=1)},
            meaningful_commands_remaining=True,
        )
        activation_cost = ActionCostProfile(resource_costs={"sorcery_points": 1})
    transform_semantics = ActionSemantics(
        semantic_id="transform.opaque",
        tags=frozenset({ActionTag.CAPABILITY_TRANSFORM}),
        capability_transformations=(transformation,),
    )
    transform_ref = action_semantics_ref(transform_semantics)
    activation = ActionAffordance(
        row_id="opaque-transform",
        bucket="self_actions",
        template_name="Opaque",
        semantic_key="transform.opaque",
        display_name="Opaque",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=activation_cost,
        targets=[ActionTarget(index=0, target_uuid="actor")],
        semantic_id=transform_semantics.semantic_id,
        semantics_ref=transform_ref,
        tags=sorted(tag.value for tag in transform_semantics.tags),
    )
    initial_spell_rows: list[ActionAffordance] = []
    entities = dict(world.known_entities)
    if kind == "twinned":
        initial_spell_rows.append(ActionAffordance(
            row_id="initial-single-spell",
            bucket="entity_actions",
            template_name="Opaque Cast",
            semantic_key="spell.opaque",
            display_name="Opaque Cast",
            action_category="spell",
            target_type="entity",
            can_afford=True,
            cost=capability.cost,
            targets=[ActionTarget(
                index=0,
                target_uuid="visible-hostile",
                target_name="Target",
                position=(4, 0),
                distance=20,
            )],
            target_options=[ActionTarget(
                index=0,
                target_uuid="visible-hostile",
                target_name="Target",
                position=(4, 0),
                distance=20,
            )],
            semantic_id=spell_semantics.semantic_id,
            semantics_ref=spell_ref,
            tags=sorted(tag.value for tag in spell_semantics.tags),
        ))
        entities["visible-hostile-2"] = ObservationEntityFact(
            uuid="visible-hostile-2",
            name="Second Target",
            knowledge_state=KnowledgeState.VISIBLE,
            controlled=False,
            position=(5, 0),
            hp=20,
            max_hp=20,
            faction="heroes",
        )
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": initial_spell_rows,
        "position_actions": [],
        "self_actions": [activation],
        "capabilities": [capability],
        "semantic_catalog": {
            spell_ref: spell_semantics,
            transform_ref: transform_semantics,
        },
    })
    return world.model_copy(update={
        "known_entities": entities,
        "known_objects": {},
        "current_epoch": epoch.model_copy(update={
            "economy": economy,
            "affordances": affordances,
        }),
    })


def _spell_transform_followup_world(
    first_world: SubjectiveWorldState,
    kind: str,
) -> SubjectiveWorldState:
    """Build the authoritative post-transform epoch with its fresh legal spell row."""
    first_epoch = first_world.current_epoch
    assert first_epoch is not None
    capability = first_epoch.affordances.capabilities[0]
    original = first_epoch.affordances.semantic_catalog[capability.semantics_ref]
    if kind == "quickened":
        semantics = original
        cost = ActionCostProfile(bonus_action_cost=1, spell_slot_cost=1)
        target_options = [ActionTarget(
            index=0,
            target_uuid="visible-hostile",
            target_name="Target",
            position=(4, 0),
            distance=20,
        )]
        row_id = "fresh-quickened-spell"
    else:
        semantics = original.model_copy(update={
            "tags": frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_MULTI_TARGET}),
            "targeting": original.targeting.model_copy(update={
                "allocation": TargetAllocation.MULTI_ENTITY,
                "minimum_targets": 2,
                "maximum_targets": 2,
            }),
        })
        cost = ActionCostProfile(action_cost=1, spell_slot_cost=1)
        target_options = [
            ActionTarget(
                index=0,
                target_uuid="visible-hostile",
                target_name="Target",
                position=(4, 0),
                distance=20,
            ),
            ActionTarget(
                index=1,
                target_uuid="visible-hostile-2",
                target_name="Second Target",
                position=(5, 0),
                distance=25,
            ),
        ]
        row_id = "fresh-twinned-spell"
    semantics_ref = action_semantics_ref(semantics)
    row = ActionAffordance(
        row_id=row_id,
        bucket="entity_actions",
        template_name="Fresh Opaque Cast",
        semantic_key=capability.semantic_key,
        display_name="Fresh Opaque Cast",
        action_category="spell",
        target_type="entity" if kind == "quickened" else "multi_entity",
        can_afford=True,
        cost=cost,
        targets=[target_options[0]],
        target_options=target_options,
        num_projectiles=2 if kind == "twinned" else None,
        allow_same_target=True if kind == "twinned" else None,
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
        tags=sorted(tag.value for tag in semantics.tags),
    )
    affordances = first_epoch.affordances.model_copy(update={
        "entity_actions": [row],
        "self_actions": [],
        "semantic_catalog": {semantics_ref: semantics},
    })
    second_epoch = first_epoch.model_copy(update={
        "epoch_id": "epoch-2",
        "epoch_index": 2,
        "basis_observation_cursor": 2,
        "reason": DecisionEpochReason.ACTION_COMPLETED,
        "affordances": affordances.model_copy(update={"computed_at_observation_cursor": 2}),
    })
    return first_world.model_copy(update={
        "observation_cursor": 2,
        "current_epoch": second_epoch,
        "epoch_cursor": 2,
    })


def _quickened_competing_area_world(
    world: SubjectiveWorldState,
) -> SubjectiveWorldState:
    """Add a higher-coverage spell that consumes setup but differs from its goal."""
    epoch = world.current_epoch
    assert epoch is not None
    entities = dict(world.known_entities)
    entities["visible-hostile-2"] = ObservationEntityFact(
        uuid="visible-hostile-2",
        name="Second Target",
        knowledge_state=KnowledgeState.VISIBLE,
        controlled=False,
        position=(5, 0),
        hp=20,
        max_hp=20,
        faction="heroes",
    )
    semantics = ActionSemantics(
        semantic_id="damage.area",
        tags=frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_AREA}),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.AREA,
            minimum_targets=1,
            maximum_targets=1,
        ),
    )
    semantics_ref = action_semantics_ref(semantics)
    row = ActionAffordance(
        row_id="competing-area-spell",
        bucket="position_actions",
        template_name="Opaque Area Cast",
        semantic_key="spell.area.opaque",
        display_name="Opaque Area Cast",
        action_category="spell",
        target_type="position_aoe",
        can_afford=True,
        cost=ActionCostProfile(bonus_action_cost=1, spell_slot_cost=1),
        targets=[ActionTarget(
            index=0,
            position=(4, 0),
            affected_entity_uuids=["visible-hostile", "visible-hostile-2"],
            affected_positions=[(4, 0), (5, 0)],
        )],
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
        tags=sorted(tag.value for tag in semantics.tags),
    )
    affordances = epoch.affordances.model_copy(update={
        "position_actions": [row],
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            semantics_ref: semantics,
        },
    })
    return world.model_copy(update={
        "known_entities": entities,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })


def _result(
    status: CommandResultStatus,
    *,
    command_id: str = "command-1",
    actor_uuid: str = "actor",
    row_id: str = "move-row",
    action_resolution: ActionResolutionStatus | None = ActionResolutionStatus.COMPLETED,
) -> CommandResult:
    """Build one server-shaped result for the prepared door command."""
    return CommandResult(
        status=status,
        command_id=command_id,
        session_id="session",
        actor_uuid=actor_uuid,
        requested_epoch_id="epoch-1",
        current_epoch_id="epoch-2" if status is CommandResultStatus.ACCEPTED else "epoch-1",
        row_id=row_id,
        action_resolution=action_resolution,
    )


def _accept_policy_decision(
    host: PolicyHost,
    world: SubjectiveWorldState,
    decision: PolicyDecision,
    command_id: str,
) -> PolicyResultRecord:
    """Prepare and accept one selected command against its exact test epoch."""
    epoch = world.current_epoch
    assert epoch is not None
    intent = decision.selected.intent
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id=epoch.epoch_id,
        command_id=command_id,
    )
    outcome = host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id=command_id,
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id=epoch.epoch_id,
        current_epoch_id=f"{epoch.epoch_id}:next",
        row_id=(
            intent.row_id
            if isinstance(intent, ExecuteIntent)
            else END_TURN_ROW_ID
        ),
        action_resolution=(
            ActionResolutionStatus.COMPLETED
            if isinstance(intent, ExecuteIntent)
            else None
        ),
    ))
    assert outcome.disposition is PolicyResultDisposition.ACCEPTED
    assert host.pending_submission(command_id) is None
    return outcome
