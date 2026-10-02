"""Passive selector for the accepted permanent point-light lifecycle."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ContinualFlameCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["continual-flame"]
