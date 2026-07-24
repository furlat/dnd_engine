"""Deterministic construction of frame-closed subjective presentation graphs.

The engine event tree contains technical lifecycle nodes that are not part of
the player presentation contract.  Event interpretation therefore happens in
``mapper.py`` and supplies only the safe semantic nodes that survived
projection.  This module assigns projection-native identities after that
filtering, validates the resulting parent/child graph, and materializes cues in
parent-before-child order.

No engine object or source lineage is exposed by this layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Optional

from server.player_replication_contract import SubjectivePresentationCue


class PresentationGraphError(ValueError):
    """Raised when safe presentation drafts do not form one closed forest."""


@dataclass(frozen=True)
class PresentationNodeCoordinates:
    """Final graph coordinates supplied to one typed cue factory."""

    presentation_cursor: int
    presentation_id: str
    parent_presentation_id: Optional[str]
    child_presentation_ids: tuple[str, ...]
    presentation_ids_by_key: Mapping[str, str]


PresentationCueFactory = Callable[[PresentationNodeCoordinates], SubjectivePresentationCue]


@dataclass(frozen=True)
class PresentationNodeDraft:
    """One already-authorized semantic node awaiting stable graph identity."""

    key: str
    parent_key: Optional[str]
    order_key: tuple[int, ...]
    factory: PresentationCueFactory

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("presentation draft key must not be empty")
        if not self.order_key:
            raise ValueError("presentation draft order key must not be empty")
        if self.parent_key == self.key:
            raise ValueError("presentation draft cannot parent itself")


def materialize_presentation_graph(
    drafts: tuple[PresentationNodeDraft, ...],
    *,
    perspective_epoch_id: str,
    observation_cursor: int,
    presentation_from_cursor: int,
) -> tuple[SubjectivePresentationCue, ...]:
    """Assign deterministic IDs and materialize one closed semantic forest.

    IDs are local to the immutable perspective epoch and observation frame.
    They deliberately do not contain raw engine lineage UUIDs.  A depth-first
    traversal gives every parent a lower presentation cursor than its children;
    sibling order is the mapper's explicit semantic order.
    """
    if not perspective_epoch_id:
        raise ValueError("perspective epoch must not be empty")
    if observation_cursor < 1:
        raise ValueError("observation cursor must be positive")
    if presentation_from_cursor < 0:
        raise ValueError("presentation cursor boundary must be nonnegative")

    by_key: dict[str, PresentationNodeDraft] = {}
    for draft in drafts:
        if draft.key in by_key:
            raise PresentationGraphError(f"duplicate presentation draft key: {draft.key}")
        by_key[draft.key] = draft

    children_by_parent: dict[str, list[PresentationNodeDraft]] = {
        key: [] for key in by_key
    }
    roots: list[PresentationNodeDraft] = []
    for draft in drafts:
        if draft.parent_key is None:
            roots.append(draft)
            continue
        if draft.parent_key not in by_key:
            raise PresentationGraphError(
                f"presentation parent is absent after projection: {draft.parent_key}"
            )
        children_by_parent[draft.parent_key].append(draft)

    roots.sort(key=_draft_sort_key)
    for children in children_by_parent.values():
        children.sort(key=_draft_sort_key)

    ordered: list[PresentationNodeDraft] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(draft: PresentationNodeDraft) -> None:
        if draft.key in visiting:
            raise PresentationGraphError("presentation graph contains a cycle")
        if draft.key in visited:
            return
        visiting.add(draft.key)
        ordered.append(draft)
        for child in children_by_parent[draft.key]:
            visit(child)
        visiting.remove(draft.key)
        visited.add(draft.key)

    for root in roots:
        visit(root)
    if len(visited) != len(drafts):
        raise PresentationGraphError("presentation graph has no reachable root")

    ids_by_key = {
        draft.key: (
            f"{perspective_epoch_id}:{observation_cursor}:{ordinal}"
        )
        for ordinal, draft in enumerate(ordered, start=1)
    }

    cues: list[SubjectivePresentationCue] = []
    for ordinal, draft in enumerate(ordered, start=1):
        parent_id = (
            ids_by_key[draft.parent_key]
            if draft.parent_key is not None
            else None
        )
        child_ids = tuple(
            ids_by_key[child.key]
            for child in children_by_parent[draft.key]
        )
        coordinates = PresentationNodeCoordinates(
            presentation_cursor=presentation_from_cursor + ordinal,
            presentation_id=ids_by_key[draft.key],
            parent_presentation_id=parent_id,
            child_presentation_ids=child_ids,
            presentation_ids_by_key=ids_by_key,
        )
        cue = draft.factory(coordinates)
        if (
            cue.presentation_cursor != coordinates.presentation_cursor
            or cue.presentation_id != coordinates.presentation_id
            or cue.parent_presentation_id != coordinates.parent_presentation_id
            or cue.child_presentation_ids != coordinates.child_presentation_ids
        ):
            raise PresentationGraphError(
                f"presentation factory changed assigned graph coordinates: {draft.key}"
            )
        cues.append(cue)
    return tuple(cues)


def _draft_sort_key(draft: PresentationNodeDraft) -> tuple[tuple[int, ...], str]:
    """Return a total deterministic ordering for roots and siblings."""
    return draft.order_key, draft.key


__all__ = [
    "PresentationCueFactory",
    "PresentationGraphError",
    "PresentationNodeCoordinates",
    "PresentationNodeDraft",
    "materialize_presentation_graph",
]
