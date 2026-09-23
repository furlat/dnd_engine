"""Propagation and camera-occlusion masks for extended ground area artwork.

This clips a picture's ground footprint, including artwork outside its mechanical
radius. Camera occlusion additionally uses the actual submitted boundary sprites.
Neither operation recomputes targeting or uses observer visibility as a mask.
"""

from dataclasses import dataclass, field
from math import hypot

import numpy as np
import pygame

from dnd.types.world import CardinalDirection
from dnd.core.events import WorldTileState
from dnd.types.world_placement import WorldObjectPlacement
from game.projection import Camera, camera_pose, project_screen, project_world


@dataclass(frozen=True, slots=True)
class AreaSolid:
    """Disclosed solid support; absent top means topology only, not a wall."""

    position: tuple[int, int]
    base_height_steps: float
    top_height_steps: float | None = None


@dataclass(slots=True)
class AreaMedia:
    boundaries: tuple[WorldObjectPlacement, ...]
    solids: tuple[AreaSolid, ...] = ()
    supports: tuple[WorldTileState, ...] = ()
    masks: dict[tuple, pygame.Surface] = field(default_factory=dict)
    compositions: dict[tuple, "_AreaMasks"] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AreaLayer:
    center: tuple[float, float]
    elevation: float
    media: AreaMedia | None


@dataclass(frozen=True, slots=True)
class BoundarySprite:
    placements: tuple[WorldObjectPlacement, ...]
    image: pygame.Surface
    destination: tuple[int, int]
    key: tuple[int, float, float, int, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class WallContactSlice:
    image: pygame.Surface
    destination: tuple[int, int]
    key: tuple[int, float, float, int, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class _AreaMasks:
    ground: pygame.Surface
    normal_faces: tuple[WallContactSlice, ...]
    additive_faces: tuple[WallContactSlice, ...]


def boundary_in_front(wall: WorldObjectPlacement, center: tuple[float, float], camera: Camera) -> bool:
    """Camera and impact lie on opposite sides of the actual boundary plane."""
    first, last = boundary_segment(wall)
    direction = wall.boundary_direction
    assert direction is not None
    axis = 0 if first[0] == last[0] else 1
    # E/S are the two camera-facing positive edge normals after rotation.
    positive_normal = direction in (CardinalDirection.EAST, CardinalDirection.NORTH)
    toward_camera = camera_pose(direction.value, camera.quadrant) in ("e", "s")
    camera_sign = 1 if toward_camera == positive_normal else -1
    return (first[axis] - center[axis]) * camera_sign > 0


def _reachable_face_columns(wall: WorldObjectPlacement, xs: np.ndarray,
                            layer: AreaLayer, camera: Camera) -> np.ndarray:
    """Ray-test the actual receiving footpoint, independent of face height."""
    first, last = boundary_segment(wall)
    first_x = project_screen(first, camera)[0]
    last_x = project_screen(last, camera)[0]
    along = np.clip((xs - first_x) / (last_x - first_x), 0, 1)
    dx = first[0] + along * (last[0] - first[0]) - layer.center[0]
    dy = first[1] + along * (last[1] - first[1]) - layer.center[1]
    reachable = np.ones(xs.shape, dtype=bool)
    for blocker in layer.media.boundaries if layer.media is not None else ():
        if not blocker.base_height_steps <= layer.elevation < blocker.top_height_steps:
            continue
        start, end = boundary_segment(blocker)
        sx, sy = end[0] - start[0], end[1] - start[1]
        ox, oy = start[0] - layer.center[0], start[1] - layer.center[1]
        denominator = dx * sy - dy * sx
        crosses = abs(denominator) > 1e-8
        t = np.divide(ox * sy - oy * sx, denominator, out=np.zeros_like(dx), where=crosses)
        u = np.divide(ox * dy - oy * dx, denominator, out=np.zeros_like(dx), where=crosses)
        reachable &= ~(crosses & (t > 1e-7) & (t < 1 - 1e-7) & (u >= -1e-7) & (u <= 1 + 1e-7))
    return reachable


def compose_area(image: pygame.Surface, destination: tuple[int, int], layer: AreaLayer,
                 camera: Camera, boundaries: list[BoundarySprite], blend: int,
                 ) -> tuple[pygame.Surface, tuple[WallContactSlice, ...]]:
    """Partition an area into ground and disjoint, reachable wall-face pixels.

    Every wall pixel has one owner. Rear slices join their wall's painter depth;
    foreground structure wins regardless of an extended sprite's center key.
    """
    if not boundaries and (layer.media is None or not layer.media.boundaries):
        return image, ()
    key = (image.get_size(), destination, layer.center, layer.elevation, camera,
           tuple((b.image, b.destination, b.key, b.placements) for b in boundaries))
    cached = layer.media.compositions.get(key) if layer.media is not None else None
    if cached is None:
        cached = _compose_masks(image.get_size(), destination, layer, camera, boundaries)
        if layer.media is not None:
            if len(layer.media.compositions) >= 4:
                layer.media.compositions.pop(next(iter(layer.media.compositions)))
            layer.media.compositions[key] = cached
    result = image.copy()
    result.blit(cached.ground, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    contacts = []
    masks = cached.additive_faces if blend == pygame.BLEND_RGB_ADD else cached.normal_faces
    for mask in masks:
        local = mask.image.get_rect(topleft=(mask.destination[0] - destination[0],
                                            mask.destination[1] - destination[1]))
        face = image.subsurface(local).copy()
        face.blit(mask.image, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        contacts.append(WallContactSlice(face, mask.destination, mask.key))
    return result, tuple(contacts)


def _compose_masks(size: tuple[int, int], destination: tuple[int, int], layer: AreaLayer,
                   camera: Camera, boundaries: list[BoundarySprite]) -> _AreaMasks:
    result = _ground_mask(size, destination, layer.center, layer.elevation, camera,
                          layer.media.boundaries if layer.media is not None else ())
    image_rect = pygame.Rect(destination, size)
    claimed = np.zeros(size, dtype=bool)
    normal_faces, additive_faces = [], []
    ordered = sorted(boundaries, key=lambda boundary: (
        any(boundary_in_front(wall, layer.center, camera) for wall in boundary.placements), boundary.key), reverse=True)
    for boundary in ordered:
        overlap = image_rect.clip(boundary.image.get_rect(topleft=boundary.destination))
        if not overlap:
            continue
        local = overlap.move(-destination[0], -destination[1])
        wall_local = overlap.move(-boundary.destination[0], -boundary.destination[1])
        alpha = pygame.surfarray.array_alpha(boundary.image.subsurface(wall_local))
        prior = claimed[local.left:local.right, local.top:local.bottom]
        owned = (alpha > 0) & ~prior
        prior |= alpha > 0
        if not np.any(owned):
            continue
        # Remove ownership before blending either layer; additive fire must not
        # be drawn twice where neighboring wall silhouettes overlap.
        ground = result.subsurface(local)
        pygame.surfarray.pixels3d(ground)[owned] = 0
        pygame.surfarray.pixels_alpha(ground)[owned] = 0
        if any(boundary_in_front(wall, layer.center, camera) for wall in boundary.placements):
            continue
        reachable = np.zeros(overlap.width, dtype=bool)
        xs = np.arange(overlap.left, overlap.right, dtype=float) + .5
        for wall in boundary.placements:
            if wall.base_height_steps <= layer.elevation < wall.top_height_steps:
                reachable |= _reachable_face_columns(wall, xs, layer, camera)
        coverage = np.where(owned & reachable[:, None], alpha, 0)
        if not np.any(coverage):
            continue
        normal = pygame.Surface(overlap.size, pygame.SRCALPHA)
        normal.fill((255, 255, 255, 255))
        pygame.surfarray.pixels_alpha(normal)[:] = coverage
        additive = normal.copy()
        pygame.surfarray.pixels3d(additive)[:] = coverage[:, :, None]
        key = boundary.key
        after_wall = (*key[:3], key[3] + 1, key[4])
        normal_faces.append(WallContactSlice(normal, overlap.topleft, after_wall))
        additive_faces.append(WallContactSlice(additive, overlap.topleft, after_wall))
    return _AreaMasks(result, tuple(normal_faces), tuple(additive_faces))


def boundary_segment(placement: WorldObjectPlacement) -> tuple[tuple[float, float], tuple[float, float]]:
    """The actual half-cell edge, independent of its sprite registration."""
    x, y = placement.position
    direction = placement.boundary_direction
    if direction is CardinalDirection.EAST:
        return (x + .5, y - .5), (x + .5, y + .5)
    if direction is CardinalDirection.WEST:
        return (x - .5, y - .5), (x - .5, y + .5)
    if direction is CardinalDirection.NORTH:
        return (x - .5, y + .5), (x + .5, y + .5)
    if direction is CardinalDirection.SOUTH:
        return (x - .5, y - .5), (x + .5, y - .5)
    raise ValueError("an area boundary needs its recorded direction")


def mask_ground_area(image: pygame.Surface, destination: tuple[int, int],
                     center: tuple[float, float], elevation: float,
                     camera: Camera, media: AreaMedia) -> pygame.Surface:
    """Intersect finite wall shadows once per view, preserving shared frames."""
    if not media.boundaries:
        return image
    origin = project_world(center, elevation_steps=elevation, quadrant=camera.quadrant)
    # Screen placement is rounded by the media adapter. Include that subpixel
    # registration while keeping pan-independent mask reuse for ordinary frames.
    offset = (origin[0] * camera.zoom + camera.pan[0] - destination[0],
              origin[1] * camera.zoom + camera.pan[1] - destination[1])
    key = (image.get_size(), center, elevation, camera.quadrant, camera.zoom,
           round(offset[0], 5), round(offset[1], 5))
    mask = media.masks.get(key)
    if mask is None:
        mask = _ground_mask(image.get_size(), destination, center, elevation, camera, media.boundaries)
        # The cache belongs to this historical cast. Camera zooms may vary;
        # retain only the most recent four full effect masks.
        if len(media.masks) >= 4:
            media.masks.pop(next(iter(media.masks)))
        media.masks[key] = mask
    result = image.copy()
    # Both RGB and alpha are cleared: additive fire ignores alpha by design.
    result.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return result


def _ground_mask(size: tuple[int, int], destination: tuple[int, int],
                 center: tuple[float, float], elevation: float, camera: Camera,
                 boundaries: tuple[WorldObjectPlacement, ...]) -> pygame.Surface:
    origin = project_world(center, elevation_steps=elevation, quadrant=camera.quadrant)
    offset = (origin[0] * camera.zoom + camera.pan[0] - destination[0],
              origin[1] * camera.zoom + camera.pan[1] - destination[1])
    mask = pygame.Surface(size, pygame.SRCALPHA)
    mask.fill((255, 255, 255, 255))
    for wall in boundaries:
        if not wall.base_height_steps <= elevation < wall.top_height_steps:
            continue
        first, last = boundary_segment(wall)
        # Extend the shadow well beyond this finite effect canvas. Wall
        # endpoints keep their finite angular silhouette; doors use their
        # captured open/closed propagation state from the native item.
        far = []
        for point in (first, last):
            dx, dy = point[0] - center[0], point[1] - center[1]
            length = hypot(dx, dy)
            scale = 1 + max(size) / max(camera.zoom, .01) / max(length, .01)
            far.append((center[0] + dx * scale, center[1] + dy * scale))
        points = []
        for point in (first, last, far[1], far[0]):
            x, y = project_world(point, elevation_steps=elevation, quadrant=camera.quadrant)
            points.append(((x - origin[0]) * camera.zoom + offset[0],
                           (y - origin[1]) * camera.zoom + offset[1]))
        pygame.draw.polygon(mask, (0, 0, 0, 0), points)
    return mask
