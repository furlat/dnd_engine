"""Authored treatment of body/equipment pixels, before independent media layers."""

from math import ceil, sin, floor, pi

import numpy as np
import pygame

from game.condition_types import ConditionBodyDistortion, ConditionLiveCopies, ConditionAbsenceEcho
from game.animation_types import SilhouetteDust


def reveal_body(image: pygame.Surface, coverage: float) -> pygame.Surface:
    """Stable source-pixel dissolve, preserving RGB, registration and transparency."""
    if coverage >= 1:
        return image
    result = image.copy()
    alpha = pygame.surfarray.pixels_alpha(result)
    if coverage <= 0:
        alpha[:] = 0
    else:
        occupied = np.nonzero(alpha)[1]
        if occupied.size:
            top, bottom = occupied.min(), occupied.max()
            x, y = np.indices(result.get_size())
            threshold = (bottom-y)/max(1, bottom-top)*.84 + ((x*73+y*157) % 97)/97*.16
            blend = np.clip((coverage-threshold+.06)/.12, 0, 1)
            alpha[:] = np.rint(alpha * blend*blend*(3-2*blend))
    del alpha
    return result


def ghost_body(image: pygame.Surface, palette: tuple[int, int, int, int], maximum: float,
               *, copies: ConditionLiveCopies | None = None, time_ms: float = 0., slot: int = 0) -> pygame.Surface:
    result = image.copy()
    rgb = pygame.surfarray.pixels3d(result)
    luminance = rgb[:, :, 0] * .2126 + rgb[:, :, 1] * .7152 + rgb[:, :, 2] * .0722
    indices = np.clip((luminance * 4 / maximum).astype(np.int32), 0, 3)
    colors = np.array([((color >> 16) & 255, (color >> 8) & 255, color & 255) for color in palette], dtype=np.uint8)
    rgb[:] = colors[indices]
    del rgb
    if copies is not None:
        x, y = np.indices(result.get_size())
        t = time_ms / 1000
        wave = np.sin(x * copies.waveFrequency[0] + y * copies.waveFrequency[1]
                      - t * copies.waveSpeed[0] + slot * copies.slotPhase)
        wave *= np.sin(y * copies.secondaryRowFrequency - t * copies.waveSpeed[1])
        alpha = pygame.surfarray.pixels_alpha(result)
        alpha[:] = np.rint(alpha * (copies.minimumOpacity + (1 - copies.minimumOpacity) * (.5 + .5 * wave)))
        del alpha
    return result


def absence_silhouette(image: pygame.Surface, recipe: ConditionAbsenceEcho,
                       progress: float, opacity: float) -> pygame.Surface:
    """Accepted fixed source-pixel dissolution; geometry and gear stay intact."""
    result=image.copy()
    rgb=pygame.surfarray.array3d(image).astype(np.float64)
    source_alpha=pygame.surfarray.array_alpha(image).astype(np.float64)
    x,y=np.indices(image.get_size(),dtype=np.uint64)
    n=((((x>>2)+3)*374761393)&0xffffffff)^((((y>>2)+7)*668265263)&0xffffffff)
    n=((n^(n>>13))*1274126177)&0xffffffff
    noise=(n^(n>>16)).astype(np.float64)/4294967295
    p=floor(max(0.,min(1.,progress))*32+.5)/32
    front=(1-y/image.height)*.84+noise*.16
    u=np.clip((p-front+.035)/.07,0,1)
    fade=u*u*(3-2*u) if p<1 else np.ones_like(u)
    rim=np.maximum(0,1-np.abs(front-p)/.035)*sin(pi*p)
    luminance=(rgb[:,:,0]*.2126+rgb[:,:,1]*.7152+rgb[:,:,2]*.0722)/255
    ghost=np.asarray(recipe.ghostBase)+luminance[:,:,None]*np.asarray(recipe.ghostLight)
    pixels=pygame.surfarray.pixels3d(result)
    pixels[:]=np.rint(np.clip(rgb*(1-fade[:,:,None])+ghost*fade[:,:,None]
        +rim[:,:,None]*np.asarray(recipe.rimColor),0,255)).astype(np.uint8)
    del pixels
    padded=np.pad(source_alpha,1)
    edge=np.minimum.reduce((padded[:-2,1:-1],padded[2:,1:-1],padded[1:-1,:-2],padded[1:-1,2:])) < .12*255
    alpha=pygame.surfarray.pixels_alpha(result)
    alpha[:]=np.rint(source_alpha*((1-fade)+fade*np.where(edge,.46,.20+.12*luminance))*opacity)
    del alpha
    return result


def distort_body(image: pygame.Surface, recipe: ConditionBodyDistortion, time_ms: float, strength: float = 1.,
                 ) -> tuple[pygame.Surface, int]:
    """Row displacement pads its canvas; registration never moves the actor anchor."""
    padding = ceil(sum(abs(wave.amplitudePx) for wave in recipe.waves))
    result = pygame.Surface((image.width + padding * 2, image.height), pygame.SRCALPHA)
    for row in range(0, image.height, recipe.bandHeightPx):
        displacement = sum(sin(row * wave.rowFrequency + time_ms / 1000 * wave.timeFrequency)
                           * wave.amplitudePx * strength for wave in recipe.waves)
        height = min(recipe.bandHeightPx, image.height - row)
        result.blit(image, (padding + round(displacement), row), (0, row, image.width, height))
    return result, padding


def silhouette_dust(image: pygame.Surface, recipe: SilhouetteDust, elapsed_ms: float,
                    seed: int, *, affected: np.ndarray | None = None,
                    ) -> tuple[pygame.Surface, tuple[int, int]]:
    """Port of the accepted DustOutcome.js, sampling only actual source alpha.

    Coordinates are source pixels. A caller-supplied native section mask limits
    object erosion; the operator never chooses damage or reconstructs anatomy.
    """
    if elapsed_ms < 0:
        return image, (0, 0)
    t = elapsed_ms / 1000
    erosion = recipe.erosionMs / 1000
    lifetime = recipe.particleLifetimeMs / 1000
    padding = ceil(max(recipe.velocityX * lifetime,
                       sum(abs(v) for v in recipe.velocityY) * lifetime,
                       recipe.gravity * lifetime * lifetime)) + 2
    result = pygame.Surface((image.width + 2*padding, image.height + 2*padding), pygame.SRCALPHA)
    source_alpha = pygame.surfarray.array_alpha(image)
    x, y = np.indices(image.get_size(), dtype=np.uint64)

    def noise(px: np.ndarray, py: np.ndarray) -> np.ndarray:
        # JavaScript Math.imul and >>> wrap exactly at 32 bits.
        n = (((px + (seed & 0xffffffff)*13)*374761393) & 0xffffffff) ^ (((py + (seed & 0xffffffff)*17)*668265263) & 0xffffffff)
        n = ((n ^ (n >> 13))*1274126177) & 0xffffffff
        return n.astype(np.float64)/4294967295

    rank = (1-recipe.horizontalRankWeight)*noise(x,y)+recipe.horizontalRankWeight*x/image.width
    occupied = source_alpha >= recipe.alphaThreshold
    if affected is not None:
        if affected.shape != source_alpha.shape:
            raise ValueError('Native section mask must match the actual source frame')
        occupied &= affected
    removed = occupied & (np.clip(t/erosion, 0, 1) >= rank)
    body = image.copy()
    alpha = pygame.surfarray.pixels_alpha(body)
    alpha[removed] = 0
    del alpha
    result.blit(body, (padding, padding))
    age = t-rank*erosion
    particles = removed & (((y*image.width+x) % recipe.particleEvery) == 0) & (age > 0) & (age < lifetime)
    fade = np.clip(age/(recipe.particleFadeInMs/1000), 0, 1)*(1-age/lifetime)
    vx = (noise(x+9,y+7)-.5)*recipe.velocityX
    vy = recipe.velocityY[0]+noise(x+3,y+41)*recipe.velocityY[1]
    luminance = recipe.minimumLuminance+(1-recipe.minimumLuminance)*noise(x+33,y)
    color = np.array(((recipe.color >> 16)&255,(recipe.color >> 8)&255,recipe.color&255))
    # Painter order is the original source scan order (y then x).
    for iy, ix in np.argwhere(particles.T):
        a = float(age[ix,iy])
        rgb = np.rint(color*luminance[ix,iy]).astype(int)
        rgba = (*map(int,rgb), int(round(float(source_alpha[ix,iy]*fade[ix,iy]))))
        position = (padding+float(ix)+float(vx[ix,iy])*a,
                    padding+float(iy)+float(vy[ix,iy])*a+recipe.gravity*a*a)
        pygame.draw.rect(result, rgba, (*position, max(1,recipe.particleSize), max(1,recipe.particleSize)))
    return result, (-padding, -padding)
