"""Clip vertical actor billboards against received finite wall faces and openings."""

from collections.abc import Sequence

import numpy as np
import pygame

from game.area_media import BoundarySprite, boundary_segment, boundary_in_front
from game.draw_commands import DrawCommand
from game.interaction_frame import cut_selection
from game.interaction_types import SelectionCoverage
from game.projection import Camera, HEIGHT_STEP_PIXELS, project_screen, project_world
from dnd.types.event_facts import WorldTileState


def reveal_visible_supports(commands: list[DrawCommand], boundaries: Sequence[BoundarySprite],
                            visible: Sequence[WorldTileState], camera: Camera,
                            ) -> tuple[list[DrawCommand], tuple[BoundarySprite, ...]]:
    """Fade faces covering received visible ground; keep their bases selectable.

    Only camera occlusion changes. Propagation and movement keep their native
    boundaries, and this pass never adds a tile or actor to the received scene.
    """
    polygons = [(tile.position, tuple(project_screen((tile.position[0]+dx, tile.position[1]+dy),
        camera, elevation_steps=tile.elevation_steps) for dx,dy in
        ((-.48,-.48),(.48,-.48),(.48,.48),(-.48,.48)))) for tile in visible]
    supports = [(position, polygon, (min(p[0] for p in polygon), max(p[0] for p in polygon),
                                    min(p[1] for p in polygon), max(p[1] for p in polygon)))
                for position, polygon in polygons]
    faded = {}
    retained = []
    command_coverage = {command.surface: command.selection_block_mask for command in commands
                        if command.selection_block_mask is not None}
    for boundary in boundaries:
        if not boundary.fade_for_visible_ground:
            retained.append(boundary)
            continue
        image = boundary.image
        bounds = pygame.Rect(boundary.destination, image.get_size())
        coverage = None
        for position, polygon, (left, right, top, bottom) in supports:
            if right < bounds.left or left > bounds.right or bottom < bounds.top or top > bounds.bottom:
                continue
            if not any(boundary_in_front(wall, position, camera) for wall in boundary.placements):
                continue
            if coverage is None:
                coverage = pygame.Surface(image.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(coverage, 'white', [(round(x-bounds.x),round(y-bounds.y)) for x,y in polygon])
        if coverage is None:
            retained.append(boundary)
            continue
        physical = command_coverage.get(image)
        if physical is None:
            physical = pygame.surfarray.array_alpha(image) > 0
        pixels = pygame.surfarray.pixels_alpha(coverage)
        overlaps = np.any((pixels > 0) & physical)
        del pixels
        if not overlaps:
            retained.append(boundary)
            continue
        faded[boundary.key] = boundary
    if not faded:
        return commands, tuple(retained)
    result = []
    for command in commands:
        boundary = faded.get(command.key)
        if boundary is None:
            result.append(command)
            continue
        physical = command_coverage.get(command.surface)
        if physical is None:
            physical = pygame.surfarray.array_alpha(command.surface) > 0
        image = command.surface.copy()
        image.set_alpha(65)
        x = command.destination[0] + np.arange(image.width)[:,None]
        y = command.destination[1] + np.arange(image.height)[None,:]
        base = np.zeros(image.get_size(), dtype=bool)
        edges: dict[str, np.ndarray] = {}
        for placement in boundary.placements:
            first,last = boundary_segment(placement)
            a,b = [project_screen(p,camera,elevation_steps=placement.base_height_steps) for p in (first,last)]
            t = (x-a[0])/(b[0]-a[0])
            edge = (t>=0)&(t<=1)&(np.abs(y-(a[1]+t*(b[1]-a[1])))<=6*camera.zoom) & physical
            edges[str(placement.object_uuid)] = edge
            base |= edge
        base &= physical
        # A window passage is intentionally transparent. Its click region must
        # survive fading the solid frame to its selectable base.
        selection = []
        for original in command.selection:
            mask = (original.mask if original.hit.kind == 'aperture' else
                    original.mask & edges.get(original.hit.identity, base))
            mask.setflags(write=False)
            selection.append(SelectionCoverage(original.hit, mask))
        result.append(command._replace(surface=image,selection=tuple(selection),selection_block_mask=base))
    return result, tuple(retained)


def clip_actor_boundaries(
    commands: list[DrawCommand], boundaries: Sequence[BoundarySprite], camera: Camera,
) -> list[DrawCommand]:
    """Sprite transparency does not erase a physical wall; an authored aperture does."""
    faces = []
    for boundary in boundaries:
        if not boundary.actor_occludes:
            continue
        aperture = boundary.actor_aperture_mask
        if aperture is None and boundary.actor_aperture is not None:
            aperture = pygame.surfarray.array_alpha(boundary.actor_aperture) > 0
        for placement in boundary.placements:
            first, last = boundary_segment(placement)
            a = project_screen(first, camera, elevation_steps=placement.base_height_steps)
            b = project_screen(last, camera, elevation_steps=placement.base_height_steps)
            depth_a = project_world(first, quadrant=camera.quadrant)[1]
            depth_b = project_world(last, quadrant=camera.quadrant)[1]
            rise = (placement.top_height_steps - placement.base_height_steps) * HEIGHT_STEP_PIXELS * camera.zoom
            faces.append((boundary, a, b, depth_a, depth_b, rise, placement.base_height_steps, aperture))
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
        for boundary, a, b, depth_a, depth_b, rise, base_height, aperture in faces:
            if (command.destination[0] + width < min(a[0], b[0])
                    or command.destination[0] > max(a[0], b[0])
                    or command.destination[1] + height < min(a[1], b[1]) - rise):
                continue
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
            if aperture is not None:
                opening_width, opening_height = aperture.shape
                local_x = x - boundary.destination[0]
                local_y = y - boundary.destination[1]
                inside = ((local_x >= 0) & (local_x < opening_width)
                          & (local_y >= 0) & (local_y < opening_height))
                allowed = aperture[np.clip(local_x, 0, opening_width - 1),
                                   np.clip(local_y, 0, opening_height - 1)]
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
