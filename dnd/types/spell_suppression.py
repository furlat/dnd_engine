"""Native spell protection outcomes, independent of presentation and handlers."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SpellSuppression(BaseModel):
    """The protection responsible for excluding part of an admitted spell."""

    model_config = ConfigDict(frozen=True)

    provider_uuid: UUID
    positions: tuple[tuple[int, int], ...]
