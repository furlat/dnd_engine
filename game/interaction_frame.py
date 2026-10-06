"""Use the compositor's final pieces for picking and unobscured outlines."""

from dataclasses import dataclass
from collections.abc import Sequence

import numpy as np
import pygame

from game.draw_commands import DrawCommand
from game.interaction_types import InteractionRegion, SelectionCoverage, WorldHit
from game.projection import Camera, project_screen
from dnd.types.event_facts import WorldTileState


@dataclass(frozen=True, slots=True)
class InteractionFrame:
    regions: tuple[InteractionRegion, ...] = ()


def cut_selection(command: DrawCommand, retained: np.ndarray,
                  crop: tuple[int, int, int, int] | None = None
                  ) -> tuple[tuple[SelectionCoverage, ...], np.ndarray | None]:
    """Apply an already decided visual cut, never recompute depth/visibility."""
    def cut(mask: np.ndarray) -> np.ndarray:
        result = mask & retained
        if crop is not None:
            x, y, width, height = crop
            result = result[x:x + width, y:y + height]
        result.setflags(write=False)
        return result
    return (tuple(SelectionCoverage(row.hit, cut(row.mask)) for row in command.selection),
            cut(command.selection_block_mask) if command.selection_block_mask is not None else None)


def align_coverage(mask: np.ndarray, destination: tuple[int, int], command: DrawCommand) -> np.ndarray:
    """Register a physical/selection source within a padded visual command."""
    result = np.zeros(command.surface.get_size(), dtype=bool)
    left, top = destination[0] - command.destination[0], destination[1] - command.destination[1]
    source = pygame.Rect(left, top, *mask.shape)
    overlap = source.clip(command.surface.get_rect())
    if overlap:
        result[overlap.left:overlap.right, overlap.top:overlap.bottom] = mask[
            overlap.left-left:overlap.right-left, overlap.top-top:overlap.bottom-top]
    result.setflags(write=False)
    return result


def compose_interaction_frame(commands: Sequence[DrawCommand], viewport: tuple[int, int]) -> InteractionFrame:
    """Subtract foreground physical coverage in the painter's actual order."""
    covered = np.zeros(viewport, dtype=bool)
    regions = []
    for order in range(len(commands) - 1, -1, -1):
        command = commands[order]
        if command.surface.get_alpha() == 0:
            continue
        bounds = pygame.Rect(command.destination, command.surface.get_size())
        overlap = bounds.clip(pygame.Rect((0, 0), viewport))
        if not overlap:
            continue
        local = (slice(overlap.left-bounds.left, overlap.right-bounds.left),
                 slice(overlap.top-bounds.top, overlap.bottom-bounds.top))
        screen_region = (slice(overlap.left, overlap.right), slice(overlap.top, overlap.bottom))
        for selection in command.selection:
            mask = selection.mask[local] & ~covered[screen_region]
            if np.any(mask):
                mask.setflags(write=False)
                regions.append(InteractionRegion(selection.hit, overlap.topleft, mask, order))
        if command.selection_occluder:
            physical = (command.selection_block_mask if command.selection_block_mask is not None
                        else pygame.surfarray.array_alpha(command.surface) > 0)
            covered[screen_region] |= physical[local]
    return InteractionFrame(tuple(regions))


def pick_world(frame: InteractionFrame, point: tuple[int, int]) -> WorldHit | None:
    aperture = None
    for region in frame.regions:
        x, y = point[0]-region.destination[0], point[1]-region.destination[1]
        if not (0 <= x < region.mask.shape[0] and 0 <= y < region.mask.shape[1] and region.mask[x,y]):
            continue
        if region.hit.kind == "aperture":
            aperture = aperture or region.hit
        elif region.hit.kind == "ground":
            return aperture or region.hit
        else:
            return region.hit
    return aperture


def draw_highlights(screen: pygame.Surface, frame: InteractionFrame,
                    selected: Sequence[tuple[WorldHit, tuple[int, int, int]]], *, width: int = 2) -> None:
    """Outline the already visible coverage, with no recoloring of scene pixels."""
    chosen = {(hit.kind, hit.identity): color for hit, color in selected}
    for region in reversed(frame.regions):
        color = chosen.get((region.hit.kind, region.hit.identity))
        if color is None:
            continue
        padded = np.pad(region.mask, width)
        sx, sy = region.mask.shape
        interior = region.mask.copy()
        for dx, dy in ((width, 0), (-width, 0), (0, width), (0, -width)):
            interior &= padded[width+dx:width+dx+sx, width+dy:width+dy+sy]
        image = pygame.Surface(region.mask.shape, pygame.SRCALPHA)
        image.fill((*color, 0))
        pygame.surfarray.pixels_alpha(image)[:] = (region.mask & ~interior) * 255
        screen.blit(image, region.destination)


def support_selection(command: DrawCommand, tile: WorldTileState, camera: Camera) -> DrawCommand:
    """A disclosed support top uses the terrain command's actual surviving pixels."""
    image = pygame.Surface(command.surface.get_size(), pygame.SRCALPHA)
    x,y=tile.position
    corners=tuple(project_screen((x+dx,y+dy),camera,elevation_steps=tile.elevation_steps)
        for dx,dy in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)))
    pygame.draw.polygon(image,'white',[(round(px-command.destination[0]),round(py-command.destination[1]))
        for px,py in corners])
    mask=(pygame.surfarray.array_alpha(image)>0)&(pygame.surfarray.array_alpha(command.surface)>0)
    mask.setflags(write=False)
    coverage=SelectionCoverage(WorldHit('ground',str(tile.tile_uuid),tile.position,tile.elevation_steps),mask)
    return command._replace(selection=(*command.selection,coverage))
