"""Rasterize the blood handoff's small shared droplet vocabulary."""

from math import ceil, floor, hypot

import pygame

from game.animation_types import BloodResponse, ParticleMediaAsset
from game.particle_media import ParticleSample
from game.projection import Camera, project_screen


def blood_particle_image(particle: ParticleSample, response: BloodResponse,
                          asset: ParticleMediaAsset, colors: tuple[int, int],
                          camera: Camera, scale: float) -> tuple[pygame.Surface, tuple[int, int]]:
    head = project_screen(particle.grid, camera, elevation_steps=particle.elevation)
    previous = project_screen(particle.previous_grid, camera, elevation_steps=particle.previous_elevation)
    dx, dy = head[0] - previous[0], head[1] - previous[1]
    distance = hypot(dx, dy)
    ux, uy = (dx / distance, dy / distance) if distance else (1., 0.)
    factor = camera.zoom * scale
    snap = asset.snapPx * camera.zoom
    head = round(head[0] / snap) * snap, round(head[1] / snap) * snap
    size = particle.size * camera.zoom
    length = min(asset.tailMaxPx * factor * response.tailScale,
                 max(asset.tailMinPx * factor, distance * response.tailScale))
    shapes = []

    def rectangle(x: float, y: float, width: float, height: float, color: int) -> None:
        shapes.append((tuple((head[0] + a * ux - b * uy, head[1] + a * uy + b * ux)
            for a, b in ((x, y), (x + width, y), (x + width, y + height), (x, y + height))), color))

    if response.shape == "frozen":
        # The same world-space piece shrinks as its own ground kernel melts.
        radius = (particle.size * .45 + .2) * particle.solid ** (1 / 3) / 64
        corners = ((-radius, -radius), (radius, -radius), (radius, radius), (-radius, radius))
        low = tuple(project_screen((particle.grid[0]+x, particle.grid[1]+y), camera,
                    elevation_steps=particle.elevation) for x, y in corners)
        high = tuple(project_screen((particle.grid[0]+x, particle.grid[1]+y), camera,
                    elevation_steps=particle.elevation+2*radius) for x, y in corners)
        # Select camera-near sides; physics and fragment size never rotate with the camera.
        first = (1-camera.quadrant) % 4
        for index in (first, (first + 1) % 4):
            other = (index + 1) % 4
            shapes.append(((high[index], high[other], low[other], low[index]), colors[0]))
        shapes.append((high, colors[1]))
    else:
        if response.shape == "bead":
            rectangle(-length*1.5, -size*.35, length*1.5, size*.7, colors[0])
            rectangle(-size, -size, size*2, size*2, colors[0])
        else:
            rectangle(-length, -size, length+2*factor, size*2, colors[0])
            if response.shape == "ragged":
                rectangle(-length-factor, -size*.3, length+size+2*factor, size, colors[0])
        rectangle(-factor, -size, max(factor, 2*factor), max(factor, size*.45), colors[1])
        detail = response.detail
        if detail == "lightning" and int(particle.age*24+particle.identity) % 4 == 0:
            rectangle(-length*.6, 0, max(factor, length*.3), factor, 0xC0C5CB)
        elif detail == "poison":
            rectangle(-length*.85, -size*.2, max(factor,length*.75), max(factor,size*.5), 0x858E35)
            rectangle(-size*.5, -size*.65, max(factor,size*.6), factor, 0xC6B978)
        elif detail == "acid":
            rectangle(-size*.7, -size*.4, max(factor,size), factor, 0xB9AD54)
            rectangle(0, 0, factor, factor, 0x361014)
        elif detail == "radiant":
            rectangle(-length*.65, -size*.2, max(factor,length*.35), factor, 0xD4B56B)
        elif detail == "necrotic":
            rectangle(-length*.5, 0, max(factor,size), factor, 0x536D38)
    left = floor(min(x for points, _ in shapes for x, _ in points))
    top = floor(min(y for points, _ in shapes for _, y in points))
    right = ceil(max(x for points, _ in shapes for x, _ in points))
    bottom = ceil(max(y for points, _ in shapes for _, y in points))
    image = pygame.Surface((max(1,right-left+1),max(1,bottom-top+1)),pygame.SRCALPHA)
    for points, color in shapes:
        pygame.draw.polygon(image, (color>>16&255,color>>8&255,color&255),
                            tuple((x-left,y-top) for x,y in points))
    return image, (left, top)
