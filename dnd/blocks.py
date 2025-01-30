
from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.values import ModifiableValue
from dnd.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws
from enum import Enum
from random import randint
from functools import cached_property

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

    def _set_values_and_blocks_source(self, block: 'BaseBlock') -> None:
        """
        Helper function to set source and target for values and sub-blocks.

        Args:
            block (BaseBlock): The block to process.
        """
        for value in block.get_values():
            value.set_source_entity(block.source_entity_uuid, block.source_entity_name)
            if block.context is not None:
                value.set_context(block.context)
            if block.target_entity_uuid is not None:
                value.set_target_entity(block.target_entity_uuid, block.target_entity_name)
        
        for sub_block in block.get_blocks():
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
        """
        Create a new BaseBlock instance with the given parameters.

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
        for value in self.get_values():
            if value.uuid == uuid:
                return value
        return None

    def get_value_from_name(self, name: str) -> Optional[ModifiableValue]:
        """
        Get a ModifiableValue instance from this block by its name.

        Args:
            name (str): The name of the value to retrieve.

        Returns:
            Optional[ModifiableValue]: The ModifiableValue instance if found, None otherwise.
        """
        for value in self.get_values():
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
        for block in self.get_blocks():
            if block.uuid == uuid:
                return block
        return None

    def get_block_from_name(self, name: str) -> Optional['BaseBlock']:
        """
        Get a BaseBlock instance from this block by its name.

        Args:
            name (str): The name of the block to retrieve.

        Returns:
            Optional[BaseBlock]: The BaseBlock instance if found, None otherwise.
        """
        for block in self.get_blocks():
            if block.name == name:
                return block
        return None

def ability_score_normalizer(score: int) -> int:
    """ Normalizes the ability score to obtain the modifier with: (score - 10) // 2 """
    return (score - 10) // 2
abilities = Literal['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']

class Ability(BaseBlock):
    """
    Represents an ability score in the D&D 5e game system.

    This class extends BaseBlock to represent a specific ability score, including its
    base value and any modifiers.

    Attributes:
        name (abilities): The name of the ability (e.g., 'strength', 'dexterity', etc.).
        ability_score (ModifiableValue): The base ability score value, typically ranging from 3 to 20 for most characters.
        modifier_bonus (ModifiableValue): Any additional bonus to the ability modifier, separate from the base score.
        uuid (UUID): Unique identifier for the block. (Inherited from BaseBlock)
        source_entity_uuid (UUID): UUID of the entity that is the source of this block. (Inherited from BaseBlock)
        source_entity_name (Optional[str]): Name of the entity that is the source of this block. (Inherited from BaseBlock)
        target_entity_uuid (Optional[UUID]): UUID of the entity that this block targets, if any. (Inherited from BaseBlock)
        target_entity_name (Optional[str]): Name of the entity that this block targets, if any. (Inherited from BaseBlock)
        context (Optional[Dict[str, Any]]): Additional context information for this block. (Inherited from BaseBlock)

    Inherits all attributes and methods from BaseBlock.

    Additional Methods:
        get(cls, uuid: UUID) -> Optional['Ability']:
            Retrieve an Ability instance from the registry by its UUID.
        get_values() -> List[ModifiableValue]: (Inherited from BaseBlock)
            Searches through attributes and returns all ModifiableValue instances that are attributes of this class.
        get_blocks() -> List['BaseBlock']: (Inherited from BaseBlock)
            Searches through attributes and returns all BaseBlock instances that are attributes of this class.
        set_target_entity(target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None: (Inherited from BaseBlock)
            Set the target entity for all the values contained in this Block instance.
        clear_target_entity() -> None: (Inherited from BaseBlock)
            Clear the target entity for all the values contained in this Block instance.
        set_context(context: Dict[str, Any]) -> None: (Inherited from BaseBlock)
            Set the context for all the values contained in this Block instance.
        clear_context() -> None: (Inherited from BaseBlock)
            Clear the context for all the values contained in this Block instance.
        clear() -> None: (Inherited from BaseBlock)
            Clear the source, target, and context for all the values contained in this Block instance.

    Computed Fields:
        modifier (int): The calculated ability modifier, combining the normalized ability score and any bonuses.
        values_dict_uuid_name (Dict[UUID, str]): A dictionary mapping value UUIDs to their names. (Inherited from BaseBlock)
        values_dict_name_uuid (Dict[str, UUID]): A dictionary mapping value names to their UUIDs. (Inherited from BaseBlock)
        blocks_dict_uuid_name (Dict[UUID, str]): A dictionary mapping block UUIDs to their names. (Inherited from BaseBlock)
        blocks_dict_name_uuid (Dict[str, UUID]): A dictionary mapping block names to their UUIDs. (Inherited from BaseBlock)
    """

    name: abilities = Field(default="strength", description="The name of the ability (Strength, Dexterity, Constitution, Intelligence, Wisdom, or Charisma)")
    ability_score: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=10, value_name="Ability Score",score_normalizer=ability_score_normalizer), description="The base ability score, typically ranging from 3 to 20 for most characters")
    modifier_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Modifier Bonus"), description="Any additional bonus to the ability modifier, separate from the base score")
    @classmethod
    def get(cls, uuid: UUID) -> Optional['Ability']:
        """
        Retrieve an Ability instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the Ability instance to retrieve.

        Returns:
            Optional[Ability]: The Ability instance if found, None otherwise.

        Raises:
            ValueError: If the value with the given UUID is not an AbilityScore.
        """
        obj= super().get(uuid)
        if obj is not None and not isinstance(obj, Ability):
            raise ValueError(f"Value with UUID {uuid} is not an AbilityScore, but {type(obj)}")
        return obj
    @computed_field
    @property
    def modifier(self) -> int:
        """
        Combines the ability score, normalized with: (score - 10) // 2, and the modifier bonus.

        Returns:
            int: The calculated ability modifier.
        """
        return self.ability_score.normalized_score + self.modifier_bonus.score
    
    
class AbilityScores(BaseBlock):
    """
    Represents the set of six ability scores for an entity in the D&D 5e game system.

    This class extends BaseBlock to represent all six standard ability scores used in D&D 5e.

    Attributes:
        name (str): The name of this ability scores block. Defaults to "AbilityScores".
        strength (Ability): Strength measures bodily power, athletic training, and the extent to which you can exert raw physical force.
        dexterity (Ability): Dexterity measures agility, reflexes, and balance.
        constitution (Ability): Constitution measures health, stamina, and vital force.
        intelligence (Ability): Intelligence measures mental acuity, accuracy of recall, and the ability to reason.
        wisdom (Ability): Wisdom reflects how attuned you are to the world around you and represents perceptiveness and intuition.
        charisma (Ability): Charisma measures your ability to interact effectively with others. It includes such factors as confidence and eloquence.
        uuid (UUID): Unique identifier for the block. (Inherited from BaseBlock)
        source_entity_uuid (UUID): UUID of the entity that is the source of this block. (Inherited from BaseBlock)
        source_entity_name (Optional[str]): Name of the entity that is the source of this block. (Inherited from BaseBlock)
        target_entity_uuid (Optional[UUID]): UUID of the entity that this block targets, if any. (Inherited from BaseBlock)
        target_entity_name (Optional[str]): Name of the entity that this block targets, if any. (Inherited from BaseBlock)
        context (Optional[Dict[str, Any]]): Additional context information for this block. (Inherited from BaseBlock)

    Inherits all attributes and methods from BaseBlock.

    Additional Methods:
        get_modifier(ability_uuid: UUID) -> int:
            Get the modifier for a specific ability by its UUID.
        get_modifier_from_uuid(ability_uuid: UUID) -> int:
            Get the modifier for a specific ability by its UUID.
        get_modifier_from_name(ability_name: abilities) -> int:
            Get the modifier for a specific ability by its name.
        get_values() -> List[ModifiableValue]: (Inherited from BaseBlock)
            Searches through attributes and returns all ModifiableValue instances that are attributes of this class.
        get_blocks() -> List['BaseBlock']: (Inherited from BaseBlock)
            Searches through attributes and returns all BaseBlock instances that are attributes of this class.
        set_target_entity(target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None: (Inherited from BaseBlock)
            Set the target entity for all the values contained in this Block instance.
        clear_target_entity() -> None: (Inherited from BaseBlock)
            Clear the target entity for all the values contained in this Block instance.
        set_context(context: Dict[str, Any]) -> None: (Inherited from BaseBlock)
            Set the context for all the values contained in this Block instance.
        clear_context() -> None: (Inherited from BaseBlock)
            Clear the context for all the values contained in this Block instance.
        clear() -> None: (Inherited from BaseBlock)
            Clear the source, target, and context for all the values contained in this Block instance.

    Computed Fields:
        abilities_list (List[Ability]): A list of all Ability instances in this AbilityScores block.
        ability_blocks_uuid_by_name (Dict[abilities, UUID]): A dictionary mapping ability names to their UUIDs.
        ability_blocks_names_by_uuid (Dict[UUID, abilities]): A dictionary mapping ability UUIDs to their names.
        values_dict_uuid_name (Dict[UUID, str]): A dictionary mapping value UUIDs to their names. (Inherited from BaseBlock)
        values_dict_name_uuid (Dict[str, UUID]): A dictionary mapping value names to their UUIDs. (Inherited from BaseBlock)
        blocks_dict_uuid_name (Dict[UUID, str]): A dictionary mapping block UUIDs to their names. (Inherited from BaseBlock)
        blocks_dict_name_uuid (Dict[str, UUID]): A dictionary mapping block names to their UUIDs. (Inherited from BaseBlock)
    """

    name: str = Field(default="AbilityScores", description="The set of six core ability scores in D&D 5e")
    strength: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="strength"), description="Strength measures bodily power, athletic training, and the extent to which you can exert raw physical force")
    dexterity: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="dexterity"), description="Dexterity measures agility, reflexes, and balance")
    constitution: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="constitution"), description="Constitution measures health, stamina, and vital force")
    intelligence: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="intelligence"), description="Intelligence measures mental acuity, accuracy of recall, and the ability to reason")
    wisdom: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="wisdom"), description="Wisdom reflects how attuned you are to the world around you and represents perceptiveness and intuition")
    charisma: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="charisma"), description="Charisma measures your ability to interact effectively with others. It includes such factors as confidence and eloquence")

    @computed_field
    @property
    def abilities_list(self) -> List[Ability]:
        """
        A list of all Ability instances in this AbilityScores block.

        Returns:
            List[Ability]: A list of all Ability instances in this AbilityScores block.
        """
        return [self.strength, self.dexterity, self.constitution, self.intelligence, self.wisdom, self.charisma]
    @computed_field
    @property
    def ability_blocks_uuid_by_name(self) -> Dict[abilities, UUID]:
        """
        A dictionary mapping ability names to their UUIDs.

        Returns:
            Dict[abilities, UUID]: A dictionary mapping ability names to their UUIDs.
        """
        return {
            'strength': self.strength.uuid,
            'dexterity': self.dexterity.uuid,
            'constitution': self.constitution.uuid,
            'intelligence': self.intelligence.uuid,
            'wisdom': self.wisdom.uuid,
            'charisma': self.charisma.uuid
        }
    @computed_field
    @property
    def ability_blocks_names_by_uuid(self) -> Dict[UUID, abilities]:
        """
        A dictionary mapping ability UUIDs to their names.

        Returns:
            Dict[UUID, abilities]: A dictionary mapping ability UUIDs to their names.
        """
        return{ability.uuid:ability.name for ability in self.abilities_list}
    
    def get_modifier(self, ability_uuid: UUID) -> int:
        """
        Get the modifier for a specific ability by its UUID.

        Args:
            ability_uuid (UUID): The UUID of the ability.

        Returns:
            int: The modifier for the specified ability.
        """
        ability_object: Ability = getattr(self, self.ability_blocks_names_by_uuid[ability_uuid])
        return ability_object.modifier

    def get_modifier_from_uuid(self, ability_uuid: UUID) -> int:
        """
        Get the modifier for a specific ability by its UUID.

        Args:
            ability_uuid (UUID): The UUID of the ability.

        Returns:
            int: The modifier for the specified ability.

        Raises:
            ValueError: If no Ability is found with the given UUID.
        """
        ability_object = self.get_block_from_uuid(ability_uuid)
        if ability_object and isinstance(ability_object, Ability):
            return ability_object.modifier
        raise ValueError(f"No Ability found with UUID {ability_uuid}")

    def get_modifier_from_name(self, ability_name: abilities) -> int:
        """
        Get the modifier for a specific ability by its name.

        Args:
            ability_name (abilities): The name of the ability.

        Returns:
            int: The modifier for the specified ability.

        Raises:
            ValueError: If no Ability is found with the given name.
        """
        ability_object = self.get_block_from_name(ability_name)
        if ability_object and isinstance(ability_object, Ability):
            return ability_object.modifier
        raise ValueError(f"No Ability found with name {ability_name}")

skills = Literal['acrobatics', 'animal_handling', 'arcana', 'athletics', 'deception', 'history', 'insight', 'intimidation', 'investigation', 'medicine', 'nature', 'perception', 'performance', 'persuasion', 'religion', 'sleight_of_hand', 'stealth', 'survival']

ABILITY_TO_SKILLS: Dict[abilities, List[skills]] = {
    'strength': ['athletics'],
    'dexterity': ['acrobatics', 'sleight_of_hand', 'stealth'],
    'constitution': [],
    'intelligence': ['arcana', 'history', 'investigation', 'nature', 'religion'],
    'wisdom': ['animal_handling', 'insight', 'medicine', 'perception', 'survival'],
    'charisma': ['deception', 'intimidation', 'performance', 'persuasion']
}

class Skill(BaseBlock):
    """
    Represents a skill in the D&D 5e game system.

    This class extends BaseBlock to represent a specific skill, including its proficiency status and any bonuses.

    Attributes:
        name (skills): The name of the skill.
        skill_bonus (ModifiableValue): Any additional bonus applied to the skill checks.
        expertise (bool): Whether the character has expertise in this skill, which doubles the proficiency bonus.
        proficiency (bool): Whether the character is proficient in this skill, adding their proficiency bonus to checks.
        uuid (UUID): Unique identifier for the block. (Inherited from BaseBlock)
        source_entity_uuid (UUID): UUID of the entity that is the source of this block. (Inherited from BaseBlock)
        source_entity_name (Optional[str]): Name of the entity that is the source of this block. (Inherited from BaseBlock)
        target_entity_uuid (Optional[UUID]): UUID of the entity that this block targets, if any. (Inherited from BaseBlock)
        target_entity_name (Optional[str]): Name of the entity that this block targets, if any. (Inherited from BaseBlock)
        context (Optional[Dict[str, Any]]): Additional context information for this block. (Inherited from BaseBlock)

    Inherits all attributes and methods from BaseBlock.

    Additional Methods:
        set_proficiency(proficiency: bool) -> None:
            Set the proficiency status for this skill.
        set_expertise(expertise: bool) -> None:
            Set the expertise status for this skill.
        get_score(proficiency_bonus: int) -> int:
            Calculate the total score for this skill.
        get_values() -> List[ModifiableValue]: (Inherited from BaseBlock)
            Searches through attributes and returns all ModifiableValue instances that are attributes of this class.
        get_blocks() -> List['BaseBlock']: (Inherited from BaseBlock)
            Searches through attributes and returns all BaseBlock instances that are attributes of this class.
        set_target_entity(target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None: (Inherited from BaseBlock)
            Set the target entity for all the values contained in this Block instance.
        clear_target_entity() -> None: (Inherited from BaseBlock)
            Clear the target entity for all the values contained in this Block instance.
        set_context(context: Dict[str, Any]) -> None: (Inherited from BaseBlock)
            Set the context for all the values contained in this Block instance.
        clear_context() -> None: (Inherited from BaseBlock)
            Clear the context for all the values contained in this Block instance.
        clear() -> None: (Inherited from BaseBlock)
            Clear the source, target, and context for all the values contained in this Block instance.

    Class Methods:
        create(cls, source_entity_uuid: UUID, name: skills, source_entity_name: Optional[str] = None, 
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               expertise: bool = False, proficiency: bool = False) -> 'Skill':
            Create a new Skill instance with the given parameters.

    Computed Fields:
        values_dict_uuid_name (Dict[UUID, str]): A dictionary mapping value UUIDs to their names. (Inherited from BaseBlock)
        values_dict_name_uuid (Dict[str, UUID]): A dictionary mapping value names to their UUIDs. (Inherited from BaseBlock)
        blocks_dict_uuid_name (Dict[UUID, str]): A dictionary mapping block UUIDs to their names. (Inherited from BaseBlock)
        blocks_dict_name_uuid (Dict[str, UUID]): A dictionary mapping block names to their UUIDs. (Inherited from BaseBlock)
    """

    name: skills = Field(default="acrobatics", description="The name of the skill in D&D 5e")
    skill_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Skill Bonus"), description="Any additional bonus applied to skill checks, beyond ability modifier and proficiency")
    expertise: bool = Field(default=False, description="If true, the character has expertise in this skill, doubling their proficiency bonus")
    proficiency: bool = Field(default=False, description="If true, the character is proficient in this skill, adding their proficiency bonus to checks")

    def set_proficiency(self, proficiency: bool) -> None:
        """
        Set the proficiency status for this skill.

        Args:
            proficiency (bool): Whether the character is proficient in this skill.
        """
        self.proficiency = proficiency
    def set_expertise(self, expertise: bool) -> None:
        """
        Set the expertise status for this skill.

        Args:
            expertise (bool): Whether the character has expertise in this skill.
        """
        self.expertise = expertise
        if not self.proficiency:
            self.proficiency = True
    def _get_proficiency_converter(self):
        """
        Get a function that calculates the proficiency bonus based on the character's expertise and proficiency.

        Returns:
            Callable[[int], int]: A function that takes the proficiency bonus as an argument and returns the adjusted bonus.
        """
        def proficient(proficiency_bonus:int) -> int:
            return proficiency_bonus
        def not_proficient(proficiency_bonus:int) -> int:
            return 0
        def expert(proficiency_bonus:int) -> int:
            return 2*proficiency_bonus
        if self.proficiency:
            if self.expertise:
                return expert
            return proficient
        else:
            return not_proficient
    def get_score(self,profiency_bonus:int) -> int:
        """
        Calculate the total score for this skill.

        Args:
            profiency_bonus (int): The proficiency bonus for the character.

        Returns:
            int: The total score for this skill.
        """
        return self._get_proficiency_converter()(profiency_bonus)+self.skill_bonus.score
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, name: skills, source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               expertise:bool=False,proficiency:bool=False) -> 'Skill':
        """
        Create a new Skill instance with the given parameters.

        Args:
            source_entity_uuid (UUID): The UUID of the source entity.
            name (skills): The name of the skill.
            source_entity_name (Optional[str]): The name of the source entity.
            target_entity_uuid (Optional[UUID]): The UUID of the target entity.
            target_entity_name (Optional[str]): The name of the target entity.
            expertise (bool): Whether the character has expertise in this skill.
            proficiency (bool): Whether the character is proficient in this skill.

        Returns:
            Skill: The newly created Skill instance.
        """
        if expertise and not proficiency:
            proficiency = True
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                   target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                   expertise=expertise, proficiency=proficiency)
        

class SkillSet(BaseBlock):
    """
    Represents the complete set of skills for an entity in the D&D 5e game system.

    This class extends BaseBlock to represent all 18 standard skills used in D&D 5e.

    Attributes:
        name (str): The name of this skill set block. Defaults to "SkillSet".
        acrobatics (Skill): Your Dexterity (Acrobatics) check covers your attempt to stay on your feet in a tricky situation.
        animal_handling (Skill): When there is any question whether you can calm down a domesticated animal, keep a mount from getting spooked, or intuit an animal's intentions, the GM might call for a Wisdom (Animal Handling) check.
        arcana (Skill): Your Intelligence (Arcana) check measures your ability to recall lore about spells, magic items, eldritch symbols, magical traditions, the planes of existence, and the inhabitants of those planes.
        athletics (Skill): Your Strength (Athletics) check covers difficult situations you encounter while climbing, jumping, or swimming.
        deception (Skill): Your Charisma (Deception) check determines whether you can convincingly hide the truth, either verbally or through your actions.
        history (Skill): Your Intelligence (History) check measures your ability to recall lore about historical events, legendary people, ancient kingdoms, past disputes, recent wars, and lost civilizations.
        insight (Skill): Your Wisdom (Insight) check decides whether you can determine the true intentions of a creature, such as when searching out a lie or predicting someone's next move.
        intimidation (Skill): When you attempt to influence someone through overt threats, hostile actions, and physical violence, the GM might ask you to make a Charisma (Intimidation) check.
        investigation (Skill): When you look around for clues and make deductions based on those clues, you make an Intelligence (Investigation) check.
        medicine (Skill): A Wisdom (Medicine) check lets you try to stabilize a dying companion or diagnose an illness.
        nature (Skill): Your Intelligence (Nature) check measures your ability to recall lore about terrain, plants and animals, the weather, and natural cycles.
        perception (Skill): Your Wisdom (Perception) check lets you spot, hear, or otherwise detect the presence of something. It measures your general awareness of your surroundings and the keenness of your senses.
        performance (Skill): Your Charisma (Performance) check determines how well you can delight an audience with music, dance, acting, storytelling, or some other form of entertainment.
        persuasion (Skill): When you attempt to influence someone or a group of people with tact, social graces, or good nature, the GM might ask you to make a Charisma (Persuasion) check.
        religion (Skill): Your Intelligence (Religion) check measures your ability to recall lore about deities, rites and prayers, religious hierarchies, holy symbols, and the practices of secret cults.
        sleight_of_hand (Skill): Whenever you attempt an act of legerdemain or manual trickery, such as planting something on someone else or concealing an object on your person, make a Dexterity (Sleight of Hand) check.
        stealth (Skill): Make a Dexterity (Stealth) check when you attempt to conceal yourself from enemies, slink past guards, slip away without being noticed, or sneak up on someone without being seen or heard.
        survival (Skill): The GM might ask you to make a Wisdom (Survival) check to follow tracks, hunt wild game, guide your group through frozen wastelands, identify signs that owlbears live nearby, predict the weather, or avoid quicksand and other natural hazards.
        uuid (UUID): Unique identifier for the block. (Inherited from BaseBlock)
        source_entity_uuid (UUID): UUID of the entity that is the source of this block. (Inherited from BaseBlock)
        source_entity_name (Optional[str]): Name of the entity that is the source of this block. (Inherited from BaseBlock)
        target_entity_uuid (Optional[UUID]): UUID of the entity that this block targets, if any. (Inherited from BaseBlock)
        target_entity_name (Optional[str]): Name of the entity that this block targets, if any. (Inherited from BaseBlock)
        context (Optional[Dict[str, Any]]): Additional context information for this block. (Inherited from BaseBlock)

    Inherits all attributes and methods from BaseBlock.

    Methods:
        get_values() -> List[ModifiableValue]: (Inherited from BaseBlock)
            Searches through attributes and returns all ModifiableValue instances that are attributes of this class.
        get_blocks() -> List['BaseBlock']: (Inherited from BaseBlock)
            Searches through attributes and returns all BaseBlock instances that are attributes of this class.
        set_target_entity(target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None: (Inherited from BaseBlock)
            Set the target entity for all the values contained in this Block instance.
        clear_target_entity() -> None: (Inherited from BaseBlock)
            Clear the target entity for all the values contained in this Block instance.
        set_context(context: Dict[str, Any]) -> None: (Inherited from BaseBlock)
            Set the context for all the values contained in this Block instance.
        clear_context() -> None: (Inherited from BaseBlock)
            Clear the context for all the values contained in this Block instance.
        clear() -> None: (Inherited from BaseBlock)
            Clear the source, target, and context for all the values contained in this Block instance.

    Computed Fields:
        proficiencies (List[Skill]): A list of all skills in which the entity is proficient.
        expertise (List[Skill]): A list of all skills in which the entity has expertise.
        values_dict_uuid_name (Dict[UUID, str]): A dictionary mapping value UUIDs to their names. (Inherited from BaseBlock)
        values_dict_name_uuid (Dict[str, UUID]): A dictionary mapping value names to their UUIDs. (Inherited from BaseBlock)
        blocks_dict_uuid_name (Dict[UUID, str]): A dictionary mapping block UUIDs to their names. (Inherited from BaseBlock)
        blocks_dict_name_uuid (Dict[str, UUID]): A dictionary mapping block names to their UUIDs. (Inherited from BaseBlock)
    """

    name: str = Field(default="SkillSet", description="The complete set of 18 skills in D&D 5e")
    acrobatics: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="acrobatics"), description="Dexterity (Acrobatics): Staying on your feet in tricky situations, such as balancing on a tightrope or staying upright on a rocking ship's deck")
    animal_handling: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="animal_handling"), description="Wisdom (Animal Handling): Calming domesticated animals, keeping mounts from getting spooked, or intuiting an animal's intentions")
    arcana: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="arcana"), description="Intelligence (Arcana): Recalling lore about spells, magic items, eldritch symbols, magical traditions, planes of existence, and planar inhabitants")
    athletics: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="athletics"), description="Strength (Athletics): Climbing, jumping, swimming, and other difficult physical activities")
    deception: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="deception"), description="Charisma (Deception): Convincingly hiding the truth through words or actions")
    history: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="history"), description="Intelligence (History): Recalling lore about historical events, legendary people, ancient kingdoms, past disputes, recent wars, and lost civilizations")
    insight: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="insight"), description="Wisdom (Insight): Determining the true intentions of others, detecting lies, and predicting someone's next move")
    intimidation: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="intimidation"), description="Charisma (Intimidation): Influencing others through overt threats, hostile actions, and physical violence")
    investigation: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="investigation"), description="Intelligence (Investigation): Searching for clues and making deductions based on those clues")
    medicine: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="medicine"), description="Wisdom (Medicine): Stabilizing dying companions or diagnosing illnesses")
    nature: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="nature"), description="Intelligence (Nature): Recalling lore about terrain, plants and animals, the weather, and natural cycles")
    perception: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="perception"), description="Wisdom (Perception): Spotting, hearing, or detecting the presence of something, measuring general awareness and sensory acuity")
    performance: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="performance"), description="Charisma (Performance): Delighting an audience with music, dance, acting, storytelling, or other forms of entertainment")
    persuasion: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="persuasion"), description="Charisma (Persuasion): Influencing others through tact, social graces, or good nature")
    religion: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="religion"), description="Intelligence (Religion): Recalling lore about deities, rites, prayers, religious hierarchies, holy symbols, and the practices of secret cults")
    sleight_of_hand: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="sleight_of_hand"), description="Dexterity (Sleight of Hand): Performing acts of legerdemain, manual trickery, or subtle manipulations")
    stealth: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="stealth"), description="Dexterity (Stealth): Concealing yourself, moving silently, and avoiding detection")
    survival: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="survival"), description="Wisdom (Survival): Following tracks, hunting wild game, guiding through wilderness, identifying natural hazards, and predicting weather")

    @computed_field
    @property
    def proficiencies(self) -> List[Skill]:
        """
        A list of all skills in which the entity is proficient.

        Returns:
            List[Skill]: A list of all skills in which the entity is proficient.
        """
        blocks = self.get_blocks()
        return [skill for skill in blocks if isinstance(skill, Skill) and skill.proficiency]

    @computed_field
    @property
    def expertise(self) -> List[Skill]:
        blocks = self.get_blocks()
        return [skill for skill in blocks if isinstance(skill, Skill) and skill.expertise]
    
saving_throw_name_to_ability = {
    "strength_saving_throw": "strength",
    "dexterity_saving_throw": "dexterity",
    "constitution_saving_throw": "constitution",
    "intelligence_saving_throw": "intelligence",
    "wisdom_saving_throw": "wisdom",
    "charisma_saving_throw": "charisma"
}


class SavingThrow(BaseBlock):
    """
    Represents a saving throw in the D&D 5e game system.

    This class extends BaseBlock to represent a specific saving throw, including its proficiency status and any bonuses.

    Attributes:
        name (saving_throws): The name of the saving throw, corresponding to an ability score.
        proficiency (bool): Whether the entity is proficient in this saving throw, adding their proficiency bonus.
        bonus (ModifiableValue): Any additional bonus applied to the saving throw, beyond ability modifier and proficiency.
        uuid (UUID): Unique identifier for the block. (Inherited from BaseBlock)
        source_entity_uuid (UUID): UUID of the entity that is the source of this block. (Inherited from BaseBlock)
        source_entity_name (Optional[str]): Name of the entity that is the source of this block. (Inherited from BaseBlock)
        target_entity_uuid (Optional[UUID]): UUID of the entity that this block targets, if any. (Inherited from BaseBlock)
        target_entity_name (Optional[str]): Name of the entity that this block targets, if any. (Inherited from BaseBlock)
        context (Optional[Dict[str, Any]]): Additional context information for this block. (Inherited from BaseBlock)

    Inherits all attributes and methods from BaseBlock.

    Additional Methods:
        get_bonus(proficiency_bonus: int) -> int:
            Calculate the total bonus for this saving throw.
        get_values() -> List[ModifiableValue]: (Inherited from BaseBlock)
            Searches through attributes and returns all ModifiableValue instances that are attributes of this class.
        get_blocks() -> List['BaseBlock']: (Inherited from BaseBlock)
            Searches through attributes and returns all BaseBlock instances that are attributes of this class.
        set_target_entity(target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None: (Inherited from BaseBlock)
            Set the target entity for all the values contained in this Block instance.
        clear_target_entity() -> None: (Inherited from BaseBlock)
            Clear the target entity for all the values contained in this Block instance.
        set_context(context: Dict[str, Any]) -> None: (Inherited from BaseBlock)
            Set the context for all the values contained in this Block instance.
        clear_context() -> None: (Inherited from BaseBlock)
            Clear the context for all the values contained in this Block instance.
        clear() -> None: (Inherited from BaseBlock)
            Clear the source, target, and context for all the values contained in this Block instance.

    Class Methods:
        create(cls, source_entity_uuid: UUID, name: saving_throws, source_entity_name: Optional[str] = None, 
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               proficiency: bool = False) -> 'SavingThrow':
            Create a new SavingThrow instance with the given parameters.

    Computed Fields:
        values_dict_uuid_name (Dict[UUID, str]): A dictionary mapping value UUIDs to their names. (Inherited from BaseBlock)
        values_dict_name_uuid (Dict[str, UUID]): A dictionary mapping value names to their UUIDs. (Inherited from BaseBlock)
        blocks_dict_uuid_name (Dict[UUID, str]): A dictionary mapping block UUIDs to their names. (Inherited from BaseBlock)
        blocks_dict_name_uuid (Dict[str, UUID]): A dictionary mapping block names to their UUIDs. (Inherited from BaseBlock)
    """

    name: saving_throws = Field(default="strength_saving_throw", description="The name of the saving throw, corresponding to an ability score in D&D 5e")
    proficiency: bool = Field(default=False, description="If true, the character is proficient in this saving throw, adding their proficiency bonus")
    bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Saving Throw Bonus"), description="Any additional bonus applied to the saving throw, beyond ability modifier and proficiency")

    def get_bonus(self, proficiency_bonus: int) -> int:
        """
        Calculate the total bonus for this saving throw.

        Args:
            proficiency_bonus (int): The proficiency bonus of the character.

        Returns:
            int: The total bonus for the saving throw, including proficiency if applicable.
        """
        if self.proficiency:
            return self.bonus.score + proficiency_bonus
        else:
            return self.bonus.score

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: saving_throws, source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               proficiency:bool=False) -> 'SavingThrow':
        """
        Create a new SavingThrow instance with the given parameters.

        Args:
            source_entity_uuid (UUID): The UUID of the source entity.
            name (saving_throws): The name of the saving throw.
            source_entity_name (Optional[str], optional): The name of the source entity. Defaults to None.
            target_entity_uuid (Optional[UUID], optional): The UUID of the target entity. Defaults to None.
            target_entity_name (Optional[str], optional): The name of the target entity. Defaults to None.
            proficiency (bool, optional): Whether the entity is proficient in this saving throw. Defaults to False.

        Returns:
            SavingThrow: A new instance of the SavingThrow class.
        """
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                   target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                   proficiency=proficiency)

class SavingThrowSet(BaseBlock):
    """
    Represents the complete set of saving throws for an entity in the D&D 5e game system.

    This class extends BaseBlock to represent all six standard saving throws used in D&D 5e.

    Attributes:
        name (str): The name of this saving throw set block. Defaults to "SavingThrowSet".
        strength_saving_throw (SavingThrow): Used to resist physical force and avoid being moved against your will.
        dexterity_saving_throw (SavingThrow): Used to dodge area effects, such as the breath of a dragon or a fireball spell.
        constitution_saving_throw (SavingThrow): Used to resist poison, disease, and other bodily ailments.
        intelligence_saving_throw (SavingThrow): Used to resist mental attacks and illusions.
        wisdom_saving_throw (SavingThrow): Used to resist mental influence or charm effects.
        charisma_saving_throw (SavingThrow): Used to resist effects that would subsume your personality or possess you.
        uuid (UUID): Unique identifier for the block. (Inherited from BaseBlock)
        source_entity_uuid (UUID): UUID of the entity that is the source of this block. (Inherited from BaseBlock)
        source_entity_name (Optional[str]): Name of the entity that is the source of this block. (Inherited from BaseBlock)
        target_entity_uuid (Optional[UUID]): UUID of the entity that this block targets, if any. (Inherited from BaseBlock)
        target_entity_name (Optional[str]): Name of the entity that this block targets, if any. (Inherited from BaseBlock)
        context (Optional[Dict[str, Any]]): Additional context information for this block. (Inherited from BaseBlock)

    Inherits all attributes and methods from BaseBlock.

    Methods:
        get_values() -> List[ModifiableValue]: (Inherited from BaseBlock)
            Searches through attributes and returns all ModifiableValue instances that are attributes of this class.
        get_blocks() -> List['BaseBlock']: (Inherited from BaseBlock)
            Searches through attributes and returns all BaseBlock instances that are attributes of this class.
        set_target_entity(target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None: (Inherited from BaseBlock)
            Set the target entity for all the values contained in this Block instance.
        clear_target_entity() -> None: (Inherited from BaseBlock)
            Clear the target entity for all the values contained in this Block instance.
        set_context(context: Dict[str, Any]) -> None: (Inherited from BaseBlock)
            Set the context for all the values contained in this Block instance.
        clear_context() -> None: (Inherited from BaseBlock)
            Clear the context for all the values contained in this Block instance.
        clear() -> None: (Inherited from BaseBlock)
            Clear the source, target, and context for all the values contained in this Block instance.

    Computed Fields:
        proficiencies (List[SavingThrow]): A list of all saving throws in which the entity is proficient.
        values_dict_uuid_name (Dict[UUID, str]): A dictionary mapping value UUIDs to their names. (Inherited from BaseBlock)
        values_dict_name_uuid (Dict[str, UUID]): A dictionary mapping value names to their UUIDs. (Inherited from BaseBlock)
        blocks_dict_uuid_name (Dict[UUID, str]): A dictionary mapping block UUIDs to their names. (Inherited from BaseBlock)
        blocks_dict_name_uuid (Dict[str, UUID]): A dictionary mapping block names to their UUIDs. (Inherited from BaseBlock)
    """

    name: str = Field(default="SavingThrowSet", description="The complete set of six saving throws in D&D 5e")
    strength_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="strength_saving_throw"), description="Strength saving throw: Used to resist physical force and avoid being moved against your will")
    dexterity_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="dexterity_saving_throw"), description="Dexterity saving throw: Used to dodge area effects, such as the breath of a dragon or a fireball spell")
    constitution_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="constitution_saving_throw"), description="Constitution saving throw: Used to resist poison, disease, and other bodily ailments")
    intelligence_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="intelligence_saving_throw"), description="Intelligence saving throw: Used to resist mental attacks and illusions")
    wisdom_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="wisdom_saving_throw"), description="Wisdom saving throw: Used to resist mental influence or charm effects")
    charisma_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="charisma_saving_throw"), description="Charisma saving throw: Used to resist effects that would subsume your personality or possess you")
    
    @computed_field
    @property
    def proficiencies(self) -> List[SavingThrow]:
        """
        Get a list of all saving throws in which the entity is proficient.

        Returns:
            List[SavingThrow]: A list of SavingThrow instances where proficiency is True.
        """
        blocks = self.get_blocks()
        return [saving_throw for saving_throw in blocks if isinstance(saving_throw, SavingThrow) and saving_throw.proficiency]
    
    
class HitDice(BaseBlock):
    """
    Represents the hit dice of an entity in the game system.

    This class extends BaseBlock to represent the hit dice used for determining hit points and healing.

    Attributes:
        name (str): The name of this hit dice block. Defaults to "HitDice".
        hit_dice_value (ModifiableValue): The value of each hit die (e.g., d6, d8, d10, etc.).
        hit_dice_count (ModifiableValue): The number of hit dice available.
        mode (Literal["average", "maximums", "roll"]): The mode for calculating hit points.
        uuid (UUID): Unique identifier for the block. (Inherited from BaseBlock)
        source_entity_uuid (UUID): UUID of the entity that is the source of this block. (Inherited from BaseBlock)
        source_entity_name (Optional[str]): Name of the entity that is the source of this block. (Inherited from BaseBlock)
        target_entity_uuid (Optional[UUID]): UUID of the entity that this block targets, if any. (Inherited from BaseBlock)
        target_entity_name (Optional[str]): Name of the entity that this block targets, if any. (Inherited from BaseBlock)
        context (Optional[Dict[str, Any]]): Additional context information for this block. (Inherited from BaseBlock)

    Inherits all attributes and methods from BaseBlock.

    Additional Methods:
        get_values() -> List[ModifiableValue]: (Inherited from BaseBlock)
            Searches through attributes and returns all ModifiableValue instances that are attributes of this class.
        get_blocks() -> List['BaseBlock']: (Inherited from BaseBlock)
            Searches through attributes and returns all BaseBlock instances that are attributes of this class.
        set_target_entity(target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None: (Inherited from BaseBlock)
            Set the target entity for all the values contained in this Block instance.
        clear_target_entity() -> None: (Inherited from BaseBlock)
            Clear the target entity for all the values contained in this Block instance.
        set_context(context: Dict[str, Any]) -> None: (Inherited from BaseBlock)
            Set the context for all the values contained in this Block instance.
        clear_context() -> None: (Inherited from BaseBlock)
            Clear the context for all the values contained in this Block instance.
        clear() -> None: (Inherited from BaseBlock)
            Clear the source, target, and context for all the values contained in this Block instance.

    Class Methods:
        create(cls, source_entity_uuid: UUID, name: str = "HitDice", source_entity_name: Optional[str] = None, 
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               hit_dice_value: Literal[4,6,8,10,12] = 6, hit_dice_count: int = 1, 
               mode: Literal["average", "maximums","roll"] = "average") -> 'HitDice':
            Create a new HitDice instance with the given parameters.

    Computed Fields:
        hit_points (int): The calculated hit points based on the hit dice and mode.
        values_dict_uuid_name (Dict[UUID, str]): A dictionary mapping value UUIDs to their names. (Inherited from BaseBlock)
        values_dict_name_uuid (Dict[str, UUID]): A dictionary mapping value names to their UUIDs. (Inherited from BaseBlock)
        blocks_dict_uuid_name (Dict[UUID, str]): A dictionary mapping block UUIDs to their names. (Inherited from BaseBlock)
        blocks_dict_name_uuid (Dict[str, UUID]): A dictionary mapping block names to their UUIDs. (Inherited from BaseBlock)

    Validators:
        check_hit_dice_value: Ensures that the hit dice value is one of the allowed values.
        check_hit_dice_count: Ensures that the hit dice count is greater than 0.
    """

    name: str = Field(default="HitDice")
    hit_dice_value: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=6, value_name="Hit Dice Value"))
    hit_dice_count: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=1, value_name="Hit Dice Count"))
    mode: Literal["average", "maximums","roll"] = Field(default="average")

    @computed_field
    @cached_property
    def hit_points(self) -> int:
        """
        Calculate the hit points based on the hit dice and mode.

        Returns:
            int: The calculated hit points.

        Raises:
            ValueError: If an invalid mode is specified.
        """
        first_level_hit_points = self.hit_dice_value.score
        remaining_dice_count = self.hit_dice_count.score - 1
        if self.mode == "average":
            return first_level_hit_points + remaining_dice_count * ((self.hit_dice_value.score // 2)+1)
        elif self.mode == "maximums":
            return first_level_hit_points + remaining_dice_count * self.hit_dice_value.score
        elif self.mode == "roll":
            return sum(randint(1, self.hit_dice_value.score) for _ in range(self.hit_dice_count.score))
        else:
            raise ValueError(f"Invalid mode: {self.mode}")
        
    @field_validator("hit_dice_value")
    def check_hit_dice_value(cls, v: ModifiableValue) -> ModifiableValue:
        """
        Validate that the hit dice value is one of the allowed values.

        Args:
            v (ModifiableValue): The hit dice value to validate.

        Returns:
            ModifiableValue: The validated hit dice value.

        Raises:
            ValueError: If the hit dice value is not one of the allowed values.
        """
        allowed_dice = [4,6,8,10,12]
        if v.score not in allowed_dice:
            raise ValueError(f"Hit dice value must be one of the following: {allowed_dice} instead of {v.score}")
        return v

    @field_validator("hit_dice_count")
    def check_hit_dice_count(cls, v: ModifiableValue) -> ModifiableValue:
        """
        Validate that the hit dice count is greater than 0.

        Args:
            v (ModifiableValue): The hit dice count to validate.

        Returns:
            ModifiableValue: The validated hit dice count.

        Raises:
            ValueError: If the hit dice count is less than 1.
        """
        if v.score < 1:
            raise ValueError(f"Hit dice count must be greater than 0 instead of {v.score}")
        return v
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "HitDice", source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               hit_dice_value: Literal[4,6,8,10,12] = 6, hit_dice_count: int = 1, mode: Literal["average", "maximums","roll"] = "average") -> 'HitDice':
        """
        Create a new HitDice instance with the given parameters.

        Args:
            source_entity_uuid (UUID): The UUID of the source entity.
            name (str, optional): The name of the hit dice block. Defaults to "HitDice".
            source_entity_name (Optional[str], optional): The name of the source entity. Defaults to None.
            target_entity_uuid (Optional[UUID], optional): The UUID of the target entity. Defaults to None.
            target_entity_name (Optional[str], optional): The name of the target entity. Defaults to None.
            hit_dice_value (Literal[4,6,8,10,12], optional): The value of each hit die. Defaults to 6.
            hit_dice_count (int, optional): The number of hit dice. Defaults to 1.
            mode (Literal["average", "maximums","roll"], optional): The mode for calculating hit points. Defaults to "average".

        Returns:
            HitDice: A new instance of the HitDice class.
        """
        modifiable_hit_dice_value = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=hit_dice_value, value_name="Hit Dice Value")
        modifiable_hit_dice_count = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=hit_dice_count, value_name="Hit Dice Count")
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                   target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                   hit_dice_value=modifiable_hit_dice_value, hit_dice_count=modifiable_hit_dice_count, mode=mode)

# damage_types = Literal["piercing", "bludgeoning", "slashing", "fire", "cold", "poison", "psychic", "radiant", "necrotic", "thunder", "acid", "lightning", "force", "thunder", "radiant", "necrotic", "psychic", "force"]
# damage_types_list = ["piercing", "bludgeoning", "slashing", "fire", "cold", "poison", "psychic", "radiant", "necrotic", "thunder", "acid", "lightning", "force", "thunder", "radiant", "necrotic", "psychic", "force"]

class Health(BaseBlock):
    """
    Represents the health status of an entity in the game system.

    This class extends BaseBlock to represent various aspects of an entity's health, including
    hit points, temporary hit points, and damage resistances.

    Attributes:
        name (str): The name of this health block. Defaults to "Health".
        hit_dices (List[HitDice]): The hit dice used for determining hit points and healing.
        max_hit_points_bonus (ModifiableValue): Any additional bonus to maximum hit points.
        temporary_hit_points (ModifiableValue): Temporary hit points that can absorb damage.
        damage_taken (int): The amount of damage the entity has taken.
        damage_reduction (ModifiableValue): Any damage reduction applied to incoming damage.
        vulnerabilities (List[damage_types]): Types of damage the entity is vulnerable to.
        resistances (List[damage_types]): Types of damage the entity is resistant to.
        immunities (List[damage_types]): Types of damage the entity is immune to.
        uuid (UUID): Unique identifier for the block. (Inherited from BaseBlock)
        source_entity_uuid (UUID): UUID of the entity that is the source of this block. (Inherited from BaseBlock)
        source_entity_name (Optional[str]): Name of the entity that is the source of this block. (Inherited from BaseBlock)
        target_entity_uuid (Optional[UUID]): UUID of the entity that this block targets, if any. (Inherited from BaseBlock)
        target_entity_name (Optional[str]): Name of the entity that this block targets, if any. (Inherited from BaseBlock)
        context (Optional[Dict[str, Any]]): Additional context information for this block. (Inherited from BaseBlock)

    Inherits all attributes and methods from BaseBlock.

    Additional Methods:
        add_damage(damage: int) -> None:
            Add damage to the entity's current damage taken.
        remove_damage(damage: int) -> None:
            Remove damage from the entity's current damage taken.
        damage_multiplier(damage_type: damage_types) -> float:
            Calculate the damage multiplier based on vulnerabilities and resistances.
        take_damage(damage: int, damage_type: damage_types, source_entity_uuid: UUID) -> None:
            Apply damage to the entity, considering resistances and temporary hit points.
        heal(heal: int) -> None:
            Heal the entity by removing damage.
        add_temporary_hit_points(temporary_hit_points: int, source_entity_uuid: UUID) -> None:
            Add temporary hit points to the entity.
        remove_temporary_hit_points(temporary_hit_points: int, source_entity_uuid: UUID) -> None:
            Remove temporary hit points from the entity.
        get_max_hit_dices_points(constitution_modifier: int) -> int:
            Calculate the maximum hit points based on hit dice and constitution modifier.
        get_total_hit_points(constitution_modifier: int) -> int:
            Calculate the total current hit points, including temporary hit points.
        add_vulnerability(vulnerability: damage_types) -> None:
            Add a damage type to the entity's vulnerabilities.
        remove_vulnerability(vulnerability: damage_types) -> None:
            Remove a damage type from the entity's vulnerabilities.
        add_resistance(resistance: damage_types) -> None:
            Add a damage type to the entity's resistances.
        remove_resistance(resistance: damage_types) -> None:
            Remove a damage type from the entity's resistances.
        add_immunity(immunity: damage_types) -> None:
            Add a damage type to the entity's immunities.
        remove_immunity(immunity: damage_types) -> None:
            Remove a damage type from the entity's immunities.
        get_values() -> List[ModifiableValue]: (Inherited from BaseBlock)
            Searches through attributes and returns all ModifiableValue instances that are attributes of this class.
        get_blocks() -> List['BaseBlock']: (Inherited from BaseBlock)
            Searches through attributes and returns all BaseBlock instances that are attributes of this class.
        set_target_entity(target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None: (Inherited from BaseBlock)
            Set the target entity for all the values contained in this Block instance.
        clear_target_entity() -> None: (Inherited from BaseBlock)
            Clear the target entity for all the values contained in this Block instance.
        set_context(context: Dict[str, Any]) -> None: (Inherited from BaseBlock)
            Set the context for all the values contained in this Block instance.
        clear_context() -> None: (Inherited from BaseBlock)
            Clear the context for all the values contained in this Block instance.
        clear() -> None: (Inherited from BaseBlock)
            Clear the source, target, and context for all the values contained in this Block instance.

    Computed Fields:
        hit_dices_total_hit_points (int): The total hit points from all hit dice.
        total_hit_dices_number (int): The total number of hit dice.
        values_dict_uuid_name (Dict[UUID, str]): A dictionary mapping value UUIDs to their names. (Inherited from BaseBlock)
        values_dict_name_uuid (Dict[str, UUID]): A dictionary mapping value names to their UUIDs. (Inherited from BaseBlock)
        blocks_dict_uuid_name (Dict[UUID, str]): A dictionary mapping block UUIDs to their names. (Inherited from BaseBlock)
        blocks_dict_name_uuid (Dict[str, UUID]): A dictionary mapping block names to their UUIDs. (Inherited from BaseBlock)
    """

    name: str = Field(default="Health")
    hit_dices: List[HitDice] = Field(default_factory=lambda: [HitDice.create(source_entity_uuid=uuid4(),name="HitDice")])
    max_hit_points_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Max Hit Points Bonus"), description="Max Hit Points Bonus, e.g. Aid spell")
    temporary_hit_points: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Temporary Hit Points"), description="Temporary Hit Points, e.g. False Life spell")
    damage_taken: int = Field(default=0,ge=0, description="The amount of damage taken")
    damage_reduction: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Damage Reduction"), description="Damage Reduction, e.g. Damage Resistance")

    def get_resistance(self,damage_type: DamageType) -> ResistanceStatus:
        return self.damage_reduction.resistance[damage_type]
    
    @computed_field
    @property
    def hit_dices_total_hit_points(self) -> int:
        """
        Calculate the total hit points from all hit dice.

        Returns:
            int: The sum of hit points from all hit dice.
        """
        return sum(hit_dice.hit_points for hit_dice in self.hit_dices)
    @computed_field
    @property
    def total_hit_dices_number(self) -> int:
        """
        Calculate the total number of hit dice.

        Returns:
            int: The sum of hit dice counts from all hit dice.
        """
        return sum(hit_dice.hit_dice_count.score for hit_dice in self.hit_dices)
    
    def add_damage(self, damage: int) -> None:
        """
        Add damage to the entity's current damage taken.

        Args:
            damage (int): The amount of damage to add.
        """
        self.damage_taken += damage

    def remove_damage(self, damage: int) -> None:
        """
        Remove damage from the entity's current damage taken.

        Args:
            damage (int): The amount of damage to remove.
        """
        self.damage_taken = max(0, self.damage_taken - damage)
    
    def damage_multiplier(self, damage_type: DamageType) -> float:
        """
        Calculate the damage multiplier based on vulnerabilities and resistances.

        Args:
            damage_type (damage_types): The type of damage being dealt.

        Returns:
            float: The damage multiplier (2.0 for vulnerabilities, 0.5 for resistances, 1.0 otherwise).
        """
        resistance = self.get_resistance(damage_type)
        if resistance == ResistanceStatus.IMMUNITY:
            return 0
        elif resistance == ResistanceStatus.RESISTANCE:
            return 0.5
        elif resistance == ResistanceStatus.VULNERABILITY:
            return 2
        else:
            return 1
    
    def take_damage(self, damage: int, damage_type: DamageType, source_entity_uuid: UUID) -> None:
        """
        Apply damage to the entity, considering resistances and temporary hit points.

        Args:
            damage (int): The amount of damage to apply.
            damage_type (damage_types): The type of damage being dealt.
            source_entity_uuid (UUID): The UUID of the entity dealing the damage.

        Raises:
            ValueError: If damage is less than 0 or if the damage type is invalid.
        """
        if damage < 0:
            raise ValueError(f"Damage must be greater than 0 instead of {damage}")
        if not isinstance(damage_type, DamageType):
            raise ValueError(f"Damage type must be one of the following: {[damage.value for damage in DamageType]} instead of {damage_type}")
        damage_after_absorption = damage - self.damage_reduction.score
        damage_after_multiplier = int(damage_after_absorption * self.damage_multiplier(damage_type))
        current_temporary_hit_points = self.temporary_hit_points.score
        if current_temporary_hit_points < 0:
            raise ValueError(f"Temporary Hit Points must be greater than 0 instead of {current_temporary_hit_points}")
        residual_damage = damage_after_multiplier - current_temporary_hit_points
        damage_to_temporaty_hp = current_temporary_hit_points if residual_damage > 0 else damage_after_multiplier
        self.remove_temporary_hit_points(damage_to_temporaty_hp, source_entity_uuid)
        if residual_damage > 0:
            self.add_damage(residual_damage)
    
    def heal(self, heal: int) -> None:
        """
        Heal the entity by removing damage.

        Args:
            heal (int): The amount of healing to apply.
        """
        self.damage_taken = max(0, self.damage_taken - heal)

    def add_temporary_hit_points(self, temporary_hit_points: int, source_entity_uuid: UUID) -> None:
        """
        Add temporary hit points to the entity.

        Args:
            temporary_hit_points (int): The amount of temporary hit points to add.
            source_entity_uuid (UUID): The UUID of the entity granting the temporary hit points.
        """
        modifier = NumericalModifier(source_entity_uuid=source_entity_uuid, target_entity_uuid=self.source_entity_uuid, name=f"Temporary Hit Points from {source_entity_uuid}", value=temporary_hit_points)
        if modifier.value > 0 and modifier.value > self.temporary_hit_points.score:
            print(f"healths source uuid: {self.source_entity_uuid}")
            print(f"modifier target uuid: {modifier.target_entity_uuid}")
            print(f"temporary hit point source uuid: {self.temporary_hit_points.source_entity_uuid}")
            print(f"tempory hitpoint static source uuid: {self.temporary_hit_points.self_static.source_entity_uuid}")
            self.temporary_hit_points.remove_all_modifiers()
            self.temporary_hit_points.self_static.add_value_modifier(modifier)
    
    def remove_temporary_hit_points(self, temporary_hit_points: int, source_entity_uuid: UUID) -> None:
        """
        Remove temporary hit points from the entity.

        Args:
            temporary_hit_points (int): The amount of temporary hit points to remove.
            source_entity_uuid (UUID): The UUID of the entity removing the temporary hit points.
        """
        modifier = NumericalModifier(source_entity_uuid=source_entity_uuid, target_entity_uuid=self.source_entity_uuid, name=f"Temporary Hit Points from {source_entity_uuid}", value=-temporary_hit_points)
        if modifier.value + self.temporary_hit_points.score <= 0:
            self.temporary_hit_points.remove_all_modifiers()
        else:
            
            self.temporary_hit_points.self_static.add_value_modifier(modifier)

    def get_max_hit_dices_points(self, constitution_modifier: int) -> int:
        """
        Calculate the maximum hit points based on hit dice and constitution modifier.

        Args:
            constitution_modifier (int): The constitution modifier of the entity.

        Returns:
            int: The maximum hit points.
        """
        return self.hit_dices_total_hit_points + constitution_modifier * self.total_hit_dices_number
    
    def get_total_hit_points(self, constitution_modifier: int) -> int:
        """
        Calculate the total current hit points, including temporary hit points.

        Args:
            constitution_modifier (int): The constitution modifier of the entity.

        Returns:
            int: The total current hit points.
        """
        return self.get_max_hit_dices_points(constitution_modifier) + self.max_hit_points_bonus.score + self.temporary_hit_points.score - self.damage_taken



