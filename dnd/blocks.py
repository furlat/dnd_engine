from re import T
from typing import Dict, Optional, Any, List, Self, Literal,ClassVar
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.values import ModifiableValue
from dnd.modifiers import NumericalModifier
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

    @computed_field
    @property
    def values_dict_uuid_name(self) -> Dict[UUID, str]:
        return {value.uuid: value.name for value in self.get_values()}

    @computed_field
    @property
    def values_dict_name_uuid(self) -> Dict[str, UUID]:
        return {value.name: value.uuid for value in self.get_values()}

    @computed_field
    @property
    def blocks_dict_uuid_name(self) -> Dict[UUID, str]:
        return {block.uuid: block.name for block in self.get_blocks()}

    @computed_field
    @property
    def blocks_dict_name_uuid(self) -> Dict[str, UUID]:
        return {block.name: block.uuid for block in self.get_blocks()}

    def get_value_from_uuid(self, uuid: UUID) -> Optional[ModifiableValue]:
        for value in self.get_values():
            if value.uuid == uuid:
                return value
        return None

    def get_value_from_name(self, name: str) -> Optional[ModifiableValue]:
        for value in self.get_values():
            if value.name == name:
                return value
        return None

    def get_block_from_uuid(self, uuid: UUID) -> Optional['BaseBlock']:
        for block in self.get_blocks():
            if block.uuid == uuid:
                return block
        return None

    def get_block_from_name(self, name: str) -> Optional['BaseBlock']:
        for block in self.get_blocks():
            if block.name == name:
                return block
        return None

def ability_score_normalizer(score: int) -> int:
    """ Normalizes the ability score to obtain the modifier with: (score - 10) // 2 """
    return (score - 10) // 2
abilities = Literal['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']

class Ability(BaseBlock):
    name: abilities = Field(default="strength")
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
    strength: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="strength"))
    dexterity: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="dexterity"))
    constitution: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="constitution"))
    intelligence: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="intelligence"))
    wisdom: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="wisdom"))
    charisma: Ability = Field(default_factory=lambda: Ability.create(source_entity_uuid=uuid4(),name="charisma"))

    @computed_field
    @property
    def abilities_list(self) -> List[Ability]:
        return [self.strength, self.dexterity, self.constitution, self.intelligence, self.wisdom, self.charisma]
    @computed_field
    @property
    def ability_blocks_uuid_by_name(self) -> Dict[abilities, UUID]:
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
        return{ability.uuid:ability.name for ability in self.abilities_list}
    
    def get_modifier(self, ability_uuid: UUID) -> int:
        ability_object: Ability = getattr(self, self.ability_blocks_names_by_uuid[ability_uuid])
        return ability_object.modifier

    def get_modifier_from_uuid(self, ability_uuid: UUID) -> int:
        ability_object = self.get_block_from_uuid(ability_uuid)
        if ability_object and isinstance(ability_object, Ability):
            return ability_object.modifier
        raise ValueError(f"No Ability found with UUID {ability_uuid}")

    def get_modifier_from_name(self, ability_name: abilities) -> int:
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
    name: skills = Field(default="acrobatics", description="The name of the skill")
    skill_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Skill Bonus"))
    expertise: bool = Field(default=False, description="Whether the character is proficient in this skill")
    proficiency: bool = Field(default=False, description="Whether the character is proficient in this skill")

    def set_proficiency(self, proficiency: bool) -> None:
        self.proficiency = proficiency
    def set_expertise(self, expertise: bool) -> None:
        self.expertise = expertise
    def _get_proficiency_converter(self):
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
        return self._get_proficiency_converter()(profiency_bonus)+self.skill_bonus.score
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, name: skills, source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               expertise:bool=False,proficiency:bool=False) -> 'Skill':
        if expertise and not proficiency:
            proficiency = True
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                   target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                   expertise=expertise, proficiency=proficiency)
        

class SkillSet(BaseBlock):
    name: str = Field(default="SkillSet")
    acrobatics: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="acrobatics"))
    animal_handling: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="animal_handling"))
    arcana: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="arcana"))
    athletics: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="athletics"))
    deception: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="deception"))
    history: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="history"))
    insight: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="insight"))
    intimidation: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="intimidation"))
    investigation: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="investigation"))
    medicine: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="medicine"))
    nature: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="nature"))
    perception: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="perception"))
    performance: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="performance"))
    persuasion: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="persuasion"))
    religion: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="religion"))
    sleight_of_hand: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="sleight_of_hand"))
    stealth: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="stealth"))
    survival: Skill = Field(default_factory=lambda: Skill.create(source_entity_uuid=uuid4(),name="survival"))

    @computed_field
    @property
    def proficiencies(self) -> List[Skill]:
        blocks = self.get_blocks()
        return [skill for skill in blocks if isinstance(skill, Skill) and skill.proficiency]

    @computed_field
    @property
    def expertise(self) -> List[Skill]:
        blocks = self.get_blocks()
        return [skill for skill in blocks if isinstance(skill, Skill) and skill.expertise]
    
saving_throws = Literal["strength_saving_throw", "dexterity_saving_throw", "constitution_saving_throw", "intelligence_saving_throw", "wisdom_saving_throw", "charisma_saving_throw"]
saving_throw_name_to_ability = {
    "strength_saving_throw": "strength",
    "dexterity_saving_throw": "dexterity",
    "constitution_saving_throw": "constitution",
    "intelligence_saving_throw": "intelligence",
    "wisdom_saving_throw": "wisdom",
    "charisma_saving_throw": "charisma"
}
class SavingThrow(BaseBlock):
    name: saving_throws = Field(default="strength_saving_throw")
    proficiency: bool = Field(default=False)
    bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Saving Throw Bonus"))

    def get_bonus(self, proficiency_bonus:int) -> int:
        if self.proficiency:
            return self.bonus.score + proficiency_bonus
        else:
            return self.bonus.score

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: saving_throws, source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               proficiency:bool=False) -> 'SavingThrow':
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                   target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                   proficiency=proficiency)

class SavingThrowSet(BaseBlock):
    name: str = Field(default="SavingThrowSet")
    strength_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="strength_saving_throw"))
    dexterity_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="dexterity_saving_throw"))
    constitution_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="constitution_saving_throw"))
    intelligence_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="intelligence_saving_throw"))
    wisdom_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="wisdom_saving_throw"))
    charisma_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name="charisma_saving_throw"))
    
    @computed_field
    @property
    def proficiencies(self) -> List[SavingThrow]:
        blocks = self.get_blocks()
        return [saving_throw for saving_throw in blocks if isinstance(saving_throw, SavingThrow) and saving_throw.proficiency]
    
    
class HitDice(BaseBlock):
    name: str = Field(default="HitDice")
    hit_dice_value: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=6, value_name="Hit Dice Value"))
    hit_dice_count: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=1, value_name="Hit Dice Count"))
    mode: Literal["average", "maximums","roll"] = Field(default="average")

    @computed_field
    @cached_property
    def hit_points(self) -> int:
        first_level_hit_points = self.hit_dice_value.score
        remaining_dice_count = self.hit_dice_count.score - 1
        if self.mode == "average":
            return first_level_hit_points + remaining_dice_count * (self.hit_dice_value.score // 2)
        elif self.mode == "maximums":
            return first_level_hit_points + remaining_dice_count * self.hit_dice_value.score
        elif self.mode == "roll":
            return sum(randint(1, self.hit_dice_value.score) for _ in range(self.hit_dice_count.score))
        else:
            raise ValueError(f"Invalid mode: {self.mode}")
        
    @field_validator("hit_dice_value")
    def check_hit_dice_value(cls, v: ModifiableValue) -> ModifiableValue:
        allowed_dice = [4,6,8,10,12]
        if v.score not in allowed_dice:
            raise ValueError(f"Hit dice value must be one of the following: {allowed_dice} instead of {v.score}")
        return v

    @field_validator("hit_dice_count")
    def check_hit_dice_count(cls, v: ModifiableValue) -> ModifiableValue:
        if v.score < 1:
            raise ValueError(f"Hit dice count must be greater than 0 instead of {v.score}")
        return v
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "HitDice", source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               hit_dice_value: Literal[4,6,8,10,12] = 6, hit_dice_count: int = 1, mode: Literal["average", "maximums","roll"] = "average") -> 'HitDice':
        
        modifiable_hit_dice_value = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=hit_dice_value, value_name="Hit Dice Value")
        modifiable_hit_dice_count = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=hit_dice_count, value_name="Hit Dice Count")
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                   target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                   hit_dice_value=modifiable_hit_dice_value, hit_dice_count=modifiable_hit_dice_count, mode=mode)

damage_types = Literal["piercing", "bludgeoning", "slashing", "fire", "cold", "poison", "psychic", "radiant", "necrotic", "thunder", "acid", "lightning", "force", "thunder", "radiant", "necrotic", "psychic", "force"]

class Health(BaseBlock):
    name: str = Field(default="Health")
    hit_dices: List[HitDice] = Field(default_factory=lambda: [HitDice.create(source_entity_uuid=uuid4(),name="HitDice")])
    max_hit_points_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Max Hit Points Bonus"), description="Max Hit Points Bonus, e.g. Aid spell")
    temporary_hit_points: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Temporary Hit Points"), description="Temporary Hit Points, e.g. False Life spell")
    damage_taken: int = Field(default=0,ge=0, description="The amount of damage taken")
    damage_reduction: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Damage Reduction"), description="Damage Reduction, e.g. Damage Resistance")
    vulnerabilities: List[damage_types] = Field(default_factory=list, description="Damage Vulnerabilities")
    resistances: List[damage_types] = Field(default_factory=list, description="Damage Resistances")
    immunities: List[damage_types] = Field(default_factory=list, description="Damage Immunities")

    @computed_field
    @property
    def hit_dices_total_hit_points(self) -> int:
        return sum(hit_dice.hit_points for hit_dice in self.hit_dices)
    @computed_field
    @property
    def total_hit_dices_number(self) -> int:
        return sum(hit_dice.hit_dice_count.score for hit_dice in self.hit_dices)
    
    def add_damage(self, damage: int) -> None:
        self.damage_taken += damage

    def remove_damage(self, damage: int) -> None:
        self.damage_taken = max(0, self.damage_taken - damage)
    
    def damage_multiplier(self, damage_type: damage_types) -> float:
        if damage_type in self.vulnerabilities:
            return 2
        elif damage_type in self.resistances:
            return 0.5
        return 1
    
    def take_damage(self, damage: int, damage_type: damage_types,source_entity_uuid:UUID) -> None:
        if damage <0:
            raise ValueError(f"Damage must be greater than 0 instead of {damage}")
        damage_after_absorption = damage - self.damage_reduction.score
        damage_after_multiplier = int(damage_after_absorption * self.damage_multiplier(damage_type))
        current_temporary_hit_points = self.temporary_hit_points.score
        if current_temporary_hit_points <0:
            raise ValueError(f"Temporary Hit Points must be greater than 0 instead of {current_temporary_hit_points}")
        residual_damage = damage_after_multiplier - current_temporary_hit_points
        damage_to_temporaty_hp = current_temporary_hit_points if residual_damage > 0 else damage_after_multiplier
        self.remove_temporary_hit_points(damage_to_temporaty_hp,source_entity_uuid)
        if residual_damage > 0:
            self.add_damage(residual_damage)
    
    def heal(self, heal: int) -> None:
        self.damage_taken = max(0, self.damage_taken - heal)

    def add_temporary_hit_points(self, temporary_hit_points: int,source_entity_uuid:UUID) -> None:
        modifier = NumericalModifier(source_entity_uuid=source_entity_uuid,target_entity_uuid=self.uuid,name=f"Temporary Hit Points from {source_entity_uuid}",value=temporary_hit_points)
        if modifier.value > 0 and modifier.value > self.temporary_hit_points.score:
            self.temporary_hit_points.remove_all_modifiers()
            self.temporary_hit_points.self_static.add_value_modifier(modifier)
    
    def remove_temporary_hit_points(self, temporary_hit_points: int,source_entity_uuid:UUID) -> None:
        modifier = NumericalModifier(source_entity_uuid=source_entity_uuid,target_entity_uuid=self.uuid,name=f"Temporary Hit Points from {source_entity_uuid}",value=-temporary_hit_points)
        if modifier.value + self.temporary_hit_points.score <= 0:
            self.temporary_hit_points.remove_all_modifiers()
        else:
            self.temporary_hit_points.self_static.add_value_modifier(modifier)

    def get_max_hit_dices_points(self,constitution_modifier:int) -> int:
        return self.hit_dices_total_hit_points + constitution_modifier * self.total_hit_dices_number
    
    def get_total_hit_points(self,constitution_modifier:int) -> int:
        return self.get_max_hit_dices_points(constitution_modifier) + self.max_hit_points_bonus.score + self.temporary_hit_points.score - self.damage_taken

    def add_vulnerability(self, vulnerability: damage_types) -> None:
        if vulnerability not in self.vulnerabilities:
            self.vulnerabilities.append(vulnerability)
    def remove_vulnerability(self, vulnerability: damage_types) -> None:
        if vulnerability in self.vulnerabilities:
            self.vulnerabilities.remove(vulnerability)
    
    def add_resistance(self, resistance: damage_types) -> None:
        if resistance not in self.resistances:
            self.resistances.append(resistance)
    def remove_resistance(self, resistance: damage_types) -> None:
        if resistance in self.resistances:
            self.resistances.remove(resistance)
    
    def add_immunity(self, immunity: damage_types) -> None:
        if immunity not in self.immunities:
            self.immunities.append(immunity)
    def remove_immunity(self, immunity: damage_types) -> None:
        if immunity in self.immunities:
            self.immunities.remove(immunity)
