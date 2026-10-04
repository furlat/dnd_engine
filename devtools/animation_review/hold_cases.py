"""Passive selectors for native Holds and independent paralysis ownership."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HoldCase(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['hold']
    program: Literal['hold_person', 'hold_monster']
    saved: bool = False
    retain_paralysis: bool = False
    size_change: Literal['enlarge', 'reduce'] | None = None
