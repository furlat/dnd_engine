"""A spatial transition's commit order, kept the same way by the projector and the client fold.

A seat's projection and its client both record, per entity, the version that committed its last spatial
transition, so an outer move never undoes a nested arrival. Both import this leaf; neither imports the other.
"""

from collections.abc import Collection
from uuid import UUID

from dnd.player.facts import PlayerFact, SpatialFact
from dnd.types.event_facts import SpatialChangeType


def commit_current(cursors: dict[UUID, int], fact: PlayerFact, *, source_cursor: int,
                   occurrences: Collection[int]) -> bool:
    """Record a spatial transition's commit in `cursors` (by entity); False if a nested commit supersedes it (it
    is then not folded)."""
    if (isinstance(fact, SpatialFact) and fact.entity_uuid is not None
            and fact.change_type in (SpatialChangeType.ENTITY_ENTERED, SpatialChangeType.ENTITY_LEFT)):
        if fact.commit_occurrence is None or fact.commit_occurrence not in occurrences:
            raise ValueError(f"Spatial change at cursor {source_cursor} lacks its recorded commit version")
        committed_at = fact.commit_occurrence
        # Only a nested commit supersedes this closing transition. Independent
        # earlier transitions may be retimed (e.g. jump after preflight OAs).
        if committed_at < cursors.get(fact.entity_uuid, -1) < source_cursor:
            return False
        cursors[fact.entity_uuid] = committed_at
    return True
