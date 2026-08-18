"""Cold direct rules selected by one Dragonborn ancestry choice."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from dnd.types.abilities import AbilityName
from dnd.types.damage import DamageType
from dnd.types.dragonborn import (
    DragonbornAncestry,
    DragonbornBreathGeometry,
)


@dataclass(frozen=True, slots=True)
class DragonbornAncestryDefinition:
    """Renderer-independent resistance, save, and geometry facts."""

    ancestry: DragonbornAncestry
    damage_type: DamageType
    breath_geometry: DragonbornBreathGeometry
    save_ability: AbilityName
    line_length_feet: int | None = None
    line_width_feet: int | None = None
    cone_length_feet: int | None = None


def _line(
    ancestry: DragonbornAncestry,
    damage_type: DamageType,
) -> DragonbornAncestryDefinition:
    return DragonbornAncestryDefinition(
        ancestry=ancestry,
        damage_type=damage_type,
        breath_geometry=DragonbornBreathGeometry.LINE,
        save_ability=AbilityName.DEXTERITY,
        line_length_feet=30,
        line_width_feet=5,
    )


def _cone(
    ancestry: DragonbornAncestry,
    damage_type: DamageType,
    save_ability: AbilityName,
) -> DragonbornAncestryDefinition:
    return DragonbornAncestryDefinition(
        ancestry=ancestry,
        damage_type=damage_type,
        breath_geometry=DragonbornBreathGeometry.CONE,
        save_ability=save_ability,
        cone_length_feet=15,
    )


DRAGONBORN_ANCESTRY_DEFINITIONS: Mapping[
    DragonbornAncestry,
    DragonbornAncestryDefinition,
] = MappingProxyType({
    DragonbornAncestry.BLACK: _line(
        DragonbornAncestry.BLACK,
        DamageType.ACID,
    ),
    DragonbornAncestry.BLUE: _line(
        DragonbornAncestry.BLUE,
        DamageType.LIGHTNING,
    ),
    DragonbornAncestry.BRASS: _line(
        DragonbornAncestry.BRASS,
        DamageType.FIRE,
    ),
    DragonbornAncestry.BRONZE: _line(
        DragonbornAncestry.BRONZE,
        DamageType.LIGHTNING,
    ),
    DragonbornAncestry.COPPER: _line(
        DragonbornAncestry.COPPER,
        DamageType.ACID,
    ),
    DragonbornAncestry.GOLD: _cone(
        DragonbornAncestry.GOLD,
        DamageType.FIRE,
        AbilityName.DEXTERITY,
    ),
    DragonbornAncestry.GREEN: _cone(
        DragonbornAncestry.GREEN,
        DamageType.POISON,
        AbilityName.CONSTITUTION,
    ),
    DragonbornAncestry.RED: _cone(
        DragonbornAncestry.RED,
        DamageType.FIRE,
        AbilityName.DEXTERITY,
    ),
    DragonbornAncestry.SILVER: _cone(
        DragonbornAncestry.SILVER,
        DamageType.COLD,
        AbilityName.CONSTITUTION,
    ),
    DragonbornAncestry.WHITE: _cone(
        DragonbornAncestry.WHITE,
        DamageType.COLD,
        AbilityName.CONSTITUTION,
    ),
})


__all__ = [
    "DRAGONBORN_ANCESTRY_DEFINITIONS",
    "DragonbornAncestryDefinition",
]
