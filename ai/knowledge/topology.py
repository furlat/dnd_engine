"""Pure spatial queries over session-subjective tile knowledge."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import AbstractSet, Optional, Tuple

from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationTileFact,
    SubjectiveWorldState,
)
from dnd.ai.contracts.semantics import TruthValue
from dnd.core.geometry import supercover_line


Position = Tuple[int, int]


@dataclass(frozen=True)
class KnownLineOfSightWorkspace:
    """Decision-local lookup workspace built from subjective topology only.

    The workspace is derived data, not an alternate world state. It indexes the
    session's current tile facts and visible blocking objects once so a policy
    can evaluate many hypothetical origins without repeatedly scanning or
    string-keying the same subjective materialization.
    """

    tiles_by_position: Mapping[Position, ObservationTileFact]
    vision_blocker_positions: frozenset[Position]
    _cardinal_transition_cache: dict[
        tuple[Position, Position],
        TruthValue,
    ] = field(default_factory=dict, init=False, repr=False, compare=False)
    _diagonal_transition_cache: dict[
        tuple[Position, Position],
        TruthValue,
    ] = field(default_factory=dict, init=False, repr=False, compare=False)

    @classmethod
    def from_world(
        cls,
        world: SubjectiveWorldState,
        *,
        vision_blocker_positions: Optional[AbstractSet[Position]] = None,
    ) -> "KnownLineOfSightWorkspace":
        """Build immutable lookups from one session-subjective world.

        Args:
            world: Canonical materialized world for one observing session.
            vision_blocker_positions: Optional already-derived visible blocker
                positions for the same world revision.

        Returns:
            A lookup workspace containing no facts absent from ``world``.
        """
        blockers = (
            frozenset(vision_blocker_positions)
            if vision_blocker_positions is not None
            else frozenset(
                obj.position
                for obj in world.known_objects.values()
                if obj.knowledge_state is KnowledgeState.VISIBLE
                and obj.position is not None
                and (
                    obj.state.get("blocks_vision") is True
                    or obj.state.get("blocks_vision_field") is True
                )
            )
        )
        return cls(
            tiles_by_position=MappingProxyType({
                tile.position: tile
                for tile in world.known_tiles.values()
            }),
            vision_blocker_positions=blockers,
        )


def grid_distance_feet(origin: Position, target: Position) -> int:
    """Return the engine's floored Euclidean grid distance in feet."""
    tile_distance = int(math.sqrt(
        (origin[0] - target[0]) ** 2
        + (origin[1] - target[1]) ** 2
    ))
    return tile_distance * 5


def known_line_of_sight(
    world: SubjectiveWorldState,
    origin: Position,
    target: Position,
    *,
    vision_blocker_positions: Optional[AbstractSet[Position]] = None,
    workspace: Optional[KnownLineOfSightWorkspace] = None,
) -> TruthValue:
    """Evaluate a line using only currently known directional vision facts.

    Unknown cells or absent directional facts propagate `UNKNOWN`; they are never
    treated as clear. A known blocked transition returns `FALSE`.
    """
    if workspace is not None and vision_blocker_positions is not None:
        raise ValueError(
            "pass either a line-of-sight workspace or blocker positions, not both"
        )
    topology = workspace or KnownLineOfSightWorkspace.from_world(
        world,
        vision_blocker_positions=vision_blocker_positions,
    )
    path = supercover_line(origin, target)
    if not path:
        return TruthValue.FALSE
    for position in path[1:-1]:
        if position in topology.vision_blocker_positions:
            return TruthValue.FALSE

    unknown = False
    for previous, current in zip(path, path[1:]):
        result = (
            _known_diagonal_transition(
                topology,
                previous,
                current,
            )
            if _is_diagonal(previous, current)
            else _known_cardinal_transition(topology, previous, current)
        )
        if result is TruthValue.FALSE:
            return TruthValue.FALSE
        if result is TruthValue.UNKNOWN:
            unknown = True
    return TruthValue.UNKNOWN if unknown else TruthValue.TRUE


def _known_cardinal_transition(
    workspace: KnownLineOfSightWorkspace,
    origin: Position,
    target: Position,
) -> TruthValue:
    """Evaluate one cardinal transition from current visible tile facts."""
    cache_key = (origin, target)
    cached = workspace._cardinal_transition_cache.get(cache_key)
    if cached is not None:
        return cached
    origin_tile = workspace.tiles_by_position.get(origin)
    target_tile = workspace.tiles_by_position.get(target)
    if (
        origin_tile is None
        or target_tile is None
        or origin_tile.knowledge_state is not KnowledgeState.VISIBLE
        or target_tile.knowledge_state is not KnowledgeState.VISIBLE
    ):
        result = TruthValue.UNKNOWN
        workspace._cardinal_transition_cache[cache_key] = result
        workspace._cardinal_transition_cache[(target, origin)] = result
        return result
    origin_direction, target_direction = _cardinal_directions(origin, target)
    origin_result = _known_direction_open(
        origin_tile.directional_blocks_vision,
        origin_direction,
    )
    target_result = _known_direction_open(
        target_tile.directional_blocks_vision,
        target_direction,
    )
    if origin_result is TruthValue.FALSE or target_result is TruthValue.FALSE:
        result = TruthValue.FALSE
    elif origin_result is TruthValue.UNKNOWN or target_result is TruthValue.UNKNOWN:
        result = TruthValue.UNKNOWN
    else:
        result = TruthValue.TRUE
    workspace._cardinal_transition_cache[cache_key] = result
    workspace._cardinal_transition_cache[(target, origin)] = result
    return result


def _known_diagonal_transition(
    workspace: KnownLineOfSightWorkspace,
    origin: Position,
    target: Position,
) -> TruthValue:
    """Mirror the engine's either-bridge diagonal vision rule subjectively."""
    cache_key = (origin, target)
    cached = workspace._diagonal_transition_cache.get(cache_key)
    if cached is not None:
        return cached
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    bridges = ((origin[0] + dx, origin[1]), (origin[0], origin[1] + dy))
    unknown = False
    for bridge in bridges:
        if bridge in workspace.vision_blocker_positions:
            continue
        first = _known_cardinal_transition(workspace, origin, bridge)
        second = _known_cardinal_transition(workspace, bridge, target)
        if first is TruthValue.TRUE and second is TruthValue.TRUE:
            result = TruthValue.TRUE
            workspace._diagonal_transition_cache[cache_key] = result
            workspace._diagonal_transition_cache[(target, origin)] = result
            return result
        if first is not TruthValue.FALSE and second is not TruthValue.FALSE:
            unknown = True
    result = TruthValue.UNKNOWN if unknown else TruthValue.FALSE
    workspace._diagonal_transition_cache[cache_key] = result
    workspace._diagonal_transition_cache[(target, origin)] = result
    return result


def _is_diagonal(origin: Position, target: Position) -> bool:
    """Return whether adjacent positions differ on both axes."""
    return abs(target[0] - origin[0]) == 1 and abs(target[1] - origin[1]) == 1


def _known_direction_open(
    blockers: dict[str, bool],
    direction: str,
) -> TruthValue:
    """Return whether one touched side has an explicit open fact."""
    value = blockers.get(direction)
    if value is True:
        return TruthValue.FALSE
    if value is None:
        return TruthValue.UNKNOWN
    return TruthValue.TRUE


def _cardinal_directions(origin: Position, target: Position) -> tuple[str, str]:
    """Return opposing tile-relative sides for one cardinal transition."""
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    if dx > 0:
        return "east", "west"
    if dx < 0:
        return "west", "east"
    if dy > 0:
        return "north", "south"
    if dy < 0:
        return "south", "north"
    raise ValueError("cardinal transition requires distinct adjacent positions")
