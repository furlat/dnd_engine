"""Evocation spells - dealing damage and channeling energy.

Contains: FireBolt, SacredFlame, MagicMissile
"""
from typing import Optional, List
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.values import ModifiableValue
from dnd.core.dice import DiceRoll, AttackOutcome, RollType
from dnd.core.events import EventPhase, RangeType, Range, Damage
from dnd.core.modifiers import DamageType

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
    """
    name: str = Field(default="Magic Missile")
    description: str = Field(default="Three darts of force that automatically hit")
    spell_level: int = Field(default=1)
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
        """Execute Magic Missile - auto-hit darts."""
        from dnd.entity import Entity

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # Calculate number of darts: 3 base + 1 per upcast level
        num_darts = 3 + self.get_upcast_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Launching {num_darts} magic missiles"
        )

        # Each dart deals 1d4+1 force damage
        # Magic Missile is unique: all darts rolled together for simplicity
        # (RAW allows splitting between targets, but we simplify to single target)

        damages: List[Damage] = []
        damage_rolls: List[DiceRoll] = []
        total_damage = 0

        for i in range(num_darts):
            # Each dart is 1d4+1
            dart_damage = Damage(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                damage_dice=4,
                dice_numbers=1,
                damage_bonus=ModifiableValue.create(
                    source_entity_uuid=caster.uuid,
                    base_value=1,  # +1 per dart is intrinsic
                    value_name=f"Magic Missile Dart {i+1}"
                ),
                damage_type=DamageType.FORCE
            )

            # Roll damage (auto-hit, so use HIT outcome)
            damage_dice = dart_damage.get_dice(attack_outcome=AttackOutcome.HIT)
            damage_roll = damage_dice.roll

            damages.append(dart_damage)
            damage_rolls.append(damage_roll)
            total_damage += damage_roll.total

        # Apply total damage as force
        target.health.take_damage(total_damage, DamageType.FORCE, source_entity_uuid=caster.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=damages,
            damage_rolls=damage_rolls,
            status_message=f"{self.name} dealt {total_damage} force damage ({num_darts} darts)"
        )
