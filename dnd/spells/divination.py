"""Divination spells that reveal information or grant special senses."""

import random
from typing import Any, Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import (
    ActionInformationOperation,
    ActionWorldEffectAnchor,
    ActionWorldEffectCertainty,
    ActionWorldEffectProfile,
    ActionWorldEffectScope,
    ActionWorldEffectShape,
    InformationEffectProfile,
    TargetType,
)
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.base_block import SensesType, SenseMode
from dnd.core.events import Event, EventPhase, Range, RangeType, EventType, EventHandler, Trigger, D20RollResultEvent
from dnd.entity import Entity
from dnd.actions import SpellAction, SpellEvent


class SeeInvisibilityEffect(BaseCondition):
    """Grants the ability to see invisible creatures and objects."""

    name: str = Field(default="See Invisibility", description="Condition name.")
    description: str = Field(default="You can see invisible creatures and objects", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")
    _granted_sense_type: Optional[SensesType] = None

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Add see-invisible sensing to the target.

        Args:
            declaration_event: Condition application declaration event.

        Returns:
            Empty modifier and handler lists plus the effect event.
        """
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
        """Remove the granted see-invisible sense mode."""
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
    """Second-level divination spell that grants see-invisible sense."""

    name: str = Field(default="See Invisibility", description="Spell name.")
    description: str = Field(default="See invisible creatures and objects", description="Spell description.")
    spell_level: int = Field(default=2, description="Spell slot level.")
    spell_school: str = Field(default="divination", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Spell range.")

    def get_world_effect_profile(self, actor: Any) -> ActionWorldEffectProfile:
        """Declare the granted see-invisible sense and possible discoveries.

        Args:
            actor: Entity discovering the spell. The sense contract is fixed.

        Returns:
            Typed information effects matching the runtime sense mode.
        """
        return ActionWorldEffectProfile(
            semantic_id="information.see_invisibility",
            information_effects=(
                InformationEffectProfile(
                    operation=ActionInformationOperation.GRANT_SENSE,
                    certainty=ActionWorldEffectCertainty.GUARANTEED,
                    anchor=ActionWorldEffectAnchor.ACTOR,
                    scope=ActionWorldEffectScope.TARGET,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=0,
                    sense_type=SensesType.SEE_INVISIBLE.name.lower(),
                ),
                InformationEffectProfile(
                    operation=ActionInformationOperation.REVEAL_REGION,
                    certainty=ActionWorldEffectCertainty.CONDITIONAL,
                    anchor=ActionWorldEffectAnchor.ACTOR,
                    scope=ActionWorldEffectScope.REGION,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=0,
                ),
            ),
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply See Invisibility to the caster.

        Args:
            execution_event: Spell execution event.

        Returns:
            Completed spell event, or a canceled event if the caster is missing.
        """
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

        return effect_event.with_updates(
            status_message=f"{caster.name} can now see invisible creatures"
        )


class TrueSeeingEffect(BaseCondition):
    """Grants 120ft truesight."""

    name: str = Field(default="True Seeing", description="Condition name.")
    description: str = Field(default="You have truesight out to 120 feet", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")
    _granted_sense_type: Optional[SensesType] = None
    _granted_range: int = 120

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Add truesight sensing to the target.

        Args:
            declaration_event: Condition application declaration event.

        Returns:
            Empty modifier and handler lists plus the effect event.
        """
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
        """Remove the granted truesight sense mode."""
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
    """Sixth-level divination spell that grants 120-foot truesight."""

    name: str = Field(default="True Seeing", description="Spell name.")
    description: str = Field(default="Grant truesight 120ft", description="Spell description.")
    spell_level: int = Field(default=6, description="Spell slot level.")
    spell_school: str = Field(default="divination", description="Spell school.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Spell range.")
    valid_target_filter: str = Field(default="self_or_allies", description="Valid target filter key.")

    def get_world_effect_profile(self, actor: Any) -> ActionWorldEffectProfile:
        """Declare the granted truesight sense and possible discoveries.

        Args:
            actor: Entity discovering the spell. The sense contract is fixed.

        Returns:
            Typed information effects matching the runtime sense mode.
        """
        return ActionWorldEffectProfile(
            semantic_id="information.true_seeing",
            information_effects=(
                InformationEffectProfile(
                    operation=ActionInformationOperation.GRANT_SENSE,
                    certainty=ActionWorldEffectCertainty.GUARANTEED,
                    anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
                    scope=ActionWorldEffectScope.TARGET,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=120,
                    sense_type=SensesType.TRUESIGHT.name.lower(),
                ),
                InformationEffectProfile(
                    operation=ActionInformationOperation.REVEAL_REGION,
                    certainty=ActionWorldEffectCertainty.CONDITIONAL,
                    anchor=ActionWorldEffectAnchor.SELECTED_TARGET,
                    scope=ActionWorldEffectScope.REGION,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=120,
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate touch range and visibility for True Seeing.

        Args:
            declaration_event: Spell declaration event.

        Returns:
            Execution-ready, canceled, or parent-validated spell event.
        """
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        contact = caster.senses.entities.get(target.uuid)
        if target.uuid != caster.uuid and (contact is None or not contact.visual):
            return declaration_event.cancel(status_message="Target not visible")

        distance = caster.senses.get_feet_distance(target.position)
        if distance > 5:
            return declaration_event.cancel(status_message=f"Target out of touch range ({distance}ft)")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply the True Seeing condition to the target.

        Args:
            execution_event: Spell execution event.

        Returns:
            Completed spell event, or a canceled event if caster or target is
            missing.
        """
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

        return effect_event.with_updates(
            status_message=f"{target.name} gains truesight (120ft)"
        )


def _guidance_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID,
) -> Optional[D20RollResultEvent]:
    """Add 1d4 to one skill check and consume Guidance.

    Args:
        event: D20 roll-result event being modified.
        source_entity_uuid: Guided entity UUID.

    Returns:
        Modified event when Guidance applies, otherwise `None`.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    d4_value = random.randint(1, 4)
    effective = event.get_effective_roll()
    new_total = effective.total + d4_value
    new_roll = effective.model_copy(update={"total": new_total})
    modified_event = event.replace_roll(
        new_roll,
        "Guidance",
        f"+{d4_value} (1d4)",
    )

    target = Entity.get(source_entity_uuid)
    if target and "Guidance" in target.active_conditions:
        target.remove_condition("Guidance", parent_event=modified_event)

    return modified_event


class GuidanceEffect(BaseCondition):
    """Guidance spell effect that adds 1d4 to one skill check.

    One-use: the handler removes itself after firing once.
    """
    name: str = Field(default="Guidance", description="Condition name.")
    description: str = Field(default="Add 1d4 to one ability check", description="Condition description.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags.")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        """Register the one-use d20 result handler.

        Args:
            declaration_event: Condition application declaration event.

        Returns:
            Handler UUID ownership plus the effect event, or a canceled event
            when the target cannot be found.
        """
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
    name: str = Field(default="Guidance", description="Spell name.")
    description: str = Field(default="Touch: +1d4 to one ability check (concentration)", description="Spell description.")
    spell_level: int = Field(default=0, description="Cantrip spell level.")
    spell_school: str = Field(default="divination", description="Spell school.")
    concentration: bool = Field(default=True, description="Whether the spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5), description="Spell range.")
    valid_target_filter: str = Field(default="self_or_allies", description="Valid target filter key.")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Guidance and link it to concentration.

        Args:
            execution_event: Spell execution event.

        Returns:
            Completed spell event, or a canceled event if the caster is missing.
        """
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

        return effect_event.with_updates(
            status_message=f"{target.name} gains Guidance"
        )
