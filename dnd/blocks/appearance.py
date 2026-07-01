"""Passive visual identity metadata for entities.

Appearance is intentionally gameplay-inert. It gives renderers the stable body,
skin, hair, and beard taxonomy needed to build sprite layers without guessing
from entity names or classes.
"""

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from dnd.core.base_block import BaseBlock

BodyCategory = Literal["NakedBody", "NakedBody2", "NakedBody3"]
HeadCategory = Literal["Head1", "Head9", "Head10", "Head16", "Head17", "Head22"]


class AppearanceConfig(BaseModel):
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


class Appearance(BaseBlock):
    name: str = Field(default="Appearance", description="Block name used in entity composition indexes.")
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

    @classmethod
    def create(
        cls,
        source_entity_uuid: UUID,
        source_entity_name: Optional[str] = None,
        target_entity_uuid: Optional[UUID] = None,
        target_entity_name: Optional[str] = None,
        name: str = "Appearance",
        config: Optional[AppearanceConfig] = None,
    ) -> "Appearance":
        """Create an appearance block from optional renderer metadata.

        Args:
            source_entity_uuid: Entity UUID that owns the appearance block.
            source_entity_name: Optional display name for the source entity.
            target_entity_uuid: Optional target UUID propagated by block setup.
            target_entity_name: Optional display name for the target entity.
            name: Block name used in entity composition indexes.
            config: Optional appearance configuration to materialize.

        Returns:
            Appearance block with source/target metadata and renderer fields.
        """
        data = (config or AppearanceConfig()).model_dump()
        return cls(
            source_entity_uuid=source_entity_uuid,
            source_entity_name=source_entity_name,
            target_entity_uuid=target_entity_uuid,
            target_entity_name=target_entity_name,
            name=name,
            **data,
        )
