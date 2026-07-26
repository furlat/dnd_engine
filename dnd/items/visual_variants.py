"""Dependency-neutral typed parameters for presentation-only item variants."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ItemVisualVariantParameters(BaseModel):
    """Optional authored label and renderer identity over unchanged mechanics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    visual_variant_id: str | None = Field(default=None, min_length=1)
    display_name: str | None = Field(default=None, min_length=1)
