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
from dnd.core.events import (
    EquipmentSlot,
    Event,
    EventPhase,
    EventType,
    SpatialChangeEvent,
)
from dnd.blocks.health import Health, HealthConfig, HitDiceConfig
from dnd.core.base_actions import ActionEvent, BaseAction
from dnd.core.content import ContentKind


class ItemRarity(str, Enum):
    """Rarity labels used by item data."""

    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LEGENDARY = "legendary"


class EquippedVisualPolicy(str, Enum):
    """Describe whether equipped gear contributes a separate actor layer."""

    VISIBLE = "visible"
    HIDDEN = "hidden"


class BaseItem(BaseBlock):
    """Base class for all items in the game.

    Items are BaseBlocks that can exist on the grid (floor items), in inventories,
    or equipped on entities. They support conditions, spatial blocking, and breakability
    via optional Health composition.
    """

    allow_events_conditions: bool = Field(
        default=True,
        description="Whether this item can own event handlers and active conditions.",
    )
    name: str = Field(default="Item", description="Display name for this item.")
    semantic_key: Optional[str] = Field(
        default=None,
        description="Stable rules-content identity; defaults to the item class identity.",
    )
    content_kind: ContentKind = Field(
        default=ContentKind.ITEM,
        description="Rules-content family represented by this item.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional rules or UI description for this item.",
    )
    weight: float = Field(default=0.0, description="Weight in pounds")
    value: int = Field(default=0, description="Value in gold pieces")
    rarity: ItemRarity = Field(
        default=ItemRarity.COMMON,
        description="Rarity category for this item.",
    )
    is_pickable: bool = Field(default=True, description="Can be picked up by entities")
    is_equippable: bool = Field(default=False, description="Can be equipped")
    is_usable: bool = Field(default=False, description="Can be used (activate effect)")
    is_consumable: bool = Field(default=False, description="Destroyed on use")
    stack_count: int = Field(
        default=1,
        ge=1,
        description="Number of copies represented by this item stack.",
    )
    max_stack: int = Field(
        default=1,
        ge=1,
        description="Maximum copies that can be merged into this stack.",
    )
    stack_id: Optional[str] = Field(
        default=None,
        description="Items with same stack_id merge into one stack. None = never stacks.",
    )
    map_char: str = Field(default="\u03c6", description="Character to display on the map grid")
    visual_item_name: Optional[str] = Field(
        default=None,
        description="Renderer item catalog key. Defaults to name when omitted.",
    )
    visual_variant_id: Optional[str] = Field(
        default=None,
        description="Renderer sub-item variant id under visual_item_name.",
    )
    equipped_visual_policy: EquippedVisualPolicy = Field(
        default=EquippedVisualPolicy.VISIBLE,
        description="Whether this item renders as a separate equipment layer while equipped.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Free-form tags used by item queries and filtering.",
    )
    include_in_senses_objects: bool = Field(default=True, description="Whether entity senses should list this floor object")
    include_in_adjacent_senses_objects: bool = Field(default=False, description="Whether adjacent entities can sense this floor object without cell visibility")
    include_in_available_object_actions: bool = Field(default=True, description="Whether object/use action discovery should consider this floor object")
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
    is_targetable: bool = Field(default=False, description="Can be targeted by attacks")
    health: Optional[Health] = Field(default=None, description="Health block for breakable items")
    is_equipped: bool = Field(default=False, description="Whether this item is currently equipped")
    equipped_slot: Optional[str] = Field(default=None, description="Slot this item is equipped in")
    owner_uuid: Optional[UUID] = Field(default=None, description="UUID of the entity or item (e.g. chest) that owns this item")
    stored_in_uuid: Optional[UUID] = Field(default=None, description="UUID of the container block (Inventory, Equipment) holding this item")
    tile_uuid: Optional[UUID] = Field(default=None, description="UUID of tile at this item's grid position (set when on floor)")

    def get_semantic_key(self) -> str:
        """Return an explicit key or the stable item class identity."""
        if self.semantic_key:
            return self.semantic_key
        return f"{type(self).__module__}.{type(self).__name__}"

    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        """Whether this item blocks walking through its grid position."""
        return self.blocks_movement

    def blocks_vision(self, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        """Whether this item blocks line of sight through its grid position."""
        return self.blocks_vision_field

    def get_map_char(self) -> Optional[str]:
        """Return the glyph used to render this item on text maps."""
        return self.map_char

    def should_include_in_senses_objects(self) -> bool:
        """Return whether senses should list this floor object."""
        return self.include_in_senses_objects

    def should_include_in_adjacent_senses_objects(self) -> bool:
        """Return whether adjacent-object sensing may include this item."""
        return self.include_in_adjacent_senses_objects

    def should_include_in_available_object_actions(self) -> bool:
        """Return whether object/action discovery may expose this item."""
        return self.include_in_available_object_actions

    def is_exposed_flame(self) -> bool:
        """Return whether this item currently presents an exposed flame."""
        return False

    def douse_exposed_flame(self, parent_event: Optional[UUID] = None) -> bool:
        """Douse this item's exposed flame, if any.

        Args:
            parent_event: Optional parent event UUID for light-removal lineage.

        Returns:
            True if a flame was doused.
        """
        return False

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
            return
        vision_changed = self.blocks_vision_field != old_blocks_vision
        walking_changed = self.blocks_movement != old_blocks_movement
        directional_metadata = grid.recompute_tile_directional_blocking(position)
        directional_channels = directional_metadata.get("directional_channels") or []
        direction_changed = bool(directional_channels)
        revision_channels = set(directional_channels)
        if vision_changed:
            revision_channels.update({"vision", "propagation"})
        if walking_changed:
            revision_channels.add("movement")
        grid.invalidate_spatial_caches(revision_channels)
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

    def get_position(self) -> Optional[Tuple[int, int]]:
        """Get effective position of this item.

        Owned items defer to the owner's position. Floor items use their own
        position only while `tile_uuid` is set. Unplaced items return `None`.
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

    def on_grid_object_removed(self, position: Tuple[int, int], clear_location: bool = True) -> None:
        """Synchronize floor-location fields after GridMap removes this item.

        Args:
            position: Grid position the item occupied before removal.
            clear_location: Whether the grid removal should clear item floor
                authority. Internal object reindexing passes `False`.
        """
        if clear_location and self.tile_uuid is not None:
            self.tile_uuid = None

    def loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        """Called when item is picked up by an entity.

        Args:
            entity_uuid: UUID of the entity picking up the item.
            inventory_uuid: UUID of the inventory receiving the item.
        """
        self._on_loot(entity_uuid, inventory_uuid)

    def _on_loot(self, entity_uuid: UUID, inventory_uuid: UUID) -> None:
        """Subclass override hook for pickup behavior."""
        pass

    def drop(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        """Called when item is dropped from inventory.

        Args:
            entity_uuid: UUID of the entity dropping the item.
            position: Grid position where the item was dropped.
        """
        self._on_drop(entity_uuid, position)

    def _on_drop(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        """Subclass override hook for drop behavior."""
        pass

    def destroy(self) -> None:
        """Destroy this item and remove every owned runtime registration.

        The destruction hook runs before cleanup while subclasses can still
        inspect the item's container and floor location. After the hook, cleanup
        removes attached light, active conditions, container membership, floor
        placement, equipment flags, and registry state.
        """
        self._on_destroy()
        gridmap = get_map()
        gridmap.cleanup_block_light_sources(self.uuid)
        for cond_name in list(self.active_conditions.keys()):
            self.remove_condition(cond_name)
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

        Args:
            source_uuid: UUID to assign as the health block source.
            hp: Desired item hit point total.
            hit_dice_value: Die size used for maximum-mode hit dice.
            immunities: Optional damage immunities. Defaults to poison and psychic.
            resistances: Optional damage resistances.
            vulnerabilities: Optional damage vulnerabilities.

        Returns:
            Health block configured with maximum-mode hit dice.
        """
        if immunities is None:
            immunities = [DamageType.POISON, DamageType.PSYCHIC]
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

    is_equippable: bool = Field(default=True, description="Whether this item can be equipped.")
    is_pickable: bool = Field(default=True, description="Whether this item can be picked up.")

    def equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Called by Equipment.equip() after slot assignment.

        Sets equipped tracking fields, clears floor placement if item was on ground,
        then calls the subclass hook.
        """
        self.is_equipped = True
        self.equipped_slot = slot.value
        if self.tile_uuid is not None:
            gridmap = get_map()
            if gridmap.get_object_position(self.uuid) is not None:
                gridmap.remove_object(self.uuid)
            self.tile_uuid = None
        self._on_equip(slot, entity_uuid)

    def _on_equip(self, slot: EquipmentSlot, entity_uuid: UUID) -> None:
        """Override in subclasses for equip behavior.

        Subclasses commonly install direct modifiers, register actions, or add
        a condition with its own cleanup tree.
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

    The default pattern stores action templates on `use_action_templates`.
    Subclasses can override `get_use_actions()` for state-dependent behavior.
    Charges use `-1` for unlimited and `0` for depleted.
    """

    is_usable: bool = Field(default=True, description="Whether this item exposes use actions.")
    charges: int = Field(default=-1, description="Number of uses remaining (-1 = unlimited, 0 = depleted)")
    max_charges: int = Field(default=-1, description="Maximum charges (-1 = unlimited)")
    use_action_templates: List[BaseAction] = Field(
        default_factory=list,
        description="Action templates cloned and rebound when this item is used.",
    )

    def remaining_finite_uses(self) -> Optional[int]:
        """Return total currently available uses represented by this stack.

        Returns:
            Remaining uses across the active item and stacked copies, or
            ``None`` when the item has unlimited charges.
        """
        if self.charges == -1:
            return None
        reserve_uses = (
            max(0, self.stack_count - 1) * max(0, self.max_charges)
            if self.stack_id is not None
            else 0
        )
        return self.charges + reserve_uses

    def maximum_finite_uses(self) -> Optional[int]:
        """Return the configured finite capacity represented by a full stack.

        Returns:
            Maximum uses for ``max_stack`` copies, or ``None`` for an
            unlimited-charge item.
        """
        if self.max_charges == -1:
            return None
        stack_capacity = self.max_stack if self.stack_id is not None else 1
        return stack_capacity * max(0, self.max_charges)

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
            if self.charges != -1 and self.charges < template.charge_cost:
                continue
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
            return True
        if self.charges < amount:
            return False
        self.charges -= amount
        if self.charges == 0 and self.is_consumable:
            if self.stack_count > 1:
                self.stack_count -= 1
                self.charges = self.max_charges
            else:
                self.destroy()
        return True

    def consume_charge_with_event(
        self,
        amount: int,
        source_entity_uuid: UUID,
        parent_event: Event,
    ) -> "ItemChargeConsumptionEvent":
        """Consume a finite charge through a child event lifecycle.

        Args:
            amount: Number of charges to consume.
            source_entity_uuid: Entity whose action spends the item resource.
            parent_event: Action effect that caused the charge consumption.

        Returns:
            Completed or canceled item-charge event.

        Raises:
            RuntimeError: If the item cannot pay a charge already validated by
                action discovery and execution.
        """
        declaration = ItemChargeConsumptionEvent(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=self.uuid,
            parent_event=parent_event.uuid,
            item_uuid=self.uuid,
            item_semantic_key=self.get_semantic_key(),
            item_name=self.name,
            amount=amount,
            charges_before=self.charges,
            charges_after=self.charges,
            stack_count_before=self.stack_count,
            stack_count_after=self.stack_count,
        )
        execution = declaration.phase_to(
            EventPhase.EXECUTION,
            status_message="Finite item resource validated",
        )
        effect = execution.phase_to(
            EventPhase.EFFECT,
            status_message="Finite item resource ready for consumption",
        )
        if effect.canceled:
            return effect
        if not self.consume_charge(amount):
            effect.cancel(status_message="Finite item resource changed after validation")
            raise RuntimeError(
                f"Item {self.uuid} could not consume {amount} charge after successful action"
            )
        return effect.phase_to(
            EventPhase.COMPLETION,
            status_message="Finite item resource consumption completed",
            charges_after=max(0, self.charges),
            stack_count_after=self.stack_count,
            item_destroyed=BaseBlock.get(self.uuid) is None,
        )


class ItemChargeConsumptionEvent(Event):
    """Finite usable-item resource consumption owned by the item domain."""

    name: str = Field(
        default="Item Charge Consumption",
        description="Human-readable item-resource event label.",
    )
    event_type: EventType = Field(
        default=EventType.ITEM_CHARGE_CONSUMPTION,
        description="Event category for finite item-resource consumption.",
    )
    item_uuid: UUID = Field(description="Usable item whose finite resource changes.")
    item_semantic_key: str = Field(
        default="item.unclassified",
        description="Stable semantic identity of the consumed item.",
    )
    item_name: str = Field(default="Item", description="Human-readable consumed item name.")
    amount: int = Field(default=1, ge=1, description="Number of charges consumed.")
    charges_before: int = Field(ge=0, description="Active-item charges before consumption.")
    charges_after: int = Field(ge=0, description="Active-item charges after consumption.")
    stack_count_before: int = Field(ge=1, description="Represented item copies before consumption.")
    stack_count_after: int = Field(ge=1, description="Represented item copies after consumption.")
    item_destroyed: bool = Field(
        default=False,
        description="Whether consumption removed the final item from engine registries.",
    )


def consume_item_charge_before_action_completion(event: Event) -> None:
    """Consume one item-bound action resource before its root lineage completes."""
    if not isinstance(event, ActionEvent):
        return
    if (
        event.source_item_uuid is None
        or event.item_charge_cost <= 0
        or event.item_charge_action_lineage_uuid != event.lineage_uuid
    ):
        return
    item = BaseBlock.get(event.source_item_uuid)
    if not isinstance(item, UsableItem) or item.charges == -1:
        return
    result = item.consume_charge_with_event(
        event.item_charge_cost,
        event.source_entity_uuid,
        event,
    )
    if result.canceled:
        raise RuntimeError(
            f"Item charge consumption was canceled for completed action lineage {event.lineage_uuid}"
        )
