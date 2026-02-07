"""Inventory block for entity item storage."""

from typing import Optional, List, Dict
from uuid import UUID
from pydantic import Field

from dnd.core.base_block import BaseBlock
from dnd.blocks.base_item import BaseItem


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
        """Check if item can be added (slot and weight limits)."""
        if self.max_slots is not None and self.item_count >= self.max_slots:
            return False
        if self.weight_capacity is not None:
            if self.total_weight + item.weight * item.stack_count > self.weight_capacity:
                return False
        return True

    def add_item(self, item: BaseItem) -> bool:
        """Add item to inventory. Returns False if capacity exceeded."""
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
