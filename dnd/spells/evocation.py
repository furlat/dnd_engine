"""Evocation spells - dealing damage and channeling energy, and healing.

Contains: FireBolt, SacredFlame, MagicMissile, Fireball, BurningHands,
          LightningBolt, Thunderwave, Shatter, Sunburst, RayOfFrost, ScorchingRay,
          ShockingGrasp, GuidingBolt, GustOfWind, IceStorm, Sunbeam,
          CureWounds, HealingWord, PrayerOfHealing, MassHealingWord,
          MassCureWounds, HealSpell, MassHeal
"""
import random
from typing import Any, Optional, List, Set, Tuple
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.content.spatial_effect_materialization import (
    materialize_spatial_effect,
)
from dnd.core.base_actions import (
    ActionCategory,
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
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.types.conditions import (
    ConditionCategory,
    ConditionTag,
    DurationType,
    HazardFilter,
)
from dnd.core.values import ModifiableValue
from dnd.types.rolls import AttackOutcome
from dnd.types.rolls import DieSize
from typing import cast as type_cast
from dnd.types.equipment import ArmorType, WeaponSlot
from dnd.core.events.events_registry import (
    EventPhase,
    EventType,
    EventHandler,
    Trigger,
    Event,
    EventQueue,
)
from dnd.core.events.resolution_events import (
    RangeType,
    Range,
    Damage,
    Healing,
)
from dnd.core.events.world_events import (
    ForcedMovementEvent,
    SpatialChangeEvent,
    SpatialEffectInteractionEvent,
)
from dnd.types.abilities import AbilityName
from dnd.types.spatial_effects import (
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
    SpatialEffectTriggerKind,
)
from dnd.types.creatures import CreatureType
from dnd.types.damage import DamageType
from dnd.core.modifiers import AdvantageModifier, NumericalModifier
from dnd.types.rolls import AdvantageStatus
from dnd.core.aoe import AoEShape, Sphere, Cone, Line, Cube, Cylinder
from dnd.core.gridmap import get_map
from dnd.blocks.equipment import (
    Weapon as WeaponItem,
    Shield as ShieldItem,
)

from dnd.entity import Entity
from dnd.actions.standard import (
    Attack,
    AttackDamageContribution,
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_evaluator,
    validate_line_of_sight,
)
from dnd.conditions import Blinded, Deafened, Stunned, NoReactions, Concentrating, ConcentrationActionMarker, Restrained
from dnd.spells.content_metadata import srd_action_identity, srd_spell_identity
from dnd.spells.spell_utils import fire_heal_roll_result
from dnd.spells.effect_ids import (
    MAGIC_MISSILE_DAMAGE_EFFECT_ID,
)
from dnd.content.spatial_effect_recipes import (
    CONTINUAL_FLAME_FIELD_RECIPE,
    GUST_OF_WIND_FIELD_RECIPE,
    ICE_STORM_SURFACE_RECIPE,
)
from dnd.spatial.effect_base import (
    FieldEffect,
    GroundEffect,
    SpatialEffect,
    SpatialEffectController,
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
    name: str = Field(default="Fire Bolt", description="Display name for the fire bolt spell.")
    description: str = Field(default="Hurl a mote of fire at a target", description="Rules-facing summary for the fire bolt spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast fire bolt; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify fire bolt.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for fire bolt.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for fire bolt.",
    )
    projectile_type: Optional[str] = Field(default="bolt", description="Projectile visualization hint for fire bolt.")
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
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
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
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} missed"
            )

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

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.FIRE,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[fire_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} fire damage"
        )


class RayOfFrostEffect(BaseCondition):
    """Tracks Ray of Frost speed reduction on caster.

    Duration: 1 round (expires at start of caster's next turn).

    This follows the SRD: "until the start of YOUR next turn" = CASTER's turn.
    The condition lives on the caster but applies a speed modifier to the target.
    The modifier is tracked via modifiers_uuids, so it gets cleaned up automatically
    when this condition expires at caster's turn start.
    """
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
    affected_target_uuid: Optional[UUID] = Field(default=None, description="Target entity UUID whose state is modified by ray of frost effect.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.affected_target_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Affected target UUID not set")

        target = Entity.get(self.affected_target_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")
        if target.ignore_magical_speed_reduction:
            return [], [], [], [], declaration_event.cancel(status_message=f"{target.name} ignores magical speed reduction")

        outs: List[Tuple[UUID, UUID]] = []

        speed_reduction = NumericalModifier(
            name="Ray of Frost",
            value=-10,
            source_entity_uuid=self.source_entity_uuid or self.target_entity_uuid,
            target_entity_uuid=self.affected_target_uuid
        )
        mod_uuid = target.action_economy.movement.self_static.add_value_modifier(speed_reduction)
        outs.append((target.action_economy.movement.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Ray of Frost speed reduction to {target.name}"
        )
        return outs, [], [], [], effect_event


class RayOfFrost(SpellAction):
    """Ray of Frost - Evocation cantrip

    A frigid beam of blue-white light streaks toward a creature within range.
    Make a ranged spell attack. On hit, target takes 1d8 cold damage and its
    speed is reduced by 10 feet until the start of your next turn.

    Damage scales: 2d8 at 5th, 3d8 at 11th, 4d8 at 17th.
    """
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
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
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
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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
            target_entity_uuid=caster.uuid,
            affected_target_uuid=target.uuid,
            tags={ConditionTag.MAGICAL},
            duration=Duration(
                duration=1,
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid
            )
        )
        caster.add_condition(effect_condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
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
            ability_name=AbilityName.DEXTERITY,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.DEXTERITY).normalized_score

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
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        return self._validate_entity_targets_in_range_and_sight(
            declaration_event,
            self.get_all_targets(),
        )

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
            new_phase=EventPhase.COMPLETION,
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
        return self._validate_entity_targets_in_range_and_sight(
            declaration_event,
            self.get_all_targets(),
        )

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
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
                target=self.end_position if self.end_position is not None else (0, 0),
                radius_feet=20
            )

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
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply fireball damage to current target (called once per target by convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.DEXTERITY,
            dc=dc,
            parent_event=execution_event.uuid
        )

        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = save_roll.bonus

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
        completion_event = effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[fire_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Fireball deals {final_damage} fire damage to {target.name}{save_text}"
        )
        return completion_event


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

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cone(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position if self.end_position is not None else (1, 0),
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
        return self._validate_directional_self_cast(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply burning hands damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.DEXTERITY,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.DEXTERITY).normalized_score

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
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Line(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position if self.end_position is not None else (1, 0),
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

        if self.end_position is None:
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
            ability_name=AbilityName.DEXTERITY,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.DEXTERITY).normalized_score

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
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position if self.end_position is not None else (1, 0),
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

        grid = get_map()
        distance_tiles = distance_feet // 5
        last_valid_pos = start
        was_blocked = False
        blocked_by: Optional[str] = None

        current_pos = start
        for _ in range(distance_tiles):
            next_pos = (current_pos[0] + direction[0], current_pos[1] + direction[1])

            if not grid.can_transition(current_pos, next_pos, target_uuid):
                was_blocked = True
                blocked_by = grid.identify_blocker_at(next_pos, target_uuid)
                break

            entities_at_pos = grid.get_entities_at(next_pos)
            other_entities = [e for e in entities_at_pos if e != target_uuid]
            if other_entities:
                was_blocked = True
                blocker = BaseBlock.get(other_entities[0])
                blocked_by = blocker.name if blocker else "entity"
                break

            last_valid_pos = next_pos
            current_pos = next_pos

        actual_distance = abs(last_valid_pos[0] - start[0]) + abs(last_valid_pos[1] - start[1])
        actual_distance_feet = actual_distance * 5

        return (last_valid_pos, actual_distance_feet, was_blocked, blocked_by)

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate cube direction. Self-range means no LOS check to target position."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if self.end_position is None:
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
            ability_name=AbilityName.CONSTITUTION,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.CONSTITUTION).normalized_score

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
                    parent_event=effect_event.uuid,
                    use_register=False,
                )

                forced_event = EventQueue.publish_declaration(forced_event)
                if not forced_event.canceled:
                    forced_event = forced_event.phase_to(EventPhase.EXECUTION)
                if not forced_event.canceled:
                    forced_event = forced_event.phase_to(EventPhase.EFFECT)
                if not forced_event.canceled:
                    Entity.update_entity_position(
                        target,
                        end_pos,
                        parent_event=forced_event.uuid,
                    )
                    forced_event.phase_to(
                        EventPhase.COMPLETION,
                        end_position=target.position,
                    )
                    push_applied = True

        save_text = " (saved for half)" if success else ""
        push_text = f", pushed {push_distance_actual}ft" if push_applied else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
                target=self.end_position if self.end_position is not None else (0, 0),
                radius_feet=10
            )

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
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply shatter damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.CONSTITUTION,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.CONSTITUTION).normalized_score

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
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
                target=self.end_position if self.end_position is not None else (0, 0),
                radius_feet=60
            )

    def get_damage_dice_count(self) -> int:
        """8d6 base + 2d6 per level above 6th."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + (upcast_bonus * 2)

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply circle of death damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.CONSTITUTION,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.CONSTITUTION).normalized_score

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
                parent_event=effect_event.uuid
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
                target=self.end_position if self.end_position is not None else (1, 0),
                length_feet=60
            )

    def get_damage_dice_count(self) -> int:
        """8d8 base + 1d8 per level above 5th."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate cone direction. Self-range means no LOS check to target position."""
        return self._validate_directional_self_cast(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply cone of cold damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.CONSTITUTION,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.CONSTITUTION).normalized_score

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
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[cold_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Cone of Cold deals {final_damage} cold damage to {target.name}{save_text}"
        )


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

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        blinded = Blinded(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        sub_event = target.add_condition(blinded, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(blinded.uuid)

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

            sunburst_blind = target.active_conditions.get("Sunburst Blindness")
            if not sunburst_blind or sunburst_blind.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:

                target.remove_condition("Sunburst Blindness", parent_event=event)
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name=AbilityName.CONSTITUTION,
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if success:

                target.remove_condition("Sunburst Blindness", parent_event=event)
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

    base_damage_dice: int = Field(default=12, description="Base number of damage dice rolled by sunburst.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position if self.end_position is not None else (0, 0),
                radius_feet=60
            )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position LOS and range."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if target_pos is None:
            return declaration_event.cancel(status_message="No target position")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not in LOS")

        distance = caster.distance_to_position(target_pos)
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
            mod_uuid = target.saving_throws.get_saving_throw(AbilityName.CONSTITUTION).bonus.self_static.add_advantage_modifier(disadv_mod)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.CONSTITUTION,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        if has_disadvantage and mod_uuid:
            target.saving_throws.get_saving_throw(AbilityName.CONSTITUTION).bonus.self_static.remove_modifier(mod_uuid)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.CONSTITUTION).normalized_score

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
                parent_event=effect_event.uuid
            )

        if not success:
            blind_effect = SunburstBlindedEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid,
                spell_dc=dc,
                tags={ConditionTag.MAGICAL}
            )
            target.add_condition(blind_effect, parent_event=effect_event)

        blind_text = " and blinded" if not success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[radiant_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Sunburst: {final_damage} radiant{blind_text} to {target.name}"
        )


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
        return self._validate_entity_target_in_range_and_sight(declaration_event)

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
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
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
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[radiant_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} radiant damage, next attack has advantage"
        )


class EldritchBlast(SpellAction):
    """Eldritch Blast - Evocation cantrip

    A beam of crackling energy streaks toward a creature within range.
    Make a ranged spell attack. On hit, target takes 1d10 force damage.
    Damage scales with caster level: 2d10 at 5th, 3d10 at 11th, 4d10 at 17th.
    """
    name: str = Field(default="Eldritch Blast", description="Display name for the eldritch blast spell.")
    description: str = Field(default="A beam of crackling force energy", description="Rules-facing summary for the eldritch blast spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast eldritch blast; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify eldritch blast.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for eldritch blast.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for eldritch blast.",
    )
    projectile_type: Optional[str] = Field(default="beam", description="Projectile visualization hint for eldritch blast.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FORCE, description="Primary damage type for VFX")

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return Eldritch Blast's level-scaled actor-baseline attack model."""
        if not isinstance(actor, Entity):
            return None
        return self.spell_attack_outcome_profile(
            actor,
            dice_count=self._get_cantrip_dice_count(self.caster_level),
            die_size=10,
            damage_type=DamageType.FORCE,
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
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
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} missed"
            )

        num_dice = self._get_cantrip_dice_count(self.caster_level)
        is_crit = outcome == AttackOutcome.CRIT

        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0
        damage_bonus = caster.get_spell_damage_bonus()
        force_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=10,
            dice_numbers=num_dice,
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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[force_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} force damage"
        )

from dnd.spatial.effect_controllers import AreaSpatialEffectController


class GustOfWindZone(AreaSpatialEffectController):
    """Zone for Gust of Wind - 60ft line of wind that pushes creatures."""
    name: str = Field(default="Gust of Wind Zone", description="Display name for the gust of wind zone zone condition.")
    description: str = Field(default="Strong wind pushes creatures and costs extra movement", description="Rules-facing summary for the gust of wind zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the gust of wind zone for cleanup and filtering.")

    zone_shape: str = Field(default="line", description="Domain value for zone_shape on gust of wind zone.")
    zone_radius_feet: int = Field(default=60, description="Zone radius in feet used by gust of wind zone.")
    adds_difficult_terrain: bool = Field(default=True, description="Whether gust of wind zone makes affected tiles difficult terrain.")

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for gust of wind zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by gust of wind zone saving throws.")
    caster_position: Tuple[int, int] = Field(default=(0, 0), description="Domain value for caster_position on gust of wind zone.")
    _pushes_in_flight: Set[UUID] = PrivateAttr(default_factory=set)

    def _compute_affected_positions(self) -> Set[Tuple[int, int]]:
        """Compute line from caster in the chosen direction."""
        if not self.zone_direction:
            return {self.zone_center}
        dx, dy = self.zone_direction
        length_tiles = self.zone_radius_feet // 5
        target = (self.zone_center[0] + dx * length_tiles,
                  self.zone_center[1] + dy * length_tiles)

        line = Line(
            source_entity_uuid=self.source_entity_uuid,
            target=target,
            length_feet=self.zone_radius_feet,
            width_feet=10
        )
        line.compute_objective(caster_pos=self.zone_center)
        return set(line.affected_positions)

    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({
        SpatialEffectTriggerKind.ENTER,
        SpatialEffectTriggerKind.TURN_START,
    })

    def _create_zone_entry_handler(self) -> EventHandler:
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        caster_pos = self.caster_position

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
                _apply_gust_push(entity, dc, caster_pos, source_uuid, event)
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
        caster_pos = self.caster_position
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            entity = Entity.get(event.source_entity_uuid)
            if not entity or not entity.has_hp:
                return None
            if entity.senses.position not in zone_condition.affected_positions:
                return None

            if entity.uuid in zone_condition._pushes_in_flight:
                return None
            zone_condition._pushes_in_flight.add(entity.uuid)
            try:
                _apply_gust_push(entity, dc, caster_pos, source_uuid, event)
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
        """Emit strong wind exposure over the current Gust line."""
        if not self.affected_positions:
            return
        wind_event = SpatialEffectInteractionEvent(
            source_entity_uuid=self.source_entity_uuid,
            operation=SpatialEffectInteractionOperation.DISPERSE,
            positions=tuple(sorted(self.affected_positions)),
            intensity=SpatialEffectInteractionIntensity.STRONG,
            parent_event=parent_event.uuid if parent_event is not None else None,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
        EventQueue.publish_lifecycle(wind_event)

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

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
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
    save_request = entity.create_saving_throw_request(
        target_entity_uuid=entity.uuid,
        ability_name=AbilityName.STRENGTH,
        dc=dc,
        parent_event=parent_event.uuid
    )
    _, _, success = entity.saving_throw(save_request)
    if success:
        return

    entity_pos = entity.senses.position
    dx = entity_pos[0] - caster_pos[0]
    dy = entity_pos[1] - caster_pos[1]
    length = max(abs(dx), abs(dy), 1)
    push_dx = round(dx / length) if dx != 0 else 0
    push_dy = round(dy / length) if dy != 0 else 0
    if push_dx == 0 and push_dy == 0:
        push_dx = 1

    grid = get_map()
    current_pos = entity_pos
    for _ in range(3):
        next_pos = (current_pos[0] + push_dx, current_pos[1] + push_dy)
        if not grid.can_transition(current_pos, next_pos, entity.uuid):
            break
        current_pos = next_pos

    if current_pos != entity_pos:
        push_dist = (abs(current_pos[0] - entity_pos[0]) + abs(current_pos[1] - entity_pos[1])) * 5
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
            blocked_by_obstacle=push_dist < 15,
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
            Entity.update_entity_position(
                entity,
                current_pos,
                parent_event=forced_event.uuid,
            )
            forced_event.phase_to(
                EventPhase.COMPLETION,
                end_position=entity.position,
            )


class GustOfWind(SpellAction):
    """Gust of Wind - 2nd level Evocation (Concentration)

    A line of strong wind 60ft long and 10ft wide blasts from you.
    STR save or pushed 15ft away. Difficult terrain toward caster.
    """
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

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Line(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position if self.end_position is not None else (1, 0),
                length_feet=60,
                width_feet=10
            )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if self.end_position is None:
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

        _apply_gust_push(target, dc, caster.senses.position, caster.uuid, effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        target_pos = self.end_position if self.end_position is not None else (caster.senses.position[0] + 1, caster.senses.position[1])

        dx = target_pos[0] - caster.senses.position[0]
        dy = target_pos[1] - caster.senses.position[1]
        length = max(abs(dx), abs(dy), 1)
        direction = (round(dx / length), round(dy / length))

        field = materialize_spatial_effect(
            GUST_OF_WIND_FIELD_RECIPE,
            caster.uuid,
            position=caster.senses.position,
            faction=caster.faction,
            expected_type=FieldEffect,
        )
        zone = GustOfWindZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=field.uuid,
            zone_center=caster.senses.position,
            zone_direction=direction,
            spell_dc=dc,
            caster_position=caster.senses.position,
            effect_origin=parent_event.to_effect_origin(),
        )
        field.install_controller(zone, parent_event=parent_event)

        concentration = self.ensure_concentration(parent_event)
        concentration.add_linked_condition(field.uuid, zone.uuid)


class IceStormTerrain(AreaSpatialEffectController):
    """Temporary difficult terrain from Ice Storm. Lasts 1 round."""
    name: str = Field(default="Ice Storm Terrain", description="Display name for the ice storm terrain zone condition.")
    description: str = Field(default="Ground covered in ice - difficult terrain", description="Rules-facing summary for the ice storm terrain zone condition.")

    zone_shape: str = Field(default="sphere", description="Domain value for zone_shape on ice storm terrain.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by ice storm terrain.")
    adds_difficult_terrain: bool = Field(default=True, description="Whether ice storm terrain makes affected tiles difficult terrain.")

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for ice storm terrain hazard markers.")


class IceStorm(SpellAction):
    """Ice Storm - 4th level Evocation

    Hail pounds a 20ft-radius, 40ft-high cylinder. DEX save or
    2d8 bludgeoning + 4d6 cold (half on save). Ground becomes difficult terrain for 1 round.

    At Higher Levels: +1d8 bludgeoning per level above 4th.
    """
    name: str = Field(default="Ice Storm", description="Display name for the ice storm spell.")
    description: str = Field(default="20ft cylinder: 2d8 bludg + 4d6 cold (DEX half), difficult terrain 1 round", description="Rules-facing summary for the ice storm spell.")
    spell_level: int = Field(default=4, description="Spell slot level required to cast ice storm; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify ice storm.")
    concentration: bool = Field(default=False, description="Whether ice storm creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for ice storm.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60), description="Range contract used when validating targets for ice storm.")
    projectile_type: Optional[str] = Field(default="rain", description="Projectile visualization hint for ice storm.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.BLUDGEONING, description="Primary damage type for VFX")

    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by ice storm to compute affected targets.")
    include_self: bool = Field(default=True, description="Whether ice storm can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for ice storm.")

    base_bludg_dice: int = Field(default=2, description="Domain value for base_bludg_dice on ice storm.")
    cold_dice: int = Field(default=4, description="Domain value for cold_dice on ice storm.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cylinder(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position if self.end_position is not None else (0, 0),
                radius_feet=20,
                height_feet=40
            )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_visible_position_in_range(declaration_event)

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
            ability_name=AbilityName.DEXTERITY,
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
            parent_event=effect_event.uuid
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[bludg_damage, cold_damage],
            damage_rolls=[bludg_roll, cold_roll],
            total_damage=total,
            status_message=f"Ice Storm deals {total} damage to {target.name}"
        )

    def _finalize_aoe(self, effect_event: SpellEvent) -> None:
        """Apply difficult terrain zone after convolution completes."""
        self._setup_terrain(effect_event)

    def _setup_terrain(self, effect_event: SpellEvent) -> None:
        """Apply 1-round difficult terrain at the target area."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return

        target_pos = self.end_position
        if target_pos is None:
            return

        surface = materialize_spatial_effect(
            ICE_STORM_SURFACE_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            expected_type=GroundEffect,
        )
        terrain = IceStormTerrain(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=surface.uuid,
            zone_center=target_pos,
            effect_origin=effect_event.to_effect_origin(),
        )
        terrain.duration.duration_type = DurationType.ROUNDS
        terrain.duration.duration = 1
        surface.install_controller(terrain, parent_event=effect_event)


@srd_action_identity(
    content_id="action.spell.sunbeam.strike",
    display_name="Sunbeam Strike",
    description="Fire another beam from an active Sunbeam spell.",
    parent_spell_name="Sunbeam",
    source_page=184,
    sort_order=930,
)
class SunbeamStrike(BaseAction):
    """Action granted by Sunbeam to fire a beam of radiant light each turn."""
    name: str = Field(default="Sunbeam Strike", description="Display name for the sunbeam strike action.")
    description: str = Field(default="Fire a beam of brilliant light - 60ft line", description="Rules-facing summary for the sunbeam strike action.")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE, description="Targeting mode used by action discovery and validation for sunbeam strike.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Domain value for action_category on sunbeam strike.")
    aoe_shape: Optional[AoEShape] = Field(default=None, description="Area shape used by sunbeam strike to compute affected targets.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Sunbeam Strike", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute sunbeam strike.")
    spell_dc: int = Field(default=10, description="Spell save DC used by sunbeam strike saving throws.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Range contract used when validating targets for sunbeam strike.")
    include_self: bool = Field(default=False, description="Whether sunbeam strike can include the caster among valid targets.")
    valid_target_filter: str = Field(default="all", description="Relationship filter used when collecting valid targets for sunbeam strike.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Line(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position if self.end_position is not None else (1, 0),
                length_feet=60,
                width_feet=5
            )

    def _validate(self, declaration_event: Event) -> Optional[Event]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if "Concentrating" not in caster.active_conditions:
            return declaration_event.cancel(status_message="Not concentrating on Sunbeam")

        conc = caster.active_conditions.get("Concentrating")
        if not isinstance(conc, Concentrating) or conc.get_slot_by_spell_name("Sunbeam") is None:
            return declaration_event.cancel(status_message="Not concentrating on Sunbeam")

        if self.end_position is None:
            return declaration_event.cancel(status_message="No direction specified")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: Event) -> Optional[Event]:
        """Per-target: CON save, 6d8 radiant, Blinded on fail."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.CONSTITUTION,
            dc=self.spell_dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"CON save: {save_roll.total} vs DC {self.spell_dc}"
        )

        damage_bonus = caster.get_spell_damage_bonus()
        radiant_damage = Damage(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            damage_dice=8, dice_numbers=6, damage_bonus=damage_bonus,
            damage_type=DamageType.RADIANT
        )
        damage_roll = radiant_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        final_damage = damage_roll.total // 2 if success else damage_roll.total
        target.receive_damage(final_damage, DamageType.RADIANT, caster.uuid, parent_event=effect_event.uuid)

        if not success:
            blinded = Blinded(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                tags={ConditionTag.MAGICAL}
            )
            blinded.duration.duration_type = DurationType.ROUNDS
            blinded.duration.duration = 1
            target.add_condition(blinded, parent_event=effect_event)

        save_text = " (saved for half)" if success else " + Blinded"
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[radiant_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Sunbeam deals {final_damage} radiant to {target.name}{save_text}"
        )


class Sunbeam(SpellAction):
    """Sunbeam - 6th level Evocation (Concentration)

    A beam of brilliant light flashes out in a 60ft line.
    CON save or 6d8 radiant + Blinded (half on save, no blind).
    You can create a new beam each turn as an action.
    """
    name: str = Field(default="Sunbeam", description="Display name for the sunbeam spell.")
    description: str = Field(default="60ft line beam, 6d8 radiant + Blinded (CON half), repeatable", description="Rules-facing summary for the sunbeam spell.")
    spell_level: int = Field(default=6, description="Spell slot level required to cast sunbeam; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify sunbeam.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Primary damage type for VFX")
    concentration: bool = Field(default=True, description="Whether sunbeam creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode used by action discovery and validation for sunbeam.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Range contract used when validating targets for sunbeam.")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Sunbeam"
        )

        strike = SunbeamStrike(
            source_entity_uuid=caster.uuid,
            spell_dc=dc,
            template=True
        )

        concentration = self.ensure_concentration(effect_event)
        marker = ConcentrationActionMarker(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            action_name=strike.name
        )
        caster.register_condition_action(marker, strike)
        caster.add_condition(marker, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, marker.uuid)

        if self.end_position:
            first_strike = SunbeamStrike(
                source_entity_uuid=caster.uuid,
                end_position=self.end_position,
                spell_dc=dc,
                template=False,
                costs=[],
            )
            first_strike.apply()

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} channels Sunbeam - can fire a beam each turn"
        )


class ChainLightning(SpellAction):
    """Chain Lightning - 6th level Evocation

    You create a bolt of lightning that arcs toward a target of your choice
    within range. Three bolts then leap from that target to up to three other
    targets within 30 feet. Each target makes a DEX save, taking 10d8 lightning
    on failure or half on success.

    At Higher Levels: +1 additional secondary target per slot level above 6th.
    """
    name: str = Field(default="Chain Lightning", description="Display name for the chain lightning spell.")
    description: str = Field(default="10d8 lightning to primary + up to 3 secondaries (DEX half)", description="Rules-facing summary for the chain lightning spell.")
    spell_level: int = Field(default=6, description="Spell slot level required to cast chain lightning; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify chain lightning.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for chain lightning.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150), description="Range contract used when validating targets for chain lightning.")
    valid_target_filter: str = Field(default="enemies", description="Relationship filter used when collecting valid targets for chain lightning.")
    projectile_type: Optional[str] = Field(default="bolt", description="Projectile visualization hint for chain lightning.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.LIGHTNING, description="Primary damage type for VFX")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event
        result = super()._validate(los_event)
        return type_cast(Optional[SpellEvent], result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        upcast_bonus = self.get_upcast_bonus()
        max_secondaries = 3 + upcast_bonus
        base_dice = 10 + upcast_bonus
        damage_bonus = caster.get_spell_damage_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity", save_dc=dc,
            status_message=f"{caster.name} casts Chain Lightning"
        )

        chain_targets = [target]
        chain_uuids = {target.uuid}

        visible_enemy_dict = caster.get_visible_enemies()
        visible_enemies: List[Entity] = []
        for e_uuid in visible_enemy_dict:
            e = Entity.get(e_uuid)
            if e:
                visible_enemies.append(e)

        for _ in range(max_secondaries):
            best_candidate: Optional[Entity] = None
            best_distance = float('inf')

            for enemy in visible_enemies:
                if enemy.uuid in chain_uuids or not enemy.has_hp:
                    continue

                for chain_target in chain_targets:
                    dist = enemy.distance_to_entity(chain_target)
                    if dist <= 30 and dist < best_distance:
                        best_distance = dist
                        best_candidate = enemy

            if best_candidate is None:
                break
            chain_targets.append(best_candidate)
            chain_uuids.add(best_candidate.uuid)

        total_damage = 0
        all_damages: List[Damage] = []
        all_rolls = []
        for chain_target in chain_targets:
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=chain_target.uuid,
                ability_name=AbilityName.DEXTERITY, dc=dc,
                parent_event=effect_event.uuid
            )
            _, _, success = chain_target.saving_throw(save_request)
            lightning_damage = Damage(
                source_entity_uuid=caster.uuid, target_entity_uuid=chain_target.uuid,
                damage_dice=8, dice_numbers=base_dice, damage_bonus=damage_bonus,
                damage_type=DamageType.LIGHTNING
            )
            damage_roll = lightning_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
            final_damage = damage_roll.total // 2 if success else damage_roll.total
            chain_target.receive_damage(final_damage, DamageType.LIGHTNING, caster.uuid, parent_event=effect_event.uuid)
            total_damage += final_damage
            all_damages.append(lightning_damage)
            all_rolls.append(damage_roll)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=all_damages,
            damage_rolls=all_rolls,
            total_damage=total_damage,
            status_message=f"Chain Lightning hits {len(chain_targets)} targets for {total_damage} total lightning damage"
        )


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
                ability_name=AbilityName.CONSTITUTION, dc=dc,
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
                target=self.end_position if self.end_position is not None else (1, 0),
                length_feet=60
            )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if self.end_position is None:
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
            save_ability = (
                AbilityName.CONSTITUTION
                if color == 4
                else AbilityName.DEXTERITY
            )
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
                ability_name=AbilityName.CONSTITUTION, dc=dc,
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
                ability_name=AbilityName.WISDOM, dc=dc,
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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Prismatic Spray: {target.name} hit by {color_desc} ({color_text})"
        )


class TrueStrike(SpellAction):
    """True Strike - Evocation cantrip (5.5e version)

    Weapon attack using spellcasting ability instead of STR/DEX.
    Cantrip scaling: +1d6 radiant at levels 5, 11, 17.

    Delegates to Attack with a cold action-owned radiant contribution.

    Register two variants per caster: TrueStrike(Melee) and TrueStrike(Ranged)
    using weapon_slot field. Each variant uses the weapon's range for targeting.
    """
    name: str = Field(default="True Strike", description="Display name for the true strike spell.")
    description: str = Field(default="Weapon attack using spellcasting ability, +radiant damage at higher levels", description="Rules-facing summary for the true strike spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast true strike; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify true strike.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for true strike.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5),
        description="Range contract used when validating targets for true strike.",
    )

    weapon_slot: WeaponSlot = Field(default=WeaponSlot.MELEE_MAIN, description="Domain value for weapon_slot on true strike.")

    include_self: bool = Field(default=False, description="Whether true strike can include the caster among valid targets.")
    valid_target_filter: str = Field(default="enemies", description="Relationship filter used when collecting valid targets for true strike.")

    def get_discovery_weapon_slot(self) -> Optional[WeaponSlot]:
        """Return the weapon slot used by this spell-delivered attack."""
        return self.weapon_slot

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate: weapon exists in slot, target in LOS."""
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
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
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        ability_name: AbilityName = type_cast(AbilityName, caster.spellcasting.spellcasting_ability or "intelligence")

        extra_dice = self._get_cantrip_dice_count(self.caster_level) - 1
        contributions = (
            (
                AttackDamageContribution(
                    dice_count=extra_dice,
                    damage_die=6,
                    damage_type=DamageType.RADIANT,
                    label="True Strike Radiant Damage",
                ),
            )
            if extra_dice > 0
            else ()
        )
        attack = Attack(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=self.weapon_slot,
            override_ability=ability_name,
            additional_damage_contributions=contributions,
            costs=[],
            template=False,
        )
        attack_result = attack.apply(parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
                target=self.end_position if self.end_position is not None else (0, 0),
                radius_feet=10,
                height_feet=40
            )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_visible_position_in_range(declaration_event)

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
            ability_name=AbilityName.DEXTERITY,
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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
            parent_event=declaration_event.uuid,
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Light shines from {target.name}"
        )
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        if self.light_source_uuid:
            grid = get_map()
            grid.remove_light_source(
                self.light_source_uuid,
                parent_event=event.uuid if event is not None else None,
            )
            self.light_source_uuid = None
        return super()._remove(event)


class Light(SpellAction):
    """Light - Evocation Cantrip

    You touch one object. For the duration, the object sheds bright light
    in a 20-foot radius and dim light for an additional 20 feet.

    Duration: 1 hour.
    """
    name: str = Field(default="Light", description="Display name for the light spell.")
    description: str = Field(default="Touch: object sheds 20ft bright + 20ft dim light for 1 hour", description="Rules-facing summary for the light spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast light; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify light.")
    concentration: bool = Field(default=False, description="Light does not require concentration.")
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
        light_effect.duration.duration = 600
        target.add_condition(light_effect, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Light shines from {target.name}"
        )


class ContinualFlameController(SpatialEffectController):
    """Own the permanent light source attached to a continual-flame field."""

    name: str = Field(default="Continual Flame", description="Effect name.")
    description: str = Field(
        default="A permanent heatless flame sheds bright and dim light.",
        description="Rules-facing effect summary.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        frozen=True,
        description="The spatial effect itself is the public identity.",
    )
    position: Tuple[int, int] = Field(
        description="Exact grid cell occupied by the flame.",
    )
    _light_source_uuid: Optional[UUID] = PrivateAttr(default=None)

    def resolve_effect_footprint(self) -> Set[Tuple[int, int]]:
        """Continual Flame occupies exactly its valid target cell."""
        return {self.position} if get_map().has_tile(*self.position) else set()

    def rollback_failed_install(self) -> None:
        """Remove any anchored light created before an exceptional failure."""
        if self._light_source_uuid is not None:
            get_map().remove_light_source(self._light_source_uuid)
        self._light_source_uuid = None

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Continual Flame has no spatial owner",
            )
        effect = SpatialEffect.get_effect(self.target_entity_uuid)
        if effect is None or effect.anchor_uuid is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Continual Flame has no world-object anchor",
            )
        self._light_source_uuid = get_map().add_light_source(
            position=self.position,
            very_bright_radius_feet=0,
            bright_radius_feet=20,
            dim_radius_feet=20,
            anchor_uuid=effect.anchor_uuid,
            parent_event=declaration_event.uuid,
        )
        return (
            [],
            [],
            [],
            [],
            declaration_event.phase_to(EventPhase.EFFECT, condition=self),
        )

    def relocate_anchor(
        self,
        position: Tuple[int, int],
        *,
        parent_event: Event,
    ) -> None:
        """Move the field footprint and light with its exact world object."""
        if self.target_entity_uuid is None or self._light_source_uuid is None:
            raise RuntimeError("Continual Flame anchor runtime is unavailable")
        effect = SpatialEffect.get_effect(self.target_entity_uuid)
        if effect is None:
            raise RuntimeError("Continual Flame lost its spatial owner")
        self.position = position
        effect.set_position(position)
        get_map().move_light_source(
            self._light_source_uuid,
            position,
            parent_event=parent_event.uuid,
        )
        effect.synchronize_footprint(
            {position},
            parent_event=parent_event,
        )

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Remove the object-attached light when the field retires."""
        if self._light_source_uuid is not None:
            get_map().remove_light_source(
                self._light_source_uuid,
                parent_event=event.uuid if event is not None else None,
            )
            self._light_source_uuid = None
        return super()._remove(event)


class ContinualFlame(SpellAction):
    """Continual Flame - 2nd level Evocation (NOT concentration)

    A flame, equivalent in brightness to a torch, springs forth from an object
    that you touch. The flame emits no heat and doesn't use oxygen. A continual
    flame can be covered or hidden but not smothered or quenched.

    The flame sheds bright light in a 20-foot radius and dim light for an
    additional 20 feet. Permanent until dispelled.
    """
    name: str = Field(default="Continual Flame", description="Display name for the continual flame spell.")
    description: str = Field(default="Touch: permanent 20ft bright + 20ft dim light on object", description="Rules-facing summary for the continual flame spell.")
    spell_level: int = Field(default=2, description="Spell slot level required to cast continual flame; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify continual flame.")
    concentration: bool = Field(default=False, description="Whether continual flame creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.OBJECT, description="Continual Flame targets a placed world object.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Range contract used when validating targets for continual flame.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = (
            BaseBlock.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if caster is None:
            return declaration_event.cancel(status_message="Caster not found")
        if target is None:
            return declaration_event.cancel(status_message="No target object")
        position = get_map().get_object_position(target.uuid)
        if position is None:
            return declaration_event.cancel(
                status_message="Target object is not placed on the grid",
            )
        target_distance = caster.distance_to_object(target)
        if target_distance is None or target_distance > 5:
            return declaration_event.cancel(status_message="Target object is out of reach")
        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target = (
            BaseBlock.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        position = (
            get_map().get_object_position(target.uuid)
            if target is not None
            else None
        )
        if target is None or position is None:
            return execution_event.cancel(status_message="No target object")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Continual Flame"
        )

        flame = materialize_spatial_effect(
            CONTINUAL_FLAME_FIELD_RECIPE,
            caster.uuid,
            position=position,
            faction=caster.faction,
            anchor_uuid=target.uuid,
            expected_type=FieldEffect,
        )
        controller = ContinualFlameController(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=flame.uuid,
            position=position,
            effect_origin=execution_event.to_effect_origin(),
        )
        flame.install_controller(controller, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"A permanent flame springs forth from {target.name}"
        )


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
        healing_dice=type_cast(DieSize, die_value),
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
        return self._validate_entity_target_in_range_and_sight(declaration_event)

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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        return self._validate_entity_target_in_range_and_sight(declaration_event)

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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        """Validate range and line of sight for every selected target."""
        return self._validate_entity_targets_in_range_and_sight(
            declaration_event,
            self.get_all_targets(),
        )

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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        """Validate range and line of sight for every selected target."""
        return self._validate_entity_targets_in_range_and_sight(
            declaration_event,
            self.get_all_targets(),
        )

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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
                target=self.end_position if self.end_position is not None else (0, 0),
                radius_feet=30
            )

    def get_all_targets(self) -> List[UUID]:
        """Override to cap at 6 targets from AoE."""
        targets = super().get_all_targets()
        return targets[:self.max_targets]

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        return self._validate_visible_position_in_range(declaration_event)

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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        return self._validate_entity_target_in_range_and_sight(declaration_event)

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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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
        """Validate range and line of sight for every selected target."""
        return self._validate_entity_targets_in_range_and_sight(
            declaration_event,
            self.get_all_targets(),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply healing from pool to current target (called per target by convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        if self.healing_pool_remaining <= 0:
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
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

        execution_event = declaration_event.with_updates(
            status_message=f"Divine Word affects {target.name}"
        )

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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Divine Word: {target.name} is {outcome}"
        )
