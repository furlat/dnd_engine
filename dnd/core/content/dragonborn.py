"""Dependency-neutral Dragonborn ancestry feature contracts."""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.types.abilities import AbilityName
from dnd.types.damage import DamageType

class DragonbornAncestry(str, Enum):
    """The ten draconic ancestries defined by SRD 5.1 Dragonborn."""

    BLACK = "black"
    BLUE = "blue"
    BRASS = "brass"
    BRONZE = "bronze"
    COPPER = "copper"
    GOLD = "gold"
    GREEN = "green"
    RED = "red"
    SILVER = "silver"
    WHITE = "white"


class DragonbornBreathGeometry(str, Enum):
    """Closed geometry families used by Dragonborn Breath Weapon."""

    LINE = "line"
    CONE = "cone"


class DragonbornAncestryFeatureDefinition(BaseModel):
    """Exact rules data selected by one Dragonborn ancestry choice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ancestry: DragonbornAncestry
    damage_type: DamageType
    breath_geometry: DragonbornBreathGeometry
    save_ability: AbilityName
    line_length_feet: int | None = Field(default=None, ge=5)
    line_width_feet: int | None = Field(default=None, ge=5)
    cone_length_feet: int | None = Field(default=None, ge=5)

    @model_validator(mode="after")
    def _validate_geometry(self) -> Self:
        if self.damage_type not in {
            DamageType.ACID,
            DamageType.COLD,
            DamageType.FIRE,
            DamageType.LIGHTNING,
            DamageType.POISON,
        }:
            raise ValueError("Dragonborn ancestry requires an elemental damage type")
        if self.save_ability not in {
            AbilityName.DEXTERITY,
            AbilityName.CONSTITUTION,
        }:
            raise ValueError("Dragonborn breath requires Dexterity or Constitution")
        if self.breath_geometry is DragonbornBreathGeometry.LINE:
            if (
                self.line_length_feet != 30
                or self.line_width_feet != 5
                or self.cone_length_feet is not None
            ):
                raise ValueError(
                    "line breath must be exactly 30 feet long and 5 feet wide",
                )
            return self
        if (
            self.cone_length_feet != 15
            or self.line_length_feet is not None
            or self.line_width_feet is not None
        ):
            raise ValueError("cone breath must be exactly 15 feet long")
        return self


__all__ = [
    "DragonbornAncestry",
    "DragonbornAncestryFeatureDefinition",
    "DragonbornBreathGeometry",
]
