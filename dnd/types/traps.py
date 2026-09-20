"""Passive mechanical state and payload data for the authored spike family."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dnd.core.creature_types import DamageType
from dnd.types.abilities import AbilityName


class TrapState(str, Enum):
    """Mechanical mode of an installed device, independent of discovery."""

    READY = "ready"
    ACTIVATED = "activated"
    DEACTIVATED = "deactivated"


class TrapDamage(BaseModel):
    """One native damage component released by the spike mechanism."""

    model_config = ConfigDict(frozen=True)

    dice_count: int = Field(ge=1)
    dice_sides: Literal[4, 6, 8, 10, 12, 20]
    damage_type: DamageType


class TrapConditionPayload(BaseModel):
    """The first spike-family condition payload: a save against Poisoned."""

    model_config = ConfigDict(frozen=True)

    condition_id: Literal["condition.poisoned"] = "condition.poisoned"
    save_ability: AbilityName = "constitution"
    save_dc: int = Field(ge=0)
    duration_rounds: int = Field(ge=1)


class TrapPayload(BaseModel):
    """Finite payload data executed by the existing damage/save/condition APIs."""

    model_config = ConfigDict(frozen=True)

    damages: tuple[TrapDamage, ...] = (
        TrapDamage(dice_count=2, dice_sides=4, damage_type=DamageType.PIERCING),
    )
    condition: TrapConditionPayload | None = None
