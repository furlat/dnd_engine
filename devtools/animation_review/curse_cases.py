"""Passive inputs for the four native Bestow Curse choices."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CurseCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["curse"]
    option: int = Field(ge=1, le=4)
    saved: bool = False
