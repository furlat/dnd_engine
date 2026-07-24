"""Inventory block for entity item storage."""

from dataclasses import dataclass
from typing import Optional, List, Dict
from uuid import UUID
from pydantic import Field

from dnd.core.base_block import BaseBlock
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.gridmap import get_map


@dataclass(frozen=True)
class InventoryAddResult:
    """Exact result of accepting one item stack into an inventory."""

    succeeded: bool
    inserted_item: Optional[BaseItem] = None
    merged_into_item: Optional[BaseItem] = None


class Inventory(BaseBlock):
    """Container for items held by an entity.

    Inventory is a low-level storage block. It can enforce optional weight and
    slot limits, merge compatible stacks, surface usable item actions, and move
    items to another inventory.
    """

    name: str = Field(default="Inventory", description="Display name for this inventory.")
    items: Dict[UUID, BaseItem] = Field(
        default_factory=dict,
        description="Stored item stacks keyed by item UUID.",
    )
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

    def _find_compatible_stack(self, item: BaseItem) -> Optional[BaseItem]:
        """Return the first compatible stack with room for more items."""
        if item.stack_id is None:
            return None
        for existing in self.items.values():
            if (
                existing.uuid != item.uuid
                and existing.stack_id == item.stack_id
                and existing.stack_count < existing.max_stack
            ):
                return existing
        return None

    def _stack_remainder_count(self, item: BaseItem) -> int:
        """Return count that would remain after merging into one stack."""
        existing = self._find_compatible_stack(item)
        if existing is None:
            return item.stack_count
        return max(0, item.stack_count - (existing.max_stack - existing.stack_count))

    @staticmethod
    def _clear_consumed_item_location(item: BaseItem) -> None:
        """Clear location fields from an item stack consumed by merging.

        Args:
            item: Consumed item stack whose count has reached zero.
        """
        item.owner_uuid = None
        item.stored_in_uuid = None
        item.tile_uuid = None
        item.is_equipped = False
        item.equipped_slot = None

    def _detach_item_from_previous_location(self, item: BaseItem) -> None:
        """Remove an item from its previous floor or container location.

        Args:
            item: Item being accepted into this inventory.
        """
        if item.stored_in_uuid is not None and item.stored_in_uuid != self.uuid:
            previous_container = BaseBlock.get(item.stored_in_uuid)
            if previous_container is not None:
                previous_container.remove_contained_item(item.uuid)
        gridmap = get_map()
        if gridmap.get_object_position(item.uuid) is not None:
            gridmap.remove_object(item.uuid)
        item.tile_uuid = None

    def _stamp_item_location(self, item: BaseItem) -> None:
        """Stamp an item stack as stored in this inventory.

        Args:
            item: Item stack that survived insertion into this inventory.
        """
        item.owner_uuid = self.source_entity_uuid
        item.stored_in_uuid = self.uuid

    def can_add(self, item: BaseItem) -> bool:
        """Check if item can be added (slot and weight limits).

        A compatible existing stack bypasses the slot check because no new item
        entry is required when the incoming stack fully merges.
        """
        remainder_count = self._stack_remainder_count(item)
        needs_new_stack = remainder_count > 0
        if self.max_slots is not None and needs_new_stack and self.item_count >= self.max_slots:
            return False
        if self.weight_capacity is not None:
            if self.total_weight + item.weight * item.stack_count > self.weight_capacity:
                return False
        return True

    def add_item_with_result(self, item: BaseItem) -> InventoryAddResult:
        """Add an item stack atomically and return every changed stack.

        If fully merged, the consumed item is unregistered and
        ``inserted_item`` is ``None``. A partial merge returns both the updated
        existing stack and the surviving incoming stack, allowing a high-level
        owner to publish exact post-commit facts without scanning the inventory.
        """
        if not self.can_add(item):
            return InventoryAddResult(succeeded=False)

        self._detach_item_from_previous_location(item)
        existing = self._find_compatible_stack(item)
        if existing is not None:
            space = existing.max_stack - existing.stack_count
            transfer = min(space, item.stack_count)
            existing.stack_count += transfer
            item.stack_count -= transfer
            if item.stack_count == 0:
                self._clear_consumed_item_location(item)
                BaseBlock._registry.pop(item.uuid, None)
                return InventoryAddResult(
                    succeeded=True,
                    merged_into_item=existing,
                )

        self.items[item.uuid] = item
        self._stamp_item_location(item)
        return InventoryAddResult(
            succeeded=True,
            inserted_item=item,
            merged_into_item=existing,
        )

    def add_item(self, item: BaseItem) -> bool:
        """Add an item stack while preserving the historical boolean API."""
        return self.add_item_with_result(item).succeeded

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
        """Aggregate use actions from all usable items in this inventory."""
        actions = []
        for item in self.items.values():
            if isinstance(item, UsableItem):
                actions.extend(item.get_use_actions(owner_uuid))
        return actions

    def transfer_to(self, item_uuid: UUID, target: 'Inventory') -> bool:
        """Transfer an item stack to another inventory.

        If the item fully merges into a target stack, the incoming object is
        consumed and its location fields remain clear.

        Args:
            item_uuid: UUID of the item stack in this inventory.
            target: Inventory receiving the item stack.

        Returns:
            True when the transfer or merge succeeds; otherwise False after
            rolling the source inventory back.
        """
        item = self.remove_item(item_uuid)
        if item is None:
            return False
        if not target.add_item(item):
            self.add_item(item)
            return False
        if target.has_item(item.uuid):
            item.owner_uuid = target.source_entity_uuid
            item.stored_in_uuid = target.uuid
        else:
            self._clear_consumed_item_location(item)
        return True
