"""Register enclosing fixture pixels with the ordinary world painter.

Authored fixtures partition around overlapping world draw commands. Parts retain
their original RGBA and ordinary alpha blending; actor/VFX images stay intact.
"""

from dataclasses import dataclass
from functools import lru_cache
from math import nextafter
from pathlib import Path

import numpy as np
import pygame

from game.animation_types import PropDepth
from game.draw_commands import DrawCommand


@dataclass(frozen=True, slots=True)
class FixtureDepthSample:
    command_index: int
    atlas: Path
    registration: PropDepth
    pose: str
    frame: int
    full_size: tuple[int, int]
    crop: tuple[int, int, int, int]
    asset_scale: float
    depth_origin_offset_px: float = 0


@lru_cache(maxsize=4)
def _atlas(path: Path) -> pygame.Surface:
    return pygame.image.load(path).convert_alpha()


@lru_cache(maxsize=192)
def _depth_cell(path: Path, cell: tuple[int, int], row: int, frame: int,
                size: tuple[int, int]) -> np.ndarray:
    width, height = cell
    image = _atlas(path).subsurface((frame * width, row * height, width, height))
    values = pygame.surfarray.array3d(pygame.transform.scale(image, size)).astype(np.uint16)
    encoded = values[:, :, 0] + values[:, :, 1] * 256
    encoded.setflags(write=False)
    return encoded


def partition_world_depth(command: DrawCommand, depth: np.ndarray,
                          peer_depths: list[float], *, coverage: np.ndarray | None = None,
                          ordered_bands: bool = False) -> list[DrawCommand]:
    """Partition unchanged pixels at overlapping world-picture contact depths."""
    alpha = pygame.surfarray.array_alpha(command.surface)
    depth = np.broadcast_to(depth, alpha.shape)
    occupied = alpha != 0
    if not np.any(occupied):
        return [command]
    pieces = []
    if coverage is not None:
        occupied &= coverage
        if not np.any(occupied):
            return [command]
        remainder = command.surface.copy()
        remainder_alpha = pygame.surfarray.pixels_alpha(remainder)
        remainder_alpha[:] *= ~coverage
        del remainder_alpha
        if command.blend == pygame.BLEND_RGB_ADD:
            pygame.surfarray.pixels3d(remainder)[:] *= (~coverage)[:, :, None]
        pieces.append(command._replace(surface=remainder))
    minimum, maximum = float(depth[occupied].min()), float(depth[occupied].max())
    cuts = sorted({value for value in peer_depths if ordered_bands or minimum <= value <= maximum})
    previous = -float("inf")
    for cutoff in (*cuts, float("inf")):
        selected = occupied & (depth > previous) & (depth <= cutoff)
        lower = previous
        previous = cutoff
        xs, ys = np.nonzero(selected)
        if not len(xs):
            continue
        left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        part = command.surface.subsurface((left, top, right - left, bottom - top)).copy()
        part_alpha = pygame.surfarray.pixels_alpha(part)
        part_alpha[:] *= selected[left:right, top:bottom]
        del part_alpha
        if command.blend == pygame.BLEND_RGB_ADD:
            pygame.surfarray.pixels3d(part)[:] *= selected[left:right, top:bottom, None]
        # Coplanar pixels belong behind the vertical billboard.
        if ordered_bands:
            # Sibling materials share a band key. Their changing surface means
            # must not reverse the authored smoke/fire compositing order.
            sort_depth = (nextafter(cutoff, -float("inf")) if cutoff != float("inf")
                          else nextafter(lower, float("inf")) if cuts else command.key[1])
        else:
            sort_depth = min(float(depth[selected].mean()), nextafter(cutoff, -float("inf")))
        pieces.append(command._replace(key=(command.key[0], sort_depth, *command.key[2:]),
            surface=part, destination=(command.destination[0] + left, command.destination[1] + top),
            world_depth=(command.world_depth[left:right, top:bottom]
                         if command.world_depth is not None else None)))
    return pieces


def split_world_depth(commands: list[DrawCommand]) -> list[DrawCommand]:
    """Consume aligned ground depths after other composition, before painter sort."""
    groups: dict[tuple[str, ...], list[int]] = {}
    for index, command in enumerate(commands):
        if command.world_depth_group is not None:
            groups.setdefault(command.world_depth_group, []).append(index)
    group_cuts: dict[tuple[str, ...], list[float]] = {}
    for group, indices in groups.items():
        bounds = [commands[index].surface.get_rect(topleft=commands[index].destination) for index in indices]
        group_cuts[group] = [peer.key[1] for peer in commands
            if peer.world_depth_group != group and peer.key[0] == commands[indices[0]].key[0]
            and any(bound.colliderect(peer.surface.get_rect(topleft=peer.destination)) for bound in bounds)]
    result: list[DrawCommand] = []
    for index, command in enumerate(commands):
        depth = command.world_depth
        if depth is None:
            result.append(command)
            continue
        group = command.world_depth_group
        if group is not None:
            indices = groups[group]
            base = commands[indices[0]].key
            command = command._replace(key=(*base[:4], (*base[4], f"{indices.index(index):08d}")))
            peer_depths = group_cuts[group]
        else:
            bounds = command.surface.get_rect(topleft=command.destination)
            peer_depths = [peer.key[1] for other, peer in enumerate(commands)
                           if other != index and peer.key[0] == command.key[0]
                           and bounds.colliderect(peer.surface.get_rect(topleft=peer.destination))]
        # The attachment has been consumed. Cropped pieces need only their
        # ordinary painter key and retain the original pixels and blend mode.
        cleared = command._replace(world_depth=None, world_depth_group=None)
        result.extend(partition_world_depth(cleared, depth, peer_depths, ordered_bands=group is not None)
                      if peer_depths else (cleared,))
    return result


def split_actor_fixtures(commands: list[DrawCommand], fixtures: list[FixtureDepthSample]) -> list[DrawCommand]:
    """Split at existing overlapping painter depths, never at arbitrary screen offsets.

The actor is a vertical billboard at its ground depth, as in the existing
world painter. Including intersecting world commands in the partition preserves
their ordering too. This is local image composition, not a new depth buffer.
"""
    replacements: dict[int, list[DrawCommand]] = {}
    for fixture in fixtures:
        command = commands[fixture.command_index]
        bounds = command.surface.get_rect(topleft=command.destination)
        peers = [peer for index, peer in enumerate(commands)
                 if index != fixture.command_index and peer.key[0] == command.key[0]
                 and bounds.colliderect(peer.surface.get_rect(topleft=peer.destination))]
        if not peers:
            continue
        registration = fixture.registration
        encoded = _depth_cell(fixture.atlas, registration.cell,
            registration.rows_by_pose[fixture.pose], fixture.frame, fixture.full_size)
        x, y, width, height = fixture.crop
        encoded = encoded[x:x + width, y:y + height]
        low, high = registration.depth_range
        depth = ((encoded.astype(np.float64) - 1) / 65534 * (high - low) + low)
        depth *= registration.pixels_per_unit_by_pose[fixture.pose] * fixture.asset_scale
        depth += command.key[1] + fixture.depth_origin_offset_px
        depth[encoded == 0] = command.key[1]
        pieces = partition_world_depth(command, depth, [peer.key[1] for peer in peers])
        replacements[fixture.command_index] = [part._replace(
            evidence=(*command.evidence, "depth_part", index)) for index, part in enumerate(pieces)]
    return [part for index, command in enumerate(commands)
            for part in replacements.get(index, (command,))]
