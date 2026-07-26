"""Contracts for typed action meaning carried by decision epochs."""

import json
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.ai.contracts.control import (
    ActionAffordance,
    ActionEconomyState,
    ActionSourceDefinition,
    AffordanceSet,
    DecisionEpoch,
    DecisionEpochReason,
)
from dnd.ai.contracts.semantics import (
    AffectedRelationship,
    CapabilityAmountSource,
    CapabilityCostOperation,
    ActionTag,
    ConcentrationOperation,
    EffectDisposition,
    EffectCertainty,
    EffectOperation,
    FactExpression,
    FactOperator,
    FactPredicate,
    InformationOperation,
    MovementKind,
    OutcomeKind,
    ResourceEffect,
    ResourceOperation,
    SemanticProvenanceKind,
    SelfSetupDuration,
    D20CheckMode,
    SelfSetupMaintenanceSemantics,
    SetupMaintenanceFailure,
    SetupMaintenanceTrigger,
    TargetAllocation,
    TopologyOperation,
    TruthValue,
    WorldEffectAnchor,
    WorldEffectScope,
    WorldEffectShape,
    action_semantics_ref,
    evaluate_fact_expression,
)
from dnd.ai.runtime.action_semantics import action_semantics_for_available_action
from ai.subjective.semantic_pool import SemanticContractPool
from dnd.ai.runtime.decision_epoch import (
    _affordance_set_from_buckets,
    _build_affordance_rows_from_actions,
    _display_tags,
)
from dnd.core.base_actions import (
    ActionAvailabilityStatus,
    ActionOutcomeProfile as EngineActionOutcomeProfile,
    ActionInformationOperation,
    ActionSelfSetupProfile,
    ActionSetupMaintenanceFailure,
    ActionSetupMaintenanceProfile,
    ActionSetupMaintenanceTrigger,
    ActionSetupDuration,
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    ActionTopologyOperation,
    ActionWorldEffectAnchor,
    ActionWorldEffectCertainty,
    ActionWorldEffectProfile,
    ActionWorldEffectScope,
    ActionWorldEffectShape,
    ActionCategory,
    AvailableActionInfo,
    AvailableTarget,
    BaseCost,
    DamageRollProfile as EngineDamageRollProfile,
    InformationEffectProfile,
    OutcomeResolution,
    TargetEffectDisposition,
    TargetType,
    TopologyEffectProfile,
)
from tests.content_identity import synthetic_action_attribution
from dnd.core.modifiers import AdvantageStatus
from dnd.spells.conjuration import Darkness, Daylight, FogCloud
from dnd.spells.divination import SeeInvisibility, TrueSeeing
from dnd.spells.evocation import Light
from dnd.spells.transmutation import DarkvisionSpell


def _action(
    template_name: str,
    *,
    semantic_key: str = "action.unclassified",
    display_name: str | None = None,
    target_type: TargetType = TargetType.SELF,
    action_category: ActionCategory = ActionCategory.ABILITY,
    base_template_name: str | None = None,
    costs: list[BaseCost] | None = None,
    valid_targets: list[AvailableTarget] | None = None,
    damage_types: list[str] | None = None,
    requires_concentration: bool = False,
    num_projectiles: int | None = None,
    allow_same_target: bool | None = None,
    is_item_use: bool = False,
    source_item_uuid: UUID | None = None,
    item_charge_cost: int = 0,
    fixed_healing: int | None = None,
    outcome_profile: EngineActionOutcomeProfile | None = None,
    self_setup_profile: ActionSelfSetupProfile | None = None,
    target_effect_profile: ActionTargetEffectProfile | None = None,
    world_effect_profile: ActionWorldEffectProfile | None = None,
) -> AvailableActionInfo:
    """Build one discovery row without constructing a live encounter."""
    normalized_costs = costs or []
    resolved_targets = (
        list(valid_targets)
        if valid_targets is not None
        else (
            [AvailableTarget(index=0)]
            if target_type is TargetType.SELF
            else []
        )
    )
    return AvailableActionInfo(
        template_name=template_name,
        semantic_key=semantic_key,
        behavior_attribution=synthetic_action_attribution(
            "action.synthetic_semantics",
        ),
        base_template_name=base_template_name,
        target_type=target_type,
        availability_status=(
            ActionAvailabilityStatus.AVAILABLE
            if resolved_targets
            else ActionAvailabilityStatus.NO_VALID_TARGETS
        ),
        valid_targets=resolved_targets,
        can_afford=True,
        display_name=display_name or template_name,
        cost_type=normalized_costs[0].cost_type if normalized_costs else "actions",
        cost_amount=normalized_costs[0].cost if normalized_costs else 0,
        costs=normalized_costs,
        action_category=action_category,
        damage_types=damage_types or [],
        requires_concentration=requires_concentration,
        num_projectiles=num_projectiles,
        allow_same_target=allow_same_target,
        is_item_use=is_item_use,
        source_item_uuid=source_item_uuid or (uuid4() if is_item_use else None),
        item_charge_cost=item_charge_cost,
        fixed_healing=fixed_healing,
        outcome_profile=outcome_profile,
        self_setup_profile=self_setup_profile,
        target_effect_profile=target_effect_profile,
        world_effect_profile=world_effect_profile,
    )


def test_fact_expression_preserves_unknown_instead_of_treating_it_as_false() -> None:
    """Missing subjective facts evaluate to UNKNOWN through boolean composition."""
    expression = FactExpression(
        operator=FactOperator.ALL,
        operands=(
            FactExpression(
                operator=FactOperator.PREDICATE,
                predicate=FactPredicate(fact_id="door.open", expected_value=False),
            ),
            FactExpression(
                operator=FactOperator.PREDICATE,
                predicate=FactPredicate(fact_id="actor.adjacent_to_target", expected_value=True),
            ),
        ),
    )

    result = evaluate_fact_expression(
        expression,
        {
            "door.open": False,
        },
    )

    assert result is TruthValue.UNKNOWN


def test_fact_expression_rejects_invalid_not_shape_at_validation_boundary() -> None:
    """Malformed planner logic fails when loaded instead of during a later policy tick."""
    with pytest.raises(ValidationError, match="exactly one operand"):
        FactExpression(operator=FactOperator.NOT)


def test_fact_expression_rejects_fields_irrelevant_to_its_operator() -> None:
    """Equivalent planner expressions cannot acquire different hidden payloads."""
    with pytest.raises(ValidationError, match="cannot include a predicate or operands"):
        FactExpression(
            operator=FactOperator.CONSTANT,
            constant=TruthValue.TRUE,
            predicate=FactPredicate(fact_id="ignored.fact"),
        )


def test_display_name_does_not_change_stable_action_semantics() -> None:
    """Policy classification follows the registered template identity, not UI text."""
    original = _action(
        "Move",
        semantic_key="dnd.actions.Move",
        display_name="Move",
        target_type=TargetType.POSITION_PATH,
        action_category=ActionCategory.MOVEMENT,
    )
    renamed = original.model_copy(update={
        "template_name": "WalkToCell",
        "base_template_name": "WalkToCell",
        "display_name": "Walk over there",
    })

    assert action_semantics_for_available_action(original) is action_semantics_for_available_action(renamed)


def test_end_rage_has_exact_logical_precondition_and_effects() -> None:
    """Voluntary rage cleanup is a known capability rather than an unknown action."""
    semantics = action_semantics_for_available_action(_action(
        "End Rage",
        semantic_key="dnd.classes.rage.EndRage",
    ))

    assert semantics.semantic_id == "setup.rage.end"
    assert semantics.provenance.kind is SemanticProvenanceKind.EXACT
    assert semantics.planning_preconditions == FactExpression(
        operator=FactOperator.ANY,
        operands=(
            FactExpression(
                operator=FactOperator.PREDICATE,
                predicate=FactPredicate(
                    fact_id="actor.condition.raging",
                    expected_value=True,
                ),
            ),
            FactExpression(
                operator=FactOperator.PREDICATE,
                predicate=FactPredicate(
                    fact_id="actor.condition.frenzied",
                    expected_value=True,
                ),
            ),
        ),
    )
    assert {
        (effect.fact_id, effect.operation)
        for effect in semantics.guaranteed_effects
    } == {
        ("actor.condition.raging", EffectOperation.REMOVE),
        ("actor.condition.frenzied", EffectOperation.REMOVE),
    }


def test_semantic_provenance_distinguishes_exact_profile_fallback_and_unknown() -> None:
    """Consumers can audit semantic resolution strength without reverse engineering it."""
    exact = action_semantics_for_available_action(_action(
        "Move",
        semantic_key="dnd.actions.Move",
        target_type=TargetType.POSITION_PATH,
        action_category=ActionCategory.MOVEMENT,
    ))
    profiled = action_semantics_for_available_action(_action(
        "Opaque setup",
        semantic_key="rules.actions.profiled_setup",
        self_setup_profile=ActionSelfSetupProfile(
            semantic_id="setup.opaque",
            duration=ActionSetupDuration.UNTIL_NEXT_TURN,
        ),
    ))
    fallback = action_semantics_for_available_action(_action(
        "Opaque spell",
        semantic_key="rules.spells.unregistered_damage",
        action_category=ActionCategory.SPELL,
        damage_types=["fire"],
    ))
    unknown = action_semantics_for_available_action(_action(
        "Opaque ability",
        semantic_key="rules.actions.unclassified",
    ))

    assert exact.provenance.kind is SemanticProvenanceKind.EXACT
    assert exact.provenance.semantic_key == "dnd.actions.Move"
    assert profiled.provenance.kind is SemanticProvenanceKind.STRUCTURED_PROFILE
    assert fallback.provenance.kind is SemanticProvenanceKind.CATEGORY_FALLBACK
    assert unknown.provenance.kind is SemanticProvenanceKind.UNKNOWN
    assert unknown.provenance.missing_inputs


def test_inventory_and_wake_actions_have_exact_logical_semantics() -> None:
    """Core utility actions expose their real prerequisites and effects."""
    pick_up = action_semantics_for_available_action(_action(
        "Pick Up",
        semantic_key="dnd.actions.PickUp",
        target_type=TargetType.OBJECT,
    ))
    shake_awake = action_semantics_for_available_action(_action(
        "Shake Awake",
        semantic_key="dnd.actions.ShakeAwake",
        target_type=TargetType.ENTITY,
    ))

    assert pick_up.provenance.kind is SemanticProvenanceKind.EXACT
    assert pick_up.semantic_id == "interaction.object.pick_up"
    assert ActionTag.RESOURCE_ACQUIRE in pick_up.tags
    assert {effect.fact_id for effect in pick_up.guaranteed_effects} == {
        "actor.inventory.selected_object",
        "world.floor.selected_object",
    }
    assert shake_awake.provenance.kind is SemanticProvenanceKind.EXACT
    assert shake_awake.semantic_id == "support.shake_awake"
    assert shake_awake.guaranteed_effects[0].operation is EffectOperation.REMOVE


def test_font_of_magic_conversions_describe_both_resource_sides() -> None:
    """Slot and sorcery-point conversions preserve costs and acquired resources."""
    slot_to_points = action_semantics_for_available_action(_action(
        "Slot to SP L3",
        semantic_key="dnd.classes.sorcerer.ConvertSlotToSP",
        costs=[
            BaseCost(name="Bonus Action", cost_type="bonus_actions", cost=1),
            BaseCost(name="Level 3 Slot", cost_type="spell_slot_3", cost=1),
        ],
    ))
    points_to_slot = action_semantics_for_available_action(_action(
        "5 SP to Slot L3",
        semantic_key="dnd.classes.sorcerer.ConvertSPToSlot",
        costs=[
            BaseCost(name="Bonus Action", cost_type="bonus_actions", cost=1),
            BaseCost(
                name="Sorcery Points",
                cost_type="actions",
                cost=0,
                resource_name="sorcery_points",
                resource_cost=5,
            ),
        ],
    ))

    assert slot_to_points.provenance.kind is SemanticProvenanceKind.EXACT
    assert ResourceEffect(
        resource_id="resource.sorcery_points",
        operation=ResourceOperation.RESTORE,
        amount=3,
    ) in slot_to_points.resource_effects
    assert ResourceEffect(
        resource_id="spell_slot.3",
        operation=ResourceOperation.CONSUME,
        amount=1,
    ) in slot_to_points.resource_effects
    assert points_to_slot.provenance.kind is SemanticProvenanceKind.EXACT
    assert ResourceEffect(
        resource_id="spell_slot.3",
        operation=ResourceOperation.RESTORE,
        amount=1,
    ) in points_to_slot.resource_effects
    assert ResourceEffect(
        resource_id="resource.sorcery_points",
        operation=ResourceOperation.CONSUME,
        amount=5,
    ) in points_to_slot.resource_effects


def test_move_and_dash_expose_distinct_spatial_meaning() -> None:
    """Move changes position voluntarily while Dash only extends mobility."""
    move = _action(
        "Move",
        semantic_key="dnd.actions.Move",
        target_type=TargetType.POSITION_PATH,
        action_category=ActionCategory.MOVEMENT,
        costs=[BaseCost(name="Movement", cost_type="movement", cost=15)],
        valid_targets=[AvailableTarget(index=0, position=(4, 2), path_cost=15)],
    )
    dash = _action(
        "Dash",
        semantic_key="dnd.actions.Dash",
        costs=[BaseCost(name="Action", cost_type="actions", cost=1)],
    )

    move_semantics = action_semantics_for_available_action(move)
    dash_semantics = action_semantics_for_available_action(dash)

    assert move_semantics.semantic_id == "movement.move"
    assert ActionTag.MOVEMENT_VOLUNTARY in move_semantics.tags
    assert move_semantics.spatial is not None
    assert move_semantics.spatial.movement_kind is MovementKind.VOLUNTARY
    assert any(
        effect.fact_id == "actor.position" and effect.operation is EffectOperation.SET_FROM_TARGET
        for effect in move_semantics.guaranteed_effects
    )
    assert move_semantics.information_effects[0].anchor is WorldEffectAnchor.SELECTED_TARGET
    assert move_semantics.information_effects[0].scope is WorldEffectScope.FRONTIER

    assert dash_semantics.semantic_id == "mobility.dash"
    assert ActionTag.MOBILITY_EXTEND in dash_semantics.tags
    assert ActionTag.MOVEMENT_VOLUNTARY not in dash_semantics.tags
    assert dash_semantics.spatial is not None
    assert dash_semantics.spatial.movement_kind is MovementKind.NONE
    assert any(effect.fact_id == "actor.movement_remaining" for effect in dash_semantics.guaranteed_effects)


def test_open_door_exposes_interaction_topology_and_possible_information_gain() -> None:
    """Opening a door changes topology and may reveal facts beyond it."""
    row = _action(
        "Open Door",
        semantic_key="dnd.items.test_items.OpenDoorAction",
        is_item_use=True,
    )

    semantics = action_semantics_for_available_action(row)

    assert semantics.semantic_id == "interaction.door.open"
    assert ActionTag.INTERACTION_DOOR_OPEN in semantics.tags
    assert ActionTag.INFORMATION_REVEAL in semantics.tags
    assert semantics.topology_effects[0].operation is TopologyOperation.OPEN
    assert semantics.topology_effects[0].certainty is EffectCertainty.GUARANTEED
    assert semantics.topology_effects[0].anchor is WorldEffectAnchor.SELECTED_OBJECT
    assert semantics.topology_effects[0].scope is WorldEffectScope.TARGET
    assert semantics.information_effects[0].operation is InformationOperation.REVEAL_FRONTIER
    assert semantics.information_effects[0].certainty is EffectCertainty.POTENTIAL
    assert semantics.information_effects[0].anchor is WorldEffectAnchor.SELECTED_OBJECT
    assert semantics.information_effects[0].scope is WorldEffectScope.FRONTIER
    assert evaluate_fact_expression(semantics.planning_preconditions, {}) is TruthValue.UNKNOWN


def test_pull_lever_exposes_typed_hazard_deactivation() -> None:
    """Trap controls predict hazard removal without pretending to open a blocker."""
    row = _action(
        "Pull Lever__item_test",
        semantic_key="dnd.items.test_items.PullLeverAction",
        is_item_use=True,
    )

    semantics = action_semantics_for_available_action(row)

    assert semantics.semantic_id == "interaction.trap.deactivate"
    assert ActionTag.INTERACTION_HAZARD_DEACTIVATE in semantics.tags
    assert ActionTag.INTERACTION_OBJECT in semantics.tags
    assert semantics.topology_effects[0].operation is TopologyOperation.DEACTIVATE_HAZARD
    assert semantics.topology_effects[0].affects_hazards is True
    assert semantics.topology_effects[0].affects_movement is False
    assert semantics.topology_effects[0].affects_vision is False
    assert semantics.topology_effects[0].scope is WorldEffectScope.HAZARD_REGION


def test_engine_world_effect_profile_translates_without_action_name_inference() -> None:
    """Opaque engine annotations retain typed information and topology details."""
    profile = ActionWorldEffectProfile(
        semantic_id="rules.world.opaque_sensor_field",
        information_effects=(InformationEffectProfile(
            operation=ActionInformationOperation.GRANT_SENSE,
            certainty=ActionWorldEffectCertainty.GUARANTEED,
            anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
            scope=ActionWorldEffectScope.TARGET,
            shape=ActionWorldEffectShape.SPHERE,
            radius_feet=30,
            sense_type="rules.senses.opaque",
        ),),
        topology_effects=(TopologyEffectProfile(
            operation=ActionTopologyOperation.CREATE_BLOCKER,
            certainty=ActionWorldEffectCertainty.CONDITIONAL,
            anchor=ActionWorldEffectAnchor.SELECTED_POSITION,
            scope=ActionWorldEffectScope.REGION,
            shape=ActionWorldEffectShape.SPHERE,
            radius_feet=15,
            affects_movement=False,
            affects_vision=True,
            affects_hazards=False,
        ),),
    )
    row = _action(
        "Localized opaque action",
        semantic_key="rules.actions.not_in_a_spell_table",
        target_type=TargetType.POSITION,
        action_category=ActionCategory.SPELL,
        world_effect_profile=profile,
    )

    restored_row = AvailableActionInfo.model_validate_json(row.model_dump_json())
    semantics = action_semantics_for_available_action(restored_row)

    assert restored_row.world_effect_profile == profile
    assert semantics.semantic_id == profile.semantic_id
    information = semantics.information_effects[0]
    assert information.operation is InformationOperation.GRANT_SENSE
    assert information.certainty is EffectCertainty.GUARANTEED
    assert information.anchor is WorldEffectAnchor.SELECTED_TARGET
    assert information.scope is WorldEffectScope.TARGET
    assert information.shape is WorldEffectShape.SPHERE
    assert information.radius_feet == 30
    assert information.sense_type == "rules.senses.opaque"
    topology = semantics.topology_effects[0]
    assert topology.operation is TopologyOperation.CREATE_BLOCKER
    assert topology.certainty is EffectCertainty.CONDITIONAL
    assert topology.anchor is WorldEffectAnchor.SELECTED_POSITION
    assert topology.scope is WorldEffectScope.REGION
    assert topology.shape is WorldEffectShape.SPHERE
    assert topology.radius_feet == 15
    assert topology.affects_movement is False
    assert topology.affects_vision is True
    assert topology.affects_hazards is False


@pytest.mark.parametrize(
    ("action_type", "semantic_id", "guaranteed_operation", "radius_feet", "sense_type"),
    (
        (Light, "information.light", InformationOperation.CHANGE_LIGHT, 40, None),
        (DarkvisionSpell, "information.darkvision", InformationOperation.GRANT_SENSE, 60, "darkvision"),
        (SeeInvisibility, "information.see_invisibility", InformationOperation.GRANT_SENSE, 0, "see_invisible"),
        (TrueSeeing, "information.true_seeing", InformationOperation.GRANT_SENSE, 120, "truesight"),
        (Daylight, "information.daylight", InformationOperation.CHANGE_LIGHT, 60, None),
    ),
)
def test_light_and_sense_spell_profiles_declare_guaranteed_information_with_conditional_reveal(
    action_type: type[Light] | type[DarkvisionSpell] | type[SeeInvisibility] | type[TrueSeeing] | type[Daylight],
    semantic_id: str,
    guaranteed_operation: InformationOperation,
    radius_feet: int,
    sense_type: str | None,
) -> None:
    """Positive information spells separate certain setup from possible discoveries."""
    action = action_type(source_entity_uuid=uuid4())
    profile = action.get_world_effect_profile(None)

    assert profile is not None
    assert profile.semantic_id == semantic_id
    assert len(profile.information_effects) == 2
    guaranteed, reveal = profile.information_effects
    assert guaranteed.operation.value == guaranteed_operation.value
    assert guaranteed.certainty is ActionWorldEffectCertainty.GUARANTEED
    assert guaranteed.shape is ActionWorldEffectShape.SPHERE
    assert guaranteed.radius_feet == radius_feet
    assert guaranteed.sense_type == sense_type
    assert reveal.operation is ActionInformationOperation.REVEAL_REGION
    assert reveal.certainty is ActionWorldEffectCertainty.CONDITIONAL
    assert reveal.radius_feet == radius_feet

    semantics = action_semantics_for_available_action(_action(
        "Localized information spell",
        semantic_key=f"rules.opaque.{semantic_id}",
        target_type=action.target_type,
        action_category=ActionCategory.SPELL,
        world_effect_profile=profile,
    ))
    assert semantics.semantic_id == semantic_id
    assert semantics.information_effects[0].operation is guaranteed_operation
    assert semantics.information_effects[0].certainty is EffectCertainty.GUARANTEED
    assert semantics.information_effects[0].radius_feet == radius_feet
    assert semantics.information_effects[0].sense_type == sense_type
    assert semantics.information_effects[1].operation is InformationOperation.REVEAL_REGION
    assert semantics.information_effects[1].certainty is EffectCertainty.CONDITIONAL


@pytest.mark.parametrize(
    ("action_type", "semantic_id", "radius_feet", "topology_scope"),
    (
        (Darkness, "control.darkness", 15, ActionWorldEffectScope.MAGICAL_DARKNESS),
        (FogCloud, "control.fog_cloud", 20, ActionWorldEffectScope.REGION),
    ),
)
def test_concealment_spell_profiles_create_vision_blockers_without_positive_reveal(
    action_type: type[Darkness] | type[FogCloud],
    semantic_id: str,
    radius_feet: int,
    topology_scope: ActionWorldEffectScope,
) -> None:
    """Darkness and fog advertise concealment, never a positive reveal effect."""
    action = action_type(source_entity_uuid=uuid4())
    profile = action.get_world_effect_profile(None)

    assert profile is not None
    assert profile.semantic_id == semantic_id
    assert {
        effect.operation
        for effect in profile.information_effects
    } == {ActionInformationOperation.CONCEAL_REGION}
    assert all(
        effect.certainty is ActionWorldEffectCertainty.GUARANTEED
        for effect in profile.information_effects
    )
    blocker = profile.topology_effects[0]
    assert blocker.operation is ActionTopologyOperation.CREATE_BLOCKER
    assert blocker.certainty is ActionWorldEffectCertainty.GUARANTEED
    assert blocker.scope is topology_scope
    assert blocker.shape is ActionWorldEffectShape.SPHERE
    assert blocker.radius_feet == radius_feet
    assert blocker.affects_movement is False
    assert blocker.affects_vision is True
    assert blocker.affects_hazards is False

    semantics = action_semantics_for_available_action(_action(
        "Localized concealment spell",
        semantic_key=f"rules.opaque.{semantic_id}",
        target_type=action.target_type,
        action_category=ActionCategory.SPELL,
        world_effect_profile=profile,
    ))
    assert semantics.semantic_id == semantic_id
    assert {
        effect.operation
        for effect in semantics.information_effects
    } == {InformationOperation.CONCEAL_REGION}
    assert ActionTag.INFORMATION_REVEAL not in semantics.tags
    assert semantics.topology_effects[0].scope.value == topology_scope.value


def test_daylight_removes_only_overlapping_magical_darkness_blockers() -> None:
    """Daylight's conditional topology effect does not promise to remove fog."""
    daylight = Daylight(source_entity_uuid=uuid4()).get_world_effect_profile(None)
    darkness = Darkness(source_entity_uuid=uuid4()).get_world_effect_profile(None)
    fog = FogCloud(source_entity_uuid=uuid4()).get_world_effect_profile(None)

    assert daylight is not None
    assert darkness is not None
    assert fog is not None
    removal = daylight.topology_effects[0]
    darkness_blocker = darkness.topology_effects[0]
    fog_blocker = fog.topology_effects[0]
    assert removal.operation is ActionTopologyOperation.REMOVE_BLOCKER
    assert removal.certainty is ActionWorldEffectCertainty.CONDITIONAL
    assert removal.scope is ActionWorldEffectScope.MAGICAL_DARKNESS
    assert removal.scope is darkness_blocker.scope
    assert fog_blocker.scope is ActionWorldEffectScope.REGION
    assert removal.scope is not fog_blocker.scope
    assert removal.affects_vision is True
    assert removal.affects_movement is False
    assert removal.affects_hazards is False


def test_fog_cloud_world_effect_radius_tracks_cast_slot() -> None:
    """Fog Cloud's disclosed region follows its runtime upcast radius formula."""
    base = FogCloud(source_entity_uuid=uuid4(), cast_at_level=1).get_world_effect_profile(None)
    upcast = FogCloud(source_entity_uuid=uuid4(), cast_at_level=3).get_world_effect_profile(None)

    assert base is not None
    assert upcast is not None
    assert base.information_effects[0].radius_feet == 20
    assert base.topology_effects[0].radius_feet == 20
    assert upcast.information_effects[0].radius_feet == 60
    assert upcast.topology_effects[0].radius_feet == 60


def test_healing_potion_exposes_bonus_action_healing_and_item_depletion() -> None:
    """Potion meaning carries restoration and both authoritative resource costs."""
    item_uuid = uuid4()
    row = _action(
        "Drink Potion__item_test",
        semantic_key=(
            "content.neurodragon:action:"
            "action.consumable.healing_potion.drink@1"
        ),
        target_type=TargetType.SELF,
        costs=[BaseCost(name="Drink Potion", cost_type="bonus_actions", cost=1)],
        is_item_use=True,
        source_item_uuid=item_uuid,
        item_charge_cost=1,
        fixed_healing=7,
    )

    semantics = action_semantics_for_available_action(row)
    catalog = {}
    affordance = _build_affordance_rows_from_actions(
        "self_actions",
        [row],
        catalog,
    )[0]

    assert semantics.semantic_id == "support.heal"
    assert ActionTag.SUPPORT_HEAL in semantics.tags
    assert ActionTag.RESOURCE_SPEND in semantics.tags
    assert any(
        effect.fact_id == "actor.hp"
        and effect.operation is EffectOperation.INCREASE
        and effect.value == 7
        for effect in semantics.guaranteed_effects
    )
    assert {
        (effect.resource_id, effect.operation, effect.amount)
        for effect in semantics.resource_effects
    } == {
        ("action_economy.bonus_actions", ResourceOperation.CONSUME, 1),
        (f"item_charge.{item_uuid}", ResourceOperation.CONSUME, 1),
    }
    assert affordance.cost.bonus_action_cost == 1
    assert affordance.cost.item_charge_costs == {str(item_uuid): 1}


def test_concentration_spell_describes_replacement_and_resource_consumption() -> None:
    """A concentration cast records both slot use and replacement semantics."""
    row = _action(
        "Hold Person__slot_2",
        semantic_key="dnd.spells.enchantment.HoldPerson",
        base_template_name="Hold Person",
        target_type=TargetType.ENTITY,
        action_category=ActionCategory.SPELL,
        costs=[
            BaseCost(name="Action", cost_type="actions", cost=1),
            BaseCost(name="Spell Slot", cost_type="spell_slot_2", cost=1),
        ],
        requires_concentration=True,
    )

    semantics = action_semantics_for_available_action(row)

    assert semantics.concentration_effect is not None
    assert semantics.concentration_effect.operation is ConcentrationOperation.START_OR_REPLACE
    assert ActionTag.CONTROL_HARD in semantics.tags
    assert ActionTag.CONCENTRATION_START in semantics.tags
    assert any(
        effect.outcome_kind is OutcomeKind.SAVING_THROW
        and any(
            logical.fact_id == "selected_target.condition.paralyzed"
            and logical.operation is EffectOperation.ADD
            for logical in effect.effects
        )
        for effect in semantics.stochastic_effects
    )
    assert any(
        effect.operation is ResourceOperation.CONSUME
        and effect.resource_id == "spell_slot.2"
        and effect.amount == 1
        for effect in semantics.resource_effects
    )


def test_multi_target_spell_preserves_allocation_and_repeated_target_meaning() -> None:
    """Projectile allocation is explicit rather than inferred by a policy helper."""
    row = _action(
        "Magic Missile",
        semantic_key="dnd.spells.evocation.MagicMissile",
        target_type=TargetType.MULTI_ENTITY,
        action_category=ActionCategory.SPELL,
        damage_types=["force"],
        num_projectiles=3,
        allow_same_target=True,
    )

    semantics = action_semantics_for_available_action(row)

    assert semantics.targeting.allocation is TargetAllocation.MULTI_ENTITY
    assert semantics.targeting.maximum_targets == 3
    assert semantics.targeting.allows_repeated_targets is True
    assert ActionTag.TARGET_MULTI in semantics.tags
    assert ActionTag.TARGET_REPEAT in semantics.tags


def test_damage_effect_identity_survives_affordance_transport_and_display_rename() -> None:
    """Damage protection matching receives a stable effect id through the epoch."""
    effect_id = "rules.damage.opaque_automatic_darts"
    source = _action(
        "Opaque Darts",
        semantic_key="rules.actions.opaque_automatic_darts",
        display_name="Localized harmless-looking label",
        target_type=TargetType.MULTI_ENTITY,
        action_category=ActionCategory.SPELL,
        damage_types=["force"],
        num_projectiles=3,
        allow_same_target=True,
        outcome_profile=EngineActionOutcomeProfile(
            effect_id=effect_id,
            resolution=OutcomeResolution.AUTOMATIC,
            applications=3,
            damage_rolls=(EngineDamageRollProfile(
                dice_count=1,
                die_size=4,
                flat_bonus=1,
                damage_type="force",
            ),),
        ),
    )

    catalog = {}
    affordance = _build_affordance_rows_from_actions(
        "entity_actions",
        [source],
        catalog,
    )[0]
    restored = ActionAffordance.model_validate_json(affordance.model_dump_json())

    assert restored.display_name == "Localized harmless-looking label"
    assert restored.outcome_profile is not None
    assert restored.outcome_profile.effect_id == effect_id


def test_multi_target_affordance_rejects_undisclosed_and_invalid_allocations() -> None:
    """Command allocation is fenced to subjective epoch options and rule limits."""
    first_uuid = str(uuid4())
    second_uuid = str(uuid4())
    hidden_uuid = str(uuid4())
    source = _action(
        "Opaque Darts",
        semantic_key="rules.actions.opaque_automatic_darts",
        target_type=TargetType.MULTI_ENTITY,
        action_category=ActionCategory.SPELL,
        valid_targets=[
            AvailableTarget(index=0, target_uuid=UUID(first_uuid)),
            AvailableTarget(index=1, target_uuid=UUID(second_uuid)),
        ],
        num_projectiles=3,
        allow_same_target=False,
    )
    row = _build_affordance_rows_from_actions(
        "entity_actions",
        [source],
        {},
    )[0]

    assert row.validated_extra_target_uuids((second_uuid,)) == (second_uuid,)
    with pytest.raises(ValueError, match="absent from the affordance target options"):
        row.validated_extra_target_uuids((hidden_uuid,))
    with pytest.raises(ValueError, match="unique target allocation"):
        row.validated_extra_target_uuids((first_uuid,))
    with pytest.raises(ValueError, match="allocation count"):
        row.validated_extra_target_uuids((second_uuid, second_uuid, second_uuid))


def test_single_target_affordance_rejects_additional_targets() -> None:
    """Additional UUIDs cannot be smuggled through a non-multi action row."""
    target_uuid = str(uuid4())
    source = _action(
        "Opaque Ray",
        target_type=TargetType.ENTITY,
        valid_targets=[AvailableTarget(index=0, target_uuid=UUID(target_uuid))],
    )
    row = _build_affordance_rows_from_actions("entity_actions", [source], {})[0]

    with pytest.raises(ValueError, match="multi-entity affordance"):
        row.validated_extra_target_uuids((target_uuid,))


def test_conditional_target_profile_becomes_mixed_effect_semantics() -> None:
    """Engine annotations preserve per-target benefit and harm branches."""
    profile = ActionTargetEffectProfile(
        semantic_id="spell.opaque_mixed_effect",
        branches=(
            ActionTargetEffectBranchProfile(
                effect_id="support.undead_buff",
                disposition=TargetEffectDisposition.BENEFICIAL,
                included_creature_types=frozenset({"undead"}),
                resolution=OutcomeResolution.AUTOMATIC,
                condition_fact_ids=("selected_target.condition.bless",),
                condition_semantic_keys=frozenset({"rules.conditions.Bless"}),
            ),
            ActionTargetEffectBranchProfile(
                effect_id="control.living_debuff",
                disposition=TargetEffectDisposition.HARMFUL,
                excluded_creature_types=frozenset({"undead"}),
                resolution=OutcomeResolution.SAVING_THROW,
                save_ability="charisma",
                save_dc=14,
                condition_fact_ids=("selected_target.condition.bane",),
                condition_semantic_keys=frozenset({"rules.conditions.Bane"}),
            ),
        ),
    )
    row = _action(
        "Localized mixed spell",
        semantic_key="rules.spells.OpaqueMixedEffect",
        target_type=TargetType.MULTI_ENTITY,
        action_category=ActionCategory.SPELL,
        requires_concentration=True,
        num_projectiles=4,
        allow_same_target=False,
        target_effect_profile=profile,
    )

    semantics = action_semantics_for_available_action(row)

    assert semantics.semantic_id == profile.semantic_id
    assert ActionTag.SUPPORT_BUFF in semantics.tags
    assert ActionTag.CONTROL_SOFT in semantics.tags
    assert len(semantics.target_effects) == 2
    blessing = next(
        effect
        for effect in semantics.target_effects
        if effect.disposition is EffectDisposition.BENEFICIAL
    )
    bane = next(
        effect
        for effect in semantics.target_effects
        if effect.disposition is EffectDisposition.HARMFUL
    )
    assert evaluate_fact_expression(
        blessing.applicability,
        {"selected_target.creature_type": "undead"},
    ) is TruthValue.TRUE
    assert evaluate_fact_expression(
        blessing.applicability,
        {"selected_target.creature_type": "humanoid"},
    ) is TruthValue.FALSE
    assert bane.outcome_kind is OutcomeKind.SAVING_THROW
    assert bane.save_ability == "charisma"
    assert bane.save_dc == 14
    assert bane.condition_semantic_keys == frozenset({"rules.conditions.Bane"})


def test_hide_and_aggressive_have_exact_semantic_contracts() -> None:
    """SRD mobility/stealth abilities should not fall back to unknown semantics."""
    hide = _action(
        "Localized stealth",
        semantic_key="dnd.actions.Hide",
        display_name="Cunning Action: Hide",
        action_category=ActionCategory.ABILITY,
    )
    aggressive = _action(
        "Localized close distance",
        semantic_key="dnd.monsters.traits.AggressiveMoveAction",
        display_name="Aggressive",
        target_type=TargetType.POSITION,
        action_category=ActionCategory.MOVEMENT,
        valid_targets=[AvailableTarget(index=0, position=(2, 2))],
    )

    hide_semantics = action_semantics_for_available_action(hide)
    aggressive_semantics = action_semantics_for_available_action(aggressive)

    assert hide_semantics.semantic_id == "defense.hide"
    assert {ActionTag.DEFENSE_SELF, ActionTag.SETUP_SELF, ActionTag.INFORMATION_EXPLORE}.issubset(hide_semantics.tags)
    assert any(effect.fact_id == "actor.condition.hidden" for effect in hide_semantics.guaranteed_effects)

    assert aggressive_semantics.semantic_id == "movement.aggressive"
    assert {ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_REVEAL}.issubset(aggressive_semantics.tags)
    assert aggressive_semantics.spatial is not None
    assert aggressive_semantics.spatial.movement_kind is MovementKind.VOLUNTARY


def test_quickened_spell_declares_a_typed_action_economy_transformation() -> None:
    """Quickened Spell rewrites owned spell costs without relying on UI text."""
    row = _action(
        "Opaque metamagic activation",
        semantic_key="dnd.classes.sorcerer.QuickenedSpell",
        display_name="Localized label",
        costs=[BaseCost(
            name="Metamagic",
            cost_type="actions",
            cost=0,
            resource_name="sorcery_points",
            resource_cost=2,
        )],
    )

    semantics = action_semantics_for_available_action(row)

    assert semantics.semantic_id == "transform.metamagic.quickened"
    assert ActionTag.CAPABILITY_TRANSFORM in semantics.tags
    assert len(semantics.capability_transformations) == 1
    transformation = semantics.capability_transformations[0]
    assert transformation.selector.action_categories == frozenset({"spell"})
    assert transformation.selector.required_cost_resource_ids == frozenset({
        "action_economy.actions",
    })
    assert transformation.consumed_by.action_categories == frozenset({"spell"})
    rewrite = transformation.cost_rewrites[0]
    assert rewrite.operation is CapabilityCostOperation.REPLACE
    assert rewrite.source_resource_id == "action_economy.actions"
    assert rewrite.target_resource_id == "action_economy.bonus_actions"
    assert rewrite.amount.source is CapabilityAmountSource.SOURCE_RESOURCE


def test_twinned_spell_declares_target_and_level_scaled_cost_transformations() -> None:
    """Twinned Spell exposes its target rewrite and extra cost as typed data."""
    row = _action(
        "Opaque metamagic activation",
        semantic_key="dnd.classes.sorcerer.TwinnedSpell",
        display_name="Localized label",
        costs=[BaseCost(
            name="Metamagic",
            cost_type="actions",
            cost=0,
            resource_name="sorcery_points",
            resource_cost=1,
        )],
    )

    semantics = action_semantics_for_available_action(row)

    assert semantics.semantic_id == "transform.metamagic.twinned"
    assert ActionTag.CAPABILITY_TRANSFORM in semantics.tags
    transformation = semantics.capability_transformations[0]
    assert transformation.selector.target_allocations == frozenset({
        TargetAllocation.SINGLE_ENTITY,
    })
    assert transformation.targeting_rewrite is not None
    assert transformation.targeting_rewrite.allocation is TargetAllocation.MULTI_ENTITY
    assert transformation.targeting_rewrite.minimum_targets == 2
    assert transformation.targeting_rewrite.maximum_targets == 2
    assert transformation.targeting_rewrite.allows_repeated_targets is None
    rewrite = transformation.cost_rewrites[0]
    assert rewrite.operation is CapabilityCostOperation.ADD
    assert rewrite.target_resource_id == "resource.sorcery_points"
    assert rewrite.amount.source is CapabilityAmountSource.BASE_SPELL_LEVEL
    assert rewrite.amount.offset == -1
    assert rewrite.amount.minimum == 0


def test_guardian_of_faith_declares_hostile_only_persistent_effect_scope() -> None:
    """Policies receive the engine's hostile-only guardian aura contract."""
    row = _action(
        "Guardian of Faith__slot_4",
        semantic_key="dnd.spells.conjuration.GuardianOfFaith",
        base_template_name="Guardian of Faith",
        target_type=TargetType.POSITION,
        action_category=ActionCategory.SPELL,
        costs=[
            BaseCost(name="Action", cost_type="actions", cost=1),
            BaseCost(name="Spell Slot", cost_type="spell_slot_4", cost=1),
        ],
    )

    semantics = action_semantics_for_available_action(row)

    assert semantics.semantic_id == "summon.guardian_of_faith"
    assert ActionTag.ZONE_PERSISTENT in semantics.tags
    assert semantics.targeting.allocation is TargetAllocation.POSITION
    assert semantics.targeting.affected_relationships == frozenset({AffectedRelationship.HOSTILE})
    assert semantics.targeting.effect_radius_feet == 10


def test_barbarian_setup_actions_expose_typed_benefits_and_tradeoffs() -> None:
    """Class setup meaning follows registered identity instead of display text."""
    frenzy = _action(
        "Opaque durable setup",
        semantic_key="dnd.classes.rage.Frenzy",
        display_name="Localized label",
        costs=[
            BaseCost(
                name="Setup",
                cost_type="bonus_actions",
                cost=1,
                resource_name="rage",
                resource_cost=1,
            )
        ],
    )
    reckless = _action(
        "Opaque attack setup",
        semantic_key="dnd.classes.barbarian.RecklessAttack",
        display_name="Another localized label",
    )

    frenzy_semantics = action_semantics_for_available_action(frenzy)
    reckless_semantics = action_semantics_for_available_action(reckless)

    assert ActionTag.SETUP_SELF in frenzy_semantics.tags
    assert frenzy_semantics.self_setup is not None
    assert frenzy_semantics.self_setup.duration is SelfSetupDuration.UNTIL_REMOVED
    assert frenzy_semantics.self_setup.increases_weapon_damage is True
    assert frenzy_semantics.self_setup.resistance_damage_types == frozenset({
        "bludgeoning",
        "piercing",
        "slashing",
    })
    assert frenzy_semantics.self_setup.grants_bonus_action_attack is True
    assert any(effect.fact_id == "actor.condition.frenzied" for effect in frenzy_semantics.guaranteed_effects)

    assert ActionTag.SETUP_SELF in reckless_semantics.tags
    assert reckless_semantics.self_setup is not None
    assert reckless_semantics.self_setup.duration is SelfSetupDuration.UNTIL_NEXT_TURN
    assert reckless_semantics.self_setup.grants_outgoing_attack_advantage is True
    assert reckless_semantics.self_setup.grants_incoming_attack_advantage is True
    assert reckless_semantics.self_setup.active_condition_semantic_keys == frozenset({
        "dnd.classes.barbarian.RecklessAttacking"
    })
    adjustment = reckless_semantics.self_setup.outcome_adjustments[0]
    assert adjustment.advantage_step_delta == 1
    assert adjustment.selector.action_categories == frozenset({"attack"})
    assert adjustment.selector.required_tags == frozenset({ActionTag.ATTACK_WEAPON})
    assert adjustment.selector.weapon_slots == frozenset({"MELEE_MAIN", "MELEE_OFF"})


def test_item_buffs_expose_typed_combat_outcomes_without_display_names() -> None:
    """Finite item buffs describe their durable benefits through registered identity."""
    haste_item_uuid = uuid4()
    invisibility_item_uuid = uuid4()
    haste = _action(
        "Opaque acceleration item",
        semantic_key="rules.items.localized_acceleration",
        display_name="Localized acceleration",
        costs=[BaseCost(name="Bonus Action", cost_type="bonus_actions", cost=1)],
        is_item_use=True,
        source_item_uuid=haste_item_uuid,
        item_charge_cost=1,
        self_setup_profile=ActionSelfSetupProfile(
            semantic_id="setup.haste",
            duration=ActionSetupDuration.UNTIL_REMOVED,
            maximum_duration_rounds=10,
            condition_fact_ids=("actor.condition.haste",),
            active_condition_semantic_keys=frozenset({
                "dnd.spells.transmutation.HasteEffect",
            }),
            armor_class_bonus=2,
            movement_speed_multiplier=2.0,
            extra_actions_per_turn=1,
            incapacitates_on_removal=True,
        ),
    )
    invisibility = _action(
        "Opaque concealment item",
        semantic_key="rules.items.localized_concealment",
        display_name="Localized concealment",
        costs=[BaseCost(name="Bonus Action", cost_type="bonus_actions", cost=1)],
        is_item_use=True,
        source_item_uuid=invisibility_item_uuid,
        item_charge_cost=1,
        self_setup_profile=ActionSelfSetupProfile(
            semantic_id="setup.greater_invisibility",
            duration=ActionSetupDuration.UNTIL_REMOVED,
            condition_fact_ids=("actor.condition.invisible",),
            active_condition_semantic_keys=frozenset({
                "dnd.conditions.GreaterInvisibilityEffect",
            }),
            grants_outgoing_attack_advantage=True,
            grants_incoming_attack_disadvantage=True,
            grants_invisibility=True,
            maintenance=ActionSetupMaintenanceProfile(
                trigger=ActionSetupMaintenanceTrigger.REVEALING_ACTION,
                skill_name="stealth",
                initial_dc=15,
                dc_increment_per_success=1,
                check_bonus=2,
                check_advantage=AdvantageStatus.NONE,
                failure=ActionSetupMaintenanceFailure.REMOVE_SETUP,
            ),
        ),
    )

    haste_semantics = action_semantics_for_available_action(haste)
    invisibility_semantics = action_semantics_for_available_action(invisibility)

    assert haste_semantics.semantic_id == "setup.haste"
    assert {ActionTag.SETUP_SELF, ActionTag.SUPPORT_BUFF, ActionTag.DEFENSE_SELF}.issubset(
        haste_semantics.tags
    )
    assert haste_semantics.self_setup is not None
    assert haste_semantics.self_setup.duration is SelfSetupDuration.UNTIL_REMOVED
    assert haste_semantics.self_setup.maximum_duration_rounds == 10
    assert haste_semantics.self_setup.armor_class_bonus == 2
    assert haste_semantics.self_setup.movement_speed_multiplier == 2.0
    assert haste_semantics.self_setup.extra_actions_per_turn == 1
    assert any(effect.fact_id == "actor.condition.haste" for effect in haste_semantics.guaranteed_effects)
    assert any(
        effect.resource_id == f"item_charge.{haste_item_uuid}"
        and effect.amount == 1
        for effect in haste_semantics.resource_effects
    )

    assert invisibility_semantics.semantic_id == "setup.greater_invisibility"
    assert {ActionTag.SETUP_SELF, ActionTag.SUPPORT_BUFF, ActionTag.DEFENSE_SELF}.issubset(
        invisibility_semantics.tags
    )
    assert invisibility_semantics.self_setup is not None
    assert invisibility_semantics.self_setup.grants_invisibility is True
    assert invisibility_semantics.self_setup.grants_outgoing_attack_advantage is True
    assert invisibility_semantics.self_setup.grants_incoming_attack_disadvantage is True
    assert invisibility_semantics.self_setup.maintenance == SelfSetupMaintenanceSemantics(
        trigger=SetupMaintenanceTrigger.REVEALING_ACTION,
        skill_name="stealth",
        initial_dc=15,
        dc_increment_per_success=1,
        check_bonus=2,
        check_advantage=D20CheckMode.NONE,
        failure=SetupMaintenanceFailure.REMOVE_SETUP,
    )
    assert any(
        effect.fact_id == "actor.condition.invisible"
        for effect in invisibility_semantics.guaranteed_effects
    )


def test_semantics_travel_inside_epoch_affordances_and_survive_json_round_trip() -> None:
    """The policy receives action meaning in the epoch instead of rebuilding it."""
    source = _action(
        "Move",
        semantic_key="dnd.actions.Move",
        target_type=TargetType.POSITION_PATH,
        action_category=ActionCategory.MOVEMENT,
        costs=[BaseCost(name="Movement", cost_type="movement", cost=5)],
        valid_targets=[
            AvailableTarget(index=0, position=(2, 1), path_cost=5),
            AvailableTarget(index=1, position=(3, 1), path_cost=10),
        ],
    )

    direct_catalog = {}
    direct_rows = _build_affordance_rows_from_actions("position_actions", [source], direct_catalog)
    direct_set = _affordance_set_from_buckets(
        actor_uuid="actor",
        observation_cursor=1,
        entity_actions=[],
        position_actions=direct_rows,
        self_actions=[],
        object_actions=[],
        semantic_catalog=direct_catalog,
    )
    restored = AffordanceSet.model_validate_json(direct_set.model_dump_json())
    restored_row = restored.position_actions[0]

    assert len({row.semantics_ref for row in restored.position_actions}) == 1
    assert restored.semantics_for(restored_row).semantic_id == "movement.move"
    assert restored_row.base_template_name == "Move"
    assert direct_catalog[direct_rows[0].semantics_ref].semantic_id == "movement.move"
    assert "semantics" not in restored_row.model_dump()


def test_affordance_wire_catalog_preserves_content_addressed_semantics() -> None:
    """Wire compaction cannot remove fields covered by a semantic content hash."""
    source = _action(
        "Move",
        semantic_key="dnd.actions.Move",
        target_type=TargetType.POSITION_PATH,
        action_category=ActionCategory.MOVEMENT,
        valid_targets=[AvailableTarget(index=0, position=(2, 1), path_cost=5)],
    )
    catalog = {}
    rows = _build_affordance_rows_from_actions("position_actions", [source], catalog)
    affordances = _affordance_set_from_buckets(
        actor_uuid="actor",
        observation_cursor=1,
        entity_actions=[],
        position_actions=rows,
        self_actions=[],
        object_actions=[],
        semantic_catalog=catalog,
    )
    wire_catalog = json.loads(affordances.model_dump_json())["semantic_catalog"]

    pooled = SemanticContractPool().intern_catalog(wire_catalog)

    assert set(catalog).issubset(pooled)
    assert all(pooled[reference] == semantics for reference, semantics in catalog.items())


def test_semantic_contract_pool_reuses_immutable_contracts_across_frames() -> None:
    """Repeated JSON catalogs do not allocate a new planning model every action."""
    semantics = action_semantics_for_available_action(_action(
        "Move",
        semantic_key="dnd.actions.Move",
        target_type=TargetType.POSITION_PATH,
        action_category=ActionCategory.MOVEMENT,
    ))
    reference = action_semantics_ref(semantics)
    payload = semantics.model_dump(mode="json")
    pool = SemanticContractPool()

    first = pool.intern_catalog({reference: payload})[reference]
    second = pool.intern_catalog({reference: payload})[reference]

    assert first == semantics
    assert second is first


def test_semantic_contract_pool_preserves_identity_through_affordance_validation() -> None:
    """Pydantic epoch validation retains the locally interned immutable model."""
    semantics = action_semantics_for_available_action(_action(
        "Move",
        semantic_key="dnd.actions.Move",
        target_type=TargetType.POSITION_PATH,
        action_category=ActionCategory.MOVEMENT,
    ))
    reference = action_semantics_ref(semantics)
    pool = SemanticContractPool()
    prepared = pool.intern_catalog({reference: semantics.model_dump(mode="json")})

    affordances = AffordanceSet.model_validate({
        "actor_uuid": "actor",
        "computed_at_observation_cursor": 1,
        "semantic_catalog": prepared,
    })

    assert affordances.semantic_catalog[reference] is prepared[reference]


def test_semantic_contract_pool_rejects_a_mismatched_content_reference() -> None:
    """Corrupted catalogs cannot bind unrelated meaning to a stable reference."""
    semantics = action_semantics_for_available_action(_action(
        "Move",
        semantic_key="dnd.actions.Move",
        target_type=TargetType.POSITION_PATH,
        action_category=ActionCategory.MOVEMENT,
    ))

    with pytest.raises(ValueError, match="does not match its content"):
        SemanticContractPool().intern_catalog({
            "movement.move@v1:incorrect": semantics.model_dump(mode="json"),
        })


def test_semantic_contract_pool_rejects_conflicting_content_on_a_hot_reference() -> None:
    """A cached content address cannot silently acquire different semantics."""
    move = action_semantics_for_available_action(_action(
        "Move",
        semantic_key="dnd.actions.Move",
        target_type=TargetType.POSITION_PATH,
        action_category=ActionCategory.MOVEMENT,
    ))
    dash = action_semantics_for_available_action(_action(
        "Dash",
        semantic_key="dnd.actions.Dash",
    ))
    reference = action_semantics_ref(move)
    pool = SemanticContractPool()
    pool.intern_catalog({reference: move.model_dump(mode="json")})

    with pytest.raises(ValueError, match="does not match its content"):
        pool.intern_catalog({reference: dash.model_dump(mode="json")})


def test_typed_epoch_catalog_is_replaced_with_interned_contracts() -> None:
    """Prevalidated runtime frames gain the same identity reuse as raw JSON."""
    semantics = action_semantics_for_available_action(_action(
        "Move",
        semantic_key="dnd.actions.Move",
        target_type=TargetType.POSITION_PATH,
        action_category=ActionCategory.MOVEMENT,
    ))
    reference = action_semantics_ref(semantics)
    pool = SemanticContractPool()
    pooled = pool.intern_catalog({reference: semantics.model_dump(mode="json")})[reference]
    duplicate = type(semantics).model_validate(semantics.model_dump(mode="json"))
    row = ActionAffordance(
        row_id="position|Move|pos=1,1",
        source=ActionSourceDefinition(
            source_action_id="position|Move|pos=1,1",
            bucket="position_actions",
            template_name="Move",
            semantic_key="dnd.actions.Move",
            display_name="Move",
            action_category="movement",
            target_type="position_path",
            can_afford=True,
            semantic_id=semantics.semantic_id,
            semantics_ref=reference,
        ),
    )
    epoch = DecisionEpoch(
        epoch_id="epoch-1",
        epoch_index=1,
        basis_observation_cursor=1,
        reason=DecisionEpochReason.TURN_START,
        actor_uuid="actor",
        round_number=1,
        turn_index=0,
        economy=ActionEconomyState(actor_uuid="actor"),
        affordances=AffordanceSet(
            actor_uuid="actor",
            computed_at_observation_cursor=1,
            position_actions=[row],
            semantic_catalog={reference: duplicate},
        ),
    )

    prepared = pool.prepare_epoch(epoch)

    assert isinstance(prepared, DecisionEpoch)
    assert prepared.affordances.semantic_catalog[reference] is pooled


def test_display_tags_are_deterministic() -> None:
    """Flat display tags have stable ordering across Python hash seeds."""
    semantics = action_semantics_for_available_action(_action(
        "Open Door",
        semantic_key="dnd.items.test_items.OpenDoorAction",
        is_item_use=True,
    ))

    tags = _display_tags("ability", "self", semantics)

    semantic_tags = sorted(tag.value for tag in semantics.tags)
    assert tags[:2] == ["ability", "self"]
    assert tags[2:2 + len(semantic_tags)] == semantic_tags
