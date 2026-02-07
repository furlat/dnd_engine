"""Base item classes for the D&D engine items system.

BaseItem extends BaseBlock for floor objects, inventory items, and breakable objects.
EquippableItem and UsableItem are thin stubs for future phases.
"""

from typing import Optional, List, Literal, cast
from uuid import UUID
from enum import Enum
from pydantic import Field

from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.modifiers import DamageType
from dnd.core.gridmap import get_map
from dnd.blocks.health import Health, HealthConfig, HitDiceConfig


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

    # Tags for filtering/queries
    tags: List[str] = Field(default_factory=list)

    # Spatial properties (for floor items)
    blocks_movement: bool = Field(default=False, description="Blocks entity movement when on grid")
    blocks_vision_field: bool = Field(default=False, description="Blocks line of sight when on grid")

    # Breakable object support
    is_targetable: bool = Field(default=False, description="Can be targeted by attacks")
    health: Optional[Health] = Field(default=None, description="Health block for breakable items")

    # Tracking
    equipped_slot: Optional[str] = Field(default=None, description="Slot this item is equipped in")

    # --- Spatial overrides (BaseBlock polymorphism) ---

    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        """Whether this item blocks walking through its grid position."""
        return self.blocks_movement

    def blocks_vision(self, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        """Whether this item blocks line of sight through its grid position."""
        return self.blocks_vision_field

    # --- Lifecycle hooks ---

    def loot(self) -> None:
        """Called when item is picked up by an entity."""
        self._on_loot()

    def _on_loot(self) -> None:
        """Subclass override hook for pickup behavior."""
        pass

    def drop(self) -> None:
        """Called when item is dropped from inventory."""
        self._on_drop()

    def _on_drop(self) -> None:
        """Subclass override hook for drop behavior."""
        pass

    def destroy(self) -> None:
        """Destroy this item: clean up conditions, remove from grid, unregister."""
        self._on_destroy()
        for cond_name in list(self.active_conditions.keys()):
            self.remove_condition(cond_name)
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
    """Base class for items that can be equipped. Stub for Phase 2."""
    is_equippable: bool = Field(default=True)
    is_pickable: bool = Field(default=True)


class UsableItem(BaseItem):
    """Base class for items that can be used/activated. Stub for Phase 2."""
    is_usable: bool = Field(default=True)
