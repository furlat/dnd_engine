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
from dnd.core.requests import AbilityName, SkillName

# Update the SKILL_TO_ABILITY mapping
SKILL_TO_ABILITY: Dict['SkillName', AbilityName] = {
    'acrobatics': 'dexterity',
    'animal_handling': 'wisdom',
    'arcana': 'intelligence',
    'athletics': 'strength',
    'deception': 'charisma',
    'history': 'intelligence',
    'insight': 'wisdom',
    'intimidation': 'charisma',
    'investigation': 'intelligence',
    'medicine': 'wisdom',
    'nature': 'intelligence',
    'perception': 'wisdom',
    'performance': 'charisma',
    'persuasion': 'charisma',
    'religion': 'intelligence',
    'sleight_of_hand': 'dexterity',
    'stealth': 'dexterity',
    'survival': 'wisdom'
}

# Define skills as a proper string literal type


skills_requiring_sight : List[SkillName] = ['perception','investigation', 'sleight_of_hand','stealth']
skills_requiring_hearing : List[SkillName] = ['perception','insight']
skills_requiring_speak : List[SkillName] = ['deception','intimidation','persuasion','performance']

class SkillConfig(BaseModel):
    """
    Configuration for a skill in the D&D 5e game system.

    Attributes:
    skill_bonus (int): The bonus to the skill check.
    skill_bonus_modifiers (List[Tuple[str, int]]): Any additional numerical modifiers to the skill bonus, separate from the base score.
    expertise (bool): Whether the character has expertise in this skill, which doubles the proficiency bonus.
    proficiency (bool): Whether the character is proficient in this skill, adding their proficiency bonus to checks.
    """
    skill_bonus: int = Field(default=0, description="The bonus to the skill check.")
    skill_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional numerical modifiers to the skill bonus, separate from the base score.")
    expertise: bool = Field(default=False, description="Whether the character has expertise in this skill, which doubles the proficiency bonus.")
    proficiency: bool = Field(default=False, description="Whether the character is proficient in this skill, adding their proficiency bonus to checks.")




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

    name: SkillName = Field(default="acrobatics", description="The name of the skill in D&D 5e")
    skill_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Skill Bonus"), description="Any additional bonus applied to skill checks, beyond ability modifier and proficiency")
    expertise: bool = Field(default=False, description="If true, the character has expertise in this skill, doubling their proficiency bonus")
    proficiency: bool = Field(default=False, description="If true, the character is proficient in this skill, adding their proficiency bonus to checks")

    @property
    def ability(self) -> AbilityName:
        """
        Get the ability score associated with this skill.

        Returns:
            AbilityName: The ability score type (strength, dexterity, etc.) that this skill is based on.
        """
        return SKILL_TO_ABILITY[self.name]

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
    def _get_proficiency_converter(self) -> Callable[[int], int]:
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
    def create(cls, source_entity_uuid: UUID, name: SkillName, source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
                config: Optional[SkillConfig] = None) -> 'Skill':
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
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            skill_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.skill_bonus, value_name=name+" Skill Bonus")
            if len(config.skill_bonus_modifiers) > 0:
                for modifier in config.skill_bonus_modifiers:
                    skill_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))

            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                       skill_bonus=skill_bonus, expertise=config.expertise, proficiency=config.proficiency)

class SkillSetConfig(BaseModel):
    """
    Configuration for a set of skills in the D&D 5e game system.

    Attributes:
    """
    acrobatics: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Dexterity (Acrobatics): Staying on your feet in tricky situations, such as balancing on a tightrope or staying upright on a rocking ship's deck")
    animal_handling: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Wisdom (Animal Handling): Calming domesticated animals, keeping mounts from getting spooked, or intuiting an animal's intentions")
    arcana: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Intelligence (Arcana): Recalling lore about spells, magic items, eldritch symbols, magical traditions, planes of existence, and planar inhabitants")
    athletics: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Strength (Athletics): Climbing, jumping, swimming, and other difficult physical activities")
    deception: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Charisma (Deception): Convincingly hiding the truth through words or actions")
    history: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Intelligence (History): Recalling lore about historical events, legendary people, ancient kingdoms, past disputes, recent wars, and lost civilizations")
    insight: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Wisdom (Insight): Determining the true intentions of others, detecting lies, and predicting someone's next move")
    intimidation: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Charisma (Intimidation): Influencing others through overt threats, hostile actions, and physical violence")
    investigation: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Intelligence (Investigation): Searching for clues and making deductions based on those clues")
    medicine: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Wisdom (Medicine): Stabilizing dying companions or diagnosing illnesses")
    nature: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Intelligence (Nature): Recalling lore about terrain, plants and animals, the weather, and natural cycles")
    perception: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Wisdom (Perception): Spotting, hearing, or detecting the presence of something, measuring general awareness and sensory acuity")
    performance: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Charisma (Performance): Delighting an audience with music, dance, acting, storytelling, or other forms of entertainment")
    persuasion: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Charisma (Persuasion): Influencing others through tact, social graces, or good nature")
    religion: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Intelligence (Religion): Recalling lore about deities, rites, prayers, religious hierarchies, holy symbols, and the practices of secret cults")
    sleight_of_hand: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Dexterity (Sleight of Hand): Performing acts of legerdemain, manual trickery, or subtle manipulations")
    stealth: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Dexterity (Stealth): Concealing yourself, moving silently, and avoiding detection")
    survival: SkillConfig = Field(default_factory=lambda: SkillConfig(skill_bonus=0, skill_bonus_modifiers=[], expertise=False, proficiency=False), description="Wisdom (Survival): Following tracks, hunting wild game, guiding through wilderness, identifying natural hazards, and predicting weather")
    
    





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
    def get_skill(self, skill_name: SkillName) -> Skill:
        """ Get the attribute corresponding to the skill name"""
        return getattr(self, skill_name)
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None, 
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               config: Optional[SkillSetConfig] = None) -> 'SkillSet':
        """
        Create a new SkillSet instance with the given parameters.
        """
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name="skill_set", source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            acrobatics = Skill.create(source_entity_uuid=source_entity_uuid, name="acrobatics", source_entity_name=source_entity_name, 
                                      target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.acrobatics)
            animal_handling = Skill.create(source_entity_uuid=source_entity_uuid, name="animal_handling", source_entity_name=source_entity_name, 
                                           target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.animal_handling)
            arcana = Skill.create(source_entity_uuid=source_entity_uuid, name="arcana", source_entity_name=source_entity_name, 
                                 target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.arcana)
            athletics = Skill.create(source_entity_uuid=source_entity_uuid, name="athletics", source_entity_name=source_entity_name, 
                                    target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.athletics)
            deception = Skill.create(source_entity_uuid=source_entity_uuid, name="deception", source_entity_name=source_entity_name, 
                                    target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.deception)
            history = Skill.create(source_entity_uuid=source_entity_uuid, name="history", source_entity_name=source_entity_name, 
                                  target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.history)
            insight = Skill.create(source_entity_uuid=source_entity_uuid, name="insight", source_entity_name=source_entity_name, 
                                  target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.insight)
            intimidation = Skill.create(source_entity_uuid=source_entity_uuid, name="intimidation", source_entity_name=source_entity_name, 
                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.intimidation)
            investigation = Skill.create(source_entity_uuid=source_entity_uuid, name="investigation", source_entity_name=source_entity_name, 
                                         target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.investigation)
            medicine = Skill.create(source_entity_uuid=source_entity_uuid, name="medicine", source_entity_name=source_entity_name, 
                                    target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.medicine)
            nature = Skill.create(source_entity_uuid=source_entity_uuid, name="nature", source_entity_name=source_entity_name, 
                                  target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.nature)
            perception = Skill.create(source_entity_uuid=source_entity_uuid, name="perception", source_entity_name=source_entity_name, 
                                      target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.perception)
            performance = Skill.create(source_entity_uuid=source_entity_uuid, name="performance", source_entity_name=source_entity_name, 
                                      target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.performance)
            persuasion = Skill.create(source_entity_uuid=source_entity_uuid, name="persuasion", source_entity_name=source_entity_name, 
                                      target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.persuasion)
            religion = Skill.create(source_entity_uuid=source_entity_uuid, name="religion", source_entity_name=source_entity_name, 
                                    target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.religion)
            sleight_of_hand = Skill.create(source_entity_uuid=source_entity_uuid, name="sleight_of_hand", source_entity_name=source_entity_name, 
                                          target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.sleight_of_hand)
            stealth = Skill.create(source_entity_uuid=source_entity_uuid, name="stealth", source_entity_name=source_entity_name, 
                                  target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.stealth)
            survival = Skill.create(source_entity_uuid=source_entity_uuid, name="survival", source_entity_name=source_entity_name, 
                                   target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.survival)
            
            return cls(source_entity_uuid=source_entity_uuid, name="skill_set", source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                       acrobatics=acrobatics, animal_handling=animal_handling, arcana=arcana, athletics=athletics, deception=deception, history=history, 
                       insight=insight, intimidation=intimidation, investigation=investigation, medicine=medicine, nature=nature, perception=perception, 
                       performance=performance, persuasion=persuasion, religion=religion, sleight_of_hand=sleight_of_hand, stealth=stealth, survival=survival)
    
    