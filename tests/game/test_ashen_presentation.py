"""Retained Ashen conditions produce persistent pixels without changing surfaces."""

from copy import deepcopy
from dataclasses import replace
import os
from uuid import UUID

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from dnd.runtime_reset import reset_engine_runtime
from dnd.types.materials import Material
from dnd.types.residues import ObjectResidueState, TileResidueState
from dnd.types.world import CardinalDirection, LightLevel
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.demo import build_demo_intervals
from game.presentation import reduce_interval
from game.projection import Camera, camera_pose
from game.surface_residue import ResidueSurfaceCache, ground_residue_image


@pytest.fixture(scope="module")
def scene():
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    intervals = build_demo_intervals()
    target, _ = reduce_interval(None, intervals[0])
    reset_engine_runtime()
    assert target.senses is not None
    source = next(row for row in target.objects.values() if row.item.boundary_structure is not None
                  and row.item.boundary_structure.structure.value == "wall")
    wall = source.model_copy(update={"placement": source.placement.model_copy(update={
        "position": (20, 20), "boundary_direction": CardinalDirection.EAST,
        "base_height_steps": 0, "top_height_steps": 1})})
    floor = next(tile for tile in target.tiles.values() if tile.surface.base_material is Material.WOOD)
    target.tiles = {position: floor.model_copy(update={"position": position, "tile_uuid": UUID(int=index + 100),
                    "elevation_steps": 0, "residues": ()})
                    for index, position in enumerate((x, y) for x in range(19, 23) for y in range(19, 23))}
    target.objects = {wall.item.item_uuid: wall}
    target.senses = replace(target.senses, visible=set(target.tiles), seen=set(target.tiles), objects={},
                            effective_light_levels={p: LightLevel.BRIGHT_LIGHT for p in target.tiles})
    catalog = load_catalog()
    yield screen, catalog, SurfaceCache(catalog), target
    pygame.quit()


def pixels(scene, target, quadrant):
    screen, catalog, cache, _ = scene
    camera = Camera(quadrant=quadrant, zoom=1, viewport=screen.get_size()).with_focus((20, 20))
    draw_frame(screen, target, catalog, cache, camera, 0, show_grid=False,
               mouse_position=None, show_debug=False)
    return pygame.surfarray.array3d(screen)


@pytest.mark.parametrize("quadrant", range(4))
def test_ashen_floor_state_changes_pixels_and_removal_restores_floor(scene, quadrant):
    _, _, _, initial = scene
    after = deepcopy(initial)
    after.objects = {}
    initial = deepcopy(initial)
    initial.objects = {}
    before = pixels(scene, initial, quadrant)
    for index, position in enumerate(((20, 20), (20, 21), (21, 20), (21, 21))):
        after.tiles[position] = after.tiles[position].model_copy(update={"residues": (
            TileResidueState(condition_uuid=UUID(int=index + 200), residue_id="residue.ashen", description="Ashen"),)})
    visible = pixels(scene, after, quadrant)
    assert np.count_nonzero(np.any(before != visible, axis=2)) > 100
    np.testing.assert_array_equal(pixels(scene, after, quadrant), visible)
    assert np.array_equal(pixels(scene, initial, quadrant), before)


@pytest.mark.parametrize("quadrant", range(4))
def test_only_recorded_camera_facing_wall_side_receives_soot(scene, quadrant):
    _, _, _, initial = scene
    before = pixels(scene, initial, quadrant)
    after = deepcopy(initial)
    identity, wall = next(iter(after.objects.items()))
    after.objects[identity] = wall.model_copy(update={"item": wall.item.model_copy(update={"surface_residues": (
        ObjectResidueState(condition_uuid=UUID(int=300), residue_id="residue.ashen", description="Ashen",
                           faces=(CardinalDirection.WEST,)),)})})
    visible = pixels(scene, after, quadrant)
    visible_face = camera_pose("west", quadrant) in ("e", "s")
    assert np.any(before != visible) == visible_face
    if visible_face:
        assert np.all(visible <= before), "Soot must darken the existing material, never replace it with brighter paint"
    np.testing.assert_array_equal(pixels(scene, after, quadrant), visible)


def test_connected_floor_mask_keeps_internal_edges_and_world_pattern(scene):
    _, catalog, _, _ = scene
    style = catalog.residue_surfaces["residue.ashen"]
    atlas = pygame.image.load(catalog.resources[style.floor_atlas].path).convert_alpha()
    cache = ResidueSurfaceCache(limit_bytes=128 * 1024)
    camera = Camera(zoom=1)
    isolated = ground_residue_image(cache, atlas, style, (20, 20), frozenset({(20, 20)}), camera, (1, 1, 1))
    connected = frozenset((x, y) for x in range(19, 22) for y in range(19, 22))
    joined = ground_residue_image(cache, atlas, style, (20, 20), connected, camera, (1, 1, 1))
    assert pygame.surfarray.array_alpha(joined).sum() > pygame.surfarray.array_alpha(isolated).sum()
    neighbor = ground_residue_image(cache, atlas, style, (21, 20), connected, camera, (1, 1, 1))
    assert pygame.image.tobytes(neighbor, "RGBA") != pygame.image.tobytes(joined, "RGBA")
    for x in range(30):
        ground_residue_image(cache, atlas, style, (x, 20), frozenset({(x, 20)}), camera, (1, 1, 1))
    assert cache.decoded_bytes <= cache.limit_bytes
