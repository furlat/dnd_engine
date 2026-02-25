"""Illusion spells - deceiving the senses and mind.

Contains: Blur, Fear, HypnoticPattern, ColorSpray, Invisibility, GreaterInvisibility, MirrorImage
"""
import random
from typing import Any, Optional, List, Tuple
from uuid import UUID

from pydantic import Field
from typing import cast as type_cast

from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import BaseCondition, Duration, DurationType
from dnd.core.events import EventPhase, RangeType, Range, EventType, EventHandler, Trigger, Event
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus, NumericalModifier
from dnd.core.dice import AttackOutcome
from dnd.core.aoe import AoEShape, Cone, Cube
from dnd.entity import Entity
from dnd.actions import SpellAction, SpellEvent, AttackEvent
from dnd.conditions import Concentrating, Frightened, Charmed, Incapacitated, Blinded, InvisibilityEffect, GreaterInvisibilityEffect


class BlurEffect(BaseCondition):
    """Effect from Blur spell.

    Attackers have disadvantage on attack rolls against you.
    """
    name: str = "Blur"
    description: str = "Your body becomes blurred, giving attackers disadvantage"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        # Attackers have disadvantage - add to AC's to_target_static channel
        disadv_mod = AdvantageModifier(
            name="Blur",
            value=AdvantageStatus.DISADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.source_entity_uuid or self.target_entity_uuid
        )
        mod_uuid = target.equipment.ac_bonus.to_target_static.add_advantage_modifier(disadv_mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Blur to {target.name}"
        )
        return outs, [], [], [], effect_event


class Blur(SpellAction):
    """Blur - 2nd level Illusion (Concentration)

    Your body becomes blurred, shifting and wavering to all who can see you.
    For the duration, any creature has disadvantage on attack rolls against you.
    An attacker is immune to this effect if it doesn't rely on sight, as with
    blindsight, or can see through illusions, as with truesight.

    Duration: Concentration, up to 1 minute.
    """
    name: str = Field(default="Blur")
    description: str = Field(default="Concentration. Attackers have disadvantage against you.")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="illusion")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.SELF)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Self-targeting spell - minimal validation."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Blur effect to self."""

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} becomes blurred"
        )

        # Apply BlurEffect condition
        blur_effect = BlurEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid
        )
        caster.add_condition(blur_effect, parent_event=effect_event)

        # Apply Concentrating condition
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Blur"
        )
        caster.add_condition(concentration, parent_event=effect_event)

        # Link effect to concentration
        concentration.add_linked_condition(caster.uuid, blur_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} casts Blur (concentration)"
        )


class FearEffect(BaseCondition):
    """Effect from Fear spell.

    Target is Frightened of the caster and must Dash away on each turn.
    Repeat WIS save at end of each turn (only if can't see caster).
    """
    name: str = "Fear"
    description: str = "Frightened of the caster, must Dash away"

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

        # Apply Frightened as sub-condition (with source being caster)
        frightened = Frightened(
            source_entity_uuid=self.caster_uuid or self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid
        )
        sub_event = target.add_condition(frightened, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(frightened.uuid)

        # Register repeat save handler (only when can't see caster)
        if self.caster_uuid:
            handler = self._create_repeat_save_handler()
            target.add_event_handler(handler)
            handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Fear effect to {target.name}"
        )
        return [], handler_uuids, sub_condition_uuids, [], effect_event

    def _create_repeat_save_handler(self) -> EventHandler:
        """WIS save at end of turn to end fear (only if can't see caster)."""
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

            # Check if still affected by Fear
            fear_effect = target.active_conditions.get("Fear")
            if not fear_effect or fear_effect.uuid != effect_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                # Caster gone, end the effect
                target.remove_condition("Fear", parent_event=event)
                return None

            # Only save if target CAN'T see caster
            if caster_uuid in target.senses.entities:
                # Can still see caster - no save this turn
                return None

            # Repeat WIS save (child of triggering turn end event)
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=target.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _roll, _outcome, success = target.saving_throw(save_request)

            if success:
                target.remove_condition("Fear", parent_event=event)
            return None

        return EventHandler(
            name=f"Fear Repeat Save ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT)
            ],
            event_processor=repeat_save_processor
        )


class Fear(SpellAction):
    """Fear - 3rd level Illusion (Concentration)

    You project a phantasmal image of a creature's worst fears. Each creature
    in a 30-foot cone must succeed on a WIS save or drop whatever it is holding
    and become frightened for the duration.

    While frightened, a creature must Dash away from you each turn by the safest
    available route. If there is nowhere to move, the creature can use the Dodge
    action. If the creature ends its turn in a location where it doesn't have line
    of sight to you, the creature can make a WIS save. On success, the spell ends.

    Duration: Concentration, up to 1 minute.
    """
    name: str = Field(default="Fear")
    description: str = Field(default="30ft cone, WIS save or Frightened + must Dash away")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="illusion")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    include_self: bool = Field(default=False)
    valid_target_filter: str = Field(default="all")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cone(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                length_feet=30
            )

    def get_range(self) -> Range:
        return self.spell_range

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate cone direction."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        if not self.end_position:
            return declaration_event.cancel(status_message="No direction specified for cone")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Fear to current target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # WIS save (child of execution event)
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
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Fear"
            )

        # Apply Fear effect
        fear_effect = FearEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_uuid=caster.uuid,
            spell_dc=dc
        )
        target.add_condition(fear_effect, parent_event=effect_event)

        # Apply Concentrating (only on first target via convolution)
        # Note: Convolution handles multi-target, but concentration is per-spell
        if "Concentrating" not in caster.active_conditions:
            concentration = Concentrating(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid,
                spell_name="Fear"
            )
            caster.add_condition(concentration, parent_event=effect_event)

        # Link fear effect to concentration
        conc = caster.active_conditions.get("Concentrating")
        if conc and isinstance(conc, Concentrating) and conc.spell_name == "Fear":
            conc.add_linked_condition(target.uuid, fear_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is Frightened by Fear"
        )


class HypnoticPatternEffect(BaseCondition):
    """Effect from Hypnotic Pattern spell.

    Target is Charmed and Incapacitated (incapacitated + speed 0).
    Breaks when target takes damage or is shaken awake.
    """
    name: str = "Hypnotic Pattern"
    description: str = "Charmed and incapacitated by swirling pattern"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []
        handler_uuids: List[UUID] = []

        # Apply Charmed as sub-condition
        charmed = Charmed(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid
        )
        sub_event = target.add_condition(charmed, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(charmed.uuid)

        # Apply Incapacitated as sub-condition
        incapacitated = Incapacitated(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid
        )
        sub_event2 = target.add_condition(incapacitated, parent_event=declaration_event)
        if sub_event2 and sub_event2.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(incapacitated.uuid)

        # Register handler to break on damage
        handler = self._create_damage_break_handler()
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Hypnotic Pattern effect to {target.name}"
        )
        return [], handler_uuids, sub_condition_uuids, [], effect_event

    def _create_damage_break_handler(self) -> EventHandler:
        """Break Hypnotic Pattern when target takes damage."""
        assert self.target_entity_uuid is not None

        target_uuid = self.target_entity_uuid
        effect_uuid = self.uuid

        def damage_break_processor(event: Event, _: UUID) -> Optional[Event]:
            if event.target_entity_uuid != target_uuid:
                return None

            target = Entity.get(target_uuid)
            if not target:
                return None

            # Check if still affected
            hp_effect = target.active_conditions.get("Hypnotic Pattern")
            if not hp_effect or hp_effect.uuid != effect_uuid:
                return None

            # Break the effect
            target.remove_condition("Hypnotic Pattern", parent_event=event)
            return None

        return EventHandler(
            name=f"Hypnotic Pattern Damage Break ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.TAKE_DAMAGE, event_phase=EventPhase.EFFECT)
            ],
            event_processor=damage_break_processor
        )


class HypnoticPattern(SpellAction):
    """Hypnotic Pattern - 3rd level Illusion (Concentration)

    You create a twisting pattern of colors that weaves through the air inside
    a 30-foot cube within range. Each creature in the area who sees the pattern
    must make a WIS save. On a failed save, the creature becomes charmed for the
    duration. While charmed, the creature is incapacitated and has a speed of 0.

    The spell ends for an affected creature if it takes any damage or if someone
    else uses an action to shake the creature out of its stupor.

    Duration: Concentration, up to 1 minute.
    """
    name: str = Field(default="Hypnotic Pattern")
    description: str = Field(default="30ft cube, WIS save or Charmed + Incapacitated")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="illusion")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=120))

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    include_self: bool = Field(default=False)  # Caster can be hit if in area
    valid_target_filter: str = Field(default="all")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (0, 0),
                size_feet=30,
                centered=True
            )

    def get_range(self) -> Range:
        return self.spell_range

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

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(status_message=f"Out of range ({distance}ft)")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Hypnotic Pattern to current target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        # WIS save (child of execution event)
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
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Hypnotic Pattern"
            )

        # Apply Hypnotic Pattern effect
        hp_effect = HypnoticPatternEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(hp_effect, parent_event=effect_event)

        # Apply Concentrating (only on first target)
        if "Concentrating" not in caster.active_conditions:
            concentration = Concentrating(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid,
                spell_name="Hypnotic Pattern"
            )
            caster.add_condition(concentration, parent_event=effect_event)

        # Link effect to concentration
        conc = caster.active_conditions.get("Concentrating")
        if conc and isinstance(conc, Concentrating) and conc.spell_name == "Hypnotic Pattern":
            conc.add_linked_condition(target.uuid, hp_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is mesmerized by Hypnotic Pattern"
        )


class ColorSprayEffect(BaseCondition):
    """Effect from Color Spray spell.

    Target is Blinded for 1 round (until end of caster's next turn).
    """
    name: str = "Color Spray"
    description: str = "Blinded by dazzling colors"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        sub_condition_uuids: List[UUID] = []

        # Apply Blinded as sub-condition
        blinded = Blinded(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid
        )
        sub_event = target.add_condition(blinded, parent_event=declaration_event)
        if sub_event and sub_event.phase == EventPhase.COMPLETION:
            sub_condition_uuids.append(blinded.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Color Spray blindness to {target.name}"
        )
        return [], [], sub_condition_uuids, [], effect_event


class ColorSpray(SpellAction):
    """Color Spray - 1st level Illusion

    Roll 6d10 HP pool. Creatures in 15ft cone are Blinded for 1 round
    in order of lowest HP until pool exhausted.

    Skip: Unconscious creatures, already-blinded creatures
    Upcast: +2d10 per slot level above 1st.
    """
    name: str = Field(default="Color Spray")
    description: str = Field(default="Roll 6d10 HP pool. Affects creatures in order of lowest HP.")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="illusion")
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    # AoE configuration
    aoe_shape: Optional[AoEShape] = Field(default=None)

    # Target filtering - but we override get_all_targets for HP-pool logic
    include_self: bool = Field(default=False)  # Cone emanates from caster
    valid_target_filter: str = Field(default="all")

    # HP pool tracking (set during get_all_targets)
    hp_pool_rolled: int = Field(default=0)
    hp_pool_remaining: int = Field(default=0)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cone(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position or (1, 0),
                length_feet=15
            )

    def get_range(self) -> Range:
        return self.spell_range

    def get_hp_pool_dice(self) -> Tuple[int, int]:
        """Returns (dice_count, dice_value). 6d10 base + 2d10 per upcast."""
        base_dice = 6
        upcast_bonus = max(0, self.cast_at_level - self.spell_level) * 2
        return (base_dice + upcast_bonus, 10)

    def get_all_targets(self) -> List[UUID]:
        """Override: Select targets by HP pool instead of all AoE targets.

        1. Get AoE candidates using parent logic
        2. Filter: skip unconscious, skip already-blinded
        3. Sort by current HP (ascending)
        4. Select targets until HP pool exhausted
        """
        # 1. Get AoE candidates
        if not (self.aoe_shape and self.end_position):
            return []

        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return []

        self.aoe_shape.compute_objective(caster.position)

        # 2. Filter candidates
        candidates: List[Tuple[int, UUID]] = []
        for uid in self.aoe_shape.affected_entity_uuids:
            # Skip caster (cone emanates from self)
            if uid == self.source_entity_uuid:
                continue

            entity = Entity.get(uid)
            if not entity or not entity.has_hp:
                continue

            # Color Spray skips unconscious creatures
            if "Unconscious" in entity.active_conditions:
                continue

            # Skip already-blinded creatures (they can't be affected further)
            if "Blinded" in entity.active_conditions:
                continue

            # Skip creatures immune to blindness
            if entity.check_condition_immunity("Blinded"):
                continue

            candidates.append((entity.get_hp(), uid))

        # 3. Sort by HP ascending (lowest first)
        # Tie-breaker: UUID for deterministic ordering
        candidates.sort(key=lambda x: (x[0], str(x[1])))

        # 4. Roll HP pool if not already rolled
        if self.hp_pool_rolled == 0:
            dice_count, dice_value = self.get_hp_pool_dice()
            roll_results = [random.randint(1, dice_value) for _ in range(dice_count)]
            total = sum(roll_results)
            self.hp_pool_rolled = total
            self.hp_pool_remaining = total

        # 5. Select targets until pool exhausted
        targets: List[UUID] = []
        remaining = self.hp_pool_remaining
        for hp, uid in candidates:
            if hp <= remaining:
                targets.append(uid)
                remaining -= hp

        self.hp_pool_remaining = remaining
        return targets

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
        """Apply Color Spray blindness to current target (called once per target by convolution)."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Color Spray affecting {target.name} ({target.get_hp()} HP)"
        )

        # Apply ColorSprayEffect condition (has Blinded as sub-condition)
        # Duration: 1 round (ends at start of caster's next turn)
        color_spray_effect = ColorSprayEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            duration=Duration(
                duration=1,
                duration_type=DurationType.ROUNDS,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid  # Duration tied to caster's turns
            )
        )
        target.add_condition(color_spray_effect, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} is blinded by Color Spray ({target.get_hp()} HP)"
        )


class Invisibility(SpellAction):
    """Invisibility - 2nd level Illusion (Concentration)

    A creature you touch becomes invisible until the spell ends.
    Anything the target is wearing or carrying is invisible as long as it
    is on the target's person. The spell ends for a target that attacks
    or casts a spell.

    Duration: Concentration, up to 1 hour.
    Range: Touch (5ft).
    """
    name: str = Field(default="Invisibility")
    description: str = Field(default="Concentration. Touch target becomes invisible until attacking or casting.")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="illusion")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="all")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate touch range (5ft)."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        # Self-cast is always valid
        if target.uuid != caster.uuid:
            distance = caster.senses.get_feet_distance(target.position)
            if distance > self.spell_range.normal:
                return declaration_event.cancel(
                    status_message=f"Target out of range ({distance}ft, max {self.spell_range.normal}ft)"
                )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Invisibility to target."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not target or not isinstance(target, Entity):
            return execution_event.cancel(status_message="Target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Invisibility on {target.name}"
        )

        # Apply InvisibilityEffect condition (breaks on attack/cast)
        invis_effect = InvisibilityEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(invis_effect, parent_event=effect_event)

        # Apply Concentrating condition on caster
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Invisibility"
        )
        caster.add_condition(concentration, parent_event=effect_event)

        # Link effect to concentration for cleanup
        concentration.add_linked_condition(target.uuid, invis_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} casts Invisibility on {target.name} (concentration)"
        )


class GreaterInvisibility(SpellAction):
    """Greater Invisibility - 4th level Illusion (Concentration)

    BG3-style: A creature you touch becomes invisible. On attack or spell cast,
    rolls a Stealth check vs escalating DC to maintain invisibility
    (DC 15, +1 per success).

    Duration: Concentration, up to 10 rounds.
    Range: Touch (5ft).
    """
    name: str = Field(default="Greater Invisibility")
    description: str = Field(default="Concentration. Touch target becomes invisible, Stealth check to maintain on attack/cast.")
    spell_level: int = Field(default=4)
    spell_school: str = Field(default="illusion")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="all")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate touch range (5ft)."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        # Self-cast is always valid
        if target.uuid != caster.uuid:
            distance = caster.senses.get_feet_distance(target.position)
            if distance > self.spell_range.normal:
                return declaration_event.cancel(
                    status_message=f"Target out of range ({distance}ft, max {self.spell_range.normal}ft)"
                )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Greater Invisibility to target."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not target or not isinstance(target, Entity):
            return execution_event.cancel(status_message="Target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Greater Invisibility on {target.name}"
        )

        # Apply GreaterInvisibilityEffect condition (stealth check to maintain)
        invis_effect = GreaterInvisibilityEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(invis_effect, parent_event=effect_event)

        # Apply Concentrating condition on caster
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Greater Invisibility"
        )
        caster.add_condition(concentration, parent_event=effect_event)

        # Link effect to concentration for cleanup
        concentration.add_linked_condition(target.uuid, invis_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} casts Greater Invisibility on {target.name} (concentration)"
        )


# =============================================================================
# Mirror Image (2nd-level Illusion, NO Concentration) — BG3 Version
# =============================================================================

class MirrorImageEffect(BaseCondition):
    """Effect from Mirror Image spell (BG3 version).

    Creates 3 illusory duplicates. Each duplicate grants +3 AC.
    When an attack misses the caster, one duplicate disappears (AC drops by 3).
    Condition removed when all duplicates are destroyed or after 10 rounds.

    - 3 duplicates: +9 AC
    - 2 duplicates: +6 AC
    - 1 duplicate:  +3 AC
    - 0 duplicates: condition ends
    """
    name: str = "Mirror Image"
    description: str = "Illusory duplicates increase AC by 3 each"

    duplicates: int = Field(default=3, description="Number of remaining duplicates")

    # Track the AC modifier UUID so we can update it when duplicates are destroyed
    _ac_modifier_uuid: Optional[UUID] = None
    _ac_mv_uuid: Optional[UUID] = None

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(type_cast(UUID, self.target_entity_uuid))
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target not found"
            )

        self.duplicates = 3

        # Duration: 10 rounds
        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 10

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        # +9 AC (3 duplicates × 3)
        ac_mod = NumericalModifier(
            name="Mirror Image",
            value=9,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = target.equipment.ac_bonus.self_static.add_value_modifier(ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))
        self._ac_modifier_uuid = ac_mod.uuid
        self._ac_mv_uuid = target.equipment.ac_bonus.uuid

        # Handler: on attack miss, destroy a duplicate
        miss_handler = self._create_miss_handler()
        target.add_event_handler(miss_handler)
        handler_uuids.append(miss_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Mirror Image (+9 AC, 3 duplicates) to {target.name}"
        )
        return outs, handler_uuids, [], [], effect_event

    def _create_miss_handler(self) -> EventHandler:
        """When an attack misses the caster, destroy one duplicate."""
        target_uuid = type_cast(UUID, self.target_entity_uuid)
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.target_entity_uuid != target_uuid:
                return None

            if not isinstance(event, AttackEvent):
                return None
            if event.attack_outcome is None:
                return None

            # Only trigger on misses (the attack was evaded thanks to high AC)
            if event.attack_outcome not in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS):
                return None

            if condition.duplicates <= 0:
                return None

            # Destroy one duplicate
            condition.duplicates -= 1
            remaining = condition.duplicates

            # Update AC modifier: new value = remaining * 3
            if condition._ac_modifier_uuid and condition._ac_mv_uuid:
                from dnd.core.values import ModifiableValue
                mv = ModifiableValue.get(condition._ac_mv_uuid)
                if mv:
                    mod = mv.self_static.value_modifiers.get(condition._ac_modifier_uuid)
                    if mod:
                        mod.value = remaining * 3

            # Remove condition if no duplicates left
            if remaining <= 0:
                target = Entity.get(target_uuid)
                if target:
                    target.remove_condition("Mirror Image", parent_event=event)

            return None

        return EventHandler(
            name="Mirror Image: Evade",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target_uuid
                )
            ],
            event_processor=processor
        )


class MirrorImage(SpellAction):
    """Mirror Image - 2nd level Illusion (NO Concentration) — BG3 Version

    Create 3 illusory duplicates of yourself to distract attackers.
    Each duplicate increases your AC by 3. When you successfully evade
    an attack, one of the duplicates disappears.

    Duration: 10 turns. No concentration.
    """
    name: str = Field(default="Mirror Image")
    description: str = Field(default="3 duplicates, +3 AC each, lost on evade")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="illusion")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.SELF)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Self-targeting spell — minimal validation."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Mirror Image to self."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} creates mirror images"
        )

        mirror_effect = MirrorImageEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid
        )
        caster.add_condition(mirror_effect, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} casts Mirror Image (3 duplicates, +9 AC)"
        )
