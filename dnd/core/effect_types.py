"""Dependency-neutral provenance contracts for applied game effects."""

from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


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
    ) -> "EffectOrigin":
        """Create explicit spell provenance from a spell event payload."""
        return cls(
            kind=EffectOriginKind.SPELL,
            source_id=source_id,
            source_event_lineage_uuid=source_event_lineage_uuid,
            source_position=source_position,
            base_spell_level=base_spell_level,
            effective_spell_level=effective_spell_level,
        )
