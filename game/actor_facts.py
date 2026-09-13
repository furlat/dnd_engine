"""Passive retained actor and world records shared by capture and presentation."""

from dataclasses import dataclass, field
from uuid import UUID

from dnd.core.events import WorldInitializedEvent, WorldObjectState, WorldTileState
from dnd.core.item_types import ItemPresentationState
from dnd.types.senses import SensesSnapshot
from dnd.types.actor_facts import ActorState as ActorState, ConditionFact as ConditionFact
from dnd.types.world_placement import WorldObjectPlacement


@dataclass(slots=True)
class PresentationTarget:
    """Read-optimized indexes over detached engine values."""

    generation: UUID
    observer_uuid: UUID
    world: WorldInitializedEvent | None = None
    tiles: dict[tuple[int, int], WorldTileState] = field(default_factory=dict)
    objects: dict[UUID, WorldObjectState] = field(default_factory=dict)
    door_uuid: UUID | None = None
    door_placement: WorldObjectPlacement | None = None
    door_is_open: bool | None = None
    standing_torch_uuid: UUID | None = None
    standing_torch_state: ItemPresentationState | None = None
    senses: SensesSnapshot | None = None
    reducer_cursor: int = 0
    actors: dict[UUID, ActorState] = field(default_factory=dict)
    current_actor_uuid: UUID | None = None
    round_number: int = 0
