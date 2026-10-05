"""Transmutation spells - transforming matter and energy.

Contains: SpikeGrowth, Slow, Haste, Darkvision, JumpSpell, ExpeditiousRetreat, Disintegrate,
          EnhanceAbility, EnlargeReduce, Regenerate
"""
from typing import cast
from dnd.blocks.equipment import EquipmentEvent, Weapon, WeaponUnequipEvent
from dnd.core.attack_types import WeaponAttackOverride
from dnd.types.materials import Material
from dnd.core.equipment_types import WeaponKind, WeaponSet, WeaponSlot
from dnd.types.world import MovementMode
from dnd.core.base_conditions import Duration
from typing import Any, Dict, Literal, Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID, uuid4

from pydantic import Field, PrivateAttr
from dnd.blocks.base_item import BaseItem
from dnd.core.life_types import RemainsDisposition
from dnd.core.base_block import BaseBlock
from dnd.types.physical_access import PhysicalAccess

from dnd.core.action_types import EntityTargetPerception
from dnd.core.action_types import EntityDestinationSelection
from dnd.core.base_actions import (
    ActionCategory,
    ActionEvent,
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
from dnd.types.world import OccupancyLayer
from dnd.core.action_types import (
    ActionEconomyCostType,
    HasteActionPolicy,
    RestrictedActionGrant,
    RestrictedActionKind,
)
from dnd.core.base_block import SensesType, SenseMode
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger, Range, RangeType, SpatialChangeEvent, Damage, Healing, ForcedMovementEvent
)
from dnd.types.abilities import AbilityName
from dnd.types.actor import ConditionState
from dnd.core.dice import AttackOutcome
from dnd.core.effect_types import EffectOrigin
from dnd.core.elevation import support_distance_feet
from dnd.core.life_types import LifeState
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.types.event_facts import LandingKind
from dnd.core.creature_types import DamageType, Size
from dnd.core.modifiers import (
    ArithmeticFactor,
    NumericalModifier,
    AdvantageModifier,
    AdvantageStatus,
)
from dnd.core.values import ModifiableValue
from dnd.core.aoe import AoEShape, Cube
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.conditions import Dashing, ConcentrationActionMarker, Prone
from dnd.creature_transforms import apply_incapacitated_transform, remove_modifier_ownership
from dnd.actions import AttackEvent, SpellAction, SpellEvent, entity_action_economy_cost_evaluator, entity_action_economy_cost_applier, commit_forced_movement, resolve_fall_damage
from dnd.spatial.area_conditions import AreaCondition
from dnd.types.spatial_effects import (
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)
from dnd.spells.content_metadata import srd_action_identity, srd_spell_identity
from dnd.spells.spell_utils import fire_heal_roll_result


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
    zone_shape: str = Field(default="sphere", description="Zone shape key.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet.")
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
            dmg_bonus = caster.get_spell_damage_bonus() if caster else ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0, value_name="Spell Damage"
            )
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=type_cast(Literal[4, 6, 8, 10, 12, 20], value), dice_numbers=count, damage_bonus=dmg_bonus,
                damage_type=DamageType.PIERCING
            )
            damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in range and visible."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = self.get_target_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Position out of range ({distance}ft > {self.effective_range}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

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
                speed.self_static.add_factor(modifier)
                outs.append((speed.uuid, modifier.uuid))

        ac_mod = NumericalModifier(
            name="Slowed",
            value=-2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        target.equipment.ac_bonus.self_static.add_value_modifier(ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, ac_mod.uuid))

        dex_save = target.saving_throws.get_saving_throw("dexterity")
        dex_mod = NumericalModifier(
            name="Slowed",
            value=-2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        dex_save.bonus.self_static.add_value_modifier(dex_mod)
        outs.append((dex_save.bonus.uuid, dex_mod.uuid))

        reaction_constraint_uuid = target.action_economy.reactions.self_static.add_max_constraint(
            constraint=NumericalModifier(
                name="Slowed",
                value=0,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
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

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                size_feet=40,
                centered=True
            )

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Slow's failed-save action-economy debuff branch."""
        if not isinstance(actor, Entity):
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not in LOS")

        distance = self.get_target_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Out of range ({distance}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Slow to current target (called per target via convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

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

        save_bonus = target.saving_throw_bonus(caster.uuid, "wisdom").normalized_score

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
        target.add_condition(slowed, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if slowed.applied:
            concentration.add_linked_condition(target.uuid, slowed.uuid)

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
            speed.self_static.add_factor(modifier)
            outs.append((speed.uuid, modifier.uuid))

        ac_mod = NumericalModifier(
            name="Haste",
            value=2,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        target.equipment.ac_bonus.self_static.add_value_modifier(ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, ac_mod.uuid))

        dex_save = target.saving_throws.get_saving_throw("dexterity")
        dex_adv = AdvantageModifier(
            name="Haste",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        dex_mod_uuid = dex_save.bonus.self_static.add_advantage_modifier(dex_adv)
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
    valid_target_filter: str = Field(default="all", description="Target filter key for available action discovery.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target is in LOS and range."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return declaration_event.cancel(status_message="No target")

        contact = caster.senses.entities.get(target.uuid)
        if contact is None or not contact.visual:
            return declaration_event.cancel(status_message=f"{target.name} not visible")

        distance = self.get_target_distance(target.senses.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Out of range ({distance}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Haste to the target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Hasting {target.name}"
        )

        haste_effect = HasteEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(haste_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if haste_effect.applied:
            concentration.add_linked_condition(target.uuid, haste_effect.uuid)

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

    def get_world_effect_profile(self, actor: Any) -> ActionWorldEffectProfile:
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
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} grants darkvision to {target.name}"
        )

        darkvision_effect = DarkvisionEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(darkvision_effect, parent_event=effect_event)

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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        los_event = self.validate_single_recipient(declaration_event)
        if los_event is None or los_event.canceled:
            return los_event

        recipient = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        source = Entity.get(self.source_entity_uuid)
        if isinstance(recipient, BaseItem):
            contact = source.senses.objects.get(recipient.uuid) if source is not None else None
            if contact is None or not contact.visual:
                return los_event.cancel(status_message="Disintegrate requires a target you can see")
            error = recipient.disintegration_error()
            return los_event.cancel(status_message=error) if error else los_event.phase_to(EventPhase.EXECUTION)

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source or not target:
            return declaration_event.cancel(status_message="Entity not found")

        contact = source.senses.entities.get(target.uuid)
        if target.uuid != source.uuid and (contact is None or not contact.visual):
            return los_event.cancel(status_message="Disintegrate requires a target you can see")

        distance = self.get_target_distance(target.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Out of range ({distance}ft > {self.effective_range}ft)"
            )

        return los_event.phase_to(EventPhase.EXECUTION, status_message=f"Validated {self.name}")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        recipient = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if isinstance(recipient, BaseItem):
            effect = execution_event.phase_to(EventPhase.EFFECT)
            if effect.canceled:
                return effect
            return (effect.with_updates(status_message=f"{recipient.name} disintegrated")
                    if recipient.disintegrate(effect) else effect.cancel(status_message="Object retirement was refused"))
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

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

        damage_bonus = caster.get_spell_damage_bonus()
        damage_bonus.self_static.add_value_modifier(NumericalModifier(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            name="Disintegrate flat damage", value=self.base_damage_bonus))
        force_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FORCE
        )
        damage_dice = force_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll
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
        mod_uuid = target.jump_distance_multiplier.self_static.add_value_modifier(mod)
        outs.append((target.jump_distance_multiplier.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self}
        ) if declaration_event else None

        return outs, [], [], [], effect_event


class JumpSpell(SpellAction):
    """Triple one creature's jump distance while concentration lasts."""
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        contact = caster.senses.entities.get(target.uuid)
        if target.uuid != caster.uuid and (contact is None or not contact.visual):
            return declaration_event.cancel(status_message="Target not visible")

        distance = self.get_target_distance(target.position)
        if distance > self.effective_range:
            return declaration_event.cancel(status_message=f"Target out of touch range ({distance}ft)")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Jump on {target.name}"
        )

        jump_effect = JumpEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(jump_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if jump_effect.applied:
            concentration.add_linked_condition(target.uuid, jump_effect.uuid)

        return effect_event.with_updates(
            status_message=f"{target.name}'s jump distance tripled"
        )


class BonusDash(BaseAction):
    """Bonus action Dash granted by Expeditious Retreat."""
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
    name: str = Field(default="Expeditious Retreat", description="Condition name.")
    description: str = Field(default="You can Dash as a bonus action", description="Rules-facing condition summary.")
    _action_name: str = PrivateAttr(default="Dash (Bonus)")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        bonus_dash = BonusDash(source_entity_uuid=target.uuid, template=True)
        target.register_action(bonus_dash)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self}
        ) if declaration_event else None

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        if self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target:
                target.unregister_action(self._action_name)
        return super()._remove(event)


class ExpeditiousRetreat(SpellAction):
    """Grant the caster a concentration-linked bonus-action Dash template."""
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

        retreat_effect = ExpeditiousRetreatEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            tags={ConditionTag.MAGICAL}
        )
        caster.add_condition(retreat_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, retreat_effect.uuid)

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
        mod_uuid = ability.ability_score.self_static.add_advantage_modifier(
            AdvantageModifier(
                name=f"Enhance Ability ({self.ability_type.title()})",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid
            )
        )
        outs.append((ability.ability_score.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Enhanced {self.ability_type.title()} on {target.name}"
        )

        if self.ability_type == "constitution":
            healing = Healing(
                source_entity_uuid=self.source_entity_uuid,
                healing_dice=6, dice_numbers=2,
                healing_bonus=ModifiableValue.create(
                    source_entity_uuid=self.source_entity_uuid, base_value=0, value_name="Bear's Endurance"
                )
            )
            temp_hp = healing.get_dice().roll.total
            target.health.add_temporary_hit_points(temp_hp, self.source_entity_uuid, parent_event=effect_event.uuid)

        return outs, [], [], [], effect_event


class EnhanceAbility(SpellAction):
    """Apply a concentration-linked Enhance Ability effect.

    This implementation stores the selected ability on the action instance and
    applies the corresponding `EnhanceAbilityEffect` to the target.
    """
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

    def _create_declaration_event(
        self, parent_event: Optional[Event] = None, use_register: bool = True,
    ) -> Optional[Event]:
        event = super()._create_declaration_event(parent_event, use_register)
        if isinstance(event, SpellEvent):
            event.effect_id = f"support.enhance_ability.{self.enhance_ability_type}"
        return event

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not target:
            target = caster
            self.target_entity_uuid = caster.uuid

        if target.uuid != caster.uuid:
            distance = self.get_target_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(status_message=f"Target out of range ({distance}ft)")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        concentration = self.ensure_concentration(execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Enhancing {self.enhance_ability_type.title()} on {target.name}"
        )

        effect = EnhanceAbilityEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            ability_type=self.enhance_ability_type,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(effect, parent_event=effect_event)
        if effect.applied:
            concentration.add_linked_condition(target.uuid, effect.uuid)

        return effect_event.with_updates(
            status_message=f"Enhanced {self.enhance_ability_type.title()} on {target.name}"
        )

_SIZE_ORDER = [Size.TINY, Size.SMALL, Size.MEDIUM, Size.LARGE, Size.HUGE, Size.GARGANTUAN]


def _shift_size(current: Size, delta: int) -> Size:
    """Shift size up or down, clamping to valid range."""
    idx = _SIZE_ORDER.index(current)
    new_idx = max(0, min(len(_SIZE_ORDER) - 1, idx + delta))
    return _SIZE_ORDER[new_idx]


class EnlargeReduceEffect(BaseCondition):
    """Change target size and Strength roll advantage state.

    Enlarge increases size by one category and grants advantage on Strength
    checks and saves. Reduce decreases size by one category and grants
    disadvantage. Size-based damage dice are handled by `Entity.get_damages()`.
    """
    name: str = Field(default="Enlarge/Reduce", description="Condition name.")
    description: str = Field(default="Size changed by magic", description="Rules-facing condition summary.")
    mode: Literal["enlarge", "reduce"] = Field(default="enlarge", description="Either 'enlarge' or 'reduce'.")
    original_size: Optional[str] = Field(default=None, description="Original size value restored when the effect ends.")

    def snapshot_state(self) -> ConditionState:
        return super().snapshot_state().model_copy(update={"size_change": self.mode})

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        self.original_size = target.size.value

        if self.mode == "enlarge":
            target.size = _shift_size(target.size, 1)
            adv_value = AdvantageStatus.ADVANTAGE
        else:
            target.size = _shift_size(target.size, -1)
            adv_value = AdvantageStatus.DISADVANTAGE

        str_ability = target.ability_scores.get_ability("strength")
        mod_uuid = str_ability.ability_score.self_static.add_advantage_modifier(
            AdvantageModifier(
                name=f"{'Enlarge' if self.mode == 'enlarge' else 'Reduce'} (STR checks)",
                value=adv_value,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid
            )
        )
        outs.append((str_ability.ability_score.uuid, mod_uuid))

        str_save = target.saving_throws.get_saving_throw("strength")
        save_mod_uuid = str_save.bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name=f"{'Enlarge' if self.mode == 'enlarge' else 'Reduce'} (STR saves)",
                value=adv_value,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid
            )
        )
        outs.append((str_save.bonus.uuid, save_mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{'Enlarged' if self.mode == 'enlarge' else 'Reduced'} {target.name} to {target.size.value}"
        )

        return outs, [], [], [], effect_event

    def _remove(self, removal_event: Optional[Event] = None) -> Optional[Event]:
        """Restore original size on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and self.original_size:
            try:
                target.size = Size(self.original_size)
            except ValueError:
                pass
        return super()._remove(removal_event)


class EnlargeReduce(SpellAction):
    """Apply Enlarge or Reduce with concentration-linked cleanup.

    Enemy targets receive a Constitution save before the size effect is applied.
    Willing targets and the caster are affected directly.
    """
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not target:
            return declaration_event.cancel(status_message="No target specified")

        if target.uuid != caster.uuid:
            distance = self.get_target_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(status_message=f"Target out of range ({distance}ft)")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
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

        concentration = self.ensure_concentration(execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{'Enlarging' if self.enlarge_mode == 'enlarge' else 'Reducing'} {target.name}"
        )

        effect = EnlargeReduceEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            mode=self.enlarge_mode,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(effect, parent_event=effect_event)
        if effect.applied:
            concentration.add_linked_condition(target.uuid, effect.uuid)

        return effect_event.with_updates(
            status_message=f"{target.name} {'enlarged' if self.enlarge_mode == 'enlarge' else 'reduced'} to {target.size.value}"
        )


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
    if not caster.senses.visible.get(destination, False):
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
                damage_bonus=ModifiableValue.create(source_entity_uuid=caster.uuid, base_value=0), damage_type=damage_type)
            roll = damage.get_dice(AttackOutcome.HIT).roll
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

    def validate_source_requirements_for_discovery(self) -> bool:
        caster = Entity.get(self.source_entity_uuid)
        marker = caster.active_conditions_by_uuid.get(self.marker_uuid) if caster else None
        return marker is not None and marker.applied and marker.contributions_active()

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        if len(self.get_all_targets()) != 1:
            return declaration_event.cancel(status_message="Choose exactly one creature")
        caster = Entity.get(self.source_entity_uuid)
        if caster is None or not self.validate_source_requirements_for_discovery():
            return declaration_event.cancel(status_message="Telekinesis concentration has ended")
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        error = _telekinesis_selection_error(caster, target, self.end_position)
        if error:
            return declaration_event.cancel(status_message=error)
        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if caster is None or target is None or self.end_position is None:
            return execution_event.cancel(status_message="Creature or destination no longer available")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if not effect.canceled and self.validate_source_requirements_for_discovery():
            _resolve_telekinetic_transfer(caster, target, self.end_position, effect,
                self.spell_dc, self.effect_origin)
        return effect

    def _apply_costs(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)


class Telekinesis(SpellAction):
    """Cast and move once; concentration grants paid, finite repeats for ten minutes."""
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        if len(self.get_all_targets()) != 1:
            return declaration_event.cancel(status_message="Choose exactly one creature")
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return declaration_event.cancel(status_message="Caster not found")
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        error = _telekinesis_selection_error(caster, target, self.end_position)
        if error:
            return declaration_event.cancel(status_message=error)
        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
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
            runs_while_suppressed=True,
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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        contact = caster.senses.entities.get(target.uuid)
        if target.uuid != caster.uuid and (contact is None or not contact.visual):
            return declaration_event.cancel(status_message="Target not in line of sight")

        distance = self.get_target_distance(target.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Out of range ({distance}ft > {self.effective_range}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        healing = Healing(
            name="Regenerate",
            source_entity_uuid=caster.uuid,
            healing_dice=8,
            dice_numbers=4,
            healing_bonus=ModifiableValue.create(
                source_entity_uuid=caster.uuid,
                base_value=15,
                value_name="Regenerate Healing"
            )
        )
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Regenerate heals {target.name}"
        )

        healing_roll = fire_heal_roll_result(caster.uuid, target.uuid, healing, effect_event, "Regenerate")
        actual = target.receive_healing(
            healing_roll.total, caster.uuid,
            source_description=f"Regenerate: {healing_roll.total}",
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level
        )

        regen = RegeneratingEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(regen, parent_event=effect_event)

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
            speed.self_static.add_value_modifier(modifier)
            owned.append((speed.uuid, modifier.uuid))
        return owned, [], [], [], event.phase_to(EventPhase.EFFECT)


class Longstrider(SpellAction):
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

    def _validate(self, event):
        if len(self.get_all_targets()) > self.get_multi_target_count():
            return event.cancel(status_message="Too many recipients for this Longstrider slot")
        return super()._validate(event)

    def _apply(self, event: SpellEvent):
        effect_event = event.phase_to(EventPhase.EFFECT)
        return self.apply_owned_condition( effect_event, LongstriderEffect(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.target_entity_uuid))


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
        value.self_static.add_min_constraint(modifier)
        return [(value.uuid, modifier.uuid)], [], [], [], event.phase_to(EventPhase.EFFECT)


class Barkskin(SpellAction):
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
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.target_entity_uuid))


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
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.target_entity_uuid))


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

        handler = EventHandler(name="Shillelagh release", source_entity_uuid=caster.uuid, runs_while_suppressed=True,
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

    def get_discovery_variants(self, entity: Any) -> list[BaseAction]:
        return [variant.model_copy(deep=True, update={"uuid": uuid4(), "weapon_slot": slot,
                "registered_template_uuid": self.registered_template_uuid or self.uuid})
            for variant in super().get_discovery_variants(entity)
            for slot in (WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF) if self._held_weapon(slot) is not None]

    def get_discovery_template_name(self) -> str:
        return f"{super().get_discovery_template_name()}__{self.weapon_slot.value}"

    def get_discovery_display_name(self) -> str:
        return f"{super().get_discovery_display_name()} ({'main hand' if self.weapon_slot is WeaponSlot.MELEE_MAIN else 'off hand'})"

    def _create_declaration_event(self, parent_event: Event | None = None, use_register: bool = True):
        weapon = self._held_weapon()
        self.selected_weapon_uuid = weapon.uuid if weapon else None
        declaration = super()._create_declaration_event(parent_event, use_register=use_register)
        return declaration.model_copy(update={"source_item_uuid":self.selected_weapon_uuid}) if declaration else None

    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Shillelagh", cost_type="bonus_actions",
        cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def _validate(self, event: SpellEvent):
        weapon = self._held_weapon()
        if weapon is None or (weapon.weapon_kind not in (WeaponKind.CLUB, WeaponKind.QUARTERSTAFF) or weapon.material != Material.WOOD):
            return event.cancel(status_message="Shillelagh requires a held wooden club or quarterstaff")
        return super()._validate(event)

    def _apply(self, event: SpellEvent):
        caster = Entity.get(self.source_entity_uuid)
        weapon = self._held_weapon()
        if (caster is None or weapon is None or weapon.uuid != self.selected_weapon_uuid
                or (weapon.weapon_kind not in (WeaponKind.CLUB, WeaponKind.QUARTERSTAFF) or weapon.material != Material.WOOD)):
            return event.cancel(status_message="Exact eligible held weapon was lost")
        return self.apply_owned_condition( event.phase_to(EventPhase.EFFECT), ShillelaghEffect(
            source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, weapon_uuid=weapon.uuid,
            casting_ability=caster.spellcasting.resolve_spellcasting_ability(self.spellcasting_source_id)))
