"""Typed multi-epoch policy routine checks."""

from types import SimpleNamespace

from ai.policy import (
    AgentCommandType,
    command_from_policy_decision,
    PolicyHost,
    PolicyResultDisposition,
)
from ai.knowledge import derive_agent_facts
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationSessionState,
    ObservationTileFact,
    SubjectiveWorldState,
)
from ai.policy import PolicyContext, PolicyMemoryStore, RoutineProgress
from dnd.ai.contracts.decision import EndTurnIntent, ExecuteIntent
from ai.policy.economy import project_capability_transformation
from ai.policy.routines import (
    APPROACH_OPEN_REASSESS,
    ENABLE_THEN_ACT,
    TRANSFORM_THEN_ACT,
    RoutinePlanStatus,
    RoutinePurpose,
    RoutineRevalidationStatus,
    apply_routine_revalidation,
    plan_registered_routines,
    plan_approach_open_reassess,
    plan_transform_then_act,
    revalidate_active_routine,
    revalidate_approach_open_reassess,
)
from dnd.ai.contracts.control import (
    ActionResolutionStatus,
    ActionAffordance,
    ActionBucket,
    ActionCapability,
    ActionCostProfile,
    ActionEconomyState,
    ActionOutcomeProfile,
    ActionTarget,
    AffordanceSet,
    CommandResult,
    CommandResultStatus,
    DecisionEpoch,
    DecisionEpochReason,
    DamageRollProfile,
    OutcomeResolution,
    ResourcePool,
)
from dnd.ai.contracts.semantics import (
    ActionSemantics,
    ActionTag,
    CapabilityAmountFormula,
    CapabilityAmountSource,
    CapabilityCostOperation,
    CapabilityCostRewrite,
    CapabilitySelector,
    CapabilityTransformation,
    TargetAllocation,
    TargetingSemantics,
    action_semantics_ref,
)
from dnd.ai.runtime.action_semantics import action_semantics_for_available_action
from dnd.core.base_actions import ActionCategory, AvailableActionInfo, BaseCost, TargetType


def test_quickened_projection_repairs_only_the_declared_action_cost() -> None:
    """A transform projection preserves slots and resources while moving action cost."""
    activation = AvailableActionInfo(
        template_name="Opaque",
        semantic_key="dnd.classes.sorcerer.QuickenedSpell",
        target_type=TargetType.SELF,
        valid_targets=[],
        can_afford=True,
        display_name="Opaque",
        cost_type="actions",
        cost_amount=0,
        costs=[BaseCost(
            name="Metamagic",
            cost_type="actions",
            cost=0,
            resource_name="sorcery_points",
            resource_cost=2,
        )],
        action_category=ActionCategory.ABILITY,
    )
    transformation = action_semantics_for_available_action(
        activation
    ).capability_transformations[0]
    capability = ActionCapability(
        capability_id="spell|single",
        semantic_key="spell.test",
        action_category="spell",
        target_type="entity",
        cost=ActionCostProfile(
            action_cost=1,
            spell_slot_cost=2,
            resource_costs={"class_resource": 1},
            affordability="unaffordable",
            affordability_reasons=["actions"],
        ),
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        base_spell_level=2,
        cast_at_level=2,
        semantic_id="damage.single_target",
        semantics_ref="spell.test@v1:test",
    )
    spell_semantics = ActionSemantics(
        semantic_id="damage.single_target",
        tags=frozenset({ActionTag.ATTACK_SPELL, ActionTag.DAMAGE_SINGLE_TARGET}),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.SINGLE_ENTITY,
            minimum_targets=1,
            maximum_targets=1,
        ),
    )
    economy = ActionEconomyState(
        actor_uuid="actor",
        actions=0,
        bonus_actions=1,
        spell_slots={2: ResourcePool(current=1, max=1)},
        resources={
            "class_resource": ResourcePool(current=1, max=1),
            "sorcery_points": ResourcePool(current=2, max=2),
        },
    )

    projection = project_capability_transformation(
        capability,
        spell_semantics,
        transformation,
        economy,
    )

    assert projection is not None
    assert projection.cost.action_cost == 0
    assert projection.cost.bonus_action_cost == 1
    assert projection.cost.spell_slot_cost == 2
    assert projection.cost.resource_costs == {"class_resource": 1}
    assert projection.cost.affordability == "affordable"


def test_twinned_projection_uses_base_spell_level_and_preserves_repeat_policy() -> None:
    """Twinned cost scales from the base spell while targeting preserves repeat policy."""
    activation = AvailableActionInfo(
        template_name="Opaque",
        semantic_key="dnd.classes.sorcerer.TwinnedSpell",
        target_type=TargetType.SELF,
        valid_targets=[],
        can_afford=True,
        display_name="Opaque",
        cost_type="actions",
        cost_amount=0,
        costs=[],
        action_category=ActionCategory.ABILITY,
    )
    transformation = action_semantics_for_available_action(
        activation
    ).capability_transformations[0]
    capability = ActionCapability(
        capability_id="spell|single",
        semantic_key="spell.test",
        action_category="spell",
        target_type="entity",
        cost=ActionCostProfile(action_cost=1, spell_slot_cost=4),
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        base_spell_level=3,
        cast_at_level=4,
        semantic_id="damage.single_target",
        semantics_ref="spell.test@v1:test",
    )
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
    economy = ActionEconomyState(
        actor_uuid="actor",
        actions=1,
        spell_slots={4: ResourcePool(current=1, max=1)},
        resources={"sorcery_points": ResourcePool(current=3, max=3)},
    )

    projection = project_capability_transformation(
        capability,
        spell_semantics,
        transformation,
        economy,
    )

    assert projection is not None
    assert projection.cost.resource_costs == {"sorcery_points": 2}
    assert projection.targeting.allocation is TargetAllocation.MULTI_ENTITY
    assert projection.targeting.minimum_targets == 2
    assert projection.targeting.maximum_targets == 2
    assert projection.targeting.allows_repeated_targets is True


def test_transform_planner_uses_shared_outcome_cache_for_projected_damage(monkeypatch) -> None:
    """Projected transform follow-ups should reuse disclosed-value outcome caches."""
    observed_shared_cache_flags: list[bool | None] = []

    def fake_estimate_damage_outcome(
        _profile,
        _target,
        *,
        applications=None,
        workspace=None,
        effect_block_hypothesis=None,
    ):
        observed_shared_cache_flags.append(getattr(workspace, "shared_value_cache", None))
        return SimpleNamespace(guaranteed_zero=False)

    monkeypatch.setattr(
        "ai.policy.routines.estimate_damage_outcome",
        fake_estimate_damage_outcome,
    )
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
        capability_id="spell|bolt",
        semantic_key="spell.bolt",
        action_category="spell",
        target_type="entity",
        cost=ActionCostProfile(
            action_cost=1,
            affordability="unaffordable",
            affordability_reasons=["actions"],
        ),
        range_type="Range",
        normal_range_feet=60,
        requires_line_of_sight=True,
        valid_target_filter="enemies",
        base_spell_level=1,
        cast_at_level=1,
        semantic_id=spell_semantics.semantic_id,
        semantics_ref=spell_ref,
        outcome_profile=ActionOutcomeProfile(
            resolution=OutcomeResolution.SAVING_THROW,
            damage_rolls=(DamageRollProfile(
                dice_count=1,
                die_size=6,
                damage_type="fire",
            ),),
        ),
        tags=sorted(tag.value for tag in spell_semantics.tags),
    )
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
    transform_semantics = ActionSemantics(
        semantic_id="setup.transform",
        tags=frozenset({ActionTag.CAPABILITY_TRANSFORM}),
        capability_transformations=(transformation,),
    )
    transform_ref = action_semantics_ref(transform_semantics)
    transform_row = ActionAffordance.model_validate({
        "row_id": "quickened-row",
        "bucket": "self_actions",
        "template_name": "Quickened Spell",
        "display_name": "Quickened Spell",
        "action_category": "ability",
        "target_type": "self",
        "can_afford": True,
        "cost": ActionCostProfile(),
        "targets": (ActionTarget(index=0),),
        "target_options": (ActionTarget(index=0),),
        "semantic_id": transform_semantics.semantic_id,
        "semantics_ref": transform_ref,
        "tags": [ActionTag.CAPABILITY_TRANSFORM.value],
    })
    context = _context(
        [(transform_row, transform_semantics)],
        visible_hostile=True,
        capabilities=[capability],
        extra_semantics=[spell_semantics],
    )

    plan = plan_transform_then_act(context, None)

    assert plan.status is RoutinePlanStatus.PROPOSED
    assert plan.proposal is not None
    assert plan.proposal.reason == "typed capability transformation predicts a stronger affordable follow-up"
    assert observed_shared_cache_flags
    assert all(flag is True for flag in observed_shared_cache_flags)


def test_door_routine_contract_declares_logic_resources_and_revalidation() -> None:
    """The routine definition is planner-readable rather than prose-only metadata."""
    assert APPROACH_OPEN_REASSESS.routine_id == "routine.approach_open_reassess"
    assert APPROACH_OPEN_REASSESS.purpose is RoutinePurpose.SUBJECTIVE_DISCOVERY
    assert ENABLE_THEN_ACT.purpose is RoutinePurpose.OFFENSIVE_ENABLEMENT
    assert [step.step_id for step in ENABLE_THEN_ACT.steps] == [
        "enable",
        "reassess",
        "act",
    ]
    assert TRANSFORM_THEN_ACT.purpose is RoutinePurpose.CAPABILITY_TRANSFORMATION
    assert [step.step_id for step in APPROACH_OPEN_REASSESS.steps] == [
        "approach",
        "extend_mobility",
        "open",
        "reassess",
    ]
    assert APPROACH_OPEN_REASSESS.applicability is not None
    assert APPROACH_OPEN_REASSESS.invariants is not None
    assert APPROACH_OPEN_REASSESS.completion is not None
    assert ActionTag.MOVEMENT_VOLUNTARY in APPROACH_OPEN_REASSESS.steps[0].accepted_action_tags
    assert ActionTag.INTERACTION_DOOR_OPEN in APPROACH_OPEN_REASSESS.steps[2].accepted_action_tags
    assert "actions" in APPROACH_OPEN_REASSESS.steps[0].preserved_resources
    assert "subjective_event" in APPROACH_OPEN_REASSESS.revalidate_after
    assert "command_result" in APPROACH_OPEN_REASSESS.revalidate_after


def test_door_routine_uses_semantics_and_preserves_action_before_dash() -> None:
    """A renamed movement row wins over a renamed mobility-extension row."""
    context = _context([
        _row(
            "move-row",
            "position_actions",
            "Traverse Quietly",
            "movement",
            "position",
            {ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_REVEAL},
            targets=[ActionTarget(index=7, position=(2, 0), path_cost=10, path=[(0, 0), (1, 0), (2, 0)])],
        ),
        _row(
            "extend-row",
            "self_actions",
            "Borrow Momentum",
            "ability",
            "self",
            {ActionTag.MOBILITY_EXTEND},
            targets=[ActionTarget(index=0)],
        ),
    ])

    plan = plan_approach_open_reassess(context, None)

    assert plan.status is RoutinePlanStatus.PROPOSED
    assert plan.proposal is not None
    assert plan.proposal.intent.kind == "execute"
    assert plan.proposal.intent.row_id == "move-row"
    assert plan.selected_target_index == 7
    assert plan.step_id == "approach"
    assert plan.next_progress_on_success is not None
    assert plan.next_progress_on_success.step_id == "approach"


def test_door_routine_prefers_ordinary_move_over_equal_bonus_action_jump() -> None:
    """Equal route progress preserves the more flexible bonus action."""
    destination = ActionTarget(
        index=7,
        position=(2, 0),
        path_cost=10,
        path=[(0, 0), (1, 0), (2, 0)],
    )
    context = _context([
        _row(
            "a-jump-row",
            "position_actions",
            "Opaque Bonus Relocation",
            "movement",
            "position",
            {ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_REVEAL},
            targets=[destination],
            cost=ActionCostProfile(bonus_action_cost=1, movement_cost=10),
        ),
        _row(
            "z-move-row",
            "position_actions",
            "Opaque Ordinary Relocation",
            "movement",
            "position",
            {ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_REVEAL},
            targets=[destination],
            cost=ActionCostProfile(movement_cost=10),
        ),
    ])

    plan = plan_approach_open_reassess(context, None)

    assert plan.proposal is not None
    assert plan.proposal.intent == ExecuteIntent(row_id="z-move-row")


def test_interrupted_routine_can_start_fresh_routines_in_same_epoch() -> None:
    """Cleared progress cannot suppress every registered planner for one epoch."""
    context = _context([], visible_hostile=True, epoch_index=2)
    prior_progress = _progress("approach", epoch_index=1)

    revalidation = revalidate_active_routine(context, prior_progress)
    plans = plan_registered_routines(
        context,
        prior_progress,
        revalidation,
    )

    assert revalidation.status is RoutineRevalidationStatus.INTERRUPTED
    assert revalidation.progress is None
    assert plans
    assert {plan.routine_id for plan in plans} == {
        "routine.approach_open_reassess",
        "routine.augment_then_act",
        "routine.transform_then_act",
        "routine.enable_then_act",
        "routine.pursue_capability",
    }


def test_door_routine_opens_by_semantic_tag_then_reassesses() -> None:
    """Door interaction and completion do not depend on display text."""
    context = _context([
        _row(
            "open-row",
            "self_actions",
            "Alter Boundary State",
            "ability",
            "self",
            {ActionTag.INTERACTION_DOOR_OPEN, ActionTag.INFORMATION_REVEAL},
            targets=[ActionTarget(index=0)],
            source_item_uuid="door",
        ),
    ], door_position=(1, 0))

    plan = plan_approach_open_reassess(context, None)

    assert plan.status is RoutinePlanStatus.PROPOSED
    assert plan.proposal is not None
    assert isinstance(plan.proposal.intent, ExecuteIntent)
    assert plan.proposal.intent.row_id == "open-row"
    assert plan.step_id == "open"
    assert plan.next_progress_on_success is not None
    assert plan.next_progress_on_success.step_id == "reassess"

    memory = PolicyMemoryStore().for_actor("session", "actor", "external.default")
    apply_routine_revalidation(
        memory,
        revalidate_approach_open_reassess(context, memory.active_routine),
    )
    memory.active_routine = plan.next_progress_on_success
    opened_context = _context([], door_open=True, door_position=(1, 0), epoch_index=2)
    revalidation = revalidate_approach_open_reassess(opened_context, memory.active_routine)

    assert revalidation.status is RoutineRevalidationStatus.COMPLETED
    apply_routine_revalidation(memory, revalidation)
    assert memory.active_routine is None


def test_door_routine_binds_open_affordance_to_exact_target_object() -> None:
    """A legal row for another adjacent door cannot satisfy the active target."""
    context = _context([
        _row(
            "a-other-door",
            "self_actions",
            "Alter Other Boundary",
            "ability",
            "self",
            {ActionTag.INTERACTION_DOOR_OPEN},
            targets=[ActionTarget(index=0)],
            source_item_uuid="other-door",
        ),
        _row(
            "z-target-door",
            "self_actions",
            "Alter Intended Boundary",
            "ability",
            "self",
            {ActionTag.INTERACTION_DOOR_OPEN},
            targets=[ActionTarget(index=0)],
            source_item_uuid="door",
        ),
    ], door_position=(1, 0))
    objects = dict(context.world.known_objects)
    objects["other-door"] = ObservationObjectFact(
        uuid="other-door",
        name="Other Boundary",
        knowledge_state=KnowledgeState.VISIBLE,
        position=(2, 0),
        state={"is_open": False},
    )
    world = context.world.model_copy(update={"known_objects": objects})
    context = PolicyContext(world=world, facts=derive_agent_facts(world).facts)

    plan = plan_approach_open_reassess(context, None)

    assert plan.proposal is not None
    assert plan.target_uuid == "door"
    assert isinstance(plan.proposal.intent, ExecuteIntent)
    assert plan.proposal.intent.row_id == "z-target-door"


def test_door_routine_ignores_misleading_untyped_open_name() -> None:
    """Display text cannot turn an unknown action into a door interaction."""
    context = _context([
        _row(
            "fake-open-row",
            "self_actions",
            "Open Door",
            "ability",
            "self",
            {ActionTag.UNKNOWN},
            targets=[ActionTarget(index=0)],
            source_item_uuid="door",
        ),
        _row(
            "move-row",
            "position_actions",
            "Cross Known Ground",
            "movement",
            "position",
            {ActionTag.MOVEMENT_VOLUNTARY},
            targets=[ActionTarget(index=3, position=(2, 0), path_cost=10)],
        ),
    ])

    plan = plan_approach_open_reassess(context, None)

    assert plan.proposal is not None
    assert isinstance(plan.proposal.intent, ExecuteIntent)
    assert plan.proposal.intent.row_id == "move-row"
    assert plan.step_id == "approach"


def test_door_routine_uses_mobility_extension_only_without_move_progress() -> None:
    """Dash-like semantics are a bounded fallback rather than a first choice."""
    context = _context([
        _row(
            "extend-row",
            "self_actions",
            "Borrow Momentum",
            "ability",
            "self",
            {ActionTag.MOBILITY_EXTEND},
            targets=[ActionTarget(index=0)],
        ),
    ])

    plan = plan_approach_open_reassess(context, None)

    assert plan.proposal is not None
    assert isinstance(plan.proposal.intent, ExecuteIntent)
    assert plan.proposal.intent.row_id == "extend-row"
    assert plan.step_id == "extend_mobility"
    assert plan.next_progress_on_success is not None
    assert plan.next_progress_on_success.step_id == "approach"


def test_door_routine_is_interrupted_by_new_visible_contact() -> None:
    """A reveal invalidates no-contact navigation before the next command."""
    context = _context([], visible_hostile=True, epoch_index=2)
    memory = PolicyMemoryStore().for_actor("session", "actor", "external.default")
    memory.active_routine = _progress("approach", epoch_index=1)

    revalidation = revalidate_approach_open_reassess(context, memory.active_routine)

    assert revalidation.status is RoutineRevalidationStatus.INTERRUPTED
    apply_routine_revalidation(memory, revalidation)
    assert memory.active_routine is None


def test_production_tree_runs_typed_door_routine_and_advances_on_acceptance() -> None:
    """The shared host commits a typed routine only after authoritative acceptance."""
    context = _context([
        _row(
            "move-row",
            "position_actions",
            "Traverse Quietly",
            "movement",
            "position",
            {ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_REVEAL},
            targets=[ActionTarget(index=7, position=(2, 0), path_cost=10, path=[(0, 0), (1, 0), (2, 0)])],
        ),
        _row(
            "extend-row",
            "self_actions",
            "Borrow Momentum",
            "ability",
            "self",
            {ActionTag.MOBILITY_EXTEND},
            targets=[ActionTarget(index=0)],
        ),
    ])
    host = PolicyHost(policy_id="shared.default")
    decision = host.decide(context.world, facts=context.facts)
    binding = host.binding_for("session", "actor", "epoch-1")
    command = command_from_policy_decision(context, decision, binding.routine_plan)

    assert command is not None
    assert command.command_type is AgentCommandType.EXECUTE
    assert command.row_id == "move-row"
    assert command.routine_id == APPROACH_OPEN_REASSESS.routine_id
    assert command.routine_step_id == "approach"
    assert any(
        step.node_path == "ReactiveRoot/TacticalGoalUtility/Routines/ApproachOpenReassess"
        for step in decision.trace
    )
    memory = host.memory_for("session", "actor")
    assert memory.active_routine is None

    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="command-1",
    )
    result = host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="command-1",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-1",
            current_epoch_id="epoch-2",
            row_id="move-row",
            action_resolution=ActionResolutionStatus.COMPLETED,
        ))

    assert result.disposition is PolicyResultDisposition.ACCEPTED
    assert memory.active_routine is not None
    assert memory.active_routine.routine_id == APPROACH_OPEN_REASSESS.routine_id
    assert memory.active_routine.step_id == "approach"
    assert memory.active_routine.target_uuid == "door"


def test_rejected_routine_command_does_not_advance_actor_memory() -> None:
    """Only the authoritative accepted result commits routine progress."""
    context = _context([
        _row(
            "move-row",
            "position_actions",
            "Traverse Quietly",
            "movement",
            "position",
            {ActionTag.MOVEMENT_VOLUNTARY},
            targets=[ActionTarget(index=7, position=(2, 0), path_cost=10)],
        ),
    ])
    host = PolicyHost(policy_id="shared.default")
    host.decide(context.world, facts=context.facts)
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="command-1",
    )
    result = host.record_result(CommandResult(
        status=CommandResultStatus.REJECTED,
        command_id="command-1",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-1",
        current_epoch_id="epoch-1",
        row_id="move-row",
    ))

    memory = host.memory_for("session", "actor")
    assert result.disposition is PolicyResultDisposition.REJECTED
    assert memory.active_routine is None


def test_admitted_canceled_action_is_excluded_for_the_rest_of_the_turn() -> None:
    """Protocol acceptance cannot make a canceled engine action look successful."""
    jump_row = _row(
        "position|Jump|pos=2,0",
        "position_actions",
        "Jump",
        "movement",
        "position",
        {
            ActionTag.MOVEMENT_VOLUNTARY,
            ActionTag.INFORMATION_EXPLORE,
            ActionTag.INFORMATION_REVEAL,
        },
        targets=[ActionTarget(index=0, position=(2, 0), path_cost=10)],
    )
    first_base = _context([jump_row], door_open=True, epoch_index=1)
    first_entities = dict(first_base.world.known_entities)
    first_entities["hero"] = ObservationEntityFact(
        uuid="hero",
        name="Remembered Hero",
        knowledge_state=KnowledgeState.REMEMBERED,
        position=(3, 0),
        faction="heroes",
    )
    first_world = first_base.world.model_copy(update={"known_entities": first_entities})
    first = PolicyContext(world=first_world, facts=derive_agent_facts(first_world).facts)
    host = PolicyHost(policy_id="shared.default")

    decision = host.decide(first.world, facts=first.facts)

    assert decision.selected.intent == ExecuteIntent(row_id="position|Jump|pos=2,0")
    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="command-canceled",
    )
    recorded = host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="command-canceled",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-1",
        current_epoch_id="epoch-2",
        row_id="position|Jump|pos=2,0",
        action_resolution=ActionResolutionStatus.CANCELED,
    ))

    assert recorded.memory_advanced is False
    assert "position|Jump|pos=2,0" in host.memory_for("session", "actor").canceled_row_ids

    second_base = _context([jump_row], door_open=True, epoch_index=2)
    second_entities = dict(second_base.world.known_entities)
    second_entities["hero"] = first_entities["hero"]
    second_world = second_base.world.model_copy(update={"known_entities": second_entities})
    second = PolicyContext(world=second_world, facts=derive_agent_facts(second_world).facts)
    followup = host.decide(second.world, facts=second.facts)

    assert followup.selected.intent == EndTurnIntent()
    assert any(
        step.node_path == "PolicyHost/ExecutionConstraints"
        and "row:position|Jump|pos=2,0" in step.detail
        for step in followup.trace
    )


def test_cleared_last_known_position_expands_subjective_search() -> None:
    """Negative observation at a remembered square drives a bounded local search."""
    move_row = _row(
        "position|Move|pos=2,0",
        "position_actions",
        "Move",
        "movement",
        "position",
        {
            ActionTag.MOVEMENT_VOLUNTARY,
            ActionTag.INFORMATION_EXPLORE,
            ActionTag.INFORMATION_REVEAL,
        },
        targets=[ActionTarget(index=0, position=(2, 0), path_cost=10)],
    )
    base = _context([move_row], door_open=True, epoch_index=1)
    known_entities = dict(base.world.known_entities)
    known_entities["hero"] = ObservationEntityFact(
        uuid="hero",
        name="Remembered Hero",
        knowledge_state=KnowledgeState.REMEMBERED,
        position=(0, 0),
        faction="heroes",
    )
    world = base.world.model_copy(update={"known_entities": known_entities})
    facts = derive_agent_facts(world).facts
    host = PolicyHost(policy_id="shared.default")
    memory = host.memory_for("session", "actor")
    memory.remembered_search_positions["hero"] = (0, 0)
    memory.remembered_search_failures["hero"] = 1
    memory.remembered_search_visited_positions["hero"] = {(0, 0)}

    decision = host.decide(world, facts=facts)

    assert decision.selected.intent == ExecuteIntent(row_id="position|Move|pos=2,0")
    assert decision.selected.reason == "expand_remembered_contact_search"
    exploration = decision.selected.evidence.exploration
    assert exploration is not None
    assert exploration.expanded_remembered_search is True
    assert exploration.remembered_target_uuid == "hero"
    assert exploration.remembered_search_attempt == 1

    host.prepare_submission(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        command_id="command-search",
    )
    host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="command-search",
        session_id="session",
        actor_uuid="actor",
        requested_epoch_id="epoch-1",
        current_epoch_id="epoch-2",
        row_id="position|Move|pos=2,0",
        action_resolution=ActionResolutionStatus.COMPLETED,
    ))

    assert memory.remembered_search_failures["hero"] == 2
    assert memory.remembered_search_visited_positions["hero"] == {(0, 0), (2, 0)}


def _context(
    rows: list[tuple[ActionAffordance, ActionSemantics]],
    *,
    door_open: bool = False,
    door_position: tuple[int, int] = (3, 0),
    visible_hostile: bool = False,
    epoch_index: int = 1,
    capabilities: list[ActionCapability] | None = None,
    extra_semantics: list[ActionSemantics] | None = None,
) -> PolicyContext:
    """Build one compact subjective decision context."""
    by_bucket: dict[str, list[ActionAffordance]] = {
        "entity_actions": [],
        "position_actions": [],
        "self_actions": [],
        "object_actions": [],
        "special_commands": [],
    }
    catalog: dict[str, ActionSemantics] = {}
    for row, semantics in rows:
        by_bucket[row.bucket].append(row)
        catalog[row.semantics_ref] = semantics
    for semantics in extra_semantics or []:
        catalog[action_semantics_ref(semantics)] = semantics
    affordances = AffordanceSet(
        actor_uuid="actor",
        computed_at_observation_cursor=epoch_index,
        entity_actions=by_bucket["entity_actions"],
        position_actions=by_bucket["position_actions"],
        self_actions=by_bucket["self_actions"],
        object_actions=by_bucket["object_actions"],
        special_commands=by_bucket["special_commands"],
        capabilities=capabilities or [],
        semantic_catalog=catalog,
    )
    epoch = DecisionEpoch(
        epoch_id=f"epoch-{epoch_index}",
        epoch_index=epoch_index,
        basis_observation_cursor=epoch_index,
        reason=DecisionEpochReason.TURN_START if epoch_index == 1 else DecisionEpochReason.ACTION_COMPLETED,
        actor_uuid="actor",
        round_number=1,
        turn_index=0,
        economy=ActionEconomyState(
            actor_uuid="actor",
            actions=1,
            bonus_actions=1,
            reactions=1,
            movement_remaining=30,
            meaningful_commands_remaining=bool(rows),
        ),
        affordances=affordances,
    )
    entities = {
        "actor": ObservationEntityFact(
            uuid="actor",
            name="Skeleton",
            knowledge_state=KnowledgeState.VISIBLE,
            controlled=True,
            position=(0, 0),
            hp=13,
            max_hp=13,
            faction="monsters",
        ),
    }
    if visible_hostile:
        entities["hero"] = ObservationEntityFact(
            uuid="hero",
            name="Hero",
            knowledge_state=KnowledgeState.VISIBLE,
            position=(4, 0),
            hp=20,
            max_hp=20,
            faction="heroes",
        )
    tiles = {
        f"{x},0": ObservationTileFact(
            key=f"{x},0",
            position=(x, 0),
            knowledge_state=KnowledgeState.VISIBLE,
            walkable=True,
            walking_cost=5,
            is_hazardous=False,
        )
        for x in range(5)
    }
    world = SubjectiveWorldState(
        observation_cursor=epoch_index,
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
        known_entities=entities,
        known_objects={
            "door": ObservationObjectFact(
                uuid="door",
                name="Boundary",
                knowledge_state=KnowledgeState.VISIBLE,
                position=door_position,
                state={"is_open": door_open},
            ),
        },
        known_tiles=tiles,
        current_epoch=epoch,
        epoch_cursor=epoch_index,
    )
    return PolicyContext(world=world, facts=derive_agent_facts(world).facts)


def _row(
    row_id: str,
    bucket: ActionBucket,
    name: str,
    category: str,
    target_type: str,
    tags: set[ActionTag],
    *,
    targets: list[ActionTarget],
    source_item_uuid: str | None = None,
    cost: ActionCostProfile | None = None,
) -> tuple[ActionAffordance, ActionSemantics]:
    """Build one legal row and its content-addressed semantics."""
    semantic_id = sorted(tag.value for tag in tags)[0]
    semantics = ActionSemantics(semantic_id=semantic_id, tags=frozenset(tags))
    reference = action_semantics_ref(semantics)
    row = ActionAffordance.model_validate({
        "row_id": row_id,
        "bucket": bucket,
        "template_name": name,
        "display_name": name,
        "action_category": category,
        "target_type": target_type,
        "can_afford": True,
        "cost": cost or ActionCostProfile(),
        "targets": targets,
        "target_options": targets,
        "source_item_uuid": source_item_uuid,
        "semantic_id": semantic_id,
        "semantics_ref": reference,
        "tags": [tag.value for tag in sorted(tags, key=lambda item: item.value)],
    })
    return row, semantics


def _progress(step_id: str, *, epoch_index: int) -> RoutineProgress:
    """Build routine progress through the public plan model type."""
    return RoutineProgress(
        routine_id=APPROACH_OPEN_REASSESS.routine_id,
        step_id=step_id,
        started_epoch_index=epoch_index,
        target_uuid="door",
        target_position=(3, 0),
    )
