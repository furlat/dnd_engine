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

from pydantic import Field

from dnd.core.base_actions import TargetType, BaseAction, Cost, ActionCategory
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, ConditionTag, Duration, DurationType, HazardFilter
from dnd.core.values import ModifiableValue
from dnd.core.dice import AttackOutcome, RollType
from typing import cast as type_cast
from dnd.core.events import EventPhase, RangeType, Range, Damage, Healing, ForcedMovementEvent, EventType, EventHandler, Trigger, Event, SpatialChangeEvent, WeaponSlot, AbilityName
from dnd.core.modifiers import DamageType, AdvantageModifier, AdvantageStatus, CreatureType, NumericalModifier
from dnd.core.aoe import AoEShape, Sphere, Cone, Line, Cube, Cylinder
from dnd.core.gridmap import get_map
from dnd.blocks.equipment import ArmorType, Weapon as WeaponItem, Shield as ShieldItem

from dnd.entity import Entity, determine_attack_outcome
from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator, Attack
from dnd.conditions import Blinded, Deafened, Stunned, NoReactions, Concentrating, ConcentrationActionMarker, Restrained
from dnd.spells.spell_utils import fire_heal_roll_result


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

    if target_entity.uuid not in source_entity.senses.entities.keys():
        return declaration_event.cancel(status_message=f"Target entity not in line of sight for {declaration_event.name}")
    return declaration_event.phase_to(
        new_phase=EventPhase.EXECUTION,
        status_message=f"Validated line of sight for {declaration_event.name}"
    )


class FireBolt(SpellAction):
    """Fire Bolt - Evocation cantrip

    You hurl a mote of fire at a creature or object within range.
    Make a ranged spell attack. On hit, target takes 1d10 fire damage.
    Damage scales with caster level: 2d10 at 5th, 3d10 at 11th, 4d10 at 17th.
    """
    name: str = Field(default="Fire Bolt")
    description: str = Field(default="Hurl a mote of fire at a target")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120)
    )
    projectile_type: Optional[str] = Field(default="bolt")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""

        # Validate line of sight
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        # Validate range
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = source_entity.senses.get_feet_distance(target_entity.position)
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

        # 1. Calculate bonuses
        attack_bonus = caster.spell_attack_bonus(target.uuid)
        target_ac = target.ac_bonus(caster.uuid)

        # 2. Cross-propagate modifiers (same as Attack)
        attack_bonus.set_from_target(target_ac)
        target_ac.set_from_target(attack_bonus)

        # 3. Roll attack
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK, parent_event=execution_event.uuid)
        crit_threshold = caster.get_spell_crit_threshold()
        outcome = determine_attack_outcome(dice_roll, target_ac, crit_threshold)

        # 4. Clean up cross-propagation
        attack_bonus.reset_from_target()
        target_ac.reset_from_target()

        # Update event with attack info
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )

        # 5. On miss, complete without damage
        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} missed"
            )

        # 6. On hit: roll damage
        num_dice = self._get_cantrip_dice_count(self.caster_level)
        is_crit = outcome == AttackOutcome.CRIT

        # Create damage object (un-doubled; get_dice handles crit doubling)
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

        # Roll damage
        damage_dice = fire_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        # Apply damage
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
    name: str = "Ray of Frost Effect"
    description: str = "Tracking condition for Ray of Frost speed reduction"
    affected_target_uuid: Optional[UUID] = None  # The target whose speed is reduced

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.affected_target_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Affected target UUID not set")

        target = Entity.get(self.affected_target_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        # Apply -10 speed modifier to TARGET's movement
        # This modifier is tracked by this condition and cleaned up when it expires
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
    name: str = Field(default="Ray of Frost")
    description: str = Field(default="Ranged spell attack, 1d8 cold, target speed -10ft")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )
    projectile_type: Optional[str] = Field(default="ray")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.COLD, description="Primary damage type for VFX")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = source_entity.senses.get_feet_distance(target_entity.position)
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

        # 1. Calculate bonuses
        attack_bonus = caster.spell_attack_bonus(target.uuid)
        target_ac = target.ac_bonus(caster.uuid)

        # 2. Cross-propagate modifiers
        attack_bonus.set_from_target(target_ac)
        target_ac.set_from_target(attack_bonus)

        # 3. Roll attack
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK, parent_event=execution_event.uuid)
        crit_threshold = caster.get_spell_crit_threshold()
        outcome = determine_attack_outcome(dice_roll, target_ac, crit_threshold)

        # 4. Clean up
        attack_bonus.reset_from_target()
        target_ac.reset_from_target()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )

        # 5. On miss, complete without damage
        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} missed"
            )

        # 6. On hit: roll damage
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

        # Apply damage
        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.COLD,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        # 7. Apply speed reduction
        # The effect condition goes on CASTER with duration=1 round
        # This ensures it expires at the start of CASTER's next turn (SRD correct)
        # The condition tracks the speed modifier on the TARGET via modifiers_uuids
        effect_condition = RayOfFrostEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,  # Lives on caster
            affected_target_uuid=target.uuid,  # But affects target's speed
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
    name: str = Field(default="Sacred Flame")
    description: str = Field(default="Target must succeed on DEX save or take radiant damage")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )
    projectile_type: Optional[str] = Field(default="radiance")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Primary damage type for VFX")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""

        # Validate line of sight
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        # Validate range
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = source_entity.senses.get_feet_distance(target_entity.position)
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

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Request DEX save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        # Get save bonus for combat log
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

        # 3. On successful save: no damage
        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                total_damage=0,
                status_message=f"{self.name} - target saved"
            )

        # 4. On failed save: roll damage
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

        # Roll damage (no crit for save spells)
        damage_dice = radiant_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        # Apply damage (child of effect event)
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


class MagicMissile(SpellAction):
    """Magic Missile - 1st level Evocation

    You create three glowing darts of magical force. Each dart hits automatically
    and deals 1d4+1 force damage. When cast at higher levels, create one additional
    dart per slot level above 1st.

    Darts can be split among multiple targets or all sent to a single target.
    Uses MULTI_ENTITY target type with allow_same_target=True.
    """
    name: str = Field(default="Magic Missile")
    description: str = Field(default="Three darts of force that automatically hit")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)  # Multi-target!
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120)
    )

    # Multi-entity configuration
    allow_same_target: bool = Field(default=True)  # Can send multiple darts to same target
    valid_target_filter: str = Field(default="enemies")  # Only enemies
    projectile_type: Optional[str] = Field(default="dart")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FORCE, description="Primary damage type for VFX")

    def get_num_projectiles(self) -> int:
        """3 darts base + 1 per upcast level."""
        return 3 + self.get_upcast_bonus()

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

        # If fewer targets than darts, fill with primary
        num_darts = self.get_num_projectiles()
        while len(targets) < num_darts and self.target_entity_uuid:
            targets.append(self.target_entity_uuid)

        return targets[:num_darts]

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight for all targets."""

        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return declaration_event.cancel(status_message="Source entity not found")

        # Validate all targets are in range and LOS
        all_targets = self.get_all_targets()
        validated_targets = set()  # Only validate each unique target once

        for target_uuid in all_targets:
            if target_uuid in validated_targets:
                continue
            validated_targets.add(target_uuid)

            target_entity = Entity.get(target_uuid)
            if not target_entity:
                return declaration_event.cancel(status_message=f"Target entity not found")

            # Check LOS
            if target_uuid not in source_entity.senses.entities.keys():
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} not in line of sight"
                )

            # Check range
            distance = source_entity.senses.get_feet_distance(target_entity.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} out of range ({distance}ft > {self.effective_range}ft)"
                )

        # Call parent validation for MULTI_ENTITY checks (same-target, target filter)
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

        # Each dart deals 1d4+1 force damage
        dart_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=4,
            dice_numbers=1,
            damage_bonus=ModifiableValue.create(
                source_entity_uuid=caster.uuid,
                base_value=1,  # +1 per dart is intrinsic
                value_name="Magic Missile Dart"
            ),
            damage_type=DamageType.FORCE
        )

        # Roll damage (auto-hit, so use HIT outcome)
        damage_dice = dart_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        # Apply damage (child of execution event since no effect phase for auto-hit)
        actual_damage = target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.FORCE,
            source_entity_uuid=caster.uuid,
            parent_event=execution_event.uuid
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
    name: str = Field(default="Scorching Ray")
    description: str = Field(default="3 rays, each 2d6 fire, ranged spell attack per ray")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120)
    )

    # Multi-entity configuration
    allow_same_target: bool = Field(default=True)  # Can send multiple rays to same target
    valid_target_filter: str = Field(default="enemies")
    projectile_type: Optional[str] = Field(default="ray")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")

    def get_num_projectiles(self) -> int:
        """3 rays base + 1 per upcast level."""
        return 3 + self.get_upcast_bonus()

    def get_multi_target_count(self) -> Optional[int]:
        return self.get_num_projectiles()

    def get_all_targets(self) -> List[UUID]:
        """Return targets for each ray (can have repeats)."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)

        # If fewer targets than rays, fill with primary
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

            # Check LOS
            if target_uuid not in source_entity.senses.entities.keys():
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} not in line of sight"
                )

            # Check range
            distance = source_entity.senses.get_feet_distance(target_entity.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} out of range ({distance}ft > {self.effective_range}ft)"
                )

        # Call parent validation for MULTI_ENTITY checks
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply single ray to current target (called once per ray by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate bonuses
        attack_bonus = caster.spell_attack_bonus(target.uuid)
        target_ac = target.ac_bonus(caster.uuid)

        # 2. Cross-propagate modifiers
        attack_bonus.set_from_target(target_ac)
        target_ac.set_from_target(attack_bonus)

        # 3. Roll attack
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK, parent_event=execution_event.uuid)
        crit_threshold = caster.get_spell_crit_threshold()
        outcome = determine_attack_outcome(dice_roll, target_ac, crit_threshold)

        # 4. Clean up
        attack_bonus.reset_from_target()
        target_ac.reset_from_target()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            status_message=f"Ray attack: {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )

        # 5. On miss
        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                target_entity_name=target.name,
                total_damage=0,
                status_message=f"Ray misses {target.name}"
            )

        # 6. On hit: roll 2d6 fire damage
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

        # Apply damage (child of effect event)
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


class Fireball(SpellAction):
    """Fireball - 3rd level Evocation

    A bright streak flashes from your pointing finger to a point you choose
    within range and then blossoms with a low roar into an explosion of flame.

    Each creature in a 20-foot-radius sphere centered on that point must make
    a DEX saving throw. A target takes 8d6 fire damage on a failed save,
    or half as much on a successful one.

    At Higher Levels: +1d6 damage per slot level above 3rd.
    """
    name: str = Field(default="Fireball")
    description: str = Field(default="20ft radius explosion dealing 8d6 fire damage (DEX save half)")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150))
    projectile_type: Optional[str] = Field(default="orb")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")

    # AoE configuration - set via __init__ or field default
    aoe_shape: Optional[AoEShape] = Field(default=None)

    # Target filtering - DEFAULT: hits everyone including caster and allies
    include_self: bool = Field(default=True)  # Caster can be hit
    valid_target_filter: str = Field(default="all")  # Hits everyone in area

    # Damage configuration
    base_damage_dice: int = Field(default=8)  # 8d6 at level 3

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                radius_feet=20
            )

    def get_damage_dice_count(self) -> int:
        """8d6 base + 1d6 per level above 3rd."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        # Check LOS to target position (caster must see the center point)
        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(
                status_message=f"Target position {target_pos} not in line of sight"
            )

        # Check range
        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
            )

        # Let parent handle POSITION_AOE multi-target validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply fireball damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Request DEX save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        # Get save bonus for combat log
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

        # 3. Roll damage
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

        # 4. Half damage on successful save
        final_damage = damage_roll.total // 2 if success else damage_roll.total

        # 5. Apply damage (child of effect event)
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
            total_damage=final_damage,  # Required for convolution aggregation
            status_message=f"Fireball deals {final_damage} fire damage to {target.name}{save_text}"
        )


class BurningHands(SpellAction):
    """Burning Hands - 1st level Evocation

    As you hold your hands with thumbs touching and fingers spread, a thin sheet
    of flames shoots forth from your outstretched fingertips. Each creature in a
    15-foot cone must make a DEX save. A creature takes 3d6 fire damage on a
    failed save, or half as much on a successful one.

    At Higher Levels: +1d6 damage per slot level above 1st.
    """
    name: str = Field(default="Burning Hands")
    description: str = Field(default="15ft cone of fire dealing 3d6 fire damage (DEX save half)")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="evocation")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    # Target filtering - hits everyone by default
    include_self: bool = Field(default=False)  # Caster at apex NOT hit
    valid_target_filter: str = Field(default="all")

    # Damage configuration
    base_damage_dice: int = Field(default=3)  # 3d6 at level 1

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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate cone direction. Self-range means no LOS check to target position."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        # For SELF range, end_position is direction indicator, not target
        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified for cone")

        # Let parent handle POSITION_AOE multi-target validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply burning hands damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Request DEX save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        # Get save bonus for combat log
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

        # 3. Roll damage
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

        # 4. Half damage on successful save
        final_damage = damage_roll.total // 2 if success else damage_roll.total

        # 5. Apply damage (child of effect event)
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
    name: str = Field(default="Lightning Bolt")
    description: str = Field(default="100ft×5ft line dealing 8d6 lightning damage (DEX save half)")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="evocation")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.LIGHTNING, description="Primary damage type for VFX")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    # Target filtering
    include_self: bool = Field(default=False)  # Caster at origin NOT hit
    valid_target_filter: str = Field(default="all")

    # Damage configuration
    base_damage_dice: int = Field(default=8)  # 8d6 at level 3

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

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate line direction. Self-range means no LOS check to target position."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified for line")

        # Let parent handle POSITION_AOE multi-target validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply lightning bolt damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Request DEX save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        # Get save bonus for combat log
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

        # 3. Roll damage
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

        # 4. Half damage on successful save
        final_damage = damage_roll.total // 2 if success else damage_roll.total

        # 5. Apply damage (child of effect event)
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
    name: str = Field(default="Thunderwave")
    description: str = Field(default="15ft cube dealing 2d8 thunder + 10ft push on fail (CON save)")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="evocation")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.THUNDER, description="Primary damage type for VFX")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    # Target filtering
    include_self: bool = Field(default=False)  # Caster at origin NOT hit
    valid_target_filter: str = Field(default="all")

    # Damage configuration
    base_damage_dice: int = Field(default=2)  # 2d8 at level 1
    push_distance_feet: int = Field(default=10)  # Push 10ft on failed save

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

    def _get_push_direction(self, caster_pos: Tuple[int, int], target_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Calculate push direction - away from caster (radial)."""
        dx = target_pos[0] - caster_pos[0]
        dy = target_pos[1] - caster_pos[1]

        # Normalize to unit direction
        if dx != 0:
            dx = 1 if dx > 0 else -1
        if dy != 0:
            dy = 1 if dy > 0 else -1

        # If directly on caster (shouldn't happen with include_self=False), push in spell direction
        if dx == 0 and dy == 0:
            if self.end_position:
                dx = 1 if self.end_position[0] > caster_pos[0] else (-1 if self.end_position[0] < caster_pos[0] else 0)
                dy = 1 if self.end_position[1] > caster_pos[1] else (-1 if self.end_position[1] < caster_pos[1] else 0)
            if dx == 0 and dy == 0:
                dx = 1  # Default to east

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

            # Check if the forced movement can cross into the next tile.
            if not grid.can_transition(current_pos, next_pos, target_uuid):
                was_blocked = True
                blocked_by = grid.identify_blocker_at(next_pos, target_uuid)
                break

            # Check if occupied by another entity
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

        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified for cube")

        # Let parent handle POSITION_AOE multi-target validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply thunderwave damage and push to current target."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Request CON save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        # Get save bonus for combat log
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

        # 3. Roll damage
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

        # 4. Half damage on successful save, no push
        final_damage = damage_roll.total // 2 if success else damage_roll.total

        # 5. Apply damage (child of effect event)
        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.THUNDER,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

        # 6. Push on failed save only
        push_applied = False
        push_distance_actual = 0
        if not success:
            start_pos = target.senses.position
            push_dir = self._get_push_direction(caster.senses.position, start_pos)
            end_pos, push_distance_actual, was_blocked, blocked_by = self._calculate_push_destination(
                start_pos, push_dir, self.push_distance_feet, target.uuid
            )

            if end_pos != start_pos:
                # Fire forced movement event (child of effect event)
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
                # Move to completion
                forced_event.phase_to(EventPhase.COMPLETION)

                # Apply movement via Entity helper
                # Note: Senses updated reactively via SPATIAL events from GridMap.move_entity()
                Entity.update_entity_position(target, end_pos, parent_event=effect_event.uuid)
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
    name: str = Field(default="Shatter")
    description: str = Field(default="10ft radius sphere dealing 3d8 thunder damage (CON save half)")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    projectile_type: Optional[str] = Field(default="orb")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.THUNDER, description="Primary damage type for VFX")

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    # Target filtering
    include_self: bool = Field(default=True)  # Caster can be hit if in radius
    valid_target_filter: str = Field(default="all")

    # Damage configuration
    base_damage_dice: int = Field(default=3)  # 3d8 at level 2

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Sphere(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                radius_feet=10
            )

    def get_damage_dice_count(self) -> int:
        """3d8 base + 1d8 per level above 2nd."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        # Check LOS to target position (caster must see the center point)
        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(
                status_message=f"Target position {target_pos} not in line of sight"
            )

        # Check range
        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
            )

        # Let parent handle POSITION_AOE multi-target validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply shatter damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Request CON save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        # Get save bonus for combat log
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

        # 3. Roll damage
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

        # 4. Half damage on successful save
        final_damage = damage_roll.total // 2 if success else damage_roll.total

        # 5. Apply damage (child of effect event)
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
    name: str = Field(default="Circle of Death")
    description: str = Field(default="60ft radius sphere dealing 8d6 necrotic damage (CON save half)")
    spell_level: int = Field(default=6)
    spell_school: str = Field(default="necromancy")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150))
    projectile_type: Optional[str] = Field(default="orb")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.NECROTIC, description="Primary damage type for VFX")

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    # Target filtering - caster CAN be hit
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="all")

    # Damage configuration
    base_damage_dice: int = Field(default=8)  # 8d6 at level 6

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
        return self.base_damage_dice + (upcast_bonus * 2)  # +2d6 per level

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        # Check LOS to target position
        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(
                status_message=f"Target position {target_pos} not in line of sight"
            )

        # Check range
        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
            )

        # Let parent handle POSITION_AOE multi-target validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply circle of death damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Request CON save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        # Get save bonus for combat log
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

        # 3. Roll damage
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

        # 4. Half damage on successful save
        final_damage = damage_roll.total // 2 if success else damage_roll.total

        # 5. Apply damage (child of effect event)
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
    name: str = Field(default="Cone of Cold")
    description: str = Field(default="60ft cone dealing 8d8 cold damage (CON save half)")
    spell_level: int = Field(default=5)
    spell_school: str = Field(default="evocation")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.COLD, description="Primary damage type for VFX")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    # Target filtering - caster at apex NOT hit
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="all")

    # Damage configuration
    base_damage_dice: int = Field(default=8)  # 8d8 at level 5

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

        # Let parent handle POSITION_AOE multi-target validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply cone of cold damage to current target (called once per target by convolution)."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Request CON save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        # Get save bonus for combat log
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

        # 3. Roll damage
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

        # 4. Half damage on successful save
        final_damage = damage_roll.total // 2 if success else damage_roll.total

        # 5. Apply damage (child of effect event)
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
    name: str = "Sunburst Blindness"
    description: str = "Blinded by brilliant sunlight"

    caster_uuid: Optional[UUID] = None
    spell_dc: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        # Apply Blinded as sub-condition
        blinded = Blinded(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        sub_event = target.add_condition(blinded, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(blinded.uuid)

        # Register repeat save handler
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

            # Check if still affected
            sunburst_blind = target.active_conditions.get("Sunburst Blindness")
            if not sunburst_blind or sunburst_blind.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                # Caster gone, end the effect
                target.remove_condition("Sunburst Blindness", parent_event=event)
                return None

            # Repeat CON save
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if success:
                # Remove this condition (Blinded auto-removes as sub-condition)
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
    name: str = Field(default="Sunburst")
    description: str = Field(default="60ft sphere, 12d6 radiant, CON save or blinded")
    spell_level: int = Field(default=8)
    spell_school: str = Field(default="evocation")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Primary damage type for VFX")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150))

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    # Target filtering
    include_self: bool = Field(default=True)  # Caster can be hit
    valid_target_filter: str = Field(default="all")  # Hits everyone

    # Damage configuration
    base_damage_dice: int = Field(default=12)  # 12d6

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

        distance = caster.senses.get_feet_distance(target_pos)
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

        dc = caster.spell_save_dc()

        # Check for disadvantage (undead or ooze)
        has_disadvantage = target.creature_type in [CreatureType.UNDEAD, CreatureType.OOZE]

        # Add temporary disadvantage modifier if applicable
        mod_uuid: Optional[UUID] = None
        if has_disadvantage:
            disadv_mod = AdvantageModifier(
                name="Sunburst (Undead/Ooze)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            mod_uuid = target.saving_throws.get_saving_throw("constitution").bonus.self_static.add_advantage_modifier(disadv_mod)

        # CON save request (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        # Remove temporary disadvantage modifier
        if has_disadvantage and mod_uuid:
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

        # Roll damage
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

        # Half damage on save
        final_damage = damage_roll.total // 2 if success else damage_roll.total

        # Apply damage (child of effect event)
        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.RADIANT,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

        # On FAILED save: apply blindness with repeat saves
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

    # Heavy armor is always metal
    if body_armor.type == ArmorType.HEAVY:
        return True

    # Check medium armor names for metal types
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
    name: str = Field(default="Shocking Grasp")
    description: str = Field(default="Melee spell attack, 1d8 lightning, advantage vs metal armor, no reactions")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5)
    )
    projectile_type: Optional[str] = Field(default="touch")
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

        # Melee range check (5 feet)
        distance = source_entity.senses.get_feet_distance(target_entity.position)
        if distance > 5:
            return declaration_event.cancel(
                status_message=f"Target out of melee range ({distance}ft > 5ft)"
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

        # 1. Calculate bonuses
        attack_bonus = caster.spell_attack_bonus(target.uuid)
        target_ac = target.ac_bonus(caster.uuid)

        # 2. Check for metal armor advantage
        has_metal_armor = _is_wearing_metal_armor(target)
        metal_adv_uuid: Optional[UUID] = None
        if has_metal_armor:
            metal_adv = AdvantageModifier(
                name="Shocking Grasp (Metal Armor)",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            metal_adv_uuid = attack_bonus.self_static.add_advantage_modifier(metal_adv)

        # 3. Cross-propagate modifiers
        attack_bonus.set_from_target(target_ac)
        target_ac.set_from_target(attack_bonus)

        # 4. Roll attack
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK, parent_event=execution_event.uuid)
        crit_threshold = caster.get_spell_crit_threshold()
        outcome = determine_attack_outcome(dice_roll, target_ac, crit_threshold)

        # 5. Clean up
        attack_bonus.reset_from_target()
        target_ac.reset_from_target()
        if metal_adv_uuid:
            attack_bonus.self_static.remove_modifier(metal_adv_uuid)

        metal_text = " (advantage: metal armor)" if has_metal_armor else ""
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}{metal_text}: {outcome.value}"
        )

        # 6. On miss
        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} missed"
            )

        # 7. On hit: roll damage
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

        # Apply damage (child of effect event)
        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.LIGHTNING,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        # 8. Apply No Reactions condition (1 round duration - until start of target's next turn)
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
    name: str = "Guiding Bolt"
    description: str = "Next attack against this creature has advantage"

    # Track caster for duration
    caster_uuid: Optional[UUID] = None

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity not found")

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        # Add advantage to attacks against this target (to_target_static)
        adv_uuid = target.equipment.ac_bonus.to_target_static.add_advantage_modifier(
            AdvantageModifier(
                name="Guiding Bolt",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.source_entity_uuid
            )
        )
        outs.append((target.equipment.ac_bonus.uuid, adv_uuid))

        # Register handler to remove on first attack against target
        handler = self._create_remove_on_attack_handler()
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

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
            # Only trigger for attacks against this target
            if event.target_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            # Check if still marked by this specific Guiding Bolt
            guiding_mark = target.active_conditions.get("Guiding Bolt")
            if not guiding_mark or guiding_mark.uuid != effect_uuid:
                return None

            # Remove the condition (advantage was already applied via to_target_static)
            target.remove_condition("Guiding Bolt", parent_event=event)
            return None

        return EventHandler(
            name=f"Guiding Bolt Remove ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EFFECT  # After hit/miss determined, before damage
                )
            ],
            event_processor=remove_on_attack_processor
        )


class GuidingBolt(SpellAction):
    """Guiding Bolt - 1st level Evocation

    A flash of light streaks toward a creature of your choice within range.
    Make a ranged spell attack against the target. On a hit, the target takes
    4d6 radiant damage, and the next attack roll made against this target
    before the end of your next turn has advantage.

    At Higher Levels: +1d6 damage per slot level above 1st.
    """
    name: str = Field(default="Guiding Bolt")
    description: str = Field(default="Ranged spell attack, 4d6 radiant, next attack has advantage")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120)
    )
    projectile_type: Optional[str] = Field(default="bolt")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Primary damage type for VFX")

    # Damage configuration
    base_damage_dice: int = Field(default=4)  # 4d6 at level 1

    def get_damage_dice_count(self) -> int:
        """4d6 base + 1d6 per level above 1st."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = source_entity.senses.get_feet_distance(target_entity.position)
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

        # 1. Calculate bonuses
        attack_bonus = caster.spell_attack_bonus(target.uuid)
        target_ac = target.ac_bonus(caster.uuid)

        # 2. Cross-propagate modifiers
        attack_bonus.set_from_target(target_ac)
        target_ac.set_from_target(attack_bonus)

        # 3. Roll attack
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK, parent_event=execution_event.uuid)
        crit_threshold = caster.get_spell_crit_threshold()
        outcome = determine_attack_outcome(dice_roll, target_ac, crit_threshold)

        # 4. Clean up
        attack_bonus.reset_from_target()
        target_ac.reset_from_target()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )

        # 5. On miss
        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} missed"
            )

        # 6. On hit: roll damage
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

        # Apply damage (child of effect event)
        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.RADIANT,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        # 7. Apply Guiding Bolt mark (advantage on next attack)
        # Duration: Until next attack against target OR "until the end of your next turn"
        # We use 2 rounds to cover "end of your next turn" - the handler removes on first attack
        guiding_mark = GuidingBoltMarked(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            duration=Duration(
                duration=2,  # End of caster's next turn
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid  # Expires relative to caster
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
    name: str = Field(default="Eldritch Blast")
    description: str = Field(default="A beam of crackling force energy")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120)
    )
    projectile_type: Optional[str] = Field(default="beam")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FORCE, description="Primary damage type for VFX")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = source_entity.senses.get_feet_distance(target_entity.position)
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

        # 1. Calculate bonuses
        attack_bonus = caster.spell_attack_bonus(target.uuid)
        target_ac = target.ac_bonus(caster.uuid)

        # 2. Cross-propagate modifiers
        attack_bonus.set_from_target(target_ac)
        target_ac.set_from_target(attack_bonus)

        # 3. Roll attack
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK, parent_event=execution_event.uuid)
        crit_threshold = caster.get_spell_crit_threshold()
        outcome = determine_attack_outcome(dice_roll, target_ac, crit_threshold)

        # 4. Clean up cross-propagation
        attack_bonus.reset_from_target()
        target_ac.reset_from_target()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            attack_bonus=attack_bonus,
            ac=target_ac,
            dice_roll=dice_roll,
            attack_outcome=outcome,
            status_message=f"Attack rolled {dice_roll.total} vs AC {target_ac.normalized_score}: {outcome.value}"
        )

        # 5. On miss, complete without damage
        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} missed"
            )

        # 6. On hit: roll damage
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


# =============================================================================
# Gust of Wind (Level 2, Evocation, Concentration)
# =============================================================================

from dnd.tile_conditions import ZoneControlCondition


class GustOfWindZone(ZoneControlCondition):
    """Zone for Gust of Wind - 60ft line of wind that pushes creatures."""
    name: str = "Gust of Wind Zone"
    description: str = "Strong wind pushes creatures and costs extra movement"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    zone_shape: str = Field(default="line")
    zone_radius_feet: int = Field(default=60)
    adds_difficult_terrain: bool = Field(default=True)

    marker_name: Optional[str] = Field(default="Gust of Wind")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL)

    spell_dc: int = Field(default=10)
    caster_position: Tuple[int, int] = Field(default=(0, 0))

    def _compute_affected_positions(self) -> Set[Tuple[int, int]]:
        """Compute line from caster in the chosen direction."""
        if not self.zone_direction:
            return {self.zone_center}
        dx, dy = self.zone_direction
        length_tiles = self.zone_radius_feet // 5  # 60ft / 5 = 12 tiles
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

    def _has_entry_effect(self) -> bool:
        return True

    def _has_turn_start_effect(self) -> bool:
        return True

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

            _apply_gust_push(entity, dc, caster_pos, source_uuid, event)
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

            _apply_gust_push(entity, dc, caster_pos, source_uuid, event)
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


def _apply_gust_push(entity: Entity, dc: int, caster_pos: Tuple[int, int],
                      source_uuid: UUID, parent_event: Event) -> None:
    """STR save or pushed 15ft away from caster."""
    save_request = entity.create_saving_throw_request(
        target_entity_uuid=entity.uuid,
        ability_name="strength",
        dc=dc,
        parent_event=parent_event.uuid
    )
    _, _, success = entity.saving_throw(save_request)
    if success:
        return

    # Push 3 tiles (15ft) away from caster
    entity_pos = entity.senses.position
    dx = entity_pos[0] - caster_pos[0]
    dy = entity_pos[1] - caster_pos[1]
    length = max(abs(dx), abs(dy), 1)
    push_dx = round(dx / length) if dx != 0 else 0
    push_dy = round(dy / length) if dy != 0 else 0
    if push_dx == 0 and push_dy == 0:
        push_dx = 1  # Default push direction

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
            parent_event=parent_event.uuid
        )
        forced_event.phase_to(EventPhase.COMPLETION)
        Entity.update_entity_position(entity, current_pos, parent_event=parent_event.uuid)


class GustOfWind(SpellAction):
    """Gust of Wind - 2nd level Evocation (Concentration)

    A line of strong wind 60ft long and 10ft wide blasts from you.
    STR save or pushed 15ft away. Difficult terrain toward caster.
    """
    name: str = Field(default="Gust of Wind")
    description: str = Field(default="60ft line of wind, STR save or pushed 15ft, difficult terrain")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="evocation")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    aoe_shape: Optional[AoEShape] = Field(default=None)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="all")

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

        dc = caster.spell_save_dc()

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

    def _finalize_aoe(self, effect_event: Any) -> None:
        """Create persistent zone after convolution completes."""
        self._setup_zone(effect_event)

    def _setup_zone(self, parent_event: Any) -> None:
        """Set up the persistent zone condition after initial push."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return

        dc = caster.spell_save_dc()
        target_pos = self.end_position or (caster.senses.position[0] + 1, caster.senses.position[1])

        # Compute direction for zone
        dx = target_pos[0] - caster.senses.position[0]
        dy = target_pos[1] - caster.senses.position[1]
        length = max(abs(dx), abs(dy), 1)
        direction = (round(dx / length), round(dy / length))

        zone = GustOfWindZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=caster.senses.position,
            zone_direction=direction,
            spell_dc=dc,
            caster_position=caster.senses.position
        )
        caster.add_condition(zone, parent_event=parent_event)

        concentration = self.ensure_concentration(parent_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)


# =============================================================================
# Ice Storm (Level 4, Evocation, NOT concentration)
# =============================================================================

class IceStormTerrain(ZoneControlCondition):
    """Temporary difficult terrain from Ice Storm. Lasts 1 round."""
    name: str = "Ice Storm Terrain"
    description: str = "Ground covered in ice - difficult terrain"

    zone_shape: str = Field(default="sphere")
    zone_radius_feet: int = Field(default=20)
    adds_difficult_terrain: bool = Field(default=True)

    marker_name: Optional[str] = Field(default="Ice Storm")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL)


class IceStorm(SpellAction):
    """Ice Storm - 4th level Evocation

    Hail pounds a 20ft-radius, 40ft-high cylinder. DEX save or
    2d8 bludgeoning + 4d6 cold (half on save). Ground becomes difficult terrain for 1 round.

    At Higher Levels: +1d8 bludgeoning per level above 4th.
    """
    name: str = Field(default="Ice Storm")
    description: str = Field(default="20ft cylinder: 2d8 bludg + 4d6 cold (DEX half), difficult terrain 1 round")
    spell_level: int = Field(default=4)
    spell_school: str = Field(default="evocation")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    projectile_type: Optional[str] = Field(default="rain")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.BLUDGEONING, description="Primary damage type for VFX")

    aoe_shape: Optional[AoEShape] = Field(default=None)
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="all")

    base_bludg_dice: int = Field(default=2)
    cold_dice: int = Field(default=4)

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

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Per-target: DEX save, bludgeoning + cold damage."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()
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

        # 2d8 bludgeoning (+ upcast) + 4d6 cold
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
        if success:
            total = total // 2

        target.receive_damage(
            amount=total,
            damage_type=DamageType.COLD,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[bludg_damage, cold_damage],
            damage_rolls=[bludg_roll, cold_roll],
            total_damage=total,
            status_message=f"Ice Storm deals {total} damage to {target.name}"
        )

    def _finalize_aoe(self, effect_event: Any) -> None:
        """Apply difficult terrain zone after convolution completes."""
        self._setup_terrain()

    def _setup_terrain(self) -> None:
        """Apply 1-round difficult terrain at the target area."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return

        target_pos = self.end_position
        if not target_pos:
            return

        terrain = IceStormTerrain(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos
        )
        terrain.duration.duration_type = DurationType.ROUNDS
        terrain.duration.duration = 1
        caster.add_condition(terrain)


# =============================================================================
# Sunbeam (Level 6, Evocation, Concentration)
# =============================================================================

class SunbeamStrike(BaseAction):
    """Action granted by Sunbeam to fire a beam of radiant light each turn."""
    name: str = Field(default="Sunbeam Strike")
    description: str = Field(default="Fire a beam of brilliant light - 60ft line")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY)
    aoe_shape: Optional[AoEShape] = Field(default=None)
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Sunbeam Strike", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])
    spell_dc: int = Field(default=10)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="all")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Line(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                length_feet=60,
                width_feet=5
            )

    def _create_event(self) -> Event:
        return Event(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            event_type=EventType.CAST_SPELL,
            phase=EventPhase.DECLARATION
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

        if not self.end_position:
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
            ability_name="constitution",
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

        # Blinded on failed save (1 round)
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
    name: str = Field(default="Sunbeam")
    description: str = Field(default="60ft line beam, 6d8 radiant + Blinded (CON half), repeatable")
    spell_level: int = Field(default=6)
    spell_school: str = Field(default="evocation")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Primary damage type for VFX")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.SELF)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        dc = caster.spell_save_dc()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Sunbeam"
        )

        # Register Sunbeam Strike action
        strike = SunbeamStrike(
            source_entity_uuid=caster.uuid,
            spell_dc=dc,
            template=True
        )
        caster.register_action(strike)

        # Apply Concentrating + marker condition for action cleanup
        concentration = self.ensure_concentration(effect_event)
        marker = ConcentrationActionMarker(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            action_name=strike.name
        )
        caster.add_condition(marker, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, marker.uuid)

        # Fire the first beam immediately on cast (D&D 5e: beam flashes on cast)
        if self.end_position:
            first_strike = SunbeamStrike(
                source_entity_uuid=caster.uuid,
                end_position=self.end_position,
                spell_dc=dc,
                template=False,
                costs=[],  # No additional cost — already paid by casting Sunbeam
            )
            first_strike.apply()

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} channels Sunbeam - can fire a beam each turn"
        )


# =============================================================================
# CHAIN LIGHTNING
# =============================================================================

class ChainLightning(SpellAction):
    """Chain Lightning - 6th level Evocation

    You create a bolt of lightning that arcs toward a target of your choice
    within range. Three bolts then leap from that target to up to three other
    targets within 30 feet. Each target makes a DEX save, taking 10d8 lightning
    on failure or half on success.

    At Higher Levels: +1 additional secondary target per slot level above 6th.
    """
    name: str = Field(default="Chain Lightning")
    description: str = Field(default="10d8 lightning to primary + up to 3 secondaries (DEX half)")
    spell_level: int = Field(default=6)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=150))
    valid_target_filter: str = Field(default="enemies")
    projectile_type: Optional[str] = Field(default="bolt")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.LIGHTNING, description="Primary damage type for VFX")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        result = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        return type_cast(Optional[SpellEvent], result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()
        upcast_bonus = self.get_upcast_bonus()
        max_secondaries = 3 + upcast_bonus
        base_dice = 10 + upcast_bonus
        damage_bonus = caster.get_spell_damage_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity", save_dc=dc,
            status_message=f"{caster.name} casts Chain Lightning"
        )

        # Build chain: primary + secondaries within 30ft of any chain member
        chain_targets = [target]
        chain_positions: Set[Tuple[int, int]] = {target.position}
        chain_uuids = {target.uuid}

        # Find all visible enemies as entities
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
                # Distance to nearest chain member
                for chain_pos in chain_positions:
                    dist = enemy.senses.get_feet_distance(chain_pos)
                    if dist <= 30 and dist < best_distance:
                        best_distance = dist
                        best_candidate = enemy

            if best_candidate is None:
                break
            chain_targets.append(best_candidate)
            chain_positions.add(best_candidate.position)
            chain_uuids.add(best_candidate.uuid)

        # Apply damage to each target
        total_damage = 0
        all_damages: List[Damage] = []
        all_rolls = []
        for chain_target in chain_targets:
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=chain_target.uuid,
                ability_name="dexterity", dc=dc,
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


# =============================================================================
# PRISMATIC SPRAY
# =============================================================================

class PrismaticRestrained(BaseCondition):
    """Prismatic Spray Indigo effect - Restrained with repeat CON save at turn end."""
    name: str = "Prismatic Restrained"
    description: str = "Restrained by prismatic energy, CON save to end"
    caster_uuid: Optional[UUID] = None
    spell_dc: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_conditions_uuids: List[UUID] = []

        # Apply Restrained as sub-condition
        restrained = Restrained(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(restrained, parent_event=declaration_event)
        sub_conditions_uuids.append(restrained.uuid)

        # Register repeat CON save handler
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
    name: str = Field(default="Prismatic Spray")
    description: str = Field(default="60ft cone, random color effect per target")
    spell_level: int = Field(default=7)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    aoe_shape: Optional[AoEShape] = Field(default=None)
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="all")

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
        # Colors 1-5: damage types with DEX save for half (except 4 = CON)
        color_damage: dict[int, DamageType] = {
            1: DamageType.FIRE,       # Red
            2: DamageType.ACID,       # Orange
            3: DamageType.LIGHTNING,  # Yellow
            4: DamageType.POISON,     # Green
            5: DamageType.COLD,       # Blue
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
            # Indigo: CON save or Restrained with repeat save
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
            # Violet: WIS save or Blinded
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

        dc = caster.spell_save_dc()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_dc=dc,
            status_message=f"Prismatic ray strikes {target.name}"
        )

        # Roll color (d8)
        color_roll = random.randint(1, 8)
        if color_roll == 8:
            # Roll twice, apply both effects
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

    Delegates to Attack.attack_consequences with override_ability.
    Temporarily adds cantrip radiant dice as extra attack damage.

    Register two variants per caster: TrueStrike(Melee) and TrueStrike(Ranged)
    using weapon_slot field. Each variant uses the weapon's range for targeting.
    """
    name: str = Field(default="True Strike")
    description: str = Field(default="Weapon attack using spellcasting ability, +radiant damage at higher levels")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5)
    )

    # Which weapon slot this variant uses
    weapon_slot: WeaponSlot = Field(default=WeaponSlot.MELEE_MAIN)

    # Target filtering
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="enemies")

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

        # Temporarily add cantrip radiant bonus dice to equipment
        extra_dice = self._get_cantrip_dice_count(self.caster_level) - 1
        if extra_dice > 0:
            eq = caster.equipment
            eq.extra_attack_damage_dices.append(6)
            eq.extra_attack_damage_dices_numbers.append(extra_dice)
            eq.extra_attack_damage_bonus.append(ModifiableValue(name="True Strike Radiant Bonus", source_entity_uuid=caster.uuid))
            eq.extra_attack_damage_type.append(DamageType.RADIANT)

        try:
            attack = Attack(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                weapon_slot=self.weapon_slot,
                override_ability=ability_name,
                costs=[],  # Already paid by spell action cost
                template=False
            )
            attack_result = attack.apply(parent_event=execution_event)
        finally:
            # Remove the temporary radiant bonus
            if extra_dice > 0:
                eq = caster.equipment
                eq.extra_attack_damage_dices.pop()
                eq.extra_attack_damage_dices_numbers.pop()
                eq.extra_attack_damage_bonus.pop()
                eq.extra_attack_damage_type.pop()

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


# =============================================================================
# Flame Strike (Level 5, Evocation, NOT concentration)
# =============================================================================

class FlameStrike(SpellAction):
    """Flame Strike - 5th level Evocation

    A vertical column of divine fire roars down from the heavens.
    10ft-radius, 40ft-high cylinder, 60ft range.
    4d6 fire + 4d6 radiant damage, DEX save for half.

    At Higher Levels: +1d6 fire per level above 5th.
    """
    name: str = Field(default="Flame Strike")
    description: str = Field(default="10ft cylinder: 4d6 fire + 4d6 radiant (DEX half)")
    spell_level: int = Field(default=5)
    spell_school: str = Field(default="evocation")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    projectile_type: Optional[str] = Field(default="radiance")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")

    aoe_shape: Optional[AoEShape] = Field(default=None)
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="all")

    base_fire_dice: int = Field(default=4)
    radiant_dice: int = Field(default=4)

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

        dc = caster.spell_save_dc()
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

        # 4d6 fire (+ upcast) + 4d6 radiant
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
        if success:
            total = total // 2

        target.receive_damage(
            amount=total,
            damage_type=DamageType.FIRE,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[fire_damage, radiant_damage],
            damage_rolls=[fire_roll, radiant_roll],
            total_damage=total,
            status_message=f"Flame Strike deals {total} damage to {target.name}"
        )


# =============================================================================
# Light (Cantrip, Evocation, Concentration)
# =============================================================================

class LightEffect(BaseCondition):
    """Light spell effect — emits bright light in 20ft and dim light in additional 20ft."""
    name: str = "Light"
    description: str = "Object sheds bright light in a 20-foot radius and dim light for an additional 20 feet"
    light_source_uuid: Optional[UUID] = None

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
            anchor_uuid=target.uuid
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Light shines from {target.name}"
        )
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        if self.light_source_uuid:
            grid = get_map()
            grid.remove_light_source(self.light_source_uuid)
            self.light_source_uuid = None
        return super()._remove(event)


class Light(SpellAction):
    """Light - Evocation Cantrip (Concentration)

    You touch one object. For the duration, the object sheds bright light
    in a 20-foot radius and dim light for an additional 20 feet.

    Duration: Concentration, up to 1 hour (10 rounds in combat).
    """
    name: str = Field(default="Light")
    description: str = Field(default="Touch: object sheds 20ft bright + 20ft dim light (concentration)")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="evocation")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))
    valid_target_filter: str = Field(default="self_or_allies")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        # Default to self if no target
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

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Light shines from {target.name}"
        )


# =============================================================================
# Continual Flame (Level 2, Evocation, NOT concentration)
# =============================================================================

class ContinualFlameObject(BaseBlock):
    """A heatless flame that emits light. Cannot be extinguished by normal means.

    Placed on the grid as an object. Emits bright light in 20ft and dim light
    for an additional 20ft. Permanent until dispelled.
    """
    name: str = "Continual Flame"
    flame_light_source_uuid: Optional[UUID] = None
    flame_position: Optional[Tuple[int, int]] = None

    def setup_light(self, position: Tuple[int, int]) -> None:
        """Create light source at position, anchored to self."""
        self.flame_position = position
        grid = get_map()
        grid.place_object(self.uuid, position)
        self.flame_light_source_uuid = grid.add_light_source(
            position=position,
            bright_radius_feet=20,
            dim_radius_feet=20,
            anchor_uuid=self.uuid
        )

    def destroy(self) -> None:
        """Remove flame and its light source."""
        if self.flame_light_source_uuid:
            grid = get_map()
            grid.remove_light_source(self.flame_light_source_uuid)
            self.flame_light_source_uuid = None
        if self.flame_position:
            grid = get_map()
            grid.remove_object(self.uuid)
            self.flame_position = None


class ContinualFlame(SpellAction):
    """Continual Flame - 2nd level Evocation (NOT concentration)

    A flame, equivalent in brightness to a torch, springs forth from an object
    that you touch. The flame emits no heat and doesn't use oxygen. A continual
    flame can be covered or hidden but not smothered or quenched.

    The flame sheds bright light in a 20-foot radius and dim light for an
    additional 20 feet. Permanent until dispelled.
    """
    name: str = Field(default="Continual Flame")
    description: str = Field(default="Touch: permanent 20ft bright + 20ft dim light on object")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="evocation")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.POSITION)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not self.end_position:
            return declaration_event.cancel(status_message="No target position")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        position = self.end_position
        if not position:
            return execution_event.cancel(status_message="No target position")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Continual Flame"
        )

        flame = ContinualFlameObject(
            source_entity_uuid=caster.uuid
        )
        flame.setup_light(position)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"A permanent flame springs forth at {position}"
        )


# =============================================================================
# Healing Spells
# =============================================================================


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
        healing_dice=die_value,  # type: ignore[arg-type]
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
    name: str = Field(default="Cure Wounds")
    description: str = Field(default="Touch a creature to restore 1d8 + modifier HP")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5)
    )
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid != caster.uuid:
            distance = caster.senses.get_feet_distance(target.position)
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
    name: str = Field(default="Healing Word")
    description: str = Field(default="Bonus action: heal a creature for 1d4 + modifier HP at 60ft")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    # Bonus action cost
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Healing Word Cost", cost_type="bonus_actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ])

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid != caster.uuid:
            distance = caster.senses.get_feet_distance(target.position)
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
    name: str = Field(default="Prayer of Healing")
    description: str = Field(default="Heal up to 6 allies for 2d8 + modifier HP")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30)
    )
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")
    allow_same_target: bool = Field(default=False)

    def get_multi_target_count(self) -> Optional[int]:
        return 6

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        # Validate all targets in range and LOS
        all_targets = self.get_all_targets()
        for target_uuid in set(all_targets):
            target = Entity.get(target_uuid)
            if not target:
                return declaration_event.cancel(status_message="Target not found")
            if target_uuid not in caster.senses.entities and target_uuid != caster.uuid:
                return declaration_event.cancel(
                    status_message=f"{target.name} not in line of sight"
                )
            distance = caster.senses.get_feet_distance(target.position)
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
    name: str = Field(default="Mass Healing Word")
    description: str = Field(default="Bonus action: heal up to 6 allies for 1d4 + modifier HP")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")
    allow_same_target: bool = Field(default=False)

    # Bonus action cost
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Mass Healing Word Cost", cost_type="bonus_actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ])

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
            if target_uuid not in caster.senses.entities and target_uuid != caster.uuid:
                return declaration_event.cancel(
                    status_message=f"{target.name} not in line of sight"
                )
            distance = caster.senses.get_feet_distance(target.position)
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

        num_dice = 1 + max(0, self.cast_at_level - 3)  # 1d4 at L3, 2d4 at L4, etc.
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
    name: str = Field(default="Mass Cure Wounds")
    description: str = Field(default="AoE heal up to 6 allies in 30ft sphere for 3d8 + modifier HP")
    spell_level: int = Field(default=5)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    aoe_shape: Optional[AoEShape] = Field(default=None)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    # Cap at 6 targets
    max_targets: int = Field(default=6)

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

        distance = caster.senses.get_feet_distance(target_pos)
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

        num_dice = self.cast_at_level - 2  # 3d8 at L5, 4d8 at L6, etc.
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
    name: str = Field(default="Heal")
    description: str = Field(default="Restore 70 HP and remove blindness/deafness")
    spell_level: int = Field(default=6)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid != caster.uuid:
            distance = caster.senses.get_feet_distance(target.position)
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

        # 70 HP base + 10 per upcast level
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

        # Remove Blinded and Deafened conditions
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
    name: str = Field(default="Mass Heal")
    description: str = Field(default="Distribute 700 HP of healing among visible allies, remove blindness/deafness")
    spell_level: int = Field(default=9)
    spell_school: str = Field(default="evocation")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")
    allow_same_target: bool = Field(default=False)

    # Track remaining pool across convolution loop
    healing_pool_remaining: int = Field(default=700)

    def get_multi_target_count(self) -> Optional[int]:
        return 20  # Effectively unlimited — "any number of creatures"

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        all_targets = self.get_all_targets()
        for target_uuid in set(all_targets):
            target = Entity.get(target_uuid)
            if not target:
                return declaration_event.cancel(status_message="Target not found")
            if target_uuid not in caster.senses.entities and target_uuid != caster.uuid:
                return declaration_event.cancel(
                    status_message=f"{target.name} not in line of sight"
                )
            distance = caster.senses.get_feet_distance(target.position)
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
                new_phase=EventPhase.COMPLETION,
                total_damage=0,
                target_entity_name=target.name,
                status_message=f"Mass Heal pool exhausted for {target.name}"
            )

        # Heal up to remaining pool, capped at target's missing HP
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

        # Remove Blinded and Deafened conditions
        if "Blinded" in target.active_conditions:
            target.remove_condition("Blinded", parent_event=effect_event)
        if "Deafened" in target.active_conditions:
            target.remove_condition("Deafened", parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Mass Heal heals {target.name} for {actual} HP"
        )


# =============================================================================
# Divine Word (L7) - HP-threshold effects, bonus action
# =============================================================================

class DivineWordEffect(BaseCondition):
    """Divine Word effect — applies tier-based conditions with duration handler for auto-removal."""
    name: str = "Divine Word"
    description: str = "Affected by Divine Word"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    duration_rounds: int = 10  # Default, overridden per tier

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_conditions_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        execution_event = declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Divine Word affects {target.name}"
        )

        current_hp = target.get_hp()

        if current_hp <= 20:
            # Instant kill (massive damage)
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
            # Blinded + Deafened + Stunned, 1 hour (600 rounds)
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
            # Blinded + Deafened, 10 min (100 rounds)
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
            # Deafened, 1 min (10 rounds)
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
            # >50 HP: no effect
            return [], [], [], [], execution_event.phase_to(
                EventPhase.EFFECT,
                status_message=f"Divine Word has no effect on {target.name} (HP > 50)"
            )

        # Duration handler for non-lethal tiers
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
        rounds_remaining = [self.duration_rounds]  # Mutable container for closure

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
    name: str = Field(default="Divine Word")
    description: str = Field(default="HP-threshold effects: deafen/blind/stun/kill")
    spell_level: int = Field(default=7)
    spell_school: str = Field(default="evocation")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))
    valid_target_filter: str = Field(default="enemies")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Divine Word Cost", cost_type="bonus_actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ])

    def get_num_projectiles(self) -> int:
        return 6  # Reasonable cap

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

        # Apply the condition (handles all HP tiers internally)
        condition = DivineWordEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        )
        target.add_condition(condition, parent_event=effect_event)

        # Determine outcome text
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
