from typing import ClassVar, Dict, Optional, Any, List, Self
from uuid import UUID, uuid4
from webbrowser import get
from pydantic import BaseModel, Field, model_validator, computed_field
from dnd.values import ModifiableValue

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
        set_target_entity(target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None:
            Set the target entity for all the values contained in this Block instance.
        clear_target_entity() -> None:
            Clear the target entity for all the values contained in this Block instance.

    Validators:
        validate_values_source_and_target: Ensures that all ModifiableValue instances within the block
        have the same source and target UUIDs as the block itself.
    """

    name: str = Field(
        default="A Block",
        description="The name of the block. Defaults to 'A Block' if not specified."
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

    _registry: ClassVar[Dict[UUID, 'BaseBlock']] = {}

    class Config:
        validate_assignment = True

    @model_validator(mode='after')
    def set_values_and_blocks_source(self) -> 'Self':
        for value in self.get_values():
            value.source_entity_uuid = self.source_entity_uuid
            value.source_entity_name = self.source_entity_name
            if self.context is not None:
                value.set_context(self.context)
            if self.target_entity_uuid is not None:
                value.set_target_entity(self.target_entity_uuid, self.target_entity_name)
        for block in self.get_blocks():
            block.source_entity_uuid = self.source_entity_uuid
            block.source_entity_name = self.source_entity_name
            if self.context is not None:
                block.set_context(self.context)
            if self.target_entity_uuid is not None:
                block.set_target_entity(self.target_entity_uuid, self.target_entity_name)
        return self

    @model_validator(mode='after')
    def validate_values_and_blocks_source_and_target(self) -> Self:
        for attr_name, attr_value in self.__dict__.items():
            if isinstance(attr_value, ModifiableValue):
                if attr_value.source_entity_uuid != self.source_entity_uuid:
                    raise ValueError(f"ModifiableValue '{attr_name}' has mismatched source UUID")
                if attr_value.target_entity_uuid != self.target_entity_uuid:
                    raise ValueError(f"ModifiableValue '{attr_name}' has mismatched target UUID")
            elif isinstance(attr_value, BaseBlock):
                if attr_value.source_entity_uuid != self.source_entity_uuid:
                    raise ValueError(f"BaseBlock '{attr_name}' has mismatched source UUID")
                if attr_value.target_entity_uuid != self.target_entity_uuid:
                    raise ValueError(f"BaseBlock '{attr_name}' has mismatched target UUID")
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
        Searches through attributes and returns all BaseBlock instances that are attributes of this class.

        Returns:
            List[BaseBlock]: A list of BaseBlock instances found in the attributes of this class.
        """
        blocks = []
        for name, field in self.__class__.model_fields.items():
            if isinstance(field.annotation, type) and issubclass(field.annotation, BaseBlock):
                blocks.append(getattr(self, name))
        return blocks

    def get_values(self, deep: bool = False) -> List[ModifiableValue]:
        """
        Searches through attributes and returns all ModifiableValue instances that are attributes of this class.
        If deep is True, it also searches through all sub-blocks recursively.

        Args:
            deep (bool): If True, search recursively through all sub-blocks. Defaults to False.

        Returns:
            List[ModifiableValue]: A list of ModifiableValue instances found.
        """
        values = []
        for name, field in self.__class__.model_fields.items():
            attr_value = getattr(self, name)
            if isinstance(attr_value, ModifiableValue):
                values.append(attr_value)
            elif deep and isinstance(attr_value, BaseBlock):
                values.extend(attr_value.get_values(deep=True))
        return values

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

        for value in self.get_values():
            value.set_target_entity(target_entity_uuid, target_entity_name)

        for block in self.get_blocks():
            block.set_target_entity(target_entity_uuid, target_entity_name)

    def clear_target_entity(self) -> None:
        """
        Clear the target entity for all the values and sub-blocks contained in this Block instance.
        """
        

        for value in self.get_values():
            value.clear_target_entity()

        for block in self.get_blocks():
            block.clear_target_entity()
        
        self.target_entity_uuid = None
        self.target_entity_name = None

    def set_context(self, context: Dict[str, Any]) -> None:
        """
        Set the context for all the values contained in this Block instance.
        """
        self.context = context
        values = self.get_values()
        for value in values:
            value.set_context(context)
        for block in self.get_blocks():
            block.set_context(context)
    
    def clear_context(self) -> None:
        """
        Clear the context for all the values contained in this Block instance.
        """
        self.context = None
        values = self.get_values()
        for value in values:
            value.clear_context()
        for block in self.get_blocks():
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
        return cls(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, name=name)

def ability_score_normalizer(score: int) -> int:
    """ Normalizes the ability score to obtain the modifier with: (score - 10) // 2 """
    return (score - 10) // 2

class Ability(BaseBlock):
    name: str = Field(default="Ability Score")
    ability_score: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=10, value_name="Ability Score",score_normalizer=ability_score_normalizer))
    modifier_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Modifier Bonus"))
    @classmethod
    def get(cls, uuid: UUID) -> Optional['Ability']:
        obj= super().get(uuid)
        if obj is not None and not isinstance(obj, Ability):
            raise ValueError(f"Value with UUID {uuid} is not an AbilityScore, but {type(obj)}")
        return obj
    @computed_field
    @property
    def modifier(self) -> int:
        """ Combines the ability score, normalized with: (score - 10) // 2, and the modifier bonus """
        return self.ability_score.normalized_score + self.modifier_bonus.score
    
    
class AbilityScores(BaseBlock):
    name: str = Field(default="AbilityScores")
    strength: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="Strength"))
    dexterity: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="Dexterity"))
    constitution: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="Constitution"))
    intelligence: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="Intelligence"))
    wisdom: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="Wisdom"))
    charisma: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="Charisma"))

    
