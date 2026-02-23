from typing import Dict, Optional, Any, List, Self, Set, ClassVar, Callable, Tuple
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field, PrivateAttr, model_validator, computed_field, ConfigDict
from dnd.core.values import ModifiableValue
from dnd.core.base_conditions import BaseCondition, HazardFilter
from dnd.core.events import EventHandler, EventQueue, Trigger, Event, SpatialChangeEvent, EventPhase

from collections import defaultdict

ContextualConditionImmunity = Callable[['BaseBlock', Optional['BaseBlock'],Optional[dict]], bool]


class MovementMode(str, Enum):
    """Movement modes for entities."""
    WALKING = "walking"
    FLYING = "flying"
    SWIMMING = "swimming"
    BURROWING = "burrowing"


# =========================================================================
# Light Level
# =========================================================================

class LightLevel(int, Enum):
    """Light levels for tiles. Int values are for ordering comparisons only.
    Darkvision shifting uses explicit mapping (NOT arithmetic)."""
    MAGICAL_DARKNESS = 0   # Darkness spell - darkvision blocked
    DARKNESS = 1           # No light at all
    DIM_LIGHT = 2          # Shadows, edge of torchlight
    BRIGHT_LIGHT = 3       # Normal daylight, close to torch
    VERY_BRIGHT = 4        # Intense sunlight, Daylight spell


# =========================================================================
# Sense Types
# =========================================================================

class SensesType(str, Enum):
    BLINDSIGHT = "Blindsight"
    DARKVISION = "Darkvision"
    TREMORSENSE = "Tremorsense"
    TRUESIGHT = "Truesight"
    DEVILS_SIGHT = "Devils Sight"


class SenseMode(BaseModel):
    """A sense type with its effective range in feet. 0 = unlimited."""
    sense_type: SensesType
    range_feet: int = 0


class BaseBlock(BaseModel):
    """
    Base class for all block types in the system.

    This class serves as the foundation for various types of blocks that can be used to group
    and manage related values in the game system. It includes basic information about the block,
    such as its name, source, and target entities.

    Attributes:
        name (str): The name of the block. Defaults to 'A Block' if not specified.
        uuid (UUID): Unique identifier for the block. Automatically generated if not provided.
        source_entity_uuid (UUID): UUID of the entity that is the source of this block. Required.
        source_entity_name (Optional[str]): Name of the entity that is the source of this block. Can be None.
        target_entity_uuid (Optional[UUID]): UUID of the entity that this block targets, if any. Can be None.
        target_entity_name (Optional[str]): Name of the entity that this block targets, if any. Can be None.
        context (Optional[Dict[str, Any]]): Additional context information for this block. Can be None.
        blocks: Dict[UUID, 'BaseBlock'] = Field(
            default_factory=dict,
            description="Dictionary of all BaseBlock instances that are attributes of this class."
        )
        values: Dict[UUID, 'ModifiableValue'] = Field(
            default_factory=dict,
            description="Dictionary of all ModifiableValue instances that are attributes of this class."
        )

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseBlock']]): A class-level registry to store all instances.

    Methods:
        __init__(**data): Initialize the BaseBlock and register it in the class registry.
        get(cls, uuid: UUID) -> Optional['BaseBlock']:
            Retrieve a BaseBlock instance from the registry by its UUID.
        register(cls, value: 'BaseBlock') -> None:
            Register a BaseBlock instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseBlock instance from the class registry.
        get_values() -> List[ModifiableValue]:
            Searches through attributes and returns all ModifiableValue instances that are attributes of this class.
        get_blocks() -> List['BaseBlock']:
            Searches through attributes and returns all BaseBlock instances that are attributes of this class.
        set_target_entity(target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None:
            Set the target entity for all the values contained in this Block instance.
        clear_target_entity() -> None:
            Clear the target entity for all the values contained in this Block instance.
        set_context(context: Dict[str, Any]) -> None:
            Set the context for all the values contained in this Block instance.
        clear_context() -> None:
            Clear the context for all the values contained in this Block instance.
        clear() -> None:
            Clear the source, target, and context for all the values contained in this Block instance.
        create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None, 
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               name: str = "Base Block") -> 'BaseBlock':
            Create a new BaseBlock instance with the given parameters.
        get_value_from_uuid(uuid: UUID) -> Optional[ModifiableValue]:
            Get a ModifiableValue instance from this block by its UUID.
        get_value_from_name(name: str) -> Optional[ModifiableValue]:
            Get a ModifiableValue instance from this block by its name.
        get_block_from_uuid(uuid: UUID) -> Optional['BaseBlock']:
            Get a BaseBlock instance from this block by its UUID.
        get_block_from_name(name: str) -> Optional['BaseBlock']:
            Get a BaseBlock instance from this block by its name.

    Computed Fields:
        values_dict_uuid_name (Dict[UUID, str]): A dictionary mapping value UUIDs to their names.
        values_dict_name_uuid (Dict[str, UUID]): A dictionary mapping value names to their UUIDs.
        blocks_dict_uuid_name (Dict[UUID, str]): A dictionary mapping block UUIDs to their names.
        blocks_dict_name_uuid (Dict[str, UUID]): A dictionary mapping block names to their UUIDs.

    Validators:
        set_values_and_blocks_source: Ensures that all ModifiableValue and BaseBlock instances within the block
        have the same source and target UUIDs as the block itself.
        validate_values_and_blocks_source_and_target: Ensures that all ModifiableValue and BaseBlock instances
        within the block have matching source and target UUIDs.
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
        ...,  # This makes the field required
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

    position: Tuple[int,int] = Field(default_factory=lambda: (0,0))
    faction: Optional[str] = Field(default=None, description="Faction for ally/enemy detection. None = no faction.")

    # Perceivability flags (set by conditions, read by senses pipeline)
    stealth_dc: Optional[int] = Field(default=None, exclude=True,
        description="Stealth DC required to perceive. Set by Hidden condition.")
    is_invisible: bool = Field(default=False, exclude=True,
        description="Whether invisible. Set by Invisible condition.")

    # Light source tracking (UUIDs of light sources attached to this block)
    _attached_light_sources: Set[UUID] = PrivateAttr(default_factory=set)

    active_conditions: Dict[str, BaseCondition] = Field(default_factory=dict,description="Dictionary of active conditions, key is the condition name")
    active_conditions_by_uuid: Dict[UUID, BaseCondition] = Field(default_factory=dict,description="Dictionary of active conditions, key is the condition UUID")
    condition_immunities: List[Tuple[str,Optional[str]]] = Field(default_factory=list)
    contextual_condition_immunities: Dict[str, List[Tuple[str,ContextualConditionImmunity]]] = Field(default_factory=dict)
    active_conditions_by_source: Dict[UUID, List[str]] = Field(default_factory=lambda: defaultdict(list),description="Dictionary of active conditions by source entity UUID")

    event_handlers: Dict[UUID, EventHandler] = Field(default_factory=dict)
    event_handlers_by_trigger: Dict[Trigger, List[EventHandler]] = Field(default_factory=lambda: defaultdict(list))
    event_handlers_by_simple_trigger: Dict[Trigger, List[EventHandler]] = Field(default_factory=lambda: defaultdict(list))
    
    allow_events_conditions: bool = Field(default=False,description="If True, events and conditions will be allowed to be added to the block")

    _registry: ClassVar[Dict[UUID, 'BaseBlock']] = {}

    model_config = ConfigDict(validate_assignment=False)

    def _set_values_and_blocks_source(self, block: 'BaseBlock') -> None:
        """
        Helper function to set source and target for values and sub-blocks.

        Args:
            block (BaseBlock): The block to process.
        """
        # Use the dictionaries directly for better performance
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
            # Recursively apply to sub-blocks
            self._set_values_and_blocks_source(sub_block)

    @model_validator(mode='after')
    def set_values_and_blocks_source(self) -> 'Self':
        """
        Ensure that all ModifiableValue and BaseBlock instances within the block
        have the same source and target UUIDs as the block itself.

        Returns:
            Self: The modified instance of the class.
        """
        self._set_values_and_blocks_source(self)
        return self

    @model_validator(mode='after')
    def validate_values_and_blocks_source_and_target(self) -> Self:
        """
        Ensure that all ModifiableValue and BaseBlock instances within the block
        have matching source and target UUIDs.

        Returns:
            Self: The modified instance of the class.

        Raises:
            ValueError: If there is a mismatch in source or target UUIDs.
        """
        # Skip this validation for target entity operations
        # This validator only makes sense during initialization, not during target propagation
        
        # Check all values
        for _, value in self.values.items():
            if value.source_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"ModifiableValue '{value.name}' has mismatched source UUID")

        # Check all blocks
        for _, block in self.blocks.items():
            if block.source_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"BaseBlock '{block.name}' has mismatched source UUID")
                
        return self

    @model_validator(mode='after')
    def populate_blocks_and_values(self) -> Self:
        """
        Populates the blocks and values dictionaries with all BaseBlock and ModifiableValue
        instances that are attributes of this class. This is done once during initialization.
        """
        for name, _ in self.__class__.model_fields.items():
            attr_value = getattr(self, name)
            # Skip the dictionaries themselves to avoid recursion
            if name in ['blocks', 'values']:
                continue
                
            # Use Pydantic field annotations to determine types
            if isinstance(attr_value, ModifiableValue):
                self.values[attr_value.uuid] = attr_value
            elif isinstance(attr_value, BaseBlock):
                self.blocks[attr_value.uuid] = attr_value
                
        return self

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.__class__._registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['BaseBlock']:
        """
        Retrieve a BaseBlock instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the value to retrieve.

        Returns:
            Optional[BaseBlock]: The BaseBlock instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a BaseBlock instance.
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
        """
        Register a BaseBlock instance in the class registry.

        Args:
            value (BaseBlock): The value instance to register.
        """
        cls._registry[value.uuid] = value

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        """
        Remove a BaseBlock instance from the class registry.

        Args:
            uuid (UUID): The UUID of the value to unregister.
        """
        cls._registry.pop(uuid, None)

    def get_blocks(self) -> List['BaseBlock']:
        """
        Returns all BaseBlock instances that are attributes of this class.

        Returns:
            List[BaseBlock]: A list of BaseBlock instances.
        """
        return list(self.blocks.values())

    def get_values(self, deep: bool = False) -> List['ModifiableValue']:
        """
        Returns all ModifiableValue instances that are attributes of this class.
        If deep is True, it also includes values from all sub-blocks recursively.

        Args:
            deep (bool): If True, search recursively through all sub-blocks. Defaults to False.

        Returns:
            List[ModifiableValue]: A list of ModifiableValue instances found.
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

    # --- Perceivability system ---

    def set_stealth_dc(self, value: Optional[int]) -> None:
        """Set stealth DC and notify observers. Called by Hidden condition."""
        self.stealth_dc = value
        self._notify_perceivability_changed()

    def set_invisible(self, value: bool) -> None:
        """Set invisibility flag and notify observers. Called by Invisible condition."""
        self.is_invisible = value
        self._notify_perceivability_changed()

    def _notify_perceivability_changed(self) -> None:
        """Fire a SPATIAL_PERCEIVABILITY_CHANGED event at this block's position.

        Entities subscribed to this cell via SpatialSensesCallback will
        re-evaluate their senses. Does not trigger SpatialHandlers (zone effects).
        """
        event = SpatialChangeEvent.perceivability_changed(self.position, self.uuid)
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
        """Passive perception of this block as an observer. Default 0.
        Entity overrides with passive_skill('perception')."""
        return 0

    def can_bypass_invisibility(self) -> bool:
        """Whether this block can see invisible things. Default False.
        Entity overrides by checking sense_modes for TRUESIGHT/BLINDSIGHT/TREMORSENSE."""
        return False

    def can_pierce_magical_darkness(self) -> bool:
        """Whether this block can see through magical darkness. Default False.
        Entity overrides by checking sense_modes for TRUESIGHT/DEVILS_SIGHT."""
        return False

    def get_sense_modes(self) -> List[SenseMode]:
        """Sense modes of this block as an observer. Default empty.
        Entity overrides to relay to self.senses.get_sense_modes()."""
        return []

    # --- Virtual methods for Entity features (overridden by Entity) ---

    def get_senses(self) -> Optional[Self]:
        """Override in Entity to return Senses block for subjective perception."""
        return None

    @property
    def is_active(self) -> bool:
        """Whether this block is active and should be included in interactions.
        Default True. Override in Entity/BaseItem for health-aware checks."""
        return True

    def get_hp(self) -> int:
        """Override in Entity/BaseItem to return current HP. Default: 0 (no health system)."""
        return 0

    # --- Light source tracking ---

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
        """Whether this block can be perceived by the requesting entity.
        Same signature pattern as blocks_walking(requesting_entity_uuid).
        Reads stealth_dc and is_invisible flags set by conditions."""
        if requesting_entity_uuid is None:
            return True

        observer = BaseBlock.get(requesting_entity_uuid)
        if observer is None:
            return True

        if self.is_invisible:
            if not observer.can_bypass_invisibility():
                return False

        if self.stealth_dc is not None:
            if self.stealth_dc > observer.get_passive_perception():
                return False

        return True

    def is_enemy_of(self, other_uuid: UUID) -> bool:
        """Whether this block considers other_uuid an enemy.
        Default: True (unknown blocks are enemies).
        Entity overrides with faction-based logic."""
        return True

    def is_hazardous_for(self, entity_uuid: Optional[UUID] = None) -> bool:
        """Whether this block has conditions that are hazardous to the given entity.
        Checks hazard_filter and condition_stealth_dc on each active condition."""
        for cond in self.active_conditions.values():
            if cond.hazard_filter is None:
                continue

            # Can entity perceive this hazard?
            if cond.condition_stealth_dc is not None and entity_uuid is not None:
                observer = BaseBlock.get(entity_uuid)
                if observer is not None and cond.condition_stealth_dc > observer.get_passive_perception():
                    continue  # Can't see it → don't avoid it

            # Who does it affect?
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
        """
        Set the target entity for all the values and sub-blocks contained in this Block instance.

        Args:
            target_entity_uuid (UUID): The UUID of the target entity.
            target_entity_name (Optional[str]): The name of the target entity, if available.
        """
        if not isinstance(target_entity_uuid, UUID):
            raise ValueError("target_entity_uuid must be a UUID")

        self.target_entity_uuid = target_entity_uuid
        self.target_entity_name = target_entity_name

        # Use dictionaries directly for better performance
        for value in self.values.values():
            value.set_target_entity(target_entity_uuid, target_entity_name)

        for block in self.blocks.values():
            block.set_target_entity(target_entity_uuid, target_entity_name)

    def clear_target_entity(self) -> None:
        """
        Clear the target entity for all the values and sub-blocks contained in this Block instance.
        """
        # Use dictionaries directly for better performance
        for value in self.values.values():
            value.clear_target_entity()

        for block in self.blocks.values():
            block.clear_target_entity()
        
        self.target_entity_uuid = None
        self.target_entity_name = None

    def set_context(self, context: Dict[str, Any]) -> None:
        """
        Set the context for all the values contained in this Block instance.
        """
        self.context = context
        
        # Use dictionaries directly for better performance
        for value in self.values.values():
            value.set_context(context)
            
        for block in self.blocks.values():
            block.set_context(context)
    
    def clear_context(self) -> None:
        """
        Clear the context for all the values contained in this Block instance.
        """
        self.context = None
        
        # Use dictionaries directly for better performance
        for value in self.values.values():
            value.clear_context()
            
        for block in self.blocks.values():
            block.clear_context()
    

    def clear(self) -> None:
        """
        Clear the source, target, and context for all the values contained in this Block instance.
        """
        self.clear_target_entity()
        self.clear_context()

    def remove_contained_item(self, item_uuid: UUID) -> None:
        """Remove a contained item by UUID. No-op by default.
        Overridden by Inventory to remove from items dict."""
        pass

    @classmethod
    def create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
                name: str = "Base Block") -> 'BaseBlock':
        """
        Create a new BaseBlock instance with the given parameters. Subclasses should override this method to add their own attributes and handle the modifiable values initialization in the method.

        Args:
            source_entity_uuid (UUID): The UUID of the source entity.
            source_entity_name (Optional[str]): The name of the source entity.
            target_entity_uuid (Optional[UUID]): The UUID of the target entity.
            target_entity_name (Optional[str]): The name of the target entity.
            name (str): The name of the block. Defaults to "Base Block".

        Returns:
            BaseBlock: The newly created BaseBlock instance.
        """
        return cls(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, name=name)

    @computed_field
    @property
    def values_dict_uuid_name(self) -> Dict[UUID, str]:
        """
        A dictionary mapping value UUIDs to their names.

        Returns:
            Dict[UUID, str]: A dictionary mapping value UUIDs to their names.
        """
        return {value.uuid: value.name for value in self.get_values()}

    @computed_field
    @property
    def values_dict_name_uuid(self) -> Dict[str, UUID]:
        """
        A dictionary mapping value names to their UUIDs.

        Returns:
            Dict[str, UUID]: A dictionary mapping value names to their UUIDs.
        """
        return {value.name: value.uuid for value in self.get_values()}

    @computed_field
    @property
    def blocks_dict_uuid_name(self) -> Dict[UUID, str]:
        """
        A dictionary mapping block UUIDs to their names.

        Returns:
            Dict[UUID, str]: A dictionary mapping block UUIDs to their names.
        """
        return {block.uuid: block.name for block in self.get_blocks()}

    @computed_field
    @property
    def blocks_dict_name_uuid(self) -> Dict[str, UUID]:
        """
        A dictionary mapping block names to their UUIDs.

        Returns:
            Dict[str, UUID]: A dictionary mapping block names to their UUIDs.
        """
        return {block.name: block.uuid for block in self.get_blocks()}

    def get_value_from_uuid(self, uuid: UUID) -> Optional[ModifiableValue]:
        """
        Get a ModifiableValue instance from this block by its UUID.

        Args:
            uuid (UUID): The UUID of the value to retrieve.

        Returns:
            Optional[ModifiableValue]: The ModifiableValue instance if found, None otherwise.
        """
        return self.values.get(uuid)

    def get_value_from_name(self, name: str) -> Optional[ModifiableValue]:
        """
        Get a ModifiableValue instance from this block by its name.

        Args:
            name (str): The name of the value to retrieve.

        Returns:
            Optional[ModifiableValue]: The ModifiableValue instance if found, None otherwise.
        """
        for value in self.values.values():
            if value.name == name:
                return value
        return None

    def get_block_from_uuid(self, uuid: UUID) -> Optional['BaseBlock']:
        """
        Get a BaseBlock instance from this block by its UUID.

        Args:
            uuid (UUID): The UUID of the block to retrieve.

        Returns:
            Optional[BaseBlock]: The BaseBlock instance if found, None otherwise.
        """
        return self.blocks.get(uuid)

    def get_block_from_name(self, name: str) -> Optional['BaseBlock']:
        """
        Get a BaseBlock instance from this block by its name.

        Args:
            name (str): The name of the block to retrieve.

        Returns:
            Optional[BaseBlock]: The BaseBlock instance if found, None otherwise.
        """
        for block in self.blocks.values():
            if block.name == name:
                return block
        return None
    
    
    def add_event_handler(self, event_handler: EventHandler) -> None:
        if not self.allow_events_conditions:
            return None
        self.event_handlers[event_handler.uuid] = event_handler
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                self.event_handlers_by_simple_trigger[trigger].append(event_handler)
            self.event_handlers_by_trigger[trigger].append(event_handler)
        EventQueue.add_event_handler(event_handler)

    def remove_event_handler_from_dicts(self, event_handler: EventHandler) -> None:
        if not self.allow_events_conditions:
            return None
        self.event_handlers.pop(event_handler.uuid)
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                self.event_handlers_by_simple_trigger[trigger].remove(event_handler)
            self.event_handlers_by_trigger[trigger].remove(event_handler)

    def remove_event_handler(self, event_handler: EventHandler) -> None:
        if not self.allow_events_conditions:
            return None
        event_handler.remove() #this is already handling the removal from the event queue and the dicts

    def get_event_handler_by_name(self, name: str) -> Optional[EventHandler]:
        """Find the first event handler on this block matching the given name (case-insensitive)."""
        name_lower = name.lower()
        for handler in self.event_handlers.values():
            if handler.name.lower() == name_lower:
                return handler
        return None

    def get_event_handlers_by_name(self, name: str) -> List[EventHandler]:
        """Find all event handlers on this block matching the given name (case-insensitive)."""
        name_lower = name.lower()
        return [h for h in self.event_handlers.values() if h.name.lower() == name_lower]

    def set_handler_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable the first player-toggleable handler matching the given name. Returns True if found."""
        handler = self.get_event_handler_by_name(name)
        if handler is not None and handler.player_toggleable:
            handler.enabled = enabled
            return True
        return False

    def set_handler_enabled_by_uuid(self, handler_uuid: UUID, enabled: bool) -> bool:
        """Enable or disable a specific player-toggleable handler by UUID. Returns True if found."""
        handler = self.event_handlers.get(handler_uuid)
        if handler is not None and handler.player_toggleable:
            handler.enabled = enabled
            return True
        return False

    def _remove_condition_from_dicts(self, condition: BaseCondition) -> None:
        if not self.allow_events_conditions:
            return None
        condition_name = condition.name
        assert condition.source_entity_uuid is not None and condition_name is not None
        self.active_conditions_by_source[condition.source_entity_uuid].remove(condition_name)
        # Also remove from by_uuid dict (was missing - memory leak fix)
        if condition.uuid in self.active_conditions_by_uuid:
            del self.active_conditions_by_uuid[condition.uuid]

    def _collect_all_sub_conditions(self, condition: BaseCondition) -> List[BaseCondition]:
        """Recursively collect all sub-conditions (children, grandchildren, etc.).

        This ensures when a condition is removed, ALL nested sub-conditions
        are also removed from active_conditions, not just immediate children.
        """
        all_subs: List[BaseCondition] = []
        for sub_uuid in condition.sub_conditions:
            sub = BaseCondition.get(sub_uuid)
            if sub is not None and isinstance(sub, BaseCondition):
                all_subs.append(sub)
                # Recursively get sub-conditions of this sub-condition
                all_subs.extend(self._collect_all_sub_conditions(sub))
        return all_subs

    def remove_condition(self, condition_name: str, expire: bool = False,
                         parent_event: Optional[Event] = None) -> None:
        """Remove a condition with full cross-block tree traversal.

        Handles sub-conditions (same block), linked_conditions (other blocks),
        and own state cleanup via _remove_condition_tree().

        Args:
            condition_name: Name of the condition to remove
            expire: Whether this is an expiration removal (fires _expire hook)
            parent_event: Parent event for event chain tracking
        """
        if not self.allow_events_conditions:
            return
        if condition_name not in self.active_conditions:
            return

        condition = self.active_conditions.pop(condition_name)

        # Collect and remove sub-conditions from tracking dicts FIRST
        # This must happen BEFORE _remove_condition_tree to avoid duplicate removals
        all_sub_conditions = self._collect_all_sub_conditions(condition)
        for sub_condition in all_sub_conditions:
            if sub_condition.name is not None and sub_condition.name in self.active_conditions:
                self.active_conditions.pop(sub_condition.name)
            if sub_condition.name in self.active_conditions_by_source.get(
                    sub_condition.source_entity_uuid, []):
                self._remove_condition_from_dicts(sub_condition)

        # Remove main condition from dicts
        if condition.name in self.active_conditions_by_source.get(
                condition.source_entity_uuid, []):
            self._remove_condition_from_dicts(condition)

        # Full tree traversal cleanup
        self._remove_condition_tree(condition, expire=expire, parent_event=parent_event)

    def remove_condition_by_uuid(self, condition_uuid: UUID,
                                 parent_event: Optional[Event] = None) -> None:
        """Remove a condition by UUID. Used for cross-block cleanup."""
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
        """
        # 1. Sub-conditions (same block — recurse for their cross-block deps)
        for sub_uuid in list(condition.sub_conditions):
            sub = BaseCondition.get(sub_uuid)
            if sub is not None and isinstance(sub, BaseCondition):
                self._remove_condition_tree(sub, expire=expire, parent_event=parent_event)

        # 2. Linked conditions (ANY other BaseBlock)
        for target_uuid, cond_uuid in condition.linked_conditions:
            target_block = BaseBlock.get(target_uuid)
            if target_block is not None:
                target_block.remove_condition_by_uuid(cond_uuid, parent_event=parent_event)

        # 3. Own state cleanup
        condition.cleanup_own_state(expire=expire, parent_event=parent_event)

        # 4. Notify linked parent of child removal (reverse link)
        if condition.parent_link is not None:
            parent_block_uuid, parent_cond_uuid = condition.parent_link
            parent_cond = BaseCondition.get(parent_cond_uuid)
            if (parent_cond is not None
                    and isinstance(parent_cond, BaseCondition)
                    and parent_cond.applied
                    and parent_cond.name is not None):
                parent_block = BaseBlock.get(parent_block_uuid)
                if parent_block is not None and parent_cond.name in parent_block.active_conditions:
                    # Guard passed: parent is still active (not mid-removal)
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
        """Progress condition duration, remove if expired. No saving throws.

        For entities, use Entity.advance_duration_condition() which handles saves.
        Returns True if removed.
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
        if not self.allow_events_conditions:
            return None
        if condition.name is None:
            raise ValueError("BaseCondition name is not set")
        if condition.target_entity_uuid is None:
            condition.target_entity_uuid = self.uuid
        if context is not None:
            condition.set_context(context)
        
        condition_applied = condition.apply(event)
        if condition_applied:
            if condition.name in self.active_conditions:
                #already present we need to remove the old one and add the new one for now not stackable
                self.remove_condition(condition.name)
            self.active_conditions[condition.name] = condition
            self.active_conditions_by_uuid[condition.uuid] = condition
            self.active_conditions_by_source[condition.source_entity_uuid].append(condition.name)
    
        return condition_applied
    

    def add_static_condition_immunity(self, condition_name: str,immunity_name: Optional[str]=None):
        if not self.allow_events_conditions:
            return None
        self.condition_immunities.append((condition_name,immunity_name))
    
    def _remove_static_condition_immunity(self, condition_name: str,immunity_name: Optional[str]=None):
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
    
    def add_contextual_condition_immunity(self, condition_name: str, immunity_name:str, immunity_check: ContextualConditionImmunity):
        if not self.allow_events_conditions:
            return None
        if condition_name not in self.contextual_condition_immunities:
            self.contextual_condition_immunities[condition_name] = []
        self.contextual_condition_immunities[condition_name].append((immunity_name,immunity_check))

    def add_condition_immunity(self, condition_name: str, immunity_name: Optional[str]=None, immunity_check: Optional[ContextualConditionImmunity]=None):
        if not self.allow_events_conditions:
            return None
        if immunity_check is not None:
            if immunity_name is None:
                raise ValueError("Immunity name is required when adding a contextual BaseCondition immunity")
            self.add_contextual_condition_immunity(condition_name,immunity_name,immunity_check)
        else:
            self.add_static_condition_immunity(condition_name,immunity_name)
    
    def _remove_contextual_condition_immunity(self, condition_name: str, immunity_name: Optional[str]=None):
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
        if not self.allow_events_conditions:
            return None
        self._remove_static_condition_immunity(condition_name)
        self._remove_contextual_condition_immunity(condition_name)
        return

