"""Dependency-neutral runtime gateway for authored spatial transitions."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dnd.core.content.identities import ContentRef
from dnd.types.damage import DamageType
from dnd.types.spatial_effects import (
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
)


class SpatialEffectInteractionContext(BaseModel):
    """Exact operation context passed from an event to the transition authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: SpatialEffectInteractionOperation
    positions: tuple[tuple[int, int], ...]
    intensity: SpatialEffectInteractionIntensity
    duration_rounds: int | None = None
    damage_type: DamageType | None = None
    source_object_uuid: UUID | None = None
    source_content_ref: ContentRef | None = None
    parent_event_uuid: UUID


class SpatialEffectInteractionGateway(Protocol):
    """Content-authenticated transition service installed at cold startup."""

    def apply(
        self,
        effect_uuid: UUID,
        context: SpatialEffectInteractionContext,
    ) -> None:
        """Apply one operation to one indexed effect instance."""
        ...


_interaction_gateway: SpatialEffectInteractionGateway | None = None
_interaction_gateway_content_set_digest: str | None = None


def install_spatial_effect_interaction_gateway(
    gateway: SpatialEffectInteractionGateway,
    *,
    content_set_digest: str,
) -> SpatialEffectInteractionGateway:
    """Install one transition authority for the process content generation."""
    global _interaction_gateway
    global _interaction_gateway_content_set_digest

    if _interaction_gateway is None:
        _interaction_gateway = gateway
        _interaction_gateway_content_set_digest = content_set_digest
        return gateway
    if _interaction_gateway_content_set_digest == content_set_digest:
        return _interaction_gateway
    raise RuntimeError(
        "A spatial-effect interaction gateway is already installed for a "
        "different content set",
    )


def apply_spatial_effect_interaction(
    effect_uuid: UUID,
    context: SpatialEffectInteractionContext,
) -> None:
    """Route one exact interaction through the installed transition authority."""
    gateway = _interaction_gateway
    if gateway is None:
        raise RuntimeError("Spatial-effect interaction authority is not installed")
    gateway.apply(effect_uuid, context)


__all__ = [
    "SpatialEffectInteractionContext",
    "SpatialEffectInteractionGateway",
    "apply_spatial_effect_interaction",
    "install_spatial_effect_interaction_gateway",
]
