"""Canonical semantic adapters for engine action discovery rows."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional

from dnd.ai.contracts.semantics import (
    AffectedRelationship,
    ActionSemanticProvenance,
    ActionSemantics,
    ActionTag,
    CapabilityAmountFormula,
    CapabilityAmountSource,
    CapabilityCostOperation,
    CapabilityCostRewrite,
    CapabilityOutcomeAdjustment,
    CapabilitySelector,
    CapabilityTargetingRewrite,
    CapabilityTransformation,
    ComparisonOperator,
    ConcentrationEffect,
    ConcentrationOperation,
    EffectDisposition,
    EffectCertainty,
    EffectOperation,
    FactExpression,
    FactOperator,
    FactPredicate,
    InformationEffect,
    InformationOperation,
    LogicalEffect,
    MovementKind,
    OutcomeKind,
    ResourceEffect,
    ResourceOperation,
    SemanticProvenanceKind,
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
    TopologyEffect,
    TopologyOperation,
    WorldEffectAnchor,
    WorldEffectScope,
    WorldEffectShape,
    unknown_action_semantics,
)
from dnd.core.base_actions import (
    ActionCategory,
    ActionSelectionParameterKind,
    AvailableActionInfo,
    TargetType,
)


SemanticBuilder = Callable[[], ActionSemantics]
StructuredSemanticBuilder = Callable[["_SemanticInput"], ActionSemantics]


@dataclass(frozen=True)
class _SemanticCost:
    """Hashable cost metadata used by the semantic contract cache."""

    cost_type: str
    amount: int
    resource_name: Optional[str]
    resource_cost: int


@dataclass(frozen=True)
class _SemanticSelectionParameter:
    """Hashable exact action-variant selector metadata."""

    kind: str
    value: int


@dataclass(frozen=True)
class _SemanticSetupMaintenance:
    """Hashable mirror of one engine-declared setup maintenance rule."""

    trigger: str
    skill_name: str
    initial_dc: int
    dc_increment_per_success: int
    check_bonus: int
    check_advantage: str
    failure: str


@dataclass(frozen=True)
class _SemanticSelfSetup:
    """Hashable mirror of one engine-declared self-setup profile."""

    semantic_id: str
    duration: str
    maximum_duration_rounds: Optional[int]
    condition_fact_ids: tuple[str, ...]
    active_condition_semantic_keys: frozenset[str]
    increases_weapon_damage: bool
    resistance_damage_types: frozenset[str]
    grants_bonus_action_attack: bool
    grants_outgoing_attack_advantage: bool
    grants_incoming_attack_advantage: bool
    grants_incoming_attack_disadvantage: bool
    armor_class_bonus: int
    movement_speed_multiplier: float
    extra_actions_per_turn: int
    grants_invisibility: bool
    incapacitates_on_removal: bool
    maintenance: Optional[_SemanticSetupMaintenance]


@dataclass(frozen=True)
class _SemanticTargetEffectBranch:
    """Hashable mirror of one engine-declared target-effect branch."""

    effect_id: str
    disposition: str
    included_creature_types: frozenset[str]
    excluded_creature_types: frozenset[str]
    resolution: str
    save_dc: Optional[int]
    save_ability: Optional[str]
    condition_fact_ids: tuple[str, ...]
    condition_semantic_keys: frozenset[str]


@dataclass(frozen=True)
class _SemanticTargetEffect:
    """Hashable mirror of an engine-owned conditional target effect."""

    semantic_id: str
    branches: tuple[_SemanticTargetEffectBranch, ...]


@dataclass(frozen=True)
class _SemanticInformationEffect:
    """Hashable mirror of one engine-declared information effect."""

    operation: str
    certainty: str
    anchor: str
    scope: str
    shape: Optional[str]
    radius_feet: Optional[int]
    sense_type: Optional[str]


@dataclass(frozen=True)
class _SemanticTopologyEffect:
    """Hashable mirror of one engine-declared topology effect."""

    operation: str
    certainty: str
    anchor: str
    scope: str
    shape: Optional[str]
    radius_feet: Optional[int]
    affects_movement: bool
    affects_vision: bool
    affects_hazards: bool


@dataclass(frozen=True)
class _SemanticWorldEffect:
    """Hashable mirror of an engine-owned world-effect profile."""

    semantic_id: str
    information_effects: tuple[_SemanticInformationEffect, ...]
    topology_effects: tuple[_SemanticTopologyEffect, ...]


@dataclass(frozen=True)
class _SemanticInput:
    """Hashable engine metadata that fully determines action meaning."""

    semantic_key: str
    action_category: ActionCategory
    target_type: TargetType
    damage_types: tuple[str, ...]
    requires_concentration: bool
    num_projectiles: Optional[int]
    allow_same_target: Optional[bool]
    is_item_use: bool
    source_item_uuid: Optional[str]
    item_charge_cost: int
    fixed_healing: Optional[int]
    self_setup: Optional[_SemanticSelfSetup]
    target_effect: Optional[_SemanticTargetEffect]
    world_effect: Optional[_SemanticWorldEffect]
    costs: tuple[_SemanticCost, ...]
    selection_parameter: Optional[_SemanticSelectionParameter]


HEALING_ACTION_KEYS = frozenset({
    (
        "content.neurodragon:action:"
        "action.consumable.healing_potion.drink@1"
    ),
    "dnd.spells.evocation.CureWounds",
    "dnd.spells.evocation.HealingWord",
    "dnd.spells.evocation.MassHeal",
    "dnd.spells.evocation.MassHealingWord",
    "dnd.spells.evocation.PrayerOfHealing",
})
BUFF_ACTION_KEYS = frozenset({
    "dnd.spells.abjuration.Aid",
    "dnd.spells.abjuration.MageArmor",
    "dnd.spells.abjuration.ShieldOfFaith",
    "dnd.spells.enchantment.Bless",
    "dnd.spells.transmutation.EnhanceAbility",
})
HARD_CONTROL_ACTION_KEYS = frozenset({
    "dnd.spells.enchantment.HoldMonster",
    "dnd.spells.enchantment.HoldPerson",
    "dnd.spells.enchantment.Sleep",
    "dnd.spells.illusion.HypnoticPattern",
})
SOFT_CONTROL_ACTION_KEYS = frozenset({
    "dnd.spells.conjuration.Grease",
    "dnd.spells.conjuration.StinkingCloud",
    "dnd.spells.conjuration.Web",
    "dnd.spells.enchantment.Bane",
    "dnd.spells.necromancy.BlindnessDeafness",
    "dnd.spells.transmutation.Slow",
    "dnd.spells.transmutation.SpikeGrowth",
})
SUMMON_ACTION_KEYS: frozenset[str] = frozenset()
PROFILE_PREFERRED_ACTION_KEYS = frozenset({
    "dnd.spells.enchantment.HoldMonster",
    "dnd.spells.enchantment.HoldPerson",
})


def action_semantics_for_available_action(row: AvailableActionInfo) -> ActionSemantics:
    """Build typed meaning from one engine discovery row.

    The registered template identity selects an action family. Structured fields
    then add targeting, resource, damage, and concentration details. Display text
    is deliberately excluded from classification.

    Args:
        row: Authoritative action-discovery information.

    Returns:
        Typed semantic description carried by the decision epoch.
    """
    return _action_semantics_for_input(_semantic_input(row))


@lru_cache(maxsize=2048)
def _action_semantics_for_input(data: _SemanticInput) -> ActionSemantics:
    """Build or reuse one immutable semantic contract from structured metadata."""
    builder = _EXACT_ACTION_BUILDERS.get(data.semantic_key)
    structured_builder = _STRUCTURED_ACTION_BUILDERS.get(data.semantic_key)
    use_profile_contract = (
        data.semantic_key in PROFILE_PREFERRED_ACTION_KEYS
        and data.target_effect is not None
    )
    semantics = (
        structured_builder(data)
        if structured_builder is not None
        else builder()
        if builder is not None and not use_profile_contract
        else _generic_action_semantics(data)
    )

    if structured_builder is not None or (builder is not None and not use_profile_contract):
        provenance = ActionSemanticProvenance(
            kind=SemanticProvenanceKind.EXACT,
            semantic_key=data.semantic_key,
            derivation="registered_exact_builder",
        )
    elif data.world_effect is not None or data.target_effect is not None or data.self_setup is not None:
        provenance = ActionSemanticProvenance(
            kind=SemanticProvenanceKind.STRUCTURED_PROFILE,
            semantic_key=data.semantic_key,
            derivation="engine_structured_effect_profile",
        )
    elif semantics.semantic_id != "action.unknown":
        provenance = ActionSemanticProvenance(
            kind=SemanticProvenanceKind.CATEGORY_FALLBACK,
            semantic_key=data.semantic_key,
            derivation="structured_category_fallback",
        )
    else:
        provenance = semantics.provenance.model_copy(update={
            "semantic_key": data.semantic_key,
        })

    tags = set(semantics.tags)
    tags.update(_structured_tags(data))
    concentration = semantics.concentration_effect
    if data.requires_concentration:
        concentration = ConcentrationEffect(
            operation=ConcentrationOperation.START_OR_REPLACE,
            spell_semantic_id=semantics.semantic_id,
        )
        tags.add(ActionTag.CONCENTRATION_START)

    return semantics.model_copy(update={
        "provenance": provenance,
        "tags": frozenset(tags),
        "resource_effects": (*semantics.resource_effects, *_resource_effects(data)),
        "concentration_effect": concentration,
        "targeting": _targeting_semantics(data, semantics.targeting),
    })


@lru_cache(maxsize=1)
def end_turn_action_semantics() -> ActionSemantics:
    """Return typed meaning for the runtime-provided End Turn command."""
    return ActionSemantics(
        semantic_id="turn.end",
        tags=frozenset({ActionTag.TURN_END}),
        planning_preconditions=_predicate("actor.is_active", True),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.turn_active",
                operation=EffectOperation.SET,
                value=False,
            ),
        ),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.SELF,
            minimum_targets=1,
            maximum_targets=1,
        ),
    )


def _move_semantics() -> ActionSemantics:
    """Return semantics for ordinary voluntary movement."""
    return ActionSemantics(
        semantic_id="movement.move",
        tags=frozenset({
            ActionTag.MOVEMENT_VOLUNTARY,
            ActionTag.INFORMATION_EXPLORE,
            ActionTag.INFORMATION_REVEAL,
        }),
        planning_preconditions=_all(
            _predicate("route.to_selected_target.exists", True),
            _predicate(
                "actor.movement_remaining",
                comparison=ComparisonOperator.GREATER_OR_EQUAL,
                expected_fact_id="selected_target.path_cost",
            ),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.position",
                operation=EffectOperation.SET_FROM_TARGET,
                value_ref="selected_target.position",
            ),
        ),
        spatial=SpatialSemantics(
            movement_kind=MovementKind.VOLUNTARY,
            moves_actor=True,
        ),
        information_effects=(
            InformationEffect(
                operation=InformationOperation.REVEAL_FRONTIER,
                certainty=EffectCertainty.POTENTIAL,
                anchor=WorldEffectAnchor.SELECTED_TARGET,
                scope=WorldEffectScope.FRONTIER,
                scope_ref="selected_target.observation_frontier",
            ),
        ),
    )


def _dash_semantics() -> ActionSemantics:
    """Return semantics for extending current-turn movement."""
    return ActionSemantics(
        semantic_id="mobility.dash",
        tags=frozenset({ActionTag.MOBILITY_EXTEND}),
        planning_preconditions=_predicate("actor.speed", 0, ComparisonOperator.GREATER_THAN),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.movement_remaining",
                operation=EffectOperation.INCREASE,
                value_ref="actor.speed",
            ),
        ),
        spatial=SpatialSemantics(movement_kind=MovementKind.NONE),
    )


def _jump_semantics() -> ActionSemantics:
    """Return semantics for voluntary jump movement."""
    return ActionSemantics(
        semantic_id="movement.jump",
        tags=frozenset({
            ActionTag.MOVEMENT_VOLUNTARY,
            ActionTag.INFORMATION_EXPLORE,
            ActionTag.INFORMATION_REVEAL,
        }),
        planning_preconditions=_all(
            _predicate("selected_target.visible", True),
            _predicate("selected_target.landing_walkable", True),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.position",
                operation=EffectOperation.SET_FROM_TARGET,
                value_ref="selected_target.position",
            ),
        ),
        spatial=SpatialSemantics(
            movement_kind=MovementKind.VOLUNTARY,
            moves_actor=True,
        ),
        information_effects=(
            InformationEffect(
                operation=InformationOperation.REVEAL_FRONTIER,
                certainty=EffectCertainty.POTENTIAL,
                anchor=WorldEffectAnchor.SELECTED_TARGET,
                scope=WorldEffectScope.FRONTIER,
                scope_ref="selected_target.observation_frontier",
            ),
        ),
    )


def _connector_traversal_semantics() -> ActionSemantics:
    """Return semantics for one endpoint-selected atomic connector transfer."""
    return ActionSemantics(
        semantic_id="movement.connector",
        tags=frozenset({
            ActionTag.MOVEMENT_VOLUNTARY,
            ActionTag.INFORMATION_REVEAL,
        }),
        planning_preconditions=_all(
            _predicate("connector.source_is_current_position", True),
            _predicate("connector.destination_available", True),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.position",
                operation=EffectOperation.SET_FROM_TARGET,
                value_ref="connector_traversal.command.destination_position",
            ),
        ),
        spatial=SpatialSemantics(
            movement_kind=MovementKind.VOLUNTARY,
            moves_actor=True,
            ignores_intermediate_cells=True,
        ),
    )


def _dodge_semantics() -> ActionSemantics:
    """Return semantics for the defensive Dodge condition."""
    return ActionSemantics(
        semantic_id="defense.dodge",
        tags=frozenset({ActionTag.DEFENSE_SELF}),
        planning_preconditions=FactExpression.true(),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.condition.dodging",
                operation=EffectOperation.ADD,
                value=True,
            ),
        ),
    )


def _disengage_semantics() -> ActionSemantics:
    """Return semantics for suppressing voluntary-movement opportunity attacks."""
    return ActionSemantics(
        semantic_id="defense.disengage",
        tags=frozenset({ActionTag.DEFENSE_SELF}),
        planning_preconditions=FactExpression.true(),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.condition.disengaging",
                operation=EffectOperation.ADD,
                value=True,
            ),
        ),
    )


def _hide_semantics() -> ActionSemantics:
    """Return semantics for attempting to enter the Hidden state."""
    return ActionSemantics(
        semantic_id="defense.hide",
        tags=frozenset({
            ActionTag.DEFENSE_SELF,
            ActionTag.SETUP_SELF,
            ActionTag.INFORMATION_EXPLORE,
        }),
        planning_preconditions=_predicate("actor.can_hide", True),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.condition.hidden",
                operation=EffectOperation.ADD,
                value=True,
            ),
        ),
    )


def _aggressive_movement_semantics() -> ActionSemantics:
    """Return semantics for bonus-action movement toward a visible hostile."""
    return ActionSemantics(
        semantic_id="movement.aggressive",
        tags=frozenset({
            ActionTag.MOVEMENT_VOLUNTARY,
            ActionTag.INFORMATION_EXPLORE,
            ActionTag.INFORMATION_REVEAL,
        }),
        planning_preconditions=_all(
            _predicate("actor.visible_hostile_exists", True),
            _predicate("selected_target.reduces_nearest_hostile_distance", True),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.position",
                operation=EffectOperation.SET_FROM_TARGET,
                value_ref="selected_target.position",
            ),
        ),
        spatial=SpatialSemantics(
            movement_kind=MovementKind.VOLUNTARY,
            moves_actor=True,
        ),
        information_effects=(
            InformationEffect(
                operation=InformationOperation.REVEAL_FRONTIER,
                certainty=EffectCertainty.POTENTIAL,
                anchor=WorldEffectAnchor.SELECTED_TARGET,
                scope=WorldEffectScope.FRONTIER,
                scope_ref="selected_target.observation_frontier",
            ),
        ),
    )


def _drop_concentration_semantics() -> ActionSemantics:
    """Return semantics for voluntarily ending concentration."""
    return ActionSemantics(
        semantic_id="concentration.drop",
        tags=frozenset({ActionTag.CONCENTRATION_END}),
        planning_preconditions=_predicate("actor.concentrating", True),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.concentration",
                operation=EffectOperation.REMOVE,
            ),
        ),
        concentration_effect=ConcentrationEffect(operation=ConcentrationOperation.END),
    )


def _shake_awake_semantics() -> ActionSemantics:
    """Return semantics for removing magical sleep from an adjacent creature."""
    return ActionSemantics(
        semantic_id="support.shake_awake",
        tags=frozenset({ActionTag.SUPPORT_BUFF}),
        planning_preconditions=_all(
            _predicate("actor.adjacent_to_target", True),
            _predicate("selected_target.magically_asleep", True),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="selected_target.condition.magical_sleep",
                operation=EffectOperation.REMOVE,
            ),
        ),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.SINGLE_ENTITY,
            minimum_targets=1,
            maximum_targets=1,
            affected_relationships=frozenset({AffectedRelationship.ANY_ENTITY}),
        ),
    )


def _pick_up_semantics() -> ActionSemantics:
    """Return semantics for transferring an adjacent floor object to inventory."""
    return ActionSemantics(
        semantic_id="interaction.object.pick_up",
        tags=frozenset({ActionTag.INTERACTION_OBJECT, ActionTag.RESOURCE_ACQUIRE}),
        planning_preconditions=_all(
            _predicate("selected_object.pickable", True),
            _predicate("actor.adjacent_to_target", True),
            _predicate("actor.inventory.can_add_selected_object", True),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.inventory.selected_object",
                operation=EffectOperation.ADD,
                value=True,
            ),
            LogicalEffect(
                fact_id="world.floor.selected_object",
                operation=EffectOperation.REMOVE,
            ),
        ),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.OBJECT,
            minimum_targets=1,
            maximum_targets=1,
        ),
    )


def _convert_slot_to_sorcery_semantics(data: _SemanticInput) -> ActionSemantics:
    """Return Font of Magic semantics for consuming a slot to restore points."""
    slot_level = (
        data.selection_parameter.value
        if data.selection_parameter is not None
        and data.selection_parameter.kind
        == ActionSelectionParameterKind.LEVEL.value
        else 0
    )
    return ActionSemantics(
        semantic_id="resource.convert.slot_to_sorcery_points",
        tags=frozenset({ActionTag.RESOURCE_ACQUIRE, ActionTag.RESOURCE_SPEND}),
        resource_effects=(ResourceEffect(
            resource_id="resource.sorcery_points",
            operation=ResourceOperation.RESTORE,
            amount=slot_level,
        ),),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.SELF,
            minimum_targets=1,
            maximum_targets=1,
        ),
    )


def _convert_sorcery_to_slot_semantics(data: _SemanticInput) -> ActionSemantics:
    """Return Font of Magic semantics for consuming points to restore a slot."""
    slot_level = (
        data.selection_parameter.value
        if data.selection_parameter is not None
        and data.selection_parameter.kind
        == ActionSelectionParameterKind.LEVEL.value
        else 0
    )
    return ActionSemantics(
        semantic_id="resource.convert.sorcery_points_to_slot",
        tags=frozenset({ActionTag.RESOURCE_ACQUIRE, ActionTag.RESOURCE_SPEND}),
        resource_effects=(ResourceEffect(
            resource_id=f"spell_slot.{slot_level}",
            operation=ResourceOperation.RESTORE,
            amount=1,
        ),),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.SELF,
            minimum_targets=1,
            maximum_targets=1,
        ),
    )


def _open_door_semantics() -> ActionSemantics:
    """Return semantics for opening a known adjacent door."""
    return ActionSemantics(
        semantic_id="interaction.door.open",
        tags=frozenset({
            ActionTag.INTERACTION_DOOR_OPEN,
            ActionTag.INTERACTION_OBJECT,
            ActionTag.INFORMATION_REVEAL,
        }),
        planning_preconditions=_all(
            _predicate("selected_object.open", False),
            _predicate("actor.adjacent_to_target", True),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="selected_object.open",
                operation=EffectOperation.SET,
                value=True,
            ),
        ),
        topology_effects=(
            TopologyEffect(
                operation=TopologyOperation.OPEN,
                certainty=EffectCertainty.GUARANTEED,
                anchor=WorldEffectAnchor.SELECTED_OBJECT,
                scope=WorldEffectScope.TARGET,
                subject_ref="selected_object",
                affects_movement=True,
                affects_vision=True,
            ),
        ),
        information_effects=(
            InformationEffect(
                operation=InformationOperation.REVEAL_FRONTIER,
                certainty=EffectCertainty.POTENTIAL,
                anchor=WorldEffectAnchor.SELECTED_OBJECT,
                scope=WorldEffectScope.FRONTIER,
                scope_ref="selected_object.far_side",
            ),
        ),
    )


def _close_door_semantics() -> ActionSemantics:
    """Return semantics for closing a known adjacent door."""
    return ActionSemantics(
        semantic_id="interaction.door.close",
        tags=frozenset({ActionTag.INTERACTION_DOOR_CLOSE, ActionTag.INTERACTION_OBJECT}),
        planning_preconditions=_all(
            _predicate("selected_object.open", True),
            _predicate("actor.adjacent_to_target", True),
            _predicate("selected_object.occupied", False),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="selected_object.open",
                operation=EffectOperation.SET,
                value=False,
            ),
        ),
        topology_effects=(
            TopologyEffect(
                operation=TopologyOperation.CLOSE,
                certainty=EffectCertainty.GUARANTEED,
                anchor=WorldEffectAnchor.SELECTED_OBJECT,
                scope=WorldEffectScope.TARGET,
                subject_ref="selected_object",
                affects_movement=True,
                affects_vision=True,
            ),
        ),
    )


def _deactivate_hazard_semantics() -> ActionSemantics:
    """Return semantics for disabling a known linked hazard region."""
    return ActionSemantics(
        semantic_id="interaction.trap.deactivate",
        tags=frozenset({
            ActionTag.INTERACTION_HAZARD_DEACTIVATE,
            ActionTag.INTERACTION_OBJECT,
        }),
        planning_preconditions=_all(
            _predicate("selected_object.usable", True),
            _predicate("actor.adjacent_to_target", True),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="selected_object.linked_hazard.active",
                operation=EffectOperation.SET,
                value=False,
            ),
        ),
        topology_effects=(
            TopologyEffect(
                operation=TopologyOperation.DEACTIVATE_HAZARD,
                certainty=EffectCertainty.GUARANTEED,
                anchor=WorldEffectAnchor.SELECTED_OBJECT,
                scope=WorldEffectScope.HAZARD_REGION,
                subject_ref="selected_object.linked_hazard_region",
                affects_hazards=True,
            ),
        ),
    )


def _shove_semantics() -> ActionSemantics:
    """Return semantics for BG3-style forced-movement Shove."""
    return ActionSemantics(
        semantic_id="control.shove",
        tags=frozenset({ActionTag.MOVEMENT_FORCED, ActionTag.CONTROL_SOFT}),
        planning_preconditions=_predicate("selected_target.shoveable", True),
        stochastic_effects=(
            StochasticEffect(
                outcome_kind=OutcomeKind.CONTESTED,
                effects=(
                    LogicalEffect(
                        fact_id="selected_target.position",
                        operation=EffectOperation.SET_FROM_TARGET,
                        value_ref="predicted_forced_movement_endpoint",
                    ),
                ),
            ),
        ),
        spatial=SpatialSemantics(
            movement_kind=MovementKind.FORCED,
            moves_target=True,
        ),
    )


def _guardian_of_faith_semantics() -> ActionSemantics:
    """Return hostile-only persistent guardian semantics from engine behavior."""
    return ActionSemantics(
        semantic_id="summon.guardian_of_faith",
        tags=frozenset({
            ActionTag.SUMMON,
            ActionTag.DAMAGE_AREA,
            ActionTag.CONTROL_SOFT,
            ActionTag.ZONE_PERSISTENT,
        }),
        planning_preconditions=_predicate("selected_target.position_legal", True),
        targeting=TargetingSemantics(
            allocation=TargetAllocation.POSITION,
            minimum_targets=1,
            maximum_targets=1,
            affected_relationships=frozenset({AffectedRelationship.HOSTILE}),
            effect_radius_feet=10,
        ),
    )


def _spike_growth_semantics() -> ActionSemantics:
    """Return persistent damaging terrain semantics for Spike Growth."""
    return ActionSemantics(
        semantic_id="control.spike_growth",
        tags=frozenset({
            ActionTag.CONTROL_SOFT,
            ActionTag.DAMAGE_AREA,
            ActionTag.ZONE_PERSISTENT,
        }),
        planning_preconditions=_predicate("selected_target.position_legal", True),
        topology_effects=(
            TopologyEffect(
                operation=TopologyOperation.CREATE_HAZARD,
                certainty=EffectCertainty.GUARANTEED,
                anchor=WorldEffectAnchor.SELECTED_POSITION,
                scope=WorldEffectScope.HAZARD_REGION,
                subject_ref="selected_position.hazard_region",
                shape=WorldEffectShape.SPHERE,
                radius_feet=20,
                affects_movement=True,
                affects_hazards=True,
            ),
        ),
    )


def _hold_person_semantics() -> ActionSemantics:
    """Return typed save-based paralysis meaning for Hold Person."""
    return _saving_throw_condition_control_semantics(
        semantic_id="control.hold_person",
        condition_fact_id="selected_target.condition.paralyzed",
        tag=ActionTag.CONTROL_HARD,
    )


def _hold_monster_semantics() -> ActionSemantics:
    """Return typed save-based paralysis meaning for Hold Monster."""
    return _saving_throw_condition_control_semantics(
        semantic_id="control.hold_monster",
        condition_fact_id="selected_target.condition.paralyzed",
        tag=ActionTag.CONTROL_HARD,
    )


def _saving_throw_condition_control_semantics(
    *,
    semantic_id: str,
    condition_fact_id: str,
    tag: ActionTag,
) -> ActionSemantics:
    """Build a hostile condition effect whose success depends on a save."""
    return ActionSemantics(
        semantic_id=semantic_id,
        tags=frozenset({tag}),
        planning_preconditions=_predicate("spell.target_valid", True),
        stochastic_effects=(
            StochasticEffect(
                outcome_kind=OutcomeKind.SAVING_THROW,
                effects=(
                    LogicalEffect(
                        fact_id=condition_fact_id,
                        operation=EffectOperation.ADD,
                        value=True,
                    ),
                ),
            ),
        ),
        targeting=TargetingSemantics(
            affected_relationships=frozenset({AffectedRelationship.HOSTILE}),
        ),
    )


def _rage_semantics() -> ActionSemantics:
    """Return typed durable setup meaning for Barbarian Rage."""
    return ActionSemantics(
        semantic_id="setup.rage",
        tags=frozenset({ActionTag.SETUP_SELF}),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.condition.raging",
                operation=EffectOperation.ADD,
                value=True,
            ),
            LogicalEffect(
                fact_id="actor.weapon_damage_bonus",
                operation=EffectOperation.INCREASE,
                value_ref="rage_damage",
            ),
            LogicalEffect(
                fact_id="actor.physical_damage_resistance",
                operation=EffectOperation.ADD,
                value=True,
            ),
        ),
        self_setup=SelfSetupSemantics(
            duration=SelfSetupDuration.UNTIL_REMOVED,
            increases_weapon_damage=True,
            resistance_damage_types=frozenset({"bludgeoning", "piercing", "slashing"}),
        ),
    )


def _end_rage_semantics() -> ActionSemantics:
    """Return exact meaning for voluntarily removing the Barbarian rage state."""
    return ActionSemantics(
        semantic_id="setup.rage.end",
        tags=frozenset({ActionTag.SETUP_SELF}),
        planning_preconditions=_any(
            _predicate("actor.condition.raging", True),
            _predicate("actor.condition.frenzied", True),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.condition.raging",
                operation=EffectOperation.REMOVE,
                value=True,
            ),
            LogicalEffect(
                fact_id="actor.condition.frenzied",
                operation=EffectOperation.REMOVE,
                value=True,
            ),
        ),
    )


def _frenzy_semantics() -> ActionSemantics:
    """Return typed durable setup meaning for Berserker Frenzy."""
    rage = _rage_semantics()
    return rage.model_copy(update={
        "semantic_id": "setup.frenzy",
        "guaranteed_effects": (
            *rage.guaranteed_effects,
            LogicalEffect(
                fact_id="actor.condition.frenzied",
                operation=EffectOperation.ADD,
                value=True,
            ),
            LogicalEffect(
                fact_id="actor.bonus_action_attack_access",
                operation=EffectOperation.ADD,
                value=True,
            ),
        ),
        "self_setup": SelfSetupSemantics(
            duration=SelfSetupDuration.UNTIL_REMOVED,
            increases_weapon_damage=True,
            resistance_damage_types=frozenset({"bludgeoning", "piercing", "slashing"}),
            grants_bonus_action_attack=True,
        ),
    })


def _reckless_attack_semantics() -> ActionSemantics:
    """Return typed current-cycle setup and exposure for Reckless Attack."""
    return ActionSemantics(
        semantic_id="setup.reckless_attack",
        tags=frozenset({ActionTag.SETUP_SELF}),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.condition.reckless_attacking",
                operation=EffectOperation.ADD,
                value=True,
            ),
            LogicalEffect(
                fact_id="actor.weapon_attack_advantage",
                operation=EffectOperation.ADD,
                value=True,
            ),
            LogicalEffect(
                fact_id="attackers.attack_advantage_against_actor",
                operation=EffectOperation.ADD,
                value=True,
            ),
        ),
        self_setup=SelfSetupSemantics(
            duration=SelfSetupDuration.UNTIL_NEXT_TURN,
            active_condition_semantic_keys=frozenset({
                "dnd.classes.barbarian.RecklessAttacking"
            }),
            grants_outgoing_attack_advantage=True,
            grants_incoming_attack_advantage=True,
            outcome_adjustments=(CapabilityOutcomeAdjustment(
                selector=CapabilitySelector(
                    action_categories=frozenset({ActionCategory.ATTACK.value}),
                    required_tags=frozenset({ActionTag.ATTACK_WEAPON}),
                    weapon_slots=frozenset({"MELEE_MAIN", "MELEE_OFF"}),
                ),
                advantage_step_delta=1,
            ),),
        ),
    )


def _quickened_spell_semantics() -> ActionSemantics:
    """Return the temporary action-to-bonus-action spell rewrite."""
    spell_selector = CapabilitySelector(
        action_categories=frozenset({ActionCategory.SPELL.value}),
        required_cost_resource_ids=frozenset({"action_economy.actions"}),
    )
    return ActionSemantics(
        semantic_id="transform.metamagic.quickened",
        tags=frozenset({ActionTag.CAPABILITY_TRANSFORM, ActionTag.SETUP_SELF}),
        capability_transformations=(CapabilityTransformation(
            transformation_id="metamagic.quickened.next_spell",
            selector=spell_selector,
            cost_rewrites=(CapabilityCostRewrite(
                operation=CapabilityCostOperation.REPLACE,
                source_resource_id="action_economy.actions",
                target_resource_id="action_economy.bonus_actions",
                amount=CapabilityAmountFormula(
                    source=CapabilityAmountSource.SOURCE_RESOURCE,
                ),
            ),),
            consumed_by=CapabilitySelector(
                action_categories=frozenset({ActionCategory.SPELL.value}),
            ),
        ),),
    )


def _twinned_spell_semantics() -> ActionSemantics:
    """Return the two-target spell rewrite and level-scaled extra cost."""
    return ActionSemantics(
        semantic_id="transform.metamagic.twinned",
        tags=frozenset({ActionTag.CAPABILITY_TRANSFORM, ActionTag.SETUP_SELF}),
        capability_transformations=(CapabilityTransformation(
            transformation_id="metamagic.twinned.next_spell",
            selector=CapabilitySelector(
                action_categories=frozenset({ActionCategory.SPELL.value}),
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
            consumed_by=CapabilitySelector(
                action_categories=frozenset({ActionCategory.SPELL.value}),
            ),
        ),),
    )


def _teleport_reposition_semantics(semantic_id: str, maximum_range_feet: int) -> ActionSemantics:
    """Return semantics for self-teleport repositioning spells."""
    return ActionSemantics(
        semantic_id=semantic_id,
        tags=frozenset({
            ActionTag.MOVEMENT_TELEPORT,
            ActionTag.INFORMATION_EXPLORE,
            ActionTag.INFORMATION_REVEAL,
        }),
        planning_preconditions=_all(
            _predicate("selected_target.visible", True),
            _predicate("selected_target.unoccupied", True),
            _predicate("selected_target.walkable", True),
            _predicate(
                "selected_target.distance_feet",
                comparison=ComparisonOperator.LESS_OR_EQUAL,
                expected_value=maximum_range_feet,
            ),
        ),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.position",
                operation=EffectOperation.SET_FROM_TARGET,
                value_ref="selected_target.position",
            ),
        ),
        spatial=SpatialSemantics(
            movement_kind=MovementKind.TELEPORT,
            moves_actor=True,
            ignores_intermediate_cells=True,
        ),
        information_effects=(
            InformationEffect(
                operation=InformationOperation.REVEAL_FRONTIER,
                certainty=EffectCertainty.POTENTIAL,
                anchor=WorldEffectAnchor.SELECTED_TARGET,
                scope=WorldEffectScope.FRONTIER,
                scope_ref="selected_target.observation_frontier",
            ),
        ),
    )


def _misty_step_semantics() -> ActionSemantics:
    """Return semantics for Misty Step's short bonus-action teleport."""
    return _teleport_reposition_semantics("movement.teleport.misty_step", 30)


def _dimension_door_semantics() -> ActionSemantics:
    """Return semantics for Dimension Door's long action teleport."""
    return _teleport_reposition_semantics("movement.teleport.dimension_door", 500)


_EXACT_ACTION_BUILDERS: dict[str, SemanticBuilder] = {
    "dnd.classes.barbarian.RecklessAttack": _reckless_attack_semantics,
    "dnd.classes.sorcerer.QuickenedSpell": _quickened_spell_semantics,
    "dnd.classes.sorcerer.TwinnedSpell": _twinned_spell_semantics,
    "dnd.classes.rage.Frenzy": _frenzy_semantics,
    "dnd.classes.rage.EndRage": _end_rage_semantics,
    "dnd.classes.rage.Rage": _rage_semantics,
    "dnd.actions.Dash": _dash_semantics,
    "dnd.actions.Disengage": _disengage_semantics,
    "dnd.actions.Dodge": _dodge_semantics,
    "dnd.actions.DropConcentration": _drop_concentration_semantics,
    "dnd.actions.PickUp": _pick_up_semantics,
    "dnd.actions.ShakeAwake": _shake_awake_semantics,
    "dnd.actions.Hide": _hide_semantics,
    "dnd.actions.Jump": _jump_semantics,
    "dnd.actions.Move": _move_semantics,
    "dnd.actions.TraverseConnector": _connector_traversal_semantics,
    "dnd.actions.Shove": _shove_semantics,
    "dnd.monsters.traits.AggressiveMoveAction": _aggressive_movement_semantics,
    "dnd.spells.conjuration.DimensionDoor": _dimension_door_semantics,
    "dnd.spells.conjuration.GuardianOfFaith": _guardian_of_faith_semantics,
    "dnd.spells.conjuration.MistyStep": _misty_step_semantics,
    "dnd.spells.enchantment.HoldMonster": _hold_monster_semantics,
    "dnd.spells.enchantment.HoldPerson": _hold_person_semantics,
    "dnd.spells.transmutation.SpikeGrowth": _spike_growth_semantics,
    "dnd.items.environment.CloseDirectionalDoorAction": _close_door_semantics,
    "dnd.items.environment.OpenDirectionalDoorAction": _open_door_semantics,
    "dnd.items.environment_interactables.CloseDoorAction": _close_door_semantics,
    "dnd.items.environment_interactables.OpenDoorAction": _open_door_semantics,
    "dnd.items.environment_interactables.PullLeverAction": _deactivate_hazard_semantics,
}


_STRUCTURED_ACTION_BUILDERS: dict[str, StructuredSemanticBuilder] = {
    "dnd.classes.sorcerer.ConvertSlotToSP": _convert_slot_to_sorcery_semantics,
    "dnd.classes.sorcerer.ConvertSPToSlot": _convert_sorcery_to_slot_semantics,
}


def _generic_action_semantics(data: _SemanticInput) -> ActionSemantics:
    """Derive conservative family meaning from structured discovery fields."""
    if data.world_effect is not None:
        return _world_effect_semantics_from_profile(data.world_effect)
    if data.target_effect is not None:
        if data.action_category is ActionCategory.ATTACK:
            return _attack_with_target_effect_semantics(data.target_effect)
        return _target_effect_semantics_from_profile(data.target_effect)
    if data.self_setup is not None:
        return _self_setup_semantics_from_profile(data.self_setup)
    if data.action_category is ActionCategory.ATTACK:
        return _generic_weapon_attack_semantics()
    if data.action_category is ActionCategory.SPELL:
        return _generic_spell_semantics(data)
    if data.action_category is ActionCategory.MOVEMENT:
        return _generic_voluntary_movement_semantics()
    if data.is_item_use and data.fixed_healing is not None and data.fixed_healing > 0:
        return ActionSemantics(
            semantic_id="support.heal",
            tags=frozenset({ActionTag.SUPPORT_HEAL}),
            planning_preconditions=_predicate("actor.hp_below_maximum", True),
            guaranteed_effects=(
                LogicalEffect(
                    fact_id="actor.hp",
                    operation=EffectOperation.INCREASE,
                    value=data.fixed_healing,
                ),
            ),
            targeting=TargetingSemantics(
                affected_relationships=frozenset({AffectedRelationship.ACTOR}),
            ),
        )
    if data.is_item_use and data.semantic_key in BUFF_ACTION_KEYS:
        return ActionSemantics(
            semantic_id="support.buff",
            tags=frozenset({ActionTag.SUPPORT_BUFF}),
            planning_preconditions=_predicate("actor.can_receive_buff", True),
        )
    if data.is_item_use:
        return ActionSemantics(
            semantic_id="interaction.object.use",
            tags=frozenset({ActionTag.INTERACTION_OBJECT}),
            planning_preconditions=_predicate("selected_object.usable", True),
        )
    return unknown_action_semantics()


def _world_effect_semantics_from_profile(
    profile: _SemanticWorldEffect,
) -> ActionSemantics:
    """Translate engine-owned information and topology effects."""
    tags: set[ActionTag] = set()
    information_effects: list[InformationEffect] = []
    for effect in profile.information_effects:
        operation = InformationOperation(effect.operation)
        if operation is InformationOperation.REVEAL_REGION:
            tags.add(ActionTag.INFORMATION_REVEAL)
        elif operation is InformationOperation.CONCEAL_REGION:
            tags.add(ActionTag.CONTROL_SOFT)
        information_effects.append(InformationEffect(
            operation=operation,
            certainty=EffectCertainty(effect.certainty),
            anchor=WorldEffectAnchor(effect.anchor),
            scope=WorldEffectScope(effect.scope),
            scope_ref=_world_effect_ref(effect.anchor, effect.scope),
            shape=WorldEffectShape(effect.shape) if effect.shape is not None else None,
            radius_feet=effect.radius_feet,
            sense_type=effect.sense_type,
        ))

    topology_effects: list[TopologyEffect] = []
    for effect in profile.topology_effects:
        operation = TopologyOperation(effect.operation)
        if operation is TopologyOperation.CREATE_BLOCKER and effect.affects_vision:
            tags.add(ActionTag.CONTROL_SOFT)
            if effect.shape is not None:
                tags.add(ActionTag.ZONE_PERSISTENT)
        topology_effects.append(TopologyEffect(
            operation=operation,
            certainty=EffectCertainty(effect.certainty),
            anchor=WorldEffectAnchor(effect.anchor),
            scope=WorldEffectScope(effect.scope),
            subject_ref=_world_effect_ref(effect.anchor, effect.scope),
            shape=WorldEffectShape(effect.shape) if effect.shape is not None else None,
            radius_feet=effect.radius_feet,
            affects_movement=effect.affects_movement,
            affects_vision=effect.affects_vision,
            affects_hazards=effect.affects_hazards,
        ))

    return ActionSemantics(
        semantic_id=profile.semantic_id,
        tags=frozenset(tags),
        information_effects=tuple(information_effects),
        topology_effects=tuple(topology_effects),
    )


def _world_effect_ref(anchor: str, scope: str) -> str:
    """Return a stable protocol reference for an engine-relative world scope."""
    return f"{anchor}.{scope}"


def _target_effect_semantics_from_profile(
    profile: _SemanticTargetEffect,
) -> ActionSemantics:
    """Translate engine-owned per-target rule branches into shared semantics."""
    tags: set[ActionTag] = set()
    effects: list[TargetEffectSemantics] = []
    for branch in profile.branches:
        disposition = EffectDisposition(branch.disposition)
        if disposition is EffectDisposition.BENEFICIAL:
            tags.add(ActionTag.SUPPORT_BUFF)
        elif disposition is EffectDisposition.HARMFUL:
            tags.add(
                ActionTag.CONTROL_HARD
                if _target_effect_branch_is_hard_control(branch)
                else ActionTag.CONTROL_SOFT
            )
        outcome_kind = {
            "automatic": OutcomeKind.GUARANTEED,
            "attack_roll": OutcomeKind.ATTACK_ROLL,
            "saving_throw": OutcomeKind.SAVING_THROW,
            "unknown": OutcomeKind.UNKNOWN,
        }[branch.resolution]
        effects.append(TargetEffectSemantics(
            effect_id=branch.effect_id,
            disposition=disposition,
            applicability=_target_creature_type_applicability(branch),
            outcome_kind=outcome_kind,
            save_dc=branch.save_dc,
            save_ability=branch.save_ability,
            effects=tuple(
                LogicalEffect(
                    fact_id=fact_id,
                    operation=EffectOperation.ADD,
                    value=True,
                )
                for fact_id in branch.condition_fact_ids
            ),
            condition_semantic_keys=branch.condition_semantic_keys,
        ))
    return ActionSemantics(
        semantic_id=profile.semantic_id,
        tags=frozenset(tags),
        planning_preconditions=_predicate("spell.target_valid", True),
        target_effects=tuple(effects),
    )


def _target_effect_branch_is_hard_control(
    branch: _SemanticTargetEffectBranch,
) -> bool:
    """Return whether a branch denies agency rather than merely impairs it."""
    hard_fragments = (
        "paralyzed",
        "incapacitated",
        "unconscious",
        "stunned",
        "hypnotic_pattern",
        "sleep",
        "banished",
    )
    normalized_keys = tuple(key.lower() for key in branch.condition_semantic_keys)
    normalized_facts = tuple(fact.lower() for fact in branch.condition_fact_ids)
    return any(
        fragment in key
        for fragment in hard_fragments
        for key in (*normalized_keys, *normalized_facts)
    )


def _attack_with_target_effect_semantics(
    profile: _SemanticTargetEffect,
) -> ActionSemantics:
    """Compose weapon damage semantics with target-effect rider metadata."""
    attack = _generic_weapon_attack_semantics()
    rider = _target_effect_semantics_from_profile(profile)
    return attack.model_copy(update={
        "semantic_id": profile.semantic_id,
        "tags": attack.tags | rider.tags,
        "guaranteed_effects": attack.guaranteed_effects + rider.guaranteed_effects,
        "conditional_effects": attack.conditional_effects + rider.conditional_effects,
        "stochastic_effects": attack.stochastic_effects + rider.stochastic_effects,
        "target_effects": rider.target_effects,
    })


def _target_creature_type_applicability(
    branch: _SemanticTargetEffectBranch,
) -> FactExpression:
    """Build the target creature-type predicate declared by one rule branch."""
    expressions: list[FactExpression] = []
    if branch.included_creature_types:
        included = tuple(
            _predicate("selected_target.creature_type", creature_type)
            for creature_type in sorted(branch.included_creature_types)
        )
        expressions.append(
            included[0]
            if len(included) == 1
            else FactExpression(operator=FactOperator.ANY, operands=included)
        )
    if branch.excluded_creature_types:
        excluded = tuple(
            _predicate("selected_target.creature_type", creature_type)
            for creature_type in sorted(branch.excluded_creature_types)
        )
        excluded_match = (
            excluded[0]
            if len(excluded) == 1
            else FactExpression(operator=FactOperator.ANY, operands=excluded)
        )
        expressions.append(FactExpression(
            operator=FactOperator.NOT,
            operands=(excluded_match,),
        ))
    if not expressions:
        return FactExpression.true()
    if len(expressions) == 1:
        return expressions[0]
    return FactExpression(operator=FactOperator.ALL, operands=tuple(expressions))


def _self_setup_semantics_from_profile(
    profile: _SemanticSelfSetup,
) -> ActionSemantics:
    """Translate an engine-owned setup profile into the shared semantic model."""
    tags = {ActionTag.SETUP_SELF, ActionTag.SUPPORT_BUFF}
    if (
        profile.armor_class_bonus > 0
        or profile.resistance_damage_types
        or profile.grants_incoming_attack_disadvantage
        or profile.grants_invisibility
    ):
        tags.add(ActionTag.DEFENSE_SELF)
    effects = [
        LogicalEffect(
            fact_id=fact_id,
            operation=EffectOperation.ADD,
            value=True,
        )
        for fact_id in profile.condition_fact_ids
    ]
    if profile.armor_class_bonus > 0:
        effects.append(LogicalEffect(
            fact_id="actor.armor_class",
            operation=EffectOperation.INCREASE,
            value=profile.armor_class_bonus,
        ))
    if profile.movement_speed_multiplier > 1.0:
        effects.append(LogicalEffect(
            fact_id="actor.movement_speed_multiplier",
            operation=EffectOperation.SET,
            value=profile.movement_speed_multiplier,
        ))
    if profile.extra_actions_per_turn > 0:
        effects.append(LogicalEffect(
            fact_id="actor.actions_per_turn",
            operation=EffectOperation.INCREASE,
            value=profile.extra_actions_per_turn,
        ))
    return ActionSemantics(
        semantic_id=profile.semantic_id,
        tags=frozenset(tags),
        guaranteed_effects=tuple(effects),
        self_setup=SelfSetupSemantics(
            duration=SelfSetupDuration(profile.duration),
            active_condition_semantic_keys=profile.active_condition_semantic_keys,
            maximum_duration_rounds=profile.maximum_duration_rounds,
            increases_weapon_damage=profile.increases_weapon_damage,
            resistance_damage_types=profile.resistance_damage_types,
            grants_bonus_action_attack=profile.grants_bonus_action_attack,
            grants_outgoing_attack_advantage=profile.grants_outgoing_attack_advantage,
            grants_incoming_attack_advantage=profile.grants_incoming_attack_advantage,
            grants_incoming_attack_disadvantage=profile.grants_incoming_attack_disadvantage,
            armor_class_bonus=profile.armor_class_bonus,
            movement_speed_multiplier=profile.movement_speed_multiplier,
            extra_actions_per_turn=profile.extra_actions_per_turn,
            grants_invisibility=profile.grants_invisibility,
            incapacitates_on_removal=profile.incapacitates_on_removal,
            maintenance=(
                SelfSetupMaintenanceSemantics(
                    trigger=SetupMaintenanceTrigger(profile.maintenance.trigger),
                    skill_name=profile.maintenance.skill_name,
                    initial_dc=profile.maintenance.initial_dc,
                    dc_increment_per_success=profile.maintenance.dc_increment_per_success,
                    check_bonus=profile.maintenance.check_bonus,
                    check_advantage=D20CheckMode(profile.maintenance.check_advantage),
                    failure=SetupMaintenanceFailure(profile.maintenance.failure),
                )
                if profile.maintenance is not None
                else None
            ),
        ),
    )


def _generic_weapon_attack_semantics() -> ActionSemantics:
    """Return conservative roll-based semantics for weapon attacks."""
    return ActionSemantics(
        semantic_id="attack.weapon",
        tags=frozenset({ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}),
        planning_preconditions=_predicate("selected_target.attackable", True),
        stochastic_effects=(
            StochasticEffect(
                outcome_kind=OutcomeKind.ATTACK_ROLL,
                effects=(
                    LogicalEffect(
                        fact_id="selected_target.hp",
                        operation=EffectOperation.DECREASE,
                        value_ref="rolled_damage",
                    ),
                ),
            ),
        ),
    )


def _generic_spell_semantics(data: _SemanticInput) -> ActionSemantics:
    """Return conservative spell meaning from structured fields and stable families."""
    tags: set[ActionTag] = set()
    semantic_id = "spell.effect"
    stochastic_effects: tuple[StochasticEffect, ...] = ()
    guaranteed_effects: tuple[LogicalEffect, ...] = ()

    if data.damage_types:
        tags.add(ActionTag.ATTACK_SPELL)
        damage_tag = _damage_tag(data.target_type)
        tags.add(damage_tag)
        semantic_id = damage_tag.value
        stochastic_effects = (
            StochasticEffect(
                outcome_kind=OutcomeKind.UNKNOWN,
                effects=(
                    LogicalEffect(
                        fact_id="selected_target.hp",
                        operation=EffectOperation.DECREASE,
                        value_ref="resolved_spell_damage",
                    ),
                ),
            ),
        )
    elif data.semantic_key in HEALING_ACTION_KEYS:
        tags.add(ActionTag.SUPPORT_HEAL)
        semantic_id = "support.heal"
        guaranteed_effects = (
            LogicalEffect(
                fact_id="selected_target.hp",
                operation=EffectOperation.INCREASE,
                value_ref="resolved_healing",
            ),
        )
    elif data.semantic_key in BUFF_ACTION_KEYS:
        tags.add(ActionTag.SUPPORT_BUFF)
        semantic_id = "support.buff"
    elif data.semantic_key in HARD_CONTROL_ACTION_KEYS:
        tags.add(ActionTag.CONTROL_HARD)
        semantic_id = "control.hard"
    elif data.semantic_key in SOFT_CONTROL_ACTION_KEYS:
        tags.add(ActionTag.CONTROL_SOFT)
        semantic_id = "control.soft"
    elif data.semantic_key in SUMMON_ACTION_KEYS:
        tags.add(ActionTag.SUMMON)
        semantic_id = "summon.creature"

    return ActionSemantics(
        semantic_id=semantic_id,
        tags=frozenset(tags),
        planning_preconditions=_predicate("spell.target_valid", True),
        guaranteed_effects=guaranteed_effects,
        stochastic_effects=stochastic_effects,
    )


def _generic_voluntary_movement_semantics() -> ActionSemantics:
    """Return conservative semantics for unregistered movement families."""
    return ActionSemantics(
        semantic_id="movement.voluntary",
        tags=frozenset({ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_REVEAL}),
        planning_preconditions=_predicate("selected_target.position_legal", True),
        guaranteed_effects=(
            LogicalEffect(
                fact_id="actor.position",
                operation=EffectOperation.SET_FROM_TARGET,
                value_ref="selected_target.position",
            ),
        ),
        spatial=SpatialSemantics(movement_kind=MovementKind.VOLUNTARY, moves_actor=True),
        information_effects=(
            InformationEffect(
                operation=InformationOperation.REVEAL_FRONTIER,
                certainty=EffectCertainty.POTENTIAL,
                anchor=WorldEffectAnchor.SELECTED_TARGET,
                scope=WorldEffectScope.FRONTIER,
                scope_ref="selected_target.observation_frontier",
            ),
        ),
    )


def _structured_tags(data: _SemanticInput) -> set[ActionTag]:
    """Return tags derived from typed discovery fields and stable family membership."""
    tags: set[ActionTag] = set()
    if data.target_type is TargetType.MULTI_ENTITY:
        tags.add(ActionTag.TARGET_MULTI)
        if data.allow_same_target:
            tags.add(ActionTag.TARGET_REPEAT)
    if data.semantic_key in HEALING_ACTION_KEYS:
        tags.add(ActionTag.SUPPORT_HEAL)
    if data.semantic_key in BUFF_ACTION_KEYS:
        tags.add(ActionTag.SUPPORT_BUFF)
    if data.semantic_key in HARD_CONTROL_ACTION_KEYS:
        tags.add(ActionTag.CONTROL_HARD)
    if data.semantic_key in SOFT_CONTROL_ACTION_KEYS:
        tags.add(ActionTag.CONTROL_SOFT)
    if data.semantic_key in SUMMON_ACTION_KEYS:
        tags.add(ActionTag.SUMMON)
    if data.damage_types:
        tags.add(_damage_tag(data.target_type))
    if any(
        cost.resource_name is not None or cost.cost_type.startswith("spell_slot_")
        for cost in data.costs
    ):
        tags.add(ActionTag.RESOURCE_SPEND)
    if data.item_charge_cost > 0:
        tags.add(ActionTag.RESOURCE_SPEND)
    return tags


def _damage_tag(target_type: TargetType) -> ActionTag:
    """Return damage shape from typed target allocation."""
    if target_type is TargetType.POSITION_AOE:
        return ActionTag.DAMAGE_AREA
    if target_type is TargetType.MULTI_ENTITY:
        return ActionTag.DAMAGE_MULTI_TARGET
    return ActionTag.DAMAGE_SINGLE_TARGET


def _targeting_semantics(
    data: _SemanticInput,
    base: TargetingSemantics,
) -> TargetingSemantics:
    """Build target-allocation meaning from typed target fields."""
    allocation_by_target_type = {
        TargetType.SELF: TargetAllocation.SELF,
        TargetType.ENTITY: TargetAllocation.SINGLE_ENTITY,
        TargetType.MULTI_ENTITY: TargetAllocation.MULTI_ENTITY,
        TargetType.OBJECT: TargetAllocation.OBJECT,
        TargetType.POSITION: TargetAllocation.POSITION,
        TargetType.POSITION_LOS: TargetAllocation.POSITION,
        TargetType.POSITION_PATH: TargetAllocation.PATH,
        TargetType.POSITION_AOE: TargetAllocation.AREA,
    }
    allocation = allocation_by_target_type[data.target_type]
    maximum = data.num_projectiles if data.target_type is TargetType.MULTI_ENTITY else 1
    return TargetingSemantics(
        allocation=allocation,
        minimum_targets=1,
        maximum_targets=maximum,
        allows_repeated_targets=bool(data.allow_same_target),
        affected_relationships=base.affected_relationships,
        effect_radius_feet=base.effect_radius_feet,
    )


def _resource_effects(data: _SemanticInput) -> tuple[ResourceEffect, ...]:
    """Translate authoritative action costs into semantic resource changes."""
    effects: list[ResourceEffect] = []
    for cost in data.costs:
        if cost.amount > 0:
            effects.append(ResourceEffect(
                resource_id=_resource_id(cost.cost_type),
                operation=ResourceOperation.CONSUME,
                amount=cost.amount,
            ))
        if cost.resource_name is not None and cost.resource_cost > 0:
            effects.append(ResourceEffect(
                resource_id=f"resource.{cost.resource_name}",
                operation=ResourceOperation.CONSUME,
                amount=cost.resource_cost,
            ))
    if data.source_item_uuid is not None and data.item_charge_cost > 0:
        effects.append(ResourceEffect(
            resource_id=f"item_charge.{data.source_item_uuid}",
            operation=ResourceOperation.CONSUME,
            amount=data.item_charge_cost,
        ))
    return tuple(effects)


def _semantic_input(row: AvailableActionInfo) -> _SemanticInput:
    """Freeze the structured fields that determine a row's semantic contract."""
    if row.costs:
        costs = tuple(
            _SemanticCost(
                cost_type=str(cost.cost_type),
                amount=int(cost.cost),
                resource_name=str(cost.resource_name) if cost.resource_name is not None else None,
                resource_cost=int(cost.resource_cost),
            )
            for cost in row.costs
        )
    else:
        costs = (
            _SemanticCost(
                cost_type=str(row.cost_type),
                amount=int(row.cost_amount),
                resource_name=None,
                resource_cost=0,
            ),
        )
    setup = row.self_setup_profile
    target_effect = row.target_effect_profile
    world_effect = row.world_effect_profile
    return _SemanticInput(
        semantic_key=row.semantic_key,
        action_category=row.action_category,
        target_type=row.target_type,
        damage_types=tuple(row.damage_types),
        requires_concentration=row.requires_concentration,
        num_projectiles=row.num_projectiles,
        allow_same_target=row.allow_same_target,
        is_item_use=row.is_item_use,
        source_item_uuid=(
            str(row.source_item_uuid)
            if row.source_item_uuid is not None
            else None
        ),
        item_charge_cost=row.item_charge_cost,
        fixed_healing=row.fixed_healing,
        self_setup=(
            _SemanticSelfSetup(
                semantic_id=setup.semantic_id,
                duration=setup.duration.value,
                maximum_duration_rounds=setup.maximum_duration_rounds,
                condition_fact_ids=tuple(setup.condition_fact_ids),
                active_condition_semantic_keys=setup.active_condition_semantic_keys,
                increases_weapon_damage=setup.increases_weapon_damage,
                resistance_damage_types=setup.resistance_damage_types,
                grants_bonus_action_attack=setup.grants_bonus_action_attack,
                grants_outgoing_attack_advantage=setup.grants_outgoing_attack_advantage,
                grants_incoming_attack_advantage=setup.grants_incoming_attack_advantage,
                grants_incoming_attack_disadvantage=setup.grants_incoming_attack_disadvantage,
                armor_class_bonus=setup.armor_class_bonus,
                movement_speed_multiplier=setup.movement_speed_multiplier,
                extra_actions_per_turn=setup.extra_actions_per_turn,
                grants_invisibility=setup.grants_invisibility,
                incapacitates_on_removal=setup.incapacitates_on_removal,
                maintenance=(
                    _SemanticSetupMaintenance(
                        trigger=setup.maintenance.trigger.value,
                        skill_name=setup.maintenance.skill_name,
                        initial_dc=setup.maintenance.initial_dc,
                        dc_increment_per_success=setup.maintenance.dc_increment_per_success,
                        check_bonus=setup.maintenance.check_bonus,
                        check_advantage=setup.maintenance.check_advantage.value,
                        failure=setup.maintenance.failure.value,
                    )
                    if setup.maintenance is not None
                    else None
                ),
            )
            if setup is not None
            else None
        ),
        target_effect=(
            _SemanticTargetEffect(
                semantic_id=target_effect.semantic_id,
                branches=tuple(
                    _SemanticTargetEffectBranch(
                        effect_id=branch.effect_id,
                        disposition=branch.disposition.value,
                        included_creature_types=branch.included_creature_types,
                        excluded_creature_types=branch.excluded_creature_types,
                        resolution=branch.resolution.value,
                        save_dc=branch.save_dc,
                        save_ability=branch.save_ability,
                        condition_fact_ids=tuple(branch.condition_fact_ids),
                        condition_semantic_keys=branch.condition_semantic_keys,
                    )
                    for branch in target_effect.branches
                ),
            )
            if target_effect is not None
            else None
        ),
        world_effect=(
            _SemanticWorldEffect(
                semantic_id=world_effect.semantic_id,
                information_effects=tuple(
                    _SemanticInformationEffect(
                        operation=effect.operation.value,
                        certainty=effect.certainty.value,
                        anchor=effect.anchor.value,
                        scope=effect.scope.value,
                        shape=effect.shape.value if effect.shape is not None else None,
                        radius_feet=effect.radius_feet,
                        sense_type=effect.sense_type,
                    )
                    for effect in world_effect.information_effects
                ),
                topology_effects=tuple(
                    _SemanticTopologyEffect(
                        operation=effect.operation.value,
                        certainty=effect.certainty.value,
                        anchor=effect.anchor.value,
                        scope=effect.scope.value,
                        shape=effect.shape.value if effect.shape is not None else None,
                        radius_feet=effect.radius_feet,
                        affects_movement=effect.affects_movement,
                        affects_vision=effect.affects_vision,
                        affects_hazards=effect.affects_hazards,
                    )
                    for effect in world_effect.topology_effects
                ),
            )
            if world_effect is not None
            else None
        ),
        costs=costs,
        selection_parameter=(
            _SemanticSelectionParameter(
                kind=row.selection_parameter.kind.value,
                value=row.selection_parameter.value,
            )
            if row.selection_parameter is not None
            else None
        ),
    )


def _resource_id(cost_type: str) -> str:
    """Normalize an engine cost type into the semantic resource namespace."""
    if cost_type.startswith("spell_slot_"):
        return f"spell_slot.{cost_type.removeprefix('spell_slot_')}"
    return f"action_economy.{cost_type}"


def _predicate(
    fact_id: str,
    expected_value: object = True,
    comparison: ComparisonOperator = ComparisonOperator.EQUALS,
    expected_fact_id: str | None = None,
) -> FactExpression:
    """Build one predicate expression for registry declarations."""
    if not isinstance(expected_value, (str, int, float, bool)) and expected_value is not None:
        expected_value = str(expected_value)
    return FactExpression(
        operator=FactOperator.PREDICATE,
        predicate=FactPredicate(
            fact_id=fact_id,
            comparison=comparison,
            expected_value=expected_value,
            expected_fact_id=expected_fact_id,
        ),
    )


def _all(*operands: FactExpression) -> FactExpression:
    """Build a conjunction expression for registry declarations."""
    return FactExpression(operator=FactOperator.ALL, operands=tuple(operands))


def _any(*operands: FactExpression) -> FactExpression:
    """Build a disjunction expression for registry declarations."""
    return FactExpression(operator=FactOperator.ANY, operands=tuple(operands))
