"""Evocation spells - dealing damage and channeling energy, and healing.

Contains: FireBolt, SacredFlame, MagicMissile, Fireball, BurningHands,
          LightningBolt, Thunderwave, Shatter, Sunburst, RayOfFrost, ScorchingRay,
          ShockingGrasp, GuidingBolt, GustOfWind, IceStorm, Sunbeam,
          CureWounds, HealingWord, PrayerOfHealing, MassHealingWord,
          MassCureWounds, HealSpell, MassHeal
"""
from typing import cast
from uuid import uuid4
from dnd.actions import AttackEvent
from dnd.core.elevation import support_distance_feet
from dnd.types.actor import ConditionState
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
import random
from typing import Any, Callable, Literal, Optional, List, Set, Tuple
from uuid import UUID

from dnd.types.physical_access import PhysicalAccess
from pydantic import Field, PrivateAttr
from pydantic_core import PydanticUndefined

from dnd.core.action_types import ActionVariantFacet
from dnd.core.base_actions import (
    ActionCategory,
    AvailableTarget,
    ActionEvent,
    ActionInformationOperation,
    ActionOutcomeProfile,
    ActionWorldEffectAnchor,
    ActionWorldEffectCertainty,
    ActionWorldEffectProfile,
    ActionWorldEffectScope,
    ActionWorldEffectShape,
    BaseAction,
    Cost,
    InformationEffectProfile,
    OutcomeApplicationScope,
    TargetType,
)
from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration, SpellProtectionRegistry
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.runtime import bind_runtime_action_before_admission
from dnd.core.condition_types import ConditionCategory, ConditionTag, DurationType, HazardFilter
from dnd.core.values import ModifiableValue
from dnd.core.dice import AttackOutcome
from dnd.core.effect_types import EffectOrigin, EffectOriginKind, EffectEndpoint, EffectPropagationLink, ApplicationMembership
from dnd.core.life_types import LifeState
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.core.events import SavingThrowEvent
from dnd.types.senses import OpticalObscurement
from dnd.spatial.area_conditions import AreaCondition, SpatialCondition
from typing import cast as type_cast
from dnd.core.equipment_types import ArmorType, WeaponSlot
from dnd.core.item_types import ItemEffectPresentationState, ItemIntegrity
from dnd.core.events import EventPhase, RangeType, Range, Damage, Healing, ForcedMovementEvent, EventType, EventHandler, Trigger, Event, EventQueue, SpatialChangeEvent, SpatialEffectInteractionEvent
from dnd.spatial.ignition import ignite_surface_contacts
from dnd.types.world import OccupancyLayer
from dnd.types.abilities import AbilityName
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    NumericalModifier,
)
from dnd.core.aoe import AoEShape, Sphere, Cone, Line, Cube, Cylinder
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import LinePresentationGeometry
from dnd.types.senses import PerceivedSpatialEffect
from dnd.blocks.equipment import Weapon as WeaponItem, Shield as ShieldItem
from dnd.blocks.base_item import BaseItem
from dnd.core.events import AreaReachEvent, ItemDestructionEvent
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.world import WorldEdgeChannel

from dnd.entity import Entity
from dnd.actions import (
    Attack,
    Shove,
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_evaluator,
    commit_forced_movement,
)
from dnd.conditions import Blinded, Deafened, Stunned, NoReactions, ConcentrationActionMarker, Restrained
from dnd.residues import ASHEN_RESIDUE, deposit_area_residue
from dnd.spells.content_metadata import srd_action_identity, srd_spell_identity
from dnd.spells.spell_utils import fire_heal_roll_result
from dnd.spells.effect_ids import MAGIC_MISSILE_DAMAGE_EFFECT_ID
from dnd.types.spatial_effects import (
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
)


def validate_line_of_sight(declaration_event: SpellEvent, source_entity_uuid: UUID) -> Optional[SpellEvent]:
    """Validate if the source entity and target entity are in line of sight."""
    source_entity = Entity.get(source_entity_uuid)
    if not source_entity:
        return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
    if not isinstance(source_entity, Entity):
        return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
    if not declaration_event.target_entity_uuid:
        return declaration_event.cancel(status_message=f"Target entity uuid not present for {declaration_event.name}")
    target_entity = Entity.get(declaration_event.target_entity_uuid)
    if not target_entity:
        return declaration_event.cancel(status_message=f"Target entity not found for {declaration_event.name}")
    if not isinstance(target_entity, Entity):
        return declaration_event.cancel(status_message=f"Target entity not found for {declaration_event.name}")

    contact = source_entity.senses.entities.get(target_entity.uuid)
    if contact is None or not contact.visual:
        return declaration_event.cancel(status_message=f"Target entity not in line of sight for {declaration_event.name}")
    return declaration_event.phase_to(
        new_phase=EventPhase.EXECUTION,
        status_message=f"Validated line of sight for {declaration_event.name}"
    )


@srd_spell_identity(
    content_id="spell.fire_bolt",
    display_name="Fire Bolt",
    description="Hurl a mote of fire at a target.",
    school="evocation",
    level=0,
    source_page=144,
    sort_order=10,
)
class FireBolt(SpellAction):
    """Fire Bolt - Evocation cantrip

    You hurl a mote of fire at a creature or object within range.
    Make a ranged spell attack. On hit, target takes 1d10 fire damage.
    Damage scales with caster level: 2d10 at 5th, 3d10 at 11th, 4d10 at 17th.
    """
    @property
    def performs_attack(self) -> bool:
        return True

    name: str = Field(default="Fire Bolt", description="Display name for the fire bolt spell.")
    description: str = Field(default="Hurl a mote of fire at a target", description="Rules-facing summary for the fire bolt spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast fire bolt; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify fire bolt.")
    target_type: TargetType = Field(default=TargetType.CREATURE_OR_OBJECT, description="Targeting mode used by action discovery and validation for fire bolt.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for fire bolt.",
    )
    projectile_type: Optional[str] = Field(default="bolt", description="Projectile visualization hint for fire bolt.")
    physical_access: Optional[PhysicalAccess] = PhysicalAccess.PROJECTILE
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Fire Bolt's level-scaled actor-baseline attack model."""
        if not isinstance(actor, Entity):
            return None
        return self.spell_attack_outcome_profile(
            actor,
            dice_count=self._get_cantrip_dice_count(self.caster_level),
            die_size=10,
            damage_type=DamageType.FIRE,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""

        los_event = self.validate_single_recipient(declaration_event)
        if los_event is None or los_event.canceled:
            return los_event

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute the spell attack."""

        caster = Entity.get(self.source_entity_uuid)
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not isinstance(target, (Entity, BaseItem)):
            return execution_event.cancel(status_message="Caster or target not found")

        if isinstance(target, BaseItem) and (not target.is_active or not target.is_targetable
                or not target.is_breakable() or get_map().get_object_placement(target.uuid) is None):
            return execution_event.cancel(status_message="Object is no longer a damageable placed target")
        if (error := self.physical_access_error()) is not None:
            return execution_event.cancel(status_message=error)

        resolution = self.resolve_spell_attack(caster, target, execution_event.uuid)
        attack_bonus = resolution.attack_bonus
        target_ac = resolution.target_ac
        dice_roll = resolution.dice_roll
        outcome = resolution.outcome

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            is_threatened=resolution.is_threatened,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )

        if effect_event.canceled:
            return effect_event
        if isinstance(target, BaseItem) and (not target.is_active or not target.is_targetable
                or not target.is_breakable() or get_map().get_object_placement(target.uuid) is None):
            return effect_event.cancel(status_message="Object is no longer a damageable placed target")
        if (error := self.physical_access_error()) is not None:
            return effect_event.cancel(status_message=error)

        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.with_updates(
                status_message=f"{self.name} missed"
            )

        contact = effect_event.target_position if isinstance(target, BaseItem) else target.position
        if contact is not None:
            contact_layer = target.get_occupancy_layer() if isinstance(target, Entity) else OccupancyLayer.GROUND
            if isinstance(target, BaseItem):
                tile = get_map().get_tile(*contact)
                if tile is not None and effect_event.target_base_height_steps != tile.height:
                    contact_layer = OccupancyLayer.AIR
            ignite_surface_contacts(effect_event, (contact,), occupancy_layer=contact_layer)
        num_dice = self._get_cantrip_dice_count(self.caster_level)
        is_crit = outcome == AttackOutcome.CRIT

        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0
        damage_bonus = caster.get_spell_damage_bonus()
        fire_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=10,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FIRE
        )

        damage_dice = fire_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        if isinstance(target, BaseItem):
            target.receive_damage(damage_roll.total, DamageType.FIRE, caster.uuid,
                parent_event=effect_event, damage_rolls=[damage_roll], damages=[fire_damage])
        else:
            target.receive_damage(amount=damage_roll.total, damage_type=DamageType.FIRE,
                source_entity_uuid=caster.uuid, parent_event=effect_event.uuid,
                damage_rolls=[damage_roll], damages=[fire_damage])

        return effect_event.with_updates(
            damages=[fire_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} fire damage"
        )


class RayOfFrostEffect(BaseCondition):
    """Victim-owned speed reduction, expiring on the caster's next turn."""
    name: str = Field(default="Ray of Frost Effect", description="Display name for the ray of frost effect condition.")
    description: str = Field(
        default=(
            "A creature hit by the caster has its speed reduced by 10 feet "
            "until the start of the caster's next turn."
        ),
        description="Rules-facing summary for the ray of frost effect condition.",
    )
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags that classify the ray of frost slow for cleanup and filtering.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Affected target UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")
        if target.ignore_magical_speed_reduction:
            return [], [], [], [], declaration_event.cancel(status_message=f"{target.name} ignores magical speed reduction")

        outs: List[Tuple[UUID, UUID]] = []

        speed_reduction = NumericalModifier(
            name="Ray of Frost",
            value=-10,
            source_entity_uuid=self.source_entity_uuid or self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        for speed in target.action_economy.speed_values:
            mod_uuid = speed.self_static.add_value_modifier(speed_reduction)
            outs.append((speed.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Ray of Frost speed reduction to {target.name}"
        )
        def expire(event: Event) -> None:
            target.remove_condition_by_uuid(self.uuid, parent_event=event)

        handler = _source_turn_expiry_handler(self, declaration_event, at_end=False, expire=expire)
        target.add_event_handler(handler)
        return outs, [handler.uuid], [], [], effect_event


class RayOfFrost(SpellAction):
    """Ray of Frost - Evocation cantrip

    A frigid beam of blue-white light streaks toward a creature within range.
    Make a ranged spell attack. On hit, target takes 1d8 cold damage and its
    speed is reduced by 10 feet until the start of your next turn.

    Damage scales: 2d8 at 5th, 3d8 at 11th, 4d8 at 17th.
    """
    @property
    def performs_attack(self) -> bool:
        return True

    name: str = Field(default="Ray of Frost", description="Display name for the ray of frost spell.")
    description: str = Field(default="Ranged spell attack, 1d8 cold, target speed -10ft", description="Rules-facing summary for the ray of frost spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast ray of frost; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify ray of frost.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for ray of frost.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for ray of frost.",
    )
    projectile_type: Optional[str] = Field(default="ray", description="Projectile visualization hint for ray of frost.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.COLD, description="Primary damage type for VFX")

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Ray of Frost's level-scaled actor-baseline attack model."""
        if not isinstance(actor, Entity):
            return None
        return self.spell_attack_outcome_profile(
            actor,
            dice_count=self._get_cantrip_dice_count(self.caster_level),
            die_size=8,
            damage_type=DamageType.COLD,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = self.get_target_distance(target_entity.position)
        if distance > self.effective_range:
            return declaration_event.cancel(status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)")

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute the spell attack."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        resolution = self.resolve_spell_attack(caster, target, execution_event.uuid)
        attack_bonus = resolution.attack_bonus
        target_ac = resolution.target_ac
        dice_roll = resolution.dice_roll
        outcome = resolution.outcome

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            is_threatened=resolution.is_threatened,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )

        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.with_updates(
                status_message=f"{self.name} missed"
            )

        num_dice = self._get_cantrip_dice_count(self.caster_level)
        is_crit = outcome == AttackOutcome.CRIT

        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0
        damage_bonus = caster.get_spell_damage_bonus()
        cold_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.COLD
        )

        damage_dice = cold_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.COLD,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        effect_condition = RayOfFrostEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL},
        )
        target.add_condition(effect_condition, parent_event=effect_event)

        return effect_event.with_updates(
            damages=[cold_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} cold damage, speed reduced by 10ft"
        )


class SacredFlame(SpellAction):
    """Sacred Flame - Evocation cantrip

    Flame-like radiance descends on a creature. Target must succeed on a
    DEX save or take 1d8 radiant damage. No benefit from cover.
    Damage scales: 2d8 at 5th, 3d8 at 11th, 4d8 at 17th.
    """
    name: str = Field(default="Sacred Flame", description="Display name for the sacred flame spell.")
    description: str = Field(default="Target must succeed on DEX save or take radiant damage", description="Rules-facing summary for the sacred flame spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast sacred flame; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify sacred flame.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for sacred flame.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for sacred flame.",
    )
    projectile_type: Optional[str] = Field(default="radiance", description="Projectile visualization hint for sacred flame.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Primary damage type for VFX")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = self.get_target_distance(target_entity.position)
        if distance > self.effective_range:
            return declaration_event.cancel(status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)")

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute the save-based spell."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "dexterity").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.with_updates(
                total_damage=0,
                status_message=f"{self.name} - target saved"
            )

        num_dice = self._get_cantrip_dice_count(self.caster_level)

        damage_bonus = caster.get_spell_damage_bonus()
        radiant_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.RADIANT
        )

        damage_dice = radiant_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.RADIANT,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        return effect_event.with_updates(
            damages=[radiant_damage],
            damage_rolls=[damage_roll],
            total_damage=damage_roll.total,
            status_message=f"{self.name} dealt {damage_roll.total} radiant damage"
        )


@srd_spell_identity(
    content_id="spell.magic_missile",
    display_name="Magic Missile",
    description="Create force darts that strike their chosen targets.",
    school="evocation",
    level=1,
    source_page=161,
    sort_order=20,
)
class MagicMissile(SpellAction):
    """Magic Missile - 1st level Evocation

    You create three glowing darts of magical force. Each dart hits automatically
    and deals 1d4+1 force damage. When cast at higher levels, create one additional
    dart per slot level above 1st.

    Darts can be split among multiple targets or all sent to a single target.
    Uses MULTI_ENTITY target type with allow_same_target=True.
    """
    name: str = Field(default="Magic Missile", description="Display name for the magic missile spell.")
    description: str = Field(default="Three darts of force that automatically hit", description="Rules-facing summary for the magic missile spell.")
    spell_level: int = Field(default=1, description="Spell slot level required to cast magic missile; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify magic missile.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Targeting mode used by action discovery and validation for magic missile.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for magic missile.",
    )

    allow_same_target: bool = Field(default=True, description="Whether magic missile may select the same entity more than once.")
    valid_target_filter: str = Field(default="enemies", description="Relationship filter used when collecting valid targets for magic missile.")
    projectile_type: Optional[str] = Field(default="dart", description="Projectile visualization hint for magic missile.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FORCE, description="Primary damage type for VFX")

    def get_num_projectiles(self) -> int:
        """3 darts base + 1 per upcast level."""
        return 3 + self.get_upcast_bonus()

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Magic Missile's automatic per-dart damage model."""
        if not isinstance(actor, Entity):
            return None
        return self.automatic_damage_outcome_profile(
            dice_count=1,
            die_size=4,
            flat_bonus=1,
            damage_type=DamageType.FORCE,
            applications=self.get_num_projectiles(),
            effect_id=MAGIC_MISSILE_DAMAGE_EFFECT_ID,
        )

    def get_allocation_completion(self) -> Literal["selected_only", "fill_primary"]:
        return "fill_primary"

    def get_multi_target_count(self) -> Optional[int]:
        return self.get_num_projectiles()

    def get_all_targets(self) -> List[UUID]:
        """Override: Return targets for each dart (can have repeats).

        If fewer targets specified than darts, fill remaining with primary target.
        """
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)

        num_darts = self.get_num_projectiles()
        while len(targets) < num_darts and self.target_entity_uuid:
            targets.append(self.target_entity_uuid)

        return targets[:num_darts]

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight for all targets."""

        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return declaration_event.cancel(status_message="Source entity not found")

        all_targets = self.get_all_targets()
        validated_targets = set()

        for target_uuid in all_targets:
            if target_uuid in validated_targets:
                continue
            validated_targets.add(target_uuid)

            target_entity = Entity.get(target_uuid)
            if not target_entity:
                return declaration_event.cancel(status_message=f"Target entity not found")

            contact = source_entity.senses.entities.get(target_uuid)
            if contact is None or not contact.visual:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} not in line of sight"
                )

            distance = self.get_target_distance(target_entity.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} out of range ({distance}ft > {self.effective_range}ft)"
                )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply single dart to current target (self.target_entity_uuid).

        Called once per dart by the convolution loop in BaseAction.apply().
        """

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dart_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=4,
            dice_numbers=1,
            damage_bonus=ModifiableValue.create(
                source_entity_uuid=caster.uuid,
                base_value=1,
                value_name="Magic Missile Dart"
            ),
            damage_type=DamageType.FORCE
        )

        damage_dice = dart_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        actual_damage = target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.FORCE,
            source_entity_uuid=caster.uuid,
            parent_event=execution_event.uuid,
            effect_id=MAGIC_MISSILE_DAMAGE_EFFECT_ID,
        )

        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            damages=[dart_damage],
            damage_rolls=[damage_roll],
            total_damage=actual_damage,
            status_message=f"Dart hits {target.name} for {actual_damage} force damage"
        )


class ScorchingRay(SpellAction):
    """Scorching Ray - 2nd level Evocation

    You create three rays of fire and hurl them at targets within range.
    You can hurl them at one target or several. Make a ranged spell attack
    for each ray. On a hit, the target takes 2d6 fire damage.

    At Higher Levels: Create one additional ray for each slot level above 2nd.
    """
    @property
    def performs_attack(self) -> bool:
        return True

    name: str = Field(default="Scorching Ray", description="Display name for the scorching ray spell.")
    description: str = Field(default="3 rays, each 2d6 fire, ranged spell attack per ray", description="Rules-facing summary for the scorching ray spell.")
    spell_level: int = Field(default=2, description="Spell slot level required to cast scorching ray; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify scorching ray.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Targeting mode used by action discovery and validation for scorching ray.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for scorching ray.",
    )

    allow_same_target: bool = Field(default=True, description="Whether scorching ray may select the same entity more than once.")
    valid_target_filter: str = Field(default="enemies", description="Relationship filter used when collecting valid targets for scorching ray.")
    projectile_type: Optional[str] = Field(default="ray", description="Projectile visualization hint for scorching ray.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")

    def get_num_projectiles(self) -> int:
        """3 rays base + 1 per upcast level."""
        return 3 + self.get_upcast_bonus()

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Scorching Ray's independent per-ray attack model."""
        if not isinstance(actor, Entity):
            return None
        return self.spell_attack_outcome_profile(
            actor,
            dice_count=2,
            die_size=6,
            damage_type=DamageType.FIRE,
            applications=self.get_num_projectiles(),
        )

    def get_allocation_completion(self) -> Literal["selected_only", "fill_primary"]:
        return "fill_primary"

    def get_multi_target_count(self) -> Optional[int]:
        return self.get_num_projectiles()

    def get_all_targets(self) -> List[UUID]:
        """Return targets for each ray (can have repeats)."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)

        num_rays = self.get_num_projectiles()
        while len(targets) < num_rays and self.target_entity_uuid:
            targets.append(self.target_entity_uuid)

        return targets[:num_rays]

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and LOS for all targets."""

        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return declaration_event.cancel(status_message="Source entity not found")

        all_targets = self.get_all_targets()
        validated_targets = set()

        for target_uuid in all_targets:
            if target_uuid in validated_targets:
                continue
            validated_targets.add(target_uuid)

            target_entity = Entity.get(target_uuid)
            if not target_entity:
                return declaration_event.cancel(status_message="Target entity not found")

            contact = source_entity.senses.entities.get(target_uuid)
            if contact is None or not contact.visual:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} not in line of sight"
                )

            distance = self.get_target_distance(target_entity.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} out of range ({distance}ft > {self.effective_range}ft)"
                )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply single ray to current target (called once per ray by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        resolution = self.resolve_spell_attack(caster, target, execution_event.uuid)
        attack_bonus = resolution.attack_bonus
        target_ac = resolution.target_ac
        dice_roll = resolution.dice_roll
        outcome = resolution.outcome

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            is_threatened=resolution.is_threatened,
            status_message=f"Ray attack: {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )

        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.with_updates(
                target_entity_name=target.name,
                total_damage=0,
                status_message=f"Ray misses {target.name}"
            )

        is_crit = outcome == AttackOutcome.CRIT
        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0

        damage_bonus = caster.get_spell_damage_bonus()
        fire_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=2,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FIRE
        )

        damage_dice = fire_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.FIRE,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        return effect_event.with_updates(
            target_entity_name=target.name,
            damages=[fire_damage],
            damage_rolls=[damage_roll],
            total_damage=damage_roll.total,
            status_message=f"Ray hits {target.name} for {damage_roll.total} fire damage"
        )


@srd_spell_identity(
    content_id="spell.fireball",
    display_name="Fireball",
    description="Create a fiery explosion centered on a point in range.",
    school="evocation",
    level=3,
    source_page=144,
    sort_order=30,
)
class Fireball(SpellAction):
    """Fireball - 3rd level Evocation

    A bright streak flashes from your pointing finger to a point you choose
    within range and then blossoms with a low roar into an explosion of flame.

    Each creature in a 20-foot-radius sphere centered on that point must make
    a DEX saving throw. A target takes 8d6 fire damage on a failed save,
    or half as much on a successful one.

    At Higher Levels: +1d6 damage per slot level above 3rd.
    """
    name: str = Field(default="Fireball", description="Display name for the fireball spell.")
    description: str = Field(default="20ft radius explosion dealing 8d6 fire damage (DEX save half)", description="Rules-facing summary for the fireball spell.")
    spell_level: int = Field(default=3, description="Spell slot level required to cast fireball; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify fireball.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for fireball.")
    aoe_require_targets: bool = Field(default=False, description="Fireball can target an empty visible area.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150), description="Range contract used when validating targets for fireball.")
    projectile_type: Optional[str] = Field(default="orb", description="Projectile visualization hint for fireball.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by fireball to compute affected targets.")

    include_self: bool = Field(default=True, description="Whether fireball can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for fireball.")

    base_damage_dice: int = Field(default=8, description="Base number of damage dice rolled by fireball.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                radius_feet=20,
                propagation="connected",
            )

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        if self.effective_target_type is TargetType.POSITION_AOE:
            return self._resolve_area_targets()
        return super()._resolve_execution_targets()

    def _finalize_aoe(self, effect_event: ActionEvent) -> None:
        """Leave inert Ashen conditions on surfaces actually reached by the blast."""
        deposit_area_residue(effect_event.resolved_area_positions or (), ASHEN_RESIDUE,
                             parent_event=effect_event)

    def _apply_target_applications(
        self, execution_event: ActionEvent, effect_event: ActionEvent,
        target_uuids: List[UUID],
    ) -> ActionEvent:
        """Resolve finite blast reach, actual destruction, then newly exposed targets."""
        if self.effective_target_type is not TargetType.POSITION_AOE:
            return super()._apply_target_applications(
                execution_event, effect_event, target_uuids,
            )
        if not isinstance(execution_event, SpellEvent) or not isinstance(effect_event, SpellEvent):
            raise TypeError("Fireball requires spell events")
        caster = Entity.get(self.source_entity_uuid)
        if caster is None or self.aoe_shape is None or self.end_position is None:
            return effect_event.cancel(status_message="Fireball has no caster or area")
        source_position = execution_event.effect_source_position or execution_event.source_position
        if source_position is None:
            return effect_event.cancel(status_message="Fireball has no recorded source position")
        shape = self.aoe_shape.model_copy(deep=True, update={"target": self.end_position})
        origin = shape.get_origin(source_position)
        envelope = shape.geometric_positions(source_position)
        grid = get_map()
        visited: Set[UUID] = set()
        displayed_positions: Set[Tuple[int, int]] = set()
        suppressions: dict[UUID, Set[Tuple[int, int]]] = {}
        total_damage = 0
        application_index = 0
        stage_index = 0
        previous_stage: UUID | None = None
        prerequisites: Tuple[UUID, ...] = ()

        while True:
            history = EventQueue.get_event_history(effect_event.uuid)
            if history and history[-1].canceled:
                return type_cast(ActionEvent, history[-1])
            shape.compute_objective(source_position)
            reached = shape.affected_positions & envelope
            contacts = grid.area_object_contacts(reached, geometric_positions=envelope, origin=origin)
            creatures = self._filter_targets_by_faction(caster, list(shape.affected_entity_uuids))
            candidates = {identity for identity in creatures
                if (self.include_self or identity != caster.uuid)
                and (self.include_dead or ((block := BaseBlock.get(identity)) is not None and block.is_active))}
            candidates.update(identity for identity in contacts
                if isinstance(item := BaseBlock.get(identity), BaseItem)
                and item.is_targetable and item.is_breakable())
            candidates.difference_update(visited)
            excluded = SpellProtectionRegistry.get_excluded_positions(source_position, self.spell_level)
            allowed = reached - excluded
            newly_reached = allowed - displayed_positions
            for suppression in SpellProtectionRegistry.get_suppressions(source_position, self.spell_level, reached):
                suppressions.setdefault(suppression.provider_uuid, set()).update(suppression.positions)
            if stage_index and not newly_reached and not candidates:
                break
            stage = AreaReachEvent(source_entity_uuid=caster.uuid,
                source_entity_name=caster.name, parent_event=effect_event.uuid,
                stage_index=stage_index, newly_reached_positions=tuple(sorted(newly_reached)),
                previous_reach_lineage_uuid=previous_stage,
                prerequisite_destruction_lineages=prerequisites)
            stage = stage.phase_to(EventPhase.EXECUTION)
            if not stage.canceled:
                stage = stage.phase_to(EventPhase.EFFECT)
            if stage.canceled:
                return effect_event.cancel(status_message="Fireball area expansion interrupted")
            displayed_positions.update(newly_reached)

            def target_order(identity: UUID) -> tuple[int, Tuple[int, int], str, str]:
                block = BaseBlock.get(identity)
                depth = 0
                parent = block.supported_by_uuid if isinstance(block, BaseItem) else None
                while parent is not None:
                    depth += 1
                    owner = BaseBlock.get(parent)
                    parent = owner.supported_by_uuid if isinstance(owner, BaseItem) else None
                return (depth, contacts.get(identity, block.position if block else origin),
                        block.name or "" if block else "", str(identity))

            barriers = set()
            for identity in contacts:
                block = BaseBlock.get(identity)
                if block is None:
                    continue
                structure = block.get_boundary_structure()
                if block.blocks_propagation() or (structure is not None
                        and WorldEdgeChannel.PROPAGATION in structure.blocked_channels):
                    barriers.add(identity)
            cursor = EventQueue.event_cursor()
            revision = grid.propagation_revision
            for identity in sorted(candidates, key=target_order):
                visited.add(identity)
                recipient = BaseBlock.get(identity)
                if recipient is None or (isinstance(recipient, BaseItem) and not recipient.is_breakable()):
                    continue  # The parent may already have destroyed its insert.
                placement = grid.get_object_placement(identity)
                application = execution_event.with_updates(
                    target_kind="object" if isinstance(recipient, BaseItem) else "creature",
                    target_position=contacts.get(identity, recipient.position),
                    target_base_height_steps=placement.base_height_steps if placement else None,
                )
                total_damage += self._apply_target_batch(application, [identity],
                    parent_event=stage, application_index_offset=application_index)
                application_index += 1
                history = EventQueue.get_event_history(effect_event.uuid)
                if history and history[-1].canceled:
                    stage.cancel(status_message="Parent cast interrupted")
                    return type_cast(ActionEvent, history[-1])
            ignite_surface_contacts(stage, newly_reached)
            stage = stage.phase_to(EventPhase.COMPLETION)
            previous_stage = stage.lineage_uuid
            prerequisites = tuple(event.lineage_uuid for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, ItemDestructionEvent) and event.phase is EventPhase.COMPLETION
                and event.target_entity_uuid in barriers)
            if grid.propagation_revision == revision:
                break
            stage_index += 1

        return effect_event.with_updates(total_targets=application_index, total_damage=total_damage,
            resolved_area_positions=tuple(sorted(displayed_positions)),
            suppressions=tuple(SpellSuppression(provider_uuid=identity, positions=tuple(sorted(positions)))
                for identity, positions in sorted(suppressions.items(), key=lambda pair: str(pair[0]))),
            status_message=f"Fireball affected {application_index} targets for {total_damage} total damage")

    def get_damage_dice_count(self) -> int:
        """8d6 base + 1d6 per level above 3rd."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Fireball's actor-known save and damage rule."""
        if not isinstance(actor, Entity):
            return None
        return self.saving_throw_damage_outcome_profile(
            actor,
            dice_count=self.get_damage_dice_count(),
            die_size=6,
            damage_type=DamageType.FIRE,
            save_ability="dexterity",
            half_damage_on_save=True,
            application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(
                status_message=f"Target position {target_pos} not in line of sight"
            )

        distance = self.get_target_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Resolve one exposed recipient; objects receive no creature save."""
        caster = Entity.get(self.source_entity_uuid)
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if caster is None or not isinstance(target, (Entity, BaseItem)):
            return execution_event.cancel(status_message="Caster or target not found")
        if isinstance(target, BaseItem):
            if not target.is_breakable() or get_map().get_object_placement(target.uuid) is None:
                return execution_event.cancel(status_message="Object is no longer a damageable placed target")
            success = False
            effect_event = execution_event.phase_to(EventPhase.EFFECT)
        else:
            dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
            save_request = caster.create_saving_throw_request(target_entity_uuid=target.uuid,
                ability_name="dexterity", dc=dc, parent_event=execution_event.uuid)
            _, save_roll, success = target.saving_throw(save_request)
            effect_event = execution_event.phase_to(EventPhase.EFFECT,
                save_ability="dexterity", save_dc=dc, save_success=success,
                save_roll=save_roll, save_bonus=save_roll.bonus,
                target_entity_name=target.name,
                status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}")
        if effect_event.canceled:
            return effect_event
        fire_damage = Damage(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            damage_dice=6, dice_numbers=self.get_damage_dice_count(),
            damage_bonus=caster.get_spell_damage_bonus(), damage_type=DamageType.FIRE)
        damage_roll = fire_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        final_damage = damage_roll.total // 2 if success else damage_roll.total
        if final_damage > 0:
            if isinstance(target, BaseItem):
                target.receive_damage(final_damage, DamageType.FIRE, caster.uuid,
                    parent_event=effect_event, damage_rolls=[damage_roll], damages=[fire_damage])
            else:
                target.receive_damage(final_damage, DamageType.FIRE, caster.uuid,
                    parent_event=effect_event.uuid, damage_rolls=[damage_roll], damages=[fire_damage])
        save_text = " (saved for half)" if success else ""
        return effect_event.with_updates(damages=[fire_damage], damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Fireball deals {final_damage} fire damage to {target.name}{save_text}")


@srd_spell_identity(
    content_id="spell.burning_hands",
    display_name="Burning Hands",
    description="Project a close cone of flame.",
    school="evocation",
    level=1,
    source_page=123,
    sort_order=10,
    icon_key="spell.burning-hands",
)
class BurningHands(SpellAction):
    """Burning Hands - 1st level Evocation

    As you hold your hands with thumbs touching and fingers spread, a thin sheet
    of flames shoots forth from your outstretched fingertips. Each creature in a
    15-foot cone must make a DEX save. A creature takes 3d6 fire damage on a
    failed save, or half as much on a successful one.

    At Higher Levels: +1d6 damage per slot level above 1st.
    """
    aoe_require_targets: bool = False
    name: str = Field(default="Burning Hands", description="Display name for the burning hands spell.")
    description: str = Field(default="15ft cone of fire dealing 3d6 fire damage (DEX save half)", description="Rules-facing summary for the burning hands spell.")
    spell_level: int = Field(default=1, description="Spell slot level required to cast burning hands; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify burning hands.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for burning hands.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Range contract used when validating targets for burning hands.")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by burning hands to compute affected targets.")

    include_self: bool = Field(default=False, description="Whether burning hands can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for burning hands.")

    base_damage_dice: int = Field(default=3, description="Base number of damage dice rolled by burning hands.")

    def _finalize_aoe(self, effect_event: ActionEvent) -> None:
        assert isinstance(effect_event, SpellEvent)
        origin = effect_event.effect_source_position or effect_event.source_position
        if origin is None:
            return
        excluded = SpellProtectionRegistry.get_excluded_positions(origin, self.spell_level)
        ignite_surface_contacts(effect_event, set(effect_event.resolved_area_positions or ()) - excluded)

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        if self.effective_target_type is TargetType.POSITION_AOE:
            return self._resolve_area_targets()
        return super()._resolve_execution_targets()

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cone(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                length_feet=15
            )

    def get_damage_dice_count(self) -> int:
        """3d6 base + 1d6 per level above 1st."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Burning Hands' actor-known save and damage rule."""
        if not isinstance(actor, Entity):
            return None
        return self.saving_throw_damage_outcome_profile(
            actor,
            dice_count=self.get_damage_dice_count(),
            die_size=6,
            damage_type=DamageType.FIRE,
            save_ability="dexterity",
            half_damage_on_save=True,
            application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate cone direction. Self-range means no LOS check to target position."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified for cone")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply burning hands damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "dexterity").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        num_dice = self.get_damage_dice_count()
        damage_bonus = caster.get_spell_damage_bonus()

        fire_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FIRE
        )

        damage_dice = fire_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        final_damage = damage_roll.total // 2 if success else damage_roll.total

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.FIRE,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.with_updates(
            damages=[fire_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Burning Hands deals {final_damage} fire damage to {target.name}{save_text}"
        )


class LightningBolt(SpellAction):
    """Lightning Bolt - 3rd level Evocation

    A stroke of lightning forming a line 100 feet long and 5 feet wide blasts
    out from you in a direction you choose. Each creature in the line must make
    a DEX save. A creature takes 8d6 lightning damage on a failed save, or half
    as much on a successful one.

    At Higher Levels: +1d6 damage per slot level above 3rd.
    """
    aoe_require_targets: bool = False
    name: str = Field(default="Lightning Bolt", description="Display name for the lightning bolt spell.")
    description: str = Field(default="100ft×5ft line dealing 8d6 lightning damage (DEX save half)", description="Rules-facing summary for the lightning bolt spell.")
    spell_level: int = Field(default=3, description="Spell slot level required to cast lightning bolt; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify lightning bolt.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.LIGHTNING, description="Primary damage type for VFX")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for lightning bolt.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Range contract used when validating targets for lightning bolt.")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by lightning bolt to compute affected targets.")

    include_self: bool = Field(default=False, description="Whether lightning bolt can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for lightning bolt.")

    base_damage_dice: int = Field(default=8, description="Base number of damage dice rolled by lightning bolt.")

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        return self._resolve_area_targets()

    def _finalize_aoe(self, effect_event: ActionEvent) -> None:
        assert isinstance(effect_event, SpellEvent)
        origin = effect_event.effect_source_position or effect_event.source_position
        if origin is not None:
            excluded = SpellProtectionRegistry.get_excluded_positions(origin, self.spell_level)
            ignite_surface_contacts(effect_event, set(effect_event.resolved_area_positions or ()) - excluded)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Line(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                length_feet=100,
                width_feet=5
            )

    def get_damage_dice_count(self) -> int:
        """8d6 base + 1d6 per level above 3rd."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Lightning Bolt's actor-known save and damage rule."""
        if not isinstance(actor, Entity):
            return None
        return self.saving_throw_damage_outcome_profile(
            actor,
            dice_count=self.get_damage_dice_count(),
            die_size=6,
            damage_type=DamageType.LIGHTNING,
            save_ability="dexterity",
            half_damage_on_save=True,
            application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line direction. Self-range means no LOS check to target position."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified for line")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply lightning bolt damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "dexterity").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        num_dice = self.get_damage_dice_count()
        damage_bonus = caster.get_spell_damage_bonus()

        lightning_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.LIGHTNING
        )

        damage_dice = lightning_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        final_damage = damage_roll.total // 2 if success else damage_roll.total

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.LIGHTNING,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.with_updates(
            damages=[lightning_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Lightning Bolt deals {final_damage} lightning damage to {target.name}{save_text}"
        )


class Thunderwave(SpellAction):
    """Thunderwave - 1st level Evocation

    A wave of thunderous force sweeps out from you. Each creature in a 15-foot
    cube originating from you must make a CON save. On a failed save, a creature
    takes 2d8 thunder damage and is pushed 10 feet away from you. On a successful
    save, the creature takes half as much damage and isn't pushed.

    At Higher Levels: +1d8 damage per slot level above 1st.
    """
    name: str = Field(default="Thunderwave", description="Display name for the thunderwave spell.")
    description: str = Field(default="15ft cube dealing 2d8 thunder + 10ft push on fail (CON save)", description="Rules-facing summary for the thunderwave spell.")
    spell_level: int = Field(default=1, description="Spell slot level required to cast thunderwave; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify thunderwave.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.THUNDER, description="Primary damage type for VFX")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for thunderwave.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Range contract used when validating targets for thunderwave.")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by thunderwave to compute affected targets.")

    include_self: bool = Field(default=False, description="Whether thunderwave can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for thunderwave.")

    base_damage_dice: int = Field(default=2, description="Base number of damage dice rolled by thunderwave.")
    push_distance_feet: int = Field(default=10, description="Distance in feet that thunderwave attempts to push failed-save targets.")

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        if self.effective_target_type is TargetType.POSITION_AOE:
            return self._resolve_area_targets()
        return super()._resolve_execution_targets()

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                size_feet=15,
                centered=False
            )

    def get_damage_dice_count(self) -> int:
        """2d8 base + 1d8 per level above 1st."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Thunderwave's actor-known save and damage rule."""
        if not isinstance(actor, Entity):
            return None
        return self.saving_throw_damage_outcome_profile(
            actor,
            dice_count=self.get_damage_dice_count(),
            die_size=8,
            damage_type=DamageType.THUNDER,
            save_ability="constitution",
            half_damage_on_save=True,
            application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
        )

    def _get_push_direction(self, caster_pos: Tuple[int, int], target_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Calculate push direction - away from caster (radial)."""
        dx = target_pos[0] - caster_pos[0]
        dy = target_pos[1] - caster_pos[1]

        if dx != 0:
            dx = 1 if dx > 0 else -1
        if dy != 0:
            dy = 1 if dy > 0 else -1

        if dx == 0 and dy == 0:
            if self.end_position:
                dx = 1 if self.end_position[0] > caster_pos[0] else (-1 if self.end_position[0] < caster_pos[0] else 0)
                dy = 1 if self.end_position[1] > caster_pos[1] else (-1 if self.end_position[1] < caster_pos[1] else 0)
            if dx == 0 and dy == 0:
                dx = 1

        return (dx, dy)

    def _calculate_push_destination(
        self,
        start: Tuple[int, int],
        direction: Tuple[int, int],
        distance_feet: int,
        target_uuid: UUID
    ) -> Tuple[Tuple[int, int], int, bool, Optional[str]]:
        """Calculate where target lands after being pushed.

        Returns: (final_position, actual_distance_feet, was_blocked, blocked_by)
        """

        return Shove.calculate_final_position(start, direction, distance_feet, target_uuid)

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate cube direction. Self-range means no LOS check to target position."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified for cube")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply thunderwave damage and push to current target."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "constitution").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"CON save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        num_dice = self.get_damage_dice_count()
        damage_bonus = caster.get_spell_damage_bonus()

        thunder_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.THUNDER
        )

        damage_dice = thunder_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        final_damage = damage_roll.total // 2 if success else damage_roll.total

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.THUNDER,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

        push_applied = False
        push_distance_actual = 0
        if not success:
            start_pos = target.senses.position
            push_dir = self._get_push_direction(caster.senses.position, start_pos)
            end_pos, push_distance_actual, was_blocked, blocked_by = self._calculate_push_destination(
                start_pos, push_dir, self.push_distance_feet, target.uuid
            )

            if end_pos != start_pos:

                forced_event = ForcedMovementEvent(
                    source_entity_uuid=caster.uuid,
                    target_entity_uuid=target.uuid,
                    source_entity_name=caster.name,
                    target_entity_name=target.name,
                    start_position=start_pos,
                    end_position=end_pos,
                    direction=push_dir,
                    intended_distance=self.push_distance_feet,
                    actual_distance=push_distance_actual,
                    blocked_by_obstacle=was_blocked,
                    blocked_by=blocked_by,
                    cause="thunderwave",
                    phase=EventPhase.DECLARATION,
                    parent_event=effect_event.uuid
                )

                forced_event = forced_event.phase_to(EventPhase.EXECUTION)
                forced_event = forced_event.phase_to(EventPhase.EFFECT)
                forced_event = commit_forced_movement(target, forced_event, parent_event=effect_event)
                push_distance_actual = forced_event.actual_distance
                push_applied = True

        save_text = " (saved for half)" if success else ""
        push_text = f", pushed {push_distance_actual}ft" if push_applied else ""
        return effect_event.with_updates(
            damages=[thunder_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Thunderwave deals {final_damage} thunder damage to {target.name}{save_text}{push_text}"
        )


class Shatter(SpellAction):
    """Shatter - 2nd level Evocation

    A sudden loud ringing noise, painfully intense, erupts from a point of your
    choice within range. Each creature in a 10-foot-radius sphere centered on
    that point must make a CON save. A creature takes 3d8 thunder damage on a
    failed save, or half as much damage on a successful one.

    At Higher Levels: +1d8 damage per slot level above 2nd.
    """
    name: str = Field(default="Shatter", description="Display name for the shatter spell.")
    description: str = Field(default="10ft radius sphere dealing 3d8 thunder damage (CON save half)", description="Rules-facing summary for the shatter spell.")
    spell_level: int = Field(default=2, description="Spell slot level required to cast shatter; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify shatter.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for shatter.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60), description="Range contract used when validating targets for shatter.")
    projectile_type: Optional[str] = Field(default="orb", description="Projectile visualization hint for shatter.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.THUNDER, description="Primary damage type for VFX")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by shatter to compute affected targets.")

    include_self: bool = Field(default=True, description="Whether shatter can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for shatter.")

    base_damage_dice: int = Field(default=3, description="Base number of damage dice rolled by shatter.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                radius_feet=10
            )

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        if self.effective_target_type is TargetType.POSITION_AOE:
            return self._resolve_area_targets()
        return super()._resolve_execution_targets()

    def get_damage_dice_count(self) -> int:
        """3d8 base + 1d8 per level above 2nd."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Shatter's actor-known save and damage rule."""
        if not isinstance(actor, Entity):
            return None
        return self.saving_throw_damage_outcome_profile(
            actor,
            dice_count=self.get_damage_dice_count(),
            die_size=8,
            damage_type=DamageType.THUNDER,
            save_ability="constitution",
            half_damage_on_save=True,
            application_scope=OutcomeApplicationScope.EACH_AFFECTED_ENTITY,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(
                status_message=f"Target position {target_pos} not in line of sight"
            )

        distance = self.get_target_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply shatter damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "constitution").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"CON save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        num_dice = self.get_damage_dice_count()
        damage_bonus = caster.get_spell_damage_bonus()

        thunder_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.THUNDER
        )

        damage_dice = thunder_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        final_damage = damage_roll.total // 2 if success else damage_roll.total

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.THUNDER,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.with_updates(
            damages=[thunder_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Shatter deals {final_damage} thunder damage to {target.name}{save_text}"
        )


class CircleOfDeath(SpellAction):
    """Circle of Death - 6th level Necromancy

    A sphere of negative energy ripples out in a 60-foot-radius sphere from a
    point within range. Each creature in that area must make a Constitution
    saving throw. A target takes 8d6 necrotic damage on a failed save, or
    half as much damage on a successful one.

    At Higher Levels: +2d6 damage per slot level above 6th.
    """
    name: str = Field(default="Circle of Death", description="Display name for the circle of death spell.")
    description: str = Field(default="60ft radius sphere dealing 8d6 necrotic damage (CON save half)", description="Rules-facing summary for the circle of death spell.")
    spell_level: int = Field(default=6, description="Spell slot level required to cast circle of death; cantrips use 0.")
    spell_school: str = Field(default="necromancy", description="D&D school of magic used to classify circle of death.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for circle of death.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150), description="Range contract used when validating targets for circle of death.")
    projectile_type: Optional[str] = Field(default="orb", description="Projectile visualization hint for circle of death.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.NECROTIC, description="Primary damage type for VFX")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by circle of death to compute affected targets.")

    include_self: bool = Field(default=True, description="Whether circle of death can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for circle of death.")

    base_damage_dice: int = Field(default=8, description="Base number of damage dice rolled by circle of death.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                radius_feet=60
            )

    def get_damage_dice_count(self) -> int:
        """8d6 base + 2d6 per level above 6th."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + (upcast_bonus * 2)

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(
                status_message=f"Target position {target_pos} not in line of sight"
            )

        distance = self.get_target_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply circle of death damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "constitution").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"CON save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )
        if effect_event.canceled:
            return effect_event

        num_dice = self.get_damage_dice_count()
        damage_bonus = caster.get_spell_damage_bonus()

        necrotic_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.NECROTIC
        )

        damage_dice = necrotic_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        final_damage = damage_roll.total // 2 if success else damage_roll.total

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.NECROTIC,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid,
                damage_rolls=[damage_roll],
                damages=[necrotic_damage],
                effect_origin=execution_event.get_effect_origin(),
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.with_updates(
            damages=[necrotic_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Circle of Death deals {final_damage} necrotic damage to {target.name}{save_text}"
        )


class ConeOfCold(SpellAction):
    """Cone of Cold - 5th level Evocation

    A blast of cold air erupts from your hands. Each creature in a 60-foot cone
    must make a Constitution saving throw. A creature takes 8d8 cold damage on
    a failed save, or half as much damage on a successful one.

    At Higher Levels: +1d8 damage per slot level above 5th.
    """
    name: str = Field(default="Cone of Cold", description="Display name for the cone of cold spell.")
    description: str = Field(default="60ft cone dealing 8d8 cold damage (CON save half)", description="Rules-facing summary for the cone of cold spell.")
    spell_level: int = Field(default=5, description="Spell slot level required to cast cone of cold; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify cone of cold.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.COLD, description="Primary damage type for VFX")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for cone of cold.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Range contract used when validating targets for cone of cold.")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by cone of cold to compute affected targets.")

    include_self: bool = Field(default=False, description="Whether cone of cold can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for cone of cold.")

    base_damage_dice: int = Field(default=8, description="Base number of damage dice rolled by cone of cold.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cone(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                length_feet=60
            )

    def get_damage_dice_count(self) -> int:
        """8d8 base + 1d8 per level above 5th."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate cone direction. Self-range means no LOS check to target position."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified for cone")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply cone of cold damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "constitution").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"CON save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        num_dice = self.get_damage_dice_count()
        damage_bonus = caster.get_spell_damage_bonus()

        cold_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.COLD
        )

        damage_dice = cold_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        final_damage = damage_roll.total // 2 if success else damage_roll.total

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.COLD,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.with_updates(
            damages=[cold_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Cone of Cold deals {final_damage} cold damage to {target.name}{save_text}"
        )


def _source_turn_expiry_handler(owner: BaseCondition, application: Event, *,
                                at_end: bool, expire: Callable[[Event], None]) -> EventHandler:
    """Source-turn deadlines, using native source turns and world rounds.

    A departed or dead source has no next turn; retain the effect until the
    next world round boundary instead of tying it to a recipient's initiative.
    """
    armed = False
    application_turn = application.turn_execution_id

    def processor(event: Event, _source_uuid: UUID) -> Optional[Event]:
        nonlocal armed
        if not owner.applied:
            return None
        if event.event_type is EventType.ROUND_END:
            source = Entity.get(owner.source_entity_uuid)
            if source is None or not source.is_deployed or source.health.life_state is LifeState.DEAD:
                expire(event)
        elif event.source_entity_uuid == owner.source_entity_uuid:
            if application_turn is not None and event.turn_execution_id == application_turn:
                return None
            if event.event_type is EventType.TURN_START:
                armed = True
                if not at_end:
                    expire(event)
            elif armed:
                expire(event)
        return None

    return EventHandler(name=f"{owner.name} source-turn expiry", source_entity_uuid=owner.source_entity_uuid,
        runs_while_suppressed=True,
        trigger_conditions=[
            Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=owner.source_entity_uuid),
            Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=owner.source_entity_uuid),
            Trigger(event_type=EventType.ROUND_END, event_phase=EventPhase.EFFECT),
        ], event_processor=processor)


def _share_solar_blindness(owner: BaseCondition, target: Entity, event: Event) -> bool:
    child = target.active_conditions.get("Blinded")
    if child is None:
        child = Blinded(source_entity_uuid=owner.source_entity_uuid, target_entity_uuid=target.uuid,
            parent_condition=owner.uuid, tags={ConditionTag.MAGICAL}, effect_origin=owner.effect_origin)
        application = target.add_condition(child, parent_event=event)
        if application is None or application.canceled or not child.applied:
            return False
    owner.add_shared_subcondition(child)
    return True


class SunburstBlindedEffect(BaseCondition):
    """
    Blindness effect from Sunburst spell.

    - Has Blinded as sub-condition
    - Repeat CON save at end of each turn to end blindness
    """
    name: str = Field(default="Sunburst Blindness", description="Display name for the sunburst blinded effect condition.")
    description: str = Field(default="Blinded by brilliant sunlight", description="Rules-facing summary for the sunburst blinded effect condition.")

    caster_uuid: Optional[UUID] = Field(default=None, description="Caster UUID used for ownership and effect attribution by sunburst blinded effect.")
    spell_dc: int = Field(default=10, description="Spell save DC used by sunburst blinded effect saving throws.")
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=10))

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        if not _share_solar_blindness(self, target, declaration_event):
            return [], [], [], [], declaration_event.cancel(status_message="Blinded was not admitted")

        if self.caster_uuid:
            handler = self._create_repeat_save_handler()
            target.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Sunburst blindness to {target.name}"
        )
        return [], handler_uuids, sub_condition_uuids, [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """CON save at end of turn to end blindness."""
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid
        effect_uuid = self.uuid
        dc = self.spell_dc

        def repeat_save_processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            if effect_uuid not in target.active_conditions_by_uuid:
                return None
            save_request = SavingThrowEvent(
                source_entity_uuid=caster_uuid,
                target_entity_uuid=target.uuid,
                target_entity_name=target.name,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid,
                saving_throw_context=SavingThrowContext(cause_id="spell.sunburst",
                    effect_id="spell.sunburst.repeat_save", condition_id="condition.blinded", is_magical=True),
            )
            _, _, success = target.saving_throw(save_request)

            if success:

                target.remove_condition_by_uuid(effect_uuid, parent_event=event)
            return None

        return EventHandler(
            name=f"Sunburst Blindness Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT)
            ],
            event_processor=repeat_save_processor
        )


class Sunburst(SpellAction):
    """Sunburst - 8th level Evocation

    Brilliant sunlight flashes in a 60-foot radius. Each creature must make
    a CON save. On failed save: 12d6 radiant damage and blinded for 1 minute.
    On success: half damage, not blinded.

    Undead and oozes have disadvantage on the save.
    Repeat CON save at end of each turn to end blindness.
    """
    name: str = Field(default="Sunburst", description="Display name for the sunburst spell.")
    description: str = Field(default="60ft sphere, 12d6 radiant, CON save or blinded", description="Rules-facing summary for the sunburst spell.")
    spell_level: int = Field(default=8, description="Spell slot level required to cast sunburst; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify sunburst.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Primary damage type for VFX")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for sunburst.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150), description="Range contract used when validating targets for sunburst.")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by sunburst to compute affected targets.")

    include_self: bool = Field(default=True, description="Whether sunburst can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for sunburst.")

    aoe_require_targets: bool = False

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        return self._resolve_area_targets()

    base_damage_dice: int = Field(default=12, description="Base number of damage dice rolled by sunburst.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                radius_feet=60
            )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position LOS and range."""

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
            return declaration_event.cancel(status_message=f"Out of range ({distance}ft)")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply sunburst damage and blindness to current target."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        has_disadvantage = target.creature_type in [CreatureType.UNDEAD, CreatureType.OOZE]

        mod_uuid: Optional[UUID] = None
        if has_disadvantage:
            disadv_mod = AdvantageModifier(
                name="Sunburst (Undead/Ooze)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            mod_uuid = target.saving_throws.get_saving_throw("constitution").bonus.self_static.add_advantage_modifier(disadv_mod)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        try:
            _, save_roll, success = target.saving_throw(save_request)
        finally:
            if mod_uuid is not None:
                target.saving_throws.get_saving_throw("constitution").bonus.self_static.remove_modifier(mod_uuid)

        save_bonus = target.saving_throw_bonus(caster.uuid, "constitution").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"CON save: {save_roll.total} vs DC {dc}"
        )

        if effect_event.canceled:
            return effect_event
        damage_bonus = caster.get_spell_damage_bonus()
        radiant_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=self.base_damage_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.RADIANT
        )

        damage_dice = radiant_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        final_damage = damage_roll.total // 2 if success else damage_roll.total

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.RADIANT,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid,
                damages=[radiant_damage], damage_rolls=[damage_roll],
                effect_origin=execution_event.to_effect_origin(),
            )

        if not success and target.health.life_state is not LifeState.DEAD:
            blind_effect = SunburstBlindedEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid,
                spell_dc=dc,
                tags={ConditionTag.MAGICAL}
            )
            target.add_condition(blind_effect, parent_event=effect_event)

        blind_text = " and blinded" if not success else ""
        return effect_event.with_updates(
            damages=[radiant_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Sunburst: {final_damage} radiant{blind_text} to {target.name}"
        )

    def _finalize_aoe(self, effect_event: SpellEvent) -> None:
        positions = set(effect_event.resolved_area_positions or ())
        for condition in tuple(get_map().get_spatial_conditions()):
            if not isinstance(condition, SpatialCondition):
                continue
            origin = condition.effect_origin
            if (origin is not None and origin.kind is EffectOriginKind.SPELL
                    and condition.optical_obscurement is OpticalObscurement.MAGICAL_DARKNESS
                    and not condition.affected_positions.isdisjoint(positions)):
                condition.deactivate(parent_event=effect_event)


def _is_wearing_metal_armor(entity) -> bool:
    """Check if entity is wearing metal armor (for Shocking Grasp advantage).

    Metal armors in D&D 5e SRD:
    - Heavy armor: Ring Mail, Chain Mail, Splint, Plate (all metal)
    - Medium armor: Chain Shirt, Scale Mail, Half Plate (metal); Hide, Breastplate (not metal)
    - Light armor: None are metal
    - Shields: Standard shields can be metal

    We check by armor name since ArmorType.HEAVY is always metal,
    and some medium armors contain "Chain", "Scale", or "Plate" in their name.
    """

    body_armor = entity.equipment.body_armor
    if body_armor is None:
        return False

    if body_armor.type == ArmorType.HEAVY:
        return True

    if body_armor.type == ArmorType.MEDIUM:
        armor_name = body_armor.name.lower()
        metal_keywords = ["chain", "scale", "half plate"]
        return any(keyword in armor_name for keyword in metal_keywords)

    return False


class ShockingGrasp(SpellAction):
    """Shocking Grasp - Evocation cantrip

    Lightning springs from your hand to deliver a shock to a creature you try
    to touch. Make a melee spell attack against the target. You have advantage
    on the attack roll if the target is wearing armor made of metal. On a hit,
    the target takes 1d8 lightning damage, and it can't take reactions until
    the start of its next turn.

    Damage scales: 2d8 at 5th, 3d8 at 11th, 4d8 at 17th.
    """
    @property
    def performs_attack(self) -> bool:
        return True

    name: str = Field(default="Shocking Grasp", description="Display name for the shocking grasp spell.")
    description: str = Field(default="Melee spell attack, 1d8 lightning, advantage vs metal armor, no reactions", description="Rules-facing summary for the shocking grasp spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast shocking grasp; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify shocking grasp.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for shocking grasp.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Range contract used when validating targets for shocking grasp.",
    )
    projectile_type: Optional[str] = Field(default="touch", description="Projectile visualization hint for shocking grasp.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.LIGHTNING, description="Primary damage type for VFX")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range (melee: 5ft) and line of sight."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = self.get_target_distance(target_entity.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of melee range ({distance}ft > {self.effective_range}ft)"
            )

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute melee spell attack with advantage vs metal armor."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        has_metal_armor = _is_wearing_metal_armor(target)
        metal_modifiers = (
            AdvantageModifier(
                name="Shocking Grasp (Metal Armor)",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
            ),
        ) if has_metal_armor else ()
        resolution = self.resolve_spell_attack(
            caster,
            target,
            execution_event.uuid,
            extra_advantage_modifiers=metal_modifiers,
        )
        attack_bonus = resolution.attack_bonus
        target_ac = resolution.target_ac
        dice_roll = resolution.dice_roll
        outcome = resolution.outcome

        metal_text = " (advantage: metal armor)" if has_metal_armor else ""
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            is_threatened=resolution.is_threatened,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}{metal_text}: {outcome.value}"
        )

        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.with_updates(
                status_message=f"{self.name} missed"
            )

        num_dice = self._get_cantrip_dice_count(self.caster_level)
        is_crit = outcome == AttackOutcome.CRIT

        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0
        damage_bonus = caster.get_spell_damage_bonus()
        lightning_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.LIGHTNING
        )

        damage_dice = lightning_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.LIGHTNING,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        no_reactions = NoReactions(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            duration=Duration(
                duration=1,
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
        )
        target.add_condition(no_reactions, parent_event=effect_event)

        return effect_event.with_updates(
            damages=[lightning_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} lightning damage, no reactions until next turn"
        )


class GuidingBoltMarked(BaseCondition):
    """
    Target marked by Guiding Bolt.

    "The next attack roll made against this target before the end of your
    next turn has advantage."

    Duration: Until next attack against target OR end of caster's next turn.
    Uses to_target_static to grant attackers advantage.
    Has an EventHandler to remove after first attack against target.
    """
    name: str = Field(default="Guiding Bolt", description="Display name for the guiding bolt marked condition.")
    description: str = Field(default="Next attack against this creature has advantage", description="Rules-facing summary for the guiding bolt marked condition.")

    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster UUID used for ownership and effect attribution by guiding bolt marked.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity not found")

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        adv_uuid = target.equipment.ac_bonus.to_target_static.add_advantage_modifier(
            AdvantageModifier(
                name="Guiding Bolt",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.source_entity_uuid
            )
        )
        outs.append((target.equipment.ac_bonus.uuid, adv_uuid))

        handler = self._create_remove_on_attack_handler()
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)
        expiry_handler = self._create_caster_turn_expiry_handler()
        target.add_event_handler(expiry_handler)
        handler_uuids.append(expiry_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Guiding Bolt mark to {target.name}"
        )
        return outs, handler_uuids, [], [], effect_event

    def _create_remove_on_attack_handler(self) -> EventHandler:
        """Remove this condition after first attack against target."""

        assert self.target_entity_uuid is not None

        target_uuid = self.target_entity_uuid
        effect_uuid = self.uuid

        def remove_on_attack_processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if event.target_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            guiding_mark = target.active_conditions.get("Guiding Bolt")
            if not guiding_mark or guiding_mark.uuid != effect_uuid:
                return None

            target.remove_condition("Guiding Bolt", parent_event=event)
            return None

        return EventHandler(
            name=f"Guiding Bolt Remove ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=remove_on_attack_processor
        )

    def _create_caster_turn_expiry_handler(self) -> EventHandler:
        """Remove the mark at the end of the caster's next turn."""
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid
        effect_uuid = self.uuid
        caster_turn_ends_remaining = 2

        def expire_on_caster_turn_end(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            nonlocal caster_turn_ends_remaining
            if event.source_entity_uuid != caster_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None
            guiding_mark = target.active_conditions.get("Guiding Bolt")
            if not guiding_mark or guiding_mark.uuid != effect_uuid:
                return None

            caster_turn_ends_remaining -= 1
            if caster_turn_ends_remaining == 0:
                target.remove_condition("Guiding Bolt", parent_event=event)
            return None

        return EventHandler(
            name=f"Guiding Bolt Caster Turn Expiry ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_END,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster_uuid,
                )
            ],
            runs_while_suppressed=True,
            event_processor=expire_on_caster_turn_end,
        )


class GuidingBolt(SpellAction):
    """Guiding Bolt - 1st level Evocation

    A flash of light streaks toward a creature of your choice within range.
    Make a ranged spell attack against the target. On a hit, the target takes
    4d6 radiant damage, and the next attack roll made against this target
    before the end of your next turn has advantage.

    At Higher Levels: +1d6 damage per slot level above 1st.
    """
    @property
    def performs_attack(self) -> bool:
        return True

    name: str = Field(default="Guiding Bolt", description="Display name for the guiding bolt spell.")
    description: str = Field(default="Ranged spell attack, 4d6 radiant, next attack has advantage", description="Rules-facing summary for the guiding bolt spell.")
    spell_level: int = Field(default=1, description="Spell slot level required to cast guiding bolt; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify guiding bolt.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for guiding bolt.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for guiding bolt.",
    )
    projectile_type: Optional[str] = Field(default="bolt", description="Projectile visualization hint for guiding bolt.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Primary damage type for VFX")

    base_damage_dice: int = Field(default=4, description="Base number of damage dice rolled by guiding bolt.")

    def get_damage_dice_count(self) -> int:
        """4d6 base + 1d6 per level above 1st."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Guiding Bolt's upcast actor-baseline attack model."""
        if not isinstance(actor, Entity):
            return None
        return self.spell_attack_outcome_profile(
            actor,
            dice_count=self.get_damage_dice_count(),
            die_size=6,
            damage_type=DamageType.RADIANT,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = self.get_target_distance(target_entity.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
            )

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute ranged spell attack and apply guiding mark on hit."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        resolution = self.resolve_spell_attack(caster, target, execution_event.uuid)
        attack_bonus = resolution.attack_bonus
        target_ac = resolution.target_ac
        dice_roll = resolution.dice_roll
        outcome = resolution.outcome

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            is_threatened=resolution.is_threatened,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )

        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.with_updates(
                status_message=f"{self.name} missed"
            )

        num_dice = self.get_damage_dice_count()
        is_crit = outcome == AttackOutcome.CRIT

        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0
        damage_bonus = caster.get_spell_damage_bonus()
        radiant_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.RADIANT
        )

        damage_dice = radiant_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.RADIANT,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        guiding_mark = GuidingBoltMarked(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            duration=Duration(
                duration=2,
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid
            )
        )
        target.add_condition(guiding_mark, parent_event=effect_event)

        return effect_event.with_updates(
            damages=[radiant_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} radiant damage, next attack has advantage"
        )


class EldritchBlast(SpellAction):
    """Eldritch Blast - Evocation cantrip

    A beam of crackling energy streaks toward a creature within range.
    Make a ranged spell attack. On hit, target takes 1d10 force damage.
    Separate beams scale with caster level: two at 5th, three at 11th, four at 17th.
    """
    @property
    def performs_attack(self) -> bool:
        return True

    name: str = Field(default="Eldritch Blast", description="Display name for the eldritch blast spell.")
    description: str = Field(default="A beam of crackling force energy", description="Rules-facing summary for the eldritch blast spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast eldritch blast; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify eldritch blast.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Independent beam allocation for eldritch blast.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for eldritch blast.",
    )
    projectile_type: Optional[str] = Field(default="beam", description="Projectile visualization hint for eldritch blast.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FORCE, description="Primary damage type for VFX")

    def get_num_projectiles(self) -> int:
        """Each beam gets its own attack; an explicit action override still applies."""
        return self.alt_target_count if self.alt_target_count is not None else self._get_cantrip_dice_count(self.caster_level)

    def get_allocation_completion(self) -> Literal["selected_only", "fill_primary"]:
        return "fill_primary"

    def get_multi_target_count(self) -> Optional[int]:
        return self.get_num_projectiles()

    def get_all_targets(self) -> List[UUID]:
        targets = super().get_all_targets()
        count = self.get_num_projectiles() if self.effective_target_type is TargetType.MULTI_ENTITY else 1
        if self.target_entity_uuid is not None:
            targets.extend([self.target_entity_uuid] * max(0, count - len(targets)))
        return targets[:count]

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return independent per-beam attacks and one d10 per hit."""
        if not isinstance(actor, Entity):
            return None
        return self.spell_attack_outcome_profile(
            actor,
            dice_count=1,
            applications=self.get_num_projectiles(),
            die_size=10,
            damage_type=DamageType.FORCE,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and LOS for all targets."""

        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return declaration_event.cancel(status_message="Source entity not found")

        all_targets = self.get_all_targets()
        validated_targets = set()

        for target_uuid in all_targets:
            if target_uuid in validated_targets:
                continue
            validated_targets.add(target_uuid)

            target_entity = Entity.get(target_uuid)
            if not target_entity:
                return declaration_event.cancel(status_message="Target entity not found")

            contact = source_entity.senses.entities.get(target_uuid)
            if contact is None or not contact.visual:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} not in line of sight"
                )

            distance = self.get_target_distance(target_entity.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} out of range ({distance}ft > {self.effective_range}ft)"
                )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute the spell attack."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        resolution = self.resolve_spell_attack(caster, target, execution_event.uuid)
        attack_bonus = resolution.attack_bonus
        target_ac = resolution.target_ac
        dice_roll = resolution.dice_roll
        outcome = resolution.outcome

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            is_threatened=resolution.is_threatened,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )

        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.with_updates(
                status_message=f"{self.name} missed"
            )

        is_crit = outcome == AttackOutcome.CRIT

        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0
        damage_bonus = caster.get_spell_damage_bonus()
        force_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=10,
            dice_numbers=1,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FORCE
        )

        damage_dice = force_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.FORCE,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        return effect_event.with_updates(
            damages=[force_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} force damage"
        )

from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
)


GUST_OF_WIND_ZONE_CONTENT_REF = ContentRef(
    pack_id="content.srd_5_1_cc",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.spell.gust_of_wind",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)


class GustOfWindZone(AreaCondition):
    """Zone for Gust of Wind - 60ft line of wind that pushes creatures."""
    name: str = Field(default="Gust of Wind Zone", description="Display name for the gust of wind zone zone condition.")
    description: str = Field(default="Strong wind pushes creatures and costs extra movement", description="Rules-facing summary for the gust of wind zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the gust of wind zone for cleanup and filtering.")

    content_ref: ContentRef = Field(default=GUST_OF_WIND_ZONE_CONTENT_REF)
    position: Tuple[int, int]
    anchor_kind: SpatialEffectAnchorKind = Field(
        default=SpatialEffectAnchorKind.ENTITY,
    )
    anchor_uuid: UUID = Field(default=PydanticUndefined, validate_default=True)
    layer: SpatialEffectLayer = Field(default=SpatialEffectLayer.FIELD)
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.OVERLAPPING,
    )
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
    )
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = Field(
        default_factory=lambda: frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
    )
    zone_shape: str = Field(default="line", description="Domain value for zone_shape on gust of wind zone.")
    zone_radius_feet: int = Field(default=60, description="Zone radius in feet used by gust of wind zone.")
    zone_width_feet: int = Field(default=10)
    adds_difficult_terrain: bool = Field(default=True, description="Whether gust of wind zone makes affected tiles difficult terrain.")

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.NON_SOURCE)
    spell_dc: int = Field(default=10, description="Spell save DC used by gust of wind zone saving throws.")
    _pushes_in_flight: Set[UUID] = PrivateAttr(default_factory=set)

    def get_spatial_observation(
        self, positions: Set[Tuple[int, int]], *, observer_uuid: UUID,
        discovered: bool = False,
    ) -> Optional[PerceivedSpatialEffect]:
        """Retain observed wind cells and its origin only when established."""
        if not discovered and not self.is_hazard_perceived_by(observer_uuid):
            return None
        observer = Entity.get(observer_uuid)
        previous = observer.senses.spatial_effects.get(self.uuid) if observer is not None else None
        origin_known = (self.position in positions or
                        (previous is not None and previous.anchor_position == self.position))
        geometry = (LinePresentationGeometry(
            origin=self.position, direction=self.zone_direction,
            length_feet=self.zone_radius_feet, width_feet=self.zone_width_feet,
        ) if origin_known and self.zone_direction is not None else None)
        return PerceivedSpatialEffect(
            content_ref=self.content_ref, name=self.name, description=self.description,
            positions=tuple(sorted(positions)),
            anchor_position=self.position if origin_known else None, area_geometry=geometry,
        )

    def _compute_affected_positions(self) -> Set[Tuple[int, int]]:
        """Compute line from caster in the chosen direction."""
        if not self.zone_direction:
            return {self.position}
        dx, dy = self.zone_direction
        length_tiles = self.zone_radius_feet // 5
        target = (self.position[0] + dx * length_tiles,
                  self.position[1] + dy * length_tiles)

        line = Line(
            source_entity_uuid=self.source_entity_uuid,
            target=target,
            length_feet=self.zone_radius_feet,
            width_feet=self.zone_width_feet
        )
        line.compute_objective(caster_pos=self.position)
        return set(line.affected_positions)

    def _create_zone_entry_handler(self) -> EventHandler:
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        zone = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            entity = Entity.get(event.entity_uuid)
            if not entity or not entity.has_hp:
                return None

            if entity.uuid in self._pushes_in_flight:
                return None
            self._pushes_in_flight.add(entity.uuid)
            try:
                _apply_gust_push(entity, dc, zone.position, source_uuid, event)
            finally:
                self._pushes_in_flight.discard(entity.uuid)
            return None

        return EventHandler(
            name="Gust of Wind Entry Push",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            entity = Entity.get(event.source_entity_uuid)
            if not entity or not entity.has_hp:
                return None
            if entity.position not in zone_condition.affected_positions:
                return None

            if entity.uuid in zone_condition._pushes_in_flight:
                return None
            zone_condition._pushes_in_flight.add(entity.uuid)
            try:
                _apply_gust_push(
                    entity,
                    dc,
                    zone_condition.position,
                    source_uuid,
                    event,
                )
            finally:
                zone_condition._pushes_in_flight.discard(entity.uuid)
            return None

        return EventHandler(
            name="Gust of Wind Turn Start Push",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _emit_wind_exposure(self, parent_event: Optional[Event] = None) -> None:
        """Publish strong typed dispersal over the current Gust line."""
        if not self.affected_positions:
            return
        interaction = EventQueue.publish_declaration(SpatialEffectInteractionEvent(
            source_entity_uuid=self.source_entity_uuid,
            operation=SpatialEffectInteractionOperation.DISPERSE,
            positions=tuple(sorted(self.affected_positions)),
            intensity=SpatialEffectInteractionIntensity.STRONG,
            parent_event=parent_event.uuid if parent_event is not None else None,
            phase=EventPhase.DECLARATION,
            use_register=False,
        ))
        interaction = interaction.phase_to(EventPhase.EXECUTION)
        if interaction.canceled:
            return
        interaction = interaction.phase_to(EventPhase.EFFECT)
        if interaction.canceled:
            return
        interaction.phase_to(EventPhase.COMPLETION)

    def _create_wind_exposure_turn_handler(self) -> EventHandler:
        """Create a caster-turn handler that re-emits the persistent wind."""
        source_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            if event.source_entity_uuid != source_uuid:
                return None
            zone_condition._emit_wind_exposure(event)
            return None

        return EventHandler(
            name="Gust of Wind Exposure",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=source_uuid,
            )],
            event_processor=processor,
        )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Event]:
        """Apply Gust zone state and emit its strong-wind exposure."""
        terrain_modifiers, handler_uuids, sub_condition_uuids, spatial_handler_uuids, effect_event = super()._apply(declaration_event)

        wind_handler = self._create_wind_exposure_turn_handler()
        EventQueue.add_event_handler(wind_handler)
        handler_uuids.append(wind_handler.uuid)
        self._emit_wind_exposure(effect_event)

        return terrain_modifiers, handler_uuids, sub_condition_uuids, spatial_handler_uuids, effect_event


def _apply_gust_push(entity: Entity, dc: int, caster_pos: Tuple[int, int],
                      source_uuid: UUID, parent_event: Event) -> None:
    """STR save or pushed 15ft away from caster."""
    if entity.uuid == source_uuid:
        return
    save_request = entity.create_saving_throw_request(
        target_entity_uuid=entity.uuid,
        ability_name="strength",
        dc=dc,
        parent_event=parent_event.uuid
    )
    _, _, success = entity.saving_throw(save_request)
    if success:
        return

    entity_pos = entity.position
    dx = entity_pos[0] - caster_pos[0]
    dy = entity_pos[1] - caster_pos[1]
    length = max(abs(dx), abs(dy), 1)
    push_dx = round(dx / length) if dx != 0 else 0
    push_dy = round(dy / length) if dy != 0 else 0
    if push_dx == 0 and push_dy == 0:
        push_dx = 1

    current_pos, push_dist, blocked, blocked_by = Shove.calculate_final_position(
        entity_pos, (push_dx, push_dy), 15, entity.uuid)

    if current_pos != entity_pos:
        forced_event = ForcedMovementEvent(
            source_entity_uuid=source_uuid,
            target_entity_uuid=entity.uuid,
            source_entity_name="Gust of Wind",
            target_entity_name=entity.name,
            start_position=entity_pos,
            end_position=current_pos,
            direction=(push_dx, push_dy),
            intended_distance=15,
            actual_distance=push_dist,
            blocked_by_obstacle=blocked,
            blocked_by=blocked_by,
            cause="gust_of_wind",
            phase=EventPhase.DECLARATION,
            parent_event=parent_event.uuid,
            use_register=False,
        )
        forced_event = EventQueue.publish_declaration(forced_event)
        if not forced_event.canceled:
            forced_event = forced_event.phase_to(EventPhase.EXECUTION)
        if not forced_event.canceled:
            forced_event = forced_event.phase_to(EventPhase.EFFECT)
        if not forced_event.canceled:
            commit_forced_movement(entity, forced_event, parent_event=parent_event)


class GustOfWind(SpellAction):
    """Gust of Wind - 2nd level Evocation (Concentration)

    A line of strong wind 60ft long and 10ft wide blasts from you.
    STR save or pushed 15ft away. Difficult terrain toward caster.
    """
    harmful: Optional[bool] = Field(default=True, description="This spell imposes a harmful effect on its recipients.")
    name: str = Field(default="Gust of Wind", description="Display name for the gust of wind spell.")
    description: str = Field(default="60ft line of wind, STR save or pushed 15ft, difficult terrain", description="Rules-facing summary for the gust of wind spell.")
    spell_level: int = Field(default=2, description="Spell slot level required to cast gust of wind; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify gust of wind.")
    concentration: bool = Field(default=True, description="Whether gust of wind creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for gust of wind.")
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by gust of wind to compute affected targets.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Range contract used when validating targets for gust of wind.")

    include_self: bool = Field(default=False, description="Whether gust of wind can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for gust of wind.")

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        if self.effective_target_type is TargetType.POSITION_AOE:
            return self._resolve_area_targets()
        return super()._resolve_execution_targets()

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Line(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                length_feet=60,
                width_feet=10
            )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Per-target apply: push each creature in the line."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="strength", save_dc=dc,
            status_message=f"Gust of Wind hits {target.name}"
        )

        _apply_gust_push(target, dc, caster.position, caster.uuid, effect_event)

        return effect_event.with_updates(
            status_message=f"Gust of Wind pushes {target.name}"
        )

    def _finalize_aoe(self, effect_event: SpellEvent) -> None:
        """Create persistent zone after convolution completes."""
        self._setup_zone(effect_event)

    def _setup_zone(self, parent_event: SpellEvent) -> None:
        """Set up the persistent zone condition after initial push."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        target_pos = self.end_position or (caster.position[0] + 1, caster.position[1])

        dx = target_pos[0] - caster.position[0]
        dy = target_pos[1] - caster.position[1]
        direction = (dx, dy)

        zone = GustOfWindZone(
            source_entity_uuid=caster.uuid,
            position=caster.position,
            anchor_uuid=caster.uuid,
            faction=caster.faction,
            zone_direction=direction,
            spell_dc=dc,
            effect_origin=parent_event.to_effect_origin(),
        )
        zone_result = zone.activate(parent_event=parent_event)
        if zone_result is None or zone_result.canceled or not zone.applied:
            return

        concentration = self.ensure_concentration(parent_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)


ICE_STORM_TERRAIN_CONTENT_REF = ContentRef(
    pack_id="content.srd_5_1_cc",
    definition_kind=ContentDefinitionKind.CONDITION,
    content_id="spatial_effect.spell.ice_storm",
    content_version=1,
    definition_contract_hash=(
        "a74aa0ee0fa241101b5c7d3b2551d638"
        "6e4817a8ae5ad5e5cadbc4a15d5fdeb0"
    ),
)


class IceStormTerrain(AreaCondition):
    """Difficult terrain ending at the end of the caster's next turn."""
    name: str = Field(default="Ice Storm Terrain", description="Display name for the ice storm terrain zone condition.")
    description: str = Field(default="Ground covered in ice - difficult terrain", description="Rules-facing summary for the ice storm terrain zone condition.")

    content_ref: ContentRef = Field(default=ICE_STORM_TERRAIN_CONTENT_REF)
    has_visible_presence: bool = True
    position: Tuple[int, int]
    layer: SpatialEffectLayer = Field(default=SpatialEffectLayer.GROUND_SURFACE)
    occupancy_policy: SpatialEffectOccupancyPolicy = Field(
        default=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
    )
    zone_shape: str = Field(default="sphere", description="Domain value for zone_shape on ice storm terrain.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by ice storm terrain.")
    adds_difficult_terrain: bool = Field(default=True, description="Whether ice storm terrain makes affected tiles difficult terrain.")

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for ice storm terrain hazards.")

    def _apply(self, declaration_event: Event):
        modifiers, handlers, children, spatial_handlers, effect = super()._apply(declaration_event)
        if effect is None or effect.canceled:
            return modifiers, handlers, children, spatial_handlers, effect

        def expire(event: Event) -> None:
            self.deactivate(parent_event=event)

        handler = _source_turn_expiry_handler(self, declaration_event, at_end=True, expire=expire)
        EventQueue.add_event_handler(handler)
        handlers.append(handler.uuid)
        return modifiers, handlers, children, spatial_handlers, effect


class IceStorm(SpellAction):
    """Ice Storm - 4th level Evocation

    Hail pounds a 20ft-radius, 40ft-high cylinder. DEX save or
    2d8 bludgeoning + 4d6 cold (half on save). Difficult terrain lasts through the caster's next turn.

    At Higher Levels: +1d8 bludgeoning per level above 4th.
    """
    name: str = Field(default="Ice Storm", description="Display name for the ice storm spell.")
    description: str = Field(default="20ft cylinder: 2d8 bludgeoning + 4d6 cold (DEX half); difficult terrain through the caster's next turn", description="Rules-facing summary for the ice storm spell.")
    spell_level: int = Field(default=4, description="Spell slot level required to cast ice storm; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify ice storm.")
    concentration: bool = Field(default=False, description="Whether ice storm creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for ice storm.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=300), description="Range contract used when validating targets for ice storm.")
    projectile_type: Optional[str] = Field(default="rain", description="Projectile visualization hint for ice storm.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.BLUDGEONING, description="Primary damage type for VFX")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by ice storm to compute affected targets.")
    include_self: bool = Field(default=True, description="Whether ice storm can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for ice storm.")

    aoe_require_targets: bool = False

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        return self._resolve_area_targets()

    base_bludg_dice: int = Field(default=2, description="Domain value for base_bludg_dice on ice storm.")
    cold_dice: int = Field(default=4, description="Domain value for cold_dice on ice storm.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cylinder(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                radius_feet=20,
                height_feet=40
            )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not self.end_position:
            return declaration_event.cancel(status_message="No target position")

        error = self.target_position_error(self.end_position)
        if error is not None:
            return declaration_event.cancel(status_message=error)
        if not caster.senses.visible.get(self.end_position, False):
            return declaration_event.cancel(status_message="Target position is not visible")
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Per-target: DEX save, bludgeoning + cold damage."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        upcast_bonus = self.get_upcast_bonus()

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity", save_dc=dc,
            save_success=success, save_roll=save_roll,
            target_entity_name=target.name,
            status_message=f"DEX save: {save_roll.total} vs DC {dc}"
        )

        if effect_event.canceled:
            return effect_event
        bludg_count = self.base_bludg_dice + upcast_bonus
        damage_bonus = caster.get_spell_damage_bonus()

        bludg_damage = Damage(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            damage_dice=8, dice_numbers=bludg_count, damage_bonus=damage_bonus,
            damage_type=DamageType.BLUDGEONING
        )
        cold_damage = Damage(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            damage_dice=6, dice_numbers=self.cold_dice,
            damage_bonus=ModifiableValue.create(
                source_entity_uuid=caster.uuid, base_value=0, value_name="Cold Damage"
            ),
            damage_type=DamageType.COLD
        )
        bludg_roll = bludg_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        cold_roll = cold_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        total = bludg_roll.total + cold_roll.total
        applied_rolls = [bludg_roll, cold_roll]
        if success:
            total = total // 2
            applied_bludgeoning = bludg_roll.total // 2
            applied_rolls = [
                bludg_roll.model_copy(update={"total": applied_bludgeoning}),
                cold_roll.model_copy(
                    update={"total": total - applied_bludgeoning}
                ),
            ]

        target.receive_damage(
            amount=total,
            damage_type=DamageType.BLUDGEONING,
            source_entity_uuid=caster.uuid,
            damage_rolls=applied_rolls,
            damages=[bludg_damage, cold_damage],
            parent_event=effect_event.uuid,
            effect_origin=execution_event.to_effect_origin(),
        )

        return effect_event.with_updates(
            damages=[bludg_damage, cold_damage],
            damage_rolls=[bludg_roll, cold_roll],
            total_damage=total,
            status_message=f"Ice Storm deals {total} damage to {target.name}"
        )

    def _finalize_aoe(self, effect_event: SpellEvent) -> None:
        """Apply difficult terrain zone after convolution completes."""
        self._setup_terrain(effect_event)

    def _setup_terrain(self, effect_event: SpellEvent) -> None:
        """Own the resolved footprint until the caster's next turn ends."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return

        target_pos = self.end_position
        if not target_pos:
            return

        terrain = IceStormTerrain(
            source_entity_uuid=caster.uuid,
            position=target_pos,
            effect_origin=effect_event.to_effect_origin(),
            affected_positions=set(effect_event.resolved_area_positions or ()),
        )
        terrain.activate(parent_event=effect_event)


class SunbeamBlindedEffect(BaseCondition):
    """One failed beam's shared blindness, ending on its source's next turn."""
    name: str = "Sunbeam Blindness"
    description: str = "Blinded until the start of the caster's next turn."
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, declaration_event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None or not _share_solar_blindness(self, target, declaration_event):
            return [], [], [], [], declaration_event.cancel(status_message="Blinded was not admitted")

        def expire(event: Event) -> None:
            target.remove_condition_by_uuid(self.uuid, parent_event=event)

        handler = _source_turn_expiry_handler(self, declaration_event, at_end=False, expire=expire)
        target.add_event_handler(handler)
        return [], [handler.uuid], [], [], declaration_event.phase_to(EventPhase.EFFECT)


class SunbeamEffect(ConcentrationActionMarker):
    """The concentration-owned hand light and exact repeat-action grant."""
    name: str = "Sunbeam"
    description: str = "Sunlight in the hand; create another beam as an action."
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=10))
    light_source_uuid: UUID | None = None
    _removed_light: SpatialChangeEvent | None = PrivateAttr(default=None)

    def _apply(self, declaration_event: Event):
        caster = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if caster is None:
            return [], [], [], [], declaration_event.cancel(status_message="Caster missing")
        result = super()._apply(declaration_event)
        effect = result[4]
        if effect is not None and not effect.canceled:
            self.light_source_uuid = get_map().add_light_source(caster.position,
                bright_radius_feet=30, dim_radius_feet=30, sunlight=True,
                anchor_uuid=caster.uuid, parent_event=effect.uuid,
                contribution_owner_uuid=self.uuid)
        return result

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        if self.light_source_uuid is not None:
            self._removed_light = get_map().remove_light_source(self.light_source_uuid,
                parent_event=parent_event.uuid if parent_event else None, publish_event=not self.applied)
            self.light_source_uuid = None
        super()._release_owned_runtime_state(parent_event=parent_event)

    def on_membership_changed(self, event: Event) -> None:
        removed, self._removed_light = self._removed_light, None
        if removed is not None:
            get_map()._fire_committed_spatial_event(removed)


def _sunbeam_direction_error(spell: SpellAction) -> str | None:
    caster = Entity.get(spell.source_entity_uuid)
    if caster is None or spell.end_position is None:
        return "Caster or beam direction missing"
    if spell.end_position == caster.position or spell.get_target_distance(spell.end_position) > 60:
        return "Choose a beam direction within 60ft"
    return None


def _apply_sunbeam(spell: SpellAction, event: SpellEvent, *, dc: int,
                   origin: EffectOrigin | None) -> SpellEvent:
    caster = Entity.get(spell.source_entity_uuid)
    target = Entity.get(spell.target_entity_uuid) if spell.target_entity_uuid else None
    if caster is None or target is None:
        return event.cancel(status_message="Caster or target missing")
    modifier_uuid = None
    save_bonus = target.saving_throws.get_saving_throw("constitution").bonus.self_static
    if target.creature_type in (CreatureType.UNDEAD, CreatureType.OOZE):
        modifier_uuid = save_bonus.add_advantage_modifier(AdvantageModifier(
            name="Sunbeam (Undead/Ooze)", value=AdvantageStatus.DISADVANTAGE,
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    try:
        effect, _, success = spell.resolve_saving_throw(event,
            caster=caster, target=target, ability_name="constitution", dc=dc)
    finally:
        if modifier_uuid is not None:
            save_bonus.remove_modifier(modifier_uuid)
    if effect.canceled:
        return effect
    damage = Damage(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        damage_dice=8, dice_numbers=6, damage_bonus=caster.get_spell_damage_bonus(),
        damage_type=DamageType.RADIANT)
    roll = damage.get_dice(AttackOutcome.HIT).roll
    amount = roll.total // 2 if success else roll.total
    target.receive_damage(amount, DamageType.RADIANT, caster.uuid,
        damage_rolls=[roll], damages=[damage], parent_event=effect.uuid, effect_origin=origin)
    if not success and target.health.life_state is not LifeState.DEAD:
        target.add_condition(SunbeamBlindedEffect(source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid, effect_origin=origin), parent_event=effect)
    return effect.with_updates(damages=[damage], damage_rolls=[roll], total_damage=amount)


@srd_action_identity(
    content_id="action.spell.sunbeam.strike",
    display_name="Sunbeam Strike",
    description="Fire another beam from an active Sunbeam spell.",
    parent_spell_name="Sunbeam",
    source_page=184,
    sort_order=930,
)
class SunbeamStrike(SpellAction):
    """One ordinary paid activation of an exact retained Sunbeam owner."""
    name: str = "Sunbeam Strike"
    description: str = "60 by 5ft beam, 6d8 radiant and blindness; CON half."
    action_category: ActionCategory = ActionCategory.ABILITY
    spell_level: int = 6
    spell_school: str = "evocation"
    alt_skip_slot: bool = True
    verbal: bool = False
    target_type: TargetType = TargetType.POSITION_AOE
    aoe_require_targets: bool = False
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    spell_damage_type: Optional[DamageType] = DamageType.RADIANT
    projectile_type: Optional[str] = "beam"
    include_self: bool = False
    valid_target_filter: str = "all"
    spell_dc: int = 10
    grant_condition_uuid: UUID
    effect_origin: EffectOrigin | None = None

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Line(source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0), length_feet=60, width_feet=5)

    def _create_declaration_event(self, parent_event: Event | None = None,
                                  use_register: bool = True) -> Optional[Event]:
        event = super()._create_declaration_event(parent_event, use_register)
        if isinstance(event, SpellEvent):
            return event.with_updates(retained_effect_origin=self.effect_origin)
        return event

    def validate_source_requirements_for_discovery(self) -> bool:
        caster = Entity.get(self.source_entity_uuid)
        owner = caster.active_conditions_by_uuid.get(self.grant_condition_uuid) if caster else None
        return owner is not None and owner.applied and owner.contributions_active()

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        return self._resolve_area_targets()

    def _validate(self, event: SpellEvent) -> Optional[ActionEvent]:
        if not self.validate_source_requirements_for_discovery():
            return event.cancel(status_message="Sunbeam concentration has ended")
        error = _sunbeam_direction_error(self)
        return event.cancel(status_message=error) if error else super()._validate(event)

    def _apply(self, event: SpellEvent) -> SpellEvent:
        if not self.validate_source_requirements_for_discovery():
            return event.cancel(status_message="Sunbeam concentration has ended")
        return _apply_sunbeam(self, event, dc=self.spell_dc, origin=self.effect_origin)


class Sunbeam(SpellAction):
    """One initial beam plus a one-minute, concentration-owned light and repeat."""
    name: str = "Sunbeam"
    description: str = "60 by 5ft beam, 6d8 radiant and blindness; CON half; repeat as an action."
    spell_level: int = 6
    spell_school: str = "evocation"
    concentration: bool = True
    spell_damage_type: Optional[DamageType] = DamageType.RADIANT
    projectile_type: Optional[str] = "beam"
    target_type: TargetType = TargetType.POSITION_AOE
    aoe_require_targets: bool = False
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    include_self: bool = False
    valid_target_filter: str = "all"
    spell_dc: int | None = None
    effect_origin: EffectOrigin | None = None

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Line(source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0), length_feet=60, width_feet=5)

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        return self._resolve_area_targets()

    def _validate(self, event: SpellEvent) -> Optional[ActionEvent]:
        error = _sunbeam_direction_error(self)
        return event.cancel(status_message=error) if error else super()._validate(event)

    def _apply_target_applications(self, execution_event: ActionEvent, effect_event: ActionEvent,
                                  target_uuids: List[UUID]) -> ActionEvent:
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return effect_event.cancel(status_message="Caster missing")
        self.spell_dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        marker = SunbeamEffect(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
            action_name="Sunbeam Strike")
        strike = SunbeamStrike(source_entity_uuid=caster.uuid, template=True,
            grant_condition_uuid=marker.uuid, spell_dc=self.spell_dc,
            cast_at_level=self.cast_at_level, spellcasting_source_id=self.spellcasting_source_id)
        marker.action_uuid = strike.uuid
        admitted = self.apply_owned_condition(type_cast(SpellEvent, effect_event), marker)
        if admitted.canceled or not marker.applied:
            strike.remove_from_register()
            return admitted
        self.effect_origin = marker.effect_origin
        strike.effect_origin = marker.effect_origin
        caster.register_action(strike)
        return super()._apply_target_applications(execution_event, admitted, target_uuids)

    def _apply(self, event: SpellEvent) -> SpellEvent:
        if self.spell_dc is None:
            return event.cancel(status_message="Sunbeam was not admitted")
        return _apply_sunbeam(self, event, dc=self.spell_dc, origin=self.effect_origin)


class ChainLightning(SpellAction):
    """One paid bolt and independently selected branches from its primary contact."""
    name: str = "Chain Lightning"
    description: str = "10d8 lightning to a primary and up to three selected nearby recipients (DEX half)"
    spell_level: int = 6
    spell_school: str = "evocation"
    target_type: TargetType = TargetType.MULTI_ENTITY
    multi_target_objects: bool = True
    allow_same_target: bool = False
    include_self: bool = True
    valid_target_filter: str = "all"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150))
    projectile_type: Optional[str] = "bolt"
    spell_damage_type: Optional[DamageType] = DamageType.LIGHTNING
    _primary_endpoint: EffectEndpoint | None = PrivateAttr(default=None)
    _source_endpoint: EffectEndpoint | None = PrivateAttr(default=None)

    def get_multi_target_count(self) -> Optional[int]:
        return 4 + self.get_upcast_bonus()

    def _contact(self, identity: UUID, origin: Tuple[int, int], distance: int) -> EffectEndpoint | None:
        caster = Entity.get(self.source_entity_uuid)
        target = BaseBlock.get(identity)
        if caster is None or target is None or not target.is_active:
            return None
        grid = get_map()
        if isinstance(target, BaseItem):
            seen = caster.senses.objects.get(identity)
            if seen is None or not seen.visual or not target.is_targetable or not target.is_breakable():
                return None
            position = grid.attack_object_contact(caster.uuid, identity, range_feet=distance,
                access=PhysicalAccess.PROJECTILE, subjective=True, origin=origin)
            placement = grid.get_object_placement(identity)
            if position is None or placement is None:
                return None
            return EffectEndpoint(kind="object", uuid=identity, position=position,
                                  base_height_steps=placement.base_height_steps)
        seen = caster.senses.entities.get(identity)
        if identity != caster.uuid and (seen is None or not seen.visual):
            return None
        tile, start = grid.get_tile(*target.position), grid.get_tile(*origin)
        if tile is None or start is None or support_distance_feet(origin, start.height * 5,
                target.position, tile.height * 5) > distance:
            return None
        if not grid.can_reach_between(origin, target.position, PhysicalAccess.PROJECTILE, caster.uuid):
            return None
        return EffectEndpoint(kind="creature", uuid=identity, position=target.position,
                              base_height_steps=tile.height)

    def get_secondary_target_options(self, primary_uuid: UUID) -> Optional[List[AvailableTarget]]:
        caster = Entity.get(self.source_entity_uuid)
        origin = self.get_target_origin()
        if caster is None or origin is None:
            return []
        primary = self._contact(primary_uuid, origin, self.effective_range)
        if primary is None:
            return []
        candidates = {caster.uuid, *caster.senses.entities, *caster.senses.objects} - {primary_uuid}
        result = []
        for identity in sorted(candidates, key=str):
            contact = self._contact(identity, primary.position, 30)
            target = BaseBlock.get(identity)
            if contact is not None and target is not None:
                result.append(AvailableTarget(index=len(result), target_uuid=identity,
                    target_kind=contact.kind, target_name=target.name, position=contact.position,
                    distance=support_distance_feet(primary.position, primary.base_height_steps * 5,
                        contact.position, contact.base_height_steps * 5)))
        return result

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        targets = self.get_all_targets()
        if not targets or len(targets) > 4 + self.get_upcast_bonus() or len(set(targets)) != len(targets):
            return declaration_event.cancel(status_message="Choose one primary and distinct secondary targets within the spell limit")
        origin = self.get_target_origin()
        primary = self._contact(targets[0], origin, self.effective_range) if origin is not None else None
        if primary is None:
            return declaration_event.cancel(status_message="Primary target is not visibly reachable within spell range")
        if any(self._contact(identity, primary.position, 30) is None for identity in targets[1:]):
            return declaration_event.cancel(status_message="Every secondary must be visibly reachable within 30 feet of the primary")
        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        targets = self.get_all_targets()
        origin = self.get_target_origin()
        self._primary_endpoint = self._contact(targets[0], origin, self.effective_range) if targets and origin is not None else None
        tile = get_map().get_tile(*origin) if origin is not None else None
        self._source_endpoint = (EffectEndpoint(kind="object" if self.cast_origin == "source_item" else "creature",
            uuid=(self.source_item_uuid or self.source_entity_uuid) if self.cast_origin == "source_item" else self.source_entity_uuid,
            position=origin, base_height_steps=tile.height)
            if tile is not None and origin is not None else None)
        return targets if self._primary_endpoint is not None else [], None

    def get_application_propagation(self, target_uuid: UUID,
                                    membership: ApplicationMembership) -> EffectPropagationLink | None:
        source = self._source_endpoint if membership.index == 0 else self._primary_endpoint
        if source is None:
            return None
        target = self._contact(target_uuid, source.position, self.effective_range if membership.index == 0 else 30)
        return (EffectPropagationLink(source=source, target=target, application_id=membership.application_id)
                if target is not None else None)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        recipient = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        link = execution_event.propagation
        if caster is None or not isinstance(recipient, (Entity, BaseItem)) or link is None:
            return execution_event.cancel(status_message="Lightning contact is no longer admitted")
        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        success = False
        save_roll = None
        if isinstance(recipient, Entity):
            request = caster.create_saving_throw_request(target_entity_uuid=recipient.uuid,
                ability_name="dexterity", dc=dc, parent_event=execution_event.uuid)
            _, save_roll, success = recipient.saving_throw(request)
        effect = execution_event.phase_to(EventPhase.EFFECT, target_kind=link.target.kind,
            target_position=link.target.position, target_base_height_steps=link.target.base_height_steps,
            save_ability="dexterity", save_dc=dc, save_roll=save_roll, save_success=success)
        if effect.canceled or not recipient.is_active:
            return effect
        damage = Damage(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid,
            damage_dice=8, dice_numbers=10, damage_bonus=caster.get_spell_damage_bonus(), damage_type=DamageType.LIGHTNING)
        rolled = damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        amount = rolled.total // 2 if success else rolled.total
        if isinstance(recipient, BaseItem):
            recipient.receive_damage(amount, DamageType.LIGHTNING, caster.uuid,
                parent_event=effect, damages=[damage], damage_rolls=[rolled])
        else:
            recipient.receive_damage(amount, DamageType.LIGHTNING, caster.uuid,
                parent_event=effect.uuid, damages=[damage], damage_rolls=[rolled])
        return effect.with_updates(damages=[damage], damage_rolls=[rolled], total_damage=amount)


class PrismaticRestrained(BaseCondition):
    """Prismatic Spray Indigo effect - Restrained with repeat CON save at turn end."""
    name: str = Field(default="Prismatic Restrained", description="Display name for the prismatic restrained condition.")
    description: str = Field(default="Restrained by prismatic energy, CON save to end", description="Rules-facing summary for the prismatic restrained condition.")
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster UUID used for ownership and effect attribution by prismatic restrained.")
    spell_dc: int = Field(default=10, description="Spell save DC used by prismatic restrained saving throws.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_conditions_uuids: List[UUID] = []

        restrained = Restrained(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(restrained, parent_event=declaration_event)
        sub_conditions_uuids.append(restrained.uuid)

        handler = self._create_repeat_save_handler()
        target.add_event_handler(handler)
        handler_uuids = [handler.uuid]

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is restrained by prismatic energy"
        )

        return [], handler_uuids, sub_conditions_uuids, [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """CON save at end of turn to end Restrained."""
        assert self.target_entity_uuid is not None
        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid or self.source_entity_uuid
        effect_uuid = self.uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None
            target = Entity.get(target_uuid)
            if not target:
                return None
            prismatic = target.active_conditions.get("Prismatic Restrained")
            if not prismatic or prismatic.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Prismatic Restrained", parent_event=event)
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="constitution", dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)
            if success:
                target.remove_condition("Prismatic Restrained", parent_event=event)
            return None

        return EventHandler(
            name=f"Prismatic Restrained: Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target_uuid
            )],
            event_processor=processor
        )


class PrismaticSpray(SpellAction):
    """Prismatic Spray - 7th level Evocation

    Each creature in a 60-foot cone must make a DEX save. For each target,
    roll d8 to determine which color ray affects it. Random color determines
    damage type or condition.

    Duration: Instantaneous
    """
    harmful: Optional[bool] = Field(default=True, description="This spell imposes a harmful effect on its recipients.")
    name: str = Field(default="Prismatic Spray", description="Display name for the prismatic spray spell.")
    description: str = Field(default="60ft cone, random color effect per target", description="Rules-facing summary for the prismatic spray spell.")
    spell_level: int = Field(default=7, description="Spell slot level required to cast prismatic spray; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify prismatic spray.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for prismatic spray.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Range contract used when validating targets for prismatic spray.")
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by prismatic spray to compute affected targets.")
    include_self: bool = Field(default=False, description="Whether prismatic spray can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for prismatic spray.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cone(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                length_feet=60
            )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified")
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply_color_effect(
        self, color: int, target: Entity, caster: Entity,
        dc: int, parent_event: Event
    ) -> None:
        """Apply a single color effect to a target."""

        color_damage: dict[int, DamageType] = {
            1: DamageType.FIRE,
            2: DamageType.ACID,
            3: DamageType.LIGHTNING,
            4: DamageType.POISON,
            5: DamageType.COLD,
        }

        if color in color_damage:
            save_ability = "constitution" if color == 4 else "dexterity"
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name=save_ability, dc=dc,
                parent_event=parent_event.uuid
            )
            _, _, success = target.saving_throw(save_request)
            damage_bonus = caster.get_spell_damage_bonus()
            prismatic_damage = Damage(
                source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
                damage_dice=6, dice_numbers=10, damage_bonus=damage_bonus,
                damage_type=color_damage[color]
            )
            damage_roll = prismatic_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
            final_damage = damage_roll.total // 2 if success else damage_roll.total
            target.receive_damage(final_damage, color_damage[color], caster.uuid, parent_event=parent_event.uuid)

        elif color == 6:

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="constitution", dc=dc,
                parent_event=parent_event.uuid
            )
            _, _, success = target.saving_throw(save_request)
            if not success:
                prismatic_restrained = PrismaticRestrained(
                    source_entity_uuid=caster.uuid,
                    target_entity_uuid=target.uuid,
                    caster_uuid=caster.uuid,
                    spell_dc=dc,
                    tags={ConditionTag.MAGICAL}
                )
                target.add_condition(prismatic_restrained, parent_event=parent_event)

        elif color == 7:

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom", dc=dc,
                parent_event=parent_event.uuid
            )
            _, _, success = target.saving_throw(save_request)
            if not success:
                blinded = Blinded(
                    source_entity_uuid=caster.uuid,
                    target_entity_uuid=target.uuid,
                    tags={ConditionTag.MAGICAL}
                )
                blinded.duration.duration_type = DurationType.ROUNDS
                blinded.duration.duration = 10
                target.add_condition(blinded, parent_event=parent_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_dc=dc,
            status_message=f"Prismatic ray strikes {target.name}"
        )

        color_roll = random.randint(1, 8)
        if color_roll == 8:

            color1 = random.randint(1, 7)
            color2 = random.randint(1, 7)
            while color2 == color1:
                color2 = random.randint(1, 7)
            self._apply_color_effect(color1, target, caster, dc, effect_event)
            self._apply_color_effect(color2, target, caster, dc, effect_event)
            color_text = f"colors {color1} + {color2}"
        else:
            self._apply_color_effect(color_roll, target, caster, dc, effect_event)
            color_text = f"color {color_roll}"

        color_names = {1: "Red", 2: "Orange", 3: "Yellow", 4: "Green", 5: "Blue", 6: "Indigo", 7: "Violet"}
        if color_roll == 8:
            color_desc = f"{color_names.get(color1, '?')} + {color_names.get(color2, '?')}"
        else:
            color_desc = color_names.get(color_roll, "Unknown")

        return effect_event.with_updates(
            status_message=f"Prismatic Spray: {target.name} hit by {color_desc} ({color_text})"
        )


class TrueStrike(SpellAction):
    """True Strike - Evocation cantrip (5.5e version)

    Weapon attack using spellcasting ability instead of STR/DEX.
    Cantrip scaling: +1d6 radiant at levels 5, 11, 17.

    Delegates to a cost-free child Attack with an ability override and
    attack-local radiant damage packets.

    Register two variants per caster: TrueStrike(Melee) and TrueStrike(Ranged)
    using weapon_slot field. Each variant uses the weapon's range for targeting.
    """
    @property
    def performs_attack(self) -> bool:
        return True

    name: str = Field(default="True Strike", description="Display name for the true strike spell.")
    description: str = Field(default="Weapon attack using spellcasting ability, +radiant damage at higher levels", description="Rules-facing summary for the true strike spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast true strike; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify true strike.")
    target_type: TargetType = Field(default=TargetType.CREATURE_OR_OBJECT, description="Targeting mode used by action discovery and validation for true strike.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Range contract used when validating targets for true strike.",
    )

    weapon_slot: WeaponSlot = Field(default=WeaponSlot.MELEE_MAIN, description="Domain value for weapon_slot on true strike.")

    include_self: bool = Field(default=False, description="Whether true strike can include the caster among valid targets.")
    valid_target_filter: str = Field(default="enemies", description="Relationship filter used when collecting valid targets for true strike.")

    def get_attack_source_metadata(self):
        source = Entity.get(self.source_entity_uuid)
        return source.equipment.snapshot_attack_source_metadata(self.weapon_slot) if source else None

    def get_range(self) -> Range:
        source = Entity.get(self.source_entity_uuid)
        weapon_range = source.get_weapon_range(self.weapon_slot) if source else self.spell_range
        if self.alt_range is not None:
            return weapon_range.model_copy(update={"normal": self.alt_range, "long": None})
        return weapon_range

    @property
    def effective_range(self) -> int:
        weapon_range = self.get_range()
        return weapon_range.long or weapon_range.normal

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        source = Entity.get(self.source_entity_uuid)
        return source.get_weapon_physical_access(self.weapon_slot) if source is not None else None

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate: weapon exists in slot, target in LOS."""
        los_event = self.validate_single_recipient(declaration_event)
        if los_event is None or los_event.canceled:
            return los_event

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        weapon = caster.equipment._get_weapon_by_slot(self.weapon_slot)
        if not isinstance(weapon, WeaponItem) or isinstance(weapon, ShieldItem):
            return declaration_event.cancel(status_message="True Strike requires a weapon in the selected slot")

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute True Strike — fires Attack with override_ability + cantrip radiant."""

        caster = Entity.get(self.source_entity_uuid)
        target = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        ability_name: AbilityName = type_cast(AbilityName, caster.spellcasting.spellcasting_ability or "intelligence")

        extra_dice = self._get_cantrip_dice_count(self.caster_level) - 1
        additional = [Damage(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            damage_dice=6, dice_numbers=extra_dice, damage_type=DamageType.RADIANT,
            damage_bonus=ModifiableValue.create(source_entity_uuid=caster.uuid, base_value=0))] if extra_dice > 0 else []
        attack = Attack(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            weapon_slot=self.weapon_slot, override_ability=ability_name,
            additional_damages=additional, costs=[], template=False)
        bind_runtime_action_before_admission(attack, current_binding=attack.behavior_binding,
            runtime_owner_uuid=caster.uuid)
        attack_result = attack.apply(parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{self.name}: {attack_result.status_message}" if attack_result else f"{self.name} failed"
        )


def register_true_strike(entity: Entity, caster_level: int = 1) -> None:
    """Register True Strike variants for each equipped weapon slot.

    Creates one True Strike variant per equipped weapon (melee/ranged).
    """
    for slot, label in [(WeaponSlot.MELEE_MAIN, "Melee"), (WeaponSlot.RANGED_MAIN, "Ranged")]:
        weapon = entity.equipment._get_weapon_by_slot(slot)
        if isinstance(weapon, WeaponItem) and not isinstance(weapon, ShieldItem):
            range_obj = weapon.range
            spell = TrueStrike(
                name=f"True Strike ({label})",
                source_entity_uuid=entity.uuid,
                weapon_slot=slot,
                spell_range=range_obj,
                caster_level=caster_level,
                template=True
            )
            entity.register_action(spell)


class FlameStrike(SpellAction):
    """Flame Strike - 5th level Evocation

    A vertical column of divine fire roars down from the heavens.
    10ft-radius, 40ft-high cylinder, 60ft range.
    4d6 fire + 4d6 radiant damage, DEX save for half.

    At Higher Levels: +1d6 fire per level above 5th.
    """
    name: str = Field(default="Flame Strike", description="Display name for the flame strike spell.")
    description: str = Field(default="10ft cylinder: 4d6 fire + 4d6 radiant (DEX half)", description="Rules-facing summary for the flame strike spell.")
    spell_level: int = Field(default=5, description="Spell slot level required to cast flame strike; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify flame strike.")
    concentration: bool = Field(default=False, description="Whether flame strike creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for flame strike.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60), description="Range contract used when validating targets for flame strike.")
    projectile_type: Optional[str] = Field(default="radiance", description="Projectile visualization hint for flame strike.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by flame strike to compute affected targets.")
    include_self: bool = Field(default=True, description="Whether flame strike can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for flame strike.")

    base_fire_dice: int = Field(default=4, description="Domain value for base_fire_dice on flame strike.")
    radiant_dice: int = Field(default=4, description="Domain value for radiant_dice on flame strike.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cylinder(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                radius_feet=10,
                height_feet=40
            )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not self.end_position:
            return declaration_event.cancel(status_message="No target position")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Per-target: DEX save, fire + radiant damage."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        upcast_bonus = self.get_upcast_bonus()

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity", save_dc=dc,
            save_success=success, save_roll=save_roll,
            target_entity_name=target.name,
            status_message=f"DEX save: {save_roll.total} vs DC {dc}"
        )

        fire_count = self.base_fire_dice + upcast_bonus
        damage_bonus = caster.get_spell_damage_bonus()

        fire_damage = Damage(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            damage_dice=6, dice_numbers=fire_count, damage_bonus=damage_bonus,
            damage_type=DamageType.FIRE
        )
        radiant_damage = Damage(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            damage_dice=6, dice_numbers=self.radiant_dice,
            damage_bonus=ModifiableValue.create(
                source_entity_uuid=caster.uuid, base_value=0, value_name="Radiant Damage"
            ),
            damage_type=DamageType.RADIANT
        )
        fire_roll = fire_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        radiant_roll = radiant_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        total = fire_roll.total + radiant_roll.total
        applied_rolls = [fire_roll, radiant_roll]
        if success:
            total = total // 2
            applied_fire = fire_roll.total // 2
            applied_rolls = [
                fire_roll.model_copy(update={"total": applied_fire}),
                radiant_roll.model_copy(
                    update={"total": total - applied_fire}
                ),
            ]

        target.receive_damage(
            amount=total,
            damage_type=DamageType.FIRE,
            source_entity_uuid=caster.uuid,
            damage_rolls=applied_rolls,
            damages=[fire_damage, radiant_damage],
            parent_event=effect_event.uuid
        )

        return effect_event.with_updates(
            damages=[fire_damage, radiant_damage],
            damage_rolls=[fire_roll, radiant_roll],
            total_damage=total,
            status_message=f"Flame Strike deals {total} damage to {target.name}"
        )


class LightEffect(BaseCondition):
    """Light spell effect — emits bright light in 20ft and dim light in additional 20ft."""
    name: str = Field(default="Light", description="Display name for the light effect condition.")
    description: str = Field(default="Object sheds bright light in a 20-foot radius and dim light for an additional 20 feet", description="Rules-facing summary for the light effect condition.")
    light_source_uuid: Optional[UUID] = Field(default=None, description="Light source UUID created and cleaned up by light effect.")

    _removed_light: SpatialChangeEvent | None = PrivateAttr(default=None)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No target")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        grid = get_map()
        self.light_source_uuid = grid.add_light_source(
            position=target.position,
            bright_radius_feet=20,
            dim_radius_feet=20,
            anchor_uuid=target.uuid,
            contribution_owner_uuid=self.uuid,
            parent_event=declaration_event.uuid,
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Light shines from {target.name}"
        )
        return [], [], [], [], effect_event

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        if self.light_source_uuid is not None:
            self._removed_light = get_map().remove_light_source(self.light_source_uuid,
                parent_event=parent_event.uuid if parent_event else None, publish_event=not self.applied)
            self.light_source_uuid = None
        super()._release_owned_runtime_state(parent_event=parent_event)

    def on_membership_changed(self, event: Event) -> None:
        removed, self._removed_light = self._removed_light, None
        if removed is not None:
            get_map()._fire_committed_spatial_event(removed)


class Light(SpellAction):
    """Light - Evocation Cantrip (Concentration)

    You touch one object. For the duration, the object sheds bright light
    in a 20-foot radius and dim light for an additional 20 feet.

    Duration: Concentration, up to 1 hour (10 rounds in combat).
    """
    name: str = Field(default="Light", description="Display name for the light spell.")
    description: str = Field(default="Touch: object sheds 20ft bright + 20ft dim light (concentration)", description="Rules-facing summary for the light spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast light; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify light.")
    concentration: bool = Field(default=True, description="Whether light creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for light.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Range contract used when validating targets for light.")
    valid_target_filter: str = Field(default="self_or_allies", description="Relationship filter used when collecting valid targets for light.")

    def get_world_effect_profile(self, actor: Any) -> ActionWorldEffectProfile:
        """Declare Light's anchored illumination and possible reveal region.

        Args:
            actor: Entity discovering the spell. Light's world geometry does
                not depend on actor-private state.

        Returns:
            Typed information effects matching the runtime light source.
        """
        return ActionWorldEffectProfile(
            semantic_id="information.light",
            information_effects=(
                InformationEffectProfile(
                    operation=ActionInformationOperation.CHANGE_LIGHT,
                    certainty=ActionWorldEffectCertainty.GUARANTEED,
                    anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
                    scope=ActionWorldEffectScope.REGION,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=40,
                ),
                InformationEffectProfile(
                    operation=ActionInformationOperation.REVEAL_REGION,
                    certainty=ActionWorldEffectCertainty.CONDITIONAL,
                    anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
                    scope=ActionWorldEffectScope.REGION,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=40,
                ),
            ),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        if not target:
            target = caster

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Light on {target.name}"
        )

        light_effect = LightEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        light_effect.duration.duration_type = DurationType.ROUNDS
        light_effect.duration.duration = 10
        target.add_condition(light_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if light_effect.applied:
            concentration.add_linked_condition(target.uuid, light_effect.uuid)

        return effect_event.with_updates(
            status_message=f"Light shines from {target.name}"
        )


class ContinualFlameCondition(BaseCondition):
    """Permanent heatless light owned by the touched item."""

    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    name: str = "Continual Flame"
    description: str = "A permanent heatless flame sheds bright20/dim20 light while exposed."
    semantic_key: Optional[str] = "condition.spell.continual_flame"
    _light_source_uuid: Optional[UUID] = PrivateAttr(default=None)
    _light_anchor_uuid: Optional[UUID] = PrivateAttr(default=None)
    _removed_light: SpatialChangeEvent | None = PrivateAttr(default=None)

    def snapshot_item_effect(self) -> ItemEffectPresentationState:
        return ItemEffectPresentationState(effect_uuid=self.uuid,
            behavior_id=self.get_semantic_key(),
            display_name=self.name, description=self.description,
            applied_source_event_cursor=self.applied_source_event_cursor)

    def _commit_application(self, effect_event: Event) -> None:
        self.on_owner_placement_committed(effect_event)

    def on_owner_placement_committed(self, event: Event) -> None:
        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not isinstance(item, BaseItem):
            return
        grid = get_map()
        placement = grid.get_object_placement(item.uuid)
        anchor_uuid = (item.uuid if placement is not None else
            item.owner_uuid if item.is_equipped else None)
        anchor = BaseBlock.get(anchor_uuid) if anchor_uuid is not None else None
        position = (placement.position if placement is not None else
            anchor.get_position() if anchor is not None else None)
        if item.integrity is ItemIntegrity.DESTROYED:
            anchor_uuid, position = None, None
        if self._light_source_uuid is not None and anchor_uuid != self._light_anchor_uuid:
            grid.remove_light_source(self._light_source_uuid, parent_event=event.uuid)
            self._light_source_uuid = None
        self._light_anchor_uuid = anchor_uuid
        if position is None or anchor_uuid is None:
            return
        if self._light_source_uuid is None:
            self._light_source_uuid = grid.add_light_source(position=position,
                bright_radius_feet=20, dim_radius_feet=20,
                anchor_uuid=anchor_uuid, parent_event=event.uuid, contribution_owner_uuid=self.uuid)
        else:
            grid.move_light_source(self._light_source_uuid, position, parent_event=event.uuid)

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        if self._light_source_uuid is not None:
            self._removed_light = get_map().remove_light_source(self._light_source_uuid,
                parent_event=parent_event.uuid if parent_event else None, publish_event=not self.applied)
            self._light_source_uuid = None
            self._light_anchor_uuid = None
        super()._release_owned_runtime_state(parent_event=parent_event)

    def on_membership_changed(self, event: Event) -> None:
        removed, self._removed_light = self._removed_light, None
        if removed is not None:
            get_map()._fire_committed_spatial_event(removed)


class ContinualFlame(SpellAction):
    """Touch one real item to give it permanent, coverable, heatless light."""

    name: str = "Continual Flame"
    description: str = "Touch: permanent 20ft bright + 20ft dim light on object"
    spell_level: int = 2
    spell_school: str = "evocation"
    concentration: bool = False
    target_type: TargetType = TargetType.OBJECT
    include_owned_item_targets: bool = True
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))

    def physical_access_error(self, *, subjective: bool = False) -> Optional[str]:
        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        caster = Entity.get(self.source_entity_uuid)
        if not isinstance(item, BaseItem) or item.integrity is not ItemIntegrity.INTACT:
            return "Continual Flame requires an intact item"
        if caster is None:
            return "Caster not found"
        if (caster.inventory.items.get(item.uuid) is item
                or any(owned.uuid == item.uuid for owned in caster.equipment.get_all_equipped_items())):
            return None
        return super().physical_access_error(subjective=subjective)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if not isinstance(item, BaseItem):
            return execution_event.cancel(status_message="Target item not found")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        condition = ContinualFlameCondition(source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=item.uuid, effect_origin=execution_event.get_effect_origin())
        result = item.add_condition(condition, parent_event=effect)
        if result is None or result.canceled or not condition.applied:
            return effect.cancel(status_message="Continual Flame could not be installed")
        return effect.with_updates(status_message=f"A permanent heatless flame shines from {item.name}")


def _get_spellcasting_ability_modifier(caster: Entity) -> int:
    """Get the caster's spellcasting ability modifier (e.g. WIS for Cleric)."""
    return caster.ability_scores.get_ability(
        caster.spellcasting.spellcasting_ability
    ).modifier


def _create_healing(
    caster: Entity, num_dice: int, die_value: int, spell_name: str
) -> Healing:
    """Create a Healing spec with the caster's spellcasting ability modifier as bonus."""
    wis_mod = _get_spellcasting_ability_modifier(caster)
    return Healing(
        name=spell_name,
        source_entity_uuid=caster.uuid,
        healing_dice=type_cast(Literal[4, 6, 8, 10, 12, 20], die_value),
        dice_numbers=num_dice,
        healing_bonus=ModifiableValue.create(
            source_entity_uuid=caster.uuid,
            base_value=wis_mod,
            value_name=f"{spell_name} Healing"
        )
    )


class CureWounds(SpellAction):
    """Cure Wounds - 1st level Evocation

    A creature you touch regains hit points equal to 1d8 + your spellcasting
    ability modifier. This spell has no effect on undead or constructs.

    At Higher Levels: +1d8 per slot level above 1st.
    """
    name: str = Field(default="Cure Wounds", description="Display name for the cure wounds spell.")
    description: str = Field(default="Touch a creature to restore 1d8 + modifier HP", description="Rules-facing summary for the cure wounds spell.")
    spell_level: int = Field(default=1, description="Spell slot level required to cast cure wounds; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify cure wounds.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for cure wounds.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Range contract used when validating targets for cure wounds.",
    )
    include_self: bool = Field(default=True, description="Whether cure wounds can include the caster among valid targets.")
    valid_target_filter: str = Field(default="self_or_allies", description="Relationship filter used when collecting valid targets for cure wounds.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid != caster.uuid:
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

        healing = _create_healing(caster, self.cast_at_level, 8, "Cure Wounds")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Cure Wounds heals {target.name}"
        )

        healing_roll = fire_heal_roll_result(caster.uuid, target.uuid, healing, effect_event, "Cure Wounds")
        actual = target.receive_healing(
            healing_roll.total, caster.uuid,
            source_description=f"Cure Wounds: {healing_roll.total}",
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level
        )

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Cure Wounds heals {target.name} for {actual} HP"
        )


class HealingWord(SpellAction):
    """Healing Word - 1st level Evocation

    A creature of your choice that you can see within range regains hit points
    equal to 1d4 + your spellcasting ability modifier.

    Casting Time: Bonus action. Range: 60ft.
    At Higher Levels: +1d4 per slot level above 1st.
    """
    name: str = Field(default="Healing Word", description="Display name for the healing word spell.")
    description: str = Field(default="Bonus action: heal a creature for 1d4 + modifier HP at 60ft", description="Rules-facing summary for the healing word spell.")
    spell_level: int = Field(default=1, description="Spell slot level required to cast healing word; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify healing word.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for healing word.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for healing word.",
    )
    include_self: bool = Field(default=True, description="Whether healing word can include the caster among valid targets.")
    valid_target_filter: str = Field(default="self_or_allies", description="Relationship filter used when collecting valid targets for healing word.")

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Healing Word Cost", cost_type="bonus_actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute healing word.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid != caster.uuid:
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

        healing = _create_healing(caster, self.cast_at_level, 4, "Healing Word")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Healing Word heals {target.name}"
        )

        healing_roll = fire_heal_roll_result(caster.uuid, target.uuid, healing, effect_event, "Healing Word")
        actual = target.receive_healing(
            healing_roll.total, caster.uuid,
            source_description=f"Healing Word: {healing_roll.total}",
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level
        )

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Healing Word heals {target.name} for {actual} HP"
        )


class PrayerOfHealing(SpellAction):
    """Prayer of Healing - 2nd level Evocation

    Up to six creatures of your choice that you can see within range each
    regain hit points equal to 2d8 + your spellcasting ability modifier.

    At Higher Levels: +1d8 per slot level above 2nd.
    """
    name: str = Field(default="Prayer of Healing", description="Display name for the prayer of healing spell.")
    description: str = Field(default="Heal up to 6 allies for 2d8 + modifier HP", description="Rules-facing summary for the prayer of healing spell.")
    spell_level: int = Field(default=2, description="Spell slot level required to cast prayer of healing; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify prayer of healing.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Targeting mode used by action discovery and validation for prayer of healing.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Range contract used when validating targets for prayer of healing.",
    )
    include_self: bool = Field(default=True, description="Whether prayer of healing can include the caster among valid targets.")
    valid_target_filter: str = Field(default="self_or_allies", description="Relationship filter used when collecting valid targets for prayer of healing.")
    allow_same_target: bool = Field(default=False, description="Whether prayer of healing may select the same entity more than once.")

    def get_multi_target_count(self) -> Optional[int]:
        return 6

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        all_targets = self.get_all_targets()
        for target_uuid in set(all_targets):
            target = Entity.get(target_uuid)
            if not target:
                return declaration_event.cancel(status_message="Target not found")
            contact = caster.senses.entities.get(target_uuid)
            if target_uuid != caster.uuid and (contact is None or not contact.visual):
                return declaration_event.cancel(
                    status_message=f"{target.name} not in line of sight"
                )
            distance = self.get_target_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target.name} out of range"
                )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply healing to current target (called once per target by convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        healing = _create_healing(caster, self.cast_at_level, 8, "Prayer of Healing")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Prayer of Healing heals {target.name}"
        )

        healing_roll = fire_heal_roll_result(caster.uuid, target.uuid, healing, effect_event, "Prayer of Healing")
        actual = target.receive_healing(
            healing_roll.total, caster.uuid,
            source_description=f"Prayer of Healing: {healing_roll.total}",
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level
        )

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Prayer of Healing heals {target.name} for {actual} HP"
        )


class MassHealingWord(SpellAction):
    """Mass Healing Word - 3rd level Evocation

    Up to six creatures of your choice that you can see within range
    regain hit points equal to 1d4 + your spellcasting ability modifier.

    Casting Time: Bonus action. Range: 60ft.
    At Higher Levels: +1d4 per slot level above 3rd.
    """
    name: str = Field(default="Mass Healing Word", description="Display name for the mass healing word spell.")
    description: str = Field(default="Bonus action: heal up to 6 allies for 1d4 + modifier HP", description="Rules-facing summary for the mass healing word spell.")
    spell_level: int = Field(default=3, description="Spell slot level required to cast mass healing word; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify mass healing word.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Targeting mode used by action discovery and validation for mass healing word.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for mass healing word.",
    )
    include_self: bool = Field(default=True, description="Whether mass healing word can include the caster among valid targets.")
    valid_target_filter: str = Field(default="self_or_allies", description="Relationship filter used when collecting valid targets for mass healing word.")
    allow_same_target: bool = Field(default=False, description="Whether mass healing word may select the same entity more than once.")

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Mass Healing Word Cost", cost_type="bonus_actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute mass healing word.")

    def get_multi_target_count(self) -> Optional[int]:
        return 6

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        all_targets = self.get_all_targets()
        for target_uuid in set(all_targets):
            target = Entity.get(target_uuid)
            if not target:
                return declaration_event.cancel(status_message="Target not found")
            contact = caster.senses.entities.get(target_uuid)
            if target_uuid != caster.uuid and (contact is None or not contact.visual):
                return declaration_event.cancel(
                    status_message=f"{target.name} not in line of sight"
                )
            distance = self.get_target_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target.name} out of range"
                )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply healing to current target (called once per target by convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        num_dice = 1 + max(0, self.cast_at_level - 3)
        healing = _create_healing(caster, num_dice, 4, "Mass Healing Word")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Mass Healing Word heals {target.name}"
        )

        healing_roll = fire_heal_roll_result(caster.uuid, target.uuid, healing, effect_event, "Mass Healing Word")
        actual = target.receive_healing(
            healing_roll.total, caster.uuid,
            source_description=f"Mass Healing Word: {healing_roll.total}",
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level
        )

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Mass Healing Word heals {target.name} for {actual} HP"
        )


class MassCureWounds(SpellAction):
    """Mass Cure Wounds - 5th level Evocation

    A wave of healing energy washes out from a point of your choice within range.
    Choose up to six creatures in a 30-foot-radius sphere centered on that point.
    Each target regains hit points equal to 3d8 + your spellcasting ability modifier.

    At Higher Levels: +1d8 per slot level above 5th.
    """
    name: str = Field(default="Mass Cure Wounds", description="Display name for the mass cure wounds spell.")
    description: str = Field(default="AoE heal up to 6 allies in 30ft sphere for 3d8 + modifier HP", description="Rules-facing summary for the mass cure wounds spell.")
    spell_level: int = Field(default=5, description="Spell slot level required to cast mass cure wounds; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify mass cure wounds.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for mass cure wounds.")
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by mass cure wounds to compute affected targets.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for mass cure wounds.",
    )
    include_self: bool = Field(default=True, description="Whether mass cure wounds can include the caster among valid targets.")
    valid_target_filter: str = Field(default="self_or_allies", description="Relationship filter used when collecting valid targets for mass cure wounds.")

    max_targets: int = Field(default=6, description="Maximum number of targets mass cure wounds can affect.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                radius_feet=30
            )

    def get_all_targets(self) -> List[UUID]:
        """Override to cap at 6 targets from AoE."""
        targets = super().get_all_targets()
        return targets[:self.max_targets]

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position")

        distance = self.get_target_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Position out of range ({distance}ft > {self.effective_range}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply healing to current target (called once per target by convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        num_dice = self.cast_at_level - 2
        healing = _create_healing(caster, num_dice, 8, "Mass Cure Wounds")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Mass Cure Wounds heals {target.name}"
        )

        healing_roll = fire_heal_roll_result(caster.uuid, target.uuid, healing, effect_event, "Mass Cure Wounds")
        actual = target.receive_healing(
            healing_roll.total, caster.uuid,
            source_description=f"Mass Cure Wounds: {healing_roll.total}",
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level
        )

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Mass Cure Wounds heals {target.name} for {actual} HP"
        )


class HealSpell(SpellAction):
    """Heal - 6th level Evocation

    Choose a creature that you can see within range. A surge of positive energy
    washes through the creature, causing it to regain 70 hit points. This spell
    also ends blindness and deafness on the target.

    At Higher Levels: +10 HP per slot level above 6th.
    """
    name: str = Field(default="Heal", description="Display name for the heal spell spell.")
    description: str = Field(default="Restore 70 HP and remove blindness/deafness", description="Rules-facing summary for the heal spell spell.")
    spell_level: int = Field(default=6, description="Spell slot level required to cast heal spell; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify heal spell.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for heal spell.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for heal spell.",
    )
    include_self: bool = Field(default=True, description="Whether heal spell can include the caster among valid targets.")
    valid_target_filter: str = Field(default="self_or_allies", description="Relationship filter used when collecting valid targets for heal spell.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid != caster.uuid:
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

        heal_amount = 70 + 10 * self.get_upcast_bonus()
        source_desc = f"Heal: {heal_amount} HP"

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Heal restores {target.name}"
        )

        actual = target.receive_healing(
            heal_amount, caster.uuid,
            source_description=source_desc,
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level
        )

        if "Blinded" in target.active_conditions:
            target.remove_condition("Blinded", parent_event=effect_event)
        if "Deafened" in target.active_conditions:
            target.remove_condition("Deafened", parent_event=effect_event)

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Heal restores {target.name} for {actual} HP"
        )


class MassHeal(SpellAction):
    """Mass Heal - 9th level Evocation

    A flood of healing energy flows from you into injured creatures around you.
    You restore up to 700 hit points, divided as you choose among any number
    of creatures that you can see within range. Creatures healed are also
    cured of blindness and deafness.
    """
    name: str = Field(default="Mass Heal", description="Display name for the mass heal spell.")
    description: str = Field(default="Distribute 700 HP of healing among visible allies, remove blindness/deafness", description="Rules-facing summary for the mass heal spell.")
    spell_level: int = Field(default=9, description="Spell slot level required to cast mass heal; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify mass heal.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Targeting mode used by action discovery and validation for mass heal.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for mass heal.",
    )
    include_self: bool = Field(default=True, description="Whether mass heal can include the caster among valid targets.")
    valid_target_filter: str = Field(default="self_or_allies", description="Relationship filter used when collecting valid targets for mass heal.")
    allow_same_target: bool = Field(default=False, description="Whether mass heal may select the same entity more than once.")

    healing_pool_remaining: int = Field(default=700, description="Healing pool remaining for mass heal.")

    def get_multi_target_count(self) -> Optional[int]:
        return 20

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        all_targets = self.get_all_targets()
        for target_uuid in set(all_targets):
            target = Entity.get(target_uuid)
            if not target:
                return declaration_event.cancel(status_message="Target not found")
            contact = caster.senses.entities.get(target_uuid)
            if target_uuid != caster.uuid and (contact is None or not contact.visual):
                return declaration_event.cancel(
                    status_message=f"{target.name} not in line of sight"
                )
            distance = self.get_target_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target.name} out of range"
                )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply healing from pool to current target (called per target by convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        if self.healing_pool_remaining <= 0:
            return execution_event.phase_to(
                new_phase=EventPhase.EFFECT,
                total_damage=0,
                target_entity_name=target.name,
                status_message=f"Mass Heal pool exhausted for {target.name}"
            )

        missing_hp = target.health.damage_taken
        heal_amount = min(self.healing_pool_remaining, max(missing_hp, 0))

        source_desc = f"Mass Heal: {heal_amount} HP (from pool)"

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Mass Heal heals {target.name}"
        )

        actual = target.receive_healing(
            heal_amount, caster.uuid,
            source_description=source_desc,
            parent_event=effect_event.uuid,
            spell_level=self.cast_at_level
        )

        self.healing_pool_remaining -= actual

        if "Blinded" in target.active_conditions:
            target.remove_condition("Blinded", parent_event=effect_event)
        if "Deafened" in target.active_conditions:
            target.remove_condition("Deafened", parent_event=effect_event)

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Mass Heal heals {target.name} for {actual} HP"
        )


class DivineWordEffect(BaseCondition):
    """Divine Word effect — applies tier-based conditions with duration handler for auto-removal."""
    name: str = Field(default="Divine Word", description="Display name for the divine word effect condition.")
    description: str = Field(default="Affected by Divine Word", description="Rules-facing summary for the divine word effect condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the divine word effect for cleanup and filtering.")
    duration_rounds: int = Field(default=10, description="Number of rounds that nonlethal divine word effect effects persist.")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_conditions_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        execution_event = declaration_event

        current_hp = target.get_hp()

        if current_hp <= 20:

            effect_event = execution_event.phase_to(
                EventPhase.EFFECT,
                status_message=f"Divine Word kills {target.name}"
            )
            target.receive_damage(
                amount=99999,
                damage_type=DamageType.FORCE,
                source_entity_uuid=self.source_entity_uuid,
                parent_event=effect_event.uuid,
            )
            return [], [], [], [], effect_event

        elif current_hp <= 30:

            self.duration_rounds = 600
            for condition_cls in [Blinded, Deafened, Stunned]:
                cond = condition_cls(
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=self.target_entity_uuid,
                    parent_condition=self.uuid,
                )
                result = target.add_condition(cond, parent_event=execution_event)
                if result and result.phase == EventPhase.COMPLETION:
                    sub_conditions_uuids.append(cond.uuid)

        elif current_hp <= 40:

            self.duration_rounds = 100
            for condition_cls in [Blinded, Deafened]:
                cond = condition_cls(
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=self.target_entity_uuid,
                    parent_condition=self.uuid,
                )
                result = target.add_condition(cond, parent_event=execution_event)
                if result and result.phase == EventPhase.COMPLETION:
                    sub_conditions_uuids.append(cond.uuid)

        elif current_hp <= 50:

            self.duration_rounds = 10
            deafened = Deafened(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid,
            )
            result = target.add_condition(deafened, parent_event=execution_event)
            if result and result.phase == EventPhase.COMPLETION:
                sub_conditions_uuids.append(deafened.uuid)

        else:

            return [], [], [], [], execution_event.phase_to(
                EventPhase.EFFECT,
                status_message=f"Divine Word has no effect on {target.name} (HP > 50)"
            )

        duration_handler = self._create_duration_handler()
        target.add_event_handler(duration_handler)
        handler_uuids.append(duration_handler.uuid)

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Divine Word affects {target.name} ({self.duration_rounds} rounds)"
        )
        return [], handler_uuids, sub_conditions_uuids, [], effect_event

    def _create_duration_handler(self) -> EventHandler:
        """Remove this condition after duration_rounds turns."""
        assert self.target_entity_uuid is not None
        target_uuid = self.target_entity_uuid
        condition_uuid = self.uuid
        rounds_remaining = [self.duration_rounds]

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None
            target = Entity.get(target_uuid)
            if not target:
                return None

            rounds_remaining[0] -= 1
            if rounds_remaining[0] <= 0:
                if "Divine Word" in target.active_conditions:
                    active = target.active_conditions.get("Divine Word")
                    if active and active.uuid == condition_uuid:
                        target.remove_condition("Divine Word", parent_event=event)
            return None

        return EventHandler(
            name="Divine Word Duration",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=target_uuid,
                ),
            ],
            event_processor=processor,
        )


class DivineWord(SpellAction):
    """Divine Word — 7th-level evocation.

    You utter a divine word, imbued with the power that shaped the world.
    Each creature of your choice within range is affected based on current HP:
    - 50+ HP: No effect
    - 41-50 HP: Deafened for 1 minute
    - 31-40 HP: Blinded and Deafened for 10 minutes
    - 21-30 HP: Blinded, Deafened, and Stunned for 1 hour
    - 20 or fewer HP: Killed outright
    """
    harmful: Optional[bool] = Field(default=True, description="This spell imposes a harmful effect on its recipients.")
    name: str = Field(default="Divine Word", description="Display name for the divine word spell.")
    description: str = Field(default="HP-threshold effects: deafen/blind/stun/kill", description="Rules-facing summary for the divine word spell.")
    spell_level: int = Field(default=7, description="Spell slot level required to cast divine word; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify divine word.")
    concentration: bool = Field(default=False, description="Whether divine word creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Targeting mode used by action discovery and validation for divine word.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30), description="Range contract used when validating targets for divine word.")
    valid_target_filter: str = Field(default="enemies", description="Relationship filter used when collecting valid targets for divine word.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Divine Word Cost", cost_type="bonus_actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute divine word.")

    def get_multi_target_count(self) -> int:
        return self.get_num_projectiles()

    def get_num_projectiles(self) -> int:
        return 6

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        current_hp = target.get_hp()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Divine Word targets {target.name} ({current_hp} HP)"
        )

        condition = DivineWordEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        )
        target.add_condition(condition, parent_event=effect_event)

        if current_hp <= 20:
            outcome = "killed outright"
        elif current_hp <= 30:
            outcome = "blinded, deafened, and stunned (1 hour)"
        elif current_hp <= 40:
            outcome = "blinded and deafened (10 minutes)"
        elif current_hp <= 50:
            outcome = "deafened (1 minute)"
        else:
            outcome = "no effect"

        return effect_event.with_updates(
            total_damage=0,
            status_message=f"Divine Word: {target.name} is {outcome}"
        )


class FireShieldEffect(BaseCondition):
    granted_action_uuids: set[UUID] = Field(default_factory=set)
    description: str = "Warm/chill resistance and automatic retaliation against qualifying melee hits."
    name: str = "Fire Shield"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.ROUNDS, duration=100))
    shield_kind: Literal["warm", "chill"] = "warm"
    light_source_uuid: UUID | None = None
    retaliated_lineages: set[UUID] = Field(default_factory=set, exclude=True)

    _removed_light: SpatialChangeEvent | None = PrivateAttr(default=None)

    def snapshot_state(self) -> ConditionState:
        return super().snapshot_state().model_copy(update={"energy_type":
            DamageType.FIRE if self.shield_kind == "warm" else DamageType.COLD})

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Caster missing")
        resisted = DamageType.COLD if self.shield_kind == "warm" else DamageType.FIRE
        damage_type = DamageType.FIRE if self.shield_kind == "warm" else DamageType.COLD
        value = target.health.damage_reduction
        modifier = ResistanceModifier(name=self.name, value=ResistanceStatus.RESISTANCE, damage_type=resisted,
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid)
        value.self_static.add_resistance_modifier(modifier)
        self.light_source_uuid = get_map().add_light_source(position=target.position,
            bright_radius_feet=10, dim_radius_feet=10, anchor_uuid=target.uuid, parent_event=event.uuid)

        def retaliate(attack: Event, owner_uuid: UUID):
            if attack.canceled or attack.lineage_uuid in self.retaliated_lineages:
                return None
            if attack.event_type == EventType.ATTACK:
                weapon_hit = cast(AttackEvent, attack)
                melee = weapon_hit.range is not None and weapon_hit.range.type == RangeType.REACH
                outcome = weapon_hit.attack_outcome
            elif attack.event_type == EventType.CAST_SPELL:
                spell_hit = cast(SpellEvent, attack)
                melee = spell_hit.range_type == "touch"
                outcome = spell_hit.attack_outcome
            else:
                return None
            if not melee or outcome not in (AttackOutcome.HIT, AttackOutcome.CRIT):
                return None
            attacker = Entity.get(attack.source_entity_uuid)
            owner = Entity.get(owner_uuid)
            if attacker is None or owner is None or support_distance_feet(owner.position, get_map().get_support_elevation_feet(owner.position),
                    attacker.position, get_map().get_support_elevation_feet(attacker.position)) > 5:
                return None
            self.retaliated_lineages.add(attack.lineage_uuid)
            damage = Damage(source_entity_uuid=owner.uuid, target_entity_uuid=attacker.uuid,
                damage_dice=8, dice_numbers=2, damage_type=damage_type,
                damage_bonus=ModifiableValue.create(source_entity_uuid=owner.uuid, base_value=0, value_name="Fire Shield damage"))
            roll = damage.get_dice(AttackOutcome.HIT).roll
            attacker.receive_damage(amount=roll.total, damage_type=damage_type, source_entity_uuid=owner.uuid,
                parent_event=attack.uuid, damages=[damage], damage_rolls=[roll], effect_origin=self.effect_origin,
                independent_resolution=True, source_condition_uuid=self.uuid,
                effect_id="spell.fire_shield.retaliation")
            return None

        handler = EventHandler(name="Fire Shield retaliation", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target.uuid),
                Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target.uuid)], event_processor=retaliate)
        target.add_event_handler(handler)
        dismiss = DismissFireShield(source_entity_uuid=target.uuid, effect_uuid=self.uuid, template=True)
        target.register_action(dismiss)
        self.granted_action_uuids = {dismiss.uuid}
        return [(value.uuid, modifier.uuid)], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)

    def _release_owned_runtime_state(self, *, parent_event: Event | None = None) -> None:
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if owner is not None:
            for action_uuid in self.granted_action_uuids:
                owner.unregister_action_by_uuid(action_uuid)
        self.granted_action_uuids.clear()
        if self.light_source_uuid is not None:
            self._removed_light = get_map().remove_light_source(self.light_source_uuid,
                parent_event=parent_event.uuid if parent_event else None, publish_event=not self.applied)
            self.light_source_uuid = None
        super()._release_owned_runtime_state(parent_event=parent_event)

    def on_membership_changed(self, event: Event) -> None:
        removed, self._removed_light = self._removed_light, None
        if removed is not None:
            get_map()._fire_committed_spatial_event(removed)


class FireShield(SpellAction):
    name: str = "Fire Shield"
    description: str = "Warm/cold ward: resistance, 10-foot light and 2d8 retaliation against melee hits within 5 feet."
    spell_level: int = 4
    spell_school: str = "evocation"
    target_type: TargetType = TargetType.SELF
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    shield_kind: Literal["warm", "chill"] = "warm"

    def get_discovery_variants(self, entity: Any) -> list[BaseAction]:
        return [variant.model_copy(deep=True, update={"uuid":uuid4(), "shield_kind":kind,
            "registered_template_uuid":self.registered_template_uuid or self.uuid})
            for variant in super().get_discovery_variants(entity) for kind in ("warm","chill")]

    def get_variant_facets(self) -> tuple[ActionVariantFacet, ...]:
        return (ActionVariantFacet(key="form", value=self.shield_kind, label=self.shield_kind.title()),)

    def get_discovery_template_name(self) -> str:
        return f"{super().get_discovery_template_name()}__{self.shield_kind}"

    def get_discovery_display_name(self) -> str:
        return f"{super().get_discovery_display_name()} ({self.shield_kind})"

    def _apply(self, event: SpellEvent):
        return self.apply_owned_condition( event.phase_to(EventPhase.EFFECT), FireShieldEffect(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.source_entity_uuid, shield_kind=self.shield_kind))


@srd_action_identity(content_id="action.spell.fire_shield.dismiss", display_name="Dismiss Fire Shield",
    description="Dismiss the retained fire or cold shield.", parent_spell_name="Fire Shield", source_page=144, sort_order=1)
class DismissFireShield(BaseAction):
    name: str = "Dismiss Fire Shield"
    effect_uuid: UUID
    target_type: TargetType = TargetType.SELF
    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Dismiss Shield", cost_type="actions",
        cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def _apply(self, event: Event):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None or not caster.remove_condition_by_uuid(self.effect_uuid, parent_event=event):
            return event.cancel(status_message="Shield could not be dismissed")
        return event.phase_to(EventPhase.EFFECT)
