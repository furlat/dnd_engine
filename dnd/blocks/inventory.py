"""Inventory block for entity item storage."""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
from uuid import UUID
from pydantic import Field

from dnd.core.base_block import BaseBlock
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemLocation


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
                and self.stacks_are_compatible(existing, item)
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

    def would_merge(self, item: BaseItem) -> bool:
        """Return whether adding this item would mutate an existing stack."""
        return self._find_compatible_stack(item) is not None

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

    @staticmethod
    def stacks_are_compatible(left: BaseItem, right: BaseItem) -> bool:
        """Only identical cold recipes without live owned state may merge."""
        return (
            left.has_mergeable_stack_state() and right.has_mergeable_stack_state()
            and left.item_id == right.item_id
            and left.max_stack == right.max_stack
            and left.weight == right.weight
            and left.is_magical == right.is_magical
            and left.visual_item_name == right.visual_item_name
            and left.visual_variant_id == right.visual_variant_id
        )

    def _detach_item_from_previous_location(
        self, item: BaseItem, parent_event: Optional[UUID] = None,
    ) -> bool:
        """Admit floor removal before changing any container membership."""
        grid = get_map()
        prepared = None
        if grid.get_object_position(item.uuid) is not None:
            prepared = grid.prepare_object_removals((item.uuid,), parent_event)
            if prepared is None:
                return False
        if not self.can_add(item):
            if prepared is not None:
                grid.cancel_object_removals(prepared, "Inventory changed during transfer admission")
            return False
        previous_container = None
        if item.stored_in_uuid is not None and item.stored_in_uuid != self.uuid:
            previous_container = BaseBlock.get(item.stored_in_uuid)
            if previous_container is None:
                if prepared is not None:
                    grid.cancel_object_removals(prepared, "Previous container no longer exists")
                return False
        if previous_container is not None:
            previous_container.remove_contained_item(item.uuid)
        if prepared is not None:
            grid.commit_object_removals(prepared, parent_event=parent_event)
        item.tile_uuid = None
        return True

    def _stamp_item_location(self, item: BaseItem) -> None:
        """Stamp an item stack as stored in this inventory.

        Args:
            item: Item stack that survived insertion into this inventory.
        """
        item.source_entity_uuid = self.source_entity_uuid
        item.owner_uuid = self.source_entity_uuid
        item.stored_in_uuid = self.uuid

    def can_add(self, item: BaseItem) -> bool:
        """Check if item can be added (slot and weight limits).

        A compatible existing stack bypasses the slot check because no new item
        entry is required when the incoming stack fully merges.
        """
        if item.intrinsic_owner_uuid is not None or item.is_equipped:
            return False
        if self.items.get(item.uuid) is item:
            return True
        remainder_count = self._stack_remainder_count(item)
        needs_new_stack = remainder_count > 0
        if self.max_slots is not None and needs_new_stack and self.item_count >= self.max_slots:
            return False
        if self.weight_capacity is not None:
            if self.total_weight + item.weight * item.stack_count > self.weight_capacity:
                return False
        return True

    def can_add_all(
        self, items: Iterable[BaseItem], *, excluding: Iterable[UUID] = (),
    ) -> bool:
        """Check a finite displacement batch using virtual counts, without mutation."""
        excluded = set(excluding)
        stacks = [item for item in self.items.values() if item.uuid not in excluded]
        counts = {item.uuid: item.stack_count for item in stacks}
        weight = sum(item.weight * counts[item.uuid] for item in stacks)
        for item in items:
            if item.intrinsic_owner_uuid is not None:
                return False
            if item.uuid in counts:
                continue
            weight += item.weight * item.stack_count
            remainder = item.stack_count
            if item.stack_id is not None:
                for existing in stacks:
                    if (existing.stack_id == item.stack_id
                            and self.stacks_are_compatible(existing, item)
                            and counts[existing.uuid] < existing.max_stack):
                        amount = min(remainder, existing.max_stack - counts[existing.uuid])
                        counts[existing.uuid] += amount
                        remainder -= amount
                        break
            if remainder:
                stacks.append(item)
                counts[item.uuid] = remainder
            if self.max_slots is not None and len(stacks) > self.max_slots:
                return False
            if self.weight_capacity is not None and weight > self.weight_capacity:
                return False
        return True

    def validate_initial_items(self, items: Iterable[BaseItem]) -> None:
        """Validate a complete unpublished inventory without mutating it."""
        candidates = tuple(items)
        seen_uuids = set(self.items)
        seen_stack_ids = {
            item.stack_id
            for item in self.items.values()
            if item.stack_id is not None
        }
        for item in candidates:
            if item.intrinsic_owner_uuid is not None:
                raise ValueError("Intrinsic anatomy cannot be installed in inventory")
            if item.uuid in seen_uuids:
                raise ValueError(f"duplicate initial item UUID {item.uuid}")
            seen_uuids.add(item.uuid)
            if item.source_entity_uuid != self.source_entity_uuid:
                raise ValueError(
                    f"initial item {item.item_id} belongs to another entity",
                )
            if (
                item.owner_uuid is not None
                or item.stored_in_uuid is not None
                or item.tile_uuid is not None
                or item.is_equipped
                or item.equipped_slot is not None
            ):
                raise ValueError(
                    f"initial item {item.item_id} is already placed",
                )
            if item.stack_count > item.max_stack:
                raise ValueError(
                    f"initial item {item.item_id} exceeds its stack limit",
                )
            if item.stack_id is not None:
                if item.stack_id in seen_stack_ids:
                    raise ValueError(
                        f"duplicate initial stack {item.stack_id!r}",
                    )
                seen_stack_ids.add(item.stack_id)

        if (
            self.max_slots is not None
            and self.item_count + len(candidates) > self.max_slots
        ):
            raise ValueError("initial items exceed inventory slot capacity")
        added_weight = sum(
            item.weight * item.stack_count
            for item in candidates
        )
        if (
            self.weight_capacity is not None
            and self.total_weight + added_weight > self.weight_capacity
        ):
            raise ValueError("initial items exceed inventory weight capacity")

    def install_initial_items(self, items: Iterable[BaseItem]) -> None:
        """Install validated initial holdings without publishing Events."""
        candidates = tuple(items)
        self.validate_initial_items(candidates)
        for item in candidates:
            result = self.add_item_with_result(item)
            if not result.succeeded or result.inserted_item is not item:
                raise RuntimeError("validated initial inventory commit diverged")

    def add_item_with_result(
        self, item: BaseItem, *, parent_event: Optional[UUID] = None,
    ) -> InventoryAddResult:
        """Add an item stack atomically and return every changed stack.

        If fully merged, the consumed item is unregistered and
        ``inserted_item`` is ``None``. A partial merge returns both the updated
        existing stack and the surviving incoming stack, allowing a high-level
        owner to publish exact post-commit facts without scanning the inventory.
        """
        if not self.can_add(item):
            return InventoryAddResult(succeeded=False)

        previous_owner_uuid = item.owner_uuid
        previous_container_uuid = item.stored_in_uuid
        if not self._detach_item_from_previous_location(item, parent_event):
            return InventoryAddResult(succeeded=False)
        existing = self._find_compatible_stack(item)
        if existing is not None:
            space = existing.max_stack - existing.stack_count
            transfer = min(space, item.stack_count)
            existing.stack_count += transfer
            item.stack_count -= transfer
            if item.stack_count == 0:
                self._clear_consumed_item_location(item)
                BaseBlock._registry.pop(item.uuid, None)
                if (previous_owner_uuid is not None and previous_container_uuid is not None
                        and previous_owner_uuid != self.source_entity_uuid):
                    item.publish_holdings_release(previous_owner_uuid, previous_container_uuid,
                        parent_event=parent_event)
                return InventoryAddResult(
                    succeeded=True,
                    merged_into_item=existing,
                )

        self.items[item.uuid] = item
        self._stamp_item_location(item)
        if (previous_owner_uuid is not None and previous_container_uuid is not None
                and previous_owner_uuid != self.source_entity_uuid):
            item.publish_holdings_release(previous_owner_uuid, previous_container_uuid,
                parent_event=parent_event)
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
            True when admission succeeds; rejection leaves the source intact.
        """
        item = self.items.get(item_uuid)
        if item is None:
            return False
        result = target.add_item_with_result(item)
        if not result.succeeded:
            return False
        if result.merged_into_item is not None:
            result.merged_into_item.publish_location_state(
                ItemLocation.INVENTORY, owner_uuid=target.source_entity_uuid,
                container_uuid=target.uuid,
            )
        if result.inserted_item is not None:
            result.inserted_item.publish_location_state(
                ItemLocation.INVENTORY, owner_uuid=target.source_entity_uuid,
                container_uuid=target.uuid,
            )
        else:
            item.publish_location_state(
                ItemLocation.MERGED, stack_count=0,
                merged_into_item_uuid=result.merged_into_item.uuid if result.merged_into_item is not None else None,
            )
        return True
