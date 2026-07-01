"""Feat conditions and feat-style d20 processors."""

from dnd.core.base_conditions import BaseCondition
from dnd.entity import Entity
from typing import Optional, List, Tuple
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger, D20RollResultEvent
)
from dnd.core.dice import Dice
from dnd.blocks.action_economy import RechargeType
from pydantic import Field
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

    original_total = event.roll.total
    if original_total >= 10:
        return None

    entity.action_economy.consume_resource("luck_points", 1)

    assert event.bonus is not None, "Lucky reroll requires a bonus on the event"
    dice = Dice(count=1, value=20, bonus=event.bonus, roll_type=event.roll_type)
    new_roll = dice.roll

    if new_roll.total > original_total:
        event.replace_roll(new_roll, "Lucky", f"Rerolled {original_total} -> {new_roll.total}")
        return event.model_copy(update={"modified": True})

    return None


class LuckyFeature(BaseCondition):
    """Automatic Lucky-style d20 reroll feature.

    Attributes:
        name: Feature condition name for Lucky lookup and cleanup.
        description: Short rules-facing summary of the automatic Lucky policy.
    """
    name: str = Field(default="Lucky", description="Feature condition name for Lucky lookup and cleanup.")
    description: str = Field(
        default=(
            "You have 3 luck points. When you make an attack roll, ability check, "
            "or saving throw, you can spend one luck point to reroll the d20."
        ),
        description="Short rules-facing summary of the automatic Lucky policy.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        target.action_economy.add_resource("luck_points", 3, RechargeType.LONG_REST)

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
            event_processor=lucky_processor,
            player_toggleable=True
        )

        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Lucky feat to {target.name}"
        )

        return [], [handler.uuid], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Remove the luck-point resource owned by this feature.

        Args:
            event: Removal event supplied by the condition lifecycle.

        Returns:
            Removal event after the base condition removal phases.
        """
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("luck_points")
        return super()._remove(event)
