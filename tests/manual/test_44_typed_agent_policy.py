"""Typed subjective facts and shared policy control contracts."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError

import ai.policy.candidates as candidate_module
import ai.policy.outcomes as outcomes_module
from ai.knowledge import TargetEffectBlockHypothesis, derive_agent_facts
from ai.knowledge.topology import KnownLineOfSightWorkspace, known_line_of_sight
from server.agent_protocol.observation import (
    AdjacentOffset,
    KnowledgeState,
    ObservationConditionFact,
    ObservationEncounterState,
    ObservationEffectProtection,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationObserverState,
    ObservationSessionState,
    ObservationTileFact,
    SubjectiveWorldState,
    SpatialDomainKnowledge,
)
from dnd.core.condition_types import ConditionAgencyDenial, ConditionRemovalTrigger
from ai.policy import (
    ExecuteIntent,
    PolicyContext,
    PolicyHost,
    PolicyLogicalTag,
    PolicyMemoryStore,
    PolicyProposal,
    UtilityArbiter,
    command_from_policy_decision,
)
from ai.policy.candidates import (
    build_policy_candidate_set,
    control_candidates,
    direct_damage_candidates,
    spacing_candidates,
    target_effect_candidates,
)
from ai.policy.contracts import (
    CapabilityModelStatus,
    CapabilityProjectionScope,
    CapabilityRangeState,
    CapabilityTargetProjection,
    EndTurnIntent,
    NodeStatus,
    PolicyGoal,
    TargetApplicationEvidence,
    TargetPlanEvidence,
)
from ai.policy.default import evaluate_default_policy
from ai.policy.outcomes import SubjectiveDamageEstimate, estimate_damage_outcome
from ai.policy.tree import (
    ConditionNode,
    ProposalLeaf,
    SelectorNode,
    SequenceNode,
    UtilitySelectorNode,
)
from server.agent_protocol.control import (
    ActionAffordance,
    ActionCapability,
    ActionCostProfile,
    ActionEconomyState,
    ActionTarget,
    ActionOutcomeProfile,
    AffordanceSet,
    DecisionEpoch,
    DecisionEpochReason,
    DamageRollProfile,
    OutcomeApplicationScope,
    OutcomeResolution,
    ResourcePool,
)
from server.agent_protocol.semantics import (
    ActionSemantics,
    ActionTag,
    ComparisonOperator,
    ConcentrationEffect,
    ConcentrationOperation,
    EffectDisposition,
    EffectCertainty,
    EffectOperation,
    FactExpression,
    FactOperator,
    FactPredicate,
    LogicalEffect,
    InformationEffect,
    InformationOperation,
    MovementKind,
    OutcomeKind,
    SelfSetupDuration,
    D20CheckMode,
    SelfSetupMaintenanceSemantics,
    SelfSetupSemantics,
    SetupMaintenanceFailure,
    SetupMaintenanceTrigger,
    SpatialSemantics,
    StochasticEffect,
    TargetAllocation,
    TargetEffectSemantics,
    TargetingSemantics,
    TruthValue,
    WorldEffectAnchor,
    WorldEffectScope,
    WorldEffectShape,
    action_semantics_ref,
)
from ai.subjective.hooks import HookContext, HookPoint, HookRegistry
from ai.subjective.models import AgentState
from ai.subjective.processors import AgentFactsProcessor


def test_typed_facts_preserve_subjective_knowledge_partitions() -> None:
    """Visible, remembered, dead, and unknown contacts remain distinct."""
    world = _world()

    facts = derive_agent_facts(world).facts

    assert facts.contacts.controlled_entity_uuids == ("actor",)
    assert facts.contacts.visible_hostile_uuids == ("visible-enemy",)
    assert facts.contacts.remembered_hostile_uuids == ("remembered-enemy",)
    assert facts.contacts.visible_ally_uuids == ("visible-ally",)
    assert facts.contacts.known_dead_entity_uuids == ("dead-enemy",)
    assert facts.contacts.unknown_contact_uuids == ("unknown-enemy",)
    assert facts.actor.is_concentrating is True
    assert world.known_entities[facts.contacts.unknown_contact_uuids[0]].position is None
    assert facts.objects.closed_door_uuids == ("door",)
    assert facts.topology.hazardous_positions == frozenset({(2, 0)})
    assert facts.topology.blocked_positions == frozenset({(3, 0)})


def test_object_name_alone_does_not_invent_door_state() -> None:
    """Door classification requires an explicit subjective open-state fact."""
    world = _world()
    objects = dict(world.known_objects)
    objects["door"] = objects["door"].model_copy(update={"state": {}})
    world = world.model_copy(update={"known_objects": objects})

    facts = derive_agent_facts(world).facts

    assert facts.objects.closed_door_uuids == tuple()
    assert facts.objects.open_door_uuids == tuple()


def test_affordance_index_shares_immutable_canonical_epoch_rows() -> None:
    """Facts index the one canonical epoch graph without granting mutation."""
    world = _world()
    row = world.current_epoch.affordances.entity_actions[0]  # type: ignore[union-attr]

    index = derive_agent_facts(world).facts.affordances

    assert index.by_id[row.row_id] is row
    assert index.row_ids_by_tag[ActionTag.DAMAGE_SINGLE_TARGET] == (row.row_id,)
    assert index.semantics_by_row_id[row.row_id].semantic_id == "spell.fire_bolt"
    with pytest.raises(ValidationError, match="frozen"):
        index.by_id[row.row_id].can_afford = False
    assert isinstance(index.by_id[row.row_id].targets, tuple)
    with pytest.raises(TypeError):
        index.by_id[row.row_id].cost.resource_costs["test"] = 1
    with pytest.raises(TypeError):
        index.by_id.clear()


def test_known_line_of_sight_preserves_unknown_diagonal_bridge_state() -> None:
    """Known diagonal endpoints do not imply a known traversable vision bridge."""
    world = _world()
    open_directions = {direction: False for direction in ("north", "south", "east", "west")}
    tiles = {
        "0,0": ObservationTileFact(
            key="0,0",
            position=(0, 0),
            knowledge_state=KnowledgeState.VISIBLE,
            directional_blocks_vision=open_directions,
        ),
        "1,1": ObservationTileFact(
            key="1,1",
            position=(1, 1),
            knowledge_state=KnowledgeState.VISIBLE,
            directional_blocks_vision=open_directions,
        ),
    }
    world = world.model_copy(update={"known_tiles": tiles, "known_objects": {}})

    assert known_line_of_sight(world, (0, 0), (1, 1)) is TruthValue.UNKNOWN


def test_known_line_of_sight_uses_subjectively_known_object_blockers() -> None:
    """A visible opaque object blocks a counterfactual line without engine access."""
    world = _world()
    open_directions = {direction: False for direction in ("north", "south", "east", "west")}
    tiles = {
        f"{x},0": ObservationTileFact(
            key=f"{x},0",
            position=(x, 0),
            knowledge_state=KnowledgeState.VISIBLE,
            directional_blocks_vision=open_directions,
        )
        for x in range(3)
    }
    blocker = ObservationObjectFact(
        uuid="opaque-object",
        name="Opaque Boundary",
        knowledge_state=KnowledgeState.VISIBLE,
        position=(1, 0),
        state={"blocks_vision_field": True},
    )
    world = world.model_copy(
        update={"known_tiles": tiles, "known_objects": {blocker.uuid: blocker}}
    )

    assert known_line_of_sight(world, (0, 0), (2, 0)) is TruthValue.FALSE


def test_capability_index_is_distinct_from_executable_affordances() -> None:
    """Potential action families are indexed without manufacturing legal rows."""
    world = _world()

    facts = derive_agent_facts(world).facts
    capability = facts.capabilities.rows[0]

    assert capability.capability_id == "spell.fire_bolt|entity"
    assert facts.capabilities.capability_ids_by_tag[ActionTag.DAMAGE_SINGLE_TARGET] == (
        capability.capability_id,
    )
    assert capability.capability_id not in facts.affordances.by_id
    assert not hasattr(capability, "row_id")


def test_fact_derivation_reuses_only_unchanged_sections() -> None:
    """Cursor-only revisions reuse facts while entity patches invalidate contacts."""
    first_world = _world()
    first = derive_agent_facts(first_world)
    cursor_only_world = first_world.model_copy(update={"observation_cursor": 6})

    cursor_only = derive_agent_facts(
        cursor_only_world,
        previous_world=first_world,
        previous_facts=first.facts,
    )

    assert cursor_only.invalidated_sections == ()
    assert cursor_only.facts.actor is first.facts.actor
    assert cursor_only.facts.contacts is first.facts.contacts
    assert cursor_only.facts.objects is first.facts.objects
    assert cursor_only.facts.topology is first.facts.topology
    assert cursor_only.facts.affordances is first.facts.affordances

    entities = dict(cursor_only_world.known_entities)
    entities["visible-enemy"] = entities["visible-enemy"].model_copy(update={"hp": 3})
    entity_patch_world = cursor_only_world.model_copy(
        update={"observation_cursor": 7, "known_entities": entities}
    )
    entity_patch = derive_agent_facts(
        entity_patch_world,
        previous_world=cursor_only_world,
        previous_facts=cursor_only.facts,
    )

    assert entity_patch.invalidated_sections == ("contacts",)
    assert entity_patch.facts.contacts is not cursor_only.facts.contacts
    assert entity_patch.facts.threat is cursor_only.facts.threat
    visible_uuid = entity_patch.facts.contacts.visible_hostile_uuids[0]
    assert entity_patch_world.known_entities[visible_uuid].hp == 3
    assert entity_patch.facts.actor is cursor_only.facts.actor
    assert entity_patch.facts.objects is cursor_only.facts.objects
    assert entity_patch.facts.topology is cursor_only.facts.topology
    assert entity_patch.facts.affordances is cursor_only.facts.affordances

    moved_entities = dict(entity_patch_world.known_entities)
    moved_entities["visible-enemy"] = moved_entities["visible-enemy"].model_copy(
        update={"position": (1, 0)}
    )
    moved_world = entity_patch_world.model_copy(
        update={"observation_cursor": 8, "known_entities": moved_entities}
    )
    moved_patch = derive_agent_facts(
        moved_world,
        previous_world=entity_patch_world,
        previous_facts=entity_patch.facts,
    )

    assert moved_patch.invalidated_sections == ("contacts", "threat")
    assert moved_patch.facts.threat is not entity_patch.facts.threat
    assert moved_patch.facts.threat.adjacent_hostile_uuids == ("visible-enemy",)


def test_subjective_hook_stores_typed_facts_outside_extension_variables() -> None:
    """The runtime hook owns typed facts as a first-class AgentState field."""
    world = _world()
    registry = HookRegistry([AgentFactsProcessor()])

    state = registry.run(
        HookContext(
            hook=HookPoint.EPOCH_STARTED,
            world=world,
            agent_state=AgentState(),
        )
    )

    assert state.facts is not None
    assert state.facts.actor.actor_uuid == "actor"
    assert state.variables == {}
    assert state.trace[-1].event == "processor.agent_facts"


def test_policy_memory_is_isolated_by_session_actor_and_policy() -> None:
    """One actor's routine state cannot bleed into another actor or policy."""
    store = PolicyMemoryStore()
    first = store.for_actor("session", "skeleton-1", "default")
    second = store.for_actor("session", "skeleton-2", "default")
    alternate = store.for_actor("session", "skeleton-1", "aggressive")

    first.remembered_search_failures["hero"] = 2

    assert store.for_actor("session", "skeleton-1", "default") is first
    assert second.remembered_search_failures == {}
    assert alternate.remembered_search_failures == {}


def test_shared_behavior_tree_traces_guarded_branch_selection() -> None:
    """A hierarchy records failed guards and the selected proposal path."""
    world = _world()
    facts = derive_agent_facts(world).facts
    context = PolicyContext.model_construct(world=world, facts=facts, deadline_monotonic=None)
    context.validate_alignment()
    attack_row = facts.affordances.row_ids_by_tag[ActionTag.DAMAGE_SINGLE_TARGET][0]
    tree = SelectorNode(
        "ReactiveRoot",
        [
            SequenceNode(
                "NoContact",
                [
                    ConditionNode(
                        "HasNoVisibleHostiles",
                        lambda ctx: not ctx.facts.contacts.visible_hostile_uuids,
                    ),
                    ProposalLeaf("Explore", lambda _ctx: tuple()),
                ],
            ),
            SequenceNode(
                "VisibleCombat",
                [
                    ConditionNode(
                        "HasVisibleHostiles",
                        lambda ctx: bool(ctx.facts.contacts.visible_hostile_uuids),
                    ),
                    ProposalLeaf(
                        "Attack",
                        lambda _ctx: (
                            PolicyProposal(
                                intent=ExecuteIntent(row_id=attack_row),
                                source_node="VisibleCombat/Attack",
                                reason="visible hostile and legal damage row",
                                semantic_tags=frozenset({ActionTag.DAMAGE_SINGLE_TARGET}),
                            ),
                        ),
                    ),
                ],
            ),
        ],
    )

    result = tree.tick(context)

    assert result.status is NodeStatus.SUCCESS
    assert result.proposals[0].intent.row_id == attack_row  # type: ignore[union-attr]
    assert [step.node_path for step in result.trace] == [
        "ReactiveRoot/NoContact/HasNoVisibleHostiles",
        "ReactiveRoot/NoContact",
        "ReactiveRoot/VisibleCombat/HasVisibleHostiles",
        "ReactiveRoot/VisibleCombat/Attack",
        "ReactiveRoot/VisibleCombat",
        "ReactiveRoot",
    ]
    assert result.trace[-1].detail == "selected:VisibleCombat"


def test_policy_context_rejects_mixed_world_and_fact_revisions() -> None:
    """Policies cannot silently combine facts and a different world cursor."""
    world = _world()
    facts = derive_agent_facts(world).facts
    mismatched_world = world.model_copy(update={"observation_cursor": world.observation_cursor + 1})
    context = PolicyContext.model_construct(world=mismatched_world, facts=facts, deadline_monotonic=None)

    with pytest.raises(ValueError, match="world cursor"):
        context.validate_alignment()


def test_policy_context_indexes_disclosed_entity_and_row_facts_once() -> None:
    """One decision context owns reusable subjective ordering and row indexes."""
    world = _world()
    context = PolicyHost().build_context(world)
    epoch = world.current_epoch
    assert epoch is not None
    row = epoch.affordances.entity_actions[0]

    assert set(context.evaluation_index.entity_replay_tokens) == set(world.known_entities)
    assert context.evaluation_index.entity_replay_tokens["visible-enemy"].startswith("entity|")
    assert context.evaluation_index.affected_entity_uuids_by_row_id[row.row_id] == frozenset({
        "visible-enemy"
    })
    assert context.evaluation_index.primary_target_uuid_by_row_id[row.row_id] == "visible-enemy"


def test_singleton_entity_ordering_avoids_replay_sort_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty and singleton entity sets need no semantic tie-break evaluation."""
    context = PolicyHost().build_context(_world())

    def fail_replay_lookup(_context: PolicyContext, _entity_uuid: str) -> str:
        raise AssertionError("singleton ordering evaluated a tie-break token")

    monkeypatch.setattr(
        candidate_module,
        "_entity_uuid_replay_token",
        fail_replay_lookup,
    )

    assert candidate_module._sorted_entity_uuids(context, ()) == ()
    assert candidate_module._sorted_entity_uuids(
        context,
        {"visible-enemy"},
    ) == ("visible-enemy",)


def test_policy_host_emits_shared_hierarchy_and_semantic_proposal() -> None:
    """The production policy reports one typed decision through its shared host."""
    world = _world()
    decision = PolicyHost().decide(world)

    assert isinstance(decision.selected.intent, ExecuteIntent)
    assert decision.selected.intent.row_id == "entity|Fire Bolt|uuid=visible-enemy"
    assert ActionTag.DAMAGE_SINGLE_TARGET in decision.selected.semantic_tags
    assert any(
        step.node_path == "ReactiveRoot/TacticalGoalUtility/Pressure/DirectDamage"
        for step in decision.trace
    )
    assert decision.trace[-1].node_path == "ReactiveRoot"
    assert decision.trace[-1].detail == "selected:TacticalGoalUtility"
    assert decision.selected.utility_components
    assert sum(
        component.contribution
        for component in decision.selected.utility_components
    ) == decision.selected.score


def test_utility_arbiter_has_replay_stable_row_id_ties() -> None:
    """Equal utility cannot depend on discovery or dictionary order."""
    later = PolicyProposal(
        intent=ExecuteIntent(row_id="row-z"),
        source_node="test",
        reason="equal score",
        score=10.0,
    )
    earlier = later.model_copy(update={"intent": ExecuteIntent(row_id="row-a")})

    ranked = UtilityArbiter().rank([later, earlier])

    assert [proposal.intent.row_id for proposal in ranked] == ["row-a", "row-z"]  # type: ignore[union-attr]


def test_utility_selector_evaluates_every_branch_before_selecting() -> None:
    """A tactical choice point ranks all proposals instead of using child order."""
    world = _world()
    facts = derive_agent_facts(world).facts
    context = PolicyContext.model_construct(world=world, facts=facts, deadline_monotonic=None)
    lower = PolicyProposal(
        intent=ExecuteIntent(row_id="row-lower"),
        source_node="Pressure/Lower",
        reason="lower utility",
        score=10.0,
    )
    higher = lower.model_copy(
        update={
            "intent": ExecuteIntent(row_id="row-higher"),
            "source_node": "Pressure/Higher",
            "reason": "higher utility",
            "score": 20.0,
        }
    )
    selector = UtilitySelectorNode(
        "TacticalGoalUtility",
        [
            ProposalLeaf("FirstBranch", lambda _context: (lower,)),
            ProposalLeaf("SecondBranch", lambda _context: (higher,)),
        ],
    )

    result = selector.tick(context)

    assert result.status is NodeStatus.SUCCESS
    assert [proposal.intent.row_id for proposal in result.proposals] == [  # type: ignore[union-attr]
        "row-higher",
        "row-lower",
    ]
    assert [step.node_path for step in result.trace[:2]] == [
        "TacticalGoalUtility/FirstBranch",
        "TacticalGoalUtility/SecondBranch",
    ]
    assert result.trace[-1].detail == "selected:Pressure/Higher:20.000"


def test_exact_damage_estimate_preserves_unknown_defenses_and_known_affinities() -> None:
    """Outcome math consumes disclosed rules and only subjective target facts."""
    target = _world().known_entities["visible-enemy"].model_copy(
        update={"hp": 11, "max_hp": 13, "ac": 13}
    )
    missile_profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.AUTOMATIC,
        applications=3,
        damage_rolls=[
            DamageRollProfile(
                dice_count=1,
                die_size=4,
                flat_bonus=1,
                damage_type="force",
            )
        ],
    )
    attack_profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.ATTACK_ROLL,
        attack_bonus=7,
        damage_rolls=[
            DamageRollProfile(
                dice_count=2,
                die_size=10,
                damage_type="fire",
            )
        ],
    )

    missile = estimate_damage_outcome(missile_profile, target)
    fire_bolt = estimate_damage_outcome(attack_profile, target)
    unknown_ac = estimate_damage_outcome(
        attack_profile,
        target.model_copy(update={"ac": None}),
    )
    immune_with_unknown_ac = estimate_damage_outcome(
        attack_profile,
        target.model_copy(update={
            "ac": None,
            "damage_immunities": ["fire"],
        }),
    )
    resisted = estimate_damage_outcome(
        missile_profile,
        target.model_copy(update={"damage_resistances": ["force"]}),
    )

    assert missile is not None
    assert missile.expected_raw_damage == pytest.approx(10.5)
    assert missile.expected_hp_loss == pytest.approx(9.953125)
    assert missile.defeat_probability == pytest.approx(0.5)
    assert missile.nonzero_probability == pytest.approx(1.0)
    assert fire_bolt is not None
    assert fire_bolt.expected_raw_damage == pytest.approx(8.8)
    assert unknown_ac is None
    assert immune_with_unknown_ac is not None
    assert immune_with_unknown_ac.guaranteed_zero is True
    assert immune_with_unknown_ac.model_scope == (
        "actor_baseline+known_target+known_damage_affinity"
    )
    assert resisted is not None
    assert resisted.expected_raw_damage == pytest.approx(4.5)


def test_save_damage_estimate_uses_disclosed_successful_save_lower_bound() -> None:
    """Unknown target saves preserve uncertainty without erasing guaranteed damage."""
    target = _world().known_entities["visible-enemy"].model_copy(
        update={"hp": 20, "max_hp": 20}
    )
    profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.SAVING_THROW,
        damage_rolls=[
            DamageRollProfile(
                dice_count=2,
                die_size=6,
                damage_type="fire",
            )
        ],
        save_dc=15,
        save_ability="dexterity",
        half_damage_on_save=True,
    )

    estimate = estimate_damage_outcome(profile, target)

    assert estimate is not None
    assert estimate.expected_raw_damage == pytest.approx(3.25)
    assert estimate.expected_hp_loss == pytest.approx(3.25)
    assert estimate.model_scope == "actor_baseline+known_target+successful_save_lower_bound"


def test_save_damage_estimate_keeps_zero_on_save_damage_unknown() -> None:
    """A private save bonus cannot be replaced with an invented probability."""
    target = _world().known_entities["visible-enemy"]
    profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.SAVING_THROW,
        damage_rolls=[DamageRollProfile(dice_count=2, die_size=6, damage_type="fire")],
        save_dc=15,
        save_ability="dexterity",
        half_damage_on_save=False,
    )

    assert estimate_damage_outcome(profile, target) is None


def test_outcome_workspace_reuses_one_application_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allocation counts extend one exact distribution instead of rebuilding dice."""
    target = _world().known_entities["visible-enemy"]
    profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.AUTOMATIC,
        applications=5,
        damage_rolls=[
            DamageRollProfile(
                dice_count=1,
                die_size=4,
                flat_bonus=1,
                damage_type="force",
            )
        ],
    )
    distribution_calls = 0
    original_distribution = outcomes_module._damage_distribution

    def count_distributions(
        profiles: Sequence[DamageRollProfile],
        entity: ObservationEntityFact,
        *,
        critical: bool,
        critical_extra_dice: int,
    ) -> dict[int, float]:
        nonlocal distribution_calls
        distribution_calls += 1
        return original_distribution(
            profiles,
            entity,
            critical=critical,
            critical_extra_dice=critical_extra_dice,
        )

    monkeypatch.setattr(outcomes_module, "_damage_distribution", count_distributions)
    workspace = outcomes_module.DamageOutcomeWorkspace()

    estimates = [
        estimate_damage_outcome(
            profile,
            target,
            applications=count,
            workspace=workspace,
        )
        for count in range(1, 6)
    ]
    second_target = target.model_copy(update={"uuid": "same-affinity-target"})
    second_estimate = estimate_damage_outcome(
        profile,
        second_target,
        applications=1,
        workspace=workspace,
    )

    assert all(estimate is not None for estimate in estimates)
    assert second_estimate is not None
    assert distribution_calls == 1


def test_outcome_workspace_shares_convolutions_by_disclosed_defense_state() -> None:
    """UUID and HP do not duplicate distributions with equal defenses."""
    base_target = _world().known_entities["visible-enemy"]
    targets = (
        base_target.model_copy(update={"uuid": "target-6", "hp": 6}),
        base_target.model_copy(update={"uuid": "target-14", "hp": 14}),
        base_target.model_copy(update={"uuid": "target-20", "hp": 20}),
    )
    profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.AUTOMATIC,
        applications=5,
        damage_rolls=(DamageRollProfile(
            dice_count=1,
            die_size=4,
            flat_bonus=1,
            damage_type="force",
        ),),
    )
    workspace = outcomes_module.DamageOutcomeWorkspace()

    estimates = {
        target.uuid: estimate_damage_outcome(
            profile,
            target,
            applications=5,
            workspace=workspace,
        )
        for target in targets
    }

    assert len(workspace._applications) == 1
    assert len(workspace._totals) == 1
    assert all(estimate is not None for estimate in estimates.values())
    assert estimates["target-6"].expected_hp_loss == pytest.approx(6)  # type: ignore[union-attr]
    assert estimates["target-20"].expected_hp_loss > 6  # type: ignore[union-attr]
    assert estimates["target-6"].defeat_probability > estimates["target-20"].defeat_probability  # type: ignore[union-attr]


def test_outcome_workspace_compiles_one_summary_index_per_total_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Equal defenses and application counts share one exact summary index."""
    base_target = _world().known_entities["visible-enemy"]
    targets = (
        base_target.model_copy(update={"uuid": "target-6", "hp": 6}),
        base_target.model_copy(update={"uuid": "target-14", "hp": 14}),
        base_target.model_copy(update={"uuid": "target-20", "hp": 20}),
    )
    profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.AUTOMATIC,
        applications=5,
        damage_rolls=(DamageRollProfile(
            dice_count=1,
            die_size=4,
            flat_bonus=1,
            damage_type="force",
        ),),
    )
    compile_calls = 0
    original_compile = outcomes_module._compile_damage_distribution

    def count_compile_calls(
        distribution: outcomes_module.DamageDistribution,
    ) -> outcomes_module._CompiledDamageDistribution:
        nonlocal compile_calls
        compile_calls += 1
        return original_compile(distribution)

    monkeypatch.setattr(
        outcomes_module,
        "_compile_damage_distribution",
        count_compile_calls,
    )
    workspace = outcomes_module.DamageOutcomeWorkspace()

    estimates = tuple(
        estimate_damage_outcome(
            profile,
            target,
            applications=5,
            workspace=workspace,
        )
        for target in targets
    )

    assert all(estimate is not None for estimate in estimates)
    assert compile_calls == 1


def test_outcome_workspace_projects_one_defense_state_per_profile_and_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated application counts reuse immutable disclosed defense facts."""
    target = _world().known_entities["visible-enemy"].model_copy(
        update={"ac": 13}
    )
    profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.ATTACK_ROLL,
        attack_bonus=6,
        damage_rolls=(DamageRollProfile(
            dice_count=2,
            die_size=6,
            damage_type="fire",
        ),),
    )
    projection_calls = 0
    original_projection = outcomes_module._subjective_defense_state

    def count_projections(
        active_profile: ActionOutcomeProfile,
        active_target: ObservationEntityFact,
    ) -> outcomes_module._SubjectiveDefenseState:
        nonlocal projection_calls
        projection_calls += 1
        return original_projection(active_profile, active_target)

    monkeypatch.setattr(
        outcomes_module,
        "_subjective_defense_state",
        count_projections,
    )
    workspace = outcomes_module.DamageOutcomeWorkspace()

    for applications in range(1, 7):
        assert estimate_damage_outcome(
            profile,
            target,
            applications=applications,
            workspace=workspace,
        ) is not None

    assert projection_calls == 1


def test_slot_scaled_dice_kernels_extend_prior_exact_distributions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Higher dice counts extend a shared exact kernel instead of restarting."""
    outcomes_module._cached_dice_distribution_items.cache_clear()
    outcomes_module._cached_dice_sum_items.cache_clear()
    convolution_calls = 0
    original_convolve = outcomes_module._convolve

    def count_convolutions(
        left: outcomes_module.DamageDistribution,
        right: outcomes_module.DamageDistribution,
    ) -> outcomes_module.DamageDistribution:
        nonlocal convolution_calls
        convolution_calls += 1
        return original_convolve(left, right)

    monkeypatch.setattr(outcomes_module, "_convolve", count_convolutions)

    eight_d6 = outcomes_module._dice_distribution(8, 6, 0)
    ten_d6 = outcomes_module._dice_distribution(10, 6, 0)

    assert sum(eight_d6.values()) == pytest.approx(1.0)
    assert sum(ten_d6.values()) == pytest.approx(1.0)
    assert convolution_calls == 10


def test_control_frontier_compares_only_within_exact_dominance_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unrelated control contracts never enter pairwise dominance checks."""
    seeds = tuple(
        SimpleNamespace(dominance_scope=("scope", index))
        for index in range(24)
    )
    comparison_calls = 0

    def count_comparisons(_candidate: object, _other: object) -> bool:
        nonlocal comparison_calls
        comparison_calls += 1
        return False

    monkeypatch.setattr(
        candidate_module,
        "_control_seed_dominates",
        count_comparisons,
    )

    typed_seeds = cast(
        tuple[candidate_module._ControlCandidateSeed, ...],
        seeds,
    )
    assert candidate_module._prune_dominated_control_seeds(typed_seeds) == seeds
    assert comparison_calls == 0


def test_outcome_workspace_separates_attack_distributions_by_known_defenses() -> None:
    """AC and affinity changes remain distinct application distributions."""
    target = _world().known_entities["visible-enemy"].model_copy(
        update={"uuid": "first", "hp": 10, "ac": 13}
    )
    profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.ATTACK_ROLL,
        attack_bonus=5,
        damage_rolls=(DamageRollProfile(
            dice_count=1,
            die_size=8,
            damage_type="fire",
        ),),
    )
    workspace = outcomes_module.DamageOutcomeWorkspace()

    for candidate in (
        target,
        target.model_copy(update={"uuid": "same-defense", "hp": 20}),
        target.model_copy(update={"uuid": "different-ac", "ac": 14}),
        target.model_copy(update={
            "uuid": "different-affinity",
            "damage_resistances": ["fire"],
        }),
    ):
        assert estimate_damage_outcome(
            profile,
            candidate,
            workspace=workspace,
        ) is not None

    assert len(workspace._applications) == 3
    assert len(workspace._totals) == 3


def test_pure_outcome_caches_are_value_keyed_and_do_not_share_mutable_results() -> None:
    """Equal disclosed values reuse exact math without leaking mutable dictionaries."""
    target = _world().known_entities["visible-enemy"].model_copy(
        update={"ac": 13, "damage_resistances": ["fire"]}
    )
    profiles = (
        DamageRollProfile(dice_count=2, die_size=6, flat_bonus=1, damage_type="fire"),
    )
    outcomes_module._cached_damage_distribution_items.cache_clear()
    outcomes_module._cached_convolution_items.cache_clear()
    outcomes_module._cached_distribution_summary.cache_clear()
    outcomes_module._cached_floor_scaled_distribution_items.cache_clear()
    outcomes_module._attack_outcome_probabilities.cache_clear()

    first = outcomes_module._damage_distribution(
        profiles,
        target,
        critical=False,
        critical_extra_dice=0,
    )
    first[999] = 1.0
    second = outcomes_module._damage_distribution(
        profiles,
        target.model_copy(update={"uuid": "equal-disclosed-values"}),
        critical=False,
        critical_extra_dice=0,
    )
    first_probabilities = outcomes_module._attack_outcome_probabilities(
        attack_bonus=7,
        target_ac=13,
        advantage="advantage",
        critical_threshold=20,
    )
    second_probabilities = outcomes_module._attack_outcome_probabilities(
        attack_bonus=7,
        target_ac=13,
        advantage="advantage",
        critical_threshold=20,
    )
    first_convolution = outcomes_module._convolve(
        {0: 0.5, 1: 0.5},
        {1: 0.5, 2: 0.5},
    )
    first_convolution[999] = 1.0
    second_convolution = outcomes_module._convolve(
        {0: 0.5, 1: 0.5},
        {1: 0.5, 2: 0.5},
    )
    first_scaled = outcomes_module._floor_scaled_distribution(
        {1: 0.5, 2: 0.5},
        0.5,
    )
    first_scaled[999] = 1.0
    second_scaled = outcomes_module._floor_scaled_distribution(
        {1: 0.5, 2: 0.5},
        0.5,
    )
    automatic_profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.AUTOMATIC,
        damage_rolls=profiles,
    )
    first_estimate = estimate_damage_outcome(automatic_profile, target)
    second_estimate = estimate_damage_outcome(
        automatic_profile,
        target.model_copy(update={"uuid": "same-summary-values"}),
    )

    assert 999 not in second
    assert 999 not in second_convolution
    assert 999 not in second_scaled
    assert first_probabilities == second_probabilities
    assert first_estimate == second_estimate
    assert outcomes_module._cached_damage_distribution_items.cache_info().hits >= 1
    assert outcomes_module._cached_convolution_items.cache_info().hits >= 1
    assert (
        outcomes_module._cached_floor_scaled_distribution_items.cache_info().hits
        == 1
    )
    assert outcomes_module._cached_distribution_summary.cache_info().hits == 1
    assert outcomes_module._attack_outcome_probabilities.cache_info().hits == 1


def test_shared_outcome_cache_uses_only_disclosed_target_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Separate decision workspaces reuse immutable subjective outcome math."""
    target = _world().known_entities["visible-enemy"].model_copy(update={
        "hp": 17,
        "ac": 13,
        "damage_resistances": ["fire"],
    })
    profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.ATTACK_ROLL,
        damage_rolls=[DamageRollProfile(
            dice_count=2,
            die_size=6,
            damage_type="fire",
        )],
        attack_bonus=6,
    )
    outcomes_module._SHARED_DAMAGE_ESTIMATES.clear()
    application_calls = 0
    original_application_distribution = outcomes_module._application_distribution

    def count_application_distributions(
        active_profile: ActionOutcomeProfile,
        entity: ObservationEntityFact,
        workspace: outcomes_module.DamageOutcomeWorkspace,
        defense_state: outcomes_module._SubjectiveDefenseState,
    ) -> tuple[
        outcomes_module.DamageDistribution,
        str,
        tuple[outcomes_module.SubjectiveEffectBlocker, ...],
    ] | None:
        nonlocal application_calls
        application_calls += 1
        return original_application_distribution(
            active_profile,
            entity,
            workspace,
            defense_state,
        )

    monkeypatch.setattr(
        outcomes_module,
        "_application_distribution",
        count_application_distributions,
    )
    first = estimate_damage_outcome(
        profile,
        target,
        workspace=outcomes_module.DamageOutcomeWorkspace(shared_value_cache=True),
    )
    second = estimate_damage_outcome(
        profile,
        target.model_copy(update={"uuid": "same-disclosed-target"}),
        workspace=outcomes_module.DamageOutcomeWorkspace(shared_value_cache=True),
    )

    assert first == second
    assert application_calls == 1


def test_damage_outcome_reports_typed_guaranteed_zero_blocker_evidence() -> None:
    """A visible matching protection nullifies damage without display-name rules."""
    effect_id = "rules.damage.opaque_automatic_darts"
    protection_id = "rules.protection.opaque_dart_barrier"
    target = _world().known_entities["visible-enemy"].model_copy(update={
        "effect_protections": [ObservationEffectProtection(
            protection_id=protection_id,
            blocked_effect_ids=[effect_id],
        )],
    })
    profile = ActionOutcomeProfile(
        effect_id=effect_id,
        resolution=OutcomeResolution.AUTOMATIC,
        applications=3,
        damage_rolls=[DamageRollProfile(
            dice_count=1,
            die_size=4,
            flat_bonus=1,
            damage_type="force",
        )],
    )

    estimate = estimate_damage_outcome(profile, target)

    assert estimate is not None
    assert estimate.guaranteed_zero is True
    assert estimate.expected_raw_damage == 0.0
    assert estimate.expected_hp_loss == 0.0
    assert estimate.nonzero_probability == 0.0
    assert len(estimate.blocker_evidence) == 1
    assert estimate.blocker_evidence[0].protection_id == protection_id
    assert estimate.blocker_evidence[0].effect_id == effect_id


def test_observed_block_hypothesis_mixes_once_over_multi_application_damage() -> None:
    """One blocker episode changes action-level risk without claiming certainty."""
    effect_id = "rules.damage.opaque_automatic_darts"
    target = _world().known_entities["visible-enemy"]
    profile = ActionOutcomeProfile(
        effect_id=effect_id,
        resolution=OutcomeResolution.AUTOMATIC,
        applications=6,
        damage_rolls=[DamageRollProfile(
            dice_count=1,
            die_size=4,
            flat_bonus=1,
            damage_type="force",
        )],
    )
    hypothesis = TargetEffectBlockHypothesis(
        target_uuid=target.uuid,
        effect_id=effect_id,
        blocked_episodes=1,
        total_episodes=1,
        blocked_applications=6,
        total_applications=6,
        episode_log_indices=(4,),
        latest_log_index=4,
        block_probability=2 / 3,
    )

    ordinary = estimate_damage_outcome(profile, target)
    adjusted = estimate_damage_outcome(
        profile,
        target,
        effect_block_hypothesis=hypothesis,
    )

    assert ordinary is not None
    assert adjusted is not None
    assert adjusted.expected_raw_damage == pytest.approx(ordinary.expected_raw_damage / 3)
    assert adjusted.expected_hp_loss == pytest.approx(ordinary.expected_hp_loss / 3)
    assert adjusted.nonzero_probability == pytest.approx(ordinary.nonzero_probability / 3)
    assert adjusted.guaranteed_zero is False
    assert adjusted.effect_block_hypothesis is not None
    assert adjusted.effect_block_hypothesis.effect_id == effect_id
    assert adjusted.effect_block_hypothesis.block_probability == 2 / 3


def test_observed_block_hypothesis_is_effect_specific_and_live_protection_wins() -> None:
    """Historical risk neither generalizes to other effects nor weakens live facts."""
    blocked_effect_id = "rules.damage.opaque_automatic_darts"
    target = _world().known_entities["visible-enemy"]
    hypothesis = TargetEffectBlockHypothesis(
        target_uuid=target.uuid,
        effect_id=blocked_effect_id,
        blocked_episodes=1,
        total_episodes=1,
        blocked_applications=3,
        total_applications=3,
        episode_log_indices=(4,),
        latest_log_index=4,
        block_probability=2 / 3,
    )
    unrelated = ActionOutcomeProfile(
        effect_id="rules.damage.other_effect",
        resolution=OutcomeResolution.AUTOMATIC,
        damage_rolls=[DamageRollProfile(dice_count=2, die_size=6, damage_type="fire")],
    )
    blocked_profile = unrelated.model_copy(update={"effect_id": blocked_effect_id})
    protected = target.model_copy(update={
        "effect_protections": [ObservationEffectProtection(
            protection_id="rules.protection.current_barrier",
            blocked_effect_ids=[blocked_effect_id],
        )],
    })

    ordinary_unrelated = estimate_damage_outcome(unrelated, target)
    unrelated_with_hypothesis = estimate_damage_outcome(
        unrelated,
        target,
        effect_block_hypothesis=hypothesis,
    )
    live_blocked = estimate_damage_outcome(
        blocked_profile,
        protected,
        effect_block_hypothesis=hypothesis,
    )

    assert unrelated_with_hypothesis == ordinary_unrelated
    assert live_blocked is not None
    assert live_blocked.guaranteed_zero is True
    assert live_blocked.effect_block_hypothesis is None
    assert len(live_blocked.blocker_evidence) == 1


def test_nullified_pure_damage_is_removed_from_candidate_and_effective_coverage() -> None:
    """Pure damage excludes fully protected candidates and protected recipients."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    effect_id = "rules.damage.opaque_automatic_darts"
    protected = world.known_entities["visible-enemy"].model_copy(update={
        "effect_protections": [ObservationEffectProtection(
            protection_id="rules.protection.opaque_dart_barrier",
            blocked_effect_ids=[effect_id],
        )],
    })
    exposed = protected.model_copy(update={
        "uuid": "second-visible-enemy",
        "name": "Second opaque contact",
        "position": (3, 0),
        "effect_protections": [],
    })
    damage_effect = StochasticEffect(
        outcome_kind=OutcomeKind.GUARANTEED,
        effects=(LogicalEffect(
            fact_id="selected_target.hp",
            operation=EffectOperation.DECREASE,
            value_ref="resolved_damage",
        ),),
    )
    single_semantics = ActionSemantics(
        semantic_id="damage.opaque.single",
        tags=frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_SINGLE_TARGET}),
        stochastic_effects=(damage_effect,),
    )
    area_semantics = ActionSemantics(
        semantic_id="damage.opaque.area",
        tags=frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_AREA}),
        stochastic_effects=(damage_effect,),
    )
    single_ref = action_semantics_ref(single_semantics)
    area_ref = action_semantics_ref(area_semantics)
    damage_rolls = [DamageRollProfile(
        dice_count=1,
        die_size=4,
        flat_bonus=1,
        damage_type="force",
    )]
    blocked_single = ActionAffordance(
        row_id="entity|opaque-darts|uuid=visible-enemy",
        bucket="entity_actions",
        template_name="Opaque Darts",
        semantic_key="rules.actions.opaque_automatic_darts",
        display_name="Localized harmless-looking label",
        action_category="spell",
        target_type="entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=[ActionTarget(index=0, target_uuid=protected.uuid, position=protected.position)],
        damage_types=["force"],
        outcome_profile=ActionOutcomeProfile(
            effect_id=effect_id,
            resolution=OutcomeResolution.AUTOMATIC,
            damage_rolls=damage_rolls,
        ),
        semantic_id=single_semantics.semantic_id,
        semantics_ref=single_ref,
    )
    mixed_area = ActionAffordance(
        row_id="position|opaque-darts|pos=2,0",
        bucket="position_actions",
        template_name="Opaque Burst",
        semantic_key="rules.actions.opaque_automatic_burst",
        display_name="Localized burst label",
        action_category="spell",
        target_type="position_aoe",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=[ActionTarget(
            index=0,
            position=(2, 0),
            affected_entity_uuids=[protected.uuid, exposed.uuid],
        )],
        damage_types=["force"],
        outcome_profile=ActionOutcomeProfile(
            effect_id=effect_id,
            resolution=OutcomeResolution.AUTOMATIC,
            application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
            damage_rolls=damage_rolls,
        ),
        semantic_id=area_semantics.semantic_id,
        semantics_ref=area_ref,
    )
    entities = dict(world.known_entities)
    entities[protected.uuid] = protected
    entities[exposed.uuid] = exposed
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        entity_actions=[blocked_single],
        position_actions=[mixed_area],
        semantic_catalog={single_ref: single_semantics, area_ref: area_semantics},
    )
    world = world.model_copy(update={
        "known_entities": entities,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    proposals = direct_damage_candidates(context)

    assert [proposal.intent.row_id for proposal in proposals] == [mixed_area.row_id]  # type: ignore[union-attr]
    proposal = proposals[0]
    target_plan = proposal.evidence.target_plan
    assert target_plan is not None
    assert target_plan.affected_entity_uuids == (protected.uuid, exposed.uuid)
    assert target_plan.hostile_entity_uuids == (exposed.uuid,)
    outcome_by_entity = {
        outcome.entity_uuid: outcome
        for outcome in proposal.evidence.damage_outcomes
    }
    assert outcome_by_entity[protected.uuid].guaranteed_zero is True
    assert outcome_by_entity[exposed.uuid].guaranteed_zero is False
    coverage = next(
        component
        for component in proposal.utility_components
        if component.name == "visible_hostile_coverage"
    )
    assert coverage.raw_value == 1.0


def test_shared_damage_utility_values_reliable_burst_without_name_rules() -> None:
    """Typed outcome semantics can justify spending a slot over a free attack."""
    world = _world()
    target = world.known_entities["visible-enemy"].model_copy(
        update={"hp": 11, "max_hp": 13, "ac": 13}
    )
    entities = dict(world.known_entities)
    entities[target.uuid] = target
    fire_semantics = ActionSemantics(
        semantic_id="damage.spell.attack",
        tags=frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_SINGLE_TARGET}),
    )
    missile_semantics = ActionSemantics(
        semantic_id="damage.spell.automatic_multi",
        tags=frozenset(
            {
                ActionTag.DAMAGE_MULTI_TARGET,
                ActionTag.TARGET_MULTI,
                ActionTag.TARGET_REPEAT,
            }
        ),
    )
    fire_ref = action_semantics_ref(fire_semantics)
    missile_ref = action_semantics_ref(missile_semantics)
    fire_row = ActionAffordance(
        row_id="entity|ranged-spell-attack|uuid=visible-enemy",
        bucket="entity_actions",
        template_name="ranged-spell-attack",
        semantic_key="rules.damage.spell_attack",
        display_name="Ranged spell attack",
        action_category="spell",
        target_type="entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=[ActionTarget(index=0, target_uuid=target.uuid, position=target.position)],
        outcome_profile=ActionOutcomeProfile(
            effect_id="rules.damage.ranged_spell_attack",
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=7,
            damage_rolls=[
                DamageRollProfile(
                    dice_count=2,
                    die_size=10,
                    damage_type="fire",
                )
            ],
        ),
        semantic_id=fire_semantics.semantic_id,
        semantics_ref=fire_ref,
    )
    missile_row = ActionAffordance(
        row_id="entity|automatic-darts|uuid=visible-enemy",
        bucket="entity_actions",
        template_name="automatic-darts",
        semantic_key="rules.damage.automatic_darts",
        display_name="Automatic darts",
        action_category="spell",
        target_type="multi_entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1, spell_slot_cost=1),
        targets=[ActionTarget(index=0, target_uuid=target.uuid, position=target.position)],
        target_options=[ActionTarget(index=0, target_uuid=target.uuid, position=target.position)],
        num_projectiles=3,
        allow_same_target=True,
        outcome_profile=ActionOutcomeProfile(
            effect_id="rules.damage.automatic_darts",
            resolution=OutcomeResolution.AUTOMATIC,
            applications=3,
            damage_rolls=[
                DamageRollProfile(
                    dice_count=1,
                    die_size=4,
                    flat_bonus=1,
                    damage_type="force",
                )
            ],
        ),
        semantic_id=missile_semantics.semantic_id,
        semantics_ref=missile_ref,
    )
    epoch = world.current_epoch
    assert epoch is not None
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        entity_actions=[fire_row, missile_row],
        semantic_catalog={
            fire_ref: fire_semantics,
            missile_ref: missile_semantics,
        },
    )
    world = world.model_copy(
        update={
            "known_entities": entities,
            "current_epoch": epoch.model_copy(update={"affordances": affordances}),
        }
    )
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    ranked = UtilityArbiter().rank(direct_damage_candidates(context))

    assert [proposal.intent.row_id for proposal in ranked] == [  # type: ignore[union-attr]
        missile_row.row_id,
        fire_row.row_id,
    ]
    components = {
        component.name: component
        for component in ranked[0].utility_components
    }
    assert components["subjective_expected_hp_loss"].raw_value == pytest.approx(9.953125)
    assert components["subjective_expected_defeats"].raw_value == pytest.approx(0.5)
    assert components["subjective_damage_reliability"].raw_value == pytest.approx(1.0)
    assert components["limited_resource_cost"].raw_value == pytest.approx(1.0)
    target_plan = ranked[0].evidence.target_plan
    assert target_plan is not None
    assert target_plan.applications[0].entity_uuid == target.uuid
    assert target_plan.applications[0].applications == 3
    assert ranked[0].evidence.damage_outcomes[0].expected_hp_loss == pytest.approx(9.953125)

    other_controlled_actor = "other-controlled-actor"
    blocked_applications = [
        {
            "entry_type": "damage_taken",
            "source_uuid": other_controlled_actor,
            "target_uuid": target.uuid,
            "data": {
                "damage": 0,
                "damage_type": "force",
                "blocked": True,
                "effect_id": "rules.damage.automatic_darts",
            },
            "sub_entries": [],
        }
        for _ in range(3)
    ]
    blocked_log = {
        "entry_type": "multi_entity_action",
        "source_uuid": other_controlled_actor,
        "target_uuid": None,
        "data": {},
        "sub_entries": blocked_applications,
    }
    shared_session = world.session.model_copy(update={
        "controlled_entity_uuids": [epoch.actor_uuid, other_controlled_actor],
    })
    observed_world = world.model_copy(update={
        "session": shared_session,
        "combat_logs": [blocked_log],
    })
    observed_context = PolicyContext.model_construct(
        world=observed_world,
        facts=derive_agent_facts(observed_world).facts,
        deadline_monotonic=None,
    )

    observed_ranked = UtilityArbiter().rank(direct_damage_candidates(observed_context))

    assert [proposal.intent.row_id for proposal in observed_ranked] == [  # type: ignore[union-attr]
        fire_row.row_id,
        missile_row.row_id,
    ]
    observed_missile = observed_ranked[1].evidence.damage_outcomes[0]
    assert observed_missile.expected_raw_damage == pytest.approx(3.5)
    assert observed_missile.guaranteed_zero is False
    assert observed_missile.effect_block_hypothesis is not None
    assert observed_missile.effect_block_hypothesis.block_probability == 2 / 3

    isolated_world = observed_world.model_copy(update={"session": world.session})
    isolated_context = PolicyContext.model_construct(
        world=isolated_world,
        facts=derive_agent_facts(isolated_world).facts,
        deadline_monotonic=None,
    )
    isolated_ranked = UtilityArbiter().rank(direct_damage_candidates(isolated_context))
    assert isolated_ranked[0].intent.row_id == missile_row.row_id  # type: ignore[union-attr]


def test_repeatable_damage_allocator_avoids_expected_overkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeatable projectiles balance a likely defeat against expected overkill."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    low = world.known_entities["visible-enemy"].model_copy(update={"hp": 10, "max_hp": 10})
    high = low.model_copy(
        update={
            "uuid": "second-visible-enemy",
            "name": "Second contact",
            "position": (3, 0),
            "hp": 40,
            "max_hp": 40,
        }
    )
    semantics = ActionSemantics(
        semantic_id="damage.opaque.repeatable",
        tags=frozenset({
            ActionTag.DAMAGE_MULTI_TARGET,
            ActionTag.TARGET_MULTI,
            ActionTag.TARGET_REPEAT,
        }),
    )
    reference = action_semantics_ref(semantics)
    row = ActionAffordance(
        row_id="entity|opaque-repeatable|uuid=visible-enemy",
        source_action_id="entity_actions|source=0",
        bucket="entity_actions",
        template_name="opaque-repeatable",
        semantic_key="rules.damage.repeatable",
        display_name="Unclassified effect",
        action_category="spell",
        target_type="multi_entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1, spell_slot_cost=3),
        targets=[ActionTarget(index=0, target_uuid=low.uuid, position=low.position)],
        target_options=[
            ActionTarget(index=0, target_uuid=low.uuid, position=low.position),
            ActionTarget(index=1, target_uuid=high.uuid, position=high.position),
        ],
        num_projectiles=5,
        allow_same_target=True,
        outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.AUTOMATIC,
            applications=5,
            application_scope=OutcomeApplicationScope.ALLOCATED_TARGETS,
            damage_rolls=[DamageRollProfile(dice_count=1, die_size=4, flat_bonus=1, damage_type="force")],
        ),
        semantic_id=semantics.semantic_id,
        semantics_ref=reference,
    )
    second_row = row.model_copy(update={
        "row_id": "entity|opaque-repeatable|uuid=second-visible-enemy",
        "targets": [ActionTarget(index=1, target_uuid=high.uuid, position=high.position)],
    })
    entities = dict(world.known_entities)
    entities[low.uuid] = low
    entities[high.uuid] = high
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        entity_actions=[row, second_row],
        semantic_catalog={reference: semantics},
    )
    world = world.model_copy(update={
        "known_entities": entities,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    estimate_calls = 0
    original_estimate = candidate_module.estimate_damage_outcome

    def count_estimate_calls(
        profile: ActionOutcomeProfile,
        target: ObservationEntityFact,
        *,
        applications: int | None = None,
        workspace: outcomes_module.DamageOutcomeWorkspace | None = None,
        effect_block_hypothesis: TargetEffectBlockHypothesis | None = None,
    ) -> SubjectiveDamageEstimate | None:
        nonlocal estimate_calls
        estimate_calls += 1
        return original_estimate(
            profile,
            target,
            applications=applications,
            workspace=workspace,
            effect_block_hypothesis=effect_block_hypothesis,
        )

    monkeypatch.setattr(candidate_module, "estimate_damage_outcome", count_estimate_calls)

    proposals = direct_damage_candidates(context)
    assert len(proposals) == 1
    proposal = next(
        candidate
        for candidate in proposals
        if isinstance(candidate.intent, ExecuteIntent)
        and candidate.intent.row_id == row.row_id
    )
    target_plan = proposal.evidence.target_plan

    assert target_plan is not None
    counts = {entry.entity_uuid: entry.applications for entry in target_plan.applications}
    assert sum(counts.values()) == 5
    assert counts[low.uuid] < 5
    assert counts[high.uuid] >= 1
    assert proposal.intent.extra_target_uuids.count(high.uuid) >= 1  # type: ignore[union-attr]
    assert estimate_calls == 10

    controlled_low = _with_damage_ending_control(
        low.model_copy(update={"hp": 40, "max_hp": 40}),
        applied_source_event_cursor=10,
    )
    controlled_world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            controlled_low.uuid: controlled_low,
        },
    })
    controlled_context = PolicyContext.model_construct(
        world=controlled_world,
        facts=derive_agent_facts(controlled_world).facts,
        deadline_monotonic=None,
    )

    controlled_proposal = direct_damage_candidates(controlled_context)[0]
    controlled_plan = controlled_proposal.evidence.target_plan

    assert controlled_plan is not None
    controlled_counts = {
        entry.entity_uuid: entry.applications
        for entry in controlled_plan.applications
    }
    assert controlled_counts == {high.uuid: 5}
    assert controlled_proposal.intent == ExecuteIntent(
        row_id=second_row.row_id,
        extra_target_uuids=(high.uuid, high.uuid, high.uuid, high.uuid),
    )


def test_shared_policy_preserves_new_damage_ending_control_for_one_turn() -> None:
    """Fresh hard control can yield the turn without becoming a permanent taboo."""
    world, _control_row, damage_row = _control_choice_world(
        concentrating=True,
        damage_outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.AUTOMATIC,
            damage_rolls=[DamageRollProfile(
                dice_count=1,
                die_size=4,
                flat_bonus=1,
                damage_type="force",
            )],
        ),
    )
    epoch = world.current_epoch
    assert epoch is not None
    enemy = _with_damage_ending_control(
        world.known_entities["visible-enemy"],
        applied_source_event_cursor=10,
    )
    world = world.model_copy(update={
        "encounter": _policy_encounter(turn_started_source_event_cursor=5),
        "known_entities": {**world.known_entities, enemy.uuid: enemy},
        "current_epoch": epoch.model_copy(update={
            "affordances": epoch.affordances.model_copy(update={
                "entity_actions": [damage_row],
            }),
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == EndTurnIntent()
    assert evaluation.decision.selected.goal is PolicyGoal.CONTROL_PRESERVATION
    preservation_components = {
        component.name: component
        for component in evaluation.decision.selected.utility_components
    }
    assert preservation_components[
        "newly_established_enemy_agency_denial"
    ].weight == 20.0
    damage = next(
        proposal
        for proposal in evaluation.decision.candidates
        if proposal.intent == ExecuteIntent(row_id=damage_row.row_id)
    )
    components = {component.name: component for component in damage.utility_components}
    assert components["expected_enemy_agency_restored"].raw_value > 0
    assert components["expected_enemy_agency_restored"].weight == -55.0

    later_world = world.model_copy(update={
        "encounter": _policy_encounter(turn_started_source_event_cursor=11),
    })
    later_context = PolicyContext.model_construct(
        world=later_world,
        facts=derive_agent_facts(later_world).facts,
        deadline_monotonic=None,
    )
    later = evaluate_default_policy(later_context, tuple())

    assert later.decision is not None
    assert later.decision.selected.intent == ExecuteIntent(row_id=damage_row.row_id)


@pytest.mark.parametrize("known_hp", [1, 20])
def test_control_break_cost_is_zero_for_lethal_or_guaranteed_zero_damage(
    known_hp: int,
) -> None:
    """Damage restores no future agency when it defeats or cannot hurt the target."""
    effect_id = "rules.damage.control-break-test"
    world, _control_row, damage_row = _control_choice_world(
        concentrating=True,
        enemy_hp=known_hp,
        enemy_max_hp=20,
        damage_outcome_profile=ActionOutcomeProfile(
            effect_id=effect_id,
            resolution=OutcomeResolution.AUTOMATIC,
            damage_rolls=[DamageRollProfile(
                dice_count=1,
                die_size=4,
                flat_bonus=4,
                damage_type="force",
            )],
        ),
    )
    epoch = world.current_epoch
    assert epoch is not None
    enemy = _with_damage_ending_control(
        world.known_entities["visible-enemy"],
        applied_source_event_cursor=10,
    )
    if known_hp == 20:
        enemy = enemy.model_copy(update={
            "effect_protections": [ObservationEffectProtection(
                protection_id="opaque-total-block",
                blocked_effect_ids=[effect_id],
            )],
        })
    world = world.model_copy(update={
        "encounter": _policy_encounter(turn_started_source_event_cursor=5),
        "known_entities": {**world.known_entities, enemy.uuid: enemy},
        "current_epoch": epoch.model_copy(update={
            "affordances": epoch.affordances.model_copy(update={
                "entity_actions": [damage_row],
            }),
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    if known_hp == 1:
        assert evaluation.decision.selected.intent == ExecuteIntent(row_id=damage_row.row_id)
    else:
        assert evaluation.decision.selected.intent == EndTurnIntent()
        assert evaluation.decision.selected.goal is PolicyGoal.END_TURN
    damage_proposals = direct_damage_candidates(context)
    if not damage_proposals:
        assert known_hp == 20
        return
    components = {
        component.name: component
        for component in damage_proposals[0].utility_components
    }
    assert components["expected_enemy_agency_restored"].raw_value == 0.0


def test_outcome_workspace_shares_one_application_model_across_slot_scaling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projectile count variants reuse the exact same per-projectile model."""
    target = _world().known_entities["visible-enemy"].model_copy(update={"ac": 13})
    lower = ActionOutcomeProfile(
        resolution=OutcomeResolution.ATTACK_ROLL,
        applications=3,
        application_scope=OutcomeApplicationScope.ALLOCATED_TARGETS,
        damage_rolls=[DamageRollProfile(dice_count=2, die_size=6, damage_type="fire")],
        attack_bonus=6,
    )
    higher = lower.model_copy(update={"applications": 4})
    workspace = outcomes_module.DamageOutcomeWorkspace()
    application_calls = 0
    original_application_distribution = outcomes_module._application_distribution

    def count_application_distributions(
        profile: ActionOutcomeProfile,
        entity: ObservationEntityFact,
        active_workspace: outcomes_module.DamageOutcomeWorkspace,
        defense_state: outcomes_module._SubjectiveDefenseState,
    ) -> tuple[
        outcomes_module.DamageDistribution,
        str,
        tuple[outcomes_module.SubjectiveEffectBlocker, ...],
    ] | None:
        nonlocal application_calls
        application_calls += 1
        return original_application_distribution(
            profile,
            entity,
            active_workspace,
            defense_state,
        )

    monkeypatch.setattr(
        outcomes_module,
        "_application_distribution",
        count_application_distributions,
    )

    lower_estimate = estimate_damage_outcome(
        lower,
        target,
        applications=3,
        workspace=workspace,
    )
    higher_estimate = estimate_damage_outcome(
        higher,
        target,
        applications=4,
        workspace=workspace,
    )

    assert lower_estimate is not None
    assert higher_estimate is not None
    assert application_calls == 1


def test_equal_multi_target_choices_are_invariant_to_opaque_uuid_labels() -> None:
    """Target allocation and arbitration use subjective semantics, not UUID order."""

    def context_for(uuids_by_position: dict[tuple[int, int], str]) -> PolicyContext:
        world = _world()
        epoch = world.current_epoch
        assert epoch is not None
        base = world.known_entities["visible-enemy"]
        entities = {
            entity_uuid: entity
            for entity_uuid, entity in world.known_entities.items()
            if entity_uuid != base.uuid
        }
        targets = []
        for position, entity_uuid in sorted(uuids_by_position.items()):
            target = base.model_copy(
                update={
                    "uuid": entity_uuid,
                    "name": f"Contact at {position[0]},{position[1]}",
                    "position": position,
                    "hp": 20,
                    "max_hp": 20,
                }
            )
            entities[entity_uuid] = target
            targets.append(target)
        semantics = ActionSemantics(
            semantic_id="damage.replay.repeatable",
            tags=frozenset({
                ActionTag.DAMAGE_MULTI_TARGET,
                ActionTag.TARGET_MULTI,
                ActionTag.TARGET_REPEAT,
            }),
        )
        reference = action_semantics_ref(semantics)
        options = [
            ActionTarget(index=index, target_uuid=target.uuid, position=target.position)
            for index, target in enumerate(targets)
        ]
        rows = [
            ActionAffordance(
                row_id=f"entity|replay-repeatable|uuid={target.uuid}",
                source_action_id="entity_actions|source=0",
                bucket="entity_actions",
                template_name="replay-repeatable",
                semantic_key="rules.damage.replay_repeatable",
                display_name="Replay repeatable",
                action_category="spell",
                target_type="multi_entity",
                can_afford=True,
                cost=ActionCostProfile(action_cost=1, spell_slot_cost=1),
                targets=[options[index]],
                target_options=options,
                num_projectiles=3,
                allow_same_target=True,
                outcome_profile=ActionOutcomeProfile(
                    resolution=OutcomeResolution.AUTOMATIC,
                    applications=3,
                    application_scope=OutcomeApplicationScope.ALLOCATED_TARGETS,
                    damage_rolls=[
                        DamageRollProfile(
                            dice_count=1,
                            die_size=4,
                            flat_bonus=1,
                            damage_type="force",
                        )
                    ],
                ),
                semantic_id=semantics.semantic_id,
                semantics_ref=reference,
            )
            for index, target in enumerate(targets)
        ]
        affordances = AffordanceSet(
            actor_uuid=epoch.actor_uuid,
            computed_at_observation_cursor=epoch.basis_observation_cursor,
            entity_actions=rows,
            semantic_catalog={reference: semantics},
        )
        world = world.model_copy(
            update={
                "known_entities": entities,
                "current_epoch": epoch.model_copy(update={"affordances": affordances}),
            }
        )
        return PolicyContext.model_construct(
            world=world,
            facts=derive_agent_facts(world).facts,
            deadline_monotonic=None,
        )

    def normalized_selection(context: PolicyContext) -> tuple[object, ...]:
        proposal = UtilityArbiter().select(direct_damage_candidates(context))
        assert proposal is not None
        assert isinstance(proposal.intent, ExecuteIntent)
        target_plan = proposal.evidence.target_plan
        assert target_plan is not None
        assert {application.applications for application in target_plan.applications} == {1}
        entities = context.world.known_entities
        primary_position = entities[target_plan.primary_target_uuid].position  # type: ignore[index]
        selected_positions = tuple(
            entities[entity_uuid].position
            for entity_uuid in target_plan.selected_target_uuids
        )
        application_positions = tuple(sorted(
            (entities[application.entity_uuid].position, application.applications)
            for application in target_plan.applications
        ))
        return (
            proposal.reason,
            proposal.replay_key,
            primary_position,
            selected_positions,
            application_positions,
        )

    first = context_for({
        (2, 0): "target-a",
        (3, 0): "target-b",
        (4, 0): "target-c",
    })
    relabeled = context_for({
        (2, 0): "target-c",
        (3, 0): "target-a",
        (4, 0): "target-b",
    })

    assert normalized_selection(first) == normalized_selection(relabeled)


def test_area_damage_evidence_applies_once_per_disclosed_hostile() -> None:
    """Area outcome evidence follows explicit scope without a primary UUID."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    base_enemy = world.known_entities["visible-enemy"]
    entities = dict(world.known_entities)
    hostile_uuids = [base_enemy.uuid]
    for index in range(1, 4):
        clone = base_enemy.model_copy(update={
            "uuid": f"area-enemy-{index}",
            "name": f"Area contact {index}",
            "position": (2 + index, 1),
        })
        entities[clone.uuid] = clone
        hostile_uuids.append(clone.uuid)
    semantics = ActionSemantics(
        semantic_id="damage.opaque.area",
        tags=frozenset({ActionTag.DAMAGE_AREA}),
    )
    reference = action_semantics_ref(semantics)
    row = ActionAffordance(
        row_id="position|opaque-area|pos=3,1",
        bucket="position_actions",
        template_name="opaque-area",
        semantic_key="rules.damage.area",
        display_name="Unclassified area",
        action_category="spell",
        target_type="position_aoe",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1, spell_slot_cost=3),
        targets=[ActionTarget(index=0, position=(3, 1), affected_entity_uuids=hostile_uuids)],
        outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.SAVING_THROW,
            application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
            damage_rolls=[DamageRollProfile(dice_count=2, die_size=6, damage_type="fire")],
            half_damage_on_save=True,
        ),
        semantic_id=semantics.semantic_id,
        semantics_ref=reference,
    )
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        position_actions=[row],
        semantic_catalog={reference: semantics},
    )
    world = world.model_copy(update={
        "known_entities": entities,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    proposal = direct_damage_candidates(context)[0]
    target_plan = proposal.evidence.target_plan

    assert target_plan is not None
    assert {entry.entity_uuid: entry.applications for entry in target_plan.applications} == {
        entity_uuid: 1 for entity_uuid in hostile_uuids
    }
    assert {outcome.entity_uuid for outcome in proposal.evidence.damage_outcomes} == set(hostile_uuids)


def test_area_damage_candidates_remove_typed_effect_dominated_rows() -> None:
    """A same-cost area superset dominates subsets and controlled friendly fire."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    first = world.known_entities["visible-enemy"]
    second = first.model_copy(update={
        "uuid": "second-visible-enemy",
        "name": "Second opaque contact",
        "position": (3, 0),
        "hp": 12,
        "max_hp": 12,
    })
    semantics = ActionSemantics(
        semantic_id="damage.opaque.area.frontier",
        tags=frozenset({ActionTag.DAMAGE_AREA}),
    )
    reference = action_semantics_ref(semantics)
    profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.SAVING_THROW,
        application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
        damage_rolls=[DamageRollProfile(dice_count=2, die_size=6, damage_type="force")],
        half_damage_on_save=True,
    )

    def row(
        suffix: str,
        position: tuple[int, int],
        affected: list[str],
    ) -> ActionAffordance:
        return ActionAffordance(
            row_id=f"position|opaque-frontier|{suffix}",
            bucket="position_actions",
            template_name="opaque-frontier",
            semantic_key="rules.damage.area.frontier",
            display_name="Opaque frontier",
            action_category="spell",
            target_type="position_aoe",
            can_afford=True,
            cost=ActionCostProfile(action_cost=1, spell_slot_cost=2),
            targets=[ActionTarget(index=0, position=position, affected_entity_uuids=affected)],
            outcome_profile=profile,
            semantic_id=semantics.semantic_id,
            semantics_ref=reference,
        )

    subset = row("subset", (2, 0), [first.uuid])
    superset = row("superset", (3, 0), [first.uuid, second.uuid])
    friendly_fire = row("friendly", (2, 1), [first.uuid, second.uuid, "actor"])
    allied_fire = row(
        "allied",
        (3, 1),
        [first.uuid, second.uuid, "visible-ally"],
    )
    entities = dict(world.known_entities)
    entities[second.uuid] = second
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        position_actions=[subset, superset, friendly_fire, allied_fire],
        semantic_catalog={reference: semantics},
    )
    world = world.model_copy(update={
        "known_entities": entities,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    proposals = direct_damage_candidates(context)

    assert len(proposals) == 1
    assert proposals[0].intent == ExecuteIntent(row_id=superset.row_id)
    target_plan = proposals[0].evidence.target_plan
    assert target_plan is not None
    assert target_plan.controlled_entity_uuids == tuple()
    assert target_plan.allied_entity_uuids == tuple()
    waste = next(
        component
        for component in proposals[0].utility_components
        if component.name == "subjective_expected_damage_waste"
    )
    assert waste.weight == 0.0

    controlled_second = _with_damage_ending_control(
        second,
        applied_source_event_cursor=10,
    )
    controlled_world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            controlled_second.uuid: controlled_second,
        },
    })
    controlled_context = PolicyContext.model_construct(
        world=controlled_world,
        facts=derive_agent_facts(controlled_world).facts,
        deadline_monotonic=None,
    )

    controlled_proposals = direct_damage_candidates(controlled_context)

    assert {
        proposal.intent.row_id
        for proposal in controlled_proposals
        if isinstance(proposal.intent, ExecuteIntent)
    } == {subset.row_id, superset.row_id}
    assert UtilityArbiter().select(controlled_proposals).intent == ExecuteIntent(
        row_id=subset.row_id
    )


def test_spacing_policy_uses_typed_capability_and_ignores_actor_name_or_row_order() -> None:
    """A spent ranged actor retreats by geometry without identity-name policy."""
    first_world = _spacing_choice_world(
        actor_name="Opaque participant",
        enemy_position=(2, 0),
        reverse_rows=False,
    )
    second_world = _spacing_choice_world(
        actor_name="Renamed participant",
        enemy_position=(2, 0),
        reverse_rows=True,
    )

    first = evaluate_default_policy(
        PolicyContext.model_construct(
            world=first_world,
            facts=derive_agent_facts(first_world).facts,
            deadline_monotonic=None,
        ),
        tuple(),
    )
    second = evaluate_default_policy(
        PolicyContext.model_construct(
            world=second_world,
            facts=derive_agent_facts(second_world).facts,
            deadline_monotonic=None,
        ),
        tuple(),
    )

    assert first.decision is not None
    assert second.decision is not None
    assert first.decision.selected.intent == ExecuteIntent(
        row_id="position|opaque-move|pos=-4,0"
    )
    assert second.decision.selected.intent == first.decision.selected.intent
    evidence = first.decision.selected.evidence.spacing
    assert evidence is not None
    assert evidence.current_distance_cells == 2
    assert evidence.selected_distance_cells == 6
    assert evidence.spacing_floor_cells == 6
    assert evidence.anchor_position == (-4, 0)


def test_post_pressure_melee_positioning_closes_future_range_deficit() -> None:
    """A spent melee actor uses remaining movement to enter next-turn attack range."""
    world = _spacing_choice_world(
        actor_name="Opaque melee participant",
        enemy_position=(3, 0),
        reverse_rows=False,
        movement_positions=((1, 0), (2, 0), (0, 1)),
        normal_range_feet=5,
    )
    epoch = world.current_epoch
    assert epoch is not None
    capability = epoch.affordances.capabilities[0]
    melee_semantics = ActionSemantics(
        semantic_id="damage.opaque.melee",
        tags=frozenset({ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}),
    )
    melee_ref = action_semantics_ref(melee_semantics)
    capability = capability.model_copy(update={
        "semantic_key": "damage.opaque.melee",
        "action_category": "attack",
        "target_type": "entity",
        "range_type": "Reach",
        "normal_range_feet": 5,
        "weapon_slot": "MELEE_MAIN",
        "semantic_id": melee_semantics.semantic_id,
        "semantics_ref": melee_ref,
        "tags": tuple(tag.value for tag in melee_semantics.tags),
    })
    affordances = epoch.affordances.model_copy(update={
        "capabilities": (capability,),
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            melee_ref: melee_semantics,
        },
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(
        row_id="position|opaque-move|pos=2,0",
        prefer_safe=True,
    )
    evidence = evaluation.decision.selected.evidence.spacing
    assert evidence is not None
    assert evidence.current_distance_cells == 3
    assert evidence.selected_distance_cells == 1
    assert evidence.spacing_floor_cells == 1
    assert evidence.normal_attack_range_cells == 1
    assert evidence.offensive_range_deficit_cells == 0


def test_post_pressure_positioning_preserves_stronger_ranged_envelope() -> None:
    """A weaker melee fallback cannot pull a ranged actor out of its envelope."""
    world = _spacing_choice_world(
        actor_name="Opaque mixed-loadout participant",
        enemy_position=(6, 0),
        reverse_rows=False,
        movement_positions=((5, 0), (4, 0), (0, 1)),
        normal_range_feet=30,
    )
    epoch = world.current_epoch
    assert epoch is not None
    ranged_capability = epoch.affordances.capabilities[0].model_copy(update={
        "capability_id": "damage.opaque.ranged|entity|RANGED_MAIN",
        "weapon_slot": "RANGED_MAIN",
        "range_type": "Range",
        "normal_range_feet": 30,
        "long_range_feet": 120,
        "outcome_profile": ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=5,
            damage_rolls=(
                DamageRollProfile(
                    dice_count=1,
                    die_size=8,
                    flat_bonus=3,
                    damage_type="piercing",
                ),
            ),
        ),
    })
    melee_semantics = ActionSemantics(
        semantic_id="damage.opaque.melee-fallback",
        tags=frozenset({ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}),
    )
    melee_ref = action_semantics_ref(melee_semantics)
    melee_capability = ActionCapability(
        capability_id="damage.opaque.melee|entity|MELEE_MAIN",
        semantic_key="damage.opaque.melee",
        action_category="attack",
        target_type="entity",
        cost=ActionCostProfile(action_cost=1),
        range_type="Reach",
        normal_range_feet=5,
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        weapon_slot="MELEE_MAIN",
        outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=5,
            damage_rolls=(
                DamageRollProfile(
                    dice_count=1,
                    die_size=6,
                    flat_bonus=2,
                    damage_type="slashing",
                ),
            ),
        ),
        semantic_id=melee_semantics.semantic_id,
        semantics_ref=melee_ref,
        tags=tuple(tag.value for tag in melee_semantics.tags),
    )
    affordances = epoch.affordances.model_copy(update={
        "capabilities": (melee_capability, ranged_capability),
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            melee_ref: melee_semantics,
        },
    })
    entities = dict(world.known_entities)
    entities["visible-enemy"] = entities["visible-enemy"].model_copy(
        update={"ac": 13}
    )
    world = world.model_copy(update={
        "known_entities": entities,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == EndTurnIntent()
    evidence = evaluation.decision.selected.evidence.spacing
    assert evidence is not None
    assert evidence.current_distance_cells == 6
    assert evidence.selected_distance_cells == 6
    assert evidence.spacing_floor_cells == 6
    assert evidence.normal_attack_range_cells == 6
    components = {
        component.name: component.raw_value
        for component in evaluation.decision.selected.utility_components
    }
    assert components["capability_envelopes_evaluated"] == 2.0
    assert components["capability_envelopes_retained"] == 1.0


@pytest.mark.parametrize(
    ("profile", "target_updates", "expected_status"),
    (
        (
            ActionOutcomeProfile(
                resolution=OutcomeResolution.AUTOMATIC,
                damage_rolls=(DamageRollProfile(
                    dice_count=1,
                    die_size=4,
                    damage_type="force",
                ),),
            ),
            {},
            CapabilityModelStatus.MODELED,
        ),
        (
            ActionOutcomeProfile(
                resolution=OutcomeResolution.AUTOMATIC,
                damage_rolls=(DamageRollProfile(
                    dice_count=1,
                    die_size=4,
                    damage_type="force",
                ),),
            ),
            {"damage_immunities": ["force"]},
            CapabilityModelStatus.GUARANTEED_ZERO,
        ),
        (
            ActionOutcomeProfile(
                resolution=OutcomeResolution.ATTACK_ROLL,
                attack_bonus=5,
                damage_rolls=(DamageRollProfile(
                    dice_count=1,
                    die_size=8,
                    damage_type="piercing",
                ),),
            ),
            {"ac": None},
            CapabilityModelStatus.INSUFFICIENT_FACTS,
        ),
        (
            None,
            {},
            CapabilityModelStatus.UNMODELED,
        ),
    ),
)
def test_future_capability_projection_preserves_outcome_knowledge_state(
    profile: ActionOutcomeProfile | None,
    target_updates: dict[str, object],
    expected_status: CapabilityModelStatus,
) -> None:
    """Unknown models and facts cannot silently become genuine zero pressure."""
    world = _spacing_choice_world(
        actor_name="Projection status participant",
        enemy_position=(6, 0),
        reverse_rows=False,
        normal_range_feet=30,
    )
    epoch = world.current_epoch
    assert epoch is not None
    capability = epoch.affordances.capabilities[0].model_copy(update={
        "outcome_profile": profile,
    })
    target = world.known_entities["visible-enemy"].model_copy(
        update=target_updates,
    )
    world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            target.uuid: target,
        },
        "current_epoch": epoch.model_copy(update={
            "affordances": epoch.affordances.model_copy(update={
                "capabilities": (capability,),
            }),
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    projections = candidate_module._future_capability_target_projections(context)

    assert len(projections) == 1
    projection = projections[0]
    assert projection.model_status is expected_status
    assert projection.capability_id == capability.capability_id
    assert projection.target_entity_uuid == target.uuid
    assert projection.projection_scope is CapabilityProjectionScope.FUTURE_TURN
    assert projection.range_state is CapabilityRangeState.IN_RANGE
    if expected_status in {
        CapabilityModelStatus.MODELED,
        CapabilityModelStatus.GUARANTEED_ZERO,
    }:
        assert projection.pressure_value is not None
    else:
        assert projection.pressure_value is None


def test_unmodeled_future_capability_does_not_create_a_spacing_goal() -> None:
    """A missing engine outcome contract cannot masquerade as zero-valued tactics."""
    world = _spacing_choice_world(
        actor_name="Unmodeled capability participant",
        enemy_position=(6, 0),
        reverse_rows=False,
        normal_range_feet=30,
    )
    epoch = world.current_epoch
    assert epoch is not None
    capability = epoch.affordances.capabilities[0].model_copy(
        update={"outcome_profile": None},
    )
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "affordances": epoch.affordances.model_copy(update={
                "capabilities": (capability,),
            }),
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    assert spacing_candidates(context) == tuple()
    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.goal is PolicyGoal.END_TURN
    assert evaluation.decision.selected.evidence.spacing is None


def test_future_capability_projection_binds_pressure_and_geometry_to_one_target() -> None:
    """A farther target's pressure cannot be paired with a nearer target's geometry."""
    world = _spacing_choice_world(
        actor_name="Target-bound projection participant",
        enemy_position=(2, 0),
        reverse_rows=False,
        normal_range_feet=60,
    )
    epoch = world.current_epoch
    assert epoch is not None
    capability = epoch.affordances.capabilities[0].model_copy(update={
        "outcome_profile": ActionOutcomeProfile(
            resolution=OutcomeResolution.AUTOMATIC,
            damage_rolls=(DamageRollProfile(
                dice_count=1,
                die_size=10,
                damage_type="force",
            ),),
        ),
    })
    near = world.known_entities["visible-enemy"].model_copy(update={
        "damage_immunities": ["force"],
    })
    far = near.model_copy(update={
        "uuid": "far-visible-enemy",
        "name": "Far vulnerable enemy",
        "position": (7, 0),
        "hp": 4,
        "damage_immunities": [],
    })
    world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            near.uuid: near,
            far.uuid: far,
        },
        "current_epoch": epoch.model_copy(update={
            "affordances": epoch.affordances.model_copy(update={
                "capabilities": (capability,),
            }),
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    spacing = evaluation.decision.selected.evidence.spacing
    assert spacing is not None
    projection = spacing.capability_target_projection
    assert projection is not None
    assert projection.target_entity_uuid == far.uuid
    assert spacing.reference_entity_uuid == far.uuid
    assert projection.target_position == far.position
    assert projection.distance_feet == 35
    assert projection.pressure_value is not None
    assert projection.pressure_value > 0


def test_future_projection_discloses_resources_and_concentration_replacement() -> None:
    """Future policy sees exact persistent costs and the active concentration loss."""
    world = _spacing_choice_world(
        actor_name="Concentrating resource participant",
        enemy_position=(6, 0),
        reverse_rows=False,
        normal_range_feet=30,
    )
    epoch = world.current_epoch
    assert epoch is not None
    capability = epoch.affordances.capabilities[0]
    semantics = ActionSemantics(
        semantic_id=capability.semantic_id,
        tags=frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_SINGLE_TARGET}),
        concentration_effect=ConcentrationEffect(
            operation=ConcentrationOperation.START_OR_REPLACE,
            spell_semantic_id=capability.semantic_id,
        ),
    )
    semantics_ref = action_semantics_ref(semantics)
    capability = capability.model_copy(update={
        "cost": ActionCostProfile(action_cost=1, spell_slot_cost=2),
        "semantics_ref": semantics_ref,
        "outcome_profile": ActionOutcomeProfile(
            resolution=OutcomeResolution.AUTOMATIC,
            damage_rolls=(DamageRollProfile(
                dice_count=2,
                die_size=6,
                damage_type="cold",
            ),),
        ),
    })
    economy = epoch.economy.model_copy(update={
        "spell_slots": {2: ResourcePool(current=1, max=2)},
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "economy": economy,
            "affordances": epoch.affordances.model_copy(update={
                "capabilities": (capability,),
                "semantic_catalog": {
                    **epoch.affordances.semantic_catalog,
                    semantics_ref: semantics,
                },
            }),
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    projection = candidate_module._future_capability_target_projections(context)[0]

    assert projection.turn_refresh_assumed is True
    assert [requirement.model_dump() for requirement in projection.persistent_requirements] == [
        {"resource_id": "spell_slot.2", "required": 1, "available": 1}
    ]
    assert projection.affordable_after_refresh is True
    assert projection.affordability_reasons == tuple()
    assert projection.concentration_operation is ConcentrationOperation.START_OR_REPLACE
    assert projection.actor_is_concentrating is True
    assert projection.replaces_concentration is True


def test_future_envelope_dominance_preserves_pressure_distance_tradeoff() -> None:
    """A stronger melee option remains when reach and pressure disagree."""
    def projection(
        capability_id: str,
        *,
        preferred_minimum: int,
        maximum: int,
        pressure: float,
    ) -> CapabilityTargetProjection:
        distance_feet = 30
        return CapabilityTargetProjection(
            projection_scope=CapabilityProjectionScope.FUTURE_TURN,
            capability_id=capability_id,
            semantic_id=capability_id,
            target_entity_uuid="visible-enemy",
            origin_position=(0, 0),
            target_position=(6, 0),
            distance_feet=distance_feet,
            normal_range_feet=maximum * 5,
            preferred_minimum_range_feet=preferred_minimum * 5,
            range_state=(
                CapabilityRangeState.IN_RANGE
                if distance_feet <= maximum * 5
                else CapabilityRangeState.OUT_OF_RANGE
            ),
            requires_line_of_sight=True,
            line_of_sight=TruthValue.TRUE,
            turn_refresh_assumed=True,
            affordable_after_refresh=True,
            actor_is_concentrating=False,
            replaces_concentration=False,
            model_status=CapabilityModelStatus.MODELED,
            expected_hp_loss=pressure,
            defeat_probability=0,
            nonzero_probability=1,
            pressure_value=pressure,
            model_scope="actor_baseline+known_target",
            eligible=True,
        )

    ranged = projection(
        "opaque-ranged",
        preferred_minimum=6,
        maximum=6,
        pressure=3.0,
    )
    melee = projection(
        "opaque-melee",
        preferred_minimum=1,
        maximum=1,
        pressure=4.0,
    )

    retained = candidate_module._non_dominated_distance_envelopes(
        (ranged, melee),
    )

    assert {envelope.capability_id for envelope in retained} == {
        "opaque-ranged",
        "opaque-melee",
    }


def test_future_selector_prefers_stronger_ranged_posture_over_near_melee() -> None:
    """Current positional convenience cannot define the actor's future role."""
    def projection(
        capability_id: str,
        *,
        preferred_minimum: int,
        maximum: int,
        pressure: float,
    ) -> CapabilityTargetProjection:
        distance_feet = 10
        return CapabilityTargetProjection(
            projection_scope=CapabilityProjectionScope.FUTURE_TURN,
            capability_id=capability_id,
            semantic_id=capability_id,
            target_entity_uuid="visible-enemy",
            origin_position=(0, 0),
            target_position=(2, 0),
            distance_feet=distance_feet,
            normal_range_feet=maximum * 5,
            preferred_minimum_range_feet=preferred_minimum * 5,
            range_state=(
                CapabilityRangeState.IN_RANGE
                if distance_feet <= maximum * 5
                else CapabilityRangeState.OUT_OF_RANGE
            ),
            requires_line_of_sight=True,
            line_of_sight=TruthValue.TRUE,
            turn_refresh_assumed=True,
            affordable_after_refresh=True,
            actor_is_concentrating=False,
            replaces_concentration=False,
            model_status=CapabilityModelStatus.MODELED,
            expected_hp_loss=pressure,
            defeat_probability=0,
            nonzero_probability=1,
            pressure_value=pressure,
            model_scope="actor_baseline+known_target",
            eligible=True,
        )

    ranged = projection(
        "fire-bolt",
        preferred_minimum=6,
        maximum=24,
        pressure=10.75,
    )
    melee = projection(
        "dagger",
        preferred_minimum=1,
        maximum=1,
        pressure=2.825,
    )

    retained = candidate_module._non_dominated_distance_envelopes((ranged, melee))
    selected = candidate_module._select_future_distance_envelope(retained)

    assert selected.capability_id == "fire-bolt"


def test_future_selector_preserves_usable_envelope_before_distant_pressure() -> None:
    """Spent actors hold an in-range threat instead of chasing marginal pressure."""
    def projection(
        capability_id: str,
        target_uuid: str,
        *,
        target_position: tuple[int, int],
        pressure: float,
        range_state: CapabilityRangeState,
    ) -> CapabilityTargetProjection:
        return CapabilityTargetProjection(
            projection_scope=CapabilityProjectionScope.FUTURE_TURN,
            capability_id=capability_id,
            semantic_id="damage.single_target",
            target_entity_uuid=target_uuid,
            origin_position=(0, 0),
            target_position=target_position,
            distance_feet=max(abs(target_position[0]), abs(target_position[1])) * 5,
            normal_range_feet=5,
            preferred_minimum_range_feet=5,
            range_state=range_state,
            requires_line_of_sight=True,
            line_of_sight=TruthValue.TRUE,
            turn_refresh_assumed=True,
            affordable_after_refresh=True,
            actor_is_concentrating=False,
            replaces_concentration=False,
            model_status=CapabilityModelStatus.MODELED,
            expected_hp_loss=pressure,
            defeat_probability=0,
            nonzero_probability=1,
            pressure_value=pressure,
            model_scope="actor_baseline+known_target",
            eligible=True,
        )

    adjacent_wounded_mage = projection(
        "greatsword",
        "mage",
        target_position=(1, 1),
        pressure=7.436,
        range_state=CapabilityRangeState.IN_RANGE,
    )
    distant_healthy_archer = projection(
        "greatsword",
        "archer",
        target_position=(4, 5),
        pressure=9.729,
        range_state=CapabilityRangeState.OUT_OF_RANGE,
    )

    selected = candidate_module._select_future_distance_envelope((
        adjacent_wounded_mage,
        distant_healthy_archer,
    ))

    assert selected.target_entity_uuid == "mage"


def test_post_pressure_positioning_rejects_exhausted_persistent_capability_cost() -> None:
    """Turn refresh cannot invent a spell slot or other persistent resource."""
    world = _spacing_choice_world(
        actor_name="Resource-exhausted participant",
        enemy_position=(8, 0),
        reverse_rows=False,
    )
    epoch = world.current_epoch
    assert epoch is not None
    capability = epoch.affordances.capabilities[0]
    capability = capability.model_copy(update={
        "cost": ActionCostProfile(
            action_cost=1,
            spell_slot_cost=1,
            affordability="unaffordable",
            affordability_reasons=("spell_slot.1",),
        ),
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "economy": epoch.economy.model_copy(update={"spell_slots": {}}),
            "affordances": epoch.affordances.model_copy(update={
                "capabilities": (capability,),
            }),
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    assert spacing_candidates(context) == tuple()
    evaluation = evaluate_default_policy(context, tuple())
    assert evaluation.decision is not None
    assert isinstance(evaluation.decision.selected.intent, EndTurnIntent)


def test_exhausted_actor_uses_terminal_branch_instead_of_spacing_hold() -> None:
    """A terminal epoch cannot masquerade as post-pressure positioning."""
    world = _spacing_choice_world(
        actor_name="Exhausted participant",
        enemy_position=(6, 0),
        reverse_rows=False,
    )
    epoch = world.current_epoch
    assert epoch is not None
    exhausted_epoch = epoch.model_copy(update={
        "economy": epoch.economy.model_copy(update={
            "actions": 0,
            "bonus_actions": 0,
            "reactions": 0,
            "movement_remaining": 0,
            "extra_attacks": 0,
            "meaningful_commands_remaining": False,
        }),
        "affordances": epoch.affordances.model_copy(update={
            "position_actions": tuple(),
        }),
    })
    world = world.model_copy(update={"current_epoch": exhausted_epoch})
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    assert spacing_candidates(context) == tuple()
    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == EndTurnIntent()
    assert evaluation.decision.selected.goal is PolicyGoal.END_TURN
    assert evaluation.decision.selected.source_node == "TurnLifecycle/EndTurn"
    assert evaluation.decision.selected.reason == (
        "no_higher_value_legal_tactical_or_information_action"
    )
    assert evaluation.decision.selected.evidence.spacing is None
    trace_paths = {step.node_path for step in evaluation.decision.trace}
    assert "ReactiveRoot/TerminalFallback/EndTurn" in trace_paths
    assert not any(
        path.endswith("PositionAndSurvival/CapabilityEnvelope")
        for path in trace_paths
    )


def test_spacing_policy_prices_disclosed_opportunity_attack_exposure() -> None:
    """A safer retreat outranks a longer route that crosses a hostile threat boundary."""
    world = _spacing_choice_world(
        actor_name="Exposed ranged participant",
        enemy_position=(1, 0),
        reverse_rows=False,
    )
    epoch = world.current_epoch
    assert epoch is not None
    rows = list(epoch.affordances.position_actions)
    risky_index = next(
        index
        for index, row in enumerate(rows)
        if row.row_id == "position|opaque-move|pos=-4,0"
    )
    risky_row = rows[risky_index]
    risky_target = risky_row.targets[0]
    risky_target = ActionTarget.model_validate({
        **risky_target.model_dump(mode="python"),
        "safe_path_cost": None,
        "opportunity_attack_exposures": [{
            "reactor_uuid": "visible-enemy",
            "reactor_name": "Visible Enemy",
            "from_position": (0, 0),
            "to_position": (-1, 0),
        }],
    })
    rows[risky_index] = risky_row.model_copy(update={"targets": [risky_target]})
    affordances = epoch.affordances.model_copy(update={"position_actions": rows})
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(
        row_id="position|opaque-move|pos=-2,0"
    )
    risky_proposal = next(
        proposal
        for proposal in evaluation.decision.candidates
        if isinstance(proposal.intent, ExecuteIntent)
        and proposal.intent.row_id == risky_row.row_id
    )
    exposure_component = next(
        component
        for component in risky_proposal.utility_components
        if component.name == "opportunity_attack_exposure"
    )
    assert exposure_component.raw_value == 1.0
    assert exposure_component.weight < 0
    spacing = risky_proposal.evidence.spacing
    assert spacing is not None
    assert tuple(
        exposure.reactor_uuid
        for exposure in spacing.opportunity_attack_exposures
    ) == ("visible-enemy",)


def test_spacing_policy_holds_when_spent_actor_already_has_range() -> None:
    """Post-pressure positioning ends the turn when movement cannot improve spacing."""
    world = _spacing_choice_world(
        actor_name="Another opaque participant",
        enemy_position=(8, 0),
        reverse_rows=False,
    )
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent.kind == "end_turn"
    assert evaluation.decision.selected.goal.value == "position_and_survival"
    evidence = evaluation.decision.selected.evidence.spacing
    assert evidence is not None
    assert evidence.current_distance_cells == 8
    assert evidence.selected_distance_cells == 8
    assert evidence.anchor_position == (0, 0)


def test_spacing_hold_does_not_project_endpoints_when_all_deficits_are_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Satisfied capability and ally envelopes require no geometry search."""
    world = _spacing_choice_world(
        actor_name="Satisfied-envelope participant",
        enemy_position=(8, 0),
        reverse_rows=False,
    )
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    def reject_projection(
        _context: PolicyContext,
        _projection: CapabilityTargetProjection,
        _origin: tuple[int, int],
    ) -> CapabilityTargetProjection:
        raise AssertionError("zero-deficit spacing projected a movement endpoint")

    monkeypatch.setattr(
        candidate_module,
        "_capability_projection_at_origin",
        reject_projection,
    )

    proposals = spacing_candidates(context)

    assert len(proposals) == 1
    assert proposals[0].intent.kind == "end_turn"
    components = {
        component.name: component
        for component in proposals[0].utility_components
    }
    assert components["movement_rows_evaluated"].raw_value == 0


def test_spacing_candidates_bound_dense_equivalent_movement_rows() -> None:
    """Dense movement geometry retains bounded policy-distinct representatives."""
    positions = tuple(
        (x, y)
        for x in range(-7, 8)
        for y in range(-7, 8)
        if (x, y) != (0, 0)
    )
    first_world = _spacing_choice_world(
        actor_name="Dense spacing participant",
        enemy_position=(1, 0),
        reverse_rows=False,
        movement_positions=positions,
    )
    second_world = _spacing_choice_world(
        actor_name="Reversed dense spacing participant",
        enemy_position=(1, 0),
        reverse_rows=True,
        movement_positions=positions,
    )
    first_context = PolicyContext.model_construct(
        world=first_world,
        facts=derive_agent_facts(first_world).facts,
        deadline_monotonic=None,
    )
    second_context = PolicyContext.model_construct(
        world=second_world,
        facts=derive_agent_facts(second_world).facts,
        deadline_monotonic=None,
    )

    first = spacing_candidates(first_context)
    second = spacing_candidates(second_context)

    assert len(first) == 2
    assert tuple(proposal.intent for proposal in first) == tuple(
        proposal.intent for proposal in second
    )
    selected_move = next(
        proposal for proposal in first if isinstance(proposal.intent, ExecuteIntent)
    )
    components = {
        component.name: component for component in selected_move.utility_components
    }
    assert components["movement_rows_evaluated"].raw_value == len(positions)
    assert components["represented_movement_rows"].raw_value > 100
    assert components["movement_rows_evaluated"].weight == 0
    assert components["represented_movement_rows"].weight == 0


def test_spacing_projects_capabilities_once_per_unique_movement_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Equivalent Move/Jump geometry shares one subjective line projection."""
    world = _spacing_choice_world(
        actor_name="Duplicate-endpoint participant",
        enemy_position=(1, 0),
        reverse_rows=False,
        movement_positions=((-2, 0), (-4, 0)),
    )
    epoch = world.current_epoch
    assert epoch is not None
    first_row = epoch.affordances.position_actions[0]
    duplicate = first_row.model_copy(update={
        "row_id": "position|alternate-relocation|pos=-2,0",
        "template_name": "alternate-relocation",
    })
    affordances = epoch.affordances.model_copy(update={
        "position_actions": [*epoch.affordances.position_actions, duplicate],
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )
    projection_calls = 0
    original_projection = candidate_module._capability_projection_at_origin

    def count_projection(
        active_context: PolicyContext,
        projection: CapabilityTargetProjection,
        origin: tuple[int, int],
        *,
        topology_workspace: KnownLineOfSightWorkspace | None = None,
    ) -> CapabilityTargetProjection:
        nonlocal projection_calls
        projection_calls += 1
        return original_projection(
            active_context,
            projection,
            origin,
            topology_workspace=topology_workspace,
        )

    monkeypatch.setattr(
        candidate_module,
        "_capability_projection_at_origin",
        count_projection,
    )

    assert spacing_candidates(context)
    assert projection_calls == 2


def test_spacing_policy_saturates_hostile_and_ally_distance_goals() -> None:
    """Once both spacing deficits close, the shortest legal anchor wins."""
    world = _spacing_choice_world(
        actor_name="Bounded ranged participant",
        enemy_position=(6, 0),
        reverse_rows=False,
        controlled_ally_position=(0, 1),
        movement_positions=((0, -4), (0, -6)),
    )
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(
        row_id="position|opaque-move|pos=0,-4"
    )
    spacing = evaluation.decision.selected.evidence.spacing
    assert spacing is not None
    assert spacing.hostile_spacing_deficit_cells == 0
    assert spacing.ally_spacing_deficit_cells == 0


def test_spacing_policy_preserves_typed_normal_attack_range() -> None:
    """Ally spreading does not buy one extra cell by leaving normal range."""
    world = _spacing_choice_world(
        actor_name="Range-bounded participant",
        enemy_position=(6, 0),
        reverse_rows=True,
        controlled_ally_position=(0, 1),
        movement_positions=((0, -3), (0, -4)),
        normal_range_feet=30,
    )
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(
        row_id="position|opaque-move|pos=0,-3"
    )
    spacing = evaluation.decision.selected.evidence.spacing
    assert spacing is not None
    assert spacing.normal_attack_range_cells == 6
    assert spacing.offensive_range_deficit_cells == 0


def test_shared_policy_prefers_typed_hard_control_against_healthy_hostile() -> None:
    """Hard control competes with damage through semantics and inspectable utility."""
    world, control_row, damage_row = _control_choice_world(concentrating=False)
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=control_row.row_id)
    assert {proposal.intent.row_id for proposal in evaluation.decision.candidates if isinstance(proposal.intent, ExecuteIntent)} == {
        control_row.row_id,
        damage_row.row_id,
    }
    components = {
        component.name: component
        for component in evaluation.decision.selected.utility_components
    }
    assert components["hard_control"].raw_value == 1.0
    assert components["future_action_denial_value"].raw_value == pytest.approx(1.0)
    assert components["concentration_replacement"].raw_value == 0.0


def test_shared_policy_can_trade_finite_bonus_action_healing_against_pressure() -> None:
    """Critical self-healing competes in utility without a potion-name policy branch."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    healing_semantics = ActionSemantics(
        semantic_id="support.heal",
        tags=frozenset({ActionTag.SUPPORT_HEAL, ActionTag.RESOURCE_SPEND}),
        guaranteed_effects=(LogicalEffect(
            fact_id="actor.hp",
            operation=EffectOperation.INCREASE,
            value=7,
        ),),
    )
    healing_ref = action_semantics_ref(healing_semantics)
    healing_row = ActionAffordance(
        row_id="self|opaque-recovery|uuid=potion-stack",
        bucket="self_actions",
        template_name="opaque-recovery",
        semantic_key="rules.support.fixed_healing",
        display_name="Localized recovery item",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(
            bonus_action_cost=1,
            item_charge_costs={"potion-stack": 1},
        ),
        is_item_use=True,
        source_item_uuid="potion-stack",
        semantic_id=healing_semantics.semantic_id,
        semantics_ref=healing_ref,
    )
    actor = world.known_entities["actor"].model_copy(update={
        "hp": 2,
        "normal_hp": 2,
        "temporary_hp": 0,
        "max_hp": 20,
        "healing_blocked": False,
        "conditions": [],
        "is_concentrating": False,
    })
    entities = dict(world.known_entities)
    entities[actor.uuid] = actor
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        entity_actions=epoch.affordances.entity_actions,
        self_actions=[healing_row],
        capabilities=epoch.affordances.capabilities,
        semantic_catalog={
            **epoch.affordances.semantic_catalog,
            healing_ref: healing_semantics,
        },
    )
    recovery_epoch = epoch.model_copy(update={
        "economy": epoch.economy.model_copy(update={
            "actions": 1,
            "bonus_actions": 1,
            "item_charges": {
                "potion-stack": ResourcePool(current=1, max=10),
            },
        }),
        "affordances": affordances,
    })
    recovery_world = world.model_copy(update={
        "known_entities": entities,
        "current_epoch": recovery_epoch,
    })
    context = PolicyContext.model_construct(
        world=recovery_world,
        facts=derive_agent_facts(recovery_world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=healing_row.row_id)
    assert {
        proposal.intent.row_id
        for proposal in evaluation.decision.candidates
        if isinstance(proposal.intent, ExecuteIntent)
    } == {
        epoch.affordances.entity_actions[0].row_id,
        healing_row.row_id,
    }
    healing = evaluation.decision.selected.evidence.healing
    assert healing is not None
    assert healing.entity_uuid == actor.uuid
    assert healing.expected_raw_healing == 7
    assert healing.expected_hp_restored == 7
    assert healing.expected_waste == 0
    components = {
        component.name: component
        for component in evaluation.decision.selected.utility_components
    }
    assert components["critical_survival_value"].contribution > 0
    assert components["finite_item_charge_cost"].raw_value == 1


def test_healing_utility_uses_normal_hp_and_rejects_blocked_healing() -> None:
    """Temporary HP neither hides wounds nor overrides an explicit healing block."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    semantics = ActionSemantics(
        semantic_id="support.heal",
        tags=frozenset({ActionTag.SUPPORT_HEAL}),
        guaranteed_effects=(LogicalEffect(
            fact_id="actor.hp",
            operation=EffectOperation.INCREASE,
            value=7,
        ),),
    )
    semantics_ref = action_semantics_ref(semantics)
    row = ActionAffordance(
        row_id="self|opaque-recovery|index=0",
        bucket="self_actions",
        template_name="opaque-recovery",
        semantic_key="rules.support.fixed_healing",
        display_name="Localized recovery item",
        action_category="ability",
        target_type="self",
        can_afford=True,
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
    )
    actor = world.known_entities["actor"].model_copy(update={
        "hp": 12,
        "normal_hp": 2,
        "temporary_hp": 10,
        "max_hp": 20,
        "healing_blocked": True,
    })
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        self_actions=[row],
        capabilities=epoch.affordances.capabilities,
        semantic_catalog={
            **epoch.affordances.semantic_catalog,
            semantics_ref: semantics,
        },
    )
    blocked_world = world.model_copy(update={
        "known_entities": {**world.known_entities, actor.uuid: actor},
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    blocked_context = PolicyContext.model_construct(
        world=blocked_world,
        facts=derive_agent_facts(blocked_world).facts,
        deadline_monotonic=None,
    )

    blocked = build_policy_candidate_set(blocked_context)

    assert blocked.healing == tuple()

    healable_world = blocked_world.model_copy(update={
        "known_entities": {
            **blocked_world.known_entities,
            actor.uuid: actor.model_copy(update={"healing_blocked": False}),
        },
    })
    healable_context = PolicyContext.model_construct(
        world=healable_world,
        facts=derive_agent_facts(healable_world).facts,
        deadline_monotonic=None,
    )

    healable = build_policy_candidate_set(healable_context)

    assert len(healable.healing) == 1
    assert healable.healing[0].evidence.healing is not None
    assert healable.healing[0].evidence.healing.expected_hp_restored == 7


def test_shared_policy_preserves_active_concentration_when_damage_competes() -> None:
    """An existing concentration effect creates an explicit cross-goal conflict cost."""
    world, control_row, damage_row = _control_choice_world(concentrating=True)
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=damage_row.row_id)
    control = next(
        proposal
        for proposal in evaluation.decision.candidates
        if isinstance(proposal.intent, ExecuteIntent)
        and proposal.intent.row_id == control_row.row_id
    )
    components = {component.name: component for component in control.utility_components}
    assert components["concentration_replacement"].raw_value == 1.0
    assert components["concentration_replacement"].contribution < 0


def test_shared_policy_prefers_modeled_lethal_damage_over_soft_control() -> None:
    """A high-probability defeat outranks soft control on the same one-HP target."""
    world, control_row, damage_row = _control_choice_world(
        concentrating=False,
        enemy_hp=1,
        hard_control=False,
        damage_outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=7,
            damage_rolls=[
                DamageRollProfile(
                    dice_count=1,
                    die_size=12,
                    flat_bonus=6,
                    damage_type="slashing",
                )
            ],
        ),
    )
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=damage_row.row_id)
    assert evaluation.decision.selected.intent != ExecuteIntent(row_id=control_row.row_id)
    components = {
        component.name: component
        for component in evaluation.decision.selected.utility_components
    }
    assert components["subjective_expected_defeats"].raw_value == pytest.approx(0.75)


def test_shared_policy_scales_hard_control_by_remaining_target_agency() -> None:
    """A nearly defeated target does not receive full healthy-target control value."""
    shared_cost = ActionCostProfile(bonus_action_cost=1, spell_slot_cost=2)
    world, control_row, damage_row = _control_choice_world(
        concentrating=False,
        enemy_hp=7,
        enemy_max_hp=40,
        hard_control=True,
        control_cost=shared_cost,
        damage_cost=shared_cost,
        damage_outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.SAVING_THROW,
            damage_rolls=[
                DamageRollProfile(
                    dice_count=4,
                    die_size=6,
                    flat_bonus=0,
                    damage_type="fire",
                )
            ],
            save_dc=15,
            save_ability="dexterity",
            half_damage_on_save=True,
            application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
        ),
    )
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=damage_row.row_id)
    control = next(
        proposal
        for proposal in evaluation.decision.candidates
        if isinstance(proposal.intent, ExecuteIntent)
        and proposal.intent.row_id == control_row.row_id
    )
    components = {component.name: component for component in control.utility_components}
    assert components["hard_control"].raw_value == pytest.approx(7 / 40)
    assert components["future_action_denial_value"].raw_value == pytest.approx(7 / 40)


def test_shared_policy_does_not_treat_unvalued_displacement_as_action_denial() -> None:
    """Unknown forced-movement value cannot outrank modeled direct pressure."""
    displacement = ActionSemantics(
        semantic_id="control.forced-displacement.test",
        tags=frozenset({ActionTag.CONTROL_SOFT, ActionTag.MOVEMENT_FORCED}),
        stochastic_effects=(
            StochasticEffect(
                outcome_kind=OutcomeKind.CONTESTED,
                effects=(
                    LogicalEffect(
                        fact_id="selected_target.position",
                        operation=EffectOperation.SET_FROM_TARGET,
                        value_ref="unknown_forced_movement_endpoint",
                    ),
                ),
            ),
        ),
        spatial=SpatialSemantics(
            movement_kind=MovementKind.FORCED,
            moves_target=True,
        ),
    )
    world, control_row, damage_row = _control_choice_world(
        concentrating=False,
        enemy_hp=26,
        enemy_max_hp=40,
        control_semantics=displacement,
        control_cost=ActionCostProfile(bonus_action_cost=1),
        damage_cost=ActionCostProfile(bonus_action_cost=1),
        damage_outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=6,
            damage_rolls=[
                DamageRollProfile(
                    dice_count=1,
                    die_size=12,
                    flat_bonus=6,
                    damage_type="slashing",
                )
            ],
        ),
    )
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=damage_row.row_id)
    control = next(
        proposal
        for proposal in evaluation.decision.candidates
        if proposal.intent == ExecuteIntent(row_id=control_row.row_id)
    )
    components = {component.name: component for component in control.utility_components}
    assert components["future_action_denial_value"].raw_value == 0.0


def test_shared_policy_values_durable_self_setup_from_typed_effects() -> None:
    """Durable setup can precede pressure without action-name policy."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    setup_semantics = ActionSemantics(
        semantic_id="setup.durable.test",
        tags=frozenset({ActionTag.SETUP_SELF}),
        self_setup=SelfSetupSemantics(
            duration=SelfSetupDuration.UNTIL_REMOVED,
            increases_weapon_damage=True,
            resistance_damage_types=frozenset({"physical"}),
            grants_bonus_action_attack=True,
        ),
    )
    setup_ref = action_semantics_ref(setup_semantics)
    setup_row = ActionAffordance(
        row_id="self|opaque-durable-setup|index=0",
        bucket="self_actions",
        template_name="opaque-durable-setup",
        semantic_key="rules.setup.durable",
        display_name="Localized setup label",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(
            bonus_action_cost=1,
            resource_costs={"setup_resource": 1},
        ),
        targets=[ActionTarget(index=0, target_uuid="actor")],
        semantic_id=setup_semantics.semantic_id,
        semantics_ref=setup_ref,
    )
    affordances = epoch.affordances.model_copy(update={
        "self_actions": [setup_row],
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            setup_ref: setup_semantics,
        },
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=setup_row.row_id)
    assert evaluation.decision.selected.goal is PolicyGoal.SELF_SETUP
    components = {
        component.name: component
        for component in evaluation.decision.selected.utility_components
    }
    assert components["durable_setup"].raw_value == 1.0
    assert components["weapon_damage_setup"].contribution > 0
    assert components["damage_resistance_setup"].contribution > 0
    assert components["bonus_attack_access"].contribution > 0


def test_shared_policy_discounts_setup_that_is_unlikely_to_survive_its_first_use() -> None:
    """A disclosed maintenance check prevents fragile setup from preempting pressure."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    setup_semantics = ActionSemantics(
        semantic_id="setup.fragile-invisibility",
        tags=frozenset({ActionTag.SETUP_SELF, ActionTag.DEFENSE_SELF}),
        self_setup=SelfSetupSemantics(
            duration=SelfSetupDuration.UNTIL_REMOVED,
            grants_outgoing_attack_advantage=True,
            grants_incoming_attack_disadvantage=True,
            grants_invisibility=True,
            maintenance=SelfSetupMaintenanceSemantics(
                trigger=SetupMaintenanceTrigger.REVEALING_ACTION,
                skill_name="stealth",
                initial_dc=15,
                dc_increment_per_success=1,
                check_bonus=0,
                check_advantage=D20CheckMode.NONE,
                failure=SetupMaintenanceFailure.REMOVE_SETUP,
            ),
        ),
    )
    setup_ref = action_semantics_ref(setup_semantics)
    setup_row = ActionAffordance(
        row_id="self|fragile-invisibility|uuid=finite-buff",
        bucket="self_actions",
        template_name="fragile-invisibility",
        semantic_key="rules.setup.fragile_invisibility",
        display_name="Localized concealment",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(
            bonus_action_cost=1,
            item_charge_costs={"finite-buff": 1},
        ),
        targets=[ActionTarget(index=0, target_uuid="actor")],
        is_item_use=True,
        source_item_uuid="finite-buff",
        semantic_id=setup_semantics.semantic_id,
        semantics_ref=setup_ref,
    )
    affordances = epoch.affordances.model_copy(update={
        "self_actions": [setup_row],
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            setup_ref: setup_semantics,
        },
    })
    economy = epoch.economy.model_copy(update={
        "bonus_actions": 1,
        "item_charges": {"finite-buff": ResourcePool(current=1, max=1)},
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "affordances": affordances,
            "economy": economy,
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.goal is PolicyGoal.DIRECT_PRESSURE
    setup_proposal = next(
        proposal
        for proposal in evaluation.decision.candidates
        if proposal.intent == ExecuteIntent(row_id=setup_row.row_id)
    )
    components = {
        component.name: component
        for component in setup_proposal.utility_components
    }
    assert components["first_maintenance_retention_probability"].raw_value == pytest.approx(0.3)
    assert components["durable_setup"].raw_value == pytest.approx(0.3)
    assert components["invisibility_setup"].raw_value == pytest.approx(0.3)
    assert setup_proposal.evidence.self_setup is not None
    assert setup_proposal.evidence.self_setup.first_maintenance_success_probability == pytest.approx(0.3)


def test_shared_policy_uses_typed_immediate_defense_when_actor_is_badly_wounded() -> None:
    """A generic defense row can beat pressure without action-name policy."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    defense_semantics = ActionSemantics(
        semantic_id="defense.generic",
        tags=frozenset({ActionTag.DEFENSE_SELF}),
        guaranteed_effects=(LogicalEffect(
            fact_id="actor.condition.dodging",
            operation=EffectOperation.ADD,
            value=True,
        ),),
    )
    defense_ref = action_semantics_ref(defense_semantics)
    defense_row = ActionAffordance(
        row_id="self|localized-defense|index=0",
        bucket="self_actions",
        template_name="localized-defense",
        semantic_key="rules.defense.generic",
        display_name="Localized defensive label",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=[ActionTarget(index=0, target_uuid="actor")],
        semantic_id=defense_semantics.semantic_id,
        semantics_ref=defense_ref,
    )
    disengage_semantics = ActionSemantics(
        semantic_id="defense.reposition_only",
        tags=frozenset({ActionTag.DEFENSE_SELF}),
        guaranteed_effects=(LogicalEffect(
            fact_id="actor.condition.disengaging",
            operation=EffectOperation.ADD,
            value=True,
        ),),
    )
    disengage_ref = action_semantics_ref(disengage_semantics)
    disengage_row = ActionAffordance(
        row_id="self|localized-reposition-defense|index=0",
        bucket="self_actions",
        template_name="localized-reposition-defense",
        semantic_key="rules.defense.reposition_only",
        display_name="Localized reposition-defense label",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=[ActionTarget(index=0, target_uuid="actor")],
        semantic_id=disengage_semantics.semantic_id,
        semantics_ref=disengage_ref,
    )
    affordances = epoch.affordances.model_copy(update={
        "self_actions": [defense_row, disengage_row],
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            defense_ref: defense_semantics,
            disengage_ref: disengage_semantics,
        },
    })
    low_hp_actor = world.known_entities["actor"].model_copy(update={
        "hp": 3,
        "normal_hp": 3,
        "max_hp": 20,
    })
    low_hp_world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            "actor": low_hp_actor,
        },
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    low_hp_context = PolicyContext.model_construct(
        world=low_hp_world,
        facts=derive_agent_facts(low_hp_world).facts,
        deadline_monotonic=None,
    )

    low_hp_evaluation = evaluate_default_policy(low_hp_context, tuple())

    assert low_hp_evaluation.decision is not None
    assert low_hp_evaluation.decision.selected.intent == ExecuteIntent(row_id=defense_row.row_id)
    assert low_hp_evaluation.decision.selected.reason == "take_immediate_self_defense"
    components = {
        component.name: component
        for component in low_hp_evaluation.decision.selected.utility_components
    }
    assert components["low_hp_survival_urgency"].raw_value == pytest.approx(0.85)

    healthy_context = PolicyContext.model_construct(
        world=world.model_copy(update={
            "current_epoch": epoch.model_copy(update={"affordances": affordances}),
        }),
        facts=derive_agent_facts(world.model_copy(update={
            "current_epoch": epoch.model_copy(update={"affordances": affordances}),
        })).facts,
        deadline_monotonic=None,
    )
    healthy_evaluation = evaluate_default_policy(healthy_context, tuple())

    assert healthy_evaluation.decision is not None
    assert healthy_evaluation.decision.selected.goal is PolicyGoal.DIRECT_PRESSURE

    already_defending_actor = low_hp_actor.model_copy(update={"conditions": ["Dodging"]})
    already_defending_world = low_hp_world.model_copy(update={
        "known_entities": {
            **low_hp_world.known_entities,
            "actor": already_defending_actor,
        },
    })
    already_defending_context = PolicyContext.model_construct(
        world=already_defending_world,
        facts=derive_agent_facts(already_defending_world).facts,
        deadline_monotonic=None,
    )

    candidates = build_policy_candidate_set(already_defending_context)

    assert all(
        proposal.intent != ExecuteIntent(row_id=defense_row.row_id)
        for proposal in candidates.self_setup
    )
    assert all(
        proposal.intent != ExecuteIntent(row_id=disengage_row.row_id)
        for proposal in candidates.self_setup
    )


def test_shared_policy_attacks_adjacent_hostile_before_moderate_defense_loop() -> None:
    """Adjacent hostile pressure should not be prolonged by repeated Dodge loops."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    defense_semantics = ActionSemantics(
        semantic_id="defense.generic",
        tags=frozenset({ActionTag.DEFENSE_SELF}),
        guaranteed_effects=(LogicalEffect(
            fact_id="actor.condition.dodging",
            operation=EffectOperation.ADD,
            value=True,
        ),),
    )
    defense_ref = action_semantics_ref(defense_semantics)
    defense_row = ActionAffordance(
        row_id="self|localized-defense|index=0",
        bucket="self_actions",
        template_name="localized-defense",
        semantic_key="rules.defense.generic",
        display_name="Localized defensive label",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=[ActionTarget(index=0, target_uuid="actor")],
        semantic_id=defense_semantics.semantic_id,
        semantics_ref=defense_ref,
    )
    affordances = epoch.affordances.model_copy(update={
        "self_actions": [defense_row],
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            defense_ref: defense_semantics,
        },
    })
    actor = world.known_entities["actor"].model_copy(update={
        "hp": 12,
        "normal_hp": 12,
        "max_hp": 44,
    })
    adjacent_enemy = world.known_entities["visible-enemy"].model_copy(update={
        "position": (1, 0),
        "hp": 3,
        "max_hp": 13,
    })
    engaged_world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            "actor": actor,
            "visible-enemy": adjacent_enemy,
        },
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=engaged_world,
        facts=derive_agent_facts(engaged_world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.goal is PolicyGoal.DIRECT_PRESSURE
    defense_proposal = next(
        proposal
        for proposal in evaluation.decision.candidates
        if proposal.intent == ExecuteIntent(row_id=defense_row.row_id)
    )
    components = {
        component.name: component
        for component in defense_proposal.utility_components
    }
    assert components["engaged_damage_opportunity_cost"].raw_value == pytest.approx(1.0)


def test_shared_policy_ranks_finite_item_buff_and_suppresses_observed_effect() -> None:
    """A typed finite buff competes with pressure and is not repeated while active."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    setup_semantics = ActionSemantics(
        semantic_id="setup.haste",
        tags=frozenset({
            ActionTag.SETUP_SELF,
            ActionTag.SUPPORT_BUFF,
            ActionTag.DEFENSE_SELF,
            ActionTag.RESOURCE_SPEND,
        }),
        guaranteed_effects=(LogicalEffect(
            fact_id="actor.condition.haste",
            operation=EffectOperation.ADD,
            value=True,
        ),),
        self_setup=SelfSetupSemantics(
            duration=SelfSetupDuration.UNTIL_REMOVED,
            active_condition_semantic_keys=frozenset({
                "rules.conditions.TypedHaste",
            }),
            maximum_duration_rounds=10,
            armor_class_bonus=2,
            movement_speed_multiplier=2.0,
            extra_actions_per_turn=1,
        ),
    )
    setup_ref = action_semantics_ref(setup_semantics)
    setup_row = ActionAffordance(
        row_id="self|opaque-buff|uuid=finite-buff",
        bucket="self_actions",
        template_name="opaque-buff",
        semantic_key="rules.setup.typed_buff",
        display_name="Localized item label",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(
            bonus_action_cost=1,
            item_charge_costs={"finite-buff": 1},
        ),
        targets=[ActionTarget(index=0, target_uuid="actor")],
        is_item_use=True,
        source_item_uuid="finite-buff",
        semantic_id=setup_semantics.semantic_id,
        semantics_ref=setup_ref,
    )
    affordances = epoch.affordances.model_copy(update={
        "self_actions": [setup_row],
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            setup_ref: setup_semantics,
        },
    })
    economy = epoch.economy.model_copy(update={
        "bonus_actions": 1,
        "item_charges": {"finite-buff": ResourcePool(current=1, max=1)},
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "affordances": affordances,
            "economy": economy,
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=setup_row.row_id)
    assert evaluation.decision.selected.goal is PolicyGoal.SELF_SETUP
    assert any(
        proposal.goal is PolicyGoal.DIRECT_PRESSURE
        for proposal in evaluation.decision.candidates
    )
    components = {
        component.name: component
        for component in evaluation.decision.selected.utility_components
    }
    assert components["extra_action_access"].contribution > 0
    assert components["armor_class_setup"].contribution > 0
    assert components["movement_speed_setup"].contribution > 0
    assert components["finite_item_charge_cost"].contribution < 0

    actor = world.known_entities["actor"].model_copy(update={
        "conditions": ["Haste"],
        "condition_semantic_keys": ["rules.conditions.TypedHaste"],
    })
    known_entities = dict(world.known_entities)
    known_entities[actor.uuid] = actor
    active_world = world.model_copy(update={"known_entities": known_entities})
    active_context = PolicyContext.model_construct(
        world=active_world,
        facts=derive_agent_facts(active_world).facts,
        deadline_monotonic=None,
    )

    active_evaluation = evaluate_default_policy(active_context, tuple())

    assert active_evaluation.decision is not None
    assert active_evaluation.decision.selected.intent != ExecuteIntent(row_id=setup_row.row_id)
    assert all(
        proposal.intent != ExecuteIntent(row_id=setup_row.row_id)
        for proposal in active_evaluation.decision.candidates
    )


def test_shared_policy_preserves_flexible_action_before_granted_attack_slot() -> None:
    """Equivalent attacks spend the narrower granted attack before a full action."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    semantics = ActionSemantics(
        semantic_id="damage.weapon.economy-test",
        tags=frozenset({ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}),
    )
    semantics_ref = action_semantics_ref(semantics)
    target = ActionTarget(
        index=0,
        target_uuid="visible-enemy",
        position=(2, 0),
    )
    profile = ActionOutcomeProfile(
        resolution=OutcomeResolution.ATTACK_ROLL,
        attack_bonus=7,
        damage_rolls=[
            DamageRollProfile(
                dice_count=1,
                die_size=8,
                flat_bonus=4,
                damage_type="slashing",
            )
        ],
    )
    action_row = ActionAffordance(
        row_id="entity|full-action-attack|uuid=visible-enemy",
        bucket="entity_actions",
        template_name="opaque-full-action",
        semantic_key="rules.damage.weapon",
        display_name="Opaque strike",
        action_category="attack",
        target_type="entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=[target],
        outcome_profile=profile,
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
    )
    granted_row = action_row.model_copy(
        update={
            "row_id": "entity|granted-attack|uuid=visible-enemy",
            "template_name": "opaque-granted-attack",
            "cost": ActionCostProfile(consumes_attack_slot=True),
        }
    )
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        entity_actions=[action_row, granted_row],
        semantic_catalog={semantics_ref: semantics},
    )
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "economy": epoch.economy.model_copy(update={
                "actions": 1,
                "extra_attacks": 1,
            }),
            "affordances": affordances,
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    ranked = UtilityArbiter().rank(direct_damage_candidates(context))

    assert ranked[0].intent == ExecuteIntent(row_id=granted_row.row_id)
    components = {
        component.name: component
        for component in ranked[0].utility_components
    }
    assert components["action_economy_opportunity_cost"].raw_value < 1.0


def test_shared_policy_explores_frontier_at_exact_movement_boundary() -> None:
    """No-contact policy spends legal movement equal to the remaining budget."""
    world, move_row, _jump_row = _exploration_choice_world()
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=move_row.row_id)
    assert evaluation.decision.selected.goal.value == "information_gathering"
    evidence = evaluation.decision.selected.evidence.exploration
    assert evidence is not None
    assert evidence.anchor_position == (6, 0)
    assert evidence.movement_cost == 30
    assert evidence.unknown_frontier_count > 0


def test_typed_facts_derive_same_turn_voluntary_navigation_history() -> None:
    """Navigation history comes from this actor's subjective voluntary movement."""
    world = _world().model_copy(update={
        "combat_logs": [
            {
                "entry_type": "turn_start",
                "source_uuid": "actor",
                "data": {
                    "entity_uuid": "actor",
                    "round_number": 1,
                    "turn_index": 0,
                },
            },
            {
                "entry_type": "movement",
                "source_uuid": "actor",
                "success": True,
                "data": {
                    "entity_uuid": "actor",
                    "start_position": [0, 0],
                    "end_position": [2, 0],
                    "path": [[0, 0], [1, 0], [2, 0]],
                },
            },
            {
                "entry_type": "movement",
                "source_uuid": "other-actor",
                "success": True,
                "data": {
                    "entity_uuid": "other-actor",
                    "start_position": [9, 9],
                    "end_position": [8, 9],
                    "path": [[9, 9], [8, 9]],
                },
            },
            {
                "entry_type": "movement",
                "source_uuid": "actor",
                "target_uuid": "actor",
                "success": True,
                "data": {
                    "type": "forced_movement",
                    "start_position": [2, 0],
                    "end_position": [3, 0],
                },
            },
            {
                "entry_type": "movement",
                "source_uuid": "actor",
                "success": True,
                "data": {
                    "entity_uuid": "actor",
                    "start_position": [2, 0],
                    "end_position": [2, 1],
                    "path": [[2, 0], [2, 1]],
                },
            },
        ],
    })

    navigation = derive_agent_facts(world).facts.navigation

    assert navigation.actor_uuid == "actor"
    assert navigation.round_number == 1
    assert navigation.turn_index == 0
    assert navigation.same_turn_path == ((0, 0), (1, 0), (2, 0), (2, 1))
    assert (3, 0) not in navigation.visited_positions
    assert (8, 9) not in navigation.visited_positions


def test_typed_navigation_history_resets_at_the_current_actor_turn() -> None:
    """A later matching turn start excludes paths retained from earlier turns."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "round_number": 2,
            "turn_index": 0,
        }),
        "combat_logs": [
            {
                "entry_type": "turn_start",
                "source_uuid": "actor",
                "data": {"entity_uuid": "actor", "round_number": 1, "turn_index": 0},
            },
            {
                "entry_type": "movement",
                "source_uuid": "actor",
                "success": True,
                "data": {"entity_uuid": "actor", "path": [[0, 0], [1, 0]]},
            },
            {
                "entry_type": "turn_start",
                "source_uuid": "actor",
                "data": {"entity_uuid": "actor", "round_number": 2, "turn_index": 0},
            },
            {
                "entry_type": "movement",
                "source_uuid": "actor",
                "success": True,
                "data": {"entity_uuid": "actor", "path": [[4, 0], [5, 0]]},
            },
        ],
    })

    navigation = derive_agent_facts(world).facts.navigation

    assert navigation.same_turn_path == ((4, 0), (5, 0))
    assert navigation.visited_positions == frozenset({(4, 0), (5, 0)})


def test_shared_frontier_policy_retains_revisit_when_it_is_the_only_option() -> None:
    """Turn history prevents oscillation without making backtracking illegal."""
    world, move_row, _jump_row = _exploration_choice_world()
    world = world.model_copy(update={
        "combat_logs": [
            {
                "entry_type": "turn_start",
                "source_uuid": "actor",
                "data": {"entity_uuid": "actor", "round_number": 1, "turn_index": 0},
            },
            {
                "entry_type": "movement",
                "source_uuid": "actor",
                "success": True,
                "data": {
                    "entity_uuid": "actor",
                    "path": [[0, 0], [6, 0], [0, 0]],
                },
            },
        ],
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=move_row.row_id)
    exploration = evaluation.decision.selected.evidence.exploration
    assert exploration is not None
    assert exploration.revisited_this_turn is True


def test_shared_policy_preserves_bonus_action_when_move_and_jump_reveal_same_frontier() -> None:
    """Equal information gain uses ordinary movement before a bonus-action jump."""
    world, move_row, jump_row = _exploration_choice_world()
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    proposals = candidate_module.exploration_candidates(context)
    ranked = UtilityArbiter().rank(proposals)

    assert {proposal.intent.row_id for proposal in ranked} == {  # type: ignore[union-attr]
        move_row.row_id,
        jump_row.row_id,
    }
    assert ranked[0].intent == ExecuteIntent(row_id=move_row.row_id)
    components = {
        component.name: component
        for component in ranked[0].utility_components
    }
    assert components["action_economy_opportunity_cost"].raw_value == 0.0


def test_shared_policy_does_not_treat_seen_tiles_as_unknown_frontier() -> None:
    """Retained seen tiles are accumulated knowledge, not new information."""
    world, _move_row, _jump_row = _exploration_choice_world()
    target_position = (6, 0)
    known_tiles = {
        f"{x},{y}": ObservationTileFact(
            key=f"{x},{y}",
            position=(x, y),
            knowledge_state=(
                KnowledgeState.VISIBLE
                if index == 0
                else KnowledgeState.SEEN
            ),
            walkable=True,
            walking_cost=5,
            is_hazardous=False,
        )
        for index, (x, y) in enumerate(
            (target_position[0] + dx, target_position[1] + dy)
            for dx, dy in candidate_module._FRONTIER_NEIGHBORS
        )
    }
    world = world.model_copy(update={"known_tiles": known_tiles})
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    proposals = candidate_module.exploration_candidates(context)

    assert proposals == tuple()


def test_shared_policy_does_not_treat_known_invalid_neighbors_as_frontier() -> None:
    """Explicit subjective map boundaries are not possible exploration gain."""
    world, _move_row, _jump_row = _exploration_choice_world()
    target_key = "6,0"
    target_tile = world.known_tiles[target_key]
    invalid_neighbors = {
        f"{dx},{dy}": "invalid"
        for dx, dy in candidate_module._FRONTIER_NEIGHBORS
    }
    bounded_target = ObservationTileFact.model_validate({
        **target_tile.model_dump(mode="python"),
        "adjacent_domain": invalid_neighbors,
    })
    world = world.model_copy(update={
        "known_tiles": {
            **world.known_tiles,
            target_key: bounded_target,
        },
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    proposals = candidate_module.exploration_candidates(context)

    assert proposals == tuple()


def test_world_effect_information_gain_competes_with_movement_and_upcasts() -> None:
    """Typed projected gain can justify Daylight while lower identical slots win."""
    world, move_row, daylight_low, daylight_high, conceal_row = (
        _world_effect_exploration_choice_world()
    )
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    ranked = UtilityArbiter().rank(candidate_module.exploration_candidates(context))

    row_ids = [proposal.intent.row_id for proposal in ranked]  # type: ignore[union-attr]
    assert row_ids[0] == daylight_low.row_id
    assert row_ids.index(daylight_low.row_id) < row_ids.index(daylight_high.row_id)
    assert move_row.row_id in row_ids
    assert conceal_row.row_id not in row_ids
    evidence = ranked[0].evidence.exploration
    assert evidence is not None
    assert InformationOperation.REVEAL_REGION in evidence.information_operations
    assert evidence.projected_unknown_position_count > 0
    assert evidence.effect_radius_feet == 30
    assert evidence.limited_resource_cost == 3


def test_world_effect_information_suppresses_fully_known_bright_scope() -> None:
    """Illumination and movement add no information inside accumulated bright facts."""
    world, _move_row, _daylight_low, _daylight_high, _conceal_row = (
        _world_effect_exploration_choice_world()
    )
    known_tiles = {
        f"{x},{y}": ObservationTileFact(
            key=f"{x},{y}",
            position=(x, y),
            knowledge_state=KnowledgeState.SEEN,
            walkable=True,
            walking_cost=5,
            is_hazardous=False,
            light_level=3,
        )
        for x in range(-4, 11)
        for y in range(-6, 7)
    }
    world = world.model_copy(update={"known_tiles": known_tiles})
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    assert candidate_module.exploration_candidates(context) == tuple()


def test_world_effect_information_suppresses_an_already_active_sense() -> None:
    """A typed sense grant is useful once and redundant while already observed."""
    world, _move_row, _daylight_low, _daylight_high, _conceal_row = (
        _world_effect_exploration_choice_world()
    )
    epoch = world.current_epoch
    assert epoch is not None
    sense_semantics = ActionSemantics(
        semantic_id="information.opaque_sense",
        tags=frozenset({ActionTag.INFORMATION_REVEAL}),
        information_effects=(
            InformationEffect(
                operation=InformationOperation.GRANT_SENSE,
                certainty=EffectCertainty.GUARANTEED,
                anchor=WorldEffectAnchor.ACTOR,
                scope=WorldEffectScope.TARGET,
                scope_ref="actor.target",
                shape=WorldEffectShape.SPHERE,
                radius_feet=0,
                sense_type="see_invisible",
            ),
            InformationEffect(
                operation=InformationOperation.REVEAL_REGION,
                certainty=EffectCertainty.CONDITIONAL,
                anchor=WorldEffectAnchor.ACTOR,
                scope=WorldEffectScope.REGION,
                scope_ref="actor.region",
                shape=WorldEffectShape.SPHERE,
                radius_feet=0,
            ),
        ),
    )
    sense_ref = action_semantics_ref(sense_semantics)
    sense_row = ActionAffordance(
        row_id="self|opaque-sense|index=0",
        bucket="self_actions",
        template_name="opaque-sense",
        semantic_key="rules.information.opaque_sense",
        display_name="Localized sense label",
        action_category="spell",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1, spell_slot_cost=2),
        targets=[ActionTarget(index=0, target_uuid="actor", position=(0, 0))],
        semantic_id=sense_semantics.semantic_id,
        semantics_ref=sense_ref,
    )
    bright_tiles = {
        f"{x},{y}": ObservationTileFact(
            key=f"{x},{y}",
            position=(x, y),
            knowledge_state=KnowledgeState.SEEN,
            walkable=True,
            walking_cost=5,
            light_level=3,
        )
        for x in range(-1, 2)
        for y in range(-1, 2)
    }
    base_observer = ObservationObserverState(
        observer_uuid="actor",
        entity_name="Sorcerer",
        position=(0, 0),
        passive_perception=10,
        sense_modes=[],
    )
    sense_world = world.model_copy(update={
        "known_tiles": bright_tiles,
        "observers": {"actor": base_observer},
        "current_epoch": epoch.model_copy(update={
            "affordances": AffordanceSet(
                actor_uuid=epoch.actor_uuid,
                computed_at_observation_cursor=epoch.basis_observation_cursor,
                self_actions=[sense_row],
                semantic_catalog={sense_ref: sense_semantics},
            ),
        }),
    })

    useful_context = PolicyContext.model_construct(
        world=sense_world,
        facts=derive_agent_facts(sense_world).facts,
        deadline_monotonic=None,
    )
    useful = candidate_module.exploration_candidates(useful_context)
    assert [proposal.intent.row_id for proposal in useful] == [sense_row.row_id]  # type: ignore[union-attr]
    evidence = useful[0].evidence.exploration
    assert evidence is not None
    assert evidence.granted_sense_types == ("see_invisible",)

    active_observer = base_observer.model_copy(update={
        "sense_modes": [{"sense_type": "see_invisible", "range_feet": 0}],
    })
    active_world = sense_world.model_copy(update={"observers": {"actor": active_observer}})
    active_context = PolicyContext.model_construct(
        world=active_world,
        facts=derive_agent_facts(active_world).facts,
        deadline_monotonic=None,
    )
    assert candidate_module.exploration_candidates(active_context) == tuple()


def test_shared_policy_ends_turn_when_no_tactical_or_information_action_exists() -> None:
    """The shared hierarchy owns its legal terminal fallback without legacy policy."""
    world, _move_row, _jump_row = _exploration_choice_world()
    epoch = world.current_epoch
    assert epoch is not None
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "affordances": AffordanceSet(
                actor_uuid=epoch.actor_uuid,
                computed_at_observation_cursor=epoch.basis_observation_cursor,
            ),
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent.kind == "end_turn"
    assert evaluation.decision.selected.goal.value == "end_turn"


@pytest.mark.parametrize("can_afford", [True, False])
def test_shared_policy_terminal_fallback_is_total_for_unknown_actions(can_afford: bool) -> None:
    """Opaque rows cannot suppress the terminal fallback after tactical branches fail."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    opaque_row = ActionAffordance(
        row_id="entity|opaque-action|uuid=visible-enemy",
        bucket="entity_actions",
        template_name="Opaque Action",
        display_name="Opaque Action",
        action_category="spell",
        target_type="entity",
        can_afford=can_afford,
        cost=ActionCostProfile(action_cost=1),
        targets=[ActionTarget(index=0, target_uuid="visible-enemy")],
    )
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={
            "affordances": AffordanceSet(
                actor_uuid=epoch.actor_uuid,
                computed_at_observation_cursor=epoch.basis_observation_cursor,
                entity_actions=[opaque_row],
            ),
        }),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    evaluation = evaluate_default_policy(context, tuple())

    assert evaluation.decision is not None
    assert isinstance(evaluation.decision.selected.intent, EndTurnIntent)
    assert evaluation.decision.selected.goal is PolicyGoal.END_TURN
    assert evaluation.unavailable_reason is None


def test_direct_damage_candidates_collapse_equivalent_flattened_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Policy candidates retain choices, not duplicate AoE aim positions."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    semantics = ActionSemantics(
        semantic_id="damage.area",
        tags=frozenset({ActionTag.DAMAGE_AREA}),
    )
    semantics_ref = action_semantics_ref(semantics)
    rows = [
        ActionAffordance(
            row_id=f"position|Burst|pos={x},0",
            bucket="position_actions",
            template_name="Burst",
            semantic_key="spell.burst",
            display_name="Burst",
            action_category="spell",
            target_type="position_aoe",
            can_afford=True,
            cost=ActionCostProfile(action_cost=1, spell_slot_cost=2),
            targets=[
                ActionTarget(
                    index=x,
                    position=(x, 0),
                    affected_entity_uuids=["visible-enemy"],
                )
            ],
            outcome_profile=ActionOutcomeProfile(
                resolution=OutcomeResolution.SAVING_THROW,
                application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
                damage_rolls=[
                    DamageRollProfile(
                        dice_count=2,
                        die_size=6,
                        damage_type="fire",
                    )
                ],
                half_damage_on_save=True,
            ),
            semantic_id=semantics.semantic_id,
            semantics_ref=semantics_ref,
        )
        for x in range(1, 21)
    ]
    affordances = epoch.affordances.model_copy(
        update={
            "entity_actions": [],
            "position_actions": rows,
            "semantic_catalog": {semantics_ref: semantics},
        }
    )
    world = world.model_copy(
        update={"current_epoch": epoch.model_copy(update={"affordances": affordances})}
    )
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    target_plan_calls = 0
    original_target_plan = candidate_module._target_plan_evidence

    def count_target_plans(
        context: PolicyContext,
        row: ActionAffordance,
        *,
        additional_targets: tuple[str, ...],
        hostile_affected: tuple[str, ...],
        controlled_affected: tuple[str, ...],
        allied_affected: tuple[str, ...] = tuple(),
        applications: tuple[TargetApplicationEvidence, ...] = tuple(),
    ) -> TargetPlanEvidence:
        nonlocal target_plan_calls
        target_plan_calls += 1
        return original_target_plan(
            context,
            row,
            additional_targets=additional_targets,
            hostile_affected=hostile_affected,
            controlled_affected=controlled_affected,
            allied_affected=allied_affected,
            applications=applications,
        )

    monkeypatch.setattr(candidate_module, "_target_plan_evidence", count_target_plans)

    proposals = direct_damage_candidates(context)

    assert len(proposals) == 1
    assert proposals[0].intent.row_id == "position|Burst|pos=1,0"  # type: ignore[union-attr]
    components = {
        component.name: component
        for component in proposals[0].utility_components
    }
    assert components["equivalent_legal_rows"].raw_value == 20
    assert components["equivalent_legal_rows"].contribution == 0
    assert target_plan_calls == 1


def test_unknown_damage_profile_still_collapses_typed_transient_area_aims() -> None:
    """Unknown damage magnitude does not make equivalent aim coordinates distinct."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    semantics = ActionSemantics(
        semantic_id="damage.area.unknown-outcome",
        tags=frozenset({ActionTag.DAMAGE_AREA}),
        targeting=TargetingSemantics(allocation=TargetAllocation.AREA),
    )
    semantics_ref = action_semantics_ref(semantics)
    rows = tuple(
        ActionAffordance(
            row_id=f"position|Unknown Burst|pos={x},0",
            bucket="position_actions",
            template_name="Unknown Burst",
            semantic_key="spell.unknown-burst",
            display_name="Unknown Burst",
            action_category="spell",
            target_type="position_aoe",
            can_afford=True,
            cost=ActionCostProfile(action_cost=1),
            targets=[ActionTarget(
                index=x,
                position=(x, 0),
                affected_entity_uuids=["visible-enemy"],
            )],
            outcome_profile=None,
            semantic_id=semantics.semantic_id,
            semantics_ref=semantics_ref,
        )
        for x in (1, 2)
    )
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": tuple(),
        "position_actions": rows,
        "semantic_catalog": {semantics_ref: semantics},
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    assert candidate_module._supports_transient_monotonic_area_damage(
        rows[0],
        semantics,
        semantics.tags,
    )
    proposals = direct_damage_candidates(context)

    assert len(proposals) == 1
    assert proposals[0].intent == ExecuteIntent(
        row_id="position|Unknown Burst|pos=1,0"
    )
    assert proposals[0].evidence.damage_outcomes == ()


def test_control_candidates_collapse_equivalent_area_aim_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Equivalent legal aim cells produce one policy-distinct control choice."""
    world, control_row, _damage_row = _control_choice_world(concentrating=False)
    epoch = world.current_epoch
    assert epoch is not None
    rows = [
        control_row.model_copy(update={
            "row_id": f"position|opaque-control|pos={x},0",
            "bucket": "position_actions",
            "target_type": "position_aoe",
            "source_action_id": "opaque-control-source",
            "targets": [ActionTarget(
                index=x,
                position=(x, 0),
                affected_entity_uuids=["visible-enemy"],
            )],
        })
        for x in range(1, 21)
    ]
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": tuple(),
        "position_actions": rows,
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )
    target_plan_calls = 0
    original_target_plan = candidate_module._target_plan_evidence

    def count_target_plans(*args: object, **kwargs: object) -> TargetPlanEvidence:
        nonlocal target_plan_calls
        target_plan_calls += 1
        return original_target_plan(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(candidate_module, "_target_plan_evidence", count_target_plans)

    proposals = control_candidates(context)

    assert len(proposals) == 1
    assert proposals[0].intent == ExecuteIntent(
        row_id="position|opaque-control|pos=1,0"
    )
    components = {
        component.name: component
        for component in proposals[0].utility_components
    }
    assert components["equivalent_legal_rows"].raw_value == 20
    assert components["equivalent_legal_rows"].contribution == 0
    assert target_plan_calls == 1


def test_control_candidates_prune_dominated_transient_area_aims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transient control keeps the best hostile/friendly affected-set frontier."""
    world, control_row, _damage_row = _control_choice_world(concentrating=False)
    epoch = world.current_epoch
    assert epoch is not None
    second_enemy = world.known_entities["remembered-enemy"].model_copy(update={
        "knowledge_state": KnowledgeState.VISIBLE,
        "position": (3, 0),
    })
    entities = dict(world.known_entities)
    entities[second_enemy.uuid] = second_enemy
    rows = (
        control_row.model_copy(update={
            "row_id": "position|control|pos=1,0",
            "bucket": "position_actions",
            "target_type": "position_aoe",
            "source_action_id": "transient-control-source",
            "targets": [ActionTarget(
                index=0,
                position=(1, 0),
                affected_entity_uuids=["visible-enemy"],
            )],
        }),
        control_row.model_copy(update={
            "row_id": "position|control|pos=2,0",
            "bucket": "position_actions",
            "target_type": "position_aoe",
            "source_action_id": "transient-control-source",
            "targets": [ActionTarget(
                index=1,
                position=(2, 0),
                affected_entity_uuids=["visible-enemy", "remembered-enemy"],
            )],
        }),
        control_row.model_copy(update={
            "row_id": "position|control|pos=3,0",
            "bucket": "position_actions",
            "target_type": "position_aoe",
            "source_action_id": "transient-control-source",
            "targets": [ActionTarget(
                index=2,
                position=(3, 0),
                affected_entity_uuids=[
                    "actor",
                    "visible-enemy",
                    "remembered-enemy",
                ],
            )],
        }),
    )
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": tuple(),
        "position_actions": rows,
    })
    world = world.model_copy(update={
        "known_entities": entities,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )
    target_plan_calls = 0
    original_target_plan = candidate_module._target_plan_evidence

    def count_target_plans(*args: object, **kwargs: object) -> TargetPlanEvidence:
        nonlocal target_plan_calls
        target_plan_calls += 1
        return original_target_plan(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(candidate_module, "_target_plan_evidence", count_target_plans)

    proposals = control_candidates(context)

    assert len(proposals) == 1
    assert proposals[0].intent == ExecuteIntent(row_id="position|control|pos=2,0")
    assert proposals[0].evidence.target_plan is not None
    assert proposals[0].evidence.target_plan.hostile_entity_uuids == (
        "visible-enemy",
        "remembered-enemy",
    )
    assert proposals[0].evidence.target_plan.controlled_entity_uuids == ()
    assert target_plan_calls == 1


def test_control_candidates_prune_costlier_identical_control_variants() -> None:
    """An identical control effect keeps the lower-cost executable variant."""
    world, control_row, _damage_row = _control_choice_world(concentrating=False)
    epoch = world.current_epoch
    assert epoch is not None
    lower_cost = control_row.model_copy(update={
        "row_id": "entity|control-low|uuid=visible-enemy",
        "source_action_id": "control-low-source",
        "cost": control_row.cost.model_copy(update={"spell_slot_cost": 2}),
    })
    higher_cost = control_row.model_copy(update={
        "row_id": "entity|control-high|uuid=visible-enemy",
        "source_action_id": "control-high-source",
        "cost": control_row.cost.model_copy(update={"spell_slot_cost": 4}),
    })
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": (higher_cost, lower_cost),
        "position_actions": tuple(),
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    proposals = control_candidates(context)

    assert tuple(proposal.intent for proposal in proposals) == (
        ExecuteIntent(row_id=lower_cost.row_id),
    )


def test_control_candidates_preserve_persistent_zone_aim_rows() -> None:
    """Different persistent-zone anchors remain policy-distinct choices."""
    zone_semantics = ActionSemantics(
        semantic_id="control.persistent-zone.test",
        tags=frozenset({ActionTag.CONTROL_HARD, ActionTag.ZONE_PERSISTENT}),
    )
    world, control_row, _damage_row = _control_choice_world(
        concentrating=False,
        control_semantics=zone_semantics,
    )
    epoch = world.current_epoch
    assert epoch is not None
    rows = [
        control_row.model_copy(update={
            "row_id": f"position|opaque-zone|pos={x},0",
            "bucket": "position_actions",
            "target_type": "position_aoe",
            "source_action_id": "opaque-zone-source",
            "targets": [ActionTarget(
                index=x,
                position=(x, 0),
                affected_entity_uuids=["visible-enemy"],
            )],
        })
        for x in (1, 2)
    ]
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": tuple(),
        "position_actions": rows,
    })
    world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    proposals = control_candidates(context)

    assert len(proposals) == 2
    assert {
        context.facts.affordances.by_id[proposal.intent.row_id].targets[0].position
        for proposal in proposals
        if isinstance(proposal.intent, ExecuteIntent)
    } == {(1, 0), (2, 0)}


def test_control_representative_ignores_opaque_row_order() -> None:
    """Equivalent control geometry is stable when opaque row labels change."""

    def selected_position(
        labeled_positions: tuple[tuple[str, tuple[int, int]], ...],
    ) -> tuple[int, int] | None:
        world, control_row, _damage_row = _control_choice_world(concentrating=False)
        epoch = world.current_epoch
        assert epoch is not None
        rows = [
            control_row.model_copy(update={
                "row_id": row_id,
                "bucket": "position_actions",
                "target_type": "position_aoe",
                "source_action_id": "opaque-control-source",
                "targets": [ActionTarget(
                    index=index,
                    position=position,
                    affected_entity_uuids=["visible-enemy"],
                )],
            })
            for index, (row_id, position) in enumerate(labeled_positions)
        ]
        affordances = epoch.affordances.model_copy(update={
            "entity_actions": tuple(),
            "position_actions": rows,
        })
        world = world.model_copy(update={
            "current_epoch": epoch.model_copy(update={"affordances": affordances}),
        })
        context = PolicyContext.model_construct(
            world=world,
            facts=derive_agent_facts(world).facts,
            deadline_monotonic=None,
        )

        proposals = control_candidates(context)

        assert len(proposals) == 1
        intent = proposals[0].intent
        assert isinstance(intent, ExecuteIntent)
        return context.facts.affordances.by_id[intent.row_id].targets[0].position

    first = selected_position((
        ("opaque-z", (1, 0)),
        ("opaque-a", (2, 0)),
    ))
    second = selected_position((
        ("opaque-a", (1, 0)),
        ("opaque-z", (2, 0)),
    ))

    assert first == second == (1, 0)


def test_shared_policy_allocates_conditional_effects_across_allies_and_hostiles() -> None:
    """One typed mixed-effect row buffs eligible allies and controls enemies."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    undead = FactExpression(
        operator=FactOperator.PREDICATE,
        predicate=FactPredicate(
            fact_id="selected_target.creature_type",
            comparison=ComparisonOperator.EQUALS,
            expected_value="undead",
        ),
    )
    living = FactExpression(
        operator=FactOperator.PREDICATE,
        predicate=FactPredicate(
            fact_id="selected_target.creature_type",
            comparison=ComparisonOperator.NOT_EQUALS,
            expected_value="undead",
        ),
    )
    semantics = ActionSemantics(
        semantic_id="spell.opaque_mixed_effect",
        tags=frozenset({
            ActionTag.SUPPORT_BUFF,
            ActionTag.CONTROL_SOFT,
            ActionTag.TARGET_MULTI,
            ActionTag.CONCENTRATION_START,
        }),
        target_effects=(
            TargetEffectSemantics(
                effect_id="support.undead_buff",
                disposition=EffectDisposition.BENEFICIAL,
                applicability=undead,
                outcome_kind=OutcomeKind.GUARANTEED,
                effects=(LogicalEffect(
                    fact_id="selected_target.condition.bless",
                    operation=EffectOperation.ADD,
                    value=True,
                ),),
                condition_semantic_keys=frozenset({"rules.conditions.Bless"}),
            ),
            TargetEffectSemantics(
                effect_id="control.living_debuff",
                disposition=EffectDisposition.HARMFUL,
                applicability=living,
                outcome_kind=OutcomeKind.SAVING_THROW,
                save_ability="charisma",
                save_dc=14,
                effects=(LogicalEffect(
                    fact_id="selected_target.condition.bane",
                    operation=EffectOperation.ADD,
                    value=True,
                ),),
                condition_semantic_keys=frozenset({"rules.conditions.Bane"}),
            ),
        ),
    )
    semantics_ref = action_semantics_ref(semantics)
    options = [
        ActionTarget(index=0, target_uuid="visible-enemy", position=(2, 0)),
        ActionTarget(index=1, target_uuid="visible-ally", position=(1, 1)),
        ActionTarget(index=2, target_uuid="actor", position=(0, 0)),
    ]
    row = ActionAffordance(
        row_id="entity|opaque-mixed-effect|uuid=visible-enemy",
        source_action_id="entity_actions|source=opaque-mixed-effect",
        bucket="entity_actions",
        template_name="opaque-mixed-effect",
        semantic_key="rules.spells.OpaqueMixedEffect",
        display_name="Localized spell label",
        action_category="spell",
        target_type="multi_entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1, spell_slot_cost=2),
        targets=[options[0]],
        target_options=options,
        num_projectiles=4,
        allow_same_target=False,
        requires_concentration=True,
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
    )
    entities = dict(world.known_entities)
    entities["actor"] = entities["actor"].model_copy(update={
        "creature_type": "undead",
        "conditions": [],
        "is_concentrating": False,
    })
    entities["visible-ally"] = entities["visible-ally"].model_copy(update={"creature_type": "undead"})
    entities["visible-enemy"] = entities["visible-enemy"].model_copy(update={
        "creature_type": "humanoid",
        "hp": 30,
        "max_hp": 30,
    })
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": [*epoch.affordances.entity_actions, row],
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            semantics_ref: semantics,
        },
    })
    world = world.model_copy(update={
        "known_entities": entities,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext.model_construct(
        world=world,
        facts=derive_agent_facts(world).facts,
        deadline_monotonic=None,
    )

    assert context.facts.affordances.target_effect_row_ids == (row.row_id,)
    proposals = target_effect_candidates(context)
    evaluation = evaluate_default_policy(context, tuple())

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.intent == ExecuteIntent(
        row_id=row.row_id,
        extra_target_uuids=("actor", "visible-ally"),
    )
    assert proposal.evidence.target_plan is not None
    assert set(proposal.evidence.target_plan.selected_target_uuids) == {
        "visible-enemy",
        "visible-ally",
        "actor",
    }
    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == proposal.intent
    command = command_from_policy_decision(context, evaluation.decision)
    assert command is not None
    assert PolicyLogicalTag.SUPPORT_SETUP in command.logical_tags
    assert PolicyLogicalTag.CONTROL_EFFECT in command.logical_tags
    replacement = [
        component
        for component in proposal.utility_components
        if component.name == "concentration_replacement"
    ]
    assert len(replacement) == 1

    ally_row = row.model_copy(update={
        "row_id": "entity|opaque-mixed-effect|uuid=actor",
        "targets": [options[2]],
        "target_options": [options[1], options[2]],
    })
    ally_affordances = affordances.model_copy(update={"entity_actions": [ally_row]})
    ally_world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": ally_affordances}),
    })
    ally_context = PolicyContext.model_construct(
        world=ally_world,
        facts=derive_agent_facts(ally_world).facts,
        deadline_monotonic=None,
    )
    ally_evaluation = evaluate_default_policy(ally_context, tuple())
    assert ally_evaluation.decision is not None
    ally_command = command_from_policy_decision(
        ally_context,
        ally_evaluation.decision,
    )
    assert ally_command is not None
    assert PolicyLogicalTag.SUPPORT_SETUP in ally_command.logical_tags
    assert PolicyLogicalTag.CONTROL_EFFECT not in ally_command.logical_tags


def _world() -> SubjectiveWorldState:
    """Build one compact subjective world with a current legal epoch."""
    semantics = ActionSemantics(
        semantic_id="spell.fire_bolt",
        tags=frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_SINGLE_TARGET}),
    )
    semantics_ref = action_semantics_ref(semantics)
    attack_row = ActionAffordance(
        row_id="entity|Fire Bolt|uuid=visible-enemy",
        bucket="entity_actions",
        template_name="Fire Bolt",
        semantic_key="spell.fire_bolt",
        display_name="Fire Bolt",
        action_category="spell",
        target_type="entity",
        can_afford=True,
        targets=[ActionTarget(index=0, target_uuid="visible-enemy", position=(2, 0))],
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
    )
    capability = ActionCapability(
        capability_id="spell.fire_bolt|entity",
        semantic_key="spell.fire_bolt",
        action_category="spell",
        target_type="entity",
        cost=ActionCostProfile(action_cost=1),
        range_type="Range",
        normal_range_feet=120,
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=5,
            damage_rolls=(DamageRollProfile(
                dice_count=1,
                die_size=10,
                damage_type="fire",
            ),),
        ),
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
        tags=sorted(tag.value for tag in semantics.tags),
    )
    affordances = AffordanceSet(
        actor_uuid="actor",
        computed_at_observation_cursor=5,
        entity_actions=[attack_row],
        capabilities=[capability],
        semantic_catalog={semantics_ref: semantics},
    )
    epoch = DecisionEpoch(
        epoch_id="epoch-1",
        epoch_index=1,
        basis_observation_cursor=5,
        reason=DecisionEpochReason.TURN_START,
        actor_uuid="actor",
        round_number=1,
        turn_index=0,
        economy=ActionEconomyState(actor_uuid="actor", actions=1, movement_remaining=30),
        affordances=affordances,
    )
    entities = {
        "actor": ObservationEntityFact(
            uuid="actor",
            name="Sorcerer",
            knowledge_state=KnowledgeState.VISIBLE,
            controlled=True,
            position=(0, 0),
            hp=20,
            normal_hp=20,
            temporary_hp=0,
            max_hp=20,
            healing_blocked=False,
            conditions=["Concentrating"],
            condition_semantic_keys=["dnd.conditions.Concentrating"],
            is_concentrating=True,
            faction="heroes",
        ),
        "visible-ally": ObservationEntityFact(
            uuid="visible-ally",
            name="Friendly Fighter",
            knowledge_state=KnowledgeState.VISIBLE,
            position=(1, 1),
            hp=25,
            normal_hp=25,
            temporary_hp=0,
            max_hp=25,
            healing_blocked=False,
            faction="heroes",
        ),
        "visible-enemy": ObservationEntityFact(
            uuid="visible-enemy",
            name="Skeleton",
            knowledge_state=KnowledgeState.VISIBLE,
            position=(2, 0),
            hp=8,
            max_hp=13,
            ac=13,
            faction="monsters",
        ),
        "remembered-enemy": ObservationEntityFact(
            uuid="remembered-enemy",
            name="Skeleton Archer",
            knowledge_state=KnowledgeState.REMEMBERED,
            position=(5, 0),
            faction="monsters",
        ),
        "dead-enemy": ObservationEntityFact(
            uuid="dead-enemy",
            name="Defeated Skeleton",
            knowledge_state=KnowledgeState.REMEMBERED,
            position=(4, 0),
            is_dead=True,
        ),
        "unknown-enemy": ObservationEntityFact(
            uuid="unknown-enemy",
            name="Unknown combatant",
            knowledge_state=KnowledgeState.UNKNOWN,
            position=None,
        ),
    }
    objects = {
        "door": ObservationObjectFact(
            uuid="door",
            name="Oak Door",
            knowledge_state=KnowledgeState.VISIBLE,
            position=(1, 0),
            state={"is_open": False, "secret_engine_field": "discarded"},
        )
    }
    tiles = {
        "2,0": ObservationTileFact(
            key="2,0",
            position=(2, 0),
            knowledge_state=KnowledgeState.VISIBLE,
            walkable=True,
            walking_cost=10,
            is_hazardous=True,
        ),
        "3,0": ObservationTileFact(
            key="3,0",
            position=(3, 0),
            knowledge_state=KnowledgeState.VISIBLE,
            walkable=False,
            directional_blocks_movement={"west": True},
        ),
    }
    return SubjectiveWorldState(
        observation_cursor=5,
        session=ObservationSessionState(
            session_id="session",
            player_type="ai",
            name="AI",
            connection_status="connected",
            controlled_entity_uuids=["actor"],
            active_entity_uuid="actor",
            active_entity_name="Sorcerer",
            is_my_turn=True,
        ),
        known_entities=entities,
        known_objects=objects,
        known_tiles=tiles,
        current_epoch=epoch,
        epoch_cursor=1,
    )


def _control_choice_world(
    *,
    concentrating: bool,
    enemy_hp: int = 13,
    enemy_max_hp: int = 13,
    hard_control: bool = True,
    control_semantics: ActionSemantics | None = None,
    control_cost: ActionCostProfile | None = None,
    damage_cost: ActionCostProfile | None = None,
    damage_outcome_profile: ActionOutcomeProfile | None = None,
) -> tuple[SubjectiveWorldState, ActionAffordance, ActionAffordance]:
    """Build one semantic control-versus-pressure decision without name policy."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    control_semantics = control_semantics or ActionSemantics(
        semantic_id="control.hard.test",
        tags=frozenset({
            ActionTag.CONTROL_HARD if hard_control else ActionTag.CONTROL_SOFT,
            ActionTag.CONCENTRATION_START,
        }),
    )
    damage_semantics = ActionSemantics(
        semantic_id="damage.single.test",
        tags=frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_SINGLE_TARGET}),
    )
    control_ref = action_semantics_ref(control_semantics)
    damage_ref = action_semantics_ref(damage_semantics)
    target = ActionTarget(
        index=0,
        target_uuid="visible-enemy",
        position=(2, 0),
    )
    control_row = ActionAffordance(
        row_id="entity|semantic-hard-control|uuid=visible-enemy",
        bucket="entity_actions",
        template_name="opaque-control-row",
        semantic_key="rules.control.hard",
        display_name="Opaque control",
        action_category="spell",
        target_type="entity",
        can_afford=True,
        cost=control_cost or ActionCostProfile(action_cost=1, spell_slot_cost=2),
        targets=[target],
        requires_concentration=True,
        semantic_id=control_semantics.semantic_id,
        semantics_ref=control_ref,
    )
    damage_row = ActionAffordance(
        row_id="entity|semantic-pressure|uuid=visible-enemy",
        bucket="entity_actions",
        template_name="opaque-pressure-row",
        semantic_key="rules.damage.single",
        display_name="Opaque pressure",
        action_category="spell",
        target_type="entity",
        can_afford=True,
        cost=damage_cost or ActionCostProfile(action_cost=1),
        targets=[target],
        outcome_profile=damage_outcome_profile,
        semantic_id=damage_semantics.semantic_id,
        semantics_ref=damage_ref,
    )
    actor = world.known_entities["actor"].model_copy(
        update={
            "conditions": ["Concentrating"] if concentrating else [],
            "is_concentrating": concentrating,
        }
    )
    enemy = world.known_entities["visible-enemy"].model_copy(
        update={"hp": enemy_hp, "max_hp": enemy_max_hp, "ac": 13}
    )
    entities = dict(world.known_entities)
    entities[actor.uuid] = actor
    entities[enemy.uuid] = enemy
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        entity_actions=[control_row, damage_row],
        semantic_catalog={
            control_ref: control_semantics,
            damage_ref: damage_semantics,
        },
    )
    return (
        world.model_copy(
            update={
                "known_entities": entities,
                "current_epoch": epoch.model_copy(update={"affordances": affordances}),
            }
        ),
        control_row,
        damage_row,
    )


def _with_damage_ending_control(
    entity: ObservationEntityFact,
    *,
    applied_source_event_cursor: int,
) -> ObservationEntityFact:
    """Attach one opaque typed damage-ending full-agency control fact."""
    semantic_key = "rules.condition.opaque_damage_ending_control"
    return entity.model_copy(update={
        "conditions": [*entity.conditions, "Opaque Control"],
        "condition_semantic_keys": [
            *(entity.condition_semantic_keys or []),
            semantic_key,
        ],
        "condition_facts": [
            *(entity.condition_facts or []),
            ObservationConditionFact(
                semantic_key=semantic_key,
                removal_triggers=[ConditionRemovalTrigger.POSITIVE_DAMAGE_APPLIED],
                agency_denial=ConditionAgencyDenial.FULL_TURN,
                applied_source_event_cursor=applied_source_event_cursor,
            ),
        ],
    })


def _policy_encounter(
    *,
    turn_started_source_event_cursor: int,
) -> ObservationEncounterState:
    """Build the visible current-turn boundary used by control preservation."""
    return ObservationEncounterState(
        uuid="encounter",
        name="Policy Test Encounter",
        state="active",
        round_number=1,
        current_turn_index=0,
        current_entity_uuid="actor",
        current_entity_name="Sorcerer",
        turn_started_source_event_cursor=turn_started_source_event_cursor,
    )


def _spacing_choice_world(
    *,
    actor_name: str,
    enemy_position: tuple[int, int],
    reverse_rows: bool,
    controlled_ally_position: tuple[int, int] | None = None,
    movement_positions: tuple[tuple[int, int], ...] = ((-2, 0), (-4, 0)),
    normal_range_feet: int = 120,
) -> SubjectiveWorldState:
    """Build one spent ranged epoch with server-issued movement geometry."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    actor = world.known_entities["actor"].model_copy(
        update={"name": actor_name, "position": (0, 0)}
    )
    enemy = world.known_entities["visible-enemy"].model_copy(
        update={"position": enemy_position}
    )
    entities = dict(world.known_entities)
    entities[actor.uuid] = actor
    entities[enemy.uuid] = enemy
    controlled_entity_uuids = [actor.uuid]
    if controlled_ally_position is not None:
        controlled_ally = world.known_entities["visible-ally"].model_copy(update={
            "uuid": "controlled-ally",
            "name": "Controlled Ally",
            "position": controlled_ally_position,
            "controlled": True,
        })
        entities.pop("visible-ally", None)
        entities[controlled_ally.uuid] = controlled_ally
        controlled_entity_uuids.append(controlled_ally.uuid)
    movement_semantics = ActionSemantics(
        semantic_id="movement.opaque",
        tags=frozenset({ActionTag.MOVEMENT_VOLUNTARY}),
    )
    movement_ref = action_semantics_ref(movement_semantics)
    positions = list(movement_positions)
    rows = [
        ActionAffordance(
            row_id=f"position|opaque-move|pos={position[0]},{position[1]}",
            bucket="position_actions",
            template_name="opaque-move",
            semantic_key="rules.movement.opaque",
            display_name="Unclassified relocation",
            action_category="movement",
            target_type="position_path",
            can_afford=True,
            cost=ActionCostProfile(
                movement_cost=(abs(position[0]) + abs(position[1])) * 5,
            ),
            targets=[ActionTarget(
                index=index,
                position=position,
                path_cost=(abs(position[0]) + abs(position[1])) * 5,
                safe_path_cost=(abs(position[0]) + abs(position[1])) * 5,
            )],
            semantic_id=movement_semantics.semantic_id,
            semantics_ref=movement_ref,
        )
        for index, position in enumerate(positions)
    ]
    if reverse_rows:
        rows.reverse()
    prior_catalog = dict(epoch.affordances.semantic_catalog)
    prior_catalog[movement_ref] = movement_semantics
    capabilities = [
        capability.model_copy(update={"normal_range_feet": normal_range_feet})
        for capability in epoch.affordances.capabilities
    ]
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        position_actions=rows,
        capabilities=capabilities,
        semantic_catalog=prior_catalog,
    )
    spent_epoch = epoch.model_copy(update={
        "economy": epoch.economy.model_copy(update={
            "actions": 0,
            "extra_attacks": 0,
            "movement_remaining": 30,
            "meaningful_commands_remaining": True,
        }),
        "affordances": affordances,
    })
    return world.model_copy(update={
        "session": world.session.model_copy(update={
            "controlled_entity_uuids": controlled_entity_uuids,
        }),
        "known_entities": entities,
        "current_epoch": spent_epoch,
    })


def _exploration_choice_world(
) -> tuple[SubjectiveWorldState, ActionAffordance, ActionAffordance]:
    """Build no-contact frontier rows with equal geometry and different economy."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    semantics = ActionSemantics(
        semantic_id="movement.frontier.test",
        tags=frozenset({
            ActionTag.MOVEMENT_VOLUNTARY,
            ActionTag.INFORMATION_EXPLORE,
            ActionTag.INFORMATION_REVEAL,
        }),
    )
    semantics_ref = action_semantics_ref(semantics)
    target = ActionTarget(
        index=0,
        position=(6, 0),
        path_cost=30,
        safe_path_cost=30,
        path=[(x, 0) for x in range(7)],
        safe_path=[(x, 0) for x in range(7)],
    )
    move_row = ActionAffordance(
        row_id="position|z-ordinary-move|pos=6,0",
        bucket="position_actions",
        template_name="opaque-ordinary-relocation",
        semantic_key="rules.movement.frontier",
        display_name="Relocate",
        action_category="movement",
        target_type="position_path",
        can_afford=True,
        cost=ActionCostProfile(movement_cost=30),
        targets=[target],
        semantic_id=semantics.semantic_id,
        semantics_ref=semantics_ref,
    )
    jump_row = move_row.model_copy(update={
        "row_id": "position|a-jump-like-move|pos=6,0",
        "template_name": "opaque-bonus-relocation",
        "cost": ActionCostProfile(bonus_action_cost=1, movement_cost=30),
    })
    actor = world.known_entities["actor"].model_copy(update={
        "position": (0, 0),
        "conditions": [],
        "is_concentrating": False,
    })
    known_tiles = {
        f"{x},0": ObservationTileFact(
            key=f"{x},0",
            position=(x, 0),
            knowledge_state=KnowledgeState.VISIBLE,
            walkable=True,
            walking_cost=5,
            is_hazardous=False,
            adjacent_domain=(
                {
                    offset: SpatialDomainKnowledge.UNKNOWN
                    for offset in AdjacentOffset
                }
                if x == 6
                else {}
            ),
        )
        for x in range(7)
    }
    affordances = AffordanceSet(
        actor_uuid=epoch.actor_uuid,
        computed_at_observation_cursor=epoch.basis_observation_cursor,
        position_actions=[jump_row, move_row],
        semantic_catalog={semantics_ref: semantics},
    )
    exploration_epoch = epoch.model_copy(update={
        "economy": epoch.economy.model_copy(update={
            "actions": 1,
            "bonus_actions": 1,
            "movement_remaining": 30,
        }),
        "affordances": affordances,
    })
    return (
        world.model_copy(update={
            "known_entities": {"actor": actor},
            "known_objects": {},
            "known_tiles": known_tiles,
            "current_epoch": exploration_epoch,
        }),
        move_row,
        jump_row,
    )


def _world_effect_exploration_choice_world() -> tuple[
    SubjectiveWorldState,
    ActionAffordance,
    ActionAffordance,
    ActionAffordance,
    ActionAffordance,
]:
    """Build typed illumination, concealment, and movement information choices."""
    world, move_row, _jump_row = _exploration_choice_world()
    world = world.model_copy(update={
        "known_tiles": {
            **world.known_tiles,
            "3,3": ObservationTileFact(
                key="3,3",
                position=(3, 3),
                knowledge_state=KnowledgeState.SEEN,
                walkable=True,
                walking_cost=5,
                is_hazardous=False,
                adjacent_domain={
                    offset: SpatialDomainKnowledge.UNKNOWN
                    for offset in AdjacentOffset
                },
            ),
        },
    })
    epoch = world.current_epoch
    assert epoch is not None
    daylight_semantics = ActionSemantics(
        semantic_id="information.opaque_daylight",
        tags=frozenset({ActionTag.INFORMATION_REVEAL}),
        information_effects=(
            InformationEffect(
                operation=InformationOperation.CHANGE_LIGHT,
                certainty=EffectCertainty.GUARANTEED,
                anchor=WorldEffectAnchor.SELECTED_POSITION,
                scope=WorldEffectScope.REGION,
                scope_ref="selected_position.region",
                shape=WorldEffectShape.SPHERE,
                radius_feet=30,
            ),
            InformationEffect(
                operation=InformationOperation.REVEAL_REGION,
                certainty=EffectCertainty.CONDITIONAL,
                anchor=WorldEffectAnchor.SELECTED_POSITION,
                scope=WorldEffectScope.REGION,
                scope_ref="selected_position.region",
                shape=WorldEffectShape.SPHERE,
                radius_feet=30,
            ),
        ),
    )
    conceal_semantics = ActionSemantics(
        semantic_id="control.opaque_concealment",
        tags=frozenset({ActionTag.CONTROL_SOFT}),
        information_effects=(InformationEffect(
            operation=InformationOperation.CONCEAL_REGION,
            certainty=EffectCertainty.GUARANTEED,
            anchor=WorldEffectAnchor.SELECTED_POSITION,
            scope=WorldEffectScope.REGION,
            scope_ref="selected_position.region",
            shape=WorldEffectShape.SPHERE,
            radius_feet=30,
        ),),
    )
    daylight_ref = action_semantics_ref(daylight_semantics)
    conceal_ref = action_semantics_ref(conceal_semantics)
    target = ActionTarget(index=0, position=(3, 0))
    daylight_low = ActionAffordance(
        row_id="position|opaque-daylight|slot=3|pos=3,0",
        bucket="position_actions",
        template_name="opaque-daylight",
        semantic_key="rules.information.opaque_daylight",
        display_name="Localized illumination label",
        action_category="spell",
        target_type="position",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1, spell_slot_cost=3),
        targets=[target],
        cast_at_level=3,
        semantic_id=daylight_semantics.semantic_id,
        semantics_ref=daylight_ref,
    )
    daylight_high = daylight_low.model_copy(update={
        "row_id": "position|opaque-daylight|slot=5|pos=3,0",
        "cost": ActionCostProfile(action_cost=1, spell_slot_cost=5),
        "cast_at_level": 5,
    })
    conceal_row = daylight_low.model_copy(update={
        "row_id": "position|opaque-concealment|pos=3,0",
        "template_name": "opaque-concealment",
        "semantic_key": "rules.control.opaque_concealment",
        "cost": ActionCostProfile(action_cost=1, spell_slot_cost=2),
        "cast_at_level": 2,
        "semantic_id": conceal_semantics.semantic_id,
        "semantics_ref": conceal_ref,
    })
    affordances = epoch.affordances.model_copy(update={
        "position_actions": [move_row, daylight_low, daylight_high, conceal_row],
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            daylight_ref: daylight_semantics,
            conceal_ref: conceal_semantics,
        },
    })
    return (
        world.model_copy(update={
            "current_epoch": epoch.model_copy(update={"affordances": affordances}),
        }),
        move_row,
        daylight_low,
        daylight_high,
        conceal_row,
    )
