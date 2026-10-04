"""Original deterministic particle components on existing observed-owner clocks."""

from math import cos, floor, pi, sin

import pygame

from game.animation_types import ObjectIntake, RisingMotes
from game.draw_commands import DrawCommand
from game.media_blend import SCREEN_BLEND
from game.projection import Camera, painter_key, project_screen


def _dot(identity: tuple[str, ...], position: tuple[float, float], height: float,
         screen: tuple[float, float], color: int, alpha: float,
         size: tuple[float, float], camera: Camera, *, round_shape: bool = False, blend: int = 0) -> DrawCommand:
    width, height_px = max(1, round(size[0]*camera.zoom)), max(1, round(size[1]*camera.zoom))
    image = pygame.Surface((width, height_px), pygame.SRCALPHA)
    rgba = (color >> 16, color >> 8 & 255, color & 255, round(max(0, min(1, alpha))*255))
    if round_shape:
        pygame.draw.ellipse(image, rgba, image.get_rect())
    else:
        image.fill(rgba)
    return DrawCommand(painter_key(position, elevation_steps=height, quadrant=camera.quadrant,
        role='projectile', identity=identity), image,
        (floor(screen[0]-width/2), floor(screen[1]-height_px/2)), blend, identity)


def rising_mote_commands(identity: str, recipe: RisingMotes, origin: tuple[float, float],
                         height: float, elapsed_ms: float, alpha: float,
                         camera: Camera) -> tuple[DrawCommand, ...]:
    if alpha <= 0:
        return ()
    result = []
    for index in range(recipe.count):
        life = (elapsed_ms/recipe.periodMs+index/recipe.count) % 1
        angle = index*2.399
        radius = recipe.radiusCells+life*recipe.radialGrowthCells
        position = (origin[0]+cos(angle)*radius, origin[1]+sin(angle)*radius*recipe.depthRatio)
        elevation = height+life*recipe.heightCells
        screen = project_screen(position, camera, elevation_steps=elevation)
        result.append(_dot((identity,'rising_mote',str(index)),position,elevation,screen,
            recipe.palette[0 if index % recipe.brightEvery else 1],
            alpha*sin(life*pi)*recipe.alpha,recipe.sizePixels,camera,blend=SCREEN_BLEND if recipe.blendMode == "screen" else 0))
    return tuple(result)


def intake_commands(identity: str, recipe: ObjectIntake, origin: tuple[float, float],
                    height: float, hand: tuple[float, float], progress: float,
                    camera: Camera) -> tuple[DrawCommand, ...]:
    if not 0 <= progress < 1.36:
        return ()
    x,y,z = recipe.sourceOffsetCells
    source = project_screen((origin[0]+x,origin[1]+y),camera,elevation_steps=height+z)
    u = min(1,progress)
    u = u*u*(3-2*u)
    result = []
    for index in range(recipe.count):
        v = max(0,min(1,u-index*recipe.delayPerParticle))
        alpha = sin(pi*v)*(1-index/(recipe.count+4))*recipe.alpha
        # Tail reaches the current hand; no frozen body box or invented rig socket.
        alpha *= max(0,min(1,(1.36-progress)/.36))
        point = (source[0]+(hand[0]-source[0])*v,
            source[1]+(hand[1]-source[1])*v-64*camera.zoom*recipe.arcHeightCells*sin(pi*v))
        radius = recipe.radiusPixels[0 if index == 0 else 1]
        result.append(_dot((identity,'object_intake',str(index)),origin,height,point,
            recipe.palette[0 if index % recipe.brightEvery else 1],alpha,(radius*2,radius*2),camera,round_shape=True,blend=SCREEN_BLEND if recipe.blendMode == "screen" else 0))
    return tuple(result)
