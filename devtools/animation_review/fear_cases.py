"""Passive direction selections for the native Fear review."""

from typing import Literal
from pydantic import BaseModel, ConfigDict


class FearCase(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['fear']
    direction: tuple[int, int] = (0, 1)
