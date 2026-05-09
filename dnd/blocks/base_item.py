"""Base item classes for the D&D engine items system.

BaseItem extends BaseBlock for floor objects, inventory items, and breakable objects.
EquippableItem adds equip/unequip lifecycle hooks.
UsableItem provides actions via get_use_actions() with charge tracking.
"""

from typing import Iterable, Optional, List, Literal, Tuple, cast
from uuid import UUID, uuid4
from enum import Enum
from pydantic import Field

from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.modifiers import DamageType
from dnd.core.gridmap import get_map
from dnd.core.events import EquipmentSlot, SpatialChangeEvent
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
    visual_item_name: Optional[str] = Field(
        default=None,
        description="Renderer item catalog key. Defaults to name when omitted."
    )
    visual_variant_id: Optional[str] = Field(
        default=None,
        description="Renderer sub-item variant id under visual_item_name."
    )

    # Tags for filtering/queries
    tags: List[str] = Field(default_factory=list)

    # Visibility/action discovery controls
    include_in_senses_objects: bool = Field(default=True, description="Whether entity senses should list this floor object")
    include_in_adjacent_senses_objects: bool = Field(default=False, description="Whether adjacent entities can sense this floor object without cell visibility")
    include_in_available_object_actions: bool = Field(default=True, description="Whether object/use action discovery should consider this floor object")

    # Spatial properties (for floor items)
    blocks_movement: bool = Field(default=False, description="Blocks entity movement when on grid")
    blocks_vision_field: bool = Field(default=False, description="Blocks line of sight when on grid")
    blocks_movement_north: bool = Field(default=False, description="Blocks movement crossing north from this tile")
    blocks_movement_south: bool = Field(default=False, description="Blocks movement crossing south from this tile")
    blocks_movement_east: bool = Field(default=False, description="Blocks movement crossing east from this tile")
    blocks_movement_west: bool = Field(default=False, description="Blocks movement crossing west from this tile")
    blocks_vision_north: bool = Field(default=False, description="Blocks vision crossing north from this tile")
    blocks_vision_south: bool = Field(default=False, description="Blocks vision crossing south from this tile")
    blocks_vision_east: bool = Field(default=False, description="Blocks vision crossing east from this tile")
    blocks_vision_west: bool = Field(default=False, description="Blocks vision crossing west from this tile")
    blocks_light_north: bool = Field(default=False, description="Blocks light crossing north from this tile")
    blocks_light_south: bool = Field(default=False, description="Blocks light crossing south from this tile")
    blocks_light_east: bool = Field(default=False, description="Blocks light crossing east from this tile")
    blocks_light_west: bool = Field(default=False, description="Blocks light crossing west from this tile")
    blocks_propagation_north: bool = Field(default=False, description="Blocks physical propagation crossing north from this tile")
    blocks_propagation_south: bool = Field(default=False, description="Blocks physical propagation crossing south from this tile")
    blocks_propagation_east: bool = Field(default=False, description="Blocks physical propagation crossing east from this tile")
    blocks_propagation_west: bool = Field(default=False, description="Blocks physical propagation crossing west from this tile")

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

    def get_map_char(self) -> Optional[str]:
        return self.map_char

    def should_include_in_senses_objects(self) -> bool:
        return self.include_in_senses_objects

    def should_include_in_adjacent_senses_objects(self) -> bool:
        return self.include_in_adjacent_senses_objects

    def should_include_in_available_object_actions(self) -> bool:
        return self.include_in_available_object_actions

    def _blocks_direction(self, channel: str, direction: str) -> bool:
        if channel == "movement":
            if direction == "north":
                return self.blocks_movement_north
            if direction == "south":
                return self.blocks_movement_south
            if direction == "east":
                return self.blocks_movement_east
            if direction == "west":
                return self.blocks_movement_west
        elif channel == "vision":
            if direction == "north":
                return self.blocks_vision_north
            if direction == "south":
                return self.blocks_vision_south
            if direction == "east":
                return self.blocks_vision_east
            if direction == "west":
                return self.blocks_vision_west
        elif channel == "light":
            if direction == "north":
                return self.blocks_light_north
            if direction == "south":
                return self.blocks_light_south
            if direction == "east":
                return self.blocks_light_east
            if direction == "west":
                return self.blocks_light_west
        elif channel == "propagation":
            if direction == "north":
                return self.blocks_propagation_north
            if direction == "south":
                return self.blocks_propagation_south
            if direction == "east":
                return self.blocks_propagation_east
            if direction == "west":
                return self.blocks_propagation_west
        return False

    def _set_directional_blocking_field(self, channel: str, direction: str, blocked: bool) -> bool:
        old_value = self._blocks_direction(channel, direction)
        if old_value == blocked:
            return False
        if channel == "movement":
            if direction == "north":
                self.blocks_movement_north = blocked
            elif direction == "south":
                self.blocks_movement_south = blocked
            elif direction == "east":
                self.blocks_movement_east = blocked
            elif direction == "west":
                self.blocks_movement_west = blocked
            else:
                return False
        elif channel == "vision":
            if direction == "north":
                self.blocks_vision_north = blocked
            elif direction == "south":
                self.blocks_vision_south = blocked
            elif direction == "east":
                self.blocks_vision_east = blocked
            elif direction == "west":
                self.blocks_vision_west = blocked
            else:
                return False
        elif channel == "light":
            if direction == "north":
                self.blocks_light_north = blocked
            elif direction == "south":
                self.blocks_light_south = blocked
            elif direction == "east":
                self.blocks_light_east = blocked
            elif direction == "west":
                self.blocks_light_west = blocked
            else:
                return False
        elif channel == "propagation":
            if direction == "north":
                self.blocks_propagation_north = blocked
            elif direction == "south":
                self.blocks_propagation_south = blocked
            elif direction == "east":
                self.blocks_propagation_east = blocked
            elif direction == "west":
                self.blocks_propagation_west = blocked
            else:
                return False
        else:
            return False
        return True

    def blocks_directional_movement(self, direction: str,
                                    requesting_entity_uuid: Optional[UUID] = None,
                                    mode: MovementMode = MovementMode.WALKING,
                                    subjective: bool = False) -> bool:
        """Whether this item blocks movement crossing a tile-relative direction."""
        return self._blocks_direction("movement", direction)

    def blocks_directional_vision(self, direction: str,
                                  observer_uuid: Optional[UUID] = None,
                                  subjective: bool = False) -> bool:
        """Whether this item blocks vision crossing a tile-relative direction."""
        return self._blocks_direction("vision", direction)

    def blocks_directional_light(self, direction: str,
                                 observer_uuid: Optional[UUID] = None,
                                 subjective: bool = False) -> bool:
        """Whether this item blocks light crossing a tile-relative direction."""
        return self._blocks_direction("light", direction)

    def blocks_directional_propagation(self, direction: str,
                                       requesting_entity_uuid: Optional[UUID] = None,
                                       subjective: bool = False) -> bool:
        """Whether this item blocks physical propagation crossing a tile-relative direction."""
        return self._blocks_direction("propagation", direction)

    def set_directional_blocking(self, channel: str, direction: str, blocked: bool,
                                 parent_event: Optional[UUID] = None) -> None:
        """Update one tile-relative directional blocker and notify the grid if placed."""
        if channel not in {"movement", "vision", "light", "propagation"}:
            raise ValueError(f"Unsupported directional blocking channel: {channel}")
        if direction not in {"north", "south", "east", "west"}:
            raise ValueError(f"Unsupported direction: {direction}")
        if self._set_directional_blocking_field(channel, direction, blocked):
            self._notify_blocking_changed(self.blocks_movement, self.blocks_vision_field, parent_event)

    def set_directional_blocking_bulk(
        self,
        updates: Iterable[Tuple[str, str, bool]],
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Apply multiple directional blocker updates and emit at most one spatial event."""
        normalized_updates = list(updates)
        for channel, direction, _blocked in normalized_updates:
            if channel not in {"movement", "vision", "light", "propagation"}:
                raise ValueError(f"Unsupported directional blocking channel: {channel}")
            if direction not in {"north", "south", "east", "west"}:
                raise ValueError(f"Unsupported direction: {direction}")

        changed = False
        for channel, direction, blocked in normalized_updates:
            changed = self._set_directional_blocking_field(channel, direction, blocked) or changed

        if changed:
            self._notify_blocking_changed(self.blocks_movement, self.blocks_vision_field, parent_event)

    def _notify_blocking_changed(self, old_blocks_movement: bool, old_blocks_vision: bool,
                                     parent_event: Optional[UUID] = None) -> None:
        """Fire SPATIAL_OBJECT_CHANGED if blocking state changed while on grid.

        Called after modifying blocks_movement or blocks_vision_field on an item
        that is placed on the grid. Fires an event with hint indicating which
        senses layers are affected, replacing brute-force update_all_entities_senses().

        Light recomputation is handled by GridMap's _on_vision_blocking_changed
        callback which reacts to any spatial event with requires_fov=True.
        """
        grid = get_map()
        position = grid.get_object_position(self.uuid)
        if position is None:
            return  # Not on grid
        vision_changed = self.blocks_vision_field != old_blocks_vision
        walking_changed = self.blocks_movement != old_blocks_movement
        directional_metadata = grid.recompute_tile_directional_blocking(position)
        directional_channels = directional_metadata.get("directional_channels") or []
        direction_changed = bool(directional_channels)
        if vision_changed or walking_changed or direction_changed:
            event = SpatialChangeEvent.object_changed(
                position, self.uuid,
                blocks_vision_changed=vision_changed or "vision" in directional_channels,
                blocks_walking_changed=walking_changed or "movement" in directional_channels,
                parent_event=parent_event,
                object_name=self.name,
                object_map_char=self.get_map_char(),
                object_blocks_movement=self.blocks_movement,
                object_blocks_vision=self.blocks_vision_field,
                object_is_open=self.get_spatial_open_state(),
                **directional_metadata,
            )
            grid._fire_spatial_event(event)

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

    def place_on_grid(self, position: Tuple[int, int]) -> None:
        """Place this item on the grid, setting tile_uuid and registering with GridMap."""
        grid = get_map()
        self.position = position
        tile = grid.get_tile(position[0], position[1])
        self.tile_uuid = tile.uuid if tile else None
        grid.place_object(self.uuid, position)

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
        # Clean up any light sources attached to this item
        gridmap = get_map()
        gridmap.cleanup_block_light_sources(self.uuid)
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

    @property
    def has_hp(self) -> bool:
        """Whether this item is intact. Non-breakable items always have HP."""
        if self.health is None:
            return True
        return self.get_hp() > 0

    @property
    def is_active(self) -> bool:
        """Item is active if intact (non-breakable = always active)."""
        return self.has_hp

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
        if not self.has_hp:
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
        self.equipped_slot = slot.value
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
    use_action_templates: List[BaseAction] = Field(default_factory=list)

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
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
