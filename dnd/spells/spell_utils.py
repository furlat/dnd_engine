"""Shared spell utility functions.

Contains helpers used across multiple spell school modules to avoid
cross-spell-file imports.
"""
from typing import Optional
from uuid import UUID

from dnd.core.dice import DiceRoll
from dnd.core.events import EventPhase, Healing, HealRollResultEvent, Event
from dnd.entity import Entity
from dnd.actions import SpellEvent


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

    contact = source_entity.senses.entities.get(target_entity.uuid)
    if contact is None or not contact.visual:
        return declaration_event.cancel(status_message=f"Target entity not in line of sight for {declaration_event.name}")
    return declaration_event.phase_to(
        new_phase=EventPhase.EXECUTION,
        status_message=f"Validated line of sight for {declaration_event.name}"
    )


def fire_heal_roll_result(
    caster_uuid: UUID,
    target_uuid: UUID,
    healing: Healing,
    parent_event: Event,
    spell_name: str = "",
) -> DiceRoll:
    """Roll healing dice and fire HEAL_ROLL_RESULT event for handler interception.

    Mirrors the DAMAGE_ROLL_RESULT pattern. Handlers (e.g., Beacon of Hope)
    can maximize or replace healing dice via event.replace_roll().

    Returns the final_roll (possibly modified by handlers).
    """
    original_roll = healing.get_dice().roll
    caster = Entity.get(caster_uuid)
    target = Entity.get(target_uuid)

    heal_roll_event = HealRollResultEvent(
        source_entity_uuid=caster_uuid,
        target_entity_uuid=target_uuid,
        source_entity_name=caster.name if isinstance(caster, Entity) else None,
        target_entity_name=target.name if isinstance(target, Entity) else None,
        spell_name=spell_name,
        original_roll=original_roll,
        final_roll=original_roll.model_copy(deep=True),
        parent_event=parent_event.uuid,
        phase=EventPhase.DECLARATION,
    )

    heal_roll_event = heal_roll_event.phase_to(
        EventPhase.EFFECT,
        status_message=f"Healing dice rolled for {spell_name}",
    )
    heal_roll_event = heal_roll_event.phase_to(
        EventPhase.COMPLETION,
        status_message=f"Healing dice finalized for {spell_name}",
    )

    return heal_roll_event.final_roll
