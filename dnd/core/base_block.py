from typing import Dict, Optional, Any, List, Self, Set, ClassVar, Callable, Tuple
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field, PrivateAttr, model_validator, computed_field, ConfigDict
from dnd.core.values import ModifiableValue
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import HazardFilter
from dnd.core.content.runtime import (
    bind_runtime_behavior,
    bind_runtime_handler_before_admission,
)
from dnd.core.events import EventHandler, EventQueue, Trigger, Event, SpatialChangeEvent, EventPhase
from dnd.core.senses import SenseMode as SenseMode, SensesType as SensesType

from collections import defaultdict

ContextualConditionImmunity = Callable[['BaseBlock', Optional['BaseBlock'], Optional[dict]], bool]


class MovementMode(str, Enum):
    """Movement modes for entities."""
    WALKING = "walking"
    FLYING = "flying"
    SWIMMING = "swimming"
    BURROWING = "burrowing"


class LightLevel(int, Enum):
    """Tile light levels ordered from most obscuring to brightest.

    The integer values support ordering comparisons. Darkvision uses explicit
    mapping rules rather than arithmetic over these enum values.
    """

    MAGICAL_DARKNESS = 0
    DARKNESS = 1
    DIM_LIGHT = 2
    BRIGHT_LIGHT = 3
    VERY_BRIGHT = 4

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

    def blocks_vision(self, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        """Whether this block prevents vision through its position.
        Non-spatial blocks inherit this default."""
        return False

    def blocks_directional_movement(self, direction: str,
                                    requesting_entity_uuid: Optional[UUID] = None,
                                    mode: 'MovementMode' = MovementMode.WALKING,
                                    subjective: bool = False) -> bool:
        """Whether this block prevents movement out of its tile in a direction."""
        return False

    def blocks_directional_vision(self, direction: str,
                                  observer_uuid: Optional[UUID] = None,
                                  subjective: bool = False) -> bool:
        """Whether this block prevents vision crossing out of its tile in a direction."""
        return False

    def blocks_directional_light(self, direction: str,
                                 observer_uuid: Optional[UUID] = None,
                                 subjective: bool = False) -> bool:
        """Whether this block prevents light crossing out of its tile in a direction."""
        return False

    def blocks_directional_propagation(self, direction: str,
                                       requesting_entity_uuid: Optional[UUID] = None,
                                       subjective: bool = False) -> bool:
        """Whether this block prevents physical propagation out of its tile in a direction."""
        return False

    def set_stealth_dc(self, value: Optional[int], parent_event: Optional[UUID] = None) -> None:
        """Set stealth DC and notify observers."""
        self.stealth_dc = value
        self._notify_perceivability_changed(parent_event=parent_event)

    def set_invisible(self, value: bool, parent_event: Optional[UUID] = None) -> None:
        """Set invisibility flag and notify observers."""
        self.is_invisible = value
        self._notify_perceivability_changed(parent_event=parent_event)

    def _notify_perceivability_changed(self, parent_event: Optional[UUID] = None) -> None:
        """Fire a SPATIAL_PERCEIVABILITY_CHANGED event at this block's position.

        Entities subscribed to this cell via SpatialSensesCallback will
        re-evaluate their senses. Does not trigger SpatialHandlers (zone effects).
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

    def can_bypass_invisibility(self) -> bool:
        """Return whether this block can perceive invisible things."""
        return False

    def can_pierce_magical_darkness(self) -> bool:
        """Return whether this block can see through magical darkness."""
        return False

    def get_sense_modes(self) -> List[SenseMode]:
        """Return sense modes for this block as an observer."""
        return []

    def get_senses(self) -> Optional[Self]:
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

    def is_perceivable_by(self, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        """Return whether this block is perceivable by an optional observer."""
        if requesting_entity_uuid is None:
            return True

        observer = BaseBlock.get(requesting_entity_uuid)
        if observer is None:
            return True

        if self.is_invisible:
            if not observer.can_bypass_invisibility():
                return False

        if self.stealth_dc is not None:
            if self.stealth_dc >= observer.get_passive_perception():
                return False

        return True

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
        bind_runtime_handler_before_admission(event_handler)
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

    def _remove_condition_from_dicts(self, condition: BaseCondition) -> None:
        """Remove a condition from block-local condition indexes.

        Args:
            condition: Condition to remove from index dictionaries.
        """
        if not self.allow_events_conditions:
            return None
        condition_name = condition.name
        assert condition.source_entity_uuid is not None and condition_name is not None
        self.active_conditions_by_source[condition.source_entity_uuid].remove(condition_name)
        if condition.uuid in self.active_conditions_by_uuid:
            del self.active_conditions_by_uuid[condition.uuid]

    def _collect_all_sub_conditions(self, condition: BaseCondition) -> List[BaseCondition]:
        """Recursively collect same-block descendants for a condition.

        Args:
            condition: Root condition whose sub-condition tree should be walked.

        Returns:
            Descendant conditions in traversal order.
        """
        all_subs: List[BaseCondition] = []
        for sub_uuid in condition.sub_conditions:
            sub = BaseCondition.get(sub_uuid)
            if sub is not None and isinstance(sub, BaseCondition):
                all_subs.append(sub)
                all_subs.extend(self._collect_all_sub_conditions(sub))
        return all_subs

    def remove_condition(self, condition_name: str, expire: bool = False,
                         parent_event: Optional[Event] = None) -> None:
        """Remove a condition with full cross-block tree traversal.

        Handles sub-conditions (same block), linked_conditions (other blocks),
        and own state cleanup via _remove_condition_tree().

        Args:
            condition_name: Name of the condition to remove.
            expire: Whether this is an expiration removal.
            parent_event: Parent event for event-chain tracking.
        """
        if not self.allow_events_conditions:
            return
        if condition_name not in self.active_conditions:
            return

        condition = self.active_conditions.pop(condition_name)

        all_sub_conditions = self._collect_all_sub_conditions(condition)
        for sub_condition in all_sub_conditions:
            if sub_condition.name is not None and sub_condition.name in self.active_conditions:
                self.active_conditions.pop(sub_condition.name)
            if sub_condition.name in self.active_conditions_by_source.get(
                    sub_condition.source_entity_uuid, []):
                self._remove_condition_from_dicts(sub_condition)

        if condition.name in self.active_conditions_by_source.get(
                condition.source_entity_uuid, []):
            self._remove_condition_from_dicts(condition)

        self._remove_condition_tree(condition, expire=expire, parent_event=parent_event)

    def remove_condition_by_uuid(self, condition_uuid: UUID,
                                 parent_event: Optional[Event] = None) -> None:
        """Remove a condition by UUID.

        Args:
            condition_uuid: UUID of the condition to remove.
            parent_event: Optional parent event for cleanup event lineage.
        """
        if not self.allow_events_conditions:
            return
        condition = self.active_conditions_by_uuid.get(condition_uuid)
        if condition is None:
            return
        if condition.name is not None:
            self.remove_condition(condition.name, parent_event=parent_event)

    def _remove_condition_tree(self, condition: BaseCondition, expire: bool = False,
                               parent_event: Optional[Event] = None) -> None:
        """Recursively remove condition and all cross-block dependencies.

        Handles sub-conditions (same block), linked_conditions (other blocks),
        and own state cleanup. Tracking dicts are already cleaned up by
        remove_condition() before this is called.

        Args:
            condition: Root condition to remove.
            expire: Whether this removal is an expiration path.
            parent_event: Optional parent event for cleanup event lineage.
        """
        for sub_uuid in list(condition.sub_conditions):
            sub = BaseCondition.get(sub_uuid)
            if sub is not None and isinstance(sub, BaseCondition):
                self._remove_condition_tree(sub, expire=expire, parent_event=parent_event)

        for target_uuid, cond_uuid in condition.linked_conditions:
            target_block = BaseBlock.get(target_uuid)
            if target_block is not None:
                target_block.remove_condition_by_uuid(cond_uuid, parent_event=parent_event)

        condition.cleanup_own_state(expire=expire, parent_event=parent_event)

        if condition.parent_link is not None:
            parent_block_uuid, parent_cond_uuid = condition.parent_link
            parent_cond = BaseCondition.get(parent_cond_uuid)
            if (parent_cond is not None
                    and isinstance(parent_cond, BaseCondition)
                    and parent_cond.applied
                    and parent_cond.name is not None):
                parent_block = BaseBlock.get(parent_block_uuid)
                if parent_block is not None and parent_cond.name in parent_block.active_conditions:
                    policy = parent_cond.child_removal_policy
                    if policy == "any":
                        parent_block.remove_condition(parent_cond.name, parent_event=parent_event)
                    elif policy == "last":
                        remaining = sum(
                            1 for _, cid in parent_cond.linked_conditions
                            if (c := BaseCondition.get(cid)) is not None
                            and isinstance(c, BaseCondition) and c.applied
                        )
                        if remaining == 0:
                            parent_block.remove_condition(parent_cond.name, parent_event=parent_event)

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

    def add_condition(self, condition: BaseCondition, context: Optional[Dict[str, Any]] = None, check_save_throw: bool = True, event: Optional[Event] = None)  -> Optional[Event]:
        """Apply and index a condition when lifecycle is enabled.

        Args:
            condition: Condition to apply.
            context: Optional context to attach before applying.
            check_save_throw: Accepted for API symmetry; block-level condition
                application does not perform saving throws.
            event: Optional pre-built declaration event.

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
            runtime_owner_uuid=self.uuid,
        )
        if context is not None:
            condition.set_context(context)

        condition_applied = condition.apply(event)
        if condition_applied and not condition_applied.canceled and condition.applied:
            if condition.name in self.active_conditions:
                self.remove_condition(condition.name)
            self.active_conditions[condition.name] = condition
            self.active_conditions_by_uuid[condition.uuid] = condition
            self.active_conditions_by_source[condition.source_entity_uuid].append(condition.name)

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
