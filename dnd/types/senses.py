"""Dependency-neutral types shared by perception components and events."""

from collections.abc import Mapping
from enum import Enum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SensesType(str, Enum):
    """Special sense categories supported by the perception pipeline."""

    BLINDSIGHT = "Blindsight"
    DARKVISION = "Darkvision"
    TREMORSENSE = "Tremorsense"
    TRUESIGHT = "Truesight"
    DEVILS_SIGHT = "Devils Sight"
    SEE_INVISIBLE = "See Invisible"


class SenseMode(BaseModel):
    """A special sense and its effective range in feet; zero is unlimited."""

    sense_type: SensesType = Field(description="Special sense category.")
    range_feet: int = Field(default=0, description="Range in feet; zero means unlimited.")


class OpticalObscurement(str, Enum):
    """Observer-relative optical obstruction contributed by world mechanics."""

    HEAVY = "heavy"
    MAGICAL_DARKNESS = "magical_darkness"


class PerceivedContact(BaseModel):
    """One identified entity or object perceived by an observer."""

    model_config = ConfigDict(frozen=True)

    position: tuple[int, int] = Field(description="Observed grid position.")
    visual: bool = Field(description="Whether a visual route establishes this contact.")
    special_senses: tuple[SensesType, ...] = Field(
        default=(),
        description="Non-ordinary senses which independently establish this contact.",
    )


class SensesView(Protocol):
    """Minimal perception surface exposed upward by an observing block."""

    position: tuple[int, int]
    visible: Mapping[tuple[int, int], object]
    entities: Mapping[UUID, PerceivedContact]
    objects: Mapping[UUID, PerceivedContact]

    def get_feet_distance(self, position: tuple[int, int]) -> int:
        """Return grid distance to one position in rules feet."""
        ...


__all__ = [
    "OpticalObscurement",
    "PerceivedContact",
    "SenseMode",
    "SensesType",
    "SensesView",
]
