"""SRD 5.1 Halfling origin runtime mechanics."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from dnd.core.dice import Dice, DiceRoll
from dnd.core.events import D20RollResultEvent, Event
from dnd.core.modifiers import AdvantageStatus


def _selected_natural_d20(roll: DiceRoll) -> int:
    results = roll.results if isinstance(roll.results, list) else [roll.results]
    if roll.advantage_status is AdvantageStatus.ADVANTAGE:
        return max(results)
    if roll.advantage_status is AdvantageStatus.DISADVANTAGE:
        return min(results)
    return results[0]


def halfling_lucky_processor(
    event: Event,
    source_entity_uuid: UUID,
) -> Optional[Event]:
    """Reroll one selected natural d20 result of 1 and use the replacement."""
    if (
        not isinstance(event, D20RollResultEvent)
        or event.source_entity_uuid != source_entity_uuid
        or _selected_natural_d20(event.get_effective_roll()) != 1
    ):
        return None
    if event.bonus is None:
        raise RuntimeError("Halfling Lucky requires the exact d20 bonus")
    replacement = Dice(
        count=1,
        value=20,
        bonus=event.bonus,
        roll_type=event.roll_type,
    ).roll
    return event.replace_roll(
        replacement,
        "Halfling Lucky",
        "Rerolled a natural 1 and used the replacement",
    )


__all__ = [
    "halfling_lucky_processor",
]
