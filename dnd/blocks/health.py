from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier

from enum import Enum
from random import randint
from functools import cached_property
from typing import Literal as TypeLiteral


from dnd.core.base_block import BaseBlock



class HitDiceConfig(BaseModel):
    """
    Configuration for the HitDice block.
    """
    hit_dice_value: Literal[4,6,8,10,12] = 6
    hit_dice_value_modifiers: List[Tuple[str, int]] = Field(default=[], description="Any additional static modifiers applied to the hit dice value")
    hit_dice_count: int = 1
    hit_dice_count_modifiers: List[Tuple[str, int]] = Field(default=[], description="Any additional static modifiers applied to the hit dice count")
    mode: Literal["average", "maximums","roll"] = "average"
    ignore_first_level: bool = Field(default=False)

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
    ignore_first_level: bool = Field(default=False)

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
        first_level_hit_points = self.hit_dice_value.score if not self.ignore_first_level else 0
        remaining_dice_count = self.hit_dice_count.score - 1 if not self.ignore_first_level else self.hit_dice_count.score
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
                config: Optional[HitDiceConfig] = None) -> 'HitDice':
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
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            modifiable_hit_dice_value = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=config.hit_dice_value, value_name="Hit Dice Value")
            for modifier in config.hit_dice_value_modifiers:
                modifiable_hit_dice_value.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            modifiable_hit_dice_count = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=config.hit_dice_count, value_name="Hit Dice Count")
            for modifier in config.hit_dice_count_modifiers:
                modifiable_hit_dice_count.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                       hit_dice_value=modifiable_hit_dice_value, hit_dice_count=modifiable_hit_dice_count, mode=config.mode, ignore_first_level=config.ignore_first_level)

# damage_types = Literal["piercing", "bludgeoning", "slashing", "fire", "cold", "poison", "psychic", "radiant", "necrotic", "thunder", "acid", "lightning", "force", "thunder", "radiant", "necrotic", "psychic", "force"]
# damage_types_list = ["piercing", "bludgeoning", "slashing", "fire", "cold", "poison", "psychic", "radiant", "necrotic", "thunder", "acid", "lightning", "force", "thunder", "radiant", "necrotic", "psychic", "force"]

class HealthConfig(BaseModel):
    """
    Configuration for the Health block.
    """
    hit_dices: List[HitDiceConfig] = Field(default_factory=list, description="Hit dice configuration")
    max_hit_points_bonus: int = Field(default=0, description="Max Hit Points Bonus, e.g. something like a default Aid spell, not really used in dnd but kept for consistency")
    max_hit_points_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the max hit points bonus,  e.g. Aid spell but here it would not have a duration")
    temporary_hit_points: int = Field(default=0, description="Temporary Hit Points, e.g. something like a default False Life spell")
    temporary_hit_points_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the temporary hit points, e.g. False Life spell but here it would not have a duration")
    damage_reduction: int = Field(default=0, description="Damage Reduction, e.g. flat Damage Reduction")
    damage_reduction_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the damage reduction")
    vulnerabilities: List[DamageType] = Field(default_factory=list, description="Types of damage the entity is vulnerable to")
    resistances: List[DamageType] = Field(default_factory=list, description="Types of damage the entity is resistant to")
    immunities: List[DamageType] = Field(default_factory=list, description="Types of damage the entity is immune to")

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
    
    def take_damage(self, damage: int, damage_type: DamageType, source_entity_uuid: UUID) -> int:
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
        damage_after_absorption = damage 
        damage_after_multiplier = max(0,int(damage_after_absorption * self.damage_multiplier(damage_type)) - self.damage_reduction.score)
        current_temporary_hit_points = self.temporary_hit_points.score
        if current_temporary_hit_points < 0:
            raise ValueError(f"Temporary Hit Points must be greater than 0 instead of {current_temporary_hit_points}")
        residual_damage = damage_after_multiplier - current_temporary_hit_points
        damage_to_temporaty_hp = current_temporary_hit_points if residual_damage > 0 else damage_after_multiplier
        self.remove_temporary_hit_points(damage_to_temporaty_hp, source_entity_uuid)
        if residual_damage > 0:
            self.add_damage(residual_damage)
            return residual_damage
        else:
            return 0
    
    def heal(self, heal: int) -> None:
        """
        Heal the entity by removing damage. Cannot remove damage taken by the temporary hit points.

        Args:
            heal (int): The amount of healing to apply.
        """
        if self.temporary_hit_points.score > 0:
            #check if we have temporary hit points that absorbed the damage taken, 
            # sicne we can not heal them we can only heal the portion that went through them

            damage_taken_after_temporary_hp = self.damage_taken - self.temporary_hit_points.score
            damage_absorbed_by_temporary_hp = min(self.damage_taken,self.temporary_hit_points.score)
            if damage_taken_after_temporary_hp > 0:
                #if some damage went through the temporary hit points we can heal them but keep the absorbed portion of damage
                self.damage_taken = max(0, damage_taken_after_temporary_hp - heal) + damage_absorbed_by_temporary_hp
        else:
            #if we have no temporary hit points we can heal the damage taken
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

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "Health", source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
                config: Optional[HealthConfig] = None) -> 'Health':
        """
        Create a new Health instance with the given parameters.
        """
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            hit_dices = [HitDice.create(source_entity_uuid=source_entity_uuid, config=hit_dice) for hit_dice in config.hit_dices]
            max_hit_points_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.max_hit_points_bonus, value_name="Max Hit Points Bonus")
            for modifier in config.max_hit_points_bonus_modifiers:
                max_hit_points_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            temporary_hit_points = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.temporary_hit_points, value_name="Temporary Hit Points")
            for modifier in config.temporary_hit_points_modifiers:
                temporary_hit_points.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            damage_reduction = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.damage_reduction, value_name="Damage Reduction")
            for modifier in config.damage_reduction_modifiers:
                damage_reduction.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            for vulnerability in config.vulnerabilities:
                damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid, value=ResistanceStatus.VULNERABILITY, damage_type=vulnerability, name=f"Vulnerability to {vulnerability}"))
            for resistance in config.resistances:
                damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid, value=ResistanceStatus.RESISTANCE, damage_type=resistance, name=f"Resistance to {resistance}"))
            for immunity in config.immunities:
                damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid, value=ResistanceStatus.IMMUNITY, damage_type=immunity, name=f"Immunity to {immunity}"))
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                       hit_dices=hit_dices, max_hit_points_bonus=max_hit_points_bonus, temporary_hit_points=temporary_hit_points, damage_reduction=damage_reduction)
