"""Base item classes for the D&D engine items system.

BaseItem extends BaseBlock for floor objects, inventory items, and breakable objects.
EquippableItem adds equip/unequip lifecycle hooks.
UsableItem provides actions via get_use_actions() with charge tracking.
"""

from typing import Optional, List, Literal, Tuple, cast
from uuid import UUID, uuid4
from pydantic import Field, model_validator

from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.creature_types import DamageType
from dnd.core.gridmap import get_map
from dnd.core.events import (
    Damage,
    Event,
    EventPhase,
    EventType,
    SpatialChangeEvent,
    TakeDamageEvent,
)
from dnd.core.equipment_types import EquipmentSlot
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementSpec
from dnd.core.item_types import (
    EquippedVisualPolicy,
    ItemLocation,
    ItemPresentationKind,
    ItemPresentationState,
    ItemRarity,
)
from dnd.blocks.health import Health, HealthConfig, HitDiceConfig
from dnd.core.base_actions import BaseAction
from dnd.core.content.identities import validate_namespaced_id
from dnd.core.content.runtime import (
    RuntimeBehaviorKind,
    bind_runtime_behavior_child,
)


class ItemLocationStateEvent(Event):
    """Post-commit, idempotent item placement and presentation fact."""

    name: str = Field(default="Item Location State", description="Item location-state fact label.")
    event_type: EventType = Field(
        default=EventType.ITEM_LOCATION_STATE,
        description="Event category for authoritative item location snapshots.",
    )
    item_state: ItemPresentationState = Field(
        description="Cold item presentation/state required to materialize this item."
    )
    location: ItemLocation = Field(description="Authoritative item placement after the mutation.")
    owner_uuid: Optional[UUID] = Field(
        default=None,
        description="Owning entity or container item UUID after the mutation.",
    )
    container_uuid: Optional[UUID] = Field(
        default=None,
        description="Inventory or equipment block UUID after the mutation.",
    )
    tile_uuid: Optional[UUID] = Field(default=None, description="Floor tile UUID after the mutation.")
    position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Floor position after the mutation.",
    )
    world_placement: Optional[WorldObjectPlacement] = Field(
        default=None,
        description="Exact center/boundary floor placement after the mutation.",
    )
    equipment_slot: Optional[EquipmentSlot] = Field(
        default=None,
        description="Occupied equipment slot when location is equipment.",
    )
    merged_into_item_uuid: Optional[UUID] = Field(
        default=None,
        description="Surviving stack UUID when this item was fully merged.",
    )
    entity_armor_class_after: Optional[int] = Field(
        default=None,
        ge=0,
        description="Exact aggregate owner AC after an entity-owned mutation.",
    )

    @model_validator(mode="after")
    def validate_floor_placement(self) -> "ItemLocationStateEvent":
        if self.location is ItemLocation.FLOOR:
            if self.world_placement is None:
                raise ValueError("floor item facts require world_placement")
            if self.world_placement.object_uuid != self.item_state.item_uuid:
                raise ValueError("world placement must identify the item")
            if (
                self.tile_uuid != self.world_placement.tile_uuid
                or self.position != self.world_placement.position
            ):
                raise ValueError("floor item coordinates must match world_placement")
        elif self.world_placement is not None:
            raise ValueError("non-floor item facts cannot define world_placement")
        return self


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
    item_id: str = Field(
        frozen=True,
        description="Direct authored item species identity.",
    )
    content_kind: RuntimeBehaviorKind = Field(
        default=RuntimeBehaviorKind.ITEM,
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
    blocks_optics_field: bool = Field(default=False, description="Blocks ordinary optics when on grid")
    blocks_propagation_field: bool = Field(default=False, description="Blocks physical propagation when on grid")
    is_targetable: bool = Field(default=False, description="Can be targeted by attacks")
    health: Optional[Health] = Field(default=None, description="Health block for breakable items")
    is_equipped: bool = Field(default=False, description="Whether this item is currently equipped")
    equipped_slot: Optional[str] = Field(default=None, description="Slot this item is equipped in")
    owner_uuid: Optional[UUID] = Field(default=None, description="UUID of the entity or item (e.g. chest) that owns this item")
    stored_in_uuid: Optional[UUID] = Field(default=None, description="UUID of the container block (Inventory, Equipment) holding this item")
    tile_uuid: Optional[UUID] = Field(default=None, description="UUID of tile at this item's grid position (set when on floor)")

    @model_validator(mode="after")
    def validate_item_id(self) -> "BaseItem":
        validate_namespaced_id(self.item_id, "item_id")
        return self

    def to_item_presentation_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemPresentationState:
        """Return a cold presentation/state payload owned by this item.

        Concrete item families extend this common payload with their own
        weapon, armor, shield, or finite-use facts. No transport/server model
        participates in this engine contract.
        """
        return ItemPresentationState(
            item_uuid=self.uuid,
            item_id=self.item_id,
            name=self.name,
            description=self.description,
            item_kind=ItemPresentationKind.ITEM,
            rarity=self.rarity,
            weight=self.weight,
            value=self.value,
            tags=tuple(self.tags),
            is_pickable=self.is_pickable,
            is_equippable=self.is_equippable,
            is_usable=self.is_usable,
            is_targetable=self.is_targetable,
            stack_id=self.stack_id,
            visual_item_name=self.visual_item_name or self.name,
            visual_variant_id=self.visual_variant_id,
            equipped_visual_policy=self.equipped_visual_policy,
            stack_count=self.stack_count if stack_count is None else stack_count,
            max_stack=self.max_stack,
            is_consumable=self.is_consumable,
            map_char=self.map_char,
            include_in_senses_objects=self.include_in_senses_objects,
            include_in_adjacent_senses_objects=(
                self.include_in_adjacent_senses_objects
            ),
            include_in_available_object_actions=(
                self.include_in_available_object_actions
            ),
            current_hit_points=(
                max(0, self.get_hp()) if self.health is not None else None
            ),
            maximum_hit_points=(
                self.get_max_hp() if self.health is not None else None
            ),
            boundary_structure=self.get_boundary_structure(),
            is_open=self.get_spatial_open_state(),
            blocks_movement=self.blocks_walking(),
            blocks_optics=self.blocks_optics_at_center(),
            blocks_propagation=self.blocks_propagation(),
        )

    def publish_location_state(
        self,
        location: ItemLocation,
        *,
        owner_uuid: Optional[UUID] = None,
        container_uuid: Optional[UUID] = None,
        tile_uuid: Optional[UUID] = None,
        position: Optional[Tuple[int, int]] = None,
        world_placement: Optional[WorldObjectPlacement] = None,
        equipment_slot: Optional[EquipmentSlot] = None,
        merged_into_item_uuid: Optional[UUID] = None,
        entity_armor_class_after: Optional[int] = None,
        stack_count: Optional[int] = None,
        source_entity_uuid: Optional[UUID] = None,
        parent_event: Optional[Event] = None,
    ) -> ItemLocationStateEvent:
        """Publish one non-vetoable completion fact after location has committed."""
        source_uuid = source_entity_uuid or owner_uuid or self.source_entity_uuid
        if location is ItemLocation.FLOOR and world_placement is None:
            world_placement = get_map().get_object_placement(self.uuid)
        if world_placement is not None:
            tile_uuid = world_placement.tile_uuid
            position = world_placement.position
        declaration = ItemLocationStateEvent(
            source_entity_uuid=source_uuid,
            target_entity_uuid=owner_uuid,
            parent_event=parent_event.uuid if parent_event is not None else None,
            item_state=self.to_item_presentation_state(stack_count=stack_count),
            location=location,
            owner_uuid=owner_uuid,
            container_uuid=container_uuid,
            tile_uuid=tile_uuid,
            position=position,
            world_placement=world_placement,
            equipment_slot=equipment_slot,
            merged_into_item_uuid=merged_into_item_uuid,
            entity_armor_class_after=entity_armor_class_after,
            use_register=False,
        )
        execution = declaration.phase_to(EventPhase.EXECUTION)
        effect = execution.phase_to(EventPhase.EFFECT)
        return effect.phase_to(EventPhase.COMPLETION, use_register=True)

    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        """Whether this item blocks walking through its grid position."""
        return self.blocks_movement

    def blocks_optics_at_center(self) -> bool:
        """Whether this item blocks ordinary optics through its grid position."""
        return self.blocks_optics_field

    def blocks_propagation(self) -> bool:
        """Whether this item blocks physical propagation through its grid position."""
        return self.blocks_propagation_field

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

    def get_storage_block(self) -> Optional[BaseBlock]:
        """Return this item's canonical contained-item storage, when present."""
        return None

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

    def _notify_blocking_changed(
        self,
        old_blocks_movement: bool,
        old_blocks_optics: bool,
        old_blocks_propagation: bool,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Fire SPATIAL_OBJECT_CHANGED if blocking state changed while on grid.

        Called after modifying center movement, optical, or propagation policy
        that is placed on the grid. Fires an event with hint indicating which
        senses layers are affected, replacing brute-force update_all_entities_senses().

        Light recomputation is handled by GridMap after the committed optical
        change event.
        """
        grid = get_map()
        position = grid.get_object_position(self.uuid)
        if position is None:
            return
        optics_changed = self.blocks_optics_field != old_blocks_optics
        propagation_changed = (
            self.blocks_propagation_field != old_blocks_propagation
        )
        walking_changed = self.blocks_movement != old_blocks_movement
        revision_channels = set()
        if optics_changed:
            revision_channels.add("optical")
        if propagation_changed:
            revision_channels.add("propagation")
        if walking_changed:
            revision_channels.add("movement")
        grid.invalidate_spatial_caches(revision_channels)
        if optics_changed or propagation_changed or walking_changed:
            event = SpatialChangeEvent.object_changed(
                position, self.uuid,
                blocks_optics_changed=optics_changed,
                blocks_propagation_changed=propagation_changed,
                blocks_walking_changed=walking_changed,
                parent_event=parent_event,
                object_name=self.name,
                object_map_char=self.get_map_char(),
                object_blocks_movement=self.blocks_movement,
                object_blocks_optics=self.blocks_optics_field,
                object_blocks_propagation=self.blocks_propagation_field,
                object_is_open=self.get_spatial_open_state(),
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

    def place_on_grid(
        self,
        position: Tuple[int, int],
        *,
        boundary_direction: Optional[CardinalDirection] = None,
        base_height_steps: Optional[int] = None,
        orientation: Optional[CardinalDirection] = None,
        parent_event: Optional[UUID] = None,
    ) -> WorldObjectPlacement:
        """Place this item through GridMap's exact placement contract."""
        placement = get_map().place_object(
            self.uuid,
            position,
            parent_event=parent_event,
            boundary_direction=boundary_direction,
            base_height_steps=base_height_steps,
            orientation=orientation,
        )
        self.synchronize_floor_placement(placement)
        return placement

    def synchronize_floor_placement(
        self,
        placement: Optional[WorldObjectPlacement],
    ) -> None:
        """Mirror one already-committed GridMap placement or its absence."""
        if placement is None:
            self.tile_uuid = None
            return
        self.position = placement.position
        self.tile_uuid = placement.tile_uuid

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

    def destroy(self, parent_event: Optional[Event] = None) -> None:
        """Destroy this item and remove every owned runtime registration.

        The destruction hook runs before cleanup while subclasses can still
        inspect the item's container and floor location. After the hook, cleanup
        removes attached light, active conditions, container membership, floor
        placement, equipment flags, and registry state.
        """
        previous_owner_uuid = self.owner_uuid
        previous_owner = (
            BaseBlock.get(previous_owner_uuid)
            if previous_owner_uuid is not None
            else None
        )
        self._on_destroy(parent_event)
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
            gridmap.remove_object(
                self.uuid,
                parent_event=(parent_event.uuid if parent_event is not None else None),
            )
        owner_published = (
            previous_owner.on_owned_item_destroyed(self, parent_event=parent_event)
            if previous_owner is not None
            else False
        )
        if not owner_published:
            self.publish_location_state(
                ItemLocation.DESTROYED,
                owner_uuid=previous_owner_uuid,
                stack_count=0,
                parent_event=parent_event,
            )
        BaseBlock._registry.pop(self.uuid, None)

    def _on_destroy(self, parent_event: Optional[Event]) -> None:
        """Subclass override hook with the accepted destruction cause."""
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

    def receive_damage(
        self,
        amount: int,
        damage_type: DamageType,
        source_uuid: UUID,
        parent_event: Optional[Event] = None,
    ) -> int:
        """Apply item damage through the existing damage-event lifecycle."""
        if self.health is None:
            return 0

        source = BaseBlock.get(source_uuid)
        damage_event = TakeDamageEvent(
            source_entity_uuid=source_uuid,
            source_entity_name=source.name if source is not None else None,
            target_entity_uuid=self.uuid,
            target_entity_name=self.name,
            total_damage=amount,
            damages=[
                Damage(
                    damage_type=damage_type,
                    dice_numbers=1,
                    damage_dice=4,
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=self.uuid,
                ),
            ],
            parent_event=parent_event.uuid if parent_event is not None else None,
            phase=EventPhase.DECLARATION,
        )
        damage_event = damage_event.phase_to(EventPhase.EXECUTION)
        if damage_event.canceled:
            return 0
        damage_event = damage_event.phase_to(EventPhase.EFFECT)
        if damage_event.canceled:
            return 0

        resolved_damage_type = (
            damage_event.damages[0].damage_type
            if damage_event.damages
            else damage_type
        )
        preview = self.health.preview_damage(
            damage_event.get_effective_damage(),
            resolved_damage_type,
            damage_event.normal_hit_point_damage_cap,
            declared_damage=damage_event.total_damage,
            normal_hit_points_available=max(0, self.get_hp()),
        )
        actual = self.health.apply_damage_preview(preview, source_uuid)
        if not self.has_hp:
            self.destroy(parent_event=damage_event)
        damage_event.phase_to(
            EventPhase.COMPLETION,
            final_damage=actual,
            resulting_hp=max(0, self.get_hp()),
            resolution=preview,
        )
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


class WorldItem(BaseItem):
    """Item with an explicitly authored world-placement capability."""

    world_placement_spec: WorldPlacementSpec = Field(frozen=True)

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        return self.world_placement_spec


class EquippableItem(BaseItem):
    """Base class for equippable items.

    Concrete gear declares its compatible and default slots here.  The
    :class:`Equipment` aggregate consumes that policy to validate and execute
    slot transactions; callers never need to identify concrete item classes.
    """

    is_equippable: bool = Field(default=True, description="Whether this item can be equipped.")
    is_pickable: bool = Field(default=True, description="Whether this item can be picked up.")

    def compatible_equipment_slots(self) -> Tuple[EquipmentSlot, ...]:
        """Return every slot this concrete item may occupy.

        Equippable subclasses must make the policy explicit.  An empty default
        is deliberately invalid for equipment assignment rather than silently
        accepting an arbitrary slot.
        """
        return ()

    def default_equipment_slot(self) -> Optional[EquipmentSlot]:
        """Return the unambiguous slot selected when a caller omits one."""
        return None

    def occupied_equipment_slots(
        self,
        selected_slot: EquipmentSlot,
    ) -> frozenset[EquipmentSlot]:
        """Declare the physical slot footprint for conflict resolution.

        Most gear occupies only its selected storage slot.  Concrete gear may
        widen the footprint (for example a two-handed melee weapon) while the
        Equipment aggregate remains responsible for resolving conflicts.
        """
        return frozenset((selected_slot,))

    def equipment_event_type(self, *, equipping: bool) -> EventType:
        """Return the public event category for this concrete gear family.

        Concrete equippable families own this classification alongside their
        slot policy, keeping the Equipment aggregate free of type switching.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must declare its equipment event type"
        )

    def incompatible_equipment_slot_message(self, slot: EquipmentSlot) -> str:
        """Describe why ``slot`` is outside this item's declared policy."""
        compatible = ", ".join(candidate.value for candidate in self.compatible_equipment_slots())
        return (
            f"{self.name} cannot be equipped in {slot.value}; "
            f"compatible slots: {compatible or 'none'}"
        )

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

    def bind_dynamic_use_action(self, action: BaseAction) -> BaseAction:
        """Bind one state-dependent action through this exact item provider.

        Static ``use_action_templates`` bind during canonical item
        materialization. Overrides of ``get_use_actions`` use this narrow
        admission method before returning actions constructed on demand.
        """
        bind_runtime_behavior_child(
            action,
            provided_by_id=self.item_id,
            origin_root_id=self.item_id,
            runtime_owner_uuid=self.uuid,
        )
        return action

    def to_item_presentation_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemPresentationState:
        """Add finite-use state to the common cold item presentation."""
        state = super().to_item_presentation_state(stack_count=stack_count)
        return state.model_copy(update={
            "item_kind": ItemPresentationKind.USABLE,
            "charges": self.charges,
            "max_charges": self.max_charges,
        })

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
        source_item_presentation = self.to_item_presentation_state()
        for template in self.use_action_templates:
            if self.charges != -1 and self.charges < template.charge_cost:
                continue
            action = template.model_copy(deep=True, update={
                'uuid': uuid4(),
                'source_entity_uuid': user_entity_uuid,
                'source_item_uuid': self.uuid,
                'source_item_presentation': source_item_presentation,
            })
            if action.behavior_binding is None:
                self.bind_dynamic_use_action(action)
            result.append(action)
        return result

    def consume_charge(
        self,
        amount: int = 1,
        parent_event: Optional[Event] = None,
    ) -> bool:
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
                self.destroy(parent_event=parent_event)
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
            parent_event: Stored action declaration that owns the pre-execution
                charge commitment.

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
            item_id=self.item_id,
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
        if not self.consume_charge(amount, parent_event=effect):
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
    item_id: str = Field(
        description="Direct authored identity of the consumed item.",
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
