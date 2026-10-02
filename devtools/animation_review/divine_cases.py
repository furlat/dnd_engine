"""Passive selectors for accepted Holy support presentation."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class DivineCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["divine"]
    program: Literal["beacon_of_hope", "daylight", "mass_healing_word", "divine_word", "flame_strike"]
    multiple_targets: bool = False
