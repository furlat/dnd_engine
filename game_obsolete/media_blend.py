"""Authored screen blending at the existing command compositor boundary."""

from functools import lru_cache
from typing import Sequence

import numpy as np
import pygame

from game.draw_commands import DrawCommand

# Outside SDL's special_flags domain; ordinary flags pass through unchanged.
SCREEN_BLEND = -1


def blit_media(destination: pygame.Surface, source: pygame.Surface,
               point: tuple[int, int], blend: int) -> pygame.Rect:
    if blend != SCREEN_BLEND:
        return destination.blit(source, point, special_flags=blend)
    rect = source.get_rect(topleft=point).clip(destination.get_rect()).clip(destination.get_clip())
    if not rect.width or not rect.height:
        return rect
    source_rect = pygame.Rect(rect.x-point[0],rect.y-point[1],rect.width,rect.height)
    front, back = source.subsurface(source_rect), destination.subsurface(rect)
    cs = pygame.surfarray.array3d(front).astype(np.float64)/255
    cb = pygame.surfarray.array3d(back).astype(np.float64)/255
    a = pygame.surfarray.array_alpha(front).astype(np.float64)/255
    alpha = source.get_alpha()
    if alpha is not None:
        a *= alpha/255
    key = source.get_colorkey()
    if key is not None:
        a[np.all(pygame.surfarray.array3d(front) == np.array(key[:3]),axis=2)] = 0
    b = pygame.surfarray.array_alpha(back).astype(np.float64)/255
    out_alpha = a+b*(1-a)
    # W3C source-over with B(Cb,Cs)=Cb+Cs-Cb*Cs, including a transparent target.
    premultiplied = a[...,None]*cs+b[...,None]*cb*(1-a[...,None]*cs)
    rgb = np.divide(premultiplied,out_alpha[...,None],out=np.zeros_like(cs),where=out_alpha[...,None]>0)
    pixels = pygame.surfarray.pixels3d(back)
    pixels[:] = np.rint(np.clip(rgb,0,1)*255).astype(np.uint8)
    del pixels
    if destination.get_flags() & pygame.SRCALPHA:
        pixels_alpha = pygame.surfarray.pixels_alpha(back)
        pixels_alpha[:] = np.rint(np.clip(out_alpha,0,1)*255).astype(np.uint8)
        del pixels_alpha
    return rect


@lru_cache(maxsize=8)
def _mix_buffer(size: tuple[int, int]) -> tuple[pygame.Surface, np.ndarray, np.ndarray]:
    """Scratch is consumed synchronously; no draw command retains this buffer."""
    return (pygame.Surface(size, pygame.SRCALPHA), np.zeros(size, dtype=np.float32),
            np.zeros((*size, 3), dtype=np.float32))


def _blit_mixed(destination: pygame.Surface, commands: Sequence[DrawCommand]) -> None:
    bounds = commands[0].surface.get_rect(topleft=commands[0].destination)
    for command in commands[1:]:
        bounds.union_ip(command.surface.get_rect(topleft=command.destination))
    bounds = bounds.clip(destination.get_rect()).clip(destination.get_clip())
    if not bounds.width or not bounds.height:
        return
    size = ((bounds.width+63)//64*64, (bounds.height+63)//64*64)
    buffer, all_alpha, all_color = _mix_buffer(size)
    alpha, color = all_alpha[:bounds.width,:bounds.height], all_color[:bounds.width,:bounds.height]
    alpha.fill(0);color.fill(0)
    for command in commands:
        if command.blend != 0:
            raise ValueError('Weighted frame mixing requires original normal-alpha media')
        source_bounds = command.surface.get_rect(topleft=command.destination)
        overlap = source_bounds.clip(bounds)
        if not overlap.width or not overlap.height:
            continue
        source = command.surface.subsurface(overlap.move(-source_bounds.left,-source_bounds.top))
        opacity = pygame.surfarray.array_alpha(source).astype(np.float32)/255
        surface_alpha = source.get_alpha()
        if surface_alpha is not None:
            opacity *= surface_alpha/255
        region = (slice(overlap.left-bounds.left,overlap.right-bounds.left),
                  slice(overlap.top-bounds.top,overlap.bottom-bounds.top))
        alpha[region] += opacity
        color[region] += pygame.surfarray.array3d(source)*opacity[...,None]
    rgb = pygame.surfarray.pixels3d(buffer)
    rgb[:bounds.width,:bounds.height] = np.rint(np.clip(np.divide(color,alpha[...,None],
        out=color,where=alpha[...,None]>0),0,255)).astype(np.uint8)
    del rgb
    opacity = pygame.surfarray.pixels_alpha(buffer)
    opacity[:bounds.width,:bounds.height] = np.rint(np.clip(alpha,0,1)*255).astype(np.uint8)
    del opacity
    destination.blit(buffer,bounds.topleft,area=(0,0,bounds.width,bounds.height))


def blit_media_commands(destination: pygame.Surface, commands: Sequence[DrawCommand]) -> None:
    """Preserve world ordering, mixing source samples only within one depth band."""
    groups: dict[tuple[tuple[str,...],tuple],list[DrawCommand]] = {}
    for command in commands:
        if command.media_mix_group is not None:
            groups.setdefault((command.media_mix_group,command.key[:4]),[]).append(command)
    drawn = set()
    for command in commands:
        if command.media_mix_group is None:
            blit_media(destination,command.surface,command.destination,command.blend)
            continue
        key = command.media_mix_group,command.key[:4]
        if key not in drawn:
            _blit_mixed(destination,groups[key]);drawn.add(key)
