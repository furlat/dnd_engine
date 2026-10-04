"""Dependency-neutral provenance contracts for applied game effects."""

from enum import Enum
from typing import Annotated, Literal, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ObjectSectionVolume(BaseModel):
    """One native ten-foot cube, resolved from an admitted object contact."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    minimum_position: tuple[int, int]
    base_height_steps: int

    def contains_band(self, position: tuple[int, int], height: int) -> bool:
        return (self.minimum_position[0] <= position[0] < self.minimum_position[0] + 2
            and self.minimum_position[1] <= position[1] < self.minimum_position[1] + 2
            and self.base_height_steps <= height < self.base_height_steps + 2)

    def contains_point(self, point: tuple[float, float]) -> bool:
        return (self.minimum_position[0] - .5 < point[0] < self.minimum_position[0] + 1.5
            and self.minimum_position[1] - .5 < point[1] < self.minimum_position[1] + 1.5)


class EventResolutionRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["event"] = "event"
    lineage_uuid: UUID


class ApplicationResolutionRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["application"] = "application"
    lineage_uuid: UUID
    application_id: UUID


ResolutionRef = Annotated[EventResolutionRef | ApplicationResolutionRef, Field(discriminator="kind")]


class ApplicationMembership(BaseModel):
    """One ordered application belonging to an existing action lineage."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    lineage_uuid: UUID
    application_id: UUID
    index: int = Field(ge=0)


class EffectEndpoint(BaseModel):
    """Actual contact retained before an application can remove its recipient."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["creature", "object"]
    uuid: UUID
    position: tuple[int, int]
    base_height_steps: int


class EffectPropagationLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source: EffectEndpoint
    target: EffectEndpoint
    application_id: UUID


ObservedField = Literal["position", "visibility", "light", "hazards", "senses", "paths",
                   "entity_contact", "object_contact", "spatial_effect"]


class ObservedChangeRef(BaseModel):
    """One observed field at an actual native refresh/commit boundary.

    Fields sharing a source event and cursor belong to the same indivisible
    observation. This reference supplies provenance, never a second after-value.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_event_uuid: UUID
    source_index: int = Field(ge=0)
    resolution_ref: ResolutionRef | None = None
    field: ObservedField
    owner_uuid: UUID


class AntimagicException(str, Enum):
    ARTIFACT = "artifact"
    DEITY = "deity"
    FIELD = "antimagic_field"


class EffectOriginKind(str, Enum):
    """High-level source category for an applied effect."""

    SPELL = "spell"
    ACTION = "action"
    ITEM = "item"
    ENVIRONMENT = "environment"
    UNKNOWN = "unknown"


class EffectOrigin(BaseModel):
    """Immutable, serialization-safe provenance carried by an effect.

    Fields contain only primitive transport values so this type can remain a
    true dependency leaf. Spell provenance distinguishes the spell's base
    level from the effective slot level used for protection and scaling rules.
    """

    model_config = ConfigDict(frozen=True)

    kind: EffectOriginKind = Field(default=EffectOriginKind.UNKNOWN)
    antimagic_exception: AntimagicException | None = None
    source_id: Optional[str] = Field(default=None)
    source_event_lineage_uuid: Optional[str] = Field(default=None)
    source_position: Optional[Tuple[int, int]] = Field(default=None)
    base_spell_level: Optional[int] = Field(default=None, ge=0)
    effective_spell_level: Optional[int] = Field(default=None, ge=0)

    @classmethod
    def spell(
        cls,
        *,
        source_id: Optional[str],
        source_event_lineage_uuid: Optional[str],
        source_position: Optional[Tuple[int, int]] = None,
        base_spell_level: int,
        effective_spell_level: int,
        antimagic_exception: AntimagicException | None = None,
    ) -> "EffectOrigin":
        """Create explicit spell provenance from a spell event payload."""
        return cls(
            kind=EffectOriginKind.SPELL,
            antimagic_exception=antimagic_exception,
            source_id=source_id,
            source_event_lineage_uuid=source_event_lineage_uuid,
            source_position=source_position,
            base_spell_level=base_spell_level,
            effective_spell_level=effective_spell_level,
        )
