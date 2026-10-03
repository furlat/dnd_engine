"""Finite typed item properties and the neutral wearer-value capability."""
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from dnd.core.creature_types import DamageType
from dnd.core.values import ModifiableValue


class WearerValue(str, Enum):
    CHARISMA = "charisma"
    SPELL_ATTACK = "spell_attack"


@dataclass(frozen=True, slots=True)
class WearerBonus:
    target: WearerValue
    bonus: int
    name: str


@dataclass(frozen=True, slots=True)
class UnseenStrike:
    name: str = "Unseen Strike"
    die: Literal[4, 6, 8, 10, 12, 20] = 6
    count: int = 1
    damage_type: DamageType = DamageType.PIERCING

    def __post_init__(self) -> None:
        if self.count < 1 or self.die not in (4, 6, 8, 10, 12, 20):
            raise ValueError("Unseen strike requires supported positive dice")


@dataclass(frozen=True, slots=True)
class ArmorPenalties:
    stealth_disadvantage: bool = False
    strength_requirement: int | None = None


ItemProperty = WearerBonus | UnseenStrike | ArmorPenalties


@dataclass(frozen=True, slots=True)
class AdditionalDamage:
    die: Literal[4, 6, 8, 10, 12, 20]
    count: int
    damage_type: DamageType

    def __post_init__(self) -> None:
        if self.count < 1 or self.die not in (4, 6, 8, 10, 12, 20):
            raise ValueError("Additional damage requires supported positive dice")


@dataclass(frozen=True, slots=True)
class ItemWearerValues:
    charisma: ModifiableValue
    strength: ModifiableValue
    spell_attack: ModifiableValue
    stealth: ModifiableValue
    speeds: tuple[ModifiableValue, ...]
