from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier
from dnd.core.base_conditions import BaseCondition
from dnd.core.events import EventHandler, EventQueue, Trigger, Event
from enum import Enum
from random import randint
from functools import cached_property
from typing import Literal as TypeLiteral
from collections import defaultdict

ContextualConditionImmunity = Callable[['BaseBlock', Optional['BaseBlock'],Optional[dict]], bool]


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

    class Config:
        validate_assignment = False

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
        for uuid, value in self.values.items():
            if value.source_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"ModifiableValue '{value.name}' has mismatched source UUID")
                
        # Check all blocks
        for uuid, block in self.blocks.items():
            if block.source_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"BaseBlock '{block.name}' has mismatched source UUID")
                
        return self

    @model_validator(mode='after')
    def populate_blocks_and_values(self) -> Self:
        """
        Populates the blocks and values dictionaries with all BaseBlock and ModifiableValue
        instances that are attributes of this class. This is done once during initialization.
        """
        for name, field in self.__class__.model_fields.items():
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

    def __init__(self, **data):
        """
        Initialize the BaseBlock and register it in the class registry.

        Args:
            **data: Keyword arguments to initialize the BaseBlock attributes.
        """
        super().__init__(**data)
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

    def _remove_condition_from_dicts(self, condition: BaseCondition) -> None:
        if not self.allow_events_conditions:
            return None
        condition_name = condition.name
        assert condition.source_entity_uuid is not None and condition_name is not None
        self.active_conditions_by_source[condition.source_entity_uuid].remove(condition_name)

    def remove_condition(self, condition_name: str) -> None:
        if not self.allow_events_conditions:
            return None
        condition = self.active_conditions.pop(condition_name)
        for sub_condition_uuid in condition.sub_conditions:
            sub_condition = BaseCondition.get(sub_condition_uuid)
            if sub_condition is not None and sub_condition.name is not None:
                self.active_conditions.pop(sub_condition.name)
        condition.remove()
        self._remove_condition_from_dicts(condition)
    
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

