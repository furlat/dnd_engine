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
    body_category: BodyCategory = Field(default="NakedBody")
    skin_tint: int = Field(default=0xDDAA88, ge=0, le=0xFFFFFF)
    head_category: Optional[HeadCategory] = Field(default=None)
    hair_tint: int = Field(default=0, ge=0, le=0xFFFFFF)
    has_beard: bool = Field(default=False)
    beard_tint: int = Field(default=0, ge=0, le=0xFFFFFF)


class Appearance(BaseBlock):
    name: str = Field(default="Appearance")
    body_category: BodyCategory = Field(default="NakedBody")
    skin_tint: int = Field(default=0xDDAA88, ge=0, le=0xFFFFFF)
    head_category: Optional[HeadCategory] = Field(default=None)
    hair_tint: int = Field(default=0, ge=0, le=0xFFFFFF)
    has_beard: bool = Field(default=False)
    beard_tint: int = Field(default=0, ge=0, le=0xFFFFFF)

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
        data = (config or AppearanceConfig()).model_dump()
        return cls(
            source_entity_uuid=source_entity_uuid,
            source_entity_name=source_entity_name,
            target_entity_uuid=target_entity_uuid,
            target_entity_name=target_entity_name,
            name=name,
            **data,
        )
