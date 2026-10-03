"""Passive authored actor appearance."""

from typing import Literal, Optional
from pydantic import BaseModel, Field

BodyCategory = Literal["NakedBody", "NakedBody2", "NakedBody3"]
HeadCategory = Literal["Head1", "Head9", "Head10", "Head16", "Head17", "Head22"]
PresentationKind = Literal["layered", "placeholder"]


class AppearanceConfig(BaseModel):
    portrait_key: Optional[str] = Field(
        default=None,
        description="Stable authored-portrait key assigned by scenario composition.",
    )
    presentation_kind: PresentationKind = Field(
        default="layered",
        description="Renderer strategy for the actor body while full-entity assets are introduced.",
    )
    visual_scale: float = Field(
        default=1.0,
        gt=0,
        le=4.0,
        description="Presentation-only uniform actor scale independent of the creature's rules size.",
    )
    visual_scale_x: float = Field(
        default=1.0,
        gt=0,
        le=4.0,
        description=(
            "Presentation-only horizontal actor multiplier independent of "
            "the creature's rules size."
        ),
    )
    placeholder_tint: int = Field(
        default=0x36FF62,
        ge=0,
        le=0xFFFFFF,
        description="RGB body tint used when presentation_kind is placeholder.",
    )
    body_category: BodyCategory = Field(
        default="NakedBody",
        description="Renderer body taxonomy key used for the base creature layer.",
    )
    skin_tint: int = Field(
        default=0xDDAA88,
        ge=0,
        le=0xFFFFFF,
        description="RGB tint applied to exposed skin or body material.",
    )
    head_category: Optional[HeadCategory] = Field(
        default=None,
        description="Optional renderer head taxonomy key for hair-capable heads.",
    )
    hair_tint: int = Field(
        default=0,
        ge=0,
        le=0xFFFFFF,
        description="RGB tint applied to hair layers when a head supports hair.",
    )
    has_beard: bool = Field(
        default=False,
        description="Whether the renderer should include the beard overlay.",
    )
    beard_tint: int = Field(
        default=0,
        ge=0,
        le=0xFFFFFF,
        description="RGB tint applied to the beard overlay when present.",
    )


