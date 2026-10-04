"""Passive parameters for the native holy spell gallery."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HolyCase(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['holy-spell']
    program: Literal['spirit_radiant', 'spirit_necrotic', 'guardian', 'feast']
    immune: bool = False
    expire: bool = False
