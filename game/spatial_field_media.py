"""Registered floor, clump and volume pixels on observed spatial ownership."""

from math import floor, sqrt
from uuid import UUID

import numpy as np
import pygame

from dnd.core.presentation_geometry import (
    AoEPresentationGeometry, ConePresentationGeometry, CubePresentationGeometry,
    CylinderPresentationGeometry, LinePresentationGeometry, SpherePresentationGeometry,
)
from dnd.core.geometry import circle_positions
from dnd.types.senses import PerceivedSpatialEffect, VolumeSurfaceSight
from game.animation import view_facing
from game.animation_types import AnimationData, SpatialMediaBinding, SpatialMediaLayer
from game.area_media import AreaMedia
from game.draw_commands import DrawCommand
from game.player_facts import PlayerState
from game.projection import Camera, TILE_WIDTH, camera_axis_vectors, inverse_rotate_position, painter_key, project_screen
from game.registered_media import registered_media_samples
from game.spatial_field import field_cell, sphere_field_owners
from game.volume_media import ExcludedSphere, SurfaceVolume, unobstructed_volume_points


def spatial_origin(geometry: AoEPresentationGeometry) -> tuple[int, int]:
    if isinstance(geometry, (SpherePresentationGeometry, CylinderPresentationGeometry)):
        return geometry.center
    # Walls have their own registered placement composer, never a field origin.
    assert isinstance(geometry, (ConePresentationGeometry, CubePresentationGeometry, LinePresentationGeometry))
    return geometry.origin


def field_media_commands(state: PlayerState, data: AnimationData, identity: UUID,
                         geometry: AoEPresentationGeometry | None, positions: tuple[tuple[int, int], ...],
                         binding: SpatialMediaBinding, layer: SpatialMediaLayer, layer_index: int,
                         asset_id: str, frame: int, camera: Camera, alpha: float,
                         translation: tuple[float, float] = (0, 0),
                         anchor_elevation_steps: float | None = None,
                         area: AreaMedia | None = None,
                         exclusions: tuple[ExcludedSphere, ...] = (),
                         upper_surfaces: tuple[VolumeSurfaceSight, ...] = (),
                         previous_effect: PerceivedSpatialEffect | None = None,
                         anchor_position: tuple[int, int] | None = None,
                         ) -> tuple[DrawCommand, ...]:
    """Authored registration never adds native cells or discovers occupants."""
    senses = state.senses
    if senses is None:
        return ()
    if geometry is None and (layer.composition != "clump" or anchor_position is None):
        return ()
    volume_layer = layer.composition in ("xy_volume", "xyz_volume")
    upper: dict[tuple[int, int], list[tuple[tuple[float, float, float], ...]]] = {}
    for row in upper_surfaces:
        if row.position not in positions:
            upper.setdefault(row.position, []).append(row.lower_height_planes)
    full_positions = positions
    moving_xyz = (previous_effect is not None and layer.composition == "xyz_volume"
                  and isinstance(geometry, SpherePresentationGeometry))
    if moving_xyz:
        assert isinstance(geometry, SpherePresentationGeometry)
        x0, y0, x1, y1 = state.world.bounds
        # Partition artwork with the same stable owners as stationary playback.
        # Sight is evaluated separately, at its current world position below.
        positions = tuple(sorted(p for p in circle_positions(geometry.center, geometry.radius_feet // 5)
                                 if x0 <= p[0] <= x1 and y0 <= p[1] <= y1))
    if layer.composition == "xyz_volume":
        positions = tuple(dict.fromkeys((*positions, *upper)))
    receiving = {position: (floor(position[0] + translation[0] + .5), floor(position[1] + translation[1] + .5))
                 for position in positions}
    # A visible obscuring surface need not reveal the ground or occupants behind
    # it. The native volume observation has already granted these exact cells.
    supported = {}
    for position in positions:
        cell = receiving[position]
        tile = state.tiles.get(cell)
        if volume_layer:
            height = tile.elevation_steps if tile is not None else anchor_elevation_steps
            if height is not None:
                supported[position] = height
        elif tile is not None and cell in senses.visible:
            supported[position] = tile.elevation_steps
    if not supported:
        return ()
    origin = spatial_origin(geometry) if geometry is not None else anchor_position
    assert origin is not None
    radius_scale = (geometry.radius_feet / binding.referenceRadiusFeet
        if volume_layer and isinstance(geometry, SpherePresentationGeometry)
        and binding.referenceRadiusFeet is not None else 1.)
    source = origin[0] + layer.offsetCells[0] * radius_scale, origin[1] + layer.offsetCells[1] * radius_scale
    displayed_source = source[0] + translation[0], source[1] + translation[1]
    owner = floor(source[0] + .5), floor(source[1] + .5)
    if layer.composition == "clump" and owner not in supported:
        return ()
    # Each receiving cell supplies its own known support. An observed volume
    # edge does not require the hidden center's ground tile to be disclosed.
    height = supported[owner] if layer.composition == "clump" else 0
    anchor = project_screen(displayed_source, camera, elevation_steps=height)
    facing = view_facing(layer.worldFacing, camera.quadrant, data)
    samples = registered_media_samples(data, asset_id, binding.assetPhase, frame, facing,
        scale=binding.scale * layer.scale * radius_scale * TILE_WIDTH / data.rig.TILE_W * camera.zoom,
        anchor=anchor, rows={}, alpha=alpha, zoom=camera.zoom)
    north, east = camera_axis_vectors(camera.quadrant)
    result = []
    for part_index, sample in enumerate(samples):
        image, destination = sample.image, sample.destination
        if layer.composition == "clump":
            key = painter_key(displayed_source, elevation_steps=height, quadrant=camera.quadrant,
                role="actor", identity=(str(identity), str(layer_index), str(part_index)))
            if layer.side != "center":
                key = (*key[:3], key[3] + (-1 if layer.side == "rear" else 1), key[4])
            result.append(DrawCommand(key, image, destination, sample.blend,
                (str(identity), receiving[owner], asset_id, "current", None, "authored", "spatial_media", height,
                 binding.assetPhase, frame)))
            continue
        pivot = anchor[0] - destination[0], anchor[1] - destination[1]
        points = sample.footpoints
        if points is not None and radius_scale != 1.:
            points = points * radius_scale
        if layer.composition == "xyz_volume":
            assert sample.positions is not None and sample.ownership is not None
            zero = inverse_rotate_position((0., 0.), camera.quadrant)
            axis_x = np.subtract(inverse_rotate_position((1., 0.), camera.quadrant), zero)
            axis_z = np.subtract(inverse_rotate_position((0., 1.), camera.quadrant), zero)
            points = (sample.positions[:, :, 0, None] * axis_x
                      + sample.positions[:, :, 2, None] * axis_z)
        if volume_layer and points is None:
            raise ValueError(f"Volume media requires authored world footpoints: {asset_id}")
        cells = None if points is None else np.floor(points + np.array(source) + .5).astype(np.int32)
        image_alpha = pygame.surfarray.array_alpha(image) if cells is not None else None
        outside = edge_owners = displayed_points = None
        motion_visible = motion_upper = None
        if layer.composition == "xyz_volume" and isinstance(geometry, SpherePresentationGeometry):
            assert cells is not None
            # Permission belongs to the received geometry, before presentation
            # translation. A clipped map-edge owner must not drift inward and
            # turn the map boundary into a temporary wall during movement.
            cells = sphere_field_owners(cells, geometry.center, geometry.radius_feet // 5, state.world.bounds)
            if cells is None:
                continue
            if moving_xyz:
                assert previous_effect is not None and sample.positions is not None
                motion_visible, motion_upper = _moving_sight(
                    points + np.array(displayed_source), sample.positions[:, :, 1] * sample.vertical_scale,
                    geometry, full_positions, upper_surfaces, previous_effect, state,
                    anchor_elevation_steps or 0., exclusions,
                    (geometry.center[0] + translation[0], geometry.center[1] + translation[1]))
        elif volume_layer:
            assert points is not None
            # Bounds describe the known map, not the currently visible subset.
            # Only the decorative exterior borrows an admitted edge's support;
            # its authored position and painter depth remain untouched.
            displayed_points = points + np.array(displayed_source)
            displayed_cells = np.floor(displayed_points + .5).astype(np.int32)
            x0, y0, x1, y1 = state.world.bounds
            edge_owners = np.clip(displayed_cells, (x0, y0), (x1, y1))
            outside = np.any(displayed_cells != edge_owners, axis=2)
        for position, tile_height in supported.items():
            received_position = receiving[position]
            world_depth = None
            volume = None
            if layer.composition == "floor":
                piece, crop = field_cell(image, pivot, (position[0] - source[0], position[1] - source[1]),
                                         camera.quadrant, camera.zoom)
                role = "ground_residue"
            else:
                assert points is not None and cells is not None and image_alpha is not None
                admitted = (cells[:, :, 0] == position[0]) & (cells[:, :, 1] == position[1]) & (image_alpha != 0)
                if motion_visible is not None:
                    admitted &= motion_visible
                elif layer.composition == "xyz_volume" and position in upper:
                    assert sample.positions is not None
                    sample_height = sample.positions[:, :, 1] * sample.vertical_scale + tile_height
                    witnessed = np.zeros(admitted.shape, dtype=bool)
                    for planes in upper[position]:
                        clear = admitted.copy()
                        for a, b, c in planes:
                            clear &= sample_height > a * (points[:, :, 0] + displayed_source[0]) + b * (points[:, :, 1] + displayed_source[1]) + c
                        witnessed |= clear
                    admitted &= witnessed
                if outside is not None:
                    assert edge_owners is not None and displayed_points is not None
                    fringe = (outside & (edge_owners[:, :, 0] == received_position[0])
                              & (edge_owners[:, :, 1] == received_position[1]) & (image_alpha != 0))
                    if area is not None and (area.boundaries or area.solids):
                        fx, fy = np.nonzero(fringe)
                        if len(fx):
                            fringe[fx, fy] &= unobstructed_volume_points(received_position,
                                displayed_points[fx, fy, 0], displayed_points[fx, fy, 1],
                                tile_height, area.boundaries, area.solids)
                    admitted = (admitted & ~outside) | fringe
                xs, ys = np.nonzero(admitted)
                if not len(xs):
                    continue
                left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
                piece = image.subsurface((left, top, right-left, bottom-top)).copy()
                piece_alpha = pygame.surfarray.pixels_alpha(piece)
                piece_alpha[:] *= admitted[left:right, top:bottom]
                del piece_alpha
                crop = left, top
                if layer.composition == "xyz_volume":
                    assert sample.positions is not None and sample.ownership is not None
                    volume = SurfaceVolume(displayed_source, tile_height,
                        geometry.radius_feet / 5 if isinstance(geometry, SpherePresentationGeometry) else 0,
                        sample.positions[left:right, top:bottom], sample.ownership[left:right, top:bottom],
                        sample.vertical_scale, area.boundaries if area is not None else (), exclusions,
                        area.solids if area is not None else (), area.supports if area is not None else (),
                        resolved_occupancy=True,
                        upper_only=(motion_upper[left:right, top:bottom] if motion_upper is not None
                                    else np.ones((right-left, bottom-top), dtype=bool) if position in upper else None))
                else:
                    source_depth = painter_key(displayed_source, elevation_steps=tile_height, quadrant=camera.quadrant,
                                              role="actor", identity=str(identity))[1]
                    world_depth = source_depth + points[left:right, top:bottom, 0] * east[1] + points[left:right, top:bottom, 1] * north[1]
                role = "actor"
            if not piece.get_bounding_rect().width:
                continue
            supported_anchor = project_screen(displayed_source, camera, elevation_steps=tile_height)
            placed = (destination[0] + crop[0], round(destination[1] + crop[1] + supported_anchor[1] - anchor[1]))
            result.append(DrawCommand(painter_key(received_position, elevation_steps=tile_height, quadrant=camera.quadrant,
                role=role, identity=(str(identity), str(layer_index), str(part_index), str(position))),
                piece, placed, sample.blend,
                (str(identity), received_position, asset_id, "current", None, "authored", "spatial_media", tile_height,
                 binding.assetPhase, frame), world_depth=world_depth, volume=volume,
                world_depth_group=(str(identity), "maintained-media") if volume is not None else None))
    return tuple(result)


def _moving_sight(points: np.ndarray, heights: np.ndarray,
                  geometry: SpherePresentationGeometry, positions: tuple[tuple[int, int], ...],
                  upper: tuple[VolumeSurfaceSight, ...], previous: PerceivedSpatialEffect,
                  state: PlayerState, elevation: float, exclusions: tuple[ExcludedSphere, ...],
                  center: tuple[float, float],
                  ) -> tuple[np.ndarray, np.ndarray]:
    """Sample recorded sight in world space while the artwork travels through it."""
    assert isinstance(previous.area_geometry, SpherePresentationGeometry) and state.senses is not None
    prior_positions = tuple(p for p in previous.positions
                            if p in previous.visible_volume_positions or p in state.senses.visible)
    providers = {sphere.provider for sphere in exclusions}
    prior_positions += tuple(p for row in previous.suppressions if str(row.provider_uuid) in providers
                             for p in row.positions)
    cells = np.floor(points + .5).astype(np.int32)
    x0, y0, x1, y1 = state.world.bounds
    declarations = tuple(frozenset(p for p in circle_positions(g.center, g.radius_feet // 5)
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1) for g in (previous.area_geometry, geometry))
    # A moving round rim can lie outside both endpoint lattices. Only that
    # decorative exterior borrows an endpoint owner; unknown interior stays dark.
    interior = np.zeros(cells.shape[:2], dtype=bool)
    for x, y in declarations[0] | declarations[1]:
        interior |= (cells[:, :, 0] == x) & (cells[:, :, 1] == y)
    interior &= ((cells[:, :, 0] - center[0]) ** 2 + (cells[:, :, 1] - center[1]) ** 2
                 <= (geometry.radius_feet / 5) ** 2)
    old_owners = sphere_field_owners(cells, previous.area_geometry.center,
                                   previous.area_geometry.radius_feet // 5, state.world.bounds)
    new_owners = sphere_field_owners(cells, geometry.center, geometry.radius_feet // 5, state.world.bounds)
    if old_owners is None or new_owners is None:
        return np.zeros(interior.shape, dtype=bool), np.zeros(interior.shape, dtype=bool)
    delta = np.subtract(geometry.center, previous.area_geometry.center)
    distance2 = float(delta @ delta)
    progress = float(np.subtract(center, previous.area_geometry.center) @ delta) / distance2 if distance2 else 1.
    fringe_owners = np.floor(old_owners * (1 - progress) + new_owners * progress + .5).astype(np.int32)
    owners = np.where(interior[:, :, None], cells, fringe_owners)
    visible = np.zeros(interior.shape, dtype=bool)
    full_visible = np.zeros(interior.shape, dtype=bool)
    complete_fringe = ~interior
    for endpoint_owners, full, surfaces in ((old_owners, prior_positions, previous.upper_volume_surfaces),
                                            (new_owners, positions, upper)):
        full_set = frozenset(full)
        full_fringe = np.zeros(interior.shape, dtype=bool)
        for x, y in full_set:
            full_fringe |= (endpoint_owners[:, :, 0] == x) & (endpoint_owners[:, :, 1] == y)
        complete_fringe &= full_fringe
        for position in full_set | {row.position for row in surfaces}:
            belongs = (owners[:, :, 0] == position[0]) & (owners[:, :, 1] == position[1])
            if position in full_set:
                visible |= belongs
                full_visible |= belongs
                continue
            tile = state.tiles.get(position)
            height = elevation if tile is None else tile.elevation_steps
            for row in surfaces:
                if row.position != position:
                    continue
                dx = max(0., abs(position[0] - center[0]) - .5)
                dy = max(0., abs(position[1] - center[1]) - .5)
                top = height + sqrt(max(0., (geometry.radius_feet / 5) ** 2 - dx*dx - dy*dy))
                if all(max(a*x + b*y + c for a, b, c in row.lower_height_planes) >= top
                       for x, y in ((position[0]+ox, position[1]+oy)
                                    for ox in (-.5, .5) for oy in (-.5, .5))):
                    continue
                clear = belongs.copy()
                for a, b, c in row.lower_height_planes:
                    clear &= heights + height > a * points[:, :, 0] + b * points[:, :, 1] + c
                visible |= clear
    return visible | complete_fringe, visible & ~full_visible & ~complete_fringe
