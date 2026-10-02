"""Passive selectors for accepted Slow artwork and native save outcomes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SlowCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["slow"]
    saved: bool = False
