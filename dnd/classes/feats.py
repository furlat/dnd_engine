"""
Feats Implementation

Implements D&D 5e feats as conditions that can be applied to entities.
"""

from dnd.core.base_conditions import BaseCondition
from dnd.entity import Entity
from typing import Optional, List, Tuple
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger, D20RollResultEvent
)
from dnd.core.dice import Dice
from dnd.blocks.action_economy import RechargeType
from uuid import UUID


# =============================================================================
# LUCKY FEAT
# =============================================================================

def lucky_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID
) -> Optional[D20RollResultEvent]:
    """
    Spend luck point to reroll, keep better result.

    Simple AI: Use Lucky if roll is below 10 (can be enhanced later for smarter decisions).
    """
    # Only process own rolls
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Check resource
    if not entity.action_economy.can_afford_resource("luck_points", 1):
        return None

    # Simple AI: use Lucky if roll is below 10
    original_total = event.roll.total
    if original_total >= 10:
        return None  # Don't waste on decent rolls

    # Consume resource
    entity.action_economy.consume_resource("luck_points", 1)

    # Reroll the d20
    dice = Dice(count=1, value=20, bonus=event.bonus, roll_type=event.roll_type)
    new_roll = dice.roll

    # Keep better result
    if new_roll.total > original_total:
        event.replace_roll(new_roll, "Lucky", f"Rerolled {original_total} -> {new_roll.total}")
        return event.model_copy(update={"modified": True})

    # Original was better (or equal), return None to keep original
    return None


class LuckyFeature(BaseCondition):
    """
    Lucky feat: You have 3 luck points. When you make an attack roll,
    ability check, or saving throw, you can spend one luck point to
    reroll the d20. You can choose to spend a luck point after you
    see the roll, but before the outcome is determined.

    Luck points refresh on a long rest.
    """
    name: str = "Lucky"
    description: str = (
        "You have 3 luck points. When you make an attack roll, ability check, "
        "or saving throw, you can spend one luck point to reroll the d20."
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        Optional[Event]           # completion event
    ]:
        if not self.target_entity_uuid:
            return [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        # Grant 3 luck points resource (recharges on long rest per SRD)
        target.action_economy.add_resource("luck_points", 3, RechargeType.LONG_REST)

        # Register handlers for all d20 roll event types
        # Note: EventQueue matches on exact event_type, so we need to register
        # for each specific subtype (attacks, saves, checks)
        handler = EventHandler(
            name="Lucky",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid
                ),
                Trigger(
                    event_type=EventType.SAVE_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid
                ),
                Trigger(
                    event_type=EventType.CHECK_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid
                ),
            ],
            event_processor=lucky_processor
        )

        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Lucky feat to {target.name}"
        )

        return [], [handler.uuid], [], effect_event
