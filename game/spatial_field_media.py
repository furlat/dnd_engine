"""Registered floor, clump and volume pixels on observed spatial ownership."""

from math import floor
from uuid import UUID

import numpy as np
import pygame

from dnd.core.presentation_geometry import AoEPresentationGeometry, CylinderPresentationGeometry, SpherePresentationGeometry
from game.animation import view_facing
from game.animation_types import AnimationData, SpatialMediaBinding, SpatialMediaLayer
from game.draw_commands import DrawCommand
from game.player_facts import PlayerState
from game.projection import Camera, TILE_WIDTH, camera_axis_vectors, painter_key, project_screen
from game.registered_media import registered_media_samples
from game.spatial_field import field_cell


def spatial_origin(geometry: AoEPresentationGeometry) -> tuple[int, int]:
    return geometry.center if isinstance(geometry, (SpherePresentationGeometry, CylinderPresentationGeometry)) else geometry.origin


def field_media_commands(state: PlayerState, data: AnimationData, identity: UUID,
                         geometry: AoEPresentationGeometry, positions: tuple[tuple[int, int], ...],
                         binding: SpatialMediaBinding, layer: SpatialMediaLayer, layer_index: int,
                         asset_id: str, frame: int, camera: Camera, alpha: float,
                         translation: tuple[float, float] = (0, 0),
                         anchor_elevation_steps: float | None = None,
                         ) -> tuple[DrawCommand, ...]:
    """Authored registration never adds native cells or discovers occupants."""
    senses = state.senses
    if senses is None:
        return ()
    receiving = {position: (floor(position[0] + translation[0] + .5), floor(position[1] + translation[1] + .5))
                 for position in positions}
    # A visible obscuring surface need not reveal the ground or occupants behind
    # it. The native volume observation has already granted these exact cells.
    supported = {}
    for position in positions:
        cell = receiving[position]
        tile = state.tiles.get(cell)
        if layer.composition == "volume":
            height = tile.elevation_steps if tile is not None else anchor_elevation_steps
            if height is not None:
                supported[position] = height
        elif tile is not None and cell in senses.visible:
            supported[position] = tile.elevation_steps
    if not supported:
        return ()
    origin = spatial_origin(geometry)
    radius_scale = (geometry.radius_feet / binding.referenceRadiusFeet
        if layer.composition == "volume" and isinstance(geometry, SpherePresentationGeometry)
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
    facing = view_facing("E", camera.quadrant, data)
    samples = registered_media_samples(data, asset_id, binding.assetPhase, frame, facing,
        scale=binding.scale * radius_scale * TILE_WIDTH / data.rig.TILE_W * camera.zoom,
        anchor=anchor, rows={}, alpha=alpha)
    north, east = camera_axis_vectors(camera.quadrant)
    result = []
    for part_index, sample in enumerate(samples):
        image, destination = sample.image, sample.destination
        if layer.composition == "clump":
            result.append(DrawCommand(painter_key(displayed_source, elevation_steps=height, quadrant=camera.quadrant,
                role="actor", identity=(str(identity), str(layer_index), str(part_index))), image, destination, sample.blend,
                (str(identity), receiving[owner], asset_id, "current", None, "authored", "spatial_media", height,
                 binding.assetPhase, frame)))
            continue
        pivot = anchor[0] - destination[0], anchor[1] - destination[1]
        points = sample.footpoints
        if points is not None and radius_scale != 1.:
            points = points * radius_scale
        if layer.composition == "volume" and points is None:
            raise ValueError(f"Volume media requires authored world footpoints: {asset_id}")
        cells = None if points is None else np.floor(points + np.array(source) + .5).astype(np.int32)
        image_alpha = pygame.surfarray.array_alpha(image) if cells is not None else None
        for position, tile_height in supported.items():
            received_position = receiving[position]
            world_depth = None
            if layer.composition == "floor":
                piece, crop = field_cell(image, pivot, (position[0] - source[0], position[1] - source[1]),
                                         camera.quadrant, camera.zoom)
                role = "ground_residue"
            else:
                assert points is not None and cells is not None and image_alpha is not None
                admitted = (cells[:, :, 0] == position[0]) & (cells[:, :, 1] == position[1]) & (image_alpha != 0)
                xs, ys = np.nonzero(admitted)
                if not len(xs):
                    continue
                left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
                piece = image.subsurface((left, top, right-left, bottom-top)).copy()
                piece_alpha = pygame.surfarray.pixels_alpha(piece)
                piece_alpha[:] *= admitted[left:right, top:bottom]
                del piece_alpha
                crop = left, top
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
                 binding.assetPhase, frame), world_depth=world_depth))
    return tuple(result)
