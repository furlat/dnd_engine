"""Passive selections for original Hypnotic media on real concentration events."""

from typing import Literal
from pydantic import BaseModel, ConfigDict


class HypnoticCase(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['hypnotic']
    mode: Literal['clear','damage_one','recast'] = 'clear'
