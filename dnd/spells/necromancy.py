"""Necromancy spells - manipulating life force and death.

Contains: Blight, BlindnessDeafness
"""
from typing import Optional, List, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import BaseCondition
from dnd.core.dice import AttackOutcome
from dnd.core.events import EventPhase, RangeType, Range, Damage, EventType, EventHandler, Trigger, Event
from dnd.core.modifiers import DamageType, AdvantageModifier, AdvantageStatus, CreatureType
from dnd.entity import Entity
from dnd.actions import SpellAction, SpellEvent
from dnd.spells.evocation import validate_line_of_sight
from dnd.conditions import Blinded, Deafened


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

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(status_message="Target not found")

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
        return [], handler_uuids, sub_condition_uuids, effect_event

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
