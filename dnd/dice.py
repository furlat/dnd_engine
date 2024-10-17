from pydantic import BaseModel, Field, computed_field, model_validator
from typing import List, Optional, Union, Tuple, Self, ClassVar, Dict
import random
from dnd.modifiable_values import ModifiableValue, AdvantageStatus, CriticalStatus, AutoHitStatus, StaticValue,NumericalModifier, ContextualValue
from enum import Enum
from uuid import UUID, uuid4
from functools import cached_property

class AttackOutcome(str, Enum):
    HIT = "Hit"
    MISS = "Miss"
    CRIT = "Crit"

class RollType(str, Enum):
    DAMAGE = "Damage"
    ATTACK = "Attack"
    SAVE = "Save"
    CHECK = "Check"

class DiceRoll(BaseModel):
    _registry: ClassVar[Dict[UUID, 'DiceRoll']] = {}

    roll_uuid: UUID = Field(default_factory=uuid4)
    dice_uuid: UUID
    roll_type: RollType
    results: Union[List[int], int]
    total: int
    bonus: int
    advantage_status: AdvantageStatus
    critical_status: CriticalStatus
    auto_hit_status: AutoHitStatus
    source_entity_uuid: UUID
    target_entity_uuid: Optional[UUID]
    attack_outcome: Optional[AttackOutcome]

    def __init__(self, **data):
        super().__init__(**data)
        self.__class__._registry[self.roll_uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['DiceRoll']:
        return cls._registry.get(uuid)

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        cls._registry.pop(uuid, None)

class Dice(BaseModel):
    _registry: ClassVar[Dict[UUID, 'Dice']] = {}

    uuid: UUID = Field(default_factory=uuid4)
    count: int
    value: int
    bonus: ModifiableValue
    roll_type: RollType = Field(default=RollType.ATTACK)
    attack_outcome: Optional[AttackOutcome] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.__class__._registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['Dice']:
        return cls._registry.get(uuid)

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        cls._registry.pop(uuid, None)

    @model_validator(mode="after")
    def check_attack_outcome(self) -> Self:
        if self.roll_type == RollType.DAMAGE and self.attack_outcome is None:
            raise ValueError("Attack outcome must be provided for damage rolls")
        elif self.roll_type != RollType.DAMAGE and self.attack_outcome is not None:
            raise ValueError("Attack outcome must be None for non-damage rolls")
        return self

    @model_validator(mode="after")
    def check_num_dice(self) -> Self:
        if self.roll_type != RollType.DAMAGE and self.count > 1:
            raise ValueError("Cannot have more than one die for non-damage rolls")
        return self

    @computed_field
    @property
    def source_entity_uuid(self) -> UUID:
        return self.bonus.source_entity_uuid

    @computed_field
    @property
    def target_entity_uuid(self) -> Optional[UUID]:
        return self.bonus.target_entity_uuid

    def _roll_with_advantage(self) -> Tuple[int, List[int]]:
        rolls = [random.randint(1, self.value) for _ in range(self.count)]
        return max(rolls), rolls

    def _roll_with_disadvantage(self) -> Tuple[int, List[int]]:
        rolls = [random.randint(1, self.value) for _ in range(self.count)]
        return min(rolls), rolls

    def _roll(self, crit: bool = False) -> List[Tuple[int, List[int]]]:
        count = self.count if not crit else self.count * 2
        advantage_status = self.bonus.advantage
        if advantage_status == AdvantageStatus.ADVANTAGE:
            return [self._roll_with_advantage() for _ in range(count)]
        elif advantage_status == AdvantageStatus.DISADVANTAGE:
            return [self._roll_with_disadvantage() for _ in range(count)]
        else:
            return [(random.randint(1, self.value), []) for _ in range(count)]

    def roll(self) -> DiceRoll:
        if self.roll_type == RollType.DAMAGE:
            results = [roll[0] for roll in self._roll(crit=(self.attack_outcome == AttackOutcome.CRIT))]
            total = sum(results) + self.bonus.score
        else:
            results = self._roll()[0][0]
            total = results + self.bonus.score

        return DiceRoll(
            dice_uuid=self.uuid,
            roll_type=self.roll_type,
            results=results,
            total=total,
            bonus=self.bonus.score,
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
    some_modifiable_value = ModifiableValue(source_entity_uuid=source_entity_uuid, 
                                            target_entity_uuid=target_entity_uuid, 
                                            self_static=StaticValue(name="example_static",
                                                                    source_entity_uuid=uuid4(),
                                                                    value_modifiers=[NumericalModifier(
                                                                        name="example_numerical_modifier",value=10,source_entity_uuid=source_entity_uuid)],
                                                                   ),
                                            
                                            self_contextual=ContextualValue(name="example_contextual",
                                                                        source_entity_uuid=source_entity_uuid),
                                            to_target_contextual=ContextualValue(name="example_to_target_contextual",
                                                                        source_entity_uuid=source_entity_uuid,
                                                                        target_entity_uuid=target_entity_uuid),
                                            to_target_static=StaticValue(name="example_to_target_static",
                                                                    source_entity_uuid=source_entity_uuid)
                                                                   
                                            )
    # Usage example:
    d20 = Dice(count=1, value=20, bonus=some_modifiable_value, roll_type=RollType.ATTACK)
    attack_roll = d20.roll()
    print(f"Attack roll result: {attack_roll.total}")

    # Retrieving Dice and DiceRoll objects from registry
    retrieved_dice = Dice.get(d20.uuid)
    retrieved_roll = DiceRoll.get(attack_roll.roll_uuid)