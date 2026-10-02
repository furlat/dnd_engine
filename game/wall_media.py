"""Native-view wall modules over disclosed retained flame contacts."""

from math import ceil, cos, floor, hypot, isclose, radians, sqrt
from typing import Collection
from uuid import UUID

from dnd.core.presentation_geometry import AoEPresentationGeometry, WallPresentationGeometry, WallSegment, WallRing
from dnd.core.wall_geometry import wall_shell_cells
from dnd.types.senses import PerceivedSpatialEffect
from game.animation import view_facing
from game.animation_types import AnimationData, SpatialMediaBinding, MaskedMediaTint, SpatialMediaLayer, WallAxisMedia
from game.draw_commands import DrawCommand
from game.maintained_media import maintained_media_alpha, maintained_media_frame
from game.projection import Camera, painter_key, project_screen, rotate_position, inverse_rotate_position
from game.registered_media import registered_media_samples


_AXIS_TANGENTS = {"x": (1, 0), "y": (0, 1),
                  "diagonal_positive": (1, 1), "diagonal_negative": (1, -1)}
_LEGACY_MASK_NORMALS = {"x": (0, 1), "y": (1, 0)}


def _selected_bank(layer: SpatialMediaLayer, path: WallSegment) -> WallAxisMedia | None:
    dx, dy = path.end[0]-path.start[0], path.end[1]-path.start[1]
    length = hypot(dx, dy)
    def alignment(bank: WallAxisMedia) -> float:
        x, y = _AXIS_TANGENTS[bank.axis]
        return abs(dx*x+dy*y)/(length*hypot(x, y))
    bank = max(layer.wallAxes, key=alignment)
    return bank if alignment(bank)+1e-9 >= cos(radians(bank.maxAngleDegrees)) else None


def wall_media_limitation(geometry: AoEPresentationGeometry | None,
                         binding: SpatialMediaBinding | None = None, *,
                         positions: Collection[tuple[int, int]] | None = None,
                         suppressed: bool = False) -> str | None:
    """Missing native directional coverage remains an explicit presentation gap."""
    if not isinstance(geometry, WallPresentationGeometry):
        return "Wall module media requires retained wall geometry"
    if isinstance(geometry.path, WallRing):
        if binding is None or any(layer.wallRing is None for layer in binding.layers
                                 if layer.composition == "wall_modules"):
            return "Curved wall media has not been delivered"
        if any(not isclose(layer.wallRing.radiusFeet, geometry.path.radius_feet)
               or not isclose(layer.wallRing.widthFeet, geometry.width_feet)
               for layer in binding.layers if layer.wallRing is not None):
            return "Ring media does not match the recorded radius/width"
        if suppressed or positions is not None and not wall_shell_cells(geometry) <= set(positions):
            return "Whole-ring media requires a complete disclosed, unprotected shell"
        return None
    if binding is not None:
        if any(_selected_bank(layer, geometry.path) is None for layer in binding.layers
               if layer.composition == "wall_modules"):
            return "Diagonal directional wall modules have not been delivered for this angle"
    elif not (isclose(geometry.path.start[0], geometry.path.end[0])
              or isclose(geometry.path.start[1], geometry.path.end[1])):
        return "Diagonal directional wall modules have not been delivered"
    return None


def wall_module_centers(path: WallSegment, positions: Collection[tuple[int, int]],
                        spacing: float) -> tuple[tuple[float, float], ...]:
    """Canonical arc candidates, gated by received cell centers before drawing."""
    start, end = sorted((path.start, path.end))
    dx, dy = end[0]-start[0], end[1]-start[1]
    intervals = max(1, ceil(hypot(dx, dy)/spacing))
    disclosed = frozenset(positions)
    candidates = ((start[0]+dx*index/intervals, start[1]+dy*index/intervals)
                  for index in range(intervals+1))
    return tuple(point for point in candidates
                 if (floor(point[0]+.5), floor(point[1]+.5)) in disclosed)


def wall_media_draw_commands(effect: PerceivedSpatialEffect, identity: UUID,
        data: AnimationData, binding: SpatialMediaBinding, presentation_ms: float,
        camera: Camera, applied_ms: float | None, removed_ms: float | None) -> tuple[DrawCommand, ...]:
    """Observe native contacts, select baked world axes, reuse the maintained clock."""
    geometry = effect.area_geometry
    if wall_media_limitation(geometry, binding, positions=effect.positions,
                             suppressed=bool(effect.suppressions)) is not None:
        return ()
    if isinstance(geometry, WallPresentationGeometry) and isinstance(geometry.path, WallRing):
        return _ring_draw_commands(geometry, identity, data, binding, presentation_ms,
                                   camera, applied_ms, removed_ms)
    assert isinstance(geometry, WallPresentationGeometry) and isinstance(geometry.path, WallSegment)
    dx, dy = (geometry.path.end[i]-geometry.path.start[i] for i in (0, 1))
    canonical_start = min(geometry.path.start, geometry.path.end)
    length = hypot(dx, dy)
    safe_normal = (dy, -dx) if geometry.hot_side == "left" else (-dy, dx)
    facing = view_facing("E", camera.quadrant, data)
    commands = []
    for layer_index, layer in enumerate(binding.layers):
        if layer.composition != "wall_modules":
            continue
        bank = _selected_bank(layer, geometry.path)
        assert bank is not None
        intervals = max(1, ceil(length / bank.spacingCells))
        tint = None
        if binding.safeSideTint is not None and geometry.hot_side in ("left", "right"):
            normal = bank.positiveMaskNormal or _LEGACY_MASK_NORMALS[bank.axis]
            sign = normal[0]*safe_normal[0]+normal[1]*safe_normal[1]
            tint = MaskedMediaTint(mask="positive" if sign > 0 else "negative",
                color=binding.safeSideTint.color, strength=binding.safeSideTint.strength)
        for position in wall_module_centers(geometry.path, effect.positions, bank.spacingCells):
            # Use the full arc ordinal: diagonals must not collapse to one layout,
            # and hidden modules must not renumber the remaining paired layers.
            ordinal = round(hypot(position[0]-canonical_start[0],
                                  position[1]-canonical_start[1]) * intervals / length)
            variant = bank.variants[ordinal % len(bank.variants)]
            selected_layer = layer.model_copy(update={"assetId": variant.assetId,
                "applicationAssetId": variant.applicationAssetId})
            alpha = maintained_media_alpha(binding, selected_layer, presentation_ms, removed_ms)
            if alpha <= 0:
                continue
            selected = maintained_media_frame(data, binding, selected_layer, presentation_ms, applied_ms, removed_ms)
            if selected is None:
                continue
            asset_id, frame = selected
            anchor = project_screen(position, camera, elevation_steps=geometry.base_height_steps)
            for index, part in enumerate(registered_media_samples(data, asset_id, binding.assetPhase,
                    frame, facing, scale=binding.scale*camera.zoom,
                    anchor=anchor, rows={}, alpha=alpha, zoom=camera.zoom, masked_tint=tint)):
                commands.append(DrawCommand(painter_key(position, elevation_steps=geometry.base_height_steps,
                    quadrant=camera.quadrant, role="actor_shadow" if layer.side == "rear" else "projectile",
                    identity=(str(identity), str(position), str(layer_index), str(index))),
                    part.image, part.destination, part.blend,
                    (str(identity), position, asset_id, "current", None, "authored", "spatial_media",
                     geometry.base_height_steps, binding.assetPhase, frame),
                    owner=str(identity), support_height_steps=geometry.base_height_steps))
    return tuple(commands)


def _ring_draw_commands(geometry: WallPresentationGeometry, identity: UUID,
        data: AnimationData, binding: SpatialMediaBinding, now: float, camera: Camera,
        applied_ms: float | None, removed_ms: float | None) -> tuple[DrawCommand, ...]:
    assert isinstance(geometry.path, WallRing)
    center = geometry.path.center
    camera_center = rotate_position(center, camera.quadrant)
    radius = geometry.path.radius_feet / 5
    commands = []
    for layer_index, layer in enumerate(binding.layers):
        if layer.composition != "wall_modules":
            continue
        bank = layer.wallRing
        assert bank is not None
        selected_layer = layer.model_copy(update={"assetId": bank.assetId,
            "applicationAssetId": bank.applicationAssetId})
        selected = maintained_media_frame(data, binding, selected_layer, now, applied_ms, removed_ms)
        alpha = maintained_media_alpha(binding, selected_layer, now, removed_ms)
        if selected is None or alpha <= 0:
            continue
        tint = None
        if binding.safeSideTint is not None and (
                geometry.hot_side == "inside" and layer.side == "front"
                or geometry.hot_side == "outside" and layer.side == "rear"):
            tint = MaskedMediaTint(mask="positive" if geometry.hot_side == "inside" else "negative",
                color=binding.safeSideTint.color, strength=binding.safeSideTint.strength)
        sign = -1 if layer.side == "rear" else 1
        contact = inverse_rotate_position((camera_center[0] + sign*radius/sqrt(2),
            camera_center[1] + sign*radius/sqrt(2)), camera.quadrant)
        asset_id, frame = selected
        for index, part in enumerate(registered_media_samples(data, asset_id, binding.assetPhase,
                frame, view_facing("E", camera.quadrant, data), scale=binding.scale*camera.zoom,
                anchor=project_screen(center, camera, elevation_steps=geometry.base_height_steps),
                rows={}, alpha=alpha, zoom=camera.zoom, masked_tint=tint)):
            commands.append(DrawCommand(painter_key(contact, elevation_steps=geometry.base_height_steps,
                quadrant=camera.quadrant, role="actor_shadow" if layer.side == "rear" else "projectile",
                identity=(str(identity), str(layer_index), str(index))), part.image, part.destination,
                part.blend, (str(identity), center, asset_id, "current", None, "authored", "spatial_media",
                geometry.base_height_steps, binding.assetPhase, frame), owner=str(identity),
                support_height_steps=geometry.base_height_steps))
    return tuple(commands)
