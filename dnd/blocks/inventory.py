"""Inventory block for entity item storage."""

from typing import Optional, List, Dict
from uuid import UUID
from pydantic import Field

from dnd.core.base_block import BaseBlock
from dnd.blocks.base_item import BaseItem, UsableItem


class Inventory(BaseBlock):
    """Container for items held by an entity.

    Supports weight capacity, slot limits, and item transfer.
    """

    name: str = Field(default="Inventory")
    items: Dict[UUID, BaseItem] = Field(default_factory=dict)
    weight_capacity: Optional[float] = Field(default=None, description="Max carry weight in lbs (None = unlimited)")
    max_slots: Optional[int] = Field(default=None, description="Max number of item stacks (None = unlimited)")

    @property
    def total_weight(self) -> float:
        """Total weight of all items in inventory."""
        return sum(item.weight * item.stack_count for item in self.items.values())

    @property
    def item_count(self) -> int:
        """Number of item stacks in inventory."""
        return len(self.items)

    def can_add(self, item: BaseItem) -> bool:
        """Check if item can be added (slot and weight limits).

        Stack-aware: if item can merge into an existing stack, bypasses slot limit.
        """
        if item.stack_id is not None:
            for existing in self.items.values():
                if existing.stack_id == item.stack_id and existing.stack_count < existing.max_stack:
                    return True  # Can merge without needing a free slot
        if self.max_slots is not None and self.item_count >= self.max_slots:
            return False
        if self.weight_capacity is not None:
            if self.total_weight + item.weight * item.stack_count > self.weight_capacity:
                return False
        return True

    def add_item(self, item: BaseItem) -> bool:
        """Add item to inventory. Tries stack merge before insert.

        Returns False if capacity exceeded. If fully merged, the consumed item
        is unregistered from BaseBlock._registry.
        """
        # Try to merge into existing stack
        if item.stack_id is not None:
            for existing in self.items.values():
                if existing.stack_id == item.stack_id and existing.stack_count < existing.max_stack:
                    space = existing.max_stack - existing.stack_count
                    transfer = min(space, item.stack_count)
                    existing.stack_count += transfer
                    item.stack_count -= transfer
                    if item.stack_count == 0:
                        # Fully merged — unregister consumed item
                        BaseBlock._registry.pop(item.uuid, None)
                        return True
                    break  # Partial merge — fall through to insert remainder
        # No merge or partial: insert as new entry
        if not self.can_add(item):
            return False
        self.items[item.uuid] = item
        return True

    def remove_item(self, item_uuid: UUID) -> Optional[BaseItem]:
        """Remove and return item by UUID, or None if not found."""
        return self.items.pop(item_uuid, None)

    def has_item(self, item_uuid: UUID) -> bool:
        """Check if item is in inventory."""
        return item_uuid in self.items

    def find_items_by_name(self, name: str) -> List[BaseItem]:
        """Find all items with a given name."""
        return [item for item in self.items.values() if item.name == name]

    def find_items_by_tag(self, tag: str) -> List[BaseItem]:
        """Find all items with a given tag."""
        return [item for item in self.items.values() if tag in item.tags]

    def remove_contained_item(self, item_uuid: UUID) -> None:
        """Remove item from inventory items dict."""
        self.items.pop(item_uuid, None)

    def get_all_use_actions(self, owner_uuid: UUID) -> list:
        """Aggregate use actions from all UsableItems in inventory (Step d)."""
        actions = []
        for item in self.items.values():
            if isinstance(item, UsableItem):
                actions.extend(item.get_use_actions(owner_uuid))
        return actions

    def transfer_to(self, item_uuid: UUID, target: 'Inventory') -> bool:
        """Transfer item to another inventory. Returns False on failure (rollback).

        Updates owner_uuid and stored_in_uuid to reflect the new container.
        """
        item = self.remove_item(item_uuid)
        if item is None:
            return False
        if not target.add_item(item):
            self.add_item(item)  # rollback
            return False
        item.owner_uuid = target.source_entity_uuid
        item.stored_in_uuid = target.uuid
        return True
