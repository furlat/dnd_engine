from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier
from typing import Literal as TypeLiteral
from enum import Enum
from random import randint
from functools import cached_property

from dnd.core.base_block import BaseBlock
from dnd.core.events import AbilityName
SavingThrowName = TypeLiteral[
    'strength_saving_throw', 'dexterity_saving_throw', 'constitution_saving_throw',
    'intelligence_saving_throw', 'wisdom_saving_throw', 'charisma_saving_throw'
]

saving_throw_name_to_ability = {
    "strength_saving_throw": "strength",
    "dexterity_saving_throw": "dexterity",
    "constitution_saving_throw": "constitution",
    "intelligence_saving_throw": "intelligence",
    "wisdom_saving_throw": "wisdom",
    "charisma_saving_throw": "charisma"
}

# Define saving throws as a proper string literal type

# Update the mapping dictionary
SAVING_THROW_TO_ABILITY: Dict[SavingThrowName, AbilityName] = {
    'strength_saving_throw': 'strength',
    'dexterity_saving_throw': 'dexterity',
    'constitution_saving_throw': 'constitution',
    'intelligence_saving_throw': 'intelligence',
    'wisdom_saving_throw': 'wisdom',
    'charisma_saving_throw': 'charisma'
}

class SavingThrowConfig(BaseModel):
    """
    Configuration for a saving throw in the D&D 5e game system.
    """
    proficiency: bool = Field(default=False, description="If true, the character is proficient in this saving throw, adding their proficiency bonus")
    bonus: int = Field(default=0, description="Any additional static bonus applied to the saving throw, beyond ability modifier and proficiency")
    bonus_modifiers: List[Tuple[str, int]] = Field(default=[], description="Any additional static modifiers applied to the saving throw, beyond ability modifier and proficiency")

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

    Properties:
        ability (AbilityName): The ability score type (strength, dexterity, etc.) that this saving throw is based on.

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

    name: SavingThrowName = Field(
        default="strength_saving_throw",
        description="The name of the saving throw in D&D 5e"
    )
    proficiency: bool = Field(default=False, description="If true, the character is proficient in this saving throw, adding their proficiency bonus")
    bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Saving Throw Bonus"), description="Any additional bonus applied to the saving throw, beyond ability modifier and proficiency")

    @property
    def ability(self) -> AbilityName:
        """
        Get the ability score associated with this saving throw.

        Returns:
            AbilityName: The ability score type (strength, dexterity, etc.) that this saving throw is based on.
        """
        return SAVING_THROW_TO_ABILITY[self.name]

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

    def _get_proficiency_converter(self) -> Callable[[int], int]:
        """
        Returns a lambda function that converts the proficiency bonus based on proficiency status.
        
        For saving throws, this is a simple binary multiplier:
        - If proficient: returns lambda x: x (multiplier of 1)
        - If not proficient: returns lambda x: 0 (multiplier of 0)

        Returns:
            Callable[[int], int]: A lambda function that applies the appropriate multiplier
                                 to the proficiency bonus.
        """
        return lambda x: x if self.proficiency else 0

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: SavingThrowName, source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
                config: Optional[SavingThrowConfig] = None) -> 'SavingThrow':
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
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.bonus, value_name=name+" Saving Throw Bonus")
            for modifier in config.bonus_modifiers:
                bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                       proficiency=config.proficiency, bonus=bonus)
        
class SavingThrowSetConfig(BaseModel):
    """
    Configuration for a set of saving throws in the D&D 5e game system.
    """
    strength_saving_throw: SavingThrowConfig = Field(default_factory=lambda: SavingThrowConfig(proficiency=False, bonus=0, bonus_modifiers=[]), description="Configuration for the strength saving throw")
    dexterity_saving_throw: SavingThrowConfig = Field(default_factory=lambda: SavingThrowConfig(proficiency=False, bonus=0, bonus_modifiers=[]), description="Configuration for the dexterity saving throw")
    constitution_saving_throw: SavingThrowConfig = Field(default_factory=lambda: SavingThrowConfig(proficiency=False, bonus=0, bonus_modifiers=[]), description="Configuration for the constitution saving throw")
    intelligence_saving_throw: SavingThrowConfig = Field(default_factory=lambda: SavingThrowConfig(proficiency=False, bonus=0, bonus_modifiers=[]), description="Configuration for the intelligence saving throw")
    wisdom_saving_throw: SavingThrowConfig = Field(default_factory=lambda: SavingThrowConfig(proficiency=False, bonus=0, bonus_modifiers=[]), description="Configuration for the wisdom saving throw")
    charisma_saving_throw: SavingThrowConfig = Field(default_factory=lambda: SavingThrowConfig(proficiency=False, bonus=0, bonus_modifiers=[]), description="Configuration for the charisma saving throw")


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

    Methods:
        get_saving_throw(ability_name: AbilityName) -> SavingThrow:
            Get a SavingThrow instance by its corresponding ability name.
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
    
    def get_saving_throw(self, ability_name: AbilityName) -> SavingThrow:
        """
        Get a SavingThrow instance by its corresponding ability name.

        Args:
            ability_name (AbilityName): The name of the ability to get the saving throw for.

        Returns:
            SavingThrow: The corresponding SavingThrow instance.

        Raises:
            ValueError: If no saving throw is found for the given ability name.
        """
        saving_throw_name = f"{ability_name}_saving_throw"
        if not hasattr(self, saving_throw_name):
            raise ValueError(f"No saving throw found for ability {ability_name}")
        return getattr(self, saving_throw_name)
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "SavingThrowSet", source_entity_name: Optional[str] = None, 
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               config: Optional[SavingThrowSetConfig] = None) -> 'SavingThrowSet':
        """
        Create a new SavingThrowSet instance with the given parameters.
        """
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            strength_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name="strength_saving_throw", source_entity_name=source_entity_name, 
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.strength_saving_throw)
            dexterity_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name="dexterity_saving_throw", source_entity_name=source_entity_name, 
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.dexterity_saving_throw)
            constitution_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name="constitution_saving_throw", source_entity_name=source_entity_name, 
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.constitution_saving_throw)
            intelligence_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name="intelligence_saving_throw", source_entity_name=source_entity_name, 
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.intelligence_saving_throw)
            wisdom_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name="wisdom_saving_throw", source_entity_name=source_entity_name, 
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.wisdom_saving_throw)
            charisma_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name="charisma_saving_throw", source_entity_name=source_entity_name, 
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.charisma_saving_throw)  
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                       strength_saving_throw=strength_saving_throw, dexterity_saving_throw=dexterity_saving_throw, constitution_saving_throw=constitution_saving_throw, 
                       intelligence_saving_throw=intelligence_saving_throw, wisdom_saving_throw=wisdom_saving_throw, charisma_saving_throw=charisma_saving_throw)
   