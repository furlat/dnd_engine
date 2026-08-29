"""Base item classes for the D&D engine items system.

BaseItem extends BaseBlock for floor objects, inventory items, and breakable objects.
EquippableItem adds equip/unequip lifecycle hooks.
UsableItem provides actions via get_use_actions() with charge tracking.
"""

from typing import Optional, List, Tuple, cast
from uuid import UUID, uuid4
from pydantic import Field

from dnd.core.base_block import BaseBlock
from dnd.types.world import MovementMode
from dnd.types.damage import DamageType
from dnd.core.gridmap import get_map
from dnd.core.events.resolution_events import (
    Damage,
    TakeDamageEvent,
)
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.events.item_events import (
    ItemChargeConsumptionEvent,
    ItemLocationStateEvent,
    ItemState,
)
from dnd.types.equipment import EquipmentSlot
from dnd.types.rolls import HitDieSize
from dnd.types.items import (
    ItemChargeState,
    ItemKind,
    ItemLightSourceState,
    ItemLocation,
    ItemObservationState,
    ItemRarity,
)
from dnd.types.world_placement import BoundaryStructure, WorldObjectPlacement, WorldPlacementSpec
from dnd.blocks.health import Health, HealthConfig, HitDiceConfig
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.core.base_actions import (
    BaseAction,
)
from dnd.core.content.identities import ContentRef
from dnd.types.behaviors import RuntimeBehaviorKind


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
    content_ref: Optional[ContentRef] = Field(
        default=None,
        frozen=True,
        exclude=True,
        description="Exact authored definition used to construct this runtime item.",
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
    tags: List[str] = Field(
        default_factory=list,
        description="Free-form tags used by item queries and filtering.",
    )
    include_in_senses_objects: bool = Field(default=True, description="Whether entity senses should list this floor object")
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

    def get_semantic_key(self) -> str:
        """Return an explicit key or the stable item class identity."""
        if self.content_ref is not None:
            return self.content_ref.identity_key
        if self.semantic_key:
            return self.semantic_key
        return f"{type(self).__module__}.{type(self).__name__}"

    def to_item_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemState:
        """Capture the item's renderer-independent authoritative state."""
        return ItemState(
            item_uuid=self.uuid,
            semantic_key=self.get_semantic_key(),
            name=self.name,
            description=self.description,
            item_kind=ItemKind.ITEM,
            rarity=self.rarity,
            weight=self.weight,
            value=self.value,
            tags=tuple(self.tags),
            is_pickable=self.is_pickable,
            is_equippable=self.is_equippable,
            is_usable=self.is_usable,
            is_consumable=self.is_consumable,
            is_targetable=self.is_targetable,
            stack_id=self.stack_id,
            stack_count=self.stack_count if stack_count is None else stack_count,
            max_stack=self.max_stack,
            current_hit_points=(max(0, self.get_hp()) if self.health is not None else None),
            maximum_hit_points=(self.get_max_hp() if self.health is not None else None),
            charge_state=self.get_charge_state(),
            boundary_structure=self.get_boundary_structure(),
            light_source=self.get_light_source_state(),
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
        completion = ItemLocationStateEvent(
            source_entity_uuid=source_uuid,
            target_entity_uuid=owner_uuid,
            parent_event=parent_event.uuid if parent_event is not None else None,
            item_state=self.to_item_state(stack_count=stack_count),
            location=location,
            owner_uuid=owner_uuid,
            container_uuid=container_uuid,
            world_placement=world_placement,
            equipment_slot=equipment_slot,
            merged_into_item_uuid=merged_into_item_uuid,
            entity_armor_class_after=entity_armor_class_after,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )
        return EventQueue.publish_inert_terminal_fact(completion)

    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: MovementMode = MovementMode.WALKING) -> bool:
        """Whether this item blocks walking through its grid position."""
        return self.blocks_movement

    def blocks_optics_at_center(self) -> bool:
        """Whether this item blocks ordinary optics through its cell center."""
        return self.blocks_optics_field

    def blocks_propagation(self) -> bool:
        """Whether this item blocks physical propagation through its grid position."""
        return self.blocks_propagation_field

    def should_include_in_senses_objects(self) -> bool:
        """Return whether senses should list this floor object."""
        return self.include_in_senses_objects

    def should_include_in_available_object_actions(self) -> bool:
        """Return whether object/action discovery may expose this item."""
        return self.include_in_available_object_actions

    def get_storage_block(self) -> Optional[BaseBlock]:
        """Return this item's canonical contained-item storage, when present."""
        return None

    def get_boundary_structure(self) -> Optional[BoundaryStructure]:
        """Return the current exact boundary structure, when authored."""
        return None

    def get_light_source_state(self) -> Optional[ItemLightSourceState]:
        """Return this item's visible light-emitter state, when present."""
        return None

    def get_charge_state(self) -> Optional[ItemChargeState]:
        """Return this item's finite-use state, when present."""
        return None

    def to_item_observation_state(
        self,
        requesting_entity_uuid: Optional[UUID] = None,
    ) -> ItemObservationState:
        """Return one closed observer-relative spatial item snapshot."""
        return ItemObservationState(
            blocks_movement=self.blocks_walking(requesting_entity_uuid),
            blocks_optics=self.blocks_optics_at_center(),
            blocks_propagation=self.blocks_propagation(),
            is_pickable=self.is_pickable,
            is_usable=self.is_usable,
            stack_count=self.stack_count,
            is_hazardous=self.is_hazardous_for(requesting_entity_uuid),
            is_open=self.get_spatial_open_state(),
            boundary_structure=self.get_boundary_structure(),
            light_source=self.get_light_source_state(),
            charge_state=self.get_charge_state(),
        )

    def douse_exposed_flame(self, parent_event: Optional[UUID] = None) -> bool:
        """Douse this item's exposed flame, if any.

        Args:
            parent_event: Optional parent event UUID for light-removal lineage.

        Returns:
            True if a flame was doused.
        """
        return False

    def get_position(self) -> Optional[Tuple[int, int]]:
        """Get effective position of this item.

        Owned items defer to the owner's neutral position query. Floor items
        derive their position from GridMap's committed placement.
        """
        if self.owner_uuid is not None:
            owner = BaseBlock.get(self.owner_uuid)
            return owner.get_position() if owner else None
        return get_map().get_object_position(self.uuid)

    def place_on_grid(self, position: Tuple[int, int]) -> WorldObjectPlacement:
        """Place this item through GridMap's committed placement authority."""
        return get_map().place_object(self.uuid, position)

    def on_grid_object_removed(
        self,
        position: Tuple[int, int],
        parent_event: Optional[UUID] = None,
    ) -> None:
        """React to terminal GridMap removal; placement authority is already clear."""
        del parent_event
        return None

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
        parent_event_uuid = parent_event.uuid if parent_event is not None else None
        gridmap.cleanup_block_light_sources(
            self.uuid,
            parent_event=parent_event_uuid,
        )
        for cond_name in list(self.active_conditions.keys()):
            self.remove_condition(cond_name, parent_event=parent_event)
        if self.stored_in_uuid is not None:
            container = BaseBlock.get(self.stored_in_uuid)
            if container is not None:
                container.remove_contained_item(self.uuid)
        self.owner_uuid = None
        self.stored_in_uuid = None
        self.is_equipped = False
        self.equipped_slot = None
        gridmap = get_map()
        if gridmap.get_object_position(self.uuid) is not None:
            gridmap.remove_object(self.uuid, parent_event=parent_event_uuid)
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
        """Run one typed causal destruction hook before location cleanup."""
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
        """Apply item damage through the same interruptible event boundary.

        Returns actual normal hit-point damage and destroys the item when the
        accepted packet reduces it to zero hit points.
        """
        if self.health is None:
            return 0
        source = BaseBlock.get(source_uuid)
        event = TakeDamageEvent(
            source_entity_uuid=source_uuid,
            target_entity_uuid=self.uuid,
            source_entity_name=source.name if source is not None else None,
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
            use_register=False,
        )
        event = EventQueue.publish_declaration(event)
        if event.canceled:
            return 0
        event = event.phase_to(EventPhase.EXECUTION)
        if event.canceled:
            return 0
        event = event.phase_to(EventPhase.EFFECT)
        if event.canceled:
            return 0

        resolved_damage_type = event.damages[0].damage_type
        preview = self.health.preview_damage(
            event.get_effective_damage(),
            resolved_damage_type,
            event.normal_hit_point_damage_cap,
            declared_damage=event.total_damage,
            normal_hit_points_available=max(0, self.get_hp()),
        )
        actual = self.health.apply_damage_preview(preview, source_uuid)
        if not self.has_hp:
            self.destroy(parent_event=event)
        event.phase_to(
            EventPhase.COMPLETION,
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
        dice_val = cast(HitDieSize, hit_dice_value)
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
    """Base item with an explicit immutable world-placement capability."""

    world_placement_spec: WorldPlacementSpec = Field(
        frozen=True,
        description="Explicit authored placement capability for this world item.",
    )

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        """Return the authored placement capability without inferring it."""
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
        gridmap = get_map()
        if gridmap.get_object_position(self.uuid) is not None:
            gridmap.remove_object(self.uuid)
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
        provider_id = self.get_semantic_key()
        action.provided_by_id = provider_id
        action.origin_root_id = provider_id
        action.bind_behavior_owner(origin_root_id=provider_id)
        return action

    def to_item_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemState:
        """Classify the authoritative item fact as a usable item."""
        return super().to_item_state(stack_count=stack_count).model_copy(
            update={"item_kind": ItemKind.USABLE},
        )

    def get_charge_state(self) -> ItemChargeState:
        """Return exact finite-use state for observation consumers."""
        return ItemChargeState(
            charges=self.charges,
            max_charges=self.max_charges,
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
        source_item_state = self.to_item_state()
        for template in self.use_action_templates:
            if self.charges != -1 and self.charges < template.charge_cost:
                continue
            action = template.model_copy(deep=True, update={
                'uuid': uuid4(),
                'source_entity_uuid': user_entity_uuid,
                'source_item_uuid': self.uuid,
                'source_item_state': source_item_state,
            })
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
