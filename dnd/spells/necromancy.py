"""Necromancy spells - manipulating life force and death.

Contains: Blight, BlindnessDeafness, FalseLife, ChillTouch
"""
from typing import Optional, List, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import BaseCondition, DurationType, Duration
from dnd.core.dice import AttackOutcome, Dice, RollType
from dnd.core.events import EventPhase, RangeType, Range, Damage, EventType, EventHandler, Trigger, Event
from dnd.core.modifiers import (
    DamageType, AdvantageModifier, AdvantageStatus, CreatureType,
    NumericalModifier, ContextualAdvantageModifier
)
from functools import partial
from typing import Any, Dict
from dnd.entity import Entity, determine_attack_outcome
from dnd.actions import SpellAction, SpellEvent
from dnd.spells.evocation import validate_line_of_sight
from dnd.conditions import Blinded, Deafened


class FalseLife(SpellAction):
    """False Life - 1st level Necromancy

    Bolstering yourself with a necromantic facsimile of life, you gain
    1d4 + 4 temporary hit points for the duration.

    At Higher Levels: You gain 5 additional temporary hit points for
    each slot level above 1st.

    Duration: 1 hour (not tracked - temp HP persist until depleted or replaced)
    Not concentration.
    """
    name: str = Field(default="False Life")
    description: str = Field(default="Gain 1d4+4 temporary hit points (+5 per upcast level)")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="necromancy")
    target_type: TargetType = Field(default=TargetType.SELF)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF, normal=0))

    def get_temp_hp_bonus(self) -> int:
        """4 base + 5 per upcast level above 1st."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level) * 5
        return 4 + upcast_bonus

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Self-targeting spell, minimal validation needed."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Casting {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply False Life - gain temporary hit points."""
        from dnd.core.values import ModifiableValue

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        # Roll 1d4 + bonus
        bonus_value = ModifiableValue.create(
            source_entity_uuid=caster.uuid,
            base_value=self.get_temp_hp_bonus(),
            value_name="False Life Bonus"
        )
        dice = Dice(
            count=1,
            value=4,
            bonus=bonus_value,
            roll_type=RollType.CHECK  # Using CHECK as generic roll type
        )
        temp_hp_roll = dice.roll

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            dice_roll=temp_hp_roll,
            status_message=f"Rolled 1d4+{self.get_temp_hp_bonus()} = {temp_hp_roll.total} temporary HP"
        )

        # Apply temporary hit points
        # Note: temp HP don't stack - if higher than current, replaces them
        caster.health.add_temporary_hit_points(temp_hp_roll.total, caster.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            temp_hp_gained=temp_hp_roll.total,
            status_message=f"{caster.name} gains {temp_hp_roll.total} temporary hit points"
        )


class NoHealing(BaseCondition):
    """Prevents target from regaining hit points.

    This condition is checked by Health.heal() to block healing.
    Used by Chill Touch and similar effects.
    """
    name: str = "No Healing"
    description: str = "Cannot regain hit points"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        # Add a dummy +0 modifier so applied=True (required for proper cleanup)
        # We use proficiency_bonus as it's always present
        source_uuid = self.source_entity_uuid if self.source_entity_uuid else self.target_entity_uuid
        dummy_mod = NumericalModifier(
            name="No Healing Marker",
            value=0,
            source_entity_uuid=source_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = target.proficiency_bonus.self_static.add_value_modifier(dummy_mod)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target.name} cannot regain hit points"
        )
        return [(target.proficiency_bonus.uuid, mod_uuid)], [], [], [], effect_event


class ChillTouchEffect(BaseCondition):
    """Tracks Chill Touch effect on caster.

    Duration: 1 round (expires at start of caster's next turn).

    This follows the SRD: "until the start of your next turn" = CASTER's turn.
    Uses external_conditions to manage NoHealing on the target.
    If target is undead, also adds disadvantage on attacks vs caster.
    """
    name: str = "Chill Touch Effect"
    description: str = "Tracking condition for Chill Touch debuffs"
    affected_target_uuid: Optional[UUID] = None  # The target of the spell
    target_is_undead: bool = False

    @staticmethod
    def undead_attack_disadvantage(
        caster_uuid: UUID,
        source_entity_uuid: UUID,
        target_entity_uuid: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[AdvantageModifier]:
        """Returns disadvantage when undead attacks the caster."""
        _ = context  # Unused
        if target_entity_uuid and target_entity_uuid == caster_uuid:
            return AdvantageModifier(
                name="Chill Touch (Undead)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid
            )
        return None

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.affected_target_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Affected target UUID not set")

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Caster UUID not set")

        target = Entity.get(self.affected_target_uuid)
        caster = Entity.get(self.target_entity_uuid)  # Condition is on caster
        if not target or not caster:
            return [], [], [], [], declaration_event.cancel(status_message="Target or caster not found")

        outs: List[Tuple[UUID, UUID]] = []

        # If target is undead, add disadvantage on attacks vs caster
        if self.target_is_undead:
            # Use contextual modifier that checks if attack target is the caster
            callable_func = partial(self.undead_attack_disadvantage, caster.uuid)
            disadv_mod = ContextualAdvantageModifier(
                name="Chill Touch (Undead)",
                source_entity_uuid=target.uuid,
                target_entity_uuid=caster.uuid,
                callable=callable_func
            )
            mod_uuid = target.equipment.attack_bonus.self_contextual.add_advantage_modifier(disadv_mod)
            outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Chill Touch effect tracker"
        )

        # Need at least one modifier for applied=True
        # If not undead, add a dummy modifier
        if not outs:
            dummy_mod = NumericalModifier(
                name="Chill Touch Tracker",
                value=0,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid
            )
            mod_uuid = caster.proficiency_bonus.self_static.add_value_modifier(dummy_mod)
            outs.append((caster.proficiency_bonus.uuid, mod_uuid))

        return outs, [], [], [], effect_event


class ChillTouch(SpellAction):
    """Chill Touch - Necromancy cantrip

    You create a ghostly, skeletal hand in the space of a creature within range.
    Make a ranged spell attack against the creature to assail it with the chill
    of the grave. On a hit, the target takes 1d8 necrotic damage, and it can't
    regain hit points until the start of your next turn. Until then, the hand
    clings to the target.

    If you hit an undead target, it also has disadvantage on attack rolls against
    you until the start of your next turn.

    Damage scales: 2d8 at 5th, 3d8 at 11th, 4d8 at 17th level.
    """
    name: str = Field(default="Chill Touch")
    description: str = Field(default="1d8 necrotic, target can't heal. Undead: disadvantage vs caster.")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="necromancy")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=120))

    def _get_cantrip_dice_count(self, caster_level: int) -> int:
        """1d8 base, scaling at 5/11/17."""
        if caster_level >= 17:
            return 4
        elif caster_level >= 11:
            return 3
        elif caster_level >= 5:
            return 2
        return 1

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source or not target:
            return declaration_event.cancel(status_message="Source or target entity not found")

        # Check range
        distance = source.senses.get_feet_distance(target.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute Chill Touch - spell attack for necrotic damage + debuffs."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Get attack and AC bonuses
        attack_bonus = caster.spell_attack_bonus(target.uuid)
        target_ac = target.ac_bonus(caster.uuid)

        # 2. Cross-propagate modifiers
        attack_bonus.set_from_target(target_ac)
        target_ac.set_from_target(attack_bonus)

        # 3. Roll attack
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK)
        outcome = determine_attack_outcome(dice_roll, target_ac)

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
        necrotic_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=total_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.NECROTIC
        )

        damage_dice = necrotic_damage.get_dice(attack_outcome=outcome)
        damage_roll = damage_dice.roll

        # Apply damage
        target.health.take_damage(damage_roll.total, DamageType.NECROTIC, source_entity_uuid=caster.uuid)

        # 7. Apply debuffs using effect condition on caster
        is_undead = target.creature_type == CreatureType.UNDEAD

        # Apply effect condition to caster (tracks duration)
        effect_condition = ChillTouchEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,  # Lives on caster
            affected_target_uuid=target.uuid,
            target_is_undead=is_undead,
            duration=Duration(
                duration=1,
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid
            )
        )
        caster.add_condition(effect_condition)

        # Apply No Healing to target
        no_healing = NoHealing(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(no_healing)

        # Link via external_conditions for cleanup
        effect_condition.add_external_condition(target.uuid, no_healing.uuid)

        undead_text = " (undead: disadvantage vs caster)" if is_undead else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[necrotic_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} hit for {damage_roll.total} necrotic damage, target can't heal{undead_text}"
        )


class Blight(SpellAction):
    """Blight - 4th level Necromancy

    Necromantic energy washes over a creature of your choice that you can see
    within range, draining moisture and vitality from it. The target must make
    a Constitution saving throw. The target takes 8d8 necrotic damage on a
    failed save, or half as much damage on a successful one.

    This spell has no effect on undead or constructs.
    A plant creature or a magical plant has disadvantage on the saving throw
    and the spell deals maximum damage to it.

    At Higher Levels: +1d8 damage per slot level above 4th.
    """
    name: str = Field(default="Blight")
    description: str = Field(default="8d8 necrotic, CON save half. No effect on undead/constructs. Plants: disadvantage + max damage.")
    spell_level: int = Field(default=4)
    spell_school: str = Field(default="necromancy")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))

    # Target filtering
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="enemies")

    # Damage configuration
    base_damage_dice: int = Field(default=8)  # 8d8 at level 4

    def get_damage_dice_count(self) -> int:
        """8d8 base + 1d8 per level above 4th."""
        upcast_bonus = max(0, self.cast_at_level - self.spell_level)
        return self.base_damage_dice + upcast_bonus

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range, LOS, and creature type (not undead/construct)."""
        from dnd.entity import Entity

        # Validate line of sight
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        # Blight has no effect on undead or constructs
        if target_entity.creature_type == CreatureType.UNDEAD:
            return declaration_event.cancel(
                status_message="Blight has no effect on undead"
            )
        if target_entity.creature_type == CreatureType.CONSTRUCT:
            return declaration_event.cancel(
                status_message="Blight has no effect on constructs"
            )

        # Validate range
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
        """Execute Blight - CON save or necrotic damage."""
        from dnd.entity import Entity

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # Check if target is a plant
        is_plant = target.creature_type == CreatureType.PLANT

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Add disadvantage for plants (temporary modifier)
        mod_uuid: Optional[UUID] = None
        if is_plant:
            disadv_mod = AdvantageModifier(
                name="Blight (Plant)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            mod_uuid = target.saving_throws.get_saving_throw("constitution").bonus.self_static.add_advantage_modifier(disadv_mod)

        # 3. Request CON save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc
        )
        _, save_roll, success = target.saving_throw(save_request)

        # 4. Remove disadvantage modifier
        if is_plant and mod_uuid:
            target.saving_throws.get_saving_throw("constitution").bonus.self_static.remove_modifier(mod_uuid)

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

        # 5. Calculate damage
        num_dice = self.get_damage_dice_count()
        damage_bonus = caster.get_spell_damage_bonus()
        damage_bonus_value = damage_bonus.normalized_score

        if is_plant:
            # Plants take maximum damage
            final_damage = num_dice * 8 + damage_bonus_value
        else:
            # Roll damage normally
            necrotic_damage = Damage(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                damage_dice=8,
                dice_numbers=num_dice,
                damage_bonus=damage_bonus,
                damage_type=DamageType.NECROTIC
            )
            damage_dice = necrotic_damage.get_dice(attack_outcome=AttackOutcome.HIT)
            damage_roll = damage_dice.roll

            # Half damage on successful save
            final_damage = damage_roll.total // 2 if success else damage_roll.total

        # 6. Apply damage
        if final_damage > 0:
            target.health.take_damage(final_damage, DamageType.NECROTIC, source_entity_uuid=caster.uuid)

        save_text = " (saved for half)" if success and not is_plant else ""
        plant_text = " (maximum damage)" if is_plant else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=final_damage,
            status_message=f"Blight deals {final_damage} necrotic damage to {target.name}{save_text}{plant_text}"
        )


class BlindnessDeafnessEffect(BaseCondition):
    """Effect from Blindness/Deafness spell.

    Target is either Blinded or Deafened.
    Repeat CON save at end of each turn to end the effect.
    NOT concentration.
    """
    name: str = "Blindness/Deafness"
    description: str = "Blinded or Deafened by magic"

    caster_uuid: Optional[UUID] = None
    spell_dc: int = 10
    effect_type: str = "blinded"  # "blinded" or "deafened"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        # Apply the chosen effect as sub-condition
        if self.effect_type == "blinded":
            effect = Blinded(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid
            )
        else:
            effect = Deafened(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid
            )

        sub_event = target.add_condition(effect)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(effect.uuid)

        # Register repeat save handler
        if self.caster_uuid:
            handler = self._create_repeat_save_handler()
            target.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied {self.effect_type.capitalize()} to {target.name}"
        )
        return [], handler_uuids, sub_condition_uuids, [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """CON save at end of turn to end the effect."""
        assert self.target_entity_uuid is not None
        assert self.caster_uuid is not None

        target_uuid = self.target_entity_uuid
        caster_uuid = self.caster_uuid
        effect_uuid = self.uuid
        dc = self.spell_dc

        def repeat_save_processor(event: Event, _: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            # Check if still affected
            bd_effect = target.active_conditions.get("Blindness/Deafness")
            if not bd_effect or bd_effect.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                # Caster gone, end the effect
                target.remove_condition("Blindness/Deafness")
                return None

            # Repeat CON save
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="constitution",
                dc=dc
            )
            _roll, _outcome, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Blindness/Deafness")
            return None

        return EventHandler(
            name=f"Blindness/Deafness Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT)
            ],
            event_processor=repeat_save_processor
        )


class BlindnessDeafness(SpellAction):
    """Blindness/Deafness - 2nd level Necromancy

    You can blind or deafen a foe. Choose one creature that you can see within
    range to make a CON save. If it fails, the target is either blinded or
    deafened (your choice) for the duration. At the end of each of its turns,
    the target can make a CON save. On a success, the spell ends.

    At Higher Levels: Target one additional creature for each slot level above 2nd.

    NOT concentration.
    """
    name: str = Field(default="Blindness/Deafness")
    description: str = Field(default="CON save or Blinded/Deafened. Repeat save each turn.")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="necromancy")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))

    # Multi-entity configuration
    allow_same_target: bool = Field(default=False)
    valid_target_filter: str = Field(default="enemies")

    # Effect choice: "blinded" or "deafened"
    effect_type: str = Field(default="blinded")

    def get_num_projectiles(self) -> int:
        """1 target base + 1 per upcast level."""
        return 1 + self.get_upcast_bonus()

    def get_all_targets(self) -> List[UUID]:
        """Return all targets."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)
        return targets[:self.get_num_projectiles()]

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and LOS for all targets."""
        source = Entity.get(self.source_entity_uuid)
        if not source:
            return declaration_event.cancel(status_message="Caster not found")

        # Validate effect_type
        if self.effect_type not in ["blinded", "deafened"]:
            return declaration_event.cancel(status_message="Effect type must be 'blinded' or 'deafened'")

        all_targets = self.get_all_targets()
        validated_targets = set()

        for target_uuid in all_targets:
            if target_uuid in validated_targets:
                continue
            validated_targets.add(target_uuid)

            target = Entity.get(target_uuid)
            if not target:
                return declaration_event.cancel(status_message="Target not found")

            # Check LOS
            if target_uuid not in source.senses.entities.keys():
                return declaration_event.cancel(status_message=f"{target.name} not in line of sight")

            # Check range
            distance = source.senses.get_feet_distance(target.position)
            if distance > self.spell_range.normal:
                return declaration_event.cancel(
                    status_message=f"{target.name} out of range ({distance}ft > {self.spell_range.normal}ft)"
                )

        # Call parent validation
        from typing import cast as type_cast
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply blindness/deafness to current target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # CON save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc
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

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Blindness/Deafness"
            )

        # Apply effect
        bd_effect = BlindnessDeafnessEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc,
            effect_type=self.effect_type
        )
        target.add_condition(bd_effect)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is {self.effect_type.capitalize()} by Blindness/Deafness"
        )
