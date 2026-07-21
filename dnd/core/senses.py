"""Dependency-neutral types shared by perception components and events."""

from enum import Enum

from pydantic import BaseModel, Field


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
