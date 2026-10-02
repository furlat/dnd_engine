"""Passive native ray allocation selections."""

from typing import Literal
from pydantic import BaseModel, ConfigDict


class ScorchingCase(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    kind: Literal['scorching']
    direction: tuple[int,int]=(1,0)
    split: bool=False
    miss: bool=False
