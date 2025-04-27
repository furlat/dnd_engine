from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier

from enum import Enum
from random import randint
from functools import cached_property
from typing import Literal as TypeLiteral


from dnd.blocks.base_block import BaseBlock

def ability_score_normalizer(score: int) -> int:
    """ Normalizes the ability score to obtain the modifier with: (score - 10) // 2 """
    return (score - 10) // 2
abilities = Literal['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']

# Define abilities as a proper string literal type
AbilityName = TypeLiteral[
    'strength', 'dexterity', 'constitution', 
    'intelligence', 'wisdom', 'charisma'
]


class AbilityConfig(BaseModel):
    """
    Configuration for an Ability block.

    Attributes:
        ability_score (int): The base ability score, typically ranging from 3 to 20 for most characters, it will be used to initialize the base modifier of the ability
        ability_scores_modifiers (List[NumericalModifier]): Any additional numerical modifiers to the ability score, separate from the base score
        modifier_bonus (int): Any additional bonus to the ability modifier, separate from the base score
        modifier_bonus_modifiers (List[NumericalModifier]): Any additional numerical modifiers to the modifier bonus, separate from the base score
    """

    ability_score: int = Field(default=10, description="The base ability score, typically ranging from 3 to 20 for most characters, it will be used to initialize the base modifier of the ability")
    ability_scores_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional numerical modifiers to the ability score, separate from the base score")
    modifier_bonus: int = Field(default=0, description="Any additional bonus to the ability modifier, separate from the base score")
    modifier_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional numerical modifiers to the modifier bonus, separate from the base score")


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

    name: AbilityName = Field(
        default="strength", 
        description="The name of the ability (Strength, Dexterity, Constitution, Intelligence, Wisdom, or Charisma)"
    )
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
    
    def get_combined_values(self) -> ModifiableValue:
        """
        Combines the ability score and the modifier bonus.
        """
        return self.ability_score.combine_values([self.modifier_bonus])
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
                name: Literal['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'] = 'strength', config: Optional[AbilityConfig] = None) -> 'Ability':
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
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, name=name)
        else:
            ability_score = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.ability_score, value_name=name+" Ability Score", score_normalizer=ability_score_normalizer)
            if len(config.ability_scores_modifiers) > 0:
                for modifier in config.ability_scores_modifiers:
                    ability_score.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            modifier_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.modifier_bonus, value_name=name+" Modifier Bonus")
            if len(config.modifier_bonus_modifiers) > 0:
                for modifier in config.modifier_bonus_modifiers:
                    modifier_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            return cls(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, name=name, ability_score=ability_score, modifier_bonus=modifier_bonus)
        
class AbilityScoresConfig(BaseModel):
    """
    Configuration for an AbilityScores block.

    Attributes:
        strength (AbilityConfig): Configuration for the strength ability.
        dexterity (AbilityConfig): Configuration for the dexterity ability.
        constitution (AbilityConfig): Configuration for the constitution ability.
        intelligence (AbilityConfig): Configuration for the intelligence ability.
        wisdom (AbilityConfig): Configuration for the wisdom ability.
        charisma (AbilityConfig): Configuration for the charisma ability.
    """
    strength: AbilityConfig = Field(default_factory=AbilityConfig)
    dexterity: AbilityConfig = Field(default_factory=AbilityConfig)
    constitution: AbilityConfig = Field(default_factory=AbilityConfig)
    intelligence: AbilityConfig = Field(default_factory=AbilityConfig)
    wisdom: AbilityConfig = Field(default_factory=AbilityConfig)
    charisma: AbilityConfig = Field(default_factory=AbilityConfig)

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

    name: str = Field(default="ability_scores", description="The set of six core ability scores in D&D 5e")
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

    def get_ability(self, ability_name: AbilityName) -> Ability:
        """
        Get an Ability instance by its name.

        Args:
            ability_name (AbilityName): The name of the ability to retrieve.

        Returns:
            Ability: The corresponding Ability instance.
        """
        return getattr(self, ability_name)
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None, 
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               config: Optional[AbilityScoresConfig] = None) -> 'AbilityScores':
        """
        Create a new AbilityScores instance with the given parameters.

        Args:
            source_entity_uuid (UUID): The UUID of the source entity.
            source_entity_name (Optional[str]): The name of the source entity.
            target_entity_uuid (Optional[UUID]): The UUID of the target entity.
            target_entity_name (Optional[str]): The name of the target entity.
            config (Optional[AbilityScoresConfig]): The configuration for the ability scores.

        Returns:
            AbilityScores: The newly created AbilityScores instance.
        """
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, name="ability_scores")
        else:
            strength = Ability.create(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.strength)
            dexterity = Ability.create(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.dexterity)
            constitution = Ability.create(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.constitution)
            intelligence = Ability.create(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.intelligence)
            wisdom = Ability.create(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.wisdom)
            charisma = Ability.create(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.charisma)
            return cls(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, name="ability_scores", strength=strength, dexterity=dexterity, constitution=constitution, intelligence=intelligence, wisdom=wisdom, charisma=charisma)
