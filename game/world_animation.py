"""Finite world-state transitions sampled on the existing historical clock."""

from dataclasses import dataclass
from math import hypot
from types import MappingProxyType
from typing import Literal, Mapping, Sequence
from uuid import UUID

from dnd.types.world import CardinalDirection
from game.player_facts import PlayerState, WorldUpdate
from game.animation_types import PropAnimation, SurfaceReveal


def surface_reveal_delay(update: WorldUpdate, before: PlayerState, reveal: SurfaceReveal,
                         origin: tuple[float, float], elevation: float) -> float:
    """Time received surface changes once; grouped after-values remain atomic.

    Existing marks stay in the prior state until their update is reached. Compare
    full residue values so adding a wall face works even with the same membership.
    """
    positions: list[tuple[float, float, float]] = []
    for tile in update.tiles:
        old = before.tiles.get(tile.position)
        previous = tuple(row for row in old.residues if row.residue_id in reveal.residueIds) if old else ()
        current = tuple(row for row in tile.residues if row.residue_id in reveal.residueIds)
        if current != previous:
            positions.append((*tile.position, tile.elevation_steps))
    for obj in update.objects:
        old = before.objects.get(obj.item.item_uuid)
        previous = tuple(row for row in old.item.surface_residues if row.residue_id in reveal.residueIds) if old else ()
        current = tuple(row for row in obj.item.surface_residues if row.residue_id in reveal.residueIds)
        if current != previous:
            x, y = obj.placement.position
            dx, dy = {CardinalDirection.EAST: (.5, 0), CardinalDirection.WEST: (-.5, 0),
                      CardinalDirection.NORTH: (0, .5), CardinalDirection.SOUTH: (0, -.5),
                      None: (0, 0)}[obj.placement.boundary_direction]
            positions.append((x + dx, y + dy, obj.placement.base_height_steps))
    distance = min((hypot(x - origin[0], y - origin[1], height - elevation)
                    for x, y, height in positions), default=0)
    return distance * 1000 / reveal.speedTilesPerSecond


def prop_animation(row: dict) -> PropAnimation:
    """Decode the same authored poses for timeline binding and raster drawing."""
    return PropAnimation(MappingProxyType({pose: tuple(frames)
        for pose, frames in row["frames_by_pose"].items()}), row["fps"], MappingProxyType(row["state_frames"]))


@dataclass(frozen=True, slots=True)
class WorldTransition:
    identity: UUID
    field: Literal["is_open", "is_engaged", "trap_state"]
    previous: str
    current: str
    start_ms: float


@dataclass(frozen=True, slots=True)
class WorldTransitionSample:
    transition: WorldTransition
    elapsed_ms: float


def world_transition_end(change: WorldTransition, state: PlayerState,
                         animations: Mapping[str, PropAnimation]) -> float:
    """Join finite prop motion to the existing head, even without an actor cue."""
    if change.field == "trap_state":
        effect = state.senses.spatial_effects.get(change.identity) if state.senses is not None else None
        identity = effect.content_ref.content_id if effect is not None else None
    else:
        obj = state.objects.get(change.identity)
        identity = obj.item.item_id if obj is not None else None
    animation = animations.get(identity) if identity is not None else None
    if animation is None:
        return change.start_ms
    frames = abs(animation.state_frames[change.current] - animation.state_frames[change.previous])
    return change.start_ms + frames * 1000 / animation.fps


def world_transitions(before: PlayerState, states: Sequence[tuple[float, PlayerState]]) -> tuple[WorldTransition, ...]:
    """Compile changed received values once; acquisition alone has no motion."""
    changes: list[WorldTransition] = []
    previous = before
    for at, current in states:
        for identity, obj in current.objects.items():
            old = previous.objects.get(identity)
            if old is None:
                continue
            fields: tuple[tuple[Literal["is_open", "is_engaged"], bool | None, bool | None], ...] = (
                ("is_open", old.item.is_open, obj.item.is_open),
                ("is_engaged", old.item.is_engaged, obj.item.is_engaged),
            )
            for field, start, end in fields:
                if start is not None and end is not None and start != end:
                    changes.append(WorldTransition(identity, field, str(start).lower(), str(end).lower(), at))
        previous = current
    return tuple(changes)


def sample_world_transitions(changes: Sequence[WorldTransition], elapsed_ms: float) -> tuple[WorldTransitionSample, ...]:
    """Select each field's latest reached change without consuming state."""
    selected = {}
    for change in changes:
        if elapsed_ms >= change.start_ms:
            selected[change.identity, change.field] = WorldTransitionSample(change, elapsed_ms - change.start_ms)
    return tuple(selected.values())


def merge_world_transitions(*groups: Sequence[WorldTransition]) -> tuple[WorldTransition, ...]:
    """A settled parent snapshot must not replay a child's completed change."""
    result = []
    values = {}
    for change in sorted((row for group in groups for row in group), key=lambda row: row.start_ms):
        key = change.identity, change.field
        if values.get(key) != change.current:
            result.append(change)
            values[key] = change.current
    return tuple(result)
