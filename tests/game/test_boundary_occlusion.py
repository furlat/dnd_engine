"""An unpainted part of a finite wall face is not an opening."""

from uuid import uuid4

import pygame
import pytest

from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementKind
from game.area_media import BoundarySprite
from game.boundary_occlusion import clip_actor_boundaries
from game.draw_commands import DrawCommand
from game.projection import Camera, painter_key, project_screen


@pytest.mark.parametrize('quadrant', range(4))
def test_actor_close_to_wall_cannot_leak_past_its_sloping_face(quadrant):
    camera = Camera(quadrant=quadrant, zoom=1, viewport=(600,450)).with_focus((5.5,4))
    placement = WorldObjectPlacement(kind=WorldPlacementKind.BOUNDARY, position=(5,4),
        object_uuid=uuid4(), tile_uuid=uuid4(), occupies_bands=False,
        boundary_direction=CardinalDirection.EAST, base_height_steps=0, top_height_steps=2)
    image = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    image.fill('red')
    behind = (5.4,4) if quadrant in (0,1) else (5.6,4)
    command = DrawCommand(painter_key(behind, elevation_steps=0, quadrant=quadrant,
        role='actor', identity='actor'), image, (0,0), 0, (), role='actor')
    boundary = BoundarySprite((placement,), image, (0,0), (100,0,0,0,()), actor_occludes=True)
    clipped, = clip_actor_boundaries([command], [boundary], camera)
    for tangent in (-.4, 0, .4):
        point = tuple(round(v) for v in project_screen((5.5,4+tangent), camera, elevation_steps=.5))
        assert clipped.surface.get_at(point).a == 0
    # An exaggerated attack pose cannot put a foot/weapon on the ground beyond
    # a wall while its owner is still behind the boundary.
    below = tuple(round(v) for v in project_screen((5.5,4), camera, elevation_steps=-.1))
    assert clipped.surface.get_at(below).a == 0


@pytest.mark.parametrize('quadrant',range(4))
def test_actor_is_hidden_by_unpainted_wall_face_but_visible_through_aperture(quadrant):
    camera = Camera(quadrant=quadrant,zoom=1,viewport=(600,450)).with_focus((5.5,4))
    placement = WorldObjectPlacement(kind=WorldPlacementKind.BOUNDARY,position=(5,4),
        object_uuid=uuid4(),tile_uuid=uuid4(),occupies_bands=False,boundary_direction=CardinalDirection.EAST,
        base_height_steps=0,top_height_steps=2)
    empty_art = pygame.Surface(camera.viewport,pygame.SRCALPHA)
    opening = pygame.Surface(camera.viewport,pygame.SRCALPHA)
    aperture_point = tuple(round(v) for v in project_screen((5.5,4),camera,elevation_steps=1))
    opening.fill('white',pygame.Rect(aperture_point[0]-8,aperture_point[1]-8,16,16))
    wall = BoundarySprite((placement,),empty_art,(0,0),(100,0,0,0,()),
                          actor_aperture=opening,actor_occludes=True)
    far_position = (5,4) if quadrant in (0,1) else (6,4)
    body = pygame.Surface(camera.viewport,pygame.SRCALPHA);body.fill('red')
    command = DrawCommand(painter_key(far_position,elevation_steps=0,quadrant=quadrant,
        role='actor',identity='actor'),body,(0,0),0,(),role='actor')
    clipped, = clip_actor_boundaries([command],[wall],camera)
    opaque_point = tuple(round(v) for v in project_screen((5.5,4),camera,elevation_steps=.5))
    assert clipped.surface.get_at(opaque_point).a == 0
    assert clipped.surface.get_at(aperture_point).a == 255
    above = tuple(round(v) for v in project_screen((5.5,4),camera,elevation_steps=3))
    assert clipped.surface.get_at(above).a == 255
    outside_end = tuple(round(v) for v in project_screen((5.5,5),camera,elevation_steps=.5))
    assert clipped.surface.get_at(outside_end).a == 255
    near_position = (6,4) if quadrant in (0,1) else (5,4)
    near = command._replace(key=painter_key(near_position,elevation_steps=0,quadrant=quadrant,
        role='actor',identity='actor'))
    near_draw, = clip_actor_boundaries([near],[wall],camera)
    assert near_draw.surface.get_at(opaque_point).a == 255
    assert body.get_at(opaque_point).a == 255  # Cached source pixels remain intact.


@pytest.mark.parametrize('support_height', (0, 2))
def test_shadow_stays_on_its_owners_side_of_wall(support_height):
    camera = Camera(quadrant=0,zoom=1,viewport=(600,450)).with_focus((5.5,4))
    placement = WorldObjectPlacement(kind=WorldPlacementKind.BOUNDARY,position=(5,4),
        object_uuid=uuid4(),tile_uuid=uuid4(),occupies_bands=False,
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=support_height,top_height_steps=support_height+2)
    image = pygame.Surface(camera.viewport,pygame.SRCALPHA)
    image.fill('red')
    command = DrawCommand(painter_key((5.2,4),elevation_steps=support_height,quadrant=0,
        role='actor_shadow',identity='shadow'),image,(0,0),0,(),role='actor_shadow',
        support_height_steps=support_height)
    wall = BoundarySprite((placement,),image,(0,0),(100,0,0,0,()),actor_occludes=True)
    clipped, = clip_actor_boundaries([command],[wall],camera)
    # The shadow cannot leak through the wall onto the foreground support.
    assert clipped.surface.get_at((320,212-support_height*64)).a == 0
    assert clipped.surface.get_at((320,250-support_height*64)).a == 0
    near = command._replace(key=painter_key((5.8,4), elevation_steps=support_height,
        quadrant=0, role='actor_shadow', identity='shadow'))
    near_draw, = clip_actor_boundaries([near], [wall], camera)
    # Once across, its ground shadow is visible on this side, but still cannot
    # paint over the upright wall face behind it.
    assert near_draw.surface.get_at((320,250-support_height*64)).a == 255
    assert near_draw.surface.get_at((320,212-support_height*64)).a == 0


def test_cleared_boundary_stops_occluding_actor_pixels():
    camera = Camera(viewport=(100,100))
    body = pygame.Surface(camera.viewport,pygame.SRCALPHA);body.fill('red')
    command = DrawCommand((100,0,0,0,()),body,(0,0),0,(),role='actor')
    wall = BoundarySprite((),body,(0,0),(100,1,0,0,()))
    result, = clip_actor_boundaries([command],[wall],camera)
    assert result.surface is body
