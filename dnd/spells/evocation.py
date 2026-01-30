"""Evocation spells - dealing damage and channeling energy.

Contains: FireBolt, SacredFlame, MagicMissile, Fireball
"""
from typing import Optional, List
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.values import ModifiableValue
from dnd.core.dice import AttackOutcome, RollType
from typing import cast as type_cast
from dnd.core.events import EventPhase, RangeType, Range, Damage
from dnd.core.modifiers import DamageType
from dnd.core.aoe import AoEShape

from dnd.actions import SpellAction, SpellEvent


def validate_line_of_sight(declaration_event: SpellEvent, source_entity_uuid: UUID) -> Optional[SpellEvent]:
    """Validate if the source entity and target entity are in line of sight."""
    from dnd.entity import Entity

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
        from dnd.entity import Entity

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
        from dnd.entity import Entity, determine_attack_outcome

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
        target.health.take_damage(damage_roll.total, DamageType.FIRE, source_entity_uuid=caster.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[fire_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} fire damage"
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
        from dnd.entity import Entity

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
        from dnd.entity import Entity

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # Update event
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            status_message=f"Requesting DEX save DC {dc}"
        )

        # 2. Request DEX save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = effect_event.post(
            save_success=success,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        # 3. On successful save: no damage
        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
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

        # Apply damage
        target.health.take_damage(damage_roll.total, DamageType.RADIANT, source_entity_uuid=caster.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[radiant_damage],
            damage_rolls=[damage_roll],
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
        from dnd.entity import Entity

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
        from dnd.entity import Entity

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

        # Apply damage
        target.health.take_damage(damage_roll.total, DamageType.FORCE, source_entity_uuid=caster.uuid)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[dart_damage],
            damage_rolls=[damage_roll],
            total_damage=damage_roll.total,
            status_message=f"Dart hits {target.name} for {damage_roll.total} force damage"
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

    def __init__(self, **kwargs):
        from dnd.core.aoe import Sphere
        from uuid import uuid4

        # Set up shape before super().__init__ if not provided
        if 'aoe_shape' not in kwargs or kwargs['aoe_shape'] is None:
            source_uuid = kwargs.get('source_entity_uuid') or uuid4()
            kwargs['aoe_shape'] = Sphere(
                source_entity_uuid=source_uuid,
                target=kwargs.get('end_position', (0, 0)),
                radius_feet=20
            )
        super().__init__(**kwargs)

    def get_range(self) -> Range:
        """Return spell range for POSITION_AOE target resolution."""
        return self.spell_range

    def get_damage_dice_count(self) -> int:
        """8d6 base + 1d6 per level above 3rd."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in LOS and range."""
        from dnd.entity import Entity

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
        from dnd.entity import Entity

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Request DEX save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            save_success=success,
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

        # 5. Apply damage
        if final_damage > 0:
            target.health.take_damage(final_damage, DamageType.FIRE, source_entity_uuid=caster.uuid)

        save_text = " (saved for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[fire_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,  # Required for convolution aggregation
            status_message=f"Fireball deals {final_damage} fire damage to {target.name}{save_text}"
        )
