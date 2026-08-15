from typing import Dict, Optional,  List, Callable, Tuple
from uuid import UUID, uuid4, uuid5
from pydantic import BaseModel, Field,  computed_field
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier
from dnd.core.base_block import BaseBlock
from dnd.types import abilities as ability_types
from dnd.types.proficiency import ProficiencyMode, ProficiencySourceSet

SAVING_THROW_TO_ABILITY: Dict[ability_types.SavingThrowName, ability_types.AbilityName] = {
    ability_types.SavingThrowName.STRENGTH: ability_types.AbilityName.STRENGTH,
    ability_types.SavingThrowName.DEXTERITY: ability_types.AbilityName.DEXTERITY,
    ability_types.SavingThrowName.CONSTITUTION: ability_types.AbilityName.CONSTITUTION,
    ability_types.SavingThrowName.INTELLIGENCE: ability_types.AbilityName.INTELLIGENCE,
    ability_types.SavingThrowName.WISDOM: ability_types.AbilityName.WISDOM,
    ability_types.SavingThrowName.CHARISMA: ability_types.AbilityName.CHARISMA,
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
        ability (ability_types.AbilityName): The ability score type (strength, dexterity, etc.) that this saving throw is based on.

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

    name: ability_types.SavingThrowName = Field(
        default=ability_types.SavingThrowName.STRENGTH,
        description="The name of the saving throw in D&D 5e"
    )
    bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(),base_value=0, value_name="Saving Throw Bonus"), description="Any additional bonus applied to the saving throw, beyond ability modifier and proficiency")
    proficiency_sources: ProficiencySourceSet = Field(
        default_factory=ProficiencySourceSet,
        description="Exact source-owned proficiency contributions.",
    )

    @computed_field
    @property
    def proficiency(self) -> bool:
        """Return the proficiency fact derived from owned sources."""
        return self.proficiency_sources.is_proficient

    @property
    def ability(self) -> ability_types.AbilityName:
        """
        Get the ability score associated with this saving throw.

        Returns:
            ability_types.AbilityName: The ability score type (strength, dexterity, etc.) that this saving throw is based on.
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
        return self.bonus.score + self._get_proficiency_converter()(
            proficiency_bonus
        )

    def add_proficiency_source(
        self,
        source_id: UUID,
        mode: ProficiencyMode,
    ) -> None:
        """Add one exact proficiency grant without disturbing other sources."""
        self.proficiency_sources.add(source_id, mode)

    def remove_proficiency_source(self, source_id: UUID) -> bool:
        """Remove one exact proficiency grant."""
        return self.proficiency_sources.remove(source_id)

    def set_proficiency(self, proficiency: bool) -> None:
        """Set or remove the imperative proficiency source."""
        source_id = uuid5(self.uuid, "saving-throw:manual:proficiency")
        if proficiency:
            self.add_proficiency_source(source_id, ProficiencyMode.FULL)
        else:
            self.remove_proficiency_source(source_id)

    def _get_proficiency_converter(self) -> Callable[[int], int]:
        """Return the source-owned proficiency conversion function.

        The converter applies the strongest registered proficiency mode to the
        supplied character proficiency bonus. With no registered source it
        returns zero.
        """
        def convert(proficiency_bonus: int) -> int:
            return self.proficiency_sources.apply(proficiency_bonus)

        return convert

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: ability_types.SavingThrowName, source_entity_name: Optional[str] = None,
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
            saving_throw = cls(
                source_entity_uuid=source_entity_uuid,
                name=name,
                source_entity_name=source_entity_name,
                target_entity_uuid=target_entity_uuid,
                target_entity_name=target_entity_name,
                bonus=bonus,
            )
            if config.proficiency:
                saving_throw.set_proficiency(True)
            return saving_throw

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
        get_saving_throw(ability_name: ability_types.AbilityName) -> SavingThrow:
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
    strength_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name=ability_types.SavingThrowName.STRENGTH), description="Strength saving throw: Used to resist physical force and avoid being moved against your will")
    dexterity_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name=ability_types.SavingThrowName.DEXTERITY), description="Dexterity saving throw: Used to dodge area effects, such as the breath of a dragon or a fireball spell")
    constitution_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name=ability_types.SavingThrowName.CONSTITUTION), description="Constitution saving throw: Used to resist poison, disease, and other bodily ailments")
    intelligence_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name=ability_types.SavingThrowName.INTELLIGENCE), description="Intelligence saving throw: Used to resist mental attacks and illusions")
    wisdom_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name=ability_types.SavingThrowName.WISDOM), description="Wisdom saving throw: Used to resist mental influence or charm effects")
    charisma_saving_throw: SavingThrow = Field(default_factory=lambda: SavingThrow.create(source_entity_uuid=uuid4(),name=ability_types.SavingThrowName.CHARISMA), description="Charisma saving throw: Used to resist effects that would subsume your personality or possess you")

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

    def get_saving_throw(self, ability_name: ability_types.AbilityName) -> SavingThrow:
        """
        Get a SavingThrow instance by its corresponding ability name.

        Args:
            ability_name (ability_types.AbilityName): The name of the ability to get the saving throw for.

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
            strength_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name=ability_types.SavingThrowName.STRENGTH, source_entity_name=source_entity_name,
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.strength_saving_throw)
            dexterity_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name=ability_types.SavingThrowName.DEXTERITY, source_entity_name=source_entity_name,
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.dexterity_saving_throw)
            constitution_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name=ability_types.SavingThrowName.CONSTITUTION, source_entity_name=source_entity_name,
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.constitution_saving_throw)
            intelligence_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name=ability_types.SavingThrowName.INTELLIGENCE, source_entity_name=source_entity_name,
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.intelligence_saving_throw)
            wisdom_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name=ability_types.SavingThrowName.WISDOM, source_entity_name=source_entity_name,
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.wisdom_saving_throw)
            charisma_saving_throw = SavingThrow.create(source_entity_uuid=source_entity_uuid, name=ability_types.SavingThrowName.CHARISMA, source_entity_name=source_entity_name,
                                                        target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, config=config.charisma_saving_throw)
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name,
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name,
                       strength_saving_throw=strength_saving_throw, dexterity_saving_throw=dexterity_saving_throw, constitution_saving_throw=constitution_saving_throw,
                       intelligence_saving_throw=intelligence_saving_throw, wisdom_saving_throw=wisdom_saving_throw, charisma_saving_throw=charisma_saving_throw)
