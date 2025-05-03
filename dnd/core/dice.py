from pydantic import BaseModel, Field, computed_field, model_validator
from typing import List, Optional, Union, Tuple, Self, ClassVar, Dict, Literal
import random
from dnd.core.values import ModifiableValue, AdvantageStatus, CriticalStatus, AutoHitStatus, StaticValue,NumericalModifier, ContextualValue
from enum import Enum
from uuid import UUID, uuid4
from functools import cached_property

class AttackOutcome(str, Enum):
    HIT = "Hit"
    MISS = "Miss"
    CRIT = "Crit"
    CRIT_MISS = "Crit Miss"

class RollType(str, Enum):
    DAMAGE = "Damage"
    ATTACK = "Attack"
    SAVE = "Save"
    CHECK = "Check"

class DiceRoll(BaseModel):
    """
    Represents the result of a dice roll.

    This class stores information about a specific dice roll, including the roll type,
    results, and various statuses that may affect the roll.

    Attributes:
        roll_uuid (UUID): Unique identifier for this roll. Automatically generated if not provided.
        dice_uuid (UUID): Unique identifier of the Dice object that produced this roll.
        roll_type (RollType): The type of roll (e.g., DAMAGE, ATTACK, SAVE, CHECK).
        results (Union[List[int], int]): The individual die results or a single result.
        total (int): The total value of the roll, including any bonuses.
        bonus (int): Any additional bonus applied to the roll.
        advantage_status (AdvantageStatus): The advantage status of the roll.
        critical_status (CriticalStatus): The critical status of the roll.
        auto_hit_status (AutoHitStatus): The auto-hit status of the roll.
        source_entity_uuid (UUID): UUID of the entity that made the roll.
        target_entity_uuid (Optional[UUID]): UUID of the target entity, if applicable.
        attack_outcome (Optional[AttackOutcome]): The outcome of an attack roll, if applicable.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'DiceRoll']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['DiceRoll']:
            Retrieve a DiceRoll instance from the registry by its UUID.
        unregister(cls, uuid: UUID) -> None:
            Remove a DiceRoll instance from the class registry.
    """

    _registry: ClassVar[Dict[UUID, 'DiceRoll']] = {}

    roll_uuid: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this roll. Automatically generated if not provided."
    )
    dice_uuid: UUID = Field(
        ...,
        description="Unique identifier of the Dice object that produced this roll."
    )
    roll_type: RollType = Field(
        ...,
        description="The type of roll (e.g., DAMAGE, ATTACK, SAVE, CHECK)."
    )
    results: Union[List[int], int] = Field(
        ...,
        description="The individual die results or a single result."
    )
    total: int = Field(
        ...,
        description="The total value of the roll, including any bonuses."
    )
    bonus: int = Field(
        ...,
        description="Any additional bonus applied to the roll."
    )
    advantage_status: AdvantageStatus = Field(
        ...,
        description="The advantage status of the roll."
    )
    critical_status: CriticalStatus = Field(
        ...,
        description="The critical status of the roll."
    )
    auto_hit_status: AutoHitStatus = Field(
        ...,
        description="The auto-hit status of the roll."
    )
    source_entity_uuid: UUID = Field(
        ...,
        description="UUID of the entity that made the roll."
    )
    target_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the target entity, if applicable."
    )
    attack_outcome: Optional[AttackOutcome] = Field(
        default=None,
        description="The outcome of an attack roll, if applicable."
    )

    def __init__(self, **data):
        super().__init__(**data)
        self.__class__._registry[self.roll_uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['DiceRoll']:
        """
        Retrieve a DiceRoll instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the DiceRoll to retrieve.

        Returns:
            Optional[DiceRoll]: The DiceRoll instance if found, None otherwise.
        """
        return cls._registry.get(uuid)

class Dice(BaseModel):
    """
    Represents a set of dice used for rolling.

    This class defines the properties of a set of dice, including the number of dice,
    their value, and any modifiers or special conditions that apply to rolls made with these dice.

    Attributes:
        uuid (UUID): Unique identifier for this set of dice. Automatically generated if not provided.
        count (int): The number of dice in this set.
        value (int): The number of sides on each die (e.g., 6 for a d6, 20 for a d20).
        bonus (ModifiableValue): Any modifiers or bonuses applied to rolls with these dice.
        roll_type (RollType): The type of roll these dice are used for (default is ATTACK).
        attack_outcome (Optional[AttackOutcome]): The outcome of an attack, if applicable.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'Dice']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['Dice']:
            Retrieve a Dice instance from the registry by its UUID.
        unregister(cls, uuid: UUID) -> None:
            Remove a Dice instance from the class registry.
        check_attack_outcome(self) -> Self:
            Validate the attack_outcome based on the roll_type.
        check_num_dice(self) -> Self:
            Validate the number of dice based on the roll_type.
        roll(self) -> DiceRoll:
            Perform a roll using these dice and return a DiceRoll object.

    Validators:
        check_attack_outcome(self) -> Self:
            Validate the attack_outcome based on the roll_type.
        check_num_dice(self) -> Self:
            Validate the number of dice based on the roll_type.
    """

    _registry: ClassVar[Dict[UUID, 'Dice']] = {}

    uuid: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this set of dice. Automatically generated if not provided."
    )
    count: int = Field(
        ...,
        description="The number of dice in this set.",
        ge=1,
    )
    value: Literal[4, 6, 8, 10, 12, 20] = Field(
        ...,
        description="The number of sides on each die (e.g., 6 for a d6, 20 for a d20)."
    )
    bonus: ModifiableValue = Field(
        ...,
        description="Any modifiers or bonuses applied to rolls with these dice."
    )
    roll_type: RollType = Field(
        default=RollType.ATTACK,
        description="The type of roll these dice are used for (default is ATTACK)."
    )
    attack_outcome: Optional[AttackOutcome] = Field(
        default=None,
        description="The outcome of an attack, if applicable."
    )

    def __init__(self, **data):
        super().__init__(**data)
        self.__class__._registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['Dice']:
        """
        Retrieve a Dice instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the Dice to retrieve.

        Returns:
            Optional[Dice]: The Dice instance if found, None otherwise.
        """
        return cls._registry.get(uuid)

    @model_validator(mode="after")
    def check_attack_outcome(self) -> Self:
        """
        Validate the attack_outcome based on the roll_type.

        Returns:
            Self: The validated Dice instance.

        Raises:
            ValueError: If the attack_outcome is invalid for the given roll_type.
        """
        if self.roll_type == RollType.DAMAGE and self.attack_outcome is None:
            raise ValueError("Attack outcome must be provided for damage rolls")
        elif self.roll_type != RollType.DAMAGE and self.attack_outcome is not None:
            raise ValueError("Attack outcome must be None for non-damage rolls")
        return self

    @model_validator(mode="after")
    def check_num_dice(self) -> Self:
        """
        Validate the number of dice based on the roll_type.

        Returns:
            Self: The validated Dice instance.

        Raises:
            ValueError: If the number of dice is invalid for the given roll_type.
        """
        if self.roll_type != RollType.DAMAGE and self.count > 1:
            raise ValueError("Cannot have more than one die for non-damage rolls")
        return self

    @computed_field
    @property
    def source_entity_uuid(self) -> UUID:
        """
        Get the UUID of the source entity for these dice.

        Returns:
            UUID: The UUID of the source entity.
        """
        return self.bonus.source_entity_uuid

    @computed_field
    @property
    def target_entity_uuid(self) -> Optional[UUID]:
        """
        Get the UUID of the target entity for these dice, if applicable.

        Returns:
            Optional[UUID]: The UUID of the target entity, or None if not applicable.
        """
        return self.bonus.target_entity_uuid

    def _roll_with_advantage(self) -> Tuple[int, List[int]]:
        """
        Perform a roll with advantage.

        This method rolls the dice twice and returns the higher result.

        Returns:
            Tuple[int, List[int]]: A tuple containing the highest roll result and a list of all roll results.
        """
        rolls = [random.randint(1, self.value) for _ in range(self.count)]
        return max(rolls), rolls

    def _roll_with_disadvantage(self) -> Tuple[int, List[int]]:
        """
        Perform a roll with disadvantage.

        This method rolls the dice twice and returns the lower result.

        Returns:
            Tuple[int, List[int]]: A tuple containing the lowest roll result and a list of all roll results.
        """
        rolls = [random.randint(1, self.value) for _ in range(self.count)]
        return min(rolls), rolls

    def _roll(self, crit: bool = False) -> List[Tuple[int, List[int]]]:
        """
        Perform a roll based on the current dice configuration.

        This method handles normal rolls, advantage, disadvantage, and critical hits.

        Args:
            crit (bool): Whether this is a critical hit roll. Defaults to False.

        Returns:
            List[Tuple[int, List[int]]]: A list of tuples, each containing the roll result and a list of all roll results.
        """
        count = self.count if not crit else self.count * 2
        advantage_status = self.bonus.advantage
        if advantage_status == AdvantageStatus.ADVANTAGE:
            return [self._roll_with_advantage() for _ in range(count)]
        elif advantage_status == AdvantageStatus.DISADVANTAGE:
            return [self._roll_with_disadvantage() for _ in range(count)]
        else:
            return [(random.randint(1, self.value), []) for _ in range(count)]
    @computed_field
    @cached_property
    def roll(self) -> DiceRoll:
        """
        Perform a roll using these dice and return a DiceRoll object.

        Returns:
            DiceRoll: The result of the dice roll.
        """
        if self.roll_type == RollType.DAMAGE:
            results = [roll[0] for roll in self._roll(crit=(self.attack_outcome == AttackOutcome.CRIT))]
            total = sum(results) + self.bonus.normalized_score
        else:
            results = self._roll()[0][0]
            total = results + self.bonus.normalized_score

        return DiceRoll(
            dice_uuid=self.uuid,
            roll_type=self.roll_type,
            results=results,
            total=total,
            bonus=self.bonus.normalized_score,
            advantage_status=self.bonus.advantage,
            critical_status=self.bonus.critical,
            auto_hit_status=self.bonus.auto_hit,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            attack_outcome=self.attack_outcome
        )

    
if __name__ == "__main__":
    
    source_entity_uuid = uuid4()
    target_entity_uuid = uuid4()
    modifier_uuid = uuid4()
    some_modifiable_value = ModifiableValue(source_entity_uuid=source_entity_uuid, 
                                            target_entity_uuid=target_entity_uuid, 
                                            self_static=StaticValue(name="example_static",
                                                                    source_entity_uuid=source_entity_uuid,
                                                                    value_modifiers={modifier_uuid: NumericalModifier(
                                                                        uuid=modifier_uuid,
                                                                        name="example_numerical_modifier",
                                                                        value=10,
                                                                        source_entity_uuid=source_entity_uuid,
                                                                        target_entity_uuid=source_entity_uuid)},
                                                                   ),
                                            
                                            self_contextual=ContextualValue(name="example_contextual",
                                                                        source_entity_uuid=source_entity_uuid),
                                            to_target_contextual=ContextualValue(name="example_to_target_contextual",
                                                                        source_entity_uuid=source_entity_uuid,
                                                                        target_entity_uuid=target_entity_uuid,is_outgoing_modifier=True),
                                                                        

                                            to_target_static=StaticValue(name="example_to_target_static",
                                                                    source_entity_uuid=source_entity_uuid,is_outgoing_modifier=True)
                                                                   
                                            )
    # Usage example:
    d20 = Dice(count=1, value=20, bonus=some_modifiable_value, roll_type=RollType.ATTACK)
    attack_roll = d20.roll
    print(f"Attack roll result: {attack_roll.total}")

    # Retrieving Dice and DiceRoll objects from registry
    retrieved_dice = Dice.get(d20.uuid)
    retrieved_roll = DiceRoll.get(attack_roll.roll_uuid)
    print(retrieved_roll)
