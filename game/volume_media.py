"""Registered surface samples in the existing world painter.

This composes observed geometry, never spell eligibility. Native suppression
facts supply excluded volumes; finite walls supply visibility and occlusion.
"""

from dataclasses import dataclass
from functools import lru_cache
from math import sqrt
from typing import Literal

import numpy as np
import pygame

from dnd.types.world_placement import WorldObjectPlacement
from dnd.core.events import WorldTileState
from dnd.core.world_edges import SlopeAxis, progressive_elevation_transition
from game.area_media import AreaSolid, BoundarySprite, boundary_segment
from game.projection import Camera, inverse_rotate_position, project_world


@dataclass(frozen=True, slots=True)
class ExcludedSphere:
    provider: str
    center: tuple[float, float]
    elevation: float
    radius: float
    vertical_scale: float


@dataclass(frozen=True, slots=True)
class SurfaceVolume:
    center: tuple[float, float]
    elevation: float
    radius: float
    positions: np.ndarray
    ownership: np.ndarray
    vertical_scale: float
    boundaries: tuple[WorldObjectPlacement, ...] = ()
    exclusions: tuple[ExcludedSphere, ...] = ()
    solids: tuple[AreaSolid, ...] = ()
    supports: tuple[WorldTileState, ...] = ()
    propagation: Literal["line_of_effect", "connected"] = "connected"
    admitted: tuple[tuple[int, int], ...] | None = None
    # Camera-local XY/Z displacement after resolving an authored rig attachment.
    # Y is host elevation steps; the propagation origin remains authoritative.
    translation: tuple[float, float, float] = (0, 0, 0)


@lru_cache(maxsize=32)
def _support_field(facts):
    """Small historical height field; missing cells stay unknown."""
    x0, z0 = min(row[0] for row in facts), min(row[1] for row in facts)
    shape = max(row[0] for row in facts)-x0+1, max(row[1] for row in facts)-z0+1
    heights = np.full(shape, np.nan, dtype=np.float32)
    gradients = np.zeros((*shape, 4), dtype=np.float32)
    cells = {(x, z): (height, kind, axis) for x, z, height, kind, axis in facts}
    for (x, z), (height, kind, axis) in cells.items():
        heights[x-x0, z-z0] = height
        for index, (dx, dz, slope) in enumerate(((1, 0, SlopeAxis.EAST_WEST),
                (-1, 0, SlopeAxis.EAST_WEST), (0, 1, SlopeAxis.NORTH_SOUTH),
                (0, -1, SlopeAxis.NORTH_SOUTH))):
            neighbor = cells.get((x+dx, z+dz))
            if neighbor is not None and progressive_elevation_transition(height, kind, axis, *neighbor, slope):
                gradients[x-x0, z-z0, index] = neighbor[0]-height
    return x0, z0, heights, gradients


def observed_support_heights(x: np.ndarray, z: np.ndarray, supports: tuple[WorldTileState, ...]) -> np.ndarray:
    """Sample only disclosed supports, including their compatible progressive edges."""
    x0, z0, heights, gradients = _support_field(tuple((tile.position[0], tile.position[1],
        tile.elevation_steps, tile.surface_kind, tile.slope_axis) for tile in supports))
    cx, cz = np.floor(x+.5).astype(np.int32), np.floor(z+.5).astype(np.int32)
    ix, iz = cx-x0, cz-z0
    inside = (ix >= 0) & (iz >= 0) & (ix < heights.shape[0]) & (iz < heights.shape[1])
    ix, iz = np.clip(ix, 0, heights.shape[0]-1), np.clip(iz, 0, heights.shape[1]-1)
    dx, dz = x-cx, z-cz
    gx = gradients[ix, iz, np.where(dx >= 0, 0, 1)]
    gz = gradients[ix, iz, np.where(dz >= 0, 2, 3)]
    return np.where(inside, heights[ix, iz] + gx*abs(dx) + gz*abs(dz), np.nan)


@lru_cache(maxsize=32)
def _barriers(boundaries: tuple[WorldObjectPlacement, ...], solids: tuple[AreaSolid, ...]):
    """Physical planes from received edge structures and solid support outlines."""
    result = []
    for wall in boundaries:
        a, b = boundary_segment(wall)
        axis = 0 if a[0] == b[0] else 1
        low, high = sorted((a[1-axis], b[1-axis]))
        result.append((axis, a[axis], low, high, wall.base_height_steps, wall.top_height_steps))
    for solid in solids:
        x, z = solid.position
        for axis, plane, low, high in ((0, x-.5, z-.5, z+.5), (0, x+.5, z-.5, z+.5),
                                       (1, z-.5, x-.5, x+.5), (1, z+.5, x-.5, x+.5)):
            result.append((axis, plane, low, high, solid.base_height_steps, solid.top_height_steps))
    return tuple(result)


@lru_cache(maxsize=32)
def _segments(barriers, elevation: float):
    """Merge collinear contacts so a long wall has two visibility corners."""
    groups: dict[tuple[int, float], list[tuple[float, float]]] = {}
    for axis, plane, low, high, bottom, top in barriers:
        if elevation < bottom or top is not None and elevation >= top:
            continue
        groups.setdefault((axis, plane), []).append((low, high))
    segments = []
    for (axis, plane), intervals in groups.items():
        start, stop = sorted(intervals)[0]
        for low, high in sorted(intervals)[1:]:
            if low <= stop:
                stop = max(stop, high)
            else:
                segments.append((axis, plane, start, stop))
                start, stop = low, high
        segments.append((axis, plane, start, stop))
    return tuple(segments)


def _visible_from(origin, x, z, segments):
    clear = np.ones(np.shape(x), dtype=bool)
    for axis, plane, low, high in segments:
        end, cross = (x, z) if axis == 0 else (z, x)
        delta = end - origin[axis]
        t = np.divide(plane - origin[axis], delta, out=np.full(np.shape(delta), -1., dtype=float),
                      where=np.abs(delta) > 1e-8)
        along = origin[1-axis] + t * (cross - origin[1-axis])
        clear &= ~((t > 1e-7) & (t < 1 - 1e-7) & (along >= low) & (along <= high))
    return clear


@lru_cache(maxsize=32)
def _visibility_origins(center, radius, segments):
    """Continuous corner visibility within the authored radius, not a cell stencil."""
    candidates = set()
    epsilon = 1e-4
    for axis, plane, low, high in segments:
        for end in (low, high):
            for across in (-epsilon, epsilon):
                for along in (-epsilon, epsilon):
                    p = (plane + across, end + along) if axis == 0 else (end + along, plane + across)
                    if sum((p[i] - center[i]) ** 2 for i in (0, 1)) <= radius ** 2:
                        candidates.add(p)
    found = [center]
    for origin in found:
        reached = [p for p in sorted(candidates) if _visible_from(origin, np.array(p[0]), np.array(p[1]), segments)]
        found.extend(reached)
        candidates.difference_update(reached)
    return tuple(found)


def _visual_boundary_coverage(keep: np.ndarray, depth: np.ndarray, x: np.ndarray, z: np.ndarray,
                              destination: tuple[int, int], boundaries: tuple[BoundarySprite, ...],
                              vx: float, vz: float) -> None:
    """Occlude samples behind finite registered boundary billboards.

    The picture owns the visual cap/holes, while the received segment owns its
    world depth. A foreground sample may overlap that picture without being
    hidden. This is a billboard registration, not a reconstructed wall volume.
    """
    # Adjacent sprites overlap across their cell seam. Their visible cap must
    # share the connected finite edge, rather than reopen one-pixel cracks when
    # a camera ray crosses the neighboring cell's part of that same edge.
    edges: dict[tuple[int, float, float, float | None], list[tuple[float, float]]] = {}
    for boundary in boundaries:
        for wall in boundary.placements:
            first, last = boundary_segment(wall)
            axis = 0 if first[0] == last[0] else 1
            key = axis, first[axis], wall.base_height_steps, wall.top_height_steps
            low, high = sorted((first[1-axis], last[1-axis]))
            edges.setdefault(key, []).append((low, high))
    for key, intervals in edges.items():
        merged: list[tuple[float, float]] = []
        for low, high in sorted(intervals):
            if merged and low <= merged[-1][1]:
                merged[-1] = merged[-1][0], max(merged[-1][1], high)
            else:
                merged.append((low, high))
        edges[key] = merged
    picture = pygame.Rect(destination, keep.shape)
    for boundary in boundaries:
        overlap = picture.clip(boundary.image.get_rect(topleft=boundary.destination))
        if not overlap:
            continue
        local = overlap.move(-destination[0], -destination[1])
        wall_local = overlap.move(-boundary.destination[0], -boundary.destination[1])
        opacity = pygame.surfarray.array_alpha(boundary.image.subsurface(wall_local))
        selection = np.s_[local.left:local.right, local.top:local.bottom]
        px, pz = x[selection], z[selection]
        behind = np.zeros(opacity.shape, dtype=bool)
        for wall in boundary.placements:
            first, last = boundary_segment(wall)
            axis = 0 if first[0] == last[0] else 1
            own_low, own_high = sorted((first[1-axis], last[1-axis]))
            low, high = next((low, high) for low, high in edges[
                axis, first[axis], wall.base_height_steps, wall.top_height_steps]
                if low <= own_low and high >= own_high)
            component, other, direction, cross_direction = ((px, pz, vx, vz)
                if axis == 0 else (pz, px, vz, vx))
            crossing_time = (first[axis] - component) / direction
            along = other + crossing_time * cross_direction
            behind |= (crossing_time > 1e-5) & (along >= low) & (along <= high)
        keep[selection] &= ~(behind & (opacity == 255))
        # Translucent edge pixels still composite normally over the sample.
        # Put that contribution behind the boundary instead of flattening alpha.
        depth[selection] = np.where(behind & (opacity > 0),
            np.minimum(depth[selection], np.nextafter(boundary.key[1], -np.inf)), depth[selection])


def compose_volume(image: pygame.Surface, volume: SurfaceVolume, camera: Camera, *,
                   destination: tuple[int, int] = (0, 0),
                   visual_boundaries: tuple[BoundarySprite, ...] | None = None,
                   ) -> tuple[pygame.Surface, np.ndarray]:
    """Return masked color plus ground depths for the shared painter splitter."""
    local = volume.positions
    rotated_origin = inverse_rotate_position((0., 0.), camera.quadrant)
    end_x = inverse_rotate_position((1., 0.), camera.quadrant)
    end_z = inverse_rotate_position((0., 1.), camera.quadrant)
    axis_x = end_x[0] - rotated_origin[0], end_x[1] - rotated_origin[1]
    axis_z = end_z[0] - rotated_origin[0], end_z[1] - rotated_origin[1]
    x = local[:, :, 0] * axis_x[0] + local[:, :, 2] * axis_z[0]
    z = local[:, :, 0] * axis_x[1] + local[:, :, 2] * axis_z[1]
    dx, dh, dz = volume.translation
    x += volume.center[0] + dx*axis_x[0] + dz*axis_z[0]
    z += volume.center[1] + dx*axis_x[1] + dz*axis_z[1]
    height = local[:, :, 1] * volume.vertical_scale + volume.elevation + dh
    owned = volume.ownership != 0
    keep = np.ones(owned.shape, dtype=bool)
    barriers = _barriers(volume.boundaries, volume.solids)
    segments = _segments(_barriers(volume.boundaries, tuple(solid for solid in volume.solids
        if solid.position != volume.center)), volume.elevation)
    if segments:
        reachable = np.zeros(owned.shape, dtype=bool)
        origins = (_visibility_origins(volume.center, volume.radius, segments)
                   if volume.propagation == "connected" else (volume.center,))
        for origin in origins:
            reachable |= _visible_from(origin, x, z, segments)
        keep &= reachable
    if volume.supports:
        floor_height = observed_support_heights(x, z, volume.supports)
        keep &= ~(height < floor_height - .001)
    if volume.admitted is not None:
        cells_x, cells_z = np.floor(x+.5).astype(np.int32), np.floor(z+.5).astype(np.int32)
        admitted = np.zeros(owned.shape, dtype=bool)
        for px, pz in volume.admitted:
            admitted |= (cells_x == px) & (cells_z == pz)
        keep &= admitted
    # The host projection has direction (1,1,1) in view-grid/height units.
    vx, vz = axis_x[0] + axis_z[0], axis_x[1] + axis_z[1]
    occluders = _barriers(volume.boundaries if visual_boundaries is None else (), volume.solids)
    for axis, plane, low, high, bottom, top in occluders:
        if top is None:
            continue
        component, other, direction, cross_direction = (x, z, vx, vz) if axis == 0 else (z, x, vz, vx)
        t = (plane - component) / direction
        crossing = other + t * cross_direction
        keep &= ~((t > 1e-5) & (crossing >= low) & (crossing <= high)
                  & (height + t >= bottom) & (height + t <= top))
    center_depth = project_world(volume.center, quadrant=camera.quadrant)[1]
    depth = center_depth + 32 * (local[:, :, 0] + local[:, :, 2] + dx + dz)
    if visual_boundaries is not None:
        _visual_boundary_coverage(keep, depth, x, z, destination, visual_boundaries, vx, vz)
    for sphere in volume.exclusions:
        dx, dz = x - sphere.center[0], z - sphere.center[1]
        dy = (height - sphere.elevation) / sphere.vertical_scale
        distance2 = dx * dx + dy * dy + dz * dz
        keep &= distance2 > sphere.radius ** 2
        # Exterior samples can appear in front of the shell. Register their
        # genuine side against the existing near/far authored shell depths.
        ray_length = sqrt(2 + 1 / sphere.vertical_scale ** 2)
        axial = (dx * vx + dz * vz + dy / sphere.vertical_scale) / ray_length
        intersects = distance2 - axial * axial <= sphere.radius ** 2
        shell_depth = project_world(sphere.center, quadrant=camera.quadrant)[1]
        extent = sphere.radius * sqrt(2) * 32
        depth = np.where(owned & intersects & (axial > 0), np.maximum(depth, shell_depth + extent + .01), depth)
        depth = np.where(owned & intersects & (axial < 0), np.minimum(depth, shell_depth - extent - .01), depth)
    if barriers or occluders or visual_boundaries or volume.exclusions or volume.supports or volume.admitted is not None:
        keep &= owned  # Unresolved pixels cannot bypass active spatial clipping.
    else:
        keep |= ~owned  # Raw reference artwork retains its original coverage.
    result = image.copy()
    pygame.surfarray.pixels_alpha(result)[:] *= keep
    pygame.surfarray.pixels3d(result)[:] *= keep[:, :, None]
    return result, depth
