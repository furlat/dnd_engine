"""Base item classes for the D&D engine items system.

BaseItem extends BaseBlock for floor objects, inventory items, and breakable objects.
EquippableItem adds equip/unequip lifecycle hooks.
UsableItem provides actions via get_use_actions() with charge tracking.
"""

from typing import Optional, List, Literal, Tuple, cast
from uuid import UUID, uuid4
from enum import Enum
from pydantic import Field

from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.modifiers import DamageType
from dnd.core.gridmap import get_map
from dnd.core.events import EquipmentSlot
from dnd.blocks.health import Health, HealthConfig, HitDiceConfig
from dnd.core.base_actions import BaseAction


class ItemRarity(str, Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LEGENDARY = "legendary"


class BaseItem(BaseBlock):
    """Base class for all items in the game.

    Items are BaseBlocks that can exist on the grid (floor items), in inventories,
    or equipped on entities. They support conditions, spatial blocking, and breakability
    via optional Health composition.
    """

    # Items CAN hold conditions (BaseBlock defaults to False)
    allow_events_conditions: bool = Field(default=True)

    # Identity
    name: str = Field(default="Item")
    description: Optional[str] = Field(default=None)

    # Physical properties
    weight: float = Field(default=0.0, description="Weight in pounds")
    value: int = Field(default=0, description="Value in gold pieces")
    rarity: ItemRarity = Field(default=ItemRarity.COMMON)

    # Type flags
    is_pickable: bool = Field(default=True, description="Can be picked up by entities")
    is_equippable: bool = Field(default=False, description="Can be equipped")
    is_usable: bool = Field(default=False, description="Can be used (activate effect)")
    is_consumable: bool = Field(default=False, description="Destroyed on use")

    # Stacking
    stack_count: int = Field(default=1, ge=1)
    max_stack: int = Field(default=1, ge=1)
    stack_id: Optional[str] = Field(default=None, description="Items with same stack_id merge into one stack. None = never stacks.")

    # Display
    map_char: str = Field(default="\u03c6", description="Character to display on the map grid")

    # Tags for filtering/queries
    tags: List[str] = Field(default_factory=list)

    # Spatial properties (for floor items)
    blocks_movement: bool = Field(default=False, description="Blocks entity movement when on grid")
    blocks_vision_field: bool = Field(default=False, description="Blocks line of sight when on grid")

    # Breakable object support
    is_targetable: bool = Field(default=False, description="Can be targeted by attacks")
    health: Optional[Health] = Field(default=None, description="Health block for breakable items")

    # Equip tracking
    is_equipped: bool = Field(default=False, description="Whether this item is currently equipped")
    equipped_slot: Optional[str] = Field(default=None, description="Slot this item is equipped in")

    # Location tracking
    owner_uuid: Optional[UUID] = Field(default=None, description="UUID of the entity or item (e.g. chest) that owns this item")
    stored_in_uuid: Optional[UUID] = Field(default=None, description="UUID of the container block (Inventory, Equipment) holding this item")
    tile_uuid: Optional[UUID] = Field(default=None, description="UUID of tile at this item's grid position (set when on floor)")

    # --- Spatial overrides (BaseBlock polymorphism) ---

    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        """Whether this item blocks walking through its grid position."""
        return self.blocks_movement

    def blocks_vision(self, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        """Whether this item blocks line of sight through its grid position."""
        return self.blocks_vision_field

    # --- Location ---

    def get_position(self) -> Optional[Tuple[int, int]]:
        """Get effective position of this item.

        - Has owner → defer to owner's position
        - On floor (tile_uuid set) → own position
        - Nowhere → None
        """
        if self.owner_uuid is not None:
            owner = BaseBlock.get(self.owner_uuid)
            return owner.position if owner else None
        if self.tile_uuid is not None:
            return self.position
        return None

    # --- Lifecycle hooks ---

    def loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        """Called when item is picked up by an entity.

        Args:
            entity_uuid: UUID of the entity picking up the item
            inventory_uuid: UUID of the inventory receiving the item
        """
        self._on_loot(entity_uuid, inventory_uuid)

    def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        """Subclass override hook for pickup behavior."""
        pass

    def drop(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        """Called when item is dropped from inventory.

        Args:
            entity_uuid: UUID of the entity dropping the item
            position: Grid position where the item was dropped
        """
        self._on_drop(entity_uuid, position)

    def _on_drop(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        """Subclass override hook for drop behavior."""
        pass

    def destroy(self) -> None:
        """Destroy this item: fire hook, clean up conditions, remove from container, clear location, unregister."""
        self._on_destroy()
        for cond_name in list(self.active_conditions.keys()):
            self.remove_condition(cond_name)
        # Remove from container via proper polymorphism (BaseBlock.remove_contained_item)
        if self.stored_in_uuid is not None:
            container = BaseBlock.get(self.stored_in_uuid)
            if container is not None:
                container.remove_contained_item(self.uuid)
        self.owner_uuid = None
        self.stored_in_uuid = None
        self.tile_uuid = None
        self.is_equipped = False
        self.equipped_slot = None
        gridmap = get_map()
        if gridmap.get_object_position(self.uuid) is not None:
            gridmap.remove_object(self.uuid)
        BaseBlock._registry.pop(self.uuid, None)

    def _on_destroy(self) -> None:
        """Subclass override hook for destruction behavior."""
        pass

    # --- Health delegation ---

    def is_breakable(self) -> bool:
        """Whether this item can be damaged and destroyed."""
        return self.is_targetable and self.health is not None

    def get_hp(self) -> int:
        """Get current hit points (0 constitution modifier for items)."""
        if self.health is None:
            return 0
        return self.health.get_total_hit_points(0)

    def get_max_hp(self) -> int:
        """Get maximum hit points (0 constitution modifier for items)."""
        if self.health is None:
            return 0
        return self.health.get_max_hit_dices_points(0)

    def receive_damage(self, amount: int, damage_type: DamageType, source_uuid: UUID) -> int:
        """Apply damage to this item. Health block handles resistances/immunities.

        Returns actual damage dealt. Destroys item if HP reaches 0.
        """
        if self.health is None:
            return 0
        actual = self.health.take_damage(amount, damage_type, source_uuid)
        if self.get_hp() <= 0:
            self.destroy()
        return actual

    # --- Factory helper ---

    @staticmethod
    def create_item_health(
        source_uuid: UUID,
        hp: int,
        hit_dice_value: int = 8,
        immunities: Optional[List[DamageType]] = None,
        resistances: Optional[List[DamageType]] = None,
        vulnerabilities: Optional[List[DamageType]] = None
    ) -> Health:
        """Create a Health block for a breakable item.

        Defaults: immune to poison and psychic damage.
        Uses 'maximums' mode so HP = hit_dice_count * hit_dice_value exactly.
        """
        if immunities is None:
            immunities = [DamageType.POISON, DamageType.PSYCHIC]
        # Calculate hit dice count to reach desired HP
        hit_dice_count = max(1, hp // hit_dice_value)
        dice_val = cast(Literal[4, 6, 8, 10, 12], hit_dice_value)
        config = HealthConfig(
            hit_dices=[HitDiceConfig(
                hit_dice_value=dice_val,
                hit_dice_count=hit_dice_count,
                mode="maximums"
            )],
            immunities=immunities,
            resistances=resistances or [],
            vulnerabilities=vulnerabilities or [],
        )
        return Health.create(source_entity_uuid=source_uuid, config=config)


class EquippableItem(BaseItem):
    """Base class for equippable items. Provides equip/unequip lifecycle hooks."""
    is_equippable: bool = Field(default=True)
    is_pickable: bool = Field(default=True)

    def equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Called by Equipment.equip() after slot assignment.

        Sets equipped tracking fields, clears floor placement if item was on ground,
        then calls the subclass hook.
        """
        self.is_equipped = True
        self.equipped_slot = slot.value if hasattr(slot, 'value') else str(slot)
        # Clear floor placement if item was on ground (direct equip from floor)
        if self.tile_uuid is not None:
            gridmap = get_map()
            if gridmap.get_object_position(self.uuid) is not None:
                gridmap.remove_object(self.uuid)
            self.tile_uuid = None
        self._on_equip(slot, entity_uuid)

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Override in subclasses for equip behavior.

        Three valid approaches:
        1. Direct modifiers on entity's ModifiableValues
        2. Direct action registration on entity
        3. Condition pattern (for complex effects with auto-cleanup)
        """
        pass

    def unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Called by Equipment.unequip() before slot is cleared.

        Calls the subclass hook then clears equipped tracking fields.
        stored_in_uuid is NOT cleared — the caller decides where the item goes next.
        """
        self._on_unequip(slot, entity_uuid)
        self.is_equipped = False
        self.equipped_slot = None

    def _on_unequip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Override in subclasses. Clean up everything _on_equip set up."""
        pass


class UsableItem(BaseItem):
    """Items that provide actions via get_use_actions().

    Two usage patterns:
    1. Default: populate use_action_templates field, get_use_actions() returns
       them with owner_uuid injected. Good for simple items.
    2. Override: subclass get_use_actions() for state-dependent/adaptive behavior.

    Charges: -1 = unlimited. 0 = depleted (no actions returned).
    """
    is_usable: bool = Field(default=True)

    # Charges
    charges: int = Field(default=-1, description="Number of uses remaining (-1 = unlimited, 0 = depleted)")
    max_charges: int = Field(default=-1, description="Maximum charges (-1 = unlimited)")

    # Stored action templates — default get_use_actions() returns these
    use_action_templates: List["BaseAction"] = Field(default_factory=list)

    def get_use_actions(self, user_entity_uuid: UUID) -> List["BaseAction"]:
        """Return action templates this item provides.

        Default: returns stored templates with source_entity_uuid and
        source_item_uuid injected. Returns [] if charges == 0.
        Override in subclasses for adaptive behavior.
        """
        if self.charges == 0:
            return []
        result = []
        for template in self.use_action_templates:
            action = template.model_copy(deep=True, update={
                'uuid': uuid4(),
                'source_entity_uuid': user_entity_uuid,
                'source_item_uuid': self.uuid,
            })
            result.append(action)
        return result

    def consume_charge(self, amount: int = 1) -> bool:
        """Consume charges. Returns False if not enough charges remain.

        Stack-aware: when stack_count > 1 and charges deplete, pops one from
        the stack (decrement count, reset charges) instead of destroying.
        Override for custom charge logic (e.g., recharge on rest).
        """
        if self.charges == -1:
            return True  # Unlimited
        if self.charges < amount:
            return False
        self.charges -= amount
        if self.charges == 0 and self.is_consumable:
            if self.stack_count > 1:
                self.stack_count -= 1
                self.charges = self.max_charges  # reset for next copy in stack
            else:
                self.destroy()
        return True
