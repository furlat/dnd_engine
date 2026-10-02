"""Passive module path selections for native wall review captures."""

from typing import Literal
from pydantic import BaseModel, ConfigDict


class AssemblyCase(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    kind: Literal['wall-assembly']
    program: Literal['thorns','wind']='thorns'
    direction: tuple[int,int]=(1,0)
    form: Literal['straight','corner','ring']='straight'
