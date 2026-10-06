"""Keep a floor covering and its supporting terrain coplanar during depth cuts."""

import numpy as np
import pygame

from game.draw_commands import DrawCommand
from game.interaction_frame import cut_selection


def compose_floor_coverings(commands: list[DrawCommand]) -> list[DrawCommand]:
    """Transfer only covered, same-height terrain pixels beneath the floor art.

    A raised tile's center depth must not cover the back half of its own rug.
    Transferring the underlay preserves translucent artwork and lets the existing
    ground-depth painter place both beneath actors and their contact shadows.
    """
    coverings = sorted((index for index, command in enumerate(commands) if command.role == "environment_floor"),
                       key=lambda index: commands[index].key)
    if not coverings:
        return commands
    terrain = sorted((index for index, command in enumerate(commands) if command.role == "terrain_floor"),
                     key=lambda index: commands[index].key)
    result = list(commands)
    for index in coverings:
        command = commands[index]
        bounds = command.surface.get_rect(topleft=command.destination)
        covered = pygame.surfarray.array_alpha(command.surface) != 0
        underlay = pygame.Surface(command.surface.get_size(), pygame.SRCALPHA)
        transferred = False
        for ground_index in terrain:
            ground = result[ground_index]
            if ground.support_height_steps != command.support_height_steps:
                continue
            rectangle = ground.surface.get_rect(topleft=ground.destination)
            overlap = bounds.clip(rectangle)
            if not overlap.width or not overlap.height:
                continue
            source = overlap.move(-rectangle.left, -rectangle.top)
            destination = overlap.move(-bounds.left, -bounds.top)
            selected = covered[destination.left:destination.right, destination.top:destination.bottom]
            patch = ground.surface.subsurface(source).copy()
            selected = selected & (pygame.surfarray.array_alpha(patch) != 0)
            if not np.any(selected):
                continue
            alpha = pygame.surfarray.pixels_alpha(patch)
            alpha[:] *= selected
            del alpha
            underlay.blit(patch, destination)
            remainder = ground.surface.copy()
            alpha = pygame.surfarray.pixels_alpha(remainder)
            alpha[source.left:source.right, source.top:source.bottom] *= ~selected
            del alpha
            retained = np.ones(ground.surface.get_size(), dtype=bool)
            retained[source.left:source.right, source.top:source.bottom] &= ~selected
            selection, blocker = cut_selection(ground, retained)
            result[ground_index] = ground._replace(surface=remainder, selection=selection,
                                                   selection_block_mask=blocker)
            transferred = True
        if transferred:
            underlay.blit(command.surface, (0, 0))
            result[index] = command._replace(surface=underlay)
    # Overlapping coplanar layers share the existing ordered depth bands. A
    # sparse straw layer must not slip behind its rug because their mean depths
    # differ. Disjoint coverings keep independent cuts and their ordinary cost.
    groups: list[list[int]] = []
    for index in coverings:
        command = result[index]
        bounds = command.surface.get_rect(topleft=command.destination)
        touching = [group for group in groups if any(
            result[peer].support_height_steps == command.support_height_steps
            and bounds.colliderect(result[peer].surface.get_rect(topleft=result[peer].destination))
            for peer in group)]
        groups = [group for group in groups if group not in touching]
        groups.append([index, *(peer for group in touching for peer in group)])
    for group in groups:
        if len(group) < 2:
            continue
        first = min(group, key=lambda index: result[index].key)
        identity = ("environment_floor", *result[first].key[4])
        for index in group:
            result[index] = result[index]._replace(world_depth_group=identity)
    return result
