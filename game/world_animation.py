"""Finite world-state transitions sampled on the existing historical clock."""

from dataclasses import dataclass
from math import hypot
from types import MappingProxyType
from typing import Literal, Mapping, Sequence
from uuid import UUID

from dnd.types.world import CardinalDirection
from dnd.types.senses import PerceivedSpatialEffect
from dnd.core.presentation_geometry import CylinderPresentationGeometry, SpherePresentationGeometry
from game.player_facts import PlayerState, WorldUpdate
from game.animation_types import HitFlash, MechanismProjectileArt, PropAnimation, PropDepth, SaveHop, SurfaceReveal
from game.device_art import DeviceFacing
from game.mechanism_projectile import MechanismProjectileCue
from game.environment_art import load_environment_art


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
    projectile = row.get("projectile")
    hop = row.get("successful_save_hop")
    depth = row.get("actor_depth")
    media = None if projectile is None else MechanismProjectileArt(
        MappingProxyType({pose: tuple(frames) for pose, frames in projectile["frames_by_pose"].items()}),
        MappingProxyType({pose: tuple(tuple(point) for point in points)
                          for pose, points in projectile["tip_offsets_by_pose"].items()}),
        MappingProxyType({pose: tuple(point) for pose, point in projectile["muzzle_offsets_by_pose"].items()}),
        projectile["muzzle_height_steps"], projectile["speed_tiles_per_second"],
    )
    return PropAnimation(MappingProxyType({pose: tuple(frames)
        for pose, frames in row["frames_by_pose"].items()}), row["fps"], MappingProxyType(row["state_frames"]),
        row.get("default_frame", 0), row.get("placement", "cell"),
        tuple(row.get("origin_offset", (0, 0))), row.get("creation_start_frame"),
        tuple(row["footprint_tiles"]) if "footprint_tiles" in row else None,
        tuple(row.get("activation_frames", ())), row.get("contact_frame"),
        MappingProxyType({key: tuple(frames)
                         for key, frames in row.get("transition_frames", {}).items()}), media,
        row.get("depth", "ground"), None if hop is None else SaveHop(
            hop["effect_id"], hop["body_clip"], hop["duration_ms"], hop["height_px"]),
        None if depth is None else PropDepth(depth["asset_id"], tuple(depth["cell"]),
            MappingProxyType(depth["rows_by_pose"]), tuple(depth["depth_range"]),
            MappingProxyType(depth["pixels_per_unit_by_pose"])))


@dataclass(frozen=True, slots=True)
class DestructionContact:
    """Small witnessed contact; authored rasters stay in the media catalog."""

    item_id: str
    position: tuple[int, int]
    elevation_steps: float
    facing: DeviceFacing
    pitch_degrees: float
    body_uuid: UUID
    duration_ms: float
    bank_id: str | None = None


@dataclass(frozen=True, slots=True)
class SpatialMediaMotion:
    """One witnessed same-owner field displacement, on its existing action head."""

    before: PerceivedSpatialEffect
    after: PerceivedSpatialEffect
    duration_ms: float


def bind_spatial_media_motion(before: PerceivedSpatialEffect, after: PerceivedSpatialEffect,
                              speed: float) -> SpatialMediaMotion | None:
    """Only disclosed old/new geometry can provide a moving field's endpoints."""
    old, new = before.area_geometry, after.area_geometry
    if old is None or new is None:
        return None
    start = old.center if isinstance(old, (SpherePresentationGeometry, CylinderPresentationGeometry)) else old.origin
    end = new.center if isinstance(new, (SpherePresentationGeometry, CylinderPresentationGeometry)) else new.origin
    distance = hypot(end[0] - start[0], end[1] - start[1])
    return SpatialMediaMotion(before, after, distance * 1000 / speed) if distance else None


@dataclass(frozen=True, slots=True)
class WorldTransition:
    identity: UUID
    field: Literal["is_open", "is_engaged", "trap_state", "pressed", "activation", "creation", "removal", "destruction", "hit_flash", "spatial_motion"]
    previous: str | None
    current: str | None
    start_ms: float
    destruction: DestructionContact | None = None
    hit_flash: HitFlash | None = None
    duration_ms: float | None = None
    projectile: MechanismProjectileCue | None = None
    spatial_motion: SpatialMediaMotion | None = None


@dataclass(frozen=True, slots=True)
class WorldTransitionSample:
    transition: WorldTransition
    elapsed_ms: float


def world_transition_end(change: WorldTransition, state: PlayerState,
                         animations: Mapping[str, PropAnimation]) -> float:
    """Join finite prop motion to the existing head, even without an actor cue."""
    if change.duration_ms is not None:
        return change.start_ms + change.duration_ms
    if change.field == "removal":
        return change.start_ms
    if change.destruction is not None:
        return change.start_ms + change.destruction.duration_ms
    if change.hit_flash is not None:
        return change.start_ms + change.hit_flash.durationMs
    if change.field in ("trap_state", "pressed", "activation", "creation"):
        effect = state.senses.spatial_effects.get(change.identity) if state.senses is not None else None
        identity = effect.content_ref.content_id if effect is not None else None
    else:
        obj = state.objects.get(change.identity)
        identity = obj.item.item_id if obj is not None else None
        if change.field == "is_open" and obj is not None:
            door = load_environment_art().doors.get(obj.item.item_id)
            if door is not None and obj.item.door_swing is not None:
                return change.start_ms + door.openings[obj.item.door_swing.value].duration_ms
    animation = animations.get(identity) if identity is not None else None
    if animation is None:
        return change.start_ms
    if change.field == "activation":
        return change.start_ms + len(animation.activation_frames) * 1000 / animation.fps
    if change.field == "creation":
        if animation.creation_start_frame is None:
            return change.start_ms
        frames = abs(animation.default_frame - animation.creation_start_frame)
    else:
        assert change.current is not None and change.previous is not None
        sequence = animation.transition_frames.get(f"{change.previous}:{change.current}", ())
        frames = len(sequence) if sequence else abs(animation.state_frames[change.current] - animation.state_frames[change.previous])
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
    """Sample reached changes, or hold the first recorded prior state until contact."""
    selected = {}
    for change in changes:
        key = change.identity, change.field
        if elapsed_ms >= change.start_ms:
            selected[key] = WorldTransitionSample(change, elapsed_ms - change.start_ms)
        elif (key not in selected and change.previous is not None
                and change.field in ("is_open", "is_engaged", "trap_state", "pressed")):
            # A newly received snapshot may already contain the resulting
            # state. The explicit transition supplies its authorized old pose;
            # activation pulses and unobserved prior values supply none.
            selected[key] = WorldTransitionSample(change, elapsed_ms - change.start_ms)
    return tuple(selected.values())


def merge_world_transitions(*groups: Sequence[WorldTransition]) -> tuple[WorldTransition, ...]:
    """A settled parent snapshot must not replay a child's completed change."""
    result = []
    values = {}
    for change in sorted((row for group in groups for row in group), key=lambda row: row.start_ms):
        key = change.identity, change.field
        if change.field == "activation" or change.hit_flash is not None or key not in values or values[key] != change.current:
            result.append(change)
            values[key] = change.current
    return tuple(result)
