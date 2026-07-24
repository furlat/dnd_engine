"""Focused regressions for the independently versioned current AI policy."""

from __future__ import annotations

from ai.knowledge import derive_agent_facts
from server.agent_protocol.observation import (
    ObservationConditionFact,
    ObservationEncounterState,
    ObservationEntityFact,
)
from ai.policy.contracts import (
    ExecuteIntent,
    PolicyContext,
    PolicyControlMemoryView,
    PolicyGoal,
    RememberedContactSearchState,
)
from ai.policy.default import evaluate_default_policy
from ai.policy.memory import RoutineProgress, SemanticActionGoal
from ai.policy.generations.current_candidate import (
    SemanticAdmissionStatus,
    audit_semantic_admission,
    build_current_candidate_set,
)
from ai.policy.generations.current_scoring import (
    SETUP_VALUE_HORIZON_TURNS,
    TacticalValueVector,
    scalarize_tactical_value,
)
from ai.policy.generations.registry import (
    BASELINE_GENERATION_ID,
    CANDIDATE_GENERATION_ID,
    EXPECTED_V31_BEHAVIOR_SHA256,
    get_policy_implementation,
)
from ai.policy.routines import revalidate_active_routine
from server.agent_protocol.control import (
    ActionAffordance,
    ActionCapability,
    ActionCostProfile,
    ActionOutcomeProfile,
    ActionTarget,
    DamageRollProfile,
    OutcomeResolution,
)
from server.agent_protocol.semantics import (
    ActionSemantics,
    ActionTag,
    ComparisonOperator,
    ConcentrationEffect,
    ConcentrationOperation,
    EffectCertainty,
    EffectDisposition,
    EffectOperation,
    FactExpression,
    FactOperator,
    FactPredicate,
    InformationEffect,
    InformationOperation,
    LogicalEffect,
    ResourceEffect,
    ResourceOperation,
    StochasticEffect,
    OutcomeKind,
    TargetAllocation,
    TargetEffectSemantics,
    TargetingSemantics,
    SelfSetupDuration,
    SelfSetupSemantics,
    TopologyEffect,
    TopologyOperation,
    WorldEffectAnchor,
    WorldEffectScope,
    action_semantics_ref,
)
from dnd.core.condition_types import ConditionAgencyDenial
from tests.manual.test_44_typed_agent_policy import _world
from tests.manual.test_45_policy_routines import _context, _row


def test_candidate_generation_owns_builder_planner_and_hash() -> None:
    """Accepted and candidate generations execute different policy callables."""
    baseline = get_policy_implementation(BASELINE_GENERATION_ID)
    candidate = get_policy_implementation(CANDIDATE_GENERATION_ID)

    assert baseline.identity.implementation_sha256 == EXPECTED_V31_BEHAVIOR_SHA256
    assert baseline.build_candidates.__module__ == "ai.policy.candidates"
    assert baseline.plan_routines.__module__ == "ai.policy.routines"
    assert candidate.build_candidates.__module__ == "ai.policy.generations.current_candidate"
    assert candidate.plan_routines.__module__ == "ai.policy.generations.current_candidate"
    assert candidate.identity.implementation_sha256 != baseline.identity.implementation_sha256


def test_common_value_profile_scores_identical_vectors_identically() -> None:
    """Candidate source branches cannot invent incompatible score scales."""
    vector = TacticalValueVector(
        expected_enemy_hp_loss=7.5,
        enemy_defeat_probability=0.25,
        action_opportunity_cost=1.0,
        resource_expenditure=1.0,
    )

    first_score, first_components = scalarize_tactical_value(vector)
    second_score, second_components = scalarize_tactical_value(vector.model_copy())

    assert first_score == second_score
    assert first_components == second_components
    assert first_score == sum(component.contribution for component in first_components)


def test_candidate_rejects_healthy_dodge_without_disclosed_pressure() -> None:
    """A visible but non-adjacent enemy does not make Dodge dominate pressure."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    defense_row, defense_semantics = _defense_row()
    affordances = epoch.affordances.model_copy(update={
        "self_actions": (defense_row,),
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            defense_row.semantics_ref: defense_semantics,
        },
    })
    actor = world.known_entities["actor"].model_copy(update={
        "hp": 10,
        "normal_hp": 10,
        "max_hp": 20,
    })
    candidate_world = world.model_copy(update={
        "known_entities": {**world.known_entities, "actor": actor},
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext(world=candidate_world, facts=derive_agent_facts(candidate_world).facts)
    baseline = get_policy_implementation(BASELINE_GENERATION_ID)
    current = get_policy_implementation(CANDIDATE_GENERATION_ID)

    baseline_evaluation = baseline.evaluate(
        context,
        tuple(),
        baseline.build_candidates(context),
    )
    candidate_evaluation = current.evaluate(
        context,
        tuple(),
        current.build_candidates(context),
    )

    assert baseline_evaluation.decision is not None
    assert baseline_evaluation.decision.selected.intent == ExecuteIntent(row_id=defense_row.row_id)
    assert candidate_evaluation.decision is not None
    assert candidate_evaluation.decision.selected.goal is PolicyGoal.DIRECT_PRESSURE


def test_candidate_keeps_dodge_under_adjacent_low_hp_pressure() -> None:
    """Threat-aware defense remains available when disclosed survival pressure is real."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    defense_row, defense_semantics = _defense_row()
    affordances = epoch.affordances.model_copy(update={
        "self_actions": (defense_row,),
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            defense_row.semantics_ref: defense_semantics,
        },
    })
    actor = world.known_entities["actor"].model_copy(update={
        "hp": 2,
        "normal_hp": 2,
        "max_hp": 20,
    })
    enemy = world.known_entities["visible-enemy"].model_copy(update={"position": (1, 0)})
    pressured_world = world.model_copy(update={
        "known_entities": {
            **world.known_entities,
            "actor": actor,
            "visible-enemy": enemy,
        },
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext(world=pressured_world, facts=derive_agent_facts(pressured_world).facts)
    implementation = get_policy_implementation(CANDIDATE_GENERATION_ID)

    evaluation = implementation.evaluate(
        context,
        tuple(),
        implementation.build_candidates(context),
    )

    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=defense_row.row_id)


def test_current_candidate_keeps_multi_target_effect_allocation_atomic() -> None:
    """A target-effect family remains one allocated command, not one-target fallbacks."""
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
    options = (
        ActionTarget(index=0, target_uuid="visible-enemy", position=(2, 0)),
        ActionTarget(index=1, target_uuid="visible-ally", position=(1, 1)),
        ActionTarget(index=2, target_uuid="actor", position=(0, 0)),
    )
    source_action_id = "entity_actions|source=opaque-mixed-effect"
    rows = tuple(
        ActionAffordance.model_validate({
            "row_id": f"entity|opaque-mixed-effect|uuid={target.target_uuid}",
            "source_action_id": source_action_id,
            "bucket": "entity_actions",
            "template_name": "opaque-mixed-effect",
            "semantic_key": "rules.spells.OpaqueMixedEffect",
            "display_name": "Localized spell label",
            "action_category": "spell",
            "target_type": "multi_entity",
            "can_afford": True,
            "cost": ActionCostProfile(action_cost=1, spell_slot_cost=2),
            "targets": (target,),
            "target_options": options,
            "num_projectiles": 4,
            "allow_same_target": False,
            "requires_concentration": True,
            "semantic_id": semantics.semantic_id,
            "semantics_ref": semantics_ref,
        })
        for target in options
    )
    entities = dict(world.known_entities)
    entities["actor"] = entities["actor"].model_copy(update={
        "creature_type": "undead",
        "conditions": [],
        "condition_semantic_keys": [],
        "is_concentrating": False,
    })
    entities["visible-ally"] = entities["visible-ally"].model_copy(update={
        "creature_type": "undead",
        "condition_semantic_keys": [],
    })
    entities["visible-enemy"] = entities["visible-enemy"].model_copy(update={
        "creature_type": "humanoid",
        "hp": 30,
        "max_hp": 30,
        "condition_semantic_keys": [],
    })
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": (*epoch.affordances.entity_actions, *rows),
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            semantics_ref: semantics,
        },
    })
    world = world.model_copy(update={
        "known_entities": entities,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext(world=world, facts=derive_agent_facts(world).facts)

    candidates = build_current_candidate_set(context)
    all_execute = tuple(
        proposal
        for proposal in (
            *candidates.control,
            *candidates.target_effects,
            *candidates.self_setup,
        )
        if isinstance(proposal.intent, ExecuteIntent)
    )

    allocated = [
        proposal
        for proposal in candidates.target_effects
        if proposal.intent == ExecuteIntent(
            row_id="entity|opaque-mixed-effect|uuid=visible-enemy",
            extra_target_uuids=("actor", "visible-ally"),
        )
    ]
    assert len(allocated) == 1
    assert allocated[0].reason == "apply_typed_conditional_target_effects"
    assert all(
        proposal.reason != "apply_typed_beneficial_state_or_resource_change"
        for proposal in all_execute
    )
    generic_target_effect_rows = {
        intent.row_id
        for reason, intent in (
            (proposal.reason, proposal.intent)
            for proposal in all_execute
        )
        if reason == "apply_typed_target_effect"
    }
    assert generic_target_effect_rows == set()


def test_persistent_zone_reaches_policy_arbitration_without_current_occupants() -> None:
    """A typed zone can compete by spatial effect instead of requiring leaked targets."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    zone_semantics = ActionSemantics(
        semantic_id="zone.typed.control",
        tags=frozenset({ActionTag.CONTROL_SOFT, ActionTag.ZONE_PERSISTENT, ActionTag.CONCENTRATION_START}),
        topology_effects=(TopologyEffect(
            operation=TopologyOperation.CREATE_HAZARD,
            certainty=EffectCertainty.GUARANTEED,
            anchor=WorldEffectAnchor.SELECTED_POSITION,
            scope=WorldEffectScope.REGION,
            subject_ref="zone.typed.control",
            radius_feet=10,
            shape="sphere",
            affects_movement=True,
            affects_hazards=True,
        ),),
        concentration_effect=ConcentrationEffect(
            operation=ConcentrationOperation.START_OR_REPLACE,
            spell_semantic_id="zone.typed.control",
        ),
    )
    zone_ref = action_semantics_ref(zone_semantics)
    zone_row = ActionAffordance(
        row_id="position|typed-zone|pos=2,0",
        bucket="position_actions",
        template_name="typed-zone",
        semantic_key="spell.typed_zone",
        display_name="Localized zone",
        action_category="spell",
        target_type="position_aoe",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1, spell_slot_cost=1),
        targets=(ActionTarget(index=0, position=(2, 0)),),
        requires_concentration=True,
        semantic_id=zone_semantics.semantic_id,
        semantics_ref=zone_ref,
    )
    actor = world.known_entities["actor"].model_copy(update={
        "conditions": [],
        "condition_semantic_keys": [],
        "is_concentrating": False,
    })
    affordances = epoch.affordances.model_copy(update={
        "position_actions": (zone_row,),
        "semantic_catalog": {**epoch.affordances.semantic_catalog, zone_ref: zone_semantics},
    })
    zone_world = world.model_copy(update={
        "known_entities": {**world.known_entities, "actor": actor},
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext(world=zone_world, facts=derive_agent_facts(zone_world).facts)

    candidates = build_current_candidate_set(context)
    admission = {record.row_id: record for record in audit_semantic_admission(context, candidates)}
    evaluation = evaluate_default_policy(context, tuple(), candidates)

    assert any(proposal.intent == ExecuteIntent(row_id=zone_row.row_id) for proposal in candidates.control)
    assert admission[zone_row.row_id].status is SemanticAdmissionStatus.ACTIONABLE
    assert evaluation.decision is not None
    assert evaluation.decision.selected.intent == ExecuteIntent(row_id=zone_row.row_id)


def test_search_exhaustion_suppresses_contact_but_preserves_novel_frontier() -> None:
    """An exhausted remembered contact no longer captures every exploration move."""
    move_row, move_semantics = _row(
        "position|Move|pos=2,0",
        "position_actions",
        "Move",
        "movement",
        "position",
        {ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_EXPLORE, ActionTag.INFORMATION_REVEAL},
        targets=[ActionTarget(index=0, position=(2, 0), path_cost=10)],
    )
    frontier_row = _row(
        "position|Move|pos=4,0",
        "position_actions",
        "Move",
        "movement",
        "position",
        {ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_EXPLORE, ActionTag.INFORMATION_REVEAL},
        targets=[ActionTarget(index=1, position=(4, 0), path_cost=20)],
    )
    base = _context([(move_row, move_semantics), frontier_row], door_open=True, epoch_index=1)
    remembered = ObservationEntityFact(
        uuid="hero",
        name="Remembered Hero",
        knowledge_state="remembered",
        position=(0, 0),
        faction="heroes",
    )
    world = base.world.model_copy(update={
        "known_entities": {**base.world.known_entities, "hero": remembered},
    })
    context = PolicyContext(
        world=world,
        facts=derive_agent_facts(world).facts,
        control_memory=PolicyControlMemoryView(remembered_contact_searches=(
            RememberedContactSearchState(
                entity_uuid="hero",
                last_known_position=(0, 0),
                completed_investigations=3,
                investigated_positions=((0, 0), (1, 0)),
            ),
        )),
    )

    candidates = build_current_candidate_set(context)

    assert all(
        proposal.evidence.exploration is None
        or proposal.evidence.exploration.remembered_target_uuid is None
        for proposal in candidates.exploration
    )
    assert any(
        proposal.evidence.exploration is not None
        and proposal.evidence.exploration.remembered_search_novelty_feet >= 10
        for proposal in candidates.exploration
    )


def test_new_concentration_is_not_replaced_again_in_same_turn() -> None:
    """A fresh concentration application blocks immediate churn until a later turn."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    control_semantics = ActionSemantics(
        semantic_id="control.second-concentration",
        tags=frozenset({ActionTag.CONTROL_HARD, ActionTag.CONCENTRATION_START}),
        concentration_effect=ConcentrationEffect(
            operation=ConcentrationOperation.START_OR_REPLACE,
            spell_semantic_id="control.second-concentration",
        ),
    )
    control_ref = action_semantics_ref(control_semantics)
    control_row = ActionAffordance(
        row_id="entity|second-control|uuid=visible-enemy",
        bucket="entity_actions",
        template_name="second-control",
        semantic_key="spell.second_control",
        display_name="Second control",
        action_category="spell",
        target_type="entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1, spell_slot_cost=1),
        targets=(ActionTarget(
            index=0,
            target_uuid="visible-enemy",
            position=(2, 0),
            affected_entity_uuids=("visible-enemy",),
        ),),
        requires_concentration=True,
        semantic_id=control_semantics.semantic_id,
        semantics_ref=control_ref,
    )
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": (*epoch.affordances.entity_actions, control_row),
        "semantic_catalog": {**epoch.affordances.semantic_catalog, control_ref: control_semantics},
    })
    actor = world.known_entities["actor"].model_copy(update={
        "condition_facts": (ObservationConditionFact(
            semantic_key="dnd.conditions.Concentrating",
            agency_denial=ConditionAgencyDenial.NONE,
            applied_source_event_cursor=11,
        ),),
    })
    encounter = ObservationEncounterState(
        uuid="encounter",
        name="Test",
        state="active",
        round_number=1,
        current_turn_index=0,
        current_entity_uuid="actor",
        current_entity_name="Actor",
        turn_started_source_event_cursor=10,
    )
    churn_world = world.model_copy(update={
        "known_entities": {**world.known_entities, "actor": actor},
        "encounter": encounter,
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext(world=churn_world, facts=derive_agent_facts(churn_world).facts)

    candidates = build_current_candidate_set(context)

    assert all(
        proposal.intent != ExecuteIntent(row_id=control_row.row_id)
        for proposal in (
            *candidates.direct_damage,
            *candidates.control,
            *candidates.target_effects,
            *candidates.self_setup,
        )
    )


def test_position_then_pressure_competes_with_immediate_weak_damage() -> None:
    """A bounded move can beat a legal weak attack when it enables stronger pressure."""
    weak_row, weak_semantics = _row(
        "entity|weak-pressure|uuid=hero",
        "entity_actions",
        "Weak pressure",
        "attack",
        "entity",
        {ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET},
        targets=[ActionTarget(index=0, target_uuid="hero", position=(4, 0))],
        cost=ActionCostProfile(action_cost=1),
    )
    weak_row = weak_row.model_copy(update={"outcome_profile": ActionOutcomeProfile(
        resolution=OutcomeResolution.ATTACK_ROLL,
        attack_bonus=5,
        damage_rolls=(DamageRollProfile(dice_count=1, die_size=4, damage_type="slashing"),),
    )})
    move_row, move_semantics = _row(
        "position|Move|pos=2,0",
        "position_actions",
        "Move",
        "movement",
        "position",
        {ActionTag.MOVEMENT_VOLUNTARY},
        targets=[ActionTarget(index=0, position=(2, 0), path_cost=10)],
    )
    strong_semantics = ActionSemantics(
        semantic_id="attack.strong.short-range",
        tags=frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_SINGLE_TARGET}),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.SINGLE_ENTITY,
            minimum_targets=1,
            maximum_targets=1,
        ),
    )
    strong_ref = action_semantics_ref(strong_semantics)
    strong_capability = ActionCapability(
        capability_id="attack.strong.short-range|entity",
        semantic_key="attack.strong.short-range",
        action_category="spell",
        target_type="entity",
        cost=ActionCostProfile(action_cost=1),
        range_type="Range",
        normal_range_feet=10,
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=5,
            damage_rolls=(DamageRollProfile(dice_count=3, die_size=10, damage_type="force"),),
        ),
        semantic_id=strong_semantics.semantic_id,
        semantics_ref=strong_ref,
        tags=tuple(tag.value for tag in strong_semantics.tags),
    )
    context = _context(
        [(weak_row, weak_semantics), (move_row, move_semantics)],
        visible_hostile=True,
        capabilities=[strong_capability],
        extra_semantics=[strong_semantics],
    )
    baseline = get_policy_implementation(BASELINE_GENERATION_ID)
    current = get_policy_implementation(CANDIDATE_GENERATION_ID)

    baseline_evaluation = baseline.evaluate(context, tuple(), baseline.build_candidates(context))
    candidate_candidates = current.build_candidates(context)
    candidate_plans = current.plan_routines(
        context,
        None,
        revalidate_active_routine(context, None, candidate_candidates),
        candidate_candidates,
    )
    candidate_evaluation = current.evaluate(context, candidate_plans, candidate_candidates)

    assert baseline_evaluation.decision is not None
    assert baseline_evaluation.decision.selected.intent == ExecuteIntent(row_id=weak_row.row_id)
    assert candidate_evaluation.decision is not None
    assert candidate_evaluation.decision.selected.intent == ExecuteIntent(row_id=move_row.row_id)
    assert (
        candidate_evaluation.decision.selected.reason
        == "move_once_then_revalidate_stronger_typed_pressure"
    )
    selected_plan = candidate_evaluation.selected_routine_plan
    assert selected_plan is not None
    progress = selected_plan.next_progress_on_success
    assert progress is not None
    assert progress.routine_id == "routine.enable_then_act"
    assert progress.goal is not None
    assert progress.goal.required_target_allocation is TargetAllocation.SINGLE_ENTITY
    assert progress.goal.minimum_selected_targets == 1
    assert selected_plan.proposal is not None
    components = {
        component.name: component
        for component in selected_plan.proposal.utility_components
    }
    assert components["action_opportunity_cost"].raw_value == 1.0

    strong_row, _ = _row(
        "entity|strong-pressure|uuid=hero",
        "entity_actions",
        "Strong pressure",
        "spell",
        "entity",
        {ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_SINGLE_TARGET},
        targets=[ActionTarget(index=0, target_uuid="hero", position=(4, 0))],
        cost=ActionCostProfile(action_cost=1),
    )
    strong_row = strong_row.model_copy(update={
        "semantic_id": strong_semantics.semantic_id,
        "semantics_ref": strong_ref,
        "outcome_profile": strong_capability.outcome_profile,
    })
    followup_context = _context(
        [(strong_row, strong_semantics), (move_row, move_semantics)],
        visible_hostile=True,
        capabilities=[strong_capability],
        extra_semantics=[strong_semantics],
        epoch_index=2,
    )
    followup_candidates = current.build_candidates(followup_context)
    followup_revalidation = revalidate_active_routine(
        followup_context,
        progress,
        followup_candidates,
    )
    followup_plans = current.plan_routines(
        followup_context,
        progress,
        followup_revalidation,
        followup_candidates,
    )
    followup_evaluation = current.evaluate(
        followup_context,
        followup_plans,
        followup_candidates,
    )

    assert followup_evaluation.decision is not None
    assert followup_evaluation.decision.selected.intent == ExecuteIntent(row_id=strong_row.row_id)
    followup_plan = followup_evaluation.selected_routine_plan
    assert followup_plan is not None
    assert followup_plan.clear_progress_on_success
    assert followup_plan.proposal is not None
    assert followup_plan.proposal.reason == "fresh legal row satisfies retained semantic goal"


def test_control_probability_changes_candidate_value() -> None:
    """Disclosed control probability changes value without action-name policy."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    rows: list[ActionAffordance] = []
    catalog = dict(epoch.affordances.semantic_catalog)
    for suffix, probability in (("low", 0.2), ("high", 0.8)):
        semantics = ActionSemantics(
            semantic_id=f"control.probability.{suffix}",
            tags=frozenset({ActionTag.CONTROL_HARD}),
            stochastic_effects=(StochasticEffect(
                outcome_kind=OutcomeKind.SAVING_THROW,
                probability=probability,
                effects=(LogicalEffect(
                    fact_id="selected_target.agency",
                    operation=EffectOperation.DECREASE,
                    value=1,
                ),),
            ),),
        )
        reference = action_semantics_ref(semantics)
        catalog[reference] = semantics
        rows.append(ActionAffordance(
            row_id=f"entity|control-{suffix}|uuid=visible-enemy",
            bucket="entity_actions",
            template_name=f"control-{suffix}",
            semantic_key=f"control.probability.{suffix}",
            display_name=f"Control {suffix}",
            action_category="spell",
            target_type="entity",
            can_afford=True,
            cost=ActionCostProfile(action_cost=1),
            targets=(ActionTarget(
                index=0,
                target_uuid="visible-enemy",
                position=(2, 0),
                affected_entity_uuids=("visible-enemy",),
            ),),
            semantic_id=semantics.semantic_id,
            semantics_ref=reference,
        ))
    affordances = epoch.affordances.model_copy(update={
        "entity_actions": tuple(rows),
        "semantic_catalog": catalog,
    })
    control_world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext(world=control_world, facts=derive_agent_facts(control_world).facts)

    proposals = build_current_candidate_set(context).control
    scores = {
        proposal.intent.row_id: proposal.score
        for proposal in proposals
        if isinstance(proposal.intent, ExecuteIntent)
    }

    assert scores[rows[1].row_id] > scores[rows[0].row_id]


def test_position_then_pressure_skips_capability_that_is_already_legal() -> None:
    """Legal pressure is not wrapped in a redundant movement precondition."""
    world = _world()
    epoch = world.current_epoch
    assert epoch is not None
    move_row, move_semantics = _row(
        "position|Move|pos=1,0",
        "position_actions",
        "Move",
        "movement",
        "position",
        {ActionTag.MOVEMENT_VOLUNTARY},
        targets=[ActionTarget(index=0, position=(1, 0), path_cost=5)],
    )
    affordances = epoch.affordances.model_copy(update={
        "position_actions": (move_row,),
        "semantic_catalog": {
            **epoch.affordances.semantic_catalog,
            move_row.semantics_ref: move_semantics,
        },
    })
    current_world = world.model_copy(update={
        "current_epoch": epoch.model_copy(update={"affordances": affordances}),
    })
    context = PolicyContext(world=current_world, facts=derive_agent_facts(current_world).facts)

    candidates = build_current_candidate_set(context)
    plans = get_policy_implementation(CANDIDATE_GENERATION_ID).plan_routines(
        context,
        None,
        revalidate_active_routine(context, None, candidates),
        candidates,
    )

    assert all(
        plan.proposal is None
        or plan.proposal.reason
        != "move_once_then_revalidate_stronger_typed_pressure"
        for plan in plans
    )


def test_door_topology_is_owned_by_dedicated_routines_not_generic_value() -> None:
    """Opening or closing a door requires a proved routine context."""
    row, _ = _row(
        "object|Close Door|uuid=door",
        "object_actions",
        "Close Door",
        "ability",
        "object",
        {ActionTag.INTERACTION_DOOR_CLOSE, ActionTag.INTERACTION_OBJECT},
        targets=[ActionTarget(index=0, target_uuid="door", position=(3, 0))],
    )
    semantics = ActionSemantics(
        semantic_id="interaction.door.close",
        tags=frozenset({ActionTag.INTERACTION_DOOR_CLOSE, ActionTag.INTERACTION_OBJECT}),
        topology_effects=(TopologyEffect(
            operation=TopologyOperation.CLOSE,
            certainty=EffectCertainty.GUARANTEED,
            anchor=WorldEffectAnchor.SELECTED_OBJECT,
            scope=WorldEffectScope.TARGET,
            subject_ref="selected.object",
            affects_movement=True,
            affects_vision=True,
        ),),
    )
    reference = action_semantics_ref(semantics)
    row = row.model_copy(update={
        "semantic_id": semantics.semantic_id,
        "semantics_ref": reference,
    })
    context = _context(
        [(row, semantics)],
        door_open=True,
        visible_hostile=True,
    )

    candidates = build_current_candidate_set(context)
    admission = {record.row_id: record for record in audit_semantic_admission(context, candidates)}

    assert all(
        not isinstance(proposal.intent, ExecuteIntent)
        or proposal.intent.row_id != row.row_id
        for proposal in (
            *candidates.control,
            *candidates.target_effects,
            *candidates.self_setup,
            *candidates.spacing,
            *candidates.exploration,
        )
    )
    assert admission[row.row_id].status is SemanticAdmissionStatus.CONDITIONALLY_ACTIONABLE



def test_voluntary_movement_is_not_admitted_as_generic_information_change() -> None:
    """Movement remains owned by spacing, exploration, and bounded routines."""
    row, semantics = _row(
        "position|Move|pos=4,0",
        "position_actions",
        "Move",
        "movement",
        "position",
        {
            ActionTag.MOVEMENT_VOLUNTARY,
            ActionTag.INFORMATION_EXPLORE,
            ActionTag.INFORMATION_REVEAL,
        },
        targets=[ActionTarget(index=0, position=(4, 0), path_cost=20)],
    )
    semantics = semantics.model_copy(update={
        "information_effects": (InformationEffect(
            operation=InformationOperation.REVEAL_FRONTIER,
            certainty=EffectCertainty.GUARANTEED,
            anchor=WorldEffectAnchor.SELECTED_POSITION,
            scope=WorldEffectScope.FRONTIER,
            scope_ref="subjective.frontier",
        ),),
    })
    reference = action_semantics_ref(semantics)
    row = row.model_copy(update={
        "semantic_id": semantics.semantic_id,
        "semantics_ref": reference,
    })
    context = _context([(row, semantics)], door_open=True)

    candidates = build_current_candidate_set(context)

    assert all(
        proposal.reason != "apply_typed_world_or_information_change"
        for proposal in candidates.exploration
    )



def test_typed_durable_bonus_attack_keeps_future_agency_value() -> None:
    """Durable bonus-attack access survives the common-value reduction."""
    scores: dict[bool, float] = {}
    action_values: dict[bool, float] = {}
    for grants_bonus_attack in (False, True):
        semantics = ActionSemantics(
            semantic_id=f"setup.generic.{grants_bonus_attack}",
            tags=frozenset({ActionTag.SETUP_SELF}),
            self_setup=SelfSetupSemantics(
                duration=SelfSetupDuration.UNTIL_REMOVED,
                grants_bonus_action_attack=grants_bonus_attack,
            ),
        )
        reference = action_semantics_ref(semantics)
        row = ActionAffordance(
            row_id=f"self|generic-setup-{grants_bonus_attack}|index=0",
            bucket="self_actions",
            template_name=f"generic-setup-{grants_bonus_attack}",
            semantic_key=f"setup.generic.{grants_bonus_attack}",
            display_name="Generic setup",
            action_category="ability",
            target_type="self",
            can_afford=True,
            cost=ActionCostProfile(
                bonus_action_cost=1,
                resource_costs={"generic_pool": 1},
            ),
            targets=(ActionTarget(index=0, target_uuid="actor"),),
            semantic_id=semantics.semantic_id,
            semantics_ref=reference,
        )
        context = _context([(row, semantics)], visible_hostile=True)
        proposal = build_current_candidate_set(context).self_setup[0]
        scores[grants_bonus_attack] = proposal.score
        action_values[grants_bonus_attack] = next(
            (
                component.raw_value
                for component in proposal.utility_components
                if component.name == "expected_actor_actions_preserved"
            ),
            0.0,
        )

    assert action_values[True] - action_values[False] == SETUP_VALUE_HORIZON_TURNS
    assert scores[True] - scores[False] == 70.0

def test_pursuit_uses_common_terminal_value_and_exact_goal() -> None:
    """Inherited pursuit competes through projected outcomes, not score 65."""
    context, move_row = _short_range_pressure_context(include_weak_attack=False)
    implementation = get_policy_implementation(CANDIDATE_GENERATION_ID)
    candidates = implementation.build_candidates(context)

    plans = implementation.plan_routines(
        context,
        None,
        revalidate_active_routine(context, None, candidates),
        candidates,
    )

    pursuit = next(
        plan
        for plan in plans
        if plan.routine_id == "routine.pursue_capability"
        and plan.proposal is not None
    )
    assert pursuit.proposal.intent == ExecuteIntent(row_id=move_row.row_id)
    assert pursuit.proposal.score != 65.0
    components = {
        component.name: component
        for component in pursuit.proposal.utility_components
    }
    assert components["expected_enemy_hp_loss"].raw_value > 0.0
    assert components["action_opportunity_cost"].raw_value == 1.0
    progress = pursuit.next_progress_on_success
    assert progress is not None
    assert progress.goal is not None
    assert progress.goal.required_target_allocation is TargetAllocation.SINGLE_ENTITY
    assert progress.goal.minimum_selected_targets == 1


def test_interrupted_enable_cannot_restart_in_same_turn() -> None:
    """One accepted enabler exhausts same-turn move/action routine starts."""
    context, _ = _short_range_pressure_context(include_weak_attack=True)
    implementation = get_policy_implementation(CANDIDATE_GENERATION_ID)
    candidates = implementation.build_candidates(context)
    idle_revalidation = revalidate_active_routine(context, None, candidates)
    fresh_plans = implementation.plan_routines(
        context,
        None,
        idle_revalidation,
        candidates,
    )
    assert any(
        plan.routine_id == "routine.enable_then_act"
        and plan.step_id == "enable"
        and plan.proposal is not None
        for plan in fresh_plans
    )
    prior_progress = RoutineProgress(
        routine_id="routine.enable_then_act",
        step_id="reassess",
        started_epoch_index=1,
        target_uuid="lost-target",
        target_position=(4, 0),
        goal=SemanticActionGoal(
            required_tags=frozenset({
                ActionTag.ATTACK_SPELL,
                ActionTag.DAMAGE_SINGLE_TARGET,
            }),
            target_uuid="lost-target",
            required_target_allocation=TargetAllocation.SINGLE_ENTITY,
        ),
        enablers_used=1,
        started_round_number=1,
        started_turn_index=0,
    )
    interrupted = revalidate_active_routine(
        context,
        prior_progress,
        candidates,
    )
    assert interrupted.progress is None

    plans = implementation.plan_routines(
        context,
        prior_progress,
        interrupted,
        candidates,
    )

    assert all(
        plan.routine_id != "routine.enable_then_act" or plan.step_id != "enable"
        for plan in plans
    )



def _short_range_pressure_context(
    *,
    include_weak_attack: bool,
) -> tuple[PolicyContext, ActionAffordance]:
    """Build one disclosed target requiring movement for stronger pressure."""
    move_row, move_semantics = _row(
        "position|Move|pos=2,0",
        "position_actions",
        "Move",
        "movement",
        "position",
        {ActionTag.MOVEMENT_VOLUNTARY},
        targets=[ActionTarget(index=0, position=(2, 0), path_cost=10)],
    )
    strong_semantics = ActionSemantics(
        semantic_id="attack.test.short-range",
        tags=frozenset({
            ActionTag.ATTACK_SPELL,
            ActionTag.DAMAGE_SINGLE_TARGET,
        }),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.SINGLE_ENTITY,
            minimum_targets=1,
            maximum_targets=1,
        ),
    )
    strong_ref = action_semantics_ref(strong_semantics)
    capability = ActionCapability(
        capability_id="attack.test.short-range|entity",
        semantic_key="attack.test.short-range",
        action_category="spell",
        target_type="entity",
        cost=ActionCostProfile(action_cost=1),
        range_type="Range",
        normal_range_feet=10,
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.ATTACK_ROLL,
            attack_bonus=5,
            damage_rolls=(DamageRollProfile(
                dice_count=3,
                die_size=10,
                damage_type="force",
            ),),
        ),
        semantic_id=strong_semantics.semantic_id,
        semantics_ref=strong_ref,
        tags=tuple(tag.value for tag in strong_semantics.tags),
    )
    rows = [(move_row, move_semantics)]
    if include_weak_attack:
        weak_row, weak_semantics = _row(
            "entity|weak-pressure|uuid=hero",
            "entity_actions",
            "Weak pressure",
            "attack",
            "entity",
            {ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET},
            targets=[ActionTarget(index=0, target_uuid="hero", position=(4, 0))],
            cost=ActionCostProfile(action_cost=1),
        )
        rows.append((weak_row.model_copy(update={
            "outcome_profile": ActionOutcomeProfile(
                resolution=OutcomeResolution.ATTACK_ROLL,
                attack_bonus=5,
                damage_rolls=(DamageRollProfile(
                    dice_count=1,
                    die_size=4,
                    damage_type="slashing",
                ),),
            ),
        }), weak_semantics))
    base = _context(
        rows,
        visible_hostile=True,
        capabilities=[capability],
        extra_semantics=[strong_semantics],
    )
    hero = base.world.known_entities["hero"].model_copy(update={"ac": 13})
    world = base.world.model_copy(update={
        "known_entities": {**base.world.known_entities, "hero": hero},
    })
    return PolicyContext(world=world, facts=derive_agent_facts(world).facts), move_row

def _defense_row() -> tuple[ActionAffordance, ActionSemantics]:
    """Build one generic typed Dodge-like row without display-name policy."""
    semantics = ActionSemantics(
        semantic_id="defense.generic",
        tags=frozenset({ActionTag.DEFENSE_SELF}),
        guaranteed_effects=(LogicalEffect(
            fact_id="actor.condition.dodging",
            operation=EffectOperation.ADD,
            value=True,
        ),),
    )
    reference = action_semantics_ref(semantics)
    return ActionAffordance(
        row_id="self|generic-defense|index=0",
        bucket="self_actions",
        template_name="generic-defense",
        semantic_key="rules.defense.generic",
        display_name="Generic defense",
        action_category="ability",
        target_type="self",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=(ActionTarget(index=0, target_uuid="actor"),),
        semantic_id=semantics.semantic_id,
        semantics_ref=reference,
    ), semantics
