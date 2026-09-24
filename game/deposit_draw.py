"""Render recorded liquid geometry through registered floor and air media."""

from typing import Mapping
from uuid import UUID

import numpy as np
import pygame

from game.animation import view_facing
from game.animation_types import AnimationData
from game.deposit_media import ObservedMaterialDeposit
from game.draw_commands import DrawCommand
from game.maintained_media import maintained_media_frame
from game.player_facts import PlayerState
from game.projection import Camera, TILE_WIDTH, camera_axis_vectors, painter_key, project_screen
from game.registered_media import registered_media_samples
from game.spatial_field import field_cell


def deposit_draw_commands(state: PlayerState, deposits: tuple[ObservedMaterialDeposit, ...],
                          starts: Mapping[UUID, float], data: AnimationData,
                          presentation_ms: float, camera: Camera) -> tuple[DrawCommand, ...]:
    senses = state.senses
    if senses is None:
        return ()
    result = []
    north, east = camera_axis_vectors(camera.quadrant)
    facing = view_facing("E", camera.quadrant, data)
    for deposit in deposits:
        source = deposit.source
        authored = data.deposit_media[deposit.material_id]
        binding = authored.variants[source.deposit_uuid.int % len(authored.variants)]
        supported = tuple(sorted(position for position in deposit.positions
            if position in state.tiles and (position in senses.visible or position in senses.seen)))
        if not supported:
            continue
        # Native ground deposition guarantees a common support height. Its
        # observed fragment can register the frame without discovering origin.
        height = state.tiles[supported[0]].elevation_steps
        anchor = project_screen(source.origin, camera, elevation_steps=height)
        origin_key = painter_key(source.origin, elevation_steps=height, quadrant=camera.quadrant,
                                role="actor", identity=str(source.deposit_uuid))
        for layer_index, layer in enumerate(binding.layers):
            selected = maintained_media_frame(data, binding, layer, presentation_ms, starts.get(source.deposit_uuid))
            if selected is None:
                continue
            asset_id, frame = selected
            samples = registered_media_samples(data, asset_id, binding.assetPhase, frame, facing,
                scale=binding.scale * TILE_WIDTH / data.rig.TILE_W * camera.zoom, anchor=anchor, rows={})
            for part_index, sample in enumerate(samples):
                image, destination = sample.image, sample.destination
                pivot = anchor[0] - destination[0], anchor[1] - destination[1]
                points = sample.footpoints
                cells = None if points is None else np.floor(points + .5).astype(np.int16)
                depth = None if points is None else origin_key[1] + points[:, :, 0] * east[1] + points[:, :, 1] * north[1]
                for position in supported:
                    offset = position[0] - source.origin[0], position[1] - source.origin[1]
                    world_depth = None
                    if points is None:
                        piece, crop = field_cell(image, pivot, offset, camera.quadrant, camera.zoom)
                        role, kind = "ground_residue", "deposit_floor"
                    else:
                        if position not in senses.visible:
                            continue
                        assert cells is not None and depth is not None
                        admitted = ((cells[:, :, 0] == offset[0]) & (cells[:, :, 1] == offset[1])
                                    & (pygame.surfarray.array_alpha(image) != 0))
                        xs, ys = np.nonzero(admitted)
                        if not len(xs):
                            continue
                        left, top = int(xs.min()), int(ys.min())
                        right, bottom = int(xs.max()) + 1, int(ys.max()) + 1
                        piece = image.subsurface((left, top, right-left, bottom-top)).copy()
                        alpha = pygame.surfarray.pixels_alpha(piece)
                        alpha[:] *= admitted[left:right, top:bottom]
                        del alpha
                        crop = left, top
                        world_depth = depth[left:right, top:bottom]
                        role, kind = "actor", "deposit_air"
                    if not piece.get_bounding_rect().width:
                        continue
                    key = painter_key(position, elevation_steps=height, quadrant=camera.quadrant, role=role,
                        identity=(str(source.deposit_uuid), deposit.material_id, str(layer_index), str(part_index), str(position)))
                    evidence = (str(source.deposit_uuid), position, asset_id,
                        "current" if position in senses.visible else "memory", None, "authored", kind,
                        height, binding.assetPhase, frame, deposit.material_id)
                    result.append(DrawCommand(key, piece, (destination[0]+crop[0], destination[1]+crop[1]),
                                              sample.blend, evidence, world_depth=world_depth,
                                              role=kind, owner=str(source.deposit_uuid), cell=position))
    return tuple(result)
