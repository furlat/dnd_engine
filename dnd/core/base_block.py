from typing import Dict, Optional, Any, List, Self, Set, ClassVar, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, PrivateAttr, model_validator, computed_field, ConfigDict
from dnd.core.values import ModifiableValue
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import HazardFilter
from dnd.core.content.runtime import (
    bind_runtime_behavior,
    bind_runtime_handler_before_admission,
)
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialChangeEvent,
    Trigger,
)
from dnd.types.senses import (
    SenseMode as SenseMode,
    SensesType as SensesType,
    SensesView,
)
from dnd.types.world import LightLevel, MovementMode
from dnd.types.world_placement import (
    BoundaryStructure,
    WorldPlacementKind,
    WorldPlacementSpec,
)

from collections import defaultdict

ContextualConditionImmunity = Callable[['BaseBlock', Optional['BaseBlock'], Optional[dict]], bool]


class BaseBlock(BaseModel):
    """UUID-addressable container for engine components.

    Blocks group child blocks, modifiable values, conditions, and local event
    handlers behind a shared source/target/context identity. Subclasses such as
    entities, items, tiles, equipment, and health blocks specialize the virtual
    spatial and gameplay hooks while retaining the same registry and cleanup
    contracts.
    """

    name: str = Field(
        default="A Block",
        description="The name of the block. Defaults to 'A Block' if not specified."
    )
    description: Optional[str] = Field(
        default=None,
        description="A description of the block. Can be None."
    )
    uuid: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the block. Automatically generated if not provided."
    )
    source_entity_uuid: UUID = Field(
        ...,
        description="UUID of the entity that is the source of this block. Must be provided explicitly."
    )
    source_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that is the source of this block. Can be None."
    )
    target_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the entity that this block targets, if any. Can be None."
    )
    target_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that this block targets, if any. Can be None."
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context information for this block. Can be None."
    )
    blocks: Dict[UUID, 'BaseBlock'] = Field(
        default_factory=dict,
        description="Dictionary of all BaseBlock instances that are attributes of this class."
    )
    values: Dict[UUID, 'ModifiableValue'] = Field(
        default_factory=dict,
        description="Dictionary of all ModifiableValue instances that are attributes of this class."
    )

    position: Tuple[int, int] = Field(
        default_factory=lambda: (0, 0),
        description="Grid position used by spatial blocks and propagated to child blocks."
    )
    faction: Optional[str] = Field(default=None, description="Faction for ally/enemy detection. None = no faction.")
    stealth_dc: Optional[int] = Field(default=None, exclude=True,
        description="Stealth DC required to perceive. Set by Hidden condition.")
    is_invisible: bool = Field(default=False, exclude=True,
        description="Whether invisible. Set by Invisible condition.")
    _attached_light_sources: Set[UUID] = PrivateAttr(default_factory=set)

    active_conditions: Dict[str, BaseCondition] = Field(
        default_factory=dict,
        description="Active conditions keyed by condition name."
    )
    active_conditions_by_uuid: Dict[UUID, BaseCondition] = Field(
        default_factory=dict,
        exclude=True,
        description="Active conditions keyed by condition UUID."
    )
    condition_immunities: List[Tuple[str, Optional[str]]] = Field(
        default_factory=list,
        description="Static condition immunities as condition-name/source-name pairs."
    )
    contextual_condition_immunities: Dict[str, List[Tuple[str, ContextualConditionImmunity]]] = Field(
        default_factory=dict,
        exclude=True,
        description="Runtime condition immunity checks keyed by condition name."
    )
    active_conditions_by_source: Dict[UUID, List[str]] = Field(
        default_factory=lambda: defaultdict(list),
        exclude=True,
        description="Active condition names grouped by source entity UUID."
    )

    event_handlers: Dict[UUID, EventHandler] = Field(
        default_factory=dict,
        description="Local event handlers owned by this block."
    )
    event_handlers_by_trigger: Dict[Trigger, List[EventHandler]] = Field(
        default_factory=lambda: defaultdict(list),
        exclude=True,
        description="Local event handlers indexed by full trigger."
    )
    event_handlers_by_simple_trigger: Dict[Trigger, List[EventHandler]] = Field(
        default_factory=lambda: defaultdict(list),
        exclude=True,
        description="Local event handlers indexed by simplified trigger."
    )

    allow_events_conditions: bool = Field(default=False,description="If True, events and conditions will be allowed to be added to the block")

    @computed_field
    @property
    def contextual_immunity_names(self) -> Dict[str, List[str]]:
        """Serializable view of contextual condition immunities (names only)."""
        return {cond: [name for name, _ in imms] for cond, imms in self.contextual_condition_immunities.items()}

    _registry: ClassVar[Dict[UUID, 'BaseBlock']] = {}

    model_config = ConfigDict(validate_assignment=False)

    def get_map_char(self) -> Optional[str]:
        """Map glyph for blocks that have one."""
        return None

    def get_spatial_open_state(self) -> Optional[bool]:
        """Open/closed state for spatial objects that expose one."""
        return None

    def should_include_in_senses_objects(self) -> bool:
        """Whether this block should appear in entity senses.objects."""
        return True

    def appears_in_entity_contacts(self) -> bool:
        """Whether a GridMap entity occupant belongs in perceived contacts."""
        return True

    def should_include_in_adjacent_senses_objects(self) -> bool:
        """Whether this block can be sensed from an adjacent tile even if its cell is not visible."""
        return False

    def should_include_in_available_object_actions(self) -> bool:
        """Whether this block should be considered by object/action discovery."""
        return True

    def _set_values_and_blocks_source(self, block: 'BaseBlock') -> None:
        """Propagate source, target, and context into a block tree.

        Args:
            block: Block whose immediate values and child blocks should inherit
                owner identity.
        """
        for value in block.values.values():
            value.set_source_entity(block.source_entity_uuid, block.source_entity_name)
            if block.context is not None:
                value.set_context(block.context)
            if block.target_entity_uuid is not None:
                value.set_target_entity(block.target_entity_uuid, block.target_entity_name)

        for sub_block in block.blocks.values():
            sub_block.source_entity_uuid = block.source_entity_uuid
            sub_block.source_entity_name = block.source_entity_name
            if block.context is not None:
                sub_block.set_context(block.context)
            if block.target_entity_uuid is not None:
                sub_block.set_target_entity(block.target_entity_uuid, block.target_entity_name)
            self._set_values_and_blocks_source(sub_block)

    def _populate_blocks_and_values(self) -> None:
        """Discover direct child blocks and modifiable values on this model."""
        for name, _ in self.__class__.model_fields.items():
            attr_value = getattr(self, name)
            if name in ['blocks', 'values']:
                continue
            if isinstance(attr_value, ModifiableValue):
                self.values[attr_value.uuid] = attr_value
            elif isinstance(attr_value, BaseBlock):
                self.blocks[attr_value.uuid] = attr_value

    @model_validator(mode='after')
    def set_values_and_blocks_source(self) -> 'Self':
        """Propagate this block's identity to discovered values and children.

        Returns:
            This block after propagation.
        """
        self._populate_blocks_and_values()
        self._set_values_and_blocks_source(self)
        return self

    @model_validator(mode='after')
    def validate_values_and_blocks_source_and_target(self) -> Self:
        """Validate discovered values and children share this block's source.

        Returns:
            This block after validation.

        Raises:
            ValueError: If a discovered value or child block has a mismatched
                source UUID.
        """
        for _, value in self.values.items():
            if value.source_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"ModifiableValue '{value.name}' has mismatched source UUID")

        for _, block in self.blocks.items():
            if block.source_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"BaseBlock '{block.name}' has mismatched source UUID")

        return self

    @model_validator(mode='after')
    def populate_blocks_and_values(self) -> Self:
        """Discover direct child blocks and modifiable values on this model.

        Returns:
            This block after updating the local lookup dictionaries.
        """
        self._populate_blocks_and_values()

        return self

    def model_post_init(self, __context: Any) -> None:
        """Register this block in the block registry by UUID."""
        super().model_post_init(__context)
        self.__class__._registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['BaseBlock']:
        """Retrieve a block from the block registry by UUID.

        Args:
            uuid: UUID of the block to retrieve.

        Returns:
            The registered block when found, otherwise `None`.

        Raises:
            ValueError: If the UUID resolves to a non-block object.
        """
        value = cls._registry.get(uuid)
        if value is None:
            return None
        elif isinstance(value, BaseBlock):
            return value
        else:
            raise ValueError(f"Value with UUID {uuid} is not a BaseBlock, but {type(value)}")

    @classmethod
    def register(cls, value: 'BaseBlock') -> None:
        """Register a block in the class registry.

        Args:
            value: Block instance to register.
        """
        cls._registry[value.uuid] = value

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        """Remove a block from the class registry.

        Args:
            uuid: UUID of the block to unregister.
        """
        cls._registry.pop(uuid, None)

    def get_blocks(self) -> List['BaseBlock']:
        """Return direct child blocks discovered on this block.

        Returns:
            Direct child blocks.
        """
        return list(self.blocks.values())

    def get_values(self, deep: bool = False) -> List['ModifiableValue']:
        """Return values discovered on this block.

        Args:
            deep: Whether to recurse into child blocks.

        Returns:
            Discovered modifiable values.
        """
        values = list(self.values.values())
        if deep:
            for block in self.blocks.values():
                values.extend(block.get_values(deep=True))
        return values

    def set_position(self, position: Tuple[int,int]) -> None:
        """
        Set the position of the block.
        """
        self.position = position
        for block in self.blocks.values():
            block.set_position(position)

    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: 'MovementMode' = MovementMode.WALKING) -> bool:
        """Whether this block prevents walking through its position.
        Non-spatial blocks (Equipment, Health, etc.) inherit this default."""
        return False

    def blocks_optics_at_center(self) -> bool:
        """Whether this block prevents ordinary optics through its cell center."""
        return False

    def blocks_propagation(self) -> bool:
        """Whether this block prevents physical propagation through its cell center."""
        return False

    def set_stealth_dc(self, value: Optional[int], parent_event: Optional[UUID] = None) -> None:
        """Set stealth DC and notify observers."""
        if self.stealth_dc == value:
            return
        self.stealth_dc = value
        self._notify_perceivability_changed(parent_event=parent_event)

    def set_invisible(self, value: bool, parent_event: Optional[UUID] = None) -> None:
        """Set invisibility flag and notify observers."""
        if self.is_invisible is value:
            return
        self.is_invisible = value
        self._notify_perceivability_changed(parent_event=parent_event)

    def _notify_perceivability_changed(self, parent_event: Optional[UUID] = None) -> None:
        """Fire a SPATIAL_PERCEIVABILITY_CHANGED event at this block's position.

        Candidate observers subscribed to this cell are re-evaluated by the
        spatial senses reducer. Does not trigger SpatialHandlers (zone effects).
        """
        event = SpatialChangeEvent.perceivability_changed(self.position, self.uuid, parent_event=parent_event)
        current = EventQueue.register(event)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.EXECUTION)
        current = EventQueue.register(current)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.EFFECT)
        current = EventQueue.register(current)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.COMPLETION)
        EventQueue.register(current)

    def get_passive_perception(self) -> int:
        """Return passive perception for this block as an observer."""
        return 0

    def has_ordinary_visual_sight(self) -> bool:
        """Return whether this block has ordinary visual sight."""
        return False

    def get_sense_modes(self) -> List[SenseMode]:
        """Return sense modes for this block as an observer."""
        return []

    def get_senses(self) -> Optional[SensesView]:
        """Override in Entity to return Senses block for subjective perception."""
        return None

    @property
    def is_active(self) -> bool:
        """Whether this block is active and should be included in interactions.
        Default True. Override in Entity/BaseItem for health-aware checks."""
        return True

    def can_take_actions(self) -> bool:
        """Return whether this block may originate ordinary actions.

        Non-entity blocks are permitted by default. Entity overrides this using
        its neutral action-permission capability.
        """
        return True

    def can_afford_action_resource(
        self,
        resource_name: str,
        amount: int,
    ) -> bool:
        """Return whether this block can pay a named action resource.

        Only owners with an action economy override this neutral boundary.
        """
        return False

    def get_hp(self) -> int:
        """Override in Entity/BaseItem to return current HP. Default: 0 (no health system)."""
        return 0

    def attach_light_source(self, light_source_uuid: UUID) -> None:
        """Track a light source attached to this block (for cleanup)."""
        self._attached_light_sources.add(light_source_uuid)

    def detach_light_source(self, light_source_uuid: UUID) -> None:
        """Stop tracking a light source."""
        self._attached_light_sources.discard(light_source_uuid)

    def get_attached_light_sources(self) -> Set[UUID]:
        """Get all light sources attached to this block."""
        return self._attached_light_sources.copy()

    def is_enemy_of(self, other_uuid: UUID) -> bool:
        """Whether this block considers other_uuid an enemy.
        Default: True (unknown blocks are enemies).
        Entity overrides with faction-based logic."""
        return True

    def is_hazardous_for(self, entity_uuid: Optional[UUID] = None) -> bool:
        """Return whether active hazard conditions affect an optional entity."""
        for cond in self.active_conditions.values():
            if cond.hazard_filter is None:
                continue

            if cond.condition_stealth_dc is not None and entity_uuid is not None:
                observer = BaseBlock.get(entity_uuid)
                if observer is not None and cond.condition_stealth_dc >= observer.get_passive_perception():
                    continue

            if cond.hazard_filter == HazardFilter.ALL:
                return True
            if cond.hazard_filter == HazardFilter.NON_SOURCE and entity_uuid != cond.source_entity_uuid:
                return True
            if cond.hazard_filter == HazardFilter.ENEMIES and entity_uuid is not None:
                observer = BaseBlock.get(entity_uuid)
                if observer is not None and observer.is_enemy_of(cond.source_entity_uuid):
                    return True

        return False

    def set_target_entity(self, target_entity_uuid: UUID, target_entity_name: Optional[str] = None) -> None:
        """Set target identity on this block, direct values, and child blocks.

        Args:
            target_entity_uuid: UUID of the target entity.
            target_entity_name: Optional display name for the target entity.

        Raises:
            ValueError: If `target_entity_uuid` is not a UUID.
        """
        if not isinstance(target_entity_uuid, UUID):
            raise ValueError("target_entity_uuid must be a UUID")

        self.target_entity_uuid = target_entity_uuid
        self.target_entity_name = target_entity_name

        for value in self.values.values():
            value.set_target_entity(target_entity_uuid, target_entity_name)

        for block in self.blocks.values():
            block.set_target_entity(target_entity_uuid, target_entity_name)

    def clear_target_entity(self) -> None:
        """Clear target identity on this block, direct values, and children."""
        for value in self.values.values():
            value.clear_target_entity()

        for block in self.blocks.values():
            block.clear_target_entity()

        self.target_entity_uuid = None
        self.target_entity_name = None

    def set_context(self, context: Dict[str, Any]) -> None:
        """Set runtime context on this block, direct values, and children.

        Args:
            context: Context dictionary to propagate.
        """
        self.context = context

        for value in self.values.values():
            value.set_context(context)

        for block in self.blocks.values():
            block.set_context(context)

    def clear_context(self) -> None:
        """Clear runtime context on this block, direct values, and children."""
        self.context = None

        for value in self.values.values():
            value.clear_context()

        for block in self.blocks.values():
            block.clear_context()

    def clear(self) -> None:
        """Clear target identity and context from this block tree."""
        self.clear_target_entity()
        self.clear_context()

    def remove_contained_item(self, item_uuid: UUID) -> None:
        """Remove a contained item by UUID.

        Args:
            item_uuid: UUID of the item to remove.

        The base implementation is a no-op. Inventory overrides this hook.
        """
        pass

    def on_owned_item_destroyed(
        self,
        item: 'BaseBlock',
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Allow a high-level owner to publish facts after item cleanup.

        BaseItem invokes this hook only after container membership, equipment
        hooks, and floor placement have been cleared. Entity overrides it to
        publish aggregate item/AC state without requiring BaseItem or Equipment
        to import upward. Other blocks return ``False`` so the item publishes a
        dependency-neutral destruction fact itself.

        Args:
            item: Destroyed item block, still available until its final registry
                removal.
            parent_event: Optional causal event that destroyed the item.

        Returns:
            True when the owner published the destruction fact.
        """
        return False

    def on_grid_object_removed(self, position: Tuple[int, int], clear_location: bool = True) -> None:
        """React after this block is removed from GridMap object indexes.

        Args:
            position: Grid position the object occupied before removal.
            clear_location: Whether the removal represents an authoritative
                location clear instead of an internal reindexing step.

        The base implementation is a no-op. Floor-aware subclasses override
        this hook to synchronize their own location fields.
        """
        pass

    def get_position(self) -> Tuple[int, int]:
        """Return this block's current objective position value."""
        return self.position

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        """Return the neutral one-band center placement capability."""
        return WorldPlacementSpec(
            kind=WorldPlacementKind.CENTER,
            occupies_bands=False,
            vertical_extent_steps=1,
        )

    def get_boundary_structure(self) -> Optional[BoundaryStructure]:
        """Return current boundary mechanics when this block provides them."""
        return None

    @classmethod
    def create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None,
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None,
                name: str = "Base Block") -> 'BaseBlock':
        """Create a base block with identity fields.

        Args:
            source_entity_uuid: UUID of the source entity.
            source_entity_name: Optional display name of the source entity.
            target_entity_uuid: Optional UUID of the target entity.
            target_entity_name: Optional display name of the target entity.
            name: Block name.

        Returns:
            Newly created block.
        """
        return cls(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, name=name)

    @computed_field
    @property
    def values_dict_uuid_name(self) -> Dict[UUID, str]:
        """Map direct value UUIDs to value names.

        Returns:
            Value names keyed by UUID.
        """
        return {value.uuid: value.name for value in self.get_values()}

    @computed_field
    @property
    def values_dict_name_uuid(self) -> Dict[str, UUID]:
        """Map direct value names to value UUIDs.

        Returns:
            Value UUIDs keyed by name.
        """
        return {value.name: value.uuid for value in self.get_values()}

    @computed_field
    @property
    def blocks_dict_uuid_name(self) -> Dict[UUID, str]:
        """Map direct child block UUIDs to block names.

        Returns:
            Child block names keyed by UUID.
        """
        return {block.uuid: block.name for block in self.get_blocks()}

    @computed_field
    @property
    def blocks_dict_name_uuid(self) -> Dict[str, UUID]:
        """Map direct child block names to block UUIDs.

        Returns:
            Child block UUIDs keyed by name.
        """
        return {block.name: block.uuid for block in self.get_blocks()}

    def get_value_from_uuid(self, uuid: UUID) -> Optional[ModifiableValue]:
        """Return a direct value by UUID.

        Args:
            uuid: UUID of the direct value to retrieve.

        Returns:
            Matching direct value, or `None`.
        """
        return self.values.get(uuid)

    def get_value_from_name(self, name: str) -> Optional[ModifiableValue]:
        """Return a direct value by name.

        Args:
            name: Name of the direct value to retrieve.

        Returns:
            Matching direct value, or `None`.
        """
        for value in self.values.values():
            if value.name == name:
                return value
        return None

    def get_block_from_uuid(self, uuid: UUID) -> Optional['BaseBlock']:
        """Return a direct child block by UUID.

        Args:
            uuid: UUID of the direct child block to retrieve.

        Returns:
            Matching direct child block, or `None`.
        """
        return self.blocks.get(uuid)

    def get_block_from_name(self, name: str) -> Optional['BaseBlock']:
        """Return a direct child block by name.

        Args:
            name: Name of the direct child block to retrieve.

        Returns:
            Matching direct child block, or `None`.
        """
        for block in self.blocks.values():
            if block.name == name:
                return block
        return None

    def add_event_handler(self, event_handler: EventHandler) -> None:
        """Own and register an event handler when lifecycle is enabled.

        Args:
            event_handler: Handler to add to this block and `EventQueue`.
        """
        if not self.allow_events_conditions:
            return None
        bind_runtime_handler_before_admission(
            event_handler,
            current_binding=event_handler.behavior_binding,
            runtime_owner_uuid=event_handler.source_entity_uuid,
        )
        event_handler.owner_block = self
        self.event_handlers[event_handler.uuid] = event_handler
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                self.event_handlers_by_simple_trigger[trigger].append(event_handler)
            self.event_handlers_by_trigger[trigger].append(event_handler)
        EventQueue.add_event_handler(event_handler)

    def remove_event_handler_from_dicts(self, event_handler: EventHandler) -> None:
        """Remove a handler from this block's local indexes.

        Args:
            event_handler: Handler to remove from block-local storage.
        """
        if not self.allow_events_conditions:
            return None
        self.event_handlers.pop(event_handler.uuid)
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                self.event_handlers_by_simple_trigger[trigger].remove(event_handler)
            self.event_handlers_by_trigger[trigger].remove(event_handler)

    def remove_event_handler(self, event_handler: EventHandler) -> None:
        """Remove a handler from the queue and this block's local indexes.

        Args:
            event_handler: Handler to remove.
        """
        if not self.allow_events_conditions:
            return None
        EventQueue.remove_event_handler(event_handler)
        if event_handler.uuid in self.event_handlers:
            self.remove_event_handler_from_dicts(event_handler)

    def get_event_handler_by_name(self, name: str) -> Optional[EventHandler]:
        """Find the first local event handler matching a name.

        Args:
            name: Handler name to match case-insensitively.

        Returns:
            First matching handler, or `None`.
        """
        name_lower = name.lower()
        for handler in self.event_handlers.values():
            if handler.name.lower() == name_lower:
                return handler
        return None

    def get_event_handlers_by_name(self, name: str) -> List[EventHandler]:
        """Find all local event handlers matching a name.

        Args:
            name: Handler name to match case-insensitively.

        Returns:
            Matching handlers in local storage order.
        """
        name_lower = name.lower()
        return [h for h in self.event_handlers.values() if h.name.lower() == name_lower]

    def set_handler_enabled(self, name: str, enabled: bool) -> bool:
        """Set enabled state on the first matching player-toggleable handler.

        Args:
            name: Handler name to match case-insensitively.
            enabled: New enabled state.

        Returns:
            True if a player-toggleable matching handler was updated.
        """
        handler = self.get_event_handler_by_name(name)
        if handler is not None and handler.player_toggleable:
            handler.enabled = enabled
            return True
        return False

    def set_handler_enabled_by_uuid(self, handler_uuid: UUID, enabled: bool) -> bool:
        """Set enabled state on a player-toggleable handler by UUID.

        Args:
            handler_uuid: UUID of the local handler to update.
            enabled: New enabled state.

        Returns:
            True if a player-toggleable handler was updated.
        """
        handler = self.event_handlers.get(handler_uuid)
        if handler is not None and handler.player_toggleable:
            handler.enabled = enabled
            return True
        return False

    def _discard_condition_indexes(self, condition: BaseCondition) -> None:
        """Remove one exact condition from this block's local indexes.

        Args:
            condition: Condition to remove from index dictionaries.
        """
        if not self.allow_events_conditions:
            return None
        condition_name = condition.name
        if (
            condition_name is not None
            and self.active_conditions.get(condition_name) is condition
        ):
            self.active_conditions.pop(condition_name)
        if self.active_conditions_by_uuid.get(condition.uuid) is condition:
            self.active_conditions_by_uuid.pop(condition.uuid)
        if condition_name is not None:
            source_rows = self.active_conditions_by_source.get(
                condition.source_entity_uuid,
            )
            if source_rows is not None and condition_name in source_rows:
                source_rows.remove(condition_name)

    def _discard_uncommitted_condition_tree(
        self,
        condition: BaseCondition,
    ) -> None:
        """Discard provisional condition mechanics without removal events."""
        for sub_uuid in list(condition.sub_conditions):
            sub_condition = BaseCondition.get(sub_uuid)
            if isinstance(sub_condition, BaseCondition):
                self._discard_condition_indexes(sub_condition)
                self._discard_uncommitted_condition_tree(sub_condition)

        for target_uuid, child_uuid in list(condition.linked_conditions):
            target_block = BaseBlock.get(target_uuid)
            child_condition = BaseCondition.get(child_uuid)
            if (
                isinstance(target_block, BaseBlock)
                and isinstance(child_condition, BaseCondition)
            ):
                target_block._discard_condition_indexes(child_condition)
                target_block._discard_uncommitted_condition_tree(
                    child_condition,
                )
            elif isinstance(child_condition, BaseCondition):
                child_condition.discard_from_runtime_owner()

        condition.discard_uncommitted_runtime_state()
        self._discard_condition_indexes(condition)
        condition.remove_from_register()

    def remove_condition(self, condition_name: str, expire: bool = False,
                         parent_event: Optional[Event] = None) -> bool:
        """Remove a condition with full cross-block tree traversal.

        Handles sub-conditions (same block), linked_conditions (other blocks),
        and own state cleanup via _remove_condition_tree().

        Args:
            condition_name: Name of the condition to remove.
            expire: Whether this is an expiration removal.
            parent_event: Parent event for event-chain tracking.
        """
        if not self.allow_events_conditions:
            return False
        if condition_name not in self.active_conditions:
            return False

        condition = self.active_conditions[condition_name]
        return self._remove_condition_tree(
            condition,
            expire=expire,
            parent_event=parent_event,
        )

    def remove_condition_by_uuid(self, condition_uuid: UUID,
                                 parent_event: Optional[Event] = None) -> bool:
        """Remove a condition by UUID.

        Args:
            condition_uuid: UUID of the condition to remove.
            parent_event: Optional parent event for cleanup event lineage.
        """
        if not self.allow_events_conditions:
            return False
        condition = self.active_conditions_by_uuid.get(condition_uuid)
        if condition is None:
            return False
        if condition.name is not None:
            return self.remove_condition(
                condition.name,
                parent_event=parent_event,
            )
        return False

    def _remove_condition_tree(self, condition: BaseCondition, expire: bool = False,
                               parent_event: Optional[Event] = None) -> bool:
        """Remove one complete owned condition graph atomically.

        Every removal phase is accepted before mechanics change. The prepared
        graph is then committed in reverse order so descendants finish before
        their owners while indexes remain authoritative until each node's own
        state has been released.

        Args:
            condition: Root condition to remove.
            expire: Whether this removal is an expiration path.
            parent_event: Optional parent event for cleanup event lineage.
        """
        prepared: List[
            Tuple[Optional[BaseBlock], BaseCondition, Event, bool]
        ] = []
        canceled = BaseBlock._prepare_condition_removal_tree(
            condition,
            condition_owner=self,
            expire=expire,
            parent_event=parent_event,
            prepared=prepared,
            visited=set(),
        )
        if canceled is not None:
            BaseBlock._cancel_prepared_condition_removals(
                prepared,
                canceled,
            )
            return False
        BaseBlock._commit_prepared_condition_removals(prepared)
        return True

    @staticmethod
    def _cancel_prepared_condition_removals(
        prepared: List[
            Tuple[Optional['BaseBlock'], BaseCondition, Event, bool]
        ],
        canceled: Event,
    ) -> None:
        """Close accepted removal effects without mutating condition state."""
        reason = canceled.status_message or "Dependent condition removal was canceled"
        for _, _, effect, _ in reversed(prepared):
            if not effect.canceled:
                effect.cancel(status_message=reason)
            parent = (
                EventQueue.get_event_by_uuid(effect.parent_event)
                if effect.parent_event is not None
                else None
            )
            if (
                parent is not None
                and parent.event_type is EventType.CONDITION_REMOVAL
                and not parent.canceled
            ):
                parent.cancel(status_message=reason)

    @staticmethod
    def _commit_prepared_condition_removals(
        prepared: List[
            Tuple[Optional['BaseBlock'], BaseCondition, Event, bool]
        ],
    ) -> None:
        """Commit a fully accepted condition graph child-first."""
        for owner, condition, removal_effect, expire in reversed(prepared):
            if owner is None:
                if not condition.remove_from_runtime_owner(
                    expire=expire,
                    parent_event=removal_effect,
                    prepared_removal_effect=removal_effect,
                ):
                    raise RuntimeError(
                        "Accepted independent condition removal failed",
                    )
                continue

            removed = condition.cleanup_own_state(
                expire=expire,
                parent_event=removal_effect,
                removal_effect=removal_effect,
            )
            if removed is None or removed.canceled:
                raise RuntimeError(
                    "Accepted condition removal failed during owned-state cleanup"
                )

            owner._discard_condition_indexes(condition)
            if condition.parent_link is not None:
                _, parent_condition_uuid = condition.parent_link
                parent_condition = BaseCondition.get(parent_condition_uuid)
                if isinstance(parent_condition, BaseCondition):
                    parent_condition.linked_conditions = [
                        link
                        for link in parent_condition.linked_conditions
                        if link[1] != condition.uuid
                    ]

            condition.remove_from_register()
            removed.phase_to(
                EventPhase.COMPLETION,
                **condition._post_removal_stats(),
            )

    @classmethod
    def _prepare_condition_removal_tree(
        cls,
        condition: BaseCondition,
        *,
        condition_owner: Optional['BaseBlock'],
        expire: bool,
        parent_event: Optional[Event],
        prepared: List[
            Tuple[Optional['BaseBlock'], BaseCondition, Event, bool]
        ],
        visited: Set[UUID],
    ) -> Optional[Event]:
        """Accept one graph's removal phases without mutating mechanics."""
        if condition.uuid in visited:
            return None
        visited.add(condition.uuid)

        declaration = EventQueue.publish_declaration(
            condition._declare_removal_event(
                expired=expire,
                parent_event=parent_event,
            ),
        )
        if declaration.canceled:
            return declaration

        effect = condition.publish_removal_effect(declaration)
        if effect.canceled:
            return effect
        prepared.append((condition_owner, condition, effect, expire))

        for child_uuid in list(condition.sub_conditions):
            child = BaseCondition.get(child_uuid)
            if isinstance(child, BaseCondition) and child.applied:
                if child.is_active_spatial_condition():
                    child_owner = None
                else:
                    resolved_owner = BaseBlock.get(child.target_entity_uuid)
                    child_owner = (
                        resolved_owner
                        if isinstance(resolved_owner, BaseBlock)
                        else condition_owner
                    )
                canceled = cls._prepare_condition_removal_tree(
                    child,
                    condition_owner=child_owner,
                    expire=expire,
                    parent_event=effect,
                    prepared=prepared,
                    visited=visited,
                )
                if canceled is not None:
                    return canceled

        for target_uuid, child_uuid in list(condition.linked_conditions):
            target = BaseBlock.get(target_uuid)
            child = BaseCondition.get(child_uuid)
            child_owner: Optional[BaseBlock] = None
            if isinstance(target, BaseBlock):
                indexed = target.active_conditions_by_uuid.get(child_uuid)
                child = indexed if isinstance(indexed, BaseCondition) else None
                child_owner = target
            elif not (
                isinstance(child, BaseCondition)
                and child.is_active_spatial_condition()
            ):
                child = None
            if isinstance(child, BaseCondition) and child.applied:
                canceled = cls._prepare_condition_removal_tree(
                    child,
                    condition_owner=child_owner,
                    expire=expire,
                    parent_event=effect,
                    prepared=prepared,
                    visited=visited,
                )
                if canceled is not None:
                    return canceled

        if condition.parent_link is not None:
            parent_block_uuid, parent_condition_uuid = condition.parent_link
            parent_block = BaseBlock.get(parent_block_uuid)
            parent_condition = BaseCondition.get(parent_condition_uuid)
            parent_is_independent_spatial = (
                isinstance(parent_condition, BaseCondition)
                and parent_condition.is_active_spatial_condition()
                and parent_block_uuid == parent_condition.uuid
            )
            if (
                isinstance(parent_condition, BaseCondition)
                and (
                    isinstance(parent_block, BaseBlock)
                    or parent_is_independent_spatial
                )
                and parent_condition.applied
                and parent_condition.uuid not in visited
            ):
                policy = parent_condition.child_removal_policy
                remaining_children = sum(
                    1
                    for _, linked_uuid in parent_condition.linked_conditions
                    if linked_uuid not in visited
                    and (
                        linked := BaseCondition.get(linked_uuid)
                    ) is not None
                    and isinstance(linked, BaseCondition)
                    and linked.applied
                )
                if policy == "any" or (
                    policy == "last" and remaining_children == 0
                ):
                    canceled = cls._prepare_condition_removal_tree(
                        parent_condition,
                        condition_owner=(
                            parent_block
                            if isinstance(parent_block, BaseBlock)
                            else None
                        ),
                        expire=expire,
                        parent_event=effect,
                        prepared=prepared,
                        visited=visited,
                    )
                    if canceled is not None:
                        return canceled

        return None

    def advance_duration(self, condition_name: str) -> bool:
        """Progress a block-owned condition duration without saving throws.

        Args:
            condition_name: Name of the condition to progress.

        Returns:
            True if the condition expired and was removed.
        """
        if not self.allow_events_conditions:
            return False
        condition = self.active_conditions.get(condition_name)
        if condition is None:
            return False
        expired = condition.progress()
        if expired:
            self.remove_condition(condition_name, expire=True)
        return expired

    def add_condition(self, condition: BaseCondition, context: Optional[Dict[str, Any]] = None, check_save_throw: bool = True, parent_event: Optional[Event] = None)  -> Optional[Event]:
        """Apply and index a condition when lifecycle is enabled.

        Args:
            condition: Condition to apply.
            context: Optional context to attach before applying.
            check_save_throw: Accepted for API symmetry; block-level condition
                application does not perform saving throws.
            parent_event: Optional causal parent for the application.

        Returns:
            Completion or cancellation event from condition application, or
            `None` when lifecycle is disabled.

        Raises:
            ValueError: If the condition has no name.
        """
        if not self.allow_events_conditions:
            return None
        if condition.name is None:
            raise ValueError("BaseCondition name is not set")
        if condition.target_entity_uuid is None:
            condition.target_entity_uuid = self.uuid
        bind_runtime_behavior(
            condition,
            current_binding=condition.behavior_binding,
            runtime_owner_uuid=self.uuid,
        )
        if context is not None:
            condition.set_context(context)

        declaration_event = EventQueue.publish_declaration(
            condition.declare_event(parent_event),
        )
        if declaration_event.canceled:
            self._discard_uncommitted_condition_tree(condition)
            return declaration_event

        try:
            condition_applied = condition.apply(
                declaration_event=declaration_event,
            )
        except BaseException:
            self._discard_uncommitted_condition_tree(condition)
            raise
        if condition_applied and not condition_applied.canceled and condition.applied:
            if condition.name in self.active_conditions:
                if not self.remove_condition(
                    condition.name,
                    parent_event=condition_applied,
                ):
                    self._discard_uncommitted_condition_tree(condition)
                    return condition_applied.cancel(
                        status_message=(
                            f"Condition {condition.name} could not replace "
                            "the active condition"
                        ),
                    )
            self.active_conditions[condition.name] = condition
            self.active_conditions_by_uuid[condition.uuid] = condition
            self.active_conditions_by_source[condition.source_entity_uuid].append(condition.name)
            completed_event = condition_applied.phase_to(
                EventPhase.COMPLETION,
            )
            condition.applied_source_event_cursor = EventQueue.event_cursor()
            return completed_event
        elif condition_applied and condition_applied.canceled:
            self._discard_uncommitted_condition_tree(condition)

        return condition_applied

    def add_static_condition_immunity(self, condition_name: str, immunity_name: Optional[str] = None) -> None:
        """Add a static condition immunity when lifecycle is enabled.

        Args:
            condition_name: Condition name being blocked.
            immunity_name: Optional named source of the immunity.
        """
        if not self.allow_events_conditions:
            return None
        self.condition_immunities.append((condition_name, immunity_name))

    def _remove_static_condition_immunity(self, condition_name: str, immunity_name: Optional[str] = None) -> None:
        """Remove matching static condition immunity rows.

        Args:
            condition_name: Condition name to remove.
            immunity_name: Optional immunity source name to match.
        """
        if not self.allow_events_conditions:
            return None
        for condition_tuple in self.condition_immunities:
            if condition_tuple[0] == condition_name:
                if immunity_name is None:
                    self.condition_immunities.remove(condition_tuple)
                else:
                    if condition_tuple[1] == immunity_name:
                        self.condition_immunities.remove(condition_tuple)
                        break
        return

    def add_contextual_condition_immunity(
        self,
        condition_name: str,
        immunity_name: str,
        immunity_check: ContextualConditionImmunity
    ) -> None:
        """Add a runtime condition immunity check when lifecycle is enabled.

        Args:
            condition_name: Condition name being blocked.
            immunity_name: Serializable name for the immunity source.
            immunity_check: Callable that evaluates the immunity at runtime.
        """
        if not self.allow_events_conditions:
            return None
        if condition_name not in self.contextual_condition_immunities:
            self.contextual_condition_immunities[condition_name] = []
        self.contextual_condition_immunities[condition_name].append((immunity_name, immunity_check))

    def add_condition_immunity(
        self,
        condition_name: str,
        immunity_name: Optional[str] = None,
        immunity_check: Optional[ContextualConditionImmunity] = None
    ) -> None:
        """Add a static or contextual condition immunity.

        Args:
            condition_name: Condition name being blocked.
            immunity_name: Optional named source of the immunity.
            immunity_check: Optional runtime immunity callable.

        Raises:
            ValueError: If `immunity_check` is provided without
                `immunity_name`.
        """
        if not self.allow_events_conditions:
            return None
        if immunity_check is not None:
            if immunity_name is None:
                raise ValueError("Immunity name is required when adding a contextual BaseCondition immunity")
            self.add_contextual_condition_immunity(condition_name, immunity_name, immunity_check)
        else:
            self.add_static_condition_immunity(condition_name, immunity_name)

    @staticmethod
    def _condition_immunity_source_name(source_id: UUID) -> str:
        """Encode one exact structural source without display-name identity."""
        return f"structural-source:{source_id}"

    def add_condition_immunity_source(
        self,
        condition_name: str,
        source_id: UUID,
        *,
        immunity_check: Optional[ContextualConditionImmunity] = None,
    ) -> None:
        """Install one exact source-owned static or contextual immunity."""
        source_name = self._condition_immunity_source_name(source_id)
        if any(
            name == source_name
            for name, _ in self.contextual_condition_immunities.get(
                condition_name,
                (),
            )
        ) or any(
            existing_condition == condition_name
            and existing_name == source_name
            for existing_condition, existing_name in self.condition_immunities
        ):
            raise ValueError(
                f"condition immunity source {source_id} is already installed "
                f"for {condition_name}",
            )
        self.add_condition_immunity(
            condition_name,
            immunity_name=source_name,
            immunity_check=immunity_check,
        )

    def remove_condition_immunity_source(
        self,
        condition_name: str,
        source_id: UUID,
    ) -> bool:
        """Remove exactly one source-owned immunity without touching siblings."""
        source_name = self._condition_immunity_source_name(source_id)
        removed = False
        for row in tuple(self.condition_immunities):
            if row == (condition_name, source_name):
                self.condition_immunities.remove(row)
                removed = True
        rows = self.contextual_condition_immunities.get(condition_name)
        if rows is not None:
            retained = [
                row
                for row in rows
                if row[0] != source_name
            ]
            removed = removed or len(retained) != len(rows)
            if retained:
                self.contextual_condition_immunities[condition_name] = retained
            else:
                self.contextual_condition_immunities.pop(
                    condition_name,
                    None,
                )
        return removed

    def _remove_contextual_condition_immunity(self, condition_name: str, immunity_name: Optional[str] = None) -> None:
        """Remove matching contextual condition immunity rows.

        Args:
            condition_name: Condition name to remove.
            immunity_name: Optional immunity source name to match.
        """
        if not self.allow_events_conditions:
            return None
        for self_condition_name in self.contextual_condition_immunities:
            if self_condition_name == condition_name:
                if immunity_name is None:
                    self.contextual_condition_immunities.pop(self_condition_name)
                    break
                else:
                    for immunity_tuple in self.contextual_condition_immunities[self_condition_name]:
                        if immunity_tuple[0] == immunity_name:
                            self.contextual_condition_immunities[self_condition_name].remove(immunity_tuple)
                            break

    def remove_condition_immunity(self, condition_name: str) -> None:
        """Remove static and contextual immunity rows for a condition.

        Args:
            condition_name: Condition name whose immunity rows should be removed.
        """
        if not self.allow_events_conditions:
            return None
        self._remove_static_condition_immunity(condition_name)
        self._remove_contextual_condition_immunity(condition_name)
        return
