"""Directly Tile-owned condition models retained for authored content."""

from typing import List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_conditions import BaseCondition
from dnd.core.base_tiles import Tile
from dnd.core.condition_types import ConditionCategory, HazardFilter
from dnd.core.events import Event, EventPhase
from dnd.core.gridmap import get_map


class TileEffectCondition(BaseCondition):
    """Base condition applied directly to one Tile."""

    name: str = Field(default="Tile Effect")
    description: str = Field(default="A condition owned by one tile")

    model_config = {"arbitrary_types_allowed": True}

    def get_tile(self) -> Optional[Tile]:
        """Return the authoritative Tile owner, if it still exists."""
        if self.target_entity_uuid is None:
            return None
        return get_map().get_tile_by_uuid(self.target_entity_uuid)

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        """Apply no extra mechanics beyond the ordinary condition record."""
        return (
            [],
            [],
            [],
            [],
            declaration_event.phase_to(
                EventPhase.EFFECT,
                update={"condition": self},
            ),
        )


class ZoneMarkerCondition(TileEffectCondition):
    """Legacy authored Tile marker retained for content recovery."""

    condition_category: ConditionCategory = ConditionCategory.CONDITION


class SpikeTrapCondition(TileEffectCondition):
    """Legacy authored spike-trap Tile record retained for content recovery."""

    name: str = Field(default="Spike Trap")
    description: str = Field(
        default="Sharp spikes deal damage when stepped on",
    )
    hazard_filter: HazardFilter = Field(default=HazardFilter.ALL)
    condition_category: ConditionCategory = ConditionCategory.CONDITION
