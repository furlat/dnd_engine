"""Shared spell utility functions.

Contains helpers used across multiple spell school modules to avoid
cross-spell-file imports.
"""
from uuid import UUID

from dnd.core.dice import DiceRoll
from dnd.core.events import EventPhase, Healing, HealRollResultEvent, Event
from dnd.entity import Entity


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
