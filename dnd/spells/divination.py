"""Divination spells - revealing information and granting special senses.

Contains: SeeInvisibility, TrueSeeing, Guidance
"""
import random
from typing import Optional, List, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import BaseCondition, DurationType
from dnd.core.base_block import SensesType, SenseMode
from dnd.core.events import Event, EventPhase, Range, RangeType, EventType, EventHandler, Trigger, D20RollResultEvent
from dnd.entity import Entity
from dnd.actions import SpellAction, SpellEvent


# =============================================================================
# See Invisibility (Level 2, Divination, NOT concentration)
# =============================================================================

class SeeInvisibilityEffect(BaseCondition):
    """Grants the ability to see invisible creatures and objects."""
    name: str = "See Invisibility"
    description: str = "You can see invisible creatures and objects"
    magical_origin: bool = True
    _granted_sense_type: Optional[SensesType] = None

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        target.senses.sense_modes.append(SenseMode(sense_type=SensesType.SEE_INVISIBLE, range_feet=0))
        self._granted_sense_type = SensesType.SEE_INVISIBLE
        target._notify_perceivability_changed()

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self}
        ) if declaration_event else None

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        if self._granted_sense_type is not None and self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target:
                target.senses.sense_modes = [
                    sm for sm in target.senses.sense_modes
                    if sm.sense_type != self._granted_sense_type
                ]
                target._notify_perceivability_changed()
        return super()._remove(event)


class SeeInvisibility(SpellAction):
    """See Invisibility - 2nd level Divination (NOT concentration)

    For the duration, you see invisible creatures and objects as if they
    were visible. Duration: 10 rounds.
    """
    name: str = Field(default="See Invisibility")
    description: str = Field(default="See invisible creatures and objects")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="divination")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.SELF)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts See Invisibility"
        )

        see_invis = SeeInvisibilityEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid
        )
        see_invis.duration.duration_type = DurationType.ROUNDS
        see_invis.duration.duration = 10
        caster.add_condition(see_invis, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} can now see invisible creatures"
        )


# =============================================================================
# True Seeing (Level 6, Divination, NOT concentration)
# =============================================================================

class TrueSeeingEffect(BaseCondition):
    """Grants 120ft truesight."""
    name: str = "True Seeing"
    description: str = "You have truesight out to 120 feet"
    magical_origin: bool = True
    _granted_sense_type: Optional[SensesType] = None
    _granted_range: int = 120

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        target.senses.sense_modes.append(SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=120))
        self._granted_sense_type = SensesType.TRUESIGHT
        target._notify_perceivability_changed()

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self}
        ) if declaration_event else None

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        if self._granted_sense_type is not None and self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target:
                target.senses.sense_modes = [
                    sm for sm in target.senses.sense_modes
                    if not (sm.sense_type == self._granted_sense_type
                            and sm.range_feet == self._granted_range)
                ]
                target._notify_perceivability_changed()
        return super()._remove(event)


class TrueSeeing(SpellAction):
    """True Seeing - 6th level Divination (NOT concentration)

    You touch a willing creature and grant it truesight out to 120 feet.
    Duration: 10 rounds.
    """
    name: str = Field(default="True Seeing")
    description: str = Field(default="Grant truesight 120ft")
    spell_level: int = Field(default=6)
    spell_school: str = Field(default="divination")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))
    valid_target_filter: str = Field(default="self_or_allies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid not in caster.senses.entities and target.uuid != caster.uuid:
            return declaration_event.cancel(status_message="Target not visible")

        distance = caster.senses.get_feet_distance(target.position)
        if distance > 5:
            return declaration_event.cancel(status_message=f"Target out of touch range ({distance}ft)")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} grants True Seeing to {target.name}"
        )

        true_seeing = TrueSeeingEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        true_seeing.duration.duration_type = DurationType.ROUNDS
        true_seeing.duration.duration = 10
        target.add_condition(true_seeing, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} gains truesight (120ft)"
        )


# =============================================================================
# Guidance (Cantrip, Divination, Concentration)
# =============================================================================

def _guidance_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID,
) -> Optional[D20RollResultEvent]:
    """Add 1d4 to skill check roll. One-use: disables handler after firing."""
    if event.source_entity_uuid != source_entity_uuid:
        return None

    d4_value = random.randint(1, 4)
    effective = event.get_effective_roll()
    new_total = effective.total + d4_value
    new_roll = effective.model_copy(update={"total": new_total})
    event.replace_roll(new_roll, "Guidance", f"+{d4_value} (1d4)")

    # One-use: remove the condition after firing
    target = Entity.get(source_entity_uuid)
    if target and "Guidance" in target.active_conditions:
        target.remove_condition("Guidance", parent_event=event)

    return event.model_copy(update={"modified": True})


class GuidanceEffect(BaseCondition):
    """Guidance spell effect — add 1d4 to one ability check (skill check only).

    One-use: the handler removes itself after firing once.
    """
    name: str = "Guidance"
    description: str = "Add 1d4 to one ability check"
    magical_origin: bool = True

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No target")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler = EventHandler(
            name="Guidance",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CHECK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid,
                ),
            ],
            event_processor=_guidance_processor,
        )
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Guidance to {target.name}",
        )
        return [], [handler.uuid], [], [], effect_event


class Guidance(SpellAction):
    """Guidance - Divination Cantrip (Concentration)

    You touch one willing creature. Once before the spell ends, the target
    can roll a d4 and add the number rolled to one ability check of its choice.

    Duration: Concentration, up to 1 minute (10 rounds).
    """
    name: str = Field(default="Guidance")
    description: str = Field(default="Touch: +1d4 to one ability check (concentration)")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="divination")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))
    valid_target_filter: str = Field(default="self_or_allies")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        if not target:
            target = caster

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Guidance on {target.name}"
        )

        guidance_effect = GuidanceEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        guidance_effect.duration.duration_type = DurationType.ROUNDS
        guidance_effect.duration.duration = 10
        target.add_condition(guidance_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if guidance_effect.applied:
            concentration.add_linked_condition(target.uuid, guidance_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} gains Guidance"
        )
