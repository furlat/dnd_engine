"""Passive choices and provenance for temporary creature existence."""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.core.content.recipes import ContentRecipe


class SummonFamily(str, Enum):
    ANIMALS = "animals"
    FEY = "fey"
    FIEND = "fiend"


class SummonManifestation(str, Enum):
    NATURAL = "natural"
    FEY_SPIRIT = "fey_spirit"
    FIEND = "fiend"


class SummonSustain(str, Enum):
    NONE = "none"
    EXISTENCE = "existence"
    CONTROL = "control"


class SummonDepartureCause(str, Enum):
    EXPIRED = "expired"
    DISMISSED = "dismissed"
    DEFEATED = "defeated"
    SUSTAIN_LOST = "sustain_lost"
    CLOSED = "closed"


class SummonSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    family: SummonFamily
    form_id: str = Field(min_length=1)
    cast_at_level: int = Field(ge=1, le=9)
    target_position: tuple[int, int]


class SummonRules(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    duration_rounds: int = Field(gt=0)
    sustain: SummonSustain


class SummonApplication(BaseModel):
    """Passive native cast routing; replay never resolves its runtime identities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    selection: SummonSelection
    binding_uuid: UUID
    action_uuid: UUID


class SummonOrigin(BaseModel):
    """Immutable origin; contains no copied creature state or controller."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summoner_uuid: UUID
    cast_lineage_uuid: UUID
    recipe: ContentRecipe
    form_id: str = Field(min_length=1)
    manifestation: SummonManifestation
    existence_condition_uuid: UUID
    control_condition_uuid: UUID | None = None


class TerminalOwnerRelease(BaseModel):
    """Exact ending existence owner, never an unrestricted force flag."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_uuid: UUID
    existence_condition_uuid: UUID
    cause: SummonDepartureCause
    parent_event_uuid: UUID | None = None

    @property
    def mandatory(self) -> bool:
        return self.cause is not SummonDepartureCause.DISMISSED
