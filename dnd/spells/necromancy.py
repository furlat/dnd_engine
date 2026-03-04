"""Necromancy spells - manipulating life force and death.

Contains: Blight, BlindnessDeafness, FalseLife, ChillTouch, NecroticBless, Eyebite, BestowCurse
"""
from typing import Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import BaseCondition, ConditionCategory, ConditionTag, DurationType, Duration
from dnd.core.dice import AttackOutcome, Dice, RollType
from dnd.core.events import EventPhase, RangeType, Range, Damage, EventType, EventHandler, Trigger, Event, AbilityName, SkillName
from dnd.core.modifiers import (
    DamageType, AdvantageModifier, AdvantageStatus, CreatureType,
    NumericalModifier, ContextualAdvantageModifier
)
from dnd.core.values import ModifiableValue
from functools import partial
from typing import Any, Dict
from dnd.entity import Entity, determine_attack_outcome
from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator
from dnd.spells.spell_utils import validate_line_of_sight
from dnd.core.base_actions import Cost, BaseAction, ActionCategory
from dnd.conditions import Blinded, Deafened, Unconscious, Frightened, Concentrating, ConcentrationActionMarker
from dnd.spells.enchantment import BaneEffect, BlessEffect
from dnd.blocks.skills import SKILL_TO_ABILITY


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

    Sets Health.healing_blocked = True on apply, False on remove.
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

        # Set healing_blocked flag on Health block
        target.health.healing_blocked = True

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target.name} cannot regain hit points"
        )
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Reset healing_blocked when condition is removed."""
        if self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target:
                target.health.healing_blocked = False

        # Call parent _remove for event handling
        return super()._remove(event)


class ChillTouchEffect(BaseCondition):
    """Tracks Chill Touch effect on caster.

    Duration: 1 round (expires at start of caster's next turn).

    This follows the SRD: "until the start of your next turn" = CASTER's turn.
    Uses linked_conditions to manage NoHealing on the target.
    If target is undead, also adds disadvantage on attacks vs caster.
    """
    name: str = "Chill Touch Effect"
    description: str = "Tracking condition for Chill Touch debuffs"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
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
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
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
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK, parent_event=execution_event.uuid)
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
        damage_bonus = caster.get_spell_damage_bonus()
        necrotic_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=8,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.NECROTIC
        )

        damage_dice = necrotic_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        # Apply damage (child of effect event)
        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.NECROTIC,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

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
        caster.add_condition(effect_condition, parent_event=effect_event)

        # Apply No Healing to target
        no_healing = NoHealing(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(no_healing, parent_event=effect_event)

        # Link via linked_conditions for cleanup
        effect_condition.add_linked_condition(target.uuid, no_healing.uuid)

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
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
            )

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Execute Blight - CON save or necrotic damage."""

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

        # 3. Request CON save (child of execution event)
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
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

        # 6. Apply damage (child of effect event)
        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.NECROTIC,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid
            )

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
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

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
                parent_condition=self.uuid,
                tags={ConditionTag.MAGICAL}
            )
        else:
            effect = Deafened(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                parent_condition=self.uuid,
                tags={ConditionTag.MAGICAL}
            )

        sub_event = target.add_condition(effect, parent_event=declaration_event)
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
                target.remove_condition("Blindness/Deafness", parent_event=event)
                return None

            # Repeat CON save (child of triggering turn end event)
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _roll, _outcome, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Blindness/Deafness", parent_event=event)
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

    def get_multi_target_count(self) -> Optional[int]:
        return self.get_num_projectiles()

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
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target.name} out of range ({distance}ft > {self.effective_range}ft)"
                )

        # Call parent validation
        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply blindness/deafness to current target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # CON save (child of execution event)
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
        target.add_condition(bd_effect, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is {self.effect_type.capitalize()} by Blindness/Deafness"
        )


# =============================================================================
# NECROTIC BLESS (Homebrew)
# =============================================================================

class NecroticBless(SpellAction):
    """Necrotic Bless — 2nd-level Necromancy (Concentration, Homebrew)

    Target up to 4 creatures. Undead targets gain BlessEffect (no save).
    Non-undead targets must succeed on a CHA save or suffer BaneEffect.
    """
    name: str = Field(default="Necrotic Bless")
    description: str = Field(default="4 targets: undead get +1d4, others CHA save or -1d4")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="necromancy")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30)
    )

    # Multi-target configuration
    allow_same_target: bool = Field(default=False)
    valid_target_filter: str = Field(default="all")
    include_self: bool = Field(default=True)

    def get_multi_target_count(self) -> Optional[int]:
        return 4

    def get_all_targets(self) -> List[UUID]:
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        for extra in self.extra_target_entity_uuids:
            if extra not in targets:
                targets.append(extra)
        return targets[:4]

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # Create or reuse Concentrating (safe for convolution)
        concentration = self.ensure_concentration(execution_event)

        is_undead = target.creature_type == CreatureType.UNDEAD

        if is_undead:
            # Undead: auto-apply BlessEffect (no save)
            bless_effect = BlessEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                tags={ConditionTag.MAGICAL},
            )
            target.add_condition(bless_effect, parent_event=execution_event)
            if bless_effect.applied:
                concentration.add_linked_condition(target.uuid, bless_effect.uuid)

            effect_event = execution_event.phase_to(
                new_phase=EventPhase.EFFECT,
                target_entity_name=target.name,
                status_message=f"Necrotic Bless - {target.name} (undead) is blessed",
            )
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Necrotic Bless - {target.name} (undead) is blessed",
            )
        else:
            # Non-undead: CHA save or BaneEffect
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="charisma",
                dc=dc,
                parent_event=execution_event.uuid,
            )
            _, save_roll, success = target.saving_throw(save_request)

            effect_event = execution_event.phase_to(
                new_phase=EventPhase.EFFECT,
                save_ability="charisma",
                save_dc=dc,
                save_success=success,
                save_roll=save_roll,
                target_entity_name=target.name,
                status_message=f"CHA save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}",
            )

            if success:
                return effect_event.phase_to(
                    new_phase=EventPhase.COMPLETION,
                    status_message=f"Necrotic Bless - {target.name} resists",
                )

            bane_effect = BaneEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                tags={ConditionTag.MAGICAL},
            )
            target.add_condition(bane_effect, parent_event=effect_event)
            if bane_effect.applied:
                concentration.add_linked_condition(target.uuid, bane_effect.uuid)

            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Necrotic Bless - {target.name} is baned",
            )


# =============================================================================
# EYEBITE CONDITIONS
# =============================================================================

class SickenedCondition(BaseCondition):
    """Sickened by Eyebite - disadvantage on attacks and ability checks.

    Repeat CON save at end of turn to end the effect.
    """
    name: str = "Sickened"
    description: str = "Disadvantage on attacks and ability checks"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    caster_uuid: Optional[UUID] = None
    spell_dc: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        # Disadvantage on attacks
        mod_uuid = target.equipment.attack_bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name="Sickened (attacks)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=target.uuid,
                target_entity_uuid=self.source_entity_uuid
            )
        )
        outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        # Disadvantage on all 6 ability checks
        for ability_name_str in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            ability_name_typed = type_cast(AbilityName, ability_name_str)
            ability = target.ability_scores.get_ability(ability_name_typed)
            ab_mod_uuid = ability.ability_score.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name="Sickened (ability checks)",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=target.uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((ability.ability_score.uuid, ab_mod_uuid))

        # Repeat CON save handler
        handler = self._create_repeat_save_handler()
        target.add_event_handler(handler)
        handler_uuids = [handler.uuid]

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is sickened"
        )
        return outs, handler_uuids, [], [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """CON save at end of turn to end Sickened."""
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
            sickened = target.active_conditions.get("Sickened")
            if not sickened or sickened.uuid != effect_uuid:
                return None
            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Sickened", parent_event=event)
                return None
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="constitution", dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)
            if success:
                target.remove_condition("Sickened", parent_event=event)
            return None

        return EventHandler(
            name=f"Sickened: Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target_uuid
            )],
            event_processor=processor
        )


class EyebiteAsleepEffect(BaseCondition):
    """Eyebite Asleep - applies Unconscious, wakes on damage."""
    name: str = "Eyebite Asleep"
    description: str = "Magically asleep - wakes on damage"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_conditions_uuids: List[UUID] = []

        # Apply Unconscious as sub-condition
        unconscious = Unconscious(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(unconscious, parent_event=declaration_event)
        sub_conditions_uuids.append(unconscious.uuid)

        # Wake on damage handler
        handler = self._create_wake_handler()
        target.add_event_handler(handler)
        handler_uuids = [handler.uuid]

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} falls asleep (Eyebite)"
        )
        return [], handler_uuids, sub_conditions_uuids, [], effect_event

    def _create_wake_handler(self) -> EventHandler:
        """Wake up when taking damage."""
        assert self.target_entity_uuid is not None
        target_uuid = self.target_entity_uuid
        effect_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.target_entity_uuid != target_uuid:
                return None
            target = Entity.get(target_uuid)
            if not target:
                return None
            asleep = target.active_conditions.get("Eyebite Asleep")
            if not asleep or asleep.uuid != effect_uuid:
                return None
            target.remove_condition("Eyebite Asleep", parent_event=event)
            return None

        return EventHandler(
            name=f"Eyebite: Wake on Damage ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target_uuid
            )],
            event_processor=processor
        )


class EyebitePanickedEffect(BaseCondition):
    """Eyebite Panicked - applies Frightened, repeat WIS save at turn end."""
    name: str = "Eyebite Panicked"
    description: str = "Panicked - Frightened, repeat WIS save"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    caster_uuid: Optional[UUID] = None
    spell_dc: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_conditions_uuids: List[UUID] = []

        # Apply Frightened as sub-condition
        frightened = Frightened(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(frightened, parent_event=declaration_event)
        sub_conditions_uuids.append(frightened.uuid)

        # Repeat WIS save handler
        handler = self._create_repeat_save_handler()
        target.add_event_handler(handler)
        handler_uuids = [handler.uuid]

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is panicked (Eyebite)"
        )
        return [], handler_uuids, sub_conditions_uuids, [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """WIS save at end of turn to end Panicked."""
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
            panicked = target.active_conditions.get("Eyebite Panicked")
            if not panicked or panicked.uuid != effect_uuid:
                return None
            caster = Entity.get(caster_uuid)
            if not caster:
                target.remove_condition("Eyebite Panicked", parent_event=event)
                return None
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom", dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)
            if success:
                target.remove_condition("Eyebite Panicked", parent_event=event)
            return None

        return EventHandler(
            name=f"Eyebite Panicked: Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target_uuid
            )],
            event_processor=processor
        )


# =============================================================================
# EYEBITE GRANTED ACTION + SPELL
# =============================================================================

class EyebiteStrike(BaseAction):
    """Action granted by Eyebite to target a creature each turn."""
    name: str = Field(default="Eyebite Strike")
    description: str = Field(default="Choose a creature: Asleep, Panicked, or Sickened (WIS save)")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY)
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Eyebite Strike", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])
    spell_dc: int = Field(default=10)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    effect_choice: str = Field(default="sickened")  # "asleep", "panicked", "sickened"
    valid_target_filter: str = Field(default="enemies")

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
            return declaration_event.cancel(status_message="Not concentrating on Eyebite")

        conc = caster.active_conditions.get("Concentrating")
        if not isinstance(conc, Concentrating) or conc.get_slot_by_spell_name("Eyebite") is None:
            return declaration_event.cancel(status_message="Not concentrating on Eyebite")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return declaration_event.cancel(status_message="No target specified")

        # Check range (60ft)
        distance = caster.senses.get_feet_distance(target.position)
        if distance > 60:
            return declaration_event.cancel(status_message=f"Target out of range ({distance}ft)")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: Event) -> Optional[Event]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # WIS save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom", dc=self.spell_dc,
            parent_event=execution_event.uuid
        )
        _, _, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"WIS save: {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Eyebite ({self.effect_choice})"
            )

        # Get concentration for linking
        conc = caster.active_conditions.get("Concentrating")

        # Apply chosen effect
        if self.effect_choice == "asleep":
            effect = EyebiteAsleepEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid
            )
            target.add_condition(effect, parent_event=effect_event)
            if isinstance(conc, Concentrating) and effect.applied:
                conc.add_linked_condition(target.uuid, effect.uuid)
            result_text = "Asleep"

        elif self.effect_choice == "panicked":
            effect_p = EyebitePanickedEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid,
                spell_dc=self.spell_dc
            )
            target.add_condition(effect_p, parent_event=effect_event)
            if isinstance(conc, Concentrating) and effect_p.applied:
                conc.add_linked_condition(target.uuid, effect_p.uuid)
            result_text = "Panicked"

        else:  # sickened
            effect_s = SickenedCondition(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid,
                spell_dc=self.spell_dc
            )
            target.add_condition(effect_s, parent_event=effect_event)
            if isinstance(conc, Concentrating) and effect_s.applied:
                conc.add_linked_condition(target.uuid, effect_s.uuid)
            result_text = "Sickened"

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Eyebite: {target.name} is {result_text}"
        )


class Eyebite(SpellAction):
    """Eyebite - 6th level Necromancy (Concentration)

    For the spell's duration, your eyes become pools of inky darkness.
    One creature within 60 feet must succeed on a WIS save or be affected
    by one of: Asleep, Panicked, or Sickened. Each turn you can use an
    action to target another creature.

    Duration: Concentration, up to 1 minute
    """
    name: str = Field(default="Eyebite")
    description: str = Field(default="WIS save or Asleep/Panicked/Sickened, repeatable each turn")
    spell_level: int = Field(default=6)
    spell_school: str = Field(default="necromancy")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.SELF)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    # Which effect to apply on first use
    effect_choice: str = Field(default="sickened")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        dc = caster.spell_save_dc()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Eyebite"
        )

        # Register Eyebite Strike action
        strike = EyebiteStrike(
            source_entity_uuid=caster.uuid,
            spell_dc=dc,
            effect_choice=self.effect_choice,
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

        # Fire the first strike immediately (Eyebite targets on cast)
        if self.target_entity_uuid and self.target_entity_uuid != caster.uuid:
            first_strike = EyebiteStrike(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=self.target_entity_uuid,
                spell_dc=dc,
                effect_choice=self.effect_choice,
                template=False,
                costs=[],  # No additional cost — already paid by casting Eyebite
            )
            first_strike.apply()

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} channels Eyebite - can target a creature each turn"
        )


class FingerOfDeath(SpellAction):
    """Finger of Death - 7th level Necromancy

    You send negative energy coursing through a creature that you can see
    within range, causing it searing pain. The target must make a Constitution
    saving throw. It takes 7d8 + 30 necrotic damage on a failed save, or half
    as much damage on a successful one.

    At Higher Levels: +1d8 damage per slot level above 7th (not standard but supported).
    """
    name: str = Field(default="Finger of Death")
    description: str = Field(default="7d8+30 necrotic, CON save half")
    spell_level: int = Field(default=7)
    spell_school: str = Field(default="necromancy")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))

    # Target filtering
    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="enemies")

    # Damage configuration
    base_damage_dice: int = Field(default=7)  # 7d8 at level 7
    flat_damage: int = Field(default=30)  # +30 flat damage

    def get_damage_dice_count(self) -> int:
        """7d8 base + 1d8 per level above 7th."""
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
        """Execute Finger of Death — CON save or 7d8+30 necrotic."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Calculate spell DC
        dc = caster.spell_save_dc()

        # 2. Request CON save
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

        # 3. Calculate damage: Nd8 + 30
        num_dice = self.get_damage_dice_count()
        damage_bonus = caster.get_spell_damage_bonus()

        necrotic_damage = Damage(
            source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            damage_dice=8, dice_numbers=num_dice, damage_bonus=damage_bonus,
            damage_type=DamageType.NECROTIC
        )
        damage_roll = necrotic_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        raw_damage = damage_roll.total + self.flat_damage

        # Half damage on successful save
        final_damage = raw_damage // 2 if success else raw_damage

        # 4. Apply damage
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
            status_message=f"Finger of Death deals {final_damage} necrotic damage to {target.name}{save_text}"
        )


# =============================================================================
# Inflict Wounds (L1) - Melee spell attack, 3d10 necrotic
# =============================================================================

class InflictWounds(SpellAction):
    """Inflict Wounds — 1st-level necromancy.

    Make a melee spell attack against a creature you can reach.
    On a hit, the target takes 3d10 necrotic damage.
    At Higher Levels: +1d10 per slot level above 1st.
    """
    name: str = Field(default="Inflict Wounds")
    description: str = Field(default="Melee spell attack, 3d10 necrotic")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="necromancy")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5)
    )
    valid_target_filter: str = Field(default="enemies")

    def _get_damage_dice_count(self) -> int:
        """3d10 at L1, +1d10 per level above 1st."""
        return 2 + self.cast_at_level  # 3 at L1, 4 at L2, etc.

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not source or not target:
            return declaration_event.cancel(status_message="Source or target not found")

        distance = source.senses.get_feet_distance(target.position)
        if distance > 5:
            return declaration_event.cancel(
                status_message=f"Target out of melee range ({distance}ft > 5ft)"
            )

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # Cross-propagate
        attack_bonus = caster.spell_attack_bonus(target.uuid)
        target_ac = target.ac_bonus(caster.uuid)
        attack_bonus.set_from_target(target_ac)
        target_ac.set_from_target(attack_bonus)

        # Roll attack
        dice_roll = caster.roll_d20(attack_bonus, RollType.ATTACK, parent_event=execution_event.uuid)
        crit_threshold = caster.get_spell_crit_threshold()
        outcome = determine_attack_outcome(dice_roll, target_ac, crit_threshold)

        # Clean up cross-propagation
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

        # Miss
        if outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{self.name} missed"
            )

        # Hit: roll damage
        num_dice = self._get_damage_dice_count()
        is_crit = outcome == AttackOutcome.CRIT
        crit_extra = caster.get_spell_crit_extra_dice() if is_crit else 0
        damage_bonus = caster.get_spell_damage_bonus()

        necrotic_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=10,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.NECROTIC,
        )
        damage_dice = necrotic_damage.get_dice(attack_outcome=outcome, crit_extra_dice=crit_extra)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.NECROTIC,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid,
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[necrotic_damage],
            damage_rolls=[damage_roll],
            total_damage=damage_roll.total,
            status_message=f"{self.name} deals {damage_roll.total} necrotic damage to {target.name}"
        )


# =============================================================================
# Harm (L6) - CON save, 14d6 necrotic, half on save, min 1 HP
# =============================================================================

class Harm(SpellAction):
    """Harm — 6th-level necromancy.

    You unleash a virulent disease on a creature you can see. The target
    must make a CON save. On fail: 14d6 necrotic damage. On save: half.
    The damage can't reduce the target below 1 HP.
    """
    name: str = Field(default="Harm")
    description: str = Field(default="CON save, 14d6 necrotic, half on save, min 1 HP")
    spell_level: int = Field(default=6)
    spell_school: str = Field(default="necromancy")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )
    valid_target_filter: str = Field(default="enemies")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # CON save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid,
        )
        _, _, success = target.saving_throw(save_request)

        # Roll damage: 14d6 necrotic
        necrotic_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=14,
            damage_bonus=ModifiableValue.create(
                source_entity_uuid=caster.uuid,
                base_value=0,
                value_name="Harm Damage",
            ),
            damage_type=DamageType.NECROTIC,
        )
        damage_roll = necrotic_damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        raw_damage = damage_roll.total
        final_damage = raw_damage // 2 if success else raw_damage

        # Cap: can't reduce below 1 HP
        current_hp = target.get_hp()
        if final_damage >= current_hp:
            final_damage = max(0, current_hp - 1)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Harm vs {target.name}: {'SAVE' if success else 'FAIL'}"
        )

        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.NECROTIC,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid,
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[necrotic_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=f"Harm deals {final_damage} necrotic to {target.name}{save_text} (min 1 HP)"
        )


# =============================================================================
# Bestow Curse (Level 3, Concentration, Necromancy)
# =============================================================================


# Reverse map: ability -> list of skills
_ABILITY_TO_SKILLS: Dict[AbilityName, List[SkillName]] = {}
for _skill, _ability in SKILL_TO_ABILITY.items():
    _ABILITY_TO_SKILLS.setdefault(_ability, []).append(_skill)


class AbilityCurseEffect(BaseCondition):
    """Bestow Curse option 1: disadvantage on ability checks and saves with one ability."""
    name: str = "Bestow Curse"
    description: str = "Cursed — disadvantage on checks and saves with one ability"
    condition_category: ConditionCategory = ConditionCategory.CONDITION
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL, ConditionTag.CURSE})

    cursed_ability: AbilityName = "strength"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        # Disadvantage on saving throw for the cursed ability
        save = target.saving_throws.get_saving_throw(self.cursed_ability)
        mod_uuid = save.bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name="Bestow Curse (save)",
                value=AdvantageStatus.DISADVANTAGE,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
        outs.append((save.bonus.uuid, mod_uuid))

        # Disadvantage on all skill checks linked to the cursed ability
        for skill_name in _ABILITY_TO_SKILLS.get(self.cursed_ability, []):
            skill = target.skill_set.get_skill(skill_name)
            mod_uuid = skill.skill_bonus.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name="Bestow Curse (skill)",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=self.target_entity_uuid
                )
            )
            outs.append((skill.skill_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Bestow Curse: disadvantage on {self.cursed_ability} checks and saves"
        )
        return outs, [], [], [], effect_event


class AttackCurseEffect(BaseCondition):
    """Bestow Curse option 2: disadvantage on attacks against the caster."""
    name: str = "Bestow Curse"
    description: str = "Cursed — disadvantage on attacks against the caster"
    condition_category: ConditionCategory = ConditionCategory.CONDITION
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL, ConditionTag.CURSE})

    caster_uuid: Optional[UUID] = None

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        caster_uuid = self.caster_uuid

        def attack_curse_check(
            source_entity_uuid: UUID,
            target_entity_uuid: Optional[UUID],
            context: Optional[Dict[str, Any]]
        ) -> Optional[AdvantageModifier]:
            """Disadvantage when attacking the caster."""
            if target_entity_uuid == caster_uuid:
                return AdvantageModifier(
                    name="Bestow Curse (attack)",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=source_entity_uuid,
                    target_entity_uuid=target_entity_uuid if target_entity_uuid else source_entity_uuid
                )
            return None

        mod_uuid = target.equipment.attack_bonus.self_contextual.add_advantage_modifier(
            ContextualAdvantageModifier(
                name="Bestow Curse (attack)",
                callable=attack_curse_check,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
        outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Bestow Curse: disadvantage on attacks against caster"
        )
        return outs, [], [], [], effect_event


class InactionCurseEffect(BaseCondition):
    """Bestow Curse option 3: WIS save at turn start or lose action."""
    name: str = "Bestow Curse"
    description: str = "Cursed — WIS save at turn start or waste action"
    condition_category: ConditionCategory = ConditionCategory.CONDITION
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL, ConditionTag.CURSE})

    caster_uuid: Optional[UUID] = None
    spell_dc: int = 10
    # Track the constraint so TURN_END handler can remove it
    _action_constraint_uuid: Optional[UUID] = None
    _action_value_uuid: Optional[UUID] = None

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler_uuids: List[UUID] = []

        # TURN_START handler: WIS save or lose action
        turn_start_handler = self._create_turn_start_handler()
        target.add_event_handler(turn_start_handler)
        handler_uuids.append(turn_start_handler.uuid)

        # TURN_END handler: remove action constraint if applied
        turn_end_handler = self._create_turn_end_handler()
        target.add_event_handler(turn_end_handler)
        handler_uuids.append(turn_end_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Bestow Curse: WIS save at turn start or lose action"
        )
        return [], handler_uuids, [], [], effect_event

    def _create_turn_start_handler(self) -> EventHandler:
        assert self.target_entity_uuid is not None
        target_uuid: UUID = self.target_entity_uuid
        caster_uuid = self.caster_uuid
        dc = self.spell_dc
        curse_condition = self

        def turn_start_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            _ = source_entity_uuid
            if event.source_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            # Check if still cursed
            curse = target.active_conditions.get("Bestow Curse")
            if not curse or curse.uuid != curse_condition.uuid:
                return None

            caster = Entity.get(caster_uuid) if caster_uuid else None
            if not caster:
                return None

            # WIS save
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = target.saving_throw(save_request)

            if not success:
                # Lose action: add max_constraint=0 on actions
                constraint_uuid = target.action_economy.actions.self_static.add_max_constraint(
                    constraint=NumericalModifier(
                        name="Bestow Curse (inaction)",
                        value=0,
                        source_entity_uuid=target_uuid,
                        target_entity_uuid=target_uuid
                    )
                )
                curse_condition._action_constraint_uuid = constraint_uuid
                curse_condition._action_value_uuid = target.action_economy.actions.uuid

            return None

        return EventHandler(
            name=f"Bestow Curse Turn Start ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=turn_start_processor
        )

    def _create_turn_end_handler(self) -> EventHandler:
        assert self.target_entity_uuid is not None
        target_uuid: UUID = self.target_entity_uuid
        curse_condition = self

        def turn_end_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            _ = source_entity_uuid
            if event.source_entity_uuid != target_uuid:
                return None

            # Remove constraint if it was applied this turn
            if curse_condition._action_constraint_uuid and curse_condition._action_value_uuid:
                value = ModifiableValue.get(curse_condition._action_value_uuid)
                if value and isinstance(value, ModifiableValue):
                    value.self_static.remove_max_constraint(curse_condition._action_constraint_uuid)
                curse_condition._action_constraint_uuid = None
                curse_condition._action_value_uuid = None

            return None

        return EventHandler(
            name=f"Bestow Curse Turn End ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_END,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=turn_end_processor
        )

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up any lingering action constraint on removal."""
        if self._action_constraint_uuid and self._action_value_uuid:
            value = ModifiableValue.get(self._action_value_uuid)
            if value and isinstance(value, ModifiableValue):
                value.self_static.remove_max_constraint(self._action_constraint_uuid)
            self._action_constraint_uuid = None
            self._action_value_uuid = None
        return super()._remove(event)


class DamageCurseEffect(BaseCondition):
    """Bestow Curse option 4: caster's attacks deal +1d8 necrotic to cursed target."""
    name: str = "Bestow Curse"
    description: str = "Cursed — caster deals extra 1d8 necrotic on hit"
    condition_category: ConditionCategory = ConditionCategory.CONDITION
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL, ConditionTag.CURSE})

    caster_uuid: Optional[UUID] = None

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.caster_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No caster UUID")

        caster = Entity.get(self.caster_uuid)
        if not caster or not isinstance(caster, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Caster not found")

        handler_uuids: List[UUID] = []

        handler = self._create_damage_handler()
        caster.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Bestow Curse: caster deals +1d8 necrotic on attack"
        )
        return [], handler_uuids, [], [], effect_event

    def _create_damage_handler(self) -> EventHandler:
        assert self.caster_uuid is not None
        assert self.target_entity_uuid is not None
        caster_uuid: UUID = self.caster_uuid
        cursed_uuid: UUID = self.target_entity_uuid
        curse_condition = self

        def damage_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            _ = source_entity_uuid
            # Only caster's attacks against cursed target
            if event.source_entity_uuid != caster_uuid:
                return None
            if event.target_entity_uuid != cursed_uuid:
                return None

            # Check attack hit
            attack_outcome = getattr(event, 'attack_outcome', None)
            if not attack_outcome or attack_outcome == AttackOutcome.MISS:
                return None

            # Verify curse still active
            target = Entity.get(cursed_uuid)
            if not target:
                return None
            curse = target.active_conditions.get("Bestow Curse")
            if not curse or curse.uuid != curse_condition.uuid:
                return None

            # Roll 1d8 necrotic
            dice = Dice(
                count=1,
                value=8,
                bonus=ModifiableValue.create(source_entity_uuid=caster_uuid, base_value=0, value_name="Curse Damage"),
                roll_type=RollType.DAMAGE,
                attack_outcome=AttackOutcome.HIT
            )
            roll = dice.roll
            bonus_damage = roll.total

            if bonus_damage > 0:
                target.receive_damage(
                    amount=bonus_damage,
                    damage_type=DamageType.NECROTIC,
                    source_entity_uuid=caster_uuid,
                    parent_event=event.uuid
                )

            return None

        return EventHandler(
            name=f"Bestow Curse Damage ({cursed_uuid})",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster_uuid
                )
            ],
            event_processor=damage_processor
        )


class BestowCurse(SpellAction):
    """Bestow Curse - 3rd level Necromancy (Concentration)

    Touch a creature. WIS save or be cursed. Four curse options:
    1. Disadvantage on ability checks and saves with one ability
    2. Disadvantage on attacks against the caster
    3. WIS save at turn start or lose action
    4. Caster's attacks deal +1d8 necrotic on hit
    """
    name: str = Field(default="Bestow Curse")
    description: str = Field(default="Touch: WIS save or be cursed (concentration)")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="necromancy")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5)
    )
    curse_option: int = Field(default=1, description="Curse type 1-4")
    cursed_ability: AbilityName = Field(default="strength", description="For option 1: which ability")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid not in caster.senses.entities and target.uuid != caster.uuid:
            return declaration_event.cancel(status_message="Target not in line of sight")

        distance = caster.senses.get_feet_distance(target.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Out of range ({distance}ft > {self.effective_range}ft)"
            )

        if self.curse_option < 1 or self.curse_option > 4:
            return declaration_event.cancel(status_message=f"Invalid curse option: {self.curse_option}")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # Start concentration first (breaks existing)
        concentration = self.ensure_concentration(execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            status_message=f"Requesting WIS save DC {dc}"
        )

        # WIS save
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=dc,
            parent_event=effect_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = effect_event.post(
            save_success=success,
            status_message=f"WIS save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Bestow Curse — {target.name} saved"
            )

        # Create curse condition based on option
        curse: BaseCondition
        if self.curse_option == 1:
            curse = AbilityCurseEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                cursed_ability=self.cursed_ability
            )
        elif self.curse_option == 2:
            curse = AttackCurseEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid
            )
        elif self.curse_option == 3:
            curse = InactionCurseEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid,
                spell_dc=dc
            )
        else:
            curse = DamageCurseEffect(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                caster_uuid=caster.uuid
            )

        target.add_condition(curse, parent_event=effect_event)

        if curse.applied:
            concentration.add_linked_condition(target.uuid, curse.uuid)

        option_desc = {
            1: f"disadvantage on {self.cursed_ability} checks/saves",
            2: "disadvantage on attacks vs caster",
            3: "WIS save or lose action each turn",
            4: "+1d8 necrotic on caster's attacks"
        }
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Bestow Curse on {target.name}: {option_desc[self.curse_option]}"
        )
