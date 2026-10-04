"""Passive results and selected modes of existing class features."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


MetamagicMode = Literal["quickened", "twinned", "distant"]
DraconicPresenceMode = Literal["awe", "fear"]
FontConversionDirection = Literal["slot_to_points", "points_to_slot"]


class IndomitableReroll(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    condition_uuid: UUID | None = None
    succeeded: bool


class RelentlessRageIntervention(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    condition_uuid: UUID | None = None
    succeeded: bool


class FontConversion(BaseModel):
    """One committed conversion; private resource amounts may be redacted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: FontConversionDirection
    slot_level: int | None = Field(default=None, ge=1, le=5)
    sorcery_points_delta: int | None = None
    spell_slots_delta: int | None = None
