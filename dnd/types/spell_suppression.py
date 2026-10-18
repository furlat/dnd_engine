"""Native spell protection outcomes, independent of presentation and handlers."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dnd.core.content.identities import ContentRef
from dnd.core.presentation_geometry import AoEPresentationGeometry


class SpellSuppression(BaseModel):
    """The protection responsible for excluding part of an admitted spell."""

    model_config = ConfigDict(frozen=True)

    provider_uuid: UUID
    positions: tuple[tuple[int, int], ...]
    provider_content_ref: ContentRef | None = None
    area_geometry: AoEPresentationGeometry | None = None
    anchor_elevation_steps: int | None = None
