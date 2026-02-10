"""Evocation spells - dealing damage and channeling energy.

Contains: FireBolt, SacredFlame, MagicMissile, Fireball, BurningHands,
          LightningBolt, Thunderwave, Shatter, Sunburst, RayOfFrost, ScorchingRay,
          ShockingGrasp, GuidingBolt
"""
from typing import Any, Optional, List, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import BaseCondition, Duration, DurationType
from dnd.core.values import ModifiableValue
from dnd.core.dice import AttackOutcome, RollType
from typing import cast as type_cast
from dnd.core.events import EventPhase, RangeType, Range, Damage, ForcedMovementEvent, EventType, EventHandler, Trigger, Event
from dnd.core.modifiers import DamageType, AdvantageModifier, AdvantageStatus, CreatureType, NumericalModifier
from dnd.core.aoe import AoEShape, Sphere, Cone, Line, Cube
from dnd.core.gridmap import get_map
from dnd.blocks.equipment import ArmorType

from dnd.entity import Entity, determine_attack_outcome
from dnd.actions import SpellAction, SpellEvent
from dnd.conditions import Blinded, NoReactions


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
        new_phase=EventPhase.DECLARATION,
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
        if distance > self.spell_range.normal:
            return declaration_event.cancel(status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)")

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
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK)
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

        # Extra crit dice
        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0
        total_dice = num_dice * (2 if is_crit else 1) + crit_extra

        # Create damage object
        damage_bonus = caster.get_spell_damage_bonus()
        fire_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=10,
            dice_numbers=total_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FIRE
        )

        # Roll damage
        damage_dice = fire_damage.get_dice(attack_outcome=outcome)
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
        if distance > self.spell_range.normal:
            return declaration_event.cancel(status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)")

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
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK)
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
        total_dice = num_dice * (2 if is_crit else 1) + crit_extra

        damage_bonus = caster.get_spell_damage_bonus()
        cold_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=total_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.COLD
        )

        damage_dice = cold_damage.get_dice(attack_outcome=outcome)
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
        if distance > self.spell_range.normal:
            return declaration_event.cancel(status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)")

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

    def get_num_projectiles(self) -> int:
        """3 darts base + 1 per upcast level."""
        return 3 + self.get_upcast_bonus()

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
            if distance > self.spell_range.normal:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} out of range ({distance}ft > {self.spell_range.normal}ft)"
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
        target.receive_damage(
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
            total_damage=damage_roll.total,
            status_message=f"Dart hits {target.name} for {damage_roll.total} force damage"
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

    def get_num_projectiles(self) -> int:
        """3 rays base + 1 per upcast level."""
        return 3 + self.get_upcast_bonus()

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
            if distance > self.spell_range.normal:
                return declaration_event.cancel(
                    status_message=f"{target_entity.name} out of range ({distance}ft > {self.spell_range.normal}ft)"
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
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK)
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
        total_dice = 2 * (2 if is_crit else 1) + crit_extra

        damage_bonus = caster.get_spell_damage_bonus()
        fire_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=total_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FIRE
        )

        damage_dice = fire_damage.get_dice(attack_outcome=outcome)
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

    def get_range(self) -> Range:
        """Return spell range for POSITION_AOE target resolution."""
        return self.spell_range

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
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
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

    def get_range(self) -> Range:
        """Return spell range for POSITION_AOE target resolution."""
        return self.spell_range

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

    def get_range(self) -> Range:
        """Return spell range for POSITION_AOE target resolution."""
        return self.spell_range

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

    def get_range(self) -> Range:
        """Return spell range for POSITION_AOE target resolution."""
        return self.spell_range

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
    ) -> Tuple[Tuple[int, int], int, bool]:
        """Calculate where target lands after being pushed.

        Returns: (final_position, actual_distance_feet, was_blocked)
        """

        grid = get_map()
        distance_tiles = distance_feet // 5
        last_valid_pos = start
        was_blocked = False

        for i in range(1, distance_tiles + 1):
            next_pos = (start[0] + direction[0] * i, start[1] + direction[1] * i)

            # Check if tile is walkable
            if not grid.is_walkable_for(next_pos[0], next_pos[1], target_uuid):
                was_blocked = True
                break

            # Check if occupied by another entity
            entities_at_pos = grid.get_entities_at(next_pos)
            other_entities = [e for e in entities_at_pos if e != target_uuid]
            if other_entities:
                was_blocked = True
                break

            last_valid_pos = next_pos

        actual_distance = abs(last_valid_pos[0] - start[0]) + abs(last_valid_pos[1] - start[1])
        actual_distance_feet = actual_distance * 5

        return (last_valid_pos, actual_distance_feet, was_blocked)

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
            end_pos, push_distance_actual, was_blocked = self._calculate_push_destination(
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

    def get_range(self) -> Range:
        """Return spell range for POSITION_AOE target resolution."""
        return self.spell_range

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
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
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

    def get_range(self) -> Range:
        """Return spell range for POSITION_AOE target resolution."""
        return self.spell_range

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
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
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

    def get_range(self) -> Range:
        """Return spell range for POSITION_AOE target resolution."""
        return self.spell_range

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
            parent_condition=self.uuid
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

    def get_range(self) -> Range:
        return self.spell_range

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
        if distance > self.spell_range.normal:
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
                spell_dc=dc
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
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK)
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
        total_dice = num_dice * (2 if is_crit else 1) + crit_extra

        damage_bonus = caster.get_spell_damage_bonus()
        lightning_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=total_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.LIGHTNING
        )

        damage_dice = lightning_damage.get_dice(attack_outcome=outcome)
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
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
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
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK)
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
        total_dice = num_dice * (2 if is_crit else 1) + crit_extra

        damage_bonus = caster.get_spell_damage_bonus()
        radiant_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=total_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.RADIANT
        )

        damage_dice = radiant_damage.get_dice(attack_outcome=outcome)
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
