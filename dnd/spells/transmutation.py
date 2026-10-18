"""Transmutation spells - transforming matter and energy.

Contains: SpikeGrowth, Slow, Haste, Darkvision, JumpSpell, ExpeditiousRetreat, Disintegrate,
          EnhanceAbility, EnlargeReduce, Regenerate
"""
from dnd.core.spell_damage import roll_spell_damage, finalize_spell_damage_roll
from dnd.spells.spell_utils import spell_condition_profile, condition_save
from dnd.conditions import Restrained, Petrified

from typing import cast
from dnd.blocks.equipment import EquipmentEvent, Weapon, WeaponUnequipEvent
from dnd.core.attack_types import WeaponAttackOverride
from dnd.types.materials import Material
from dnd.core.equipment_types import WeaponKind, WeaponSet, WeaponSlot
from dnd.types.world import MovementMode
from dnd.core.base_conditions import Duration
from typing import Any, Dict, Iterable, Literal, Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID, uuid4

from pydantic import Field, PrivateAttr
from dnd.blocks.base_item import BaseItem
from dnd.core.life_types import RemainsDisposition
from dnd.core.base_block import BaseBlock
from dnd.types.physical_access import PhysicalAccess

from dnd.core.action_types import ActionSelection, EntityTargetPerception, ActionVariantFacet, selection_facet
from dnd.core.action_types import EntityDestinationSelection
from dnd.core.base_actions import (
    ActionCategory,
    ActionEvent,
    lowest_hp_first,
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    ActionInformationOperation,
    ActionWorldEffectAnchor,
    ActionWorldEffectCertainty,
    ActionWorldEffectProfile,
    ActionWorldEffectScope,
    ActionWorldEffectShape,
    BaseAction,
    BaseCost,
    Cost,
    InformationEffectProfile,
    OutcomeResolution,
    PositionDiscoveryContract,
    TargetEffectDisposition,
    TargetType,
)
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import (
    ConditionAgencyDenial,
    ConditionTag,
    DurationType,
    HazardFilter,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.spell_execution import spell_execution_scope
from dnd.types.world import OccupancyLayer
from dnd.core.action_types import (
    ActionEconomyCostType,
    HasteActionPolicy,
    RestrictedActionGrant,
    RestrictedActionKind,
)
from dnd.core.base_block import SensesType, SenseMode
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, EventQueue, Trigger, Range, RangeType, SpatialChangeEvent, Damage, Healing, ForcedMovementEvent
)
from dnd.types.abilities import AbilityName
from dnd.types.actor import ConditionState
from dnd.core.dice import AttackOutcome
from dnd.core.effect_types import EffectOrigin
from dnd.core.elevation import support_distance_feet
from dnd.core.life_types import LifeState
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.types.event_facts import LandingKind
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.core.modifiers import (
    ArithmeticFactor,
    ContextualNumericalModifier,
    NumericalModifier,
    AdvantageModifier,
    AdvantageStatus,
)
from dnd.core.values import ModifiableValue, Channel, Kind, add_modifier, parts, Row, with_rows
from dnd.core.aoe import AoEShape, Cone, Cube
from dnd.core.gridmap import get_map
from dnd.core.view import cell_visible
from dnd.entity import Entity
from dnd.conditions import Dashing, ConcentrationActionMarker, Prone
from dnd.creature_transforms import apply_incapacitated_transform, remove_modifier_ownership
from dnd.actions import (
    AttackEvent,
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_evaluator,
    entity_action_economy_cost_applier,
    commit_forced_movement,
    resolve_fall_damage,
    Move,
)
from dnd.spatial.area_conditions import AreaCondition
from dnd.spatial.ignition import apply_elemental_surface_contacts, resolve_interaction
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.spatial_effect_definitions import SpatialEffectTransitionDefinition
from dnd.spatial.transitions import bind_spatial_interactions
from dnd.spatial.environmental_conditions import WetSurface, WetSurfaceMembership, IceSurface, ElectrifiedWater, SteamCloud
from dnd.spells.surfaces import SimpleToxinSurface
from dnd.items.created_items import CreatedItemsLifetime, build_goodberry, EatGoodberry
from dnd.blocks.base_item import BaseItem
from dnd.core.events import SpatialEffectInteractionEvent
from dnd.core.aoe import Sphere
from dnd.types.spatial_effects import SpatialEffectTransitionAction, SpatialEffectInteractionOperation
from dnd.types.spatial_effects import (
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)
from dnd.spells.content_metadata import srd_condition_identity, srd_action_identity, srd_spell_identity
from dnd.spells.spell_utils import (deliver_spell_damage, spell_valid_positions, in_spell_placement_region, fire_heal_roll_result,
    living_recipients_error, placement_error, seen_point_error, selected_cast_level, target_count_error)
from dnd.types.discovery import ActorScan, ScanRecord


SPIKE_GROWTH_ZONE_CONTENT_REF = ContentRef(
    pack_id="content.srd_5_1_cc",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.spell.spike_growth",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)


class SpikeGrowthZone(AreaCondition):
    """Manage the hidden damaging terrain created by Spike Growth.

    The condition independently owns its footprint, difficult terrain, hidden
    hazard identity, and position-indexed entry damage.
    """
    name: str = Field(default="Spike Growth Zone", description="Condition name.")
    description: str = Field(
        default="Sharp spikes and thorns deal 2d4 piercing per 5ft traveled",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    has_visible_presence: bool = True
    content_ref: ContentRef = Field(default=SPIKE_GROWTH_ZONE_CONTENT_REF)
    position: Tuple[int, int]
    layer: SpatialEffectLayer = Field(default=SpatialEffectLayer.GROUND_SURFACE)
    affected_occupancy_layers: frozenset[OccupancyLayer] = frozenset({OccupancyLayer.GROUND})
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({SpatialEffectTriggerKind.ENTER}),
    )
    area: AoEShape = Sphere(radius_feet=20)
    adds_difficult_terrain: bool = Field(default=True, description="Whether the zone marks terrain as difficult.")
    hazard_filter: Optional[HazardFilter] = Field(
        default=HazardFilter.NON_SOURCE,
        description="Hazard visibility filter owned by this spatial condition.",
    )
    spell_dc: int = Field(default=10, description="Spell DC for perception to notice")
    damage_dice: str = Field(default="2d4", description="Damage dice applied on each entered tile.")

    def model_post_init(self, __context: Any) -> None:
        """Synchronize hazard concealment with the caster's spell save DC."""
        super().model_post_init(__context)
        self.condition_stealth_dc = self.spell_dc

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry damage (2d4 piercing per tile entered)."""
        source_uuid = self.source_entity_uuid
        damage_dice = self.damage_dice
        effect_id = self.content_ref.identity_key

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            if entity.uuid == source_uuid:
                return None

            count_text, separator, value_text = damage_dice.lower().partition("d")
            if (
                separator != "d"
                or not count_text.isdigit()
                or not value_text.isdigit()
            ):
                raise ValueError(f"Invalid damage dice: {damage_dice!r}")
            count, value = int(count_text), int(value_text)
            caster = Entity.get(source_uuid)
            dmg_bonus = caster.get_spell_damage_bonus() if caster else parts(ModifiableValue(
                source_entity_uuid=source_uuid, base=0, name="Spell Damage"
            ))
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=type_cast(Literal[4, 6, 8, 10, 12, 20], value), dice_numbers=count, damage_bonus=dmg_bonus,
                damage_type=DamageType.PIERCING
            )
            damage_roll = roll_spell_damage(damage_obj, parent_event=event, effect_origin=self.effect_origin, attack_outcome=AttackOutcome.HIT, crit_extra_dice=0)
            entity.receive_damage(damage_roll.total, DamageType.PIERCING, source_uuid,
                                  parent_event=event.uuid, effect_id=effect_id,
                                  independent_resolution=True, effect_origin=self.effect_origin)

            return None

        return EventHandler(
            name="Spike Growth Entry Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )


@srd_spell_identity(
    content_id="spell.spike_growth",
    display_name="Spike Growth",
    description="Transform ground into hidden damaging spikes.",
    school="transmutation",
    level=2,
    source_page=182,
    sort_order=10,
)
class SpikeGrowth(SpellAction):
    """Create a concentration zone of difficult, damaging terrain.

    The spell creates an independent `SpikeGrowthZone`, links it to
    concentration, and lets that one condition own terrain, concealment, and
    spatial-entry damage.
    """
    creates = (*SpellAction.creates, SpikeGrowthZone)
    name: str = Field(default="Spike Growth", description="Spell name.")
    description: str = Field(
        default="20ft radius difficult terrain, 2d4 piercing per 5ft traveled",
        description="Rules-facing zone summary.",
    )
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.PIERCING, description="Primary damage type for VFX")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for spike growth targeting.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=150),
        description="Maximum range for the zone center.",
    )
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Spike Growth Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action-economy costs paid to cast the spell.")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Validate target position is in range and visible."""
        return seen_point_error(self, scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Spike Growth - create zone and apply concentration."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Spike Growth at {target_pos}"
        )

        zone = SpikeGrowthZone(
            source_entity_uuid=caster.uuid,
            position=target_pos,
            spell_dc=dc,
            effect_origin=execution_event.to_effect_origin(),
        )
        zone_completion = zone.activate(parent_event=effect_event)
        if (
            zone_completion is None
            or zone_completion.canceled
            or not zone.applied
        ):
            return effect_event.with_updates(
                status_message="Spike Growth could not establish its area",
            )

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)

        return effect_event.with_updates(
            status_message=f"Spike Growth active: 20ft radius at {target_pos}, difficult terrain + 2d4 damage per 5ft"
        )


class SlowedEffect(BaseCondition):
    duration: Duration = Field(default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS))
    """Apply Slow's per-target failed-save debuff bundle.

    The engine models speed, Armor Class, Dexterity-save, reaction, action or
    bonus-action lockout, and Extra Attack suppression. A repeat Wisdom save at
    turn end removes the condition on success.
    """
    name: str = Field(default="Slowed", description="Condition name.")
    description: str = Field(
        default="Speed halved, -2 AC, -2 DEX saves, no reactions, limited actions",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup, suppression, and rules filters.",
    )
    spell_dc: int = Field(default=0, description="DC for repeat WIS save")
    caster_uuid: Optional[UUID] = Field(default=None, description="UUID of the caster")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(type_cast(UUID, self.target_entity_uuid))
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target not found"
            )

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        if not target.ignore_magical_speed_reduction:
            for speed in target.action_economy.speed_values:
                modifier = ArithmeticFactor(name="Slowed", numerator=1, denominator=2,
                    source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.target_entity_uuid)
                add_modifier(speed, Channel.SELF_STATIC, Kind.FACTOR, modifier)
                outs.append((speed.uuid, modifier.uuid))

        ac_mod = NumericalModifier(
            name="Slowed",
            value=-2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        add_modifier(target.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE, ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, ac_mod.uuid))

        dex_save = target.saving_throws.get_saving_throw("dexterity")
        dex_mod = NumericalModifier(
            name="Slowed",
            value=-2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        add_modifier(dex_save.bonus, Channel.SELF_STATIC, Kind.VALUE, dex_mod)
        outs.append((dex_save.bonus.uuid, dex_mod.uuid))

        reaction_constraint_uuid = add_modifier(target.action_economy.reactions, Channel.SELF_STATIC, Kind.MAX, NumericalModifier(
                name="Slowed",
                value=0,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            ))
        outs.append((target.action_economy.reactions.uuid, reaction_constraint_uuid))

        target.action_economy.add_action_bonus_exclusion(self.uuid)
        target.action_economy.add_attack_multiplicity_limit(self.uuid, 1)

        if self.caster_uuid and self.spell_dc > 0:
            repeat_save_handler = self._create_repeat_save_handler()
            target.add_event_handler(repeat_save_handler)
            handler_uuids.append(repeat_save_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Slowed to {target.name}",
            resulting_ac=target.ac_bonus().normalized_score
        )
        return outs, handler_uuids, [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            return {"resulting_ac": target.ac_bonus().normalized_score}
        return {}

    def _release_owned_runtime_state(self, *, parent_event: Optional[Event] = None) -> None:
        """Release Slow's owned limits without recreating discarded attack credits."""
        del parent_event
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            target.action_economy.remove_action_bonus_exclusion(self.uuid)
            target.action_economy.remove_attack_multiplicity_limit(self.uuid)

    def _create_repeat_save_handler(self) -> EventHandler:
        """WIS save at end of turn to end the Slowed effect."""
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid
        effect_uuid = self.uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            slowed = target.active_conditions.get("Slowed")
            if not slowed or slowed.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Slowed", parent_event=event)
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Slowed", parent_event=event)

            return None

        return EventHandler(
            name=f"Slowed: Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_END,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=target_uuid
                )
            ],
            event_processor=processor
        )


class Slow(SpellAction):
    """Apply Slow to failed-save targets in a forty-foot cube.

    Each target resolved by AoE convolution makes a Wisdom saving throw against
    the caster's spell save DC. Failures receive an individually linked
    `SlowedEffect`, allowing concentration cleanup to remove all affected
    targets.
    """
    creates = (*SpellAction.creates, SlowedEffect)
    name: str = Field(default="Slow", description="Spell name.")
    description: str = Field(default="40ft cube, WIS save or Slowed", description="Rules-facing spell summary.")
    spell_level: int = Field(default=3, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Maximum range for the AoE origin.",
    )
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Cube area used by Slow.")
    include_self: bool = Field(default=False, description="Whether the caster can be included in the AoE.")
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")
    max_targets: int = Field(default=6, description="Maximum number of creatures Slow affects.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cube(
                size_feet=40,
                centered=True
            )

    def get_all_targets(self) -> List[UUID]:
        """Up to six creatures in the cube, lowest current HP first (plan Q4)."""
        return lowest_hp_first(super().get_all_targets(), self.max_targets)

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Declare Slow's failed-save action-economy debuff branch."""
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.slow",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.slow.debuff",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="wisdom",
                    condition_fact_ids=(
                        "selected_target.condition.slowed",
                        "selected_target.reactions_blocked",
                        "selected_target.speed_reduced",
                    ),
                    condition_semantic_keys=frozenset({"dnd.spells.transmutation.SlowedEffect"}),
                ),
            ),
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Validate target position is in LOS and range."""
        return seen_point_error(self, scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Slow to current target (called per target via convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = save_roll.bonus  # the bonus the save applied

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"WIS save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )
        if effect_event.canceled:
            return effect_event

        if success:
            return effect_event.with_updates(
                status_message=f"{target.name} resists Slow"
            )

        slowed = SlowedEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc,
            tags={ConditionTag.MAGICAL}
        )
        effect_event = self.apply_owned_condition(effect_event, slowed)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{target.name} is Slowed"
        )


class HasteLethargyEffect(BaseCondition):
    """Own the one-round incapacitation transform left when Haste ends."""

    name: str = Field(default="Haste Lethargy", description="Condition name.")
    description: str = Field(
        default="Unable to move or take actions until the lethargy ends.",
        description="Rules-facing condition summary.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags used by cleanup and rules filters.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.FULL_TURN,
        description="Haste lethargy removes the target's turn agency.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")
        outs = apply_incapacitated_transform(
            target,
            name=self.name,
            effect_source_uuid=self.source_entity_uuid,
        )
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Haste lethargy to {target.name}",
        )
        return outs, [], [], [], effect_event


class HasteEffect(BaseCondition):
    """Apply Haste's modifier bundle and cleanup lethargy.

    The effect doubles movement by adding the current base speed, grants +2 AC,
    advantage on Dexterity saves, and an explicitly restricted action budget.
    The budget never mutates ordinary actions or Extra Attack. Removal can apply
    one round of directly owned lethargy.
    """
    creates = (HasteLethargyEffect,)
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=10))
    name: str = Field(default="Haste", description="Condition name.")
    description: str = Field(
        default=(
            "Speed doubled, +2 AC, advantage on DEX saves, "
            "one restricted Haste action"
        ),
        description="Rules-facing condition summary.",
    )
    caster_uuid: Optional[UUID] = Field(default=None, description="UUID of the caster")
    apply_lethargy: bool = Field(default=True, description="Apply incapacitating lethargy when Haste ends")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(type_cast(UUID, self.target_entity_uuid))
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target not found"
            )

        outs: List[Tuple[UUID, UUID]] = []
        for speed in target.action_economy.speed_values:
            modifier = ArithmeticFactor(name="Haste", numerator=2, denominator=1,
                source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.target_entity_uuid)
            add_modifier(speed, Channel.SELF_STATIC, Kind.FACTOR, modifier)
            outs.append((speed.uuid, modifier.uuid))

        ac_mod = NumericalModifier(
            name="Haste",
            value=2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        add_modifier(target.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE, ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, ac_mod.uuid))

        dex_save = target.saving_throws.get_saving_throw("dexterity")
        dex_adv = AdvantageModifier(
            name="Haste",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        dex_mod_uuid = add_modifier(dex_save.bonus, Channel.SELF_STATIC, Kind.ADVANTAGE, dex_adv)
        outs.append((dex_save.bonus.uuid, dex_mod_uuid))

        try:
            effect_event = declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
                status_message=f"Applied Haste to {target.name}",
                resulting_ac=target.ac_bonus().normalized_score
            )
        except BaseException:
            remove_modifier_ownership(outs)
            raise
        return outs, [], [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            return {"resulting_ac": target.ac_bonus().normalized_score}
        return {}

    def _commit_application(self, effect_event: Event) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            raise RuntimeError("Prepared Haste owner disappeared")
        allowed_kinds = (
            frozenset({RestrictedActionKind.STANDARD_ACTION})
            if (
                target.action_economy.haste_action_policy
                is HasteActionPolicy.BG3_HONOUR
            )
            else frozenset(
                {
                    RestrictedActionKind.WEAPON_ATTACK,
                    RestrictedActionKind.DASH,
                    RestrictedActionKind.DISENGAGE,
                    RestrictedActionKind.HIDE,
                }
            )
        )
        target.action_economy.add_restricted_action_grant(
            RestrictedActionGrant(
                grant_id="haste",
                owner_uuid=self.uuid,
                resource_name="haste_action",
                display_name="Haste",
                allowed_kinds=allowed_kinds,
                replaced_cost_types=frozenset(
                    {
                        ActionEconomyCostType.ACTIONS,
                    }
                ),
            )
        )

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            target.action_economy.remove_restricted_action_grant("haste", self.uuid)

    def on_membership_changed(self, event: Event) -> None:
        """Lethargy is a consequence of committed removal, never failed admission."""
        if self.applied:
            return
        release = BaseBlock._terminal_release.get()
        if release is not None and release.entity_uuid == self.target_entity_uuid:
            return
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if self.apply_lethargy and target is not None and target.is_active:
            lethargy = HasteLethargyEffect(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            )
            lethargy.duration.duration_type = DurationType.ROUNDS
            lethargy.duration.duration = 1
            target.add_condition(lethargy, parent_event=event)

class Haste(SpellAction):
    """Grant Haste to one visible target and link it to concentration.

    The target receives a `HasteEffect` linked from the caster's concentration
    condition. Cleanup removes the modifier bundle and, outside suppression
    paths, applies lethargy through the effect removal hook.
    """
    creates = (*SpellAction.creates, HasteEffect)
    name: str = Field(default="Haste", description="Spell name.")
    description: str = Field(
        default=(
            "Double speed, +2 AC, DEX advantage, and one restricted action"
        ),
        description="Rules-facing spell summary.",
    )
    spell_level: int = Field(default=3, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for the target.",
    )
    include_self: bool = True
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Validate target is in LOS and range."""
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Haste to the target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Hasting {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        haste_effect = HasteEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            tags={ConditionTag.MAGICAL}
        )
        effect_event = self.apply_owned_condition(effect_event, haste_effect)
        if effect_event.canceled:
            return effect_event


        return effect_event.with_updates(
            status_message=f"{target.name} is Hasted"
        )


class DarkvisionEffect(BaseCondition):
    """Grants 60ft darkvision to the target creature."""

    name: str = Field(default="Darkvision", description="Condition name.")
    description: str = Field(default="You can see in darkness within 60 feet", description="Condition description.")
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=4800))
    _granted_sense_mode: SenseMode | None = PrivateAttr(default=None)
    _sense_changed: bool = PrivateAttr(default=False)

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Sense recipient missing")
        return [], [], [], [], event.phase_to(EventPhase.EFFECT, update={"condition": self})

    def _commit_application(self, event: Event) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            raise RuntimeError("Admitted sense recipient disappeared")
        self._granted_sense_mode = SenseMode(sense_type=SensesType.DARKVISION, range_feet=60, contribution_owner_uuid=self.uuid)
        target.senses.add_sense_mode_source(self.uuid, self._granted_sense_mode)
        self._sense_changed = True

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None and self._granted_sense_mode is not None:
            target.senses.remove_sense_mode_source(self.uuid)
            self._granted_sense_mode = None
            self._sense_changed = True

    def on_membership_changed(self, event: Event) -> None:
        changed, self._sense_changed = self._sense_changed, False
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if changed and target is not None:
            target._notify_perceivability_changed(parent_event=event.uuid)


class DarkvisionSpell(SpellAction):
    """Second-level transmutation spell that grants 60-foot darkvision."""
    creates = (*SpellAction.creates, DarkvisionEffect)

    name: str = Field(default="Darkvision", description="Spell name.")
    description: str = Field(default="Grant 60ft darkvision to a willing creature", description="Spell description.")
    spell_level: int = Field(default=2, description="Spell slot level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Spell range.")
    valid_target_filter: str = Field(default="self_or_allies", description="Valid target filter key.")

    include_self: bool = True

    entity_target_perception: EntityTargetPerception = EntityTargetPerception.TOUCH_CONTACT

    def get_world_effect_profile(self) -> ActionWorldEffectProfile:
        """Declare the granted darkvision sense and possible discoveries.

        Args:
            actor: Entity discovering the spell. The sense contract is fixed.

        Returns:
            Typed information effects matching the runtime sense mode.
        """
        return ActionWorldEffectProfile(
            semantic_id="information.darkvision",
            information_effects=(
                InformationEffectProfile(
                    operation=ActionInformationOperation.GRANT_SENSE,
                    certainty=ActionWorldEffectCertainty.GUARANTEED,
                    anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
                    scope=ActionWorldEffectScope.TARGET,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=60,
                    sense_type=SensesType.DARKVISION.name.lower(),
                ),
                InformationEffectProfile(
                    operation=ActionInformationOperation.REVEAL_REGION,
                    certainty=ActionWorldEffectCertainty.CONDITIONAL,
                    anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
                    scope=ActionWorldEffectScope.REGION,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=60,
                ),
            ),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} grants darkvision to {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        darkvision_effect = DarkvisionEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        effect_event = self.apply_owned_condition(effect_event, darkvision_effect)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{target.name} gains darkvision (60ft)"
        )


class Disintegrate(SpellAction):
    """Resolve Disintegrate's Dexterity save and force damage.

    Failed saves take 10d6 plus 40 force damage at the base slot level.
    Upcasting adds 3d6 per slot above sixth. Successful saves take no damage.
    """
    name: str = Field(default="Disintegrate", description="Spell name.")
    description: str = Field(
        default="DEX save or 10d6+40 force damage. 0 on save.",
        description="Rules-facing damage summary.",
    )
    spell_level: int = Field(default=6, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.CREATURE_OR_OBJECT, description="Targeting mode.")
    object_target_policy: Literal["damageable", "active"] = "active"
    physical_access: Optional[PhysicalAccess] = PhysicalAccess.PROJECTILE
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Maximum ray range.",
    )
    projectile_type: Optional[str] = Field(default="ray", description="Client-facing projectile visual key.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FORCE, description="Primary damage type for VFX")

    include_self: bool = Field(default=False, description="Whether the caster can be included as a target.")
    valid_target_filter: str = Field(default="enemies", description="Target filter key for available action discovery.")

    base_damage_dice: int = Field(default=10, description="Number of d6 damage dice before upcasting.")
    base_damage_bonus: int = Field(default=40, description="Flat force damage bonus on a failed save.")

    def get_damage_dice_count(self) -> int:
        """10d6 base + 3d6 per level above 6th."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus * 3

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A seen creature in range, or an active, reachable, seen, nonmagical placed object."""
        error = self.single_recipient_error(scan, selection)
        recipient = BaseBlock.get(selection.target_uuids[0]) if selection.target_uuids else None
        if error is not None or not isinstance(recipient, BaseItem):
            return error
        source = Entity.get(self.source_entity_uuid)
        contact = source.senses.objects.get(recipient.uuid) if source is not None else None
        if contact is None or not contact.visual:
            return "Disintegrate requires a target you can see"
        return recipient.disintegration_error()

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        recipient = BaseBlock.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if isinstance(recipient, BaseItem):
            effect = execution_event.phase_to(EventPhase.EFFECT)
            if effect.canceled:
                return effect
            return (effect.with_updates(status_message=f"{recipient.name} disintegrated")
                    if recipient.disintegrate(effect) else effect.cancel(status_message="Object retirement was refused"))
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        num_dice = self.get_damage_dice_count()

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            target_entity_name=target.name,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if effect_event.canceled:
            return effect_event
        if success:
            return effect_event.with_updates(
                status_message=f"{target.name} dodges the ray"
            )

        damage_bonus = with_rows(caster.get_spell_damage_bonus(), (Row(Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            name="Disintegrate flat damage", value=self.base_damage_bonus)),))
        force_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FORCE
        )
        damage_dice = force_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = finalize_spell_damage_roll(force_damage, damage_dice.roll, parent_event=execution_event, effect_origin=self.effect_origin)
        final_damage = damage_roll.total

        target.receive_damage(
            amount=final_damage,
            damage_type=DamageType.FORCE,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid,
            damage_rolls=[damage_roll], damages=[force_damage],
            effect_origin=effect_event.to_effect_origin(),
            zero_hp_disposition=RemainsDisposition.DISINTEGRATED,
        )

        return effect_event.with_updates(
            damages=[force_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Disintegrate deals {final_damage} force damage to {target.name}"
        )


class JumpEffect(BaseCondition):
    """Triples the target's jump distance.

    Adds +2 to `entity.jump_distance_multiplier`, whose base value is 1.
    """
    name: str = Field(default="Jump", description="Condition name.")
    description: str = Field(default="Jump distance tripled", description="Rules-facing condition summary.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        outs: List[Tuple[UUID, UUID]] = []
        mod = NumericalModifier(
            name="Jump Spell",
            value=2,
            source_entity_uuid=self.source_entity_uuid or target.uuid,
            target_entity_uuid=target.uuid
        )
        mod_uuid = add_modifier(target.jump_distance_multiplier, Channel.SELF_STATIC, Kind.VALUE, mod)
        outs.append((target.jump_distance_multiplier.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self}
        ) if declaration_event else None

        return outs, [], [], [], effect_event


class JumpSpell(SpellAction):
    """Triple one creature's jump distance while concentration lasts."""
    creates = (*SpellAction.creates, JumpEffect)
    name: str = Field(default="Jump", description="Spell name.")
    description: str = Field(default="Triple a creature's jump distance", description="Rules-facing spell summary.")
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Jump on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        jump_effect = JumpEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        effect_event = self.apply_owned_condition(effect_event, jump_effect)
        if effect_event.canceled:
            return effect_event


        return effect_event.with_updates(
            status_message=f"{target.name}'s jump distance tripled"
        )


class BonusDash(BaseAction):
    """Bonus action Dash granted by Expeditious Retreat."""
    creates = (Dashing,)
    name: str = Field(default="Dash (Bonus)", description="Action name.")
    description: str = Field(default="Dash as a bonus action", description="Action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Bonus Dash", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action-economy costs paid to take the bonus Dash.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None
        return ActionEvent(
            name=self.name or "Dash (Bonus)",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        dashing = Dashing(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        dashing.duration.duration_type = DurationType.ROUNDS
        dashing.duration.duration = 1
        entity.add_condition(dashing, parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{entity.name} dashes as a bonus action"
        )

    def _apply_costs(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


class ExpeditiousRetreatEffect(BaseCondition):
    """Grants a bonus action Dash each turn."""
    creates = (BonusDash,)
    name: str = Field(default="Expeditious Retreat", description="Condition name.")
    description: str = Field(default="You can Dash as a bonus action", description="Rules-facing condition summary.")
    _action_uuid: UUID | None = PrivateAttr(default=None)

    def _apply(self, declaration_event: Event):
        return [], [], [], [], declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})

    def _commit_application(self, event: Event) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            action = BonusDash(source_entity_uuid=target.uuid, template=True,
                               contribution_owner_uuid=self.uuid)
            target.register_action(action)
            self._action_uuid = action.uuid

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None and self._action_uuid is not None:
            target.unregister_action_by_uuid(self._action_uuid)
        self._action_uuid = None
        super()._release_owned_runtime_state(parent_event=parent_event)


class ExpeditiousRetreat(SpellAction):
    """Grant the caster a concentration-linked bonus-action Dash template."""
    creates = (*SpellAction.creates, ExpeditiousRetreatEffect)
    name: str = Field(default="Expeditious Retreat", description="Spell name.")
    description: str = Field(default="Bonus action Dash each turn", description="Rules-facing spell summary.")
    spell_level: int = Field(default=1, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF),
        description="Self range used by action discovery and validation.",
    )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Expeditious Retreat"
        )
        if effect_event.canceled:
            return effect_event

        retreat_effect = ExpeditiousRetreatEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            tags={ConditionTag.MAGICAL}
        )
        effect_event = self.apply_owned_condition(effect_event, retreat_effect)
        if effect_event.canceled:
            return effect_event


        return effect_event.with_updates(
            status_message=f"{caster.name} can now Dash as a bonus action"
        )


class EnhanceAbilityEffect(BaseCondition):
    """Grant advantage on one ability's checks.

    The constitution variant also grants 2d6 temporary hit points.
    """
    name: str = Field(default="Enhance Ability", description="Condition name.")
    description: str = Field(default="Advantage on one ability's checks", description="Rules-facing condition summary.")
    ability_type: AbilityName = Field(default="strength", description="Ability key enhanced by the condition.")

    def snapshot_state(self) -> ConditionState:
        return super().snapshot_state().model_copy(update={"enhanced_ability": self.ability_type})

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        ability = target.ability_scores.get_ability(self.ability_type)
        mod_uuid = add_modifier(ability.ability_score, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
                name=f"Enhance Ability ({self.ability_type.title()})",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid
            ))
        outs.append((ability.ability_score.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Enhanced {self.ability_type.title()} on {target.name}"
        )

        return outs, [], [], [], effect_event

    def _commit_application(self, effect_event: Event) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return
        if self.ability_type == "constitution":
            healing = Healing(
                source_entity_uuid=self.source_entity_uuid,
                healing_dice=6, dice_numbers=2,
                healing_bonus=parts(ModifiableValue(
                    source_entity_uuid=self.source_entity_uuid, base=0, name="Bear's Endurance"
                ))
            )
            temp_hp = healing.get_dice().roll.total
            target.health.add_temporary_hit_points(temp_hp, self.source_entity_uuid, parent_event=effect_event.uuid)


class EnhanceAbility(SpellAction):
    """Apply a concentration-linked Enhance Ability effect.

    This implementation stores the selected ability on the action instance and
    applies the corresponding `EnhanceAbilityEffect` to the target.
    """
    creates = (*SpellAction.creates, EnhanceAbilityEffect)
    name: str = Field(default="Enhance Ability", description="Spell name.")
    description: str = Field(default="Advantage on one ability's checks (concentration)", description="Rules-facing spell summary.")
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")
    enhance_ability_type: AbilityName = Field(default="strength", description="Ability key selected for enhancement.")

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return tuple((ActionVariantFacet(key="ability", value=value, label=value.title()),)
                     for value in ('strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "enhance_ability_type": selection_facet(selection, "ability")}

    def get_discovery_display_name(self) -> str:
        return f"{super().get_discovery_display_name()} · {self.enhance_ability_type.title()}"

    def _create_declaration_event(
        self, parent_event: Optional[Event] = None, use_register: bool = True,
    ) -> Optional[Event]:
        """An absent or missing recipient defaults to the caster, before the declaration names it."""
        if self.target_entity_uuid is None or Entity.get(self.target_entity_uuid) is None:
            self.target_entity_uuid = self.source_entity_uuid
        event = super()._create_declaration_event(parent_event, use_register)
        if isinstance(event, SpellEvent):
            event.effect_id = f"support.enhance_ability.{self.enhance_ability_type}"
        return event

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Touch range for the recipient; no recipient means the caster."""
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        return self.target_position_error(target.position) if target is not None else None

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")


        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Enhancing {self.enhance_ability_type.title()} on {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        effect = EnhanceAbilityEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            ability_type=self.enhance_ability_type,
            tags={ConditionTag.MAGICAL}
        )
        effect_event = self.apply_owned_condition(effect_event, effect)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"Enhanced {self.enhance_ability_type.title()} on {target.name}"
        )

class EnlargeReduceEffect(BaseCondition):
    """Change target size and Strength roll advantage state.

    Enlarge increases size by one category and grants advantage on Strength
    checks and saves. Reduce decreases size by one category and grants
    disadvantage. Size-based damage dice are handled by `Entity.get_damages()`.
    """
    name: str = Field(default="Enlarge/Reduce", description="Condition name.")
    description: str = Field(default="Size changed by magic", description="Rules-facing condition summary.")
    mode: Literal["enlarge", "reduce"] = Field(default="enlarge", description="Either 'enlarge' or 'reduce'.")

    def snapshot_state(self) -> ConditionState:
        return super().snapshot_state().model_copy(update={"size_change": self.mode})

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        if self.mode == "enlarge":
            adv_value = AdvantageStatus.ADVANTAGE
        else:
            adv_value = AdvantageStatus.DISADVANTAGE

        str_ability = target.ability_scores.get_ability("strength")
        mod_uuid = add_modifier(str_ability.ability_score, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
                name=f"{'Enlarge' if self.mode == 'enlarge' else 'Reduce'} (STR checks)",
                value=adv_value,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid
            ))
        outs.append((str_ability.ability_score.uuid, mod_uuid))

        str_save = target.saving_throws.get_saving_throw("strength")
        save_mod_uuid = add_modifier(str_save.bonus, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
                name=f"{'Enlarge' if self.mode == 'enlarge' else 'Reduce'} (STR saves)",
                value=adv_value,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid
            ))
        outs.append((str_save.bonus.uuid, save_mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{'Enlarged' if self.mode == 'enlarge' else 'Reduced'} {target.name} to {target.size.value}"
        )

        return outs, [], [], [], effect_event

    def _commit_application(self, event: Event) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            target.add_temporary_size_step(self.uuid, 1 if self.mode == "enlarge" else -1)

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            target.remove_temporary_size_step(self.uuid)
        super()._release_owned_runtime_state(parent_event=parent_event)


class EnlargeReduce(SpellAction):
    """Apply Enlarge or Reduce with concentration-linked cleanup.

    Enemy targets receive a Constitution save before the size effect is applied.
    Willing targets and the caster are affected directly.
    """
    creates = (*SpellAction.creates, EnlargeReduceEffect)
    name: str = Field(default="Enlarge/Reduce", description="Spell name.")
    description: str = Field(
        default="Change creature size, STR advantage/disadvantage, +/-1d4 weapon damage",
        description="Rules-facing spell summary.",
    )
    spell_level: int = Field(default=2, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Maximum range for the target.",
    )
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")
    enlarge_mode: Literal["enlarge", "reduce"] = Field(default="enlarge", description="Either 'enlarge' or 'reduce'.")

    def get_harmful_intent(
        self, caster: Entity, targets: List[UUID],
    ) -> Tuple[bool, List[UUID]]:
        """Match the spell's existing unwilling-recipient saving throw rule."""
        unwilling = [
            target_uuid for target_uuid in dict.fromkeys(targets)
            if (target := Entity.get(target_uuid)) is not None
            and target.uuid != caster.uuid and caster.is_enemy(target)
        ]
        return bool(unwilling), unwilling

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return tuple((ActionVariantFacet(key="form", value=value, label=value.title()),) for value in ('enlarge', 'reduce'))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "enlarge_mode": selection_facet(selection, "form")}

    def get_discovery_display_name(self) -> str:
        return f"{super().get_discovery_display_name()} · {self.enlarge_mode.title()}"

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        return self.target_position_error(target.position) if target is not None else "No target specified"

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        if target.uuid != caster.uuid and caster.is_enemy(target):
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=execution_event.uuid
            )
            _, _, success = target.saving_throw(save_request)
            if success:
                return execution_event.phase_to(
                    new_phase=EventPhase.EFFECT,
                    status_message=f"{target.name} resists {self.name} (CON save)"
                )


        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{'Enlarging' if self.enlarge_mode == 'enlarge' else 'Reducing'} {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        effect = EnlargeReduceEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            mode=self.enlarge_mode,
            tags={ConditionTag.MAGICAL}
        )
        effect_event = self.apply_owned_condition(effect_event, effect)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            status_message=f"{target.name} {'enlarged' if self.enlarge_mode == 'enlarge' else 'reduced'} to {target.size.value}"
        )


def _telekinesis_destinations(action: BaseAction, scan: ActorScan,
                               selection: ActionSelection) -> Tuple[Tuple[int, int], ...]:
    """Open destinations within the 30-foot displacement of the selected creature."""
    target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
    if target is None:
        return ()
    grid = get_map()
    target_height = grid.get_support_elevation_feet(target.position)
    return tuple(cell for cell in BaseAction.relocation_destinations(action, scan, selection)
                 if grid.get_tile(*cell) is not None and support_distance_feet(
                     target.position, target_height, cell, grid.get_support_elevation_feet(cell)) <= 30)


def _telekinesis_selection_error(caster: Entity, target: Entity | None,
                                 destination: Tuple[int, int] | None) -> str | None:
    if target is None or destination is None:
        return "Choose a creature and a destination"
    if target.size is Size.GARGANTUAN:
        return "Telekinesis affects Huge or smaller creatures"
    if target.occupancy_layer is not OccupancyLayer.GROUND:
        return "Telekinesis requires a supported creature"
    contact = caster.senses.entities.get(target.uuid)
    if target.uuid != caster.uuid and (contact is None or not contact.visual):
        return "Target is not visible"
    if not cell_visible(caster.senses.cells, destination):
        return "Destination is not visible"
    grid = get_map()
    if grid.get_tile(*destination) is None:
        return "Destination has no support"
    source_height = grid.get_support_elevation_feet(caster.position)
    target_height = grid.get_support_elevation_feet(target.position)
    end_height = grid.get_support_elevation_feet(destination)
    if (support_distance_feet(caster.position, source_height, target.position, target_height) > 60
            or support_distance_feet(caster.position, source_height, destination, end_height) > 60):
        return "Target and destination must be within 60ft"
    if support_distance_feet(target.position, target_height, destination, end_height) > 30:
        return "Telekinesis displacement exceeds 30ft"
    if grid.admit_airborne_transfer(target.position, destination, target.uuid) is None:
        return "Transfer path or landing is blocked"
    return None


def _resolve_telekinetic_transfer(caster: Entity, target: Entity,
                                  destination: Tuple[int, int], parent: Event,
                                  spell_dc: int, origin: EffectOrigin | None) -> None:
    allied = caster.is_ally(target)
    if not allied:
        request = caster.create_saving_throw_request(target.uuid, "strength", spell_dc,
            parent_event=parent.uuid, saving_throw_context=SavingThrowContext(
                cause_id="spell.telekinesis", effect_id="spell.telekinesis.move", is_magical=True))
        if target.saving_throw(request)[2]:
            return
    if _telekinesis_selection_error(caster, target, destination) is not None:
        return
    grid = get_map()
    start = target.position
    path = grid.admit_airborne_transfer(start, destination, target.uuid)
    if path is None or start == destination:
        return
    delta = (destination[0] - start[0], destination[1] - start[1])
    distance = support_distance_feet(start, grid.get_support_elevation_feet(start),
        destination, grid.get_support_elevation_feet(destination))
    event = ForcedMovementEvent(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        source_entity_name=caster.name, target_entity_name=target.name,
        start_position=start, end_position=destination,
        direction=(0 if not delta[0] else (1 if delta[0] > 0 else -1),
                   0 if not delta[1] else (1 if delta[1] > 0 else -1)),
        intended_distance=distance, actual_distance=distance, disclosed_path=path,
        start_elevation_feet=grid.get_support_elevation_feet(start),
        end_elevation_feet=grid.get_support_elevation_feet(destination),
        landing_kind=LandingKind.CONTROLLED if allied else LandingKind.IMPACT,
        effect_origin=origin, cause="telekinesis", parent_event=parent.uuid,
        phase=EventPhase.DECLARATION)
    event = event.phase_to(EventPhase.EXECUTION)
    if event.canceled:
        return
    event = event.phase_to(EventPhase.EFFECT)

    def impact(landing: ForcedMovementEvent) -> None:
        packets: tuple[tuple[Literal[6, 8], int, DamageType], ...] = (
            (8, 4, DamageType.FORCE), (6, 2, DamageType.BLUDGEONING))
        for sides, count, damage_type in packets:
            damage = Damage(name="Telekinesis impact", source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, damage_dice=sides, dice_numbers=count,
                damage_bonus=parts(ModifiableValue(source_entity_uuid=caster.uuid, base=0)), damage_type=damage_type)
            roll = roll_spell_damage(damage, parent_event=parent, effect_origin=None, attack_outcome=AttackOutcome.HIT, crit_extra_dice=0)
            target.receive_damage(roll.total, damage_type, source_entity_uuid=caster.uuid,
                damage_rolls=[roll], damages=[damage], parent_event=landing.uuid,
                effect_origin=origin, independent_resolution=True)
        resolve_fall_damage(target, drop_feet=landing.drop_feet,
            source_entity_uuid=caster.uuid, parent_event=landing, knock_prone=False)
        if target.health.life_state is not LifeState.DEAD:
            request = caster.create_saving_throw_request(target.uuid, "dexterity", spell_dc,
                parent_event=landing.uuid, condition_context="Prone",
                saving_throw_context=SavingThrowContext(cause_id="spell.telekinesis",
                    effect_id="spell.telekinesis.landing", condition_id="condition.prone", is_magical=True))
            if not target.saving_throw(request)[2]:
                target.add_condition(Prone(source_entity_uuid=caster.uuid,
                    target_entity_uuid=target.uuid, effect_origin=origin), parent_event=landing)

    commit_forced_movement(target, event, parent_event=parent,
        on_landing=None if allied else impact)


@srd_action_identity(
    content_id="action.spell.telekinesis.move",
    display_name="Telekinesis: Move",
    description="Spend an action to move one creature to a supported destination.",
    parent_spell_name="Telekinesis",
    source_page=185,
    sort_order=861,
)
class TelekinesisMove(BaseAction):
    """One paid repeat, authorized by the exact active concentration marker."""
    creates = (Move, Prone)
    name: str = "Telekinesis: Move"
    description: str = "Move a creature up to 30ft; STR negates hostile movement"
    target_type: TargetType = TargetType.ENTITY
    position_selection: EntityDestinationSelection = Field(default_factory=EntityDestinationSelection)
    action_category: ActionCategory = ActionCategory.ABILITY
    valid_target_filter: str = "all"
    include_self: bool = True
    costs: List[Cost] = Field(default_factory=lambda: [Cost(name="Telekinesis move", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)])
    marker_uuid: UUID
    spell_dc: int
    effect_origin: EffectOrigin | None = None

    def _create_declaration_event(self, parent_event: Optional[Event] = None,
                                  use_register: bool = True) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if caster is None:
            return None
        harmful = target is not None and not caster.is_ally(target)
        return SpellEvent(name=self.name, description=self.description,
            event_type=EventType.BASE_ACTION, phase=EventPhase.DECLARATION,
            source_entity_uuid=caster.uuid, source_entity_name=caster.name,
            target_entity_uuid=self.target_entity_uuid, target_entity_name=target.name if target else None,
            target_position=target.position if target else None,
            declared_target_entity_uuids=[target.uuid] if target else [],
            parent_event=parent_event.uuid if parent_event else None, use_register=use_register,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            spell_id="telekinesis", spell_level=5,
            cast_at_level=(self.effect_origin.effective_spell_level or 5) if self.effect_origin else 5,
            spell_school="transmutation", target_type=TargetType.ENTITY, verbal=False,
            source_position=caster.position, effect_source_position=caster.position,
            retained_effect_origin=self.effect_origin, harmful=harmful,
            harmful_target_entity_uuids=[target.uuid] if harmful and target else [],
            save_ability="strength", save_dc=self.spell_dc, range_type="ranged", range_ft=60,
            projectile_type="ray", damage_types=[DamageType.FORCE, DamageType.BLUDGEONING])

    def _marker_active(self) -> bool:
        caster = Entity.get(self.source_entity_uuid)
        marker = caster.active_conditions_by_uuid.get(self.marker_uuid) if caster else None
        return marker is not None and marker.applied and marker.contributions_active()

    def relocation_destinations(self, scan: ActorScan, selection: ActionSelection) -> Tuple[Tuple[int, int], ...]:
        return _telekinesis_destinations(self, scan, selection)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        if len(selection.target_uuids) != 1:
            return "Choose exactly one creature"
        caster = Entity.get(self.source_entity_uuid)
        if caster is None or not self._marker_active():
            return "Telekinesis concentration has ended"
        return _telekinesis_selection_error(caster, Entity.get(selection.target_uuids[0]),
            selection.positions[0] if selection.positions else None)

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if caster is None or target is None or self.end_position is None:
            return execution_event.cancel(status_message="Creature or destination no longer available")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if not effect.canceled and self._marker_active():
            _resolve_telekinetic_transfer(caster, target, self.end_position, effect,
                self.spell_dc, self.effect_origin)
        return effect

    def _apply_costs(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


class Telekinesis(SpellAction):
    """Cast and move once; concentration grants paid, finite repeats for ten minutes."""
    creates = (*SpellAction.creates, ConcentrationActionMarker, Prone, TelekinesisMove, Move)
    harmful: Optional[bool] = True
    name: str = "Telekinesis"
    description: str = "Move a creature up to 30ft; hostile landing deals 4d8 force + 2d6 bludgeoning"
    spell_level: int = 5
    spell_school: str = "transmutation"
    concentration: bool = True
    target_type: TargetType = TargetType.ENTITY
    position_selection: EntityDestinationSelection = Field(default_factory=EntityDestinationSelection)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    valid_target_filter: str = "all"
    include_self: bool = True
    projectile_type: Optional[str] = "ray"

    def get_harmful_intent(self, caster: Entity, targets: List[UUID]) -> Tuple[bool, List[UUID]]:
        recipients = [target_uuid for target_uuid in targets
            if (target := Entity.get(target_uuid)) is not None and not caster.is_ally(target)]
        return bool(recipients), recipients

    def relocation_destinations(self, scan: ActorScan, selection: ActionSelection) -> Tuple[Tuple[int, int], ...]:
        return _telekinesis_destinations(self, scan, selection)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        if len(selection.target_uuids) != 1:
            return "Choose exactly one creature"
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return "Caster not found"
        return _telekinesis_selection_error(caster, Entity.get(selection.target_uuids[0]),
            selection.positions[0] if selection.positions else None)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if caster is None or target is None or self.end_position is None:
            return execution_event.cancel(status_message="Creature or destination no longer available")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        repeat_uuid = uuid4()
        marker = ConcentrationActionMarker(name="Telekinesis", source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid, action_uuid=repeat_uuid, action_name="Telekinesis: Move",
            duration=Duration(duration_type=DurationType.ROUNDS, duration=100), tags={ConditionTag.MAGICAL})
        effect = self.apply_owned_condition(effect, marker)
        if effect.canceled or not marker.applied:
            return effect
        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        repeat = TelekinesisMove(uuid=repeat_uuid, source_entity_uuid=caster.uuid,
            marker_uuid=marker.uuid, contribution_owner_uuid=marker.uuid, spell_dc=dc, effect_origin=marker.effect_origin, template=True)
        caster.register_action(repeat)
        _resolve_telekinetic_transfer(caster, target, self.end_position, effect, dc, marker.effect_origin)
        return effect


class RegeneratingEffect(BaseCondition):
    """Heal the target by one hit point at the start of each turn.

    The effect tracks ten combat rounds and removes itself once the counter is
    exhausted. It is not concentration-linked by the Regenerate spell.
    """
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    name: str = Field(default="Regenerating", description="Condition name.")
    description: str = Field(
        default="Regenerating: heals 1 HP at the start of each turn",
        description="Rules-facing condition summary.",
    )
    rounds_remaining: int = Field(default=10, description="Remaining combat rounds before self-removal.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Register the turn-start healing handler."""
        if not self.target_entity_uuid:
            return [], [], [], [], None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        effect_event = declaration_event.phase_to(EventPhase.EFFECT)

        handler = EventHandler(
            name="Regenerating",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    name="Regenerating Turn Start",
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid
                )
            ],
            event_processor=self._on_turn_start
        )
        target.add_event_handler(handler)

        return [], [handler.uuid], [], [], effect_event

    def _on_turn_start(self, event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
        if self.rounds_remaining <= 0 or not self.target_entity_uuid:
            return event

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return event

        if self.contributions_active():
            target.receive_healing(
                1, self.source_entity_uuid,
                source_description="Regenerate: 1 HP",
                spell_level=self.effect_origin.effective_spell_level if self.effect_origin is not None else 7,
                effect_origin=self.effect_origin,
                source_condition_uuid=self.uuid,
                parent_event=event.uuid
            )

        self.rounds_remaining -= 1
        if self.rounds_remaining <= 0:
            target.remove_condition("Regenerating", parent_event=event)

        return event


class Regenerate(SpellAction):
    """Apply Regenerate's burst heal and ongoing turn-start healing.

    The initial effect heals 4d8 plus 15 hit points. The follow-up
    `RegeneratingEffect` then heals one hit point at the start of the target's
    turns for the combat-duration approximation used by the engine.
    """
    creates = (*SpellAction.creates, RegeneratingEffect)
    name: str = Field(default="Regenerate", description="Spell name.")
    description: str = Field(default="Heal 4d8+15 instantly, then 1 HP/round for 10 rounds", description="Rules-facing healing summary.")
    spell_level: int = Field(default=7, description="Base spell level.")
    spell_school: str = Field(default="transmutation", description="Spell school.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Touch range for the target.",
    )
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    include_self: bool = Field(default=True, description="Whether self-targeting is allowed.")
    valid_target_filter: str = Field(default="self_or_allies", description="Target filter key for available action discovery.")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return self.single_recipient_error(scan, selection)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        healing = Healing(
            name="Regenerate",
            source_entity_uuid=caster.uuid,
            healing_dice=8,
            dice_numbers=4,
            healing_bonus=parts(ModifiableValue(
                source_entity_uuid=caster.uuid,
                base=15,
                name="Regenerate Healing"
            ))
        )
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Regenerate heals {target.name}"
        )
        if effect_event.canceled:
            return effect_event

        healing_roll = fire_heal_roll_result(caster.uuid, target.uuid, healing, effect_event, "Regenerate")
        actual = target.receive_healing(
            healing_roll.total, caster.uuid,
            source_description=f"Regenerate: {healing_roll.total}",
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level, effect_origin=effect_event.get_effect_origin()
        )

        regen = RegeneratingEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        effect_event = self.apply_owned_condition(effect_event, regen)
        if effect_event.canceled:
            return effect_event

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Regenerate heals {target.name} for {actual} HP + 1 HP/round"
        )


class LongstriderEffect(BaseCondition):
    description: str = "Speed increases by 10 feet until the effect ends."
    name: str = "Longstrider"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=600))

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient missing")
        modifier = NumericalModifier(name=self.name, value=10,
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid)
        owned = []
        for speed in target.action_economy.speed_values:
            add_modifier(speed, Channel.SELF_STATIC, Kind.VALUE, modifier)
            owned.append((speed.uuid, modifier.uuid))
        return owned, [], [], [], event.phase_to(EventPhase.EFFECT)


class Longstrider(SpellAction):
    creates = (*SpellAction.creates, LongstriderEffect)
    name: str = "Longstrider"
    description: str = "Touch: speed increases by 10 feet for one hour; additional recipients when upcast."
    spell_level: int = 1
    spell_school: str = "transmutation"
    target_type: TargetType = TargetType.MULTI_ENTITY
    entity_target_perception: EntityTargetPerception = EntityTargetPerception.TOUCH_CONTACT
    include_self: bool = True
    valid_target_filter: str = "self_or_allies"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))

    def get_multi_target_count(self) -> int:
        return self.alt_target_count or max(1, self.cast_at_level)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return target_count_error(self, selection, self.alt_target_count or max(1, selected_cast_level(self, selection)))

    def _apply(self, event: SpellEvent):
        effect_event = event.phase_to(EventPhase.EFFECT)
        return self.apply_owned_condition( effect_event, LongstriderEffect(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=event.target_entity_uuid))


class BarkskinEffect(BaseCondition):
    description: str = "Armor Class cannot fall below 16."
    name: str = "Barkskin"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=600))

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient missing")
        value = target.equipment.ac_bonus
        modifier = NumericalModifier(name=self.name, value=16,
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid)
        add_modifier(value, Channel.SELF_STATIC, Kind.MIN, modifier)
        return [(value.uuid, modifier.uuid)], [], [], [], event.phase_to(EventPhase.EFFECT)


class Barkskin(SpellAction):
    creates = (*SpellAction.creates, BarkskinEffect)
    name: str = "Barkskin"
    description: str = "Touch: Armor Class cannot be below 16; concentration up to one hour."
    spell_level: int = 2
    spell_school: str = "transmutation"
    concentration: bool = True
    target_type: TargetType = TargetType.ENTITY
    include_self: bool = True
    entity_target_perception: EntityTargetPerception = EntityTargetPerception.TOUCH_CONTACT
    valid_target_filter: str = "self_or_allies"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))

    def _apply(self, event: SpellEvent):
        return self.apply_owned_condition( event.phase_to(EventPhase.EFFECT), BarkskinEffect(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=event.target_entity_uuid))


class FlyEffect(BaseCondition):
    description: str = "Source-owned flying speed and ground-to-ground movement."
    name: str = "Fly"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=100))
    flying_speed: int = Field(default=60, gt=0)

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient missing")
        target.action_economy.grant_speed(self.uuid, MovementMode.FLYING, self.flying_speed)
        return [], [], [], [], event.phase_to(EventPhase.EFFECT)

    def _remove(self, event: Event | None = None):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            target.action_economy.remove_speed_grant(self.uuid)
        return super()._remove(event)

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            target.action_economy.remove_speed_grant(self.uuid)


class Fly(SpellAction):
    creates = (*SpellAction.creates, FlyEffect)
    name: str = "Fly"
    description: str = "Touch: 60-foot flying speed, concentration for 10 minutes; supported endpoints only."
    spell_level: int = 3
    spell_school: str = "transmutation"
    concentration: bool = True
    target_type: TargetType = TargetType.MULTI_ENTITY
    include_self: bool = True
    valid_target_filter: str = "self_or_allies"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))

    def get_multi_target_count(self) -> int:
        return self.alt_target_count or max(1, self.cast_at_level - 2)

    def _apply(self, event: SpellEvent):
        return self.apply_owned_condition( event.phase_to(EventPhase.EFFECT), FlyEffect(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=event.target_entity_uuid))


class ShillelaghEffect(BaseCondition):
    description: str = "Exact held weapon becomes magical, d8 with optional casting ability."
    name: str = "Shillelagh"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=10))
    weapon_uuid: UUID
    casting_ability: AbilityName

    def snapshot_state(self) -> ConditionState:
        return super().snapshot_state().model_copy(update={"affected_item_uuid": self.weapon_uuid})

    def _apply(self, event: Event):
        caster = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        weapon = cast(Weapon | None, Weapon.get(self.weapon_uuid))
        if caster is None or weapon is None:
            return [], [], [], [], event.cancel(status_message="Held weapon missing")
        weapon.attack_overrides[self.uuid] = WeaponAttackOverride(wielder_uuid=caster.uuid,
            damage_die=8, optional_ability=self.casting_ability)

        def released(transition: Event, actor_uuid: UUID):
            if transition.canceled:
                return None
            actor = Entity.get(actor_uuid)
            exact_release = isinstance(transition, WeaponUnequipEvent) and transition.item_uuid == self.weapon_uuid
            changed_set = (isinstance(transition, (AttackEvent, EquipmentEvent))
                and transition.phase is EventPhase.COMPLETION and actor is not None
                and actor.equipment.active_weapon_set is not WeaponSet.MELEE)
            if actor is not None and (exact_release or changed_set):
                actor.remove_condition_by_uuid(self.uuid, parent_event=transition)
            return None

        handler = EventHandler(name="Shillelagh release", source_entity_uuid=caster.uuid, runs_while_owner_inactive=True,
            trigger_conditions=[Trigger(event_type=EventType.WEAPON_UNEQUIP, event_phase=EventPhase.EFFECT),
                Trigger(event_type=EventType.WEAPON_EQUIP, event_phase=EventPhase.COMPLETION),
                Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.COMPLETION,
                    event_source_entity_uuid=caster.uuid)],
            event_processor=released)
        caster.add_event_handler(handler)
        return [], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        weapon = cast(Weapon | None, Weapon.get(self.weapon_uuid))
        if weapon is not None:
            weapon.attack_overrides.pop(self.uuid, None)
        super()._release_owned_runtime_state(parent_event=parent_event)


class Shillelagh(SpellAction):
    creates = (*SpellAction.creates, ShillelaghEffect)
    name: str = "Shillelagh"
    description: str = "Held wooden club/staff: magical, d8; optionally use spellcasting ability for one minute."
    spell_school: str = "transmutation"
    target_type: TargetType = TargetType.SELF
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN
    selected_weapon_uuid: UUID | None = None

    def _held_weapon(self, slot: WeaponSlot | None = None) -> Weapon | None:
        slot = self.weapon_slot if slot is None else slot
        caster = Entity.get(self.source_entity_uuid)
        if (caster is None or caster.equipment.active_weapon_set is not WeaponSet.MELEE
                or slot not in (WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF)):
            return None
        weapon = caster.equipment.get_weapon(slot)
        return weapon if weapon is not None and weapon.weapon_kind in (WeaponKind.CLUB, WeaponKind.QUARTERSTAFF) and weapon.material is Material.WOOD else None

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        """The held weapon to empower: main or off hand."""
        return tuple((ActionVariantFacet(key="form", value=slot.value,
                                         label="Main hand" if slot is WeaponSlot.MELEE_MAIN else "Off hand"),)
                     for slot in (WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF) if self._held_weapon(slot) is not None)

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "weapon_slot": WeaponSlot(selection_facet(selection, "form"))}

    def get_discovery_display_name(self) -> str:
        return f"{super().get_discovery_display_name()} ({'main hand' if self.weapon_slot is WeaponSlot.MELEE_MAIN else 'off hand'})"

    def _create_declaration_event(self, parent_event: Event | None = None, use_register: bool = True):
        weapon = self._held_weapon()
        self.selected_weapon_uuid = weapon.uuid if weapon else None
        declaration = super()._create_declaration_event(parent_event, use_register=use_register)
        return declaration.model_copy(update={"source_item_uuid":self.selected_weapon_uuid}) if declaration else None

    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Shillelagh", cost_type="bonus_actions",
        cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        weapon = self._held_weapon()
        if weapon is None or (weapon.weapon_kind not in (WeaponKind.CLUB, WeaponKind.QUARTERSTAFF) or weapon.material != Material.WOOD):
            return "Shillelagh requires a held wooden club or quarterstaff"
        return None

    def _apply(self, event: SpellEvent):
        caster = Entity.get(self.source_entity_uuid)
        weapon = self._held_weapon()
        if (caster is None or weapon is None or weapon.uuid != self.selected_weapon_uuid
                or (weapon.weapon_kind not in (WeaponKind.CLUB, WeaponKind.QUARTERSTAFF) or weapon.material != Material.WOOD)):
            return event.cancel(status_message="Exact eligible held weapon was lost")
        return self.apply_owned_condition( event.phase_to(EventPhase.EFFECT), ShillelaghEffect(
            source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, weapon_uuid=weapon.uuid,
            casting_ability=caster.spellcasting.resolve_spellcasting_ability(self.spellcasting_source_id)))


class MagicWeaponEffect(BaseCondition):
    name: str = "Magic Weapon"
    description: str = "The exact weapon gains magical attacks and a nonstacking attack/damage bonus."
    bonus: int = 1
    duration: Duration = Field(default_factory=lambda:Duration(duration=None,duration_type=DurationType.UNTIL_LONG_REST))
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})

    def model_post_init(self,context: object) -> None:
        super().model_post_init(context)
        self.name=f"Magic Weapon:{self.source_entity_uuid}"

    def get_display_name(self) -> str:
        return "Magic Weapon"

    def _apply(self,event: Event):
        weapon=BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(weapon,Weapon):
            return [],[],[],[],event.cancel(status_message="Exact weapon no longer exists")
        weapon.magical_attack_sources.add(self.uuid)
        def strongest(source_uuid: UUID,target_uuid: UUID | None=None,context: dict | None=None):
            contenders=[condition for condition in weapon.active_conditions_by_uuid.values()
                if isinstance(condition,MagicWeaponEffect) and condition.contributions_active()]
            winner=max(contenders,key=lambda condition:(condition.bonus,str(condition.uuid)),default=None)
            if winner is not self:
                return None
            return NumericalModifier(name="Magic Weapon",value=self.bonus,source_entity_uuid=source_uuid,target_entity_uuid=target_uuid)
        modifiers=[]
        for value in (weapon.attack_bonus,weapon.damage_bonus):
            if value is None:
                continue
            identity=add_modifier(value, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(name="Magic Weapon",
                source_entity_uuid=weapon.uuid,target_entity_uuid=self.source_entity_uuid,callable=strongest))
            modifiers.append((value.uuid,identity))
        return modifiers,[],[],[],event.phase_to(EventPhase.EFFECT)

    def _release_owned_runtime_state(self,*,parent_event: Event | None=None) -> None:
        weapon=BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if isinstance(weapon,Weapon):
            weapon.magical_attack_sources.discard(self.uuid)
        super()._release_owned_runtime_state(parent_event=parent_event)


class MagicWeapon(SpellAction):
    creates = (*SpellAction.creates, MagicWeaponEffect)
    name: str = "Magic Weapon"
    description: str = "Enchant a held weapon until rest: +1 attack/damage, +2 at slot4, +3 at slot6."
    spell_level: int = 2
    spell_school: str = "transmutation"
    target_type: TargetType = TargetType.ENTITY
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.REACH,normal=5))
    valid_target_filter: str = "self_or_allies"
    include_self: bool = True
    concentration: bool = True
    harmful: bool = False
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN
    selected_weapon_uuid: UUID | None = None

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self,actor,key="magic_weapon",condition_type=MagicWeaponEffect,beneficial=True,
            save_ability=None,fact=None,)

    def _selected_weapon(self, recipient_uuid: UUID | None) -> Weapon | None:
        recipient=Entity.get(recipient_uuid or self.source_entity_uuid)
        return recipient.equipment.get_weapon(self.weapon_slot) if recipient is not None else None

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return tuple((ActionVariantFacet(key="form", value=slot.value, label=slot.value.replace('_',' ').title()),)
                     for slot in WeaponSlot)

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "weapon_slot": WeaponSlot(selection_facet(selection, "form"))}

    def _create_declaration_event(self,parent_event: Event | None=None,use_register: bool=True):
        event=super()._create_declaration_event(parent_event,use_register)
        weapon=self._selected_weapon(self.target_entity_uuid)
        self.selected_weapon_uuid=weapon.uuid if weapon is not None else None
        return event

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        error=self.single_recipient_error(scan, selection)
        if error is not None:
            return error
        weapon=self._selected_weapon(selection.target_uuids[0])
        if weapon is None or weapon.is_body_attack:
            return "Selected recipient must hold an eligible weapon"
        return None

    def _apply(self,event: SpellEvent):
        weapon=self._selected_weapon(event.target_entity_uuid)
        if weapon is None or weapon.uuid!=self.selected_weapon_uuid:
            return event.cancel(status_message="Exact selected weapon is no longer held")
        return self.apply_owned_condition(event.phase_to(EventPhase.EFFECT),MagicWeaponEffect(
            source_entity_uuid=self.source_entity_uuid,target_entity_uuid=weapon.uuid,
            bonus=3 if self.cast_at_level>=6 else 2 if self.cast_at_level>=4 else 1))


@srd_condition_identity(content_id="spatial_effect.spell.plant_growth",display_name="Plant Growth",
    description="Ten-turn vegetation imposes a strongest walking cost of four and burns away partially.")
class PlantGrowthZone(AreaCondition):
    name: str = "Plant Growth"
    description: str = "Ten-turn vegetation imposes a strongest walking cost of four and burns away partially."
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    area: AoEShape = Sphere(radius_feet=20)
    minimum_walking_cost: int = 4
    has_visible_presence: bool = True
    duration: Duration = Field(default_factory=lambda:Duration(duration=10,duration_type=DurationType.ROUNDS))
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})

    def _apply(self,event: Event):
        modifiers,handlers,children,spatial,effect=super()._apply(event)
        reaction=bind_spatial_interactions(condition=self,transitions=(SpatialEffectTransitionDefinition(
            operation=SpatialEffectInteractionOperation.IGNITE,action=SpatialEffectTransitionAction.REMOVE_AFFECTED),))
        return modifiers,handlers,children,[*spatial,reaction.uuid],effect


class PlantGrowth(SpellAction):
    creates = (*SpellAction.creates, PlantGrowthZone)
    name: str = "Plant Growth"
    description: str = "Create ten-turn vegetation in a twenty-foot radius: walking costs four feet per foot."
    spell_level: int = 3
    spell_school: str = "transmutation"
    target_type: TargetType = TargetType.POSITION_LOS
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.RANGE,normal=60))
    harmful: bool = True

    def get_valid_positions(self):
        return spell_valid_positions(self)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return placement_error(self, scan, selection)

    def _apply(self,event: SpellEvent):
        caster=Entity.get(self.source_entity_uuid)
        if caster is None or self.end_position is None:
            return event.cancel(status_message="Plant Growth placement is absent")
        effect=event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        zone=PlantGrowthZone(source_entity_uuid=caster.uuid,position=self.end_position,
            faction=caster.faction,content_ref=get_content_declaration(PlantGrowthZone).ref,
            effect_origin=event.get_effect_origin())
        admitted=zone.activate(parent_event=effect)
        return effect if admitted is not None and not admitted.canceled else effect.cancel(status_message="Vegetation was not admitted")


class RainWetEffect(WetSurfaceMembership):
    name: str = "Rain Wet"
    description: str = "Three-turn rain Wet lease and reveal, independent of water-surface membership."
    suppresses_invisibility: bool = True
    duration: Duration = Field(default_factory=lambda:Duration(duration=3,duration_type=DurationType.ROUNDS))

    def on_membership_changed(self,event: Event) -> None:
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            target._notify_perceivability_changed(parent_event=event.uuid)


class CreateOrDestroyWater(SpellAction):
    creates = (*SpellAction.creates, RainWetEffect, WetSurface)
    name: str = "Create or Destroy Water"
    description: str = "Create persistent water and three-turn rain Wet/reveal, or remove water-bearing patches."
    spell_level: int = 1
    spell_school: str = "transmutation"
    target_type: TargetType = TargetType.POSITION_AOE
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.RANGE,normal=30))
    mode: Literal["create","destroy"] = "create"
    aoe_require_targets: bool = False
    valid_target_filter: str = "all"
    include_self: bool = True
    harmful: bool = False

    def model_post_init(self,context: object) -> None:
        super().model_post_init(context)
        if self.aoe_shape is None:
            self.aoe_shape=Sphere(radius_feet=13+7*self.get_upcast_bonus())

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return tuple((ActionVariantFacet(key="form", value=mode, label=mode.title()),) for mode in ("create", "destroy"))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        """The mode, and the area at the selected level."""
        overrides = super()._selection_overrides(selection)
        level = overrides.get("cast_at_level", self.cast_at_level)
        return {**overrides, "mode": selection_facet(selection, "form"),
                "aoe_shape": Sphere(radius_feet=13+7*max(0, level-self.spell_level))}

    def _resolve_execution_targets(self):
        return self._resolve_area_targets() if self.effective_target_type is TargetType.POSITION_AOE else super()._resolve_execution_targets()

    def get_valid_positions(self):
        return spell_valid_positions(self)

    def valid_positions_among(self, points: Iterable[Tuple[int, int]]) -> List[Tuple[int, int]]:
        return [point for point in points if in_spell_placement_region(self, point)]

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        return placement_error(self, scan, selection)

    def _apply(self,event: SpellEvent):
        effect=event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        target=Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if self.mode=="create" and target is not None:
            target.add_condition(RainWetEffect(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=target.uuid,
                source_spatial_condition_uuid=event.lineage_uuid),parent_event=effect)
        return effect

    def _finalize_aoe(self,event: ActionEvent) -> None:
        positions=set(event.resolved_area_positions or ())
        if not positions or self.end_position is None:
            return
        if self.mode=="create":
            resolve_interaction(SpatialEffectInteractionEvent(source_entity_uuid=self.source_entity_uuid,
                positions=tuple(sorted(positions)),operation=SpatialEffectInteractionOperation.DOUSE,parent_event=event.uuid))
            surface=WetSurface(source_entity_uuid=self.source_entity_uuid,position=self.end_position,
                affected_positions=positions)
            surface.activate(parent_event=event)
        else:
            resolve_interaction(EventQueue.publish_declaration(SpatialEffectInteractionEvent(
                source_entity_uuid=self.source_entity_uuid, positions=tuple(sorted(positions)),
                operation=SpatialEffectInteractionOperation.DRY, parent_event=event.uuid, use_register=False)))


class DragonsBreathEffect(ConcentrationActionMarker):
    name: str = "Dragon's Breath"
    description: str = "The caster maintains an ally's elemental breath action."
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})
    duration: Duration = Field(default_factory=lambda:Duration(duration=10,duration_type=DurationType.ROUNDS))


@srd_action_identity(content_id="action.spell.dragons_breath.exhale",display_name="Exhale Dragon's Breath",
    description="Use the retained caster's elemental breath in a fifteen-foot cone.",
    parent_spell_name="Dragon's Breath",source_page=126,srd_version="5.2",sort_order=3220)
class ExhaleDragonsBreath(SpellAction):
    name: str = "Exhale Dragon's Breath"
    description: str = "Fifteen-foot cone, retained caster DC and element; Dexterity save for half."
    action_category: ActionCategory = ActionCategory.ABILITY
    spell_level: int = 2
    spell_school: str = "transmutation"
    alt_skip_slot: bool = True
    verbal: bool = False
    target_type: TargetType = TargetType.POSITION_AOE
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.SELF))
    include_self: bool = False
    aoe_require_targets: bool = False
    valid_target_filter: str = "all"
    spell_damage_type: DamageType = DamageType.FIRE
    original_caster_uuid: UUID
    spell_dc: int
    grant_condition_uuid: UUID
    effect_origin: EffectOrigin

    def spell_execution_scope(self):
        binding=self.behavior_binding
        return spell_execution_scope(source_entity_uuid=self.original_caster_uuid,damage_type=self.spell_damage_type,
            cause_id=binding.behavior_id if binding else None)

    def model_post_init(self,context: object) -> None:
        super().model_post_init(context)
        if self.aoe_shape is None:
            self.aoe_shape=Cone(length_feet=15)

    def _create_declaration_event(self,parent_event: Event | None=None,use_register: bool=True):
        event=super()._create_declaration_event(parent_event,use_register)
        actor=Entity.get(self.source_entity_uuid)
        origin=self.effect_origin.model_copy(update={"source_position":actor.position}) if actor else self.effect_origin
        return event.with_updates(retained_effect_origin=origin) if isinstance(event,SpellEvent) else event

    def _grant_active(self) -> bool:
        recipient=Entity.get(self.source_entity_uuid)
        owner=recipient.active_conditions_by_uuid.get(self.grant_condition_uuid) if recipient else None
        return (recipient is not None and recipient.health.life_state is LifeState.ALIVE
            and owner is not None and owner.applied and owner.contributions_active())

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        if not self._grant_active():
            return "Dragon's Breath grant has ended or is suppressed"
        if not selection.positions or selection.positions[0]==scan.position:
            return "Choose a breath direction"
        return None

    def _resolve_execution_targets(self):
        return self._resolve_area_targets()

    def _apply(self,event: SpellEvent):
        if not self._grant_active():
            return event.cancel(status_message="Dragon's Breath grant has ended or is suppressed")
        caster=Entity.get(self.original_caster_uuid)
        target=Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if caster is None or target is None:
            return event.cancel(status_message="Breath source or recipient is absent")
        effect,_,saved=self.resolve_saving_throw(event,caster=caster,target=target,ability_name="dexterity",dc=self.spell_dc)
        if effect.canceled:
            return effect
        damage=Damage(name="Dragon's Breath",source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid,
            damage_type=self.spell_damage_type,damage_dice=6,dice_numbers=1+self.cast_at_level,
            damage_bonus=parts(ModifiableValue(source_entity_uuid=caster.uuid,base=0)))
        roll=roll_spell_damage(damage, parent_event=event, effect_origin=self.effect_origin, attack_outcome=AttackOutcome.HIT, crit_extra_dice=0)
        return deliver_spell_damage(effect,target,damage,roll,amount=roll.total//2 if saved else roll.total)

    def _finalize_aoe(self,event: ActionEvent) -> None:
        apply_elemental_surface_contacts(event,set(event.resolved_area_positions or ()),self.spell_damage_type)


class DragonsBreath(SpellAction):
    creates = (*SpellAction.creates, DragonsBreathEffect, ExhaleDragonsBreath)
    name: str = "Dragon's Breath"
    description: str = "Grant yourself or an ally a repeatable elemental breath action; ten-turn concentration."
    spell_level: int = 2
    spell_school: str = "transmutation"
    concentration: bool = True
    target_type: TargetType = TargetType.ENTITY
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.REACH,normal=5))
    valid_target_filter: str = "self_or_allies"
    include_self: bool = True
    harmful: bool = False
    element: Literal["acid","cold","fire","lightning","poison"] = "fire"
    alt_cost_type: str | None = "bonus_actions"

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return None
        return spell_condition_profile(self,actor,key="dragons_breath",condition_type=DragonsBreathEffect,beneficial=True,
            save_ability=None,fact=None,)

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return tuple((ActionVariantFacet(key="damage_type", value=element, label=element.title()),)
                     for element in ("acid","cold","fire","lightning","poison"))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "element": selection_facet(selection, "damage_type")}

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        caster=Entity.get(self.source_entity_uuid)
        recipient=Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if caster is None or recipient is None or (recipient.uuid!=caster.uuid and not caster.is_ally(recipient)):
            return "Choose yourself or a willing ally"
        return self.single_recipient_error(scan, selection)

    def _apply(self,event: SpellEvent):
        caster=Entity.get(self.source_entity_uuid)
        recipient=Entity.get(event.target_entity_uuid or self.source_entity_uuid)
        if caster is None or recipient is None:
            return event.cancel(status_message="Breath recipient is absent")
        marker=DragonsBreathEffect(source_entity_uuid=caster.uuid,target_entity_uuid=recipient.uuid,
            action_name="Exhale Dragon's Breath")
        admitted=self.apply_owned_condition(event.phase_to(EventPhase.EFFECT),marker)
        if admitted.canceled or not marker.applied:
            return admitted
        exhale=ExhaleDragonsBreath(source_entity_uuid=recipient.uuid,template=True,
            original_caster_uuid=caster.uuid,spell_dc=caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
            grant_condition_uuid=marker.uuid,cast_at_level=self.cast_at_level,spell_damage_type=DamageType(self.element.capitalize()),
            effect_origin=admitted.get_effect_origin())
        marker.action_uuid=exhale.uuid
        recipient.register_action(exhale)
        return admitted


class GoodberryBatch(CreatedItemsLifetime):
    name: str = "Goodberry Batch"
    description: str = "Owns exact berries until the creating caster's long rest."


class Goodberry(SpellAction):
    creates = (*SpellAction.creates, GoodberryBatch, EatGoodberry)
    name: str = "Goodberry"
    description: str = "Create four real berries in an ally's inventory; bonus-action 1d4 healing, until caster long rest."
    spell_level: int = 1
    spell_school: str = "transmutation"
    target_type: TargetType = TargetType.ENTITY
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.REACH,normal=5))
    valid_target_filter: str = "self_or_allies"
    include_self: bool = True
    harmful: bool = False
    _berries: list[BaseItem] = PrivateAttr(default=[])

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        caster=Entity.get(self.source_entity_uuid)
        recipient=Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if caster is None or recipient is None or (recipient.uuid!=caster.uuid and not caster.is_ally(recipient)):
            return "Choose yourself or a willing ally"
        return self.single_recipient_error(scan, selection)

    def _apply_costs(self,event):
        recipient=Entity.get(self.target_entity_uuid or self.source_entity_uuid)
        self._berries=[build_goodberry(self.source_entity_uuid) for _ in range(4)]
        if recipient is None or not recipient.inventory.can_add_all(self._berries):
            return event.cancel(status_message="Recipient cannot carry all four berries")
        return super()._apply_costs(event)

    def _apply(self,event: SpellEvent):
        caster=Entity.get(self.source_entity_uuid)
        recipient=Entity.get(event.target_entity_uuid or self.source_entity_uuid)
        if caster is None or recipient is None or not recipient.inventory.can_add_all(self._berries):
            return event.cancel(status_message="Berry inventory admission changed")
        batch=GoodberryBatch(source_entity_uuid=caster.uuid,target_entity_uuid=caster.uuid,
            item_uuids=[item.uuid for item in self._berries])
        admitted=self.apply_owned_condition(event.phase_to(EventPhase.EFFECT),batch)
        if admitted.canceled or not batch.applied:
            return admitted
        for berry in self._berries:
            if not recipient.loot_item(berry,parent_event=admitted):
                caster.remove_condition_by_uuid(batch.uuid,parent_event=admitted)
                return admitted.cancel(status_message="Berry inventory admission changed")
        return admitted

    def apply(self,parent_event: Event | None=None):
        try:
            return super().apply(parent_event)
        finally:
            for berry in self._berries:
                if berry.owner_uuid is None and berry.stored_in_uuid is None and berry.tile_uuid is None and berry.is_active:
                    berry.retire()
            self._berries=[]


class FleshToStonePetrified(Petrified):
    name: str = "Flesh to Stone Petrified"
    description: str = "Completed petrification persists until an eligible cure."
    immunity_names: tuple[str, ...] = ("Petrified",)
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.PERMANENT))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL, ConditionTag.PETRIFICATION})


class FleshToStoneEffect(Restrained):
    creates = (FleshToStonePetrified,)
    name: str = "Flesh to Stone"
    description: str = "Restrained stages; four failed CON saves complete petrification, a success clears stages."
    immunity_names: tuple[str, ...] = ("Restrained", "Petrified")
    spell_dc: int
    failures: int = 1
    duration: Duration = Field(default_factory=lambda: Duration(duration=10, duration_type=DurationType.ROUNDS))
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        self.name = f"Flesh to Stone:{self.source_entity_uuid}"

    def get_display_name(self) -> str:
        return "Flesh to Stone"

    def _apply(self, event: Event):
        modifiers, handlers, children, spatial, effect = super()._apply(event)
        if effect is None or effect.canceled: return modifiers, handlers, children, spatial, effect
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        assert target is not None
        def progress(boundary: Event, _: UUID):
            if condition_save(self, target, boundary, "constitution", self.spell_dc, "spell.flesh_to_stone.progress"):
                target.remove_condition_by_uuid(self.uuid, parent_event=boundary)
                return None
            self.failures += 1
            if self.failures >= 4:
                stone = FleshToStonePetrified(source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=target.uuid, effect_origin=self.effect_origin)
                result = target.add_condition(stone, parent_event=boundary)
                if result is not None and not result.canceled:
                    target.remove_condition_by_uuid(self.uuid, parent_event=boundary)
            return None
        handler = EventHandler(name="Flesh to Stone progress", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target.uuid)], event_processor=progress)
        target.add_event_handler(handler)
        return modifiers, [*handlers, handler.uuid], children, spatial, effect


class FleshToStone(SpellAction):
    creates = (*SpellAction.creates, FleshToStoneEffect)
    name: str = "Flesh to Stone"
    description: str = "CON save or restrained stages; four failures petrify until cured."
    spell_level: int = 6
    spell_school: str = "transmutation"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    target_type: TargetType = TargetType.ENTITY
    concentration: bool = True
    harmful: bool = True

    def get_target_effect_profile(self):
        actor = Entity.get(self.source_entity_uuid)
        if actor is None: return None
        return spell_condition_profile(self, actor, key="flesh_to_stone", condition_type=FleshToStoneEffect,
            save_ability="constitution", fact="selected_target.condition.restrained")

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        target = Entity.get(selection.target_uuids[0]) if selection.target_uuids else None
        if target is not None and (target.flesh_body is False or target.flesh_body is None and
                target.creature_type in {CreatureType.CONSTRUCT, CreatureType.ELEMENTAL, CreatureType.PLANT, CreatureType.OOZE, CreatureType.UNDEAD}):
            return "Target has no flesh to petrify"
        return living_recipients_error(self, scan, selection.target_uuids)

    def _apply(self, event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if caster is None or target is None: return event.cancel(status_message="Petrification recipient absent")
        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        effect, _, saved = self.resolve_saving_throw(event, caster=caster, target=target, ability_name="constitution", dc=dc)
        if saved or effect.canceled: return effect
        return self.apply_owned_condition(effect, FleshToStoneEffect(source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid, spell_dc=dc))
