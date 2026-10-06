"""Clip vertical actor billboards against received finite wall faces and openings."""

from collections.abc import Sequence

import numpy as np
import pygame

from game.area_media import BoundarySprite, boundary_segment
from game.draw_commands import DrawCommand
from game.interaction_frame import cut_selection
from game.projection import Camera, HEIGHT_STEP_PIXELS, project_screen, project_world


def clip_actor_boundaries(
    commands: list[DrawCommand], boundaries: Sequence[BoundarySprite], camera: Camera,
) -> list[DrawCommand]:
    """Sprite transparency does not erase a physical wall; an authored aperture does."""
    faces = []
    for boundary in boundaries:
        if not boundary.actor_occludes:
            continue
        for placement in boundary.placements:
            first, last = boundary_segment(placement)
            a = project_screen(first, camera, elevation_steps=placement.base_height_steps)
            b = project_screen(last, camera, elevation_steps=placement.base_height_steps)
            depth_a = project_world(first, quadrant=camera.quadrant)[1]
            depth_b = project_world(last, quadrant=camera.quadrant)[1]
            rise = (placement.top_height_steps - placement.base_height_steps) * HEIGHT_STEP_PIXELS * camera.zoom
            faces.append((boundary, a, b, depth_a, depth_b, rise, placement.base_height_steps))
    if not faces:
        return commands
    result = []
    for command in commands:
        if command.role not in ('actor', 'actor_shadow', 'body_copy', 'body_contour', 'body_trail'):
            result.append(command)
            continue
        width, height = command.surface.get_size()
        x = command.destination[0] + np.arange(width)[:, None]
        y = command.destination[1] + np.arange(height)[None, :]
        blocked = np.zeros((width, height), dtype=bool)
        # Shadows lie on the support plane; bodies remain vertical billboards.
        actor_depth = ((y - camera.pan[1]) / camera.zoom
                       + command.support_height_steps * HEIGHT_STEP_PIXELS
                       if command.role == 'actor_shadow' else command.key[1])
        for boundary, a, b, depth_a, depth_b, rise, base_height in faces:
            progress = (x - a[0]) / (b[0] - a[0])
            ground_y = a[1] + progress * (b[1] - a[1])
            depth = depth_a + progress * (depth_b - depth_a)
            # Compare the actor's contact with the wall plane at that contact,
            # not each pixel of a camera-facing billboard with a sloping wall.
            contact_x = command.key[2] * camera.zoom + camera.pan[0]
            contact_progress = (contact_x - a[0]) / (b[0] - a[0])
            behind = command.key[1] < depth_a + contact_progress * (depth_b - depth_a) - 1e-6
            depth_blocked = actor_depth < depth if command.role == 'actor_shadow' else behind
            covered = ((y <= ground_y) & depth_blocked)
            # Feet and ground shadows may protrude past their sprite's pivot.
            # A same-level body behind a wall cannot leak under it onto the
            # camera-facing ground. Lower supports remain visible below it.
            if behind and command.support_height_steps >= base_height:
                covered |= y > ground_y
            covered = ((progress >= 0) & (progress <= 1)
                       & (y >= ground_y - rise) & covered)
            if boundary.actor_aperture is not None:
                opening = boundary.actor_aperture
                local_x = x - boundary.destination[0]
                local_y = y - boundary.destination[1]
                inside = ((local_x >= 0) & (local_x < opening.width)
                          & (local_y >= 0) & (local_y < opening.height))
                alpha = pygame.surfarray.array_alpha(opening)
                allowed = alpha[np.clip(local_x, 0, opening.width - 1),
                                np.clip(local_y, 0, opening.height - 1)] > 0
                covered &= ~(inside & allowed)
            blocked |= covered
        if not np.any(blocked):
            result.append(command)
            continue
        image = command.surface.copy()
        alpha = pygame.surfarray.pixels_alpha(image)
        alpha[blocked] = 0
        del alpha
        selection, blocker = cut_selection(command, ~blocked)
        result.append(command._replace(surface=image, selection=selection, selection_block_mask=blocker))
    return result
