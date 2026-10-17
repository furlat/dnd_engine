"""One staged area reach: a barrier the area destroys lets it reach further (plan §5.6).

Fireball and the spell payload blasts share this loop. Each stage recomputes
the footprint, resolves the recipients it has not visited yet, and continues
only when one of that stage's own propagation barriers broke. The broken
barriers' destruction lineages become the next stage's prerequisites.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import count
from typing import AbstractSet, FrozenSet, Optional, Set, Tuple
from uuid import UUID

from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.types.world import WorldEdgeChannel

Position = Tuple[int, int]


@dataclass(frozen=True)
class ReachStage:
    """One stage: what the area reaches now and who it has not resolved yet."""

    index: int
    reached: FrozenSet[Position]
    newly_reached: FrozenSet[Position]
    contacts: Mapping[UUID, Position]
    recipients: Tuple[UUID, ...]
    prerequisite_destruction_lineages: Tuple[UUID, ...]


def _propagation_barrier(identity: UUID) -> Optional[BaseItem]:
    item = BaseBlock.get(identity)
    if not isinstance(item, BaseItem):
        return None
    structure = item.get_boundary_structure()
    if item.blocks_propagation() or (structure is not None
            and WorldEdgeChannel.PROPAGATION in structure.blocked_channels):
        return item
    return None


def resolve_staged_area(
    footprint: Callable[[], AbstractSet[Position]],
    recipients: Callable[[FrozenSet[Position], Mapping[UUID, Position]], Iterable[UUID]],
    resolve: Callable[[ReachStage], bool],
    *,
    geometric_positions: AbstractSet[Position],
    origin: Position,
    excluded: AbstractSet[Position] = frozenset(),
) -> FrozenSet[Position]:
    """Resolve an area stage by stage and return every cell it was shown to reach.

    Args:
        footprint: The area's current objective footprint.
        recipients: The stage's recipients, in resolution order, from its reach and contacts.
        resolve: Resolves one stage; returns False to stop the area.
        geometric_positions: The shape's envelope, for object contacts.
        origin: Where the area spreads from.
        excluded: Cells the area touches but is not shown to reach.
    """
    grid = get_map()
    visited: Set[UUID] = set()
    displayed: Set[Position] = set()
    prerequisites: Tuple[UUID, ...] = ()
    for index in count():
        reached = frozenset(footprint())
        contacts = grid.area_object_contacts(reached, geometric_positions=geometric_positions, origin=origin)
        pending = tuple(identity for identity in recipients(reached, contacts) if identity not in visited)
        newly_reached = frozenset(reached - excluded - displayed)
        if index and not newly_reached and not pending:
            break
        barriers = [barrier for identity in contacts if (barrier := _propagation_barrier(identity)) is not None]
        visited.update(pending)
        displayed.update(newly_reached)
        if not resolve(ReachStage(index=index, reached=reached, newly_reached=newly_reached,
                contacts=contacts, recipients=pending, prerequisite_destruction_lineages=prerequisites)):
            break
        prerequisites = tuple(barrier.destruction_lineage_uuid for barrier in barriers
            if barrier.integrity is ItemIntegrity.DESTROYED and barrier.destruction_lineage_uuid is not None)
        if not prerequisites:
            break
    return frozenset(displayed)
