"""Pumps and taps: a working pump fills a carried waterskin; a dry tap gives nothing."""

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from dnd.actions import entity_action_economy_cost_evaluator
from dnd.blocks.base_item import BaseItem
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.events import EventPhase
from dnd.entity import Entity
from dnd.types.discovery import ActorScan
from dnd.types.physical_access import PhysicalAccess

WATER_PUMP_TAG = "water_pump"
DRY_TAP_TAG = "dry_tap"
EMPTY_WATERSKIN_ID = "gear.waterskin.empty"
FULL_WATERSKIN_ID = "gear.waterskin.full"


def build_waterskin(source_entity_uuid: UUID, *, full: bool = False) -> BaseItem:
    return BaseItem(source_entity_uuid=source_entity_uuid, item_id=FULL_WATERSKIN_ID if full else EMPTY_WATERSKIN_ID,
        name="Waterskin" if full else "Empty waterskin", description="A leather waterskin.",
        tags=["gear", "waterskin"], weight=5 if full else 1)


class WorkPump(BaseAction):
    """Work a pump or turn a tap: a working pump fills one empty waterskin the actor carries."""

    name: str = Field(default="Work Pump", description="Action name.")
    description: str = Field(default="Work the pump or turn the tap", description="Player-facing summary.")
    target_type: TargetType = Field(default=TargetType.OBJECT, description="Targets the pump or tap.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Work Pump Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        return PhysicalAccess.HAND

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        item = BaseBlock.get(selection.target_uuids[0]) if selection.target_uuids else None
        if not isinstance(item, BaseItem) or not {WATER_PUMP_TAG, DRY_TAP_TAG}.intersection(item.tags):
            return "No pump here"
        return None

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        fixture = BaseBlock.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None
        if not isinstance(entity, Entity) or not isinstance(fixture, BaseItem):
            return execution_event.cancel(status_message="No pump here")
        effect = execution_event.phase_to(EventPhase.EFFECT)
        if WATER_PUMP_TAG not in fixture.tags:
            return effect.with_updates(status_message=f"Nothing comes out of {fixture.name}")
        empty = next((item for item in entity.inventory.items.values() if item.item_id == EMPTY_WATERSKIN_ID), None)
        if empty is None:
            return effect.with_updates(status_message=f"Clean water gushes from {fixture.name} and drains away")
        full = build_waterskin(entity.uuid, full=True)
        if not entity.loot_item(full, parent_event=effect):
            full.remove_from_register()
            return effect.with_updates(status_message="The full waterskin cannot be carried")
        empty.retire(parent_event=effect)
        return effect.with_updates(status_message=f"{entity.name} fills a waterskin")
