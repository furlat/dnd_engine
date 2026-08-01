"""Feat-style d20 processors installed by structural character grants."""

from dnd.entity import Entity
from typing import Optional
from dnd.core.events import D20RollResultEvent
from dnd.core.dice import Dice
from uuid import UUID


def lucky_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID
) -> Optional[D20RollResultEvent]:
    """Spend one luck point on an automatic low-total d20 reroll.

    Args:
        event: D20 result event being processed.
        source_entity_uuid: Entity UUID that owns the Lucky handler.

    Returns:
        Modified event when Lucky replaces the effective roll, otherwise
        `None`.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    if not entity.action_economy.can_afford_resource("luck_points", 1):
        return None

    original_total = event.get_effective_roll().total
    if original_total >= 10:
        return None

    entity.action_economy.consume_resource("luck_points", 1)

    assert event.bonus is not None, "Lucky reroll requires a bonus on the event"
    dice = Dice(count=1, value=20, bonus=event.bonus, roll_type=event.roll_type)
    new_roll = dice.roll

    if new_roll.total > original_total:
        return event.replace_roll(
            new_roll,
            "Lucky",
            f"Rerolled {original_total} -> {new_roll.total}",
        )

    return event.with_updates(
        status_message=(
            f"Lucky kept {original_total} after rerolling {new_roll.total}"
        ),
    )
