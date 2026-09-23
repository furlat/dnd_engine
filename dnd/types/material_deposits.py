"""Passive physical source geometry shared by retained ground materials."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MaterialDepositSource(BaseModel):
    """One discharge's original frame; current owners retain actual coverage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    deposit_uuid: UUID
    origin: tuple[int, int]
    radius_cells: int = Field(ge=0)
