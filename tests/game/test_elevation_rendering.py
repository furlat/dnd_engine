"""Cliff and stair assembly through detached world facts and real frames."""

from copy import deepcopy
from dataclasses import replace
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection, LightLevel
from dnd.types.materials import Material
from dnd.types.world_placement import BoundaryStructureKind
from game.app import BACKGROUND, build_demo_intervals, draw_frame
from game.assets import SurfaceCache, load_catalog
from game.presentation import reduce_interval
from game.projection import Camera, pick_support, project_screen


STAIR_POSITIONS = ((16, 24), (16, 23), (16, 22))


@pytest.fixture(scope="module")
def rendering():
    intervals = build_demo_intervals()
    reset_engine_runtime()
    target, _ = reduce_interval(None, intervals[0])
    pygame.init()
    screen = pygame.display.set_mode((960, 720))
    catalog = load_catalog()
    cache = SurfaceCache(catalog)
    yield target, screen, catalog, cache
    pygame.quit()


def test_detached_world_contains_one_support_per_xy_and_a_real_stair_run(rendering):
    target, _, _, _ = rendering
    assert len(target.tiles) == 4096
    assert len({tile.tile_uuid for tile in target.tiles.values()}) == 4096
    assert {
        position: tile.elevation_steps
        for position, tile in target.tiles.items() if tile.elevation_steps != 0
    } == {
        **{(x, y): 2 for x in range(14, 19) for y in range(18, 25)
           if (x, y) not in STAIR_POSITIONS[:2]},
        (16, 23): 1,
    }
    assert [
        (target.tiles[p].elevation_steps, target.tiles[p].surface_kind,
         target.tiles[p].slope_axis)
        for p in STAIR_POSITIONS
    ] == [(h, ElevationSurfaceKind.STAIRS, SlopeAxis.NORTH_SOUTH) for h in range(3)]
    high_floor = [t for t in target.tiles.values()
                  if t.elevation_steps == 2 and t.surface_kind is ElevationSurfaceKind.ORDINARY]
    assert len(high_floor) == 32
    assert all(t.surface.base_material is Material.WOOD for t in high_floor)
    assert all(target.tiles[p].surface.base_material is Material.EARTH for p in STAIR_POSITIONS)
    assert target.tiles[(16, 25)].surface.base_material is Material.EARTH
    for p in ((15, 23), (17, 23), (15, 24), (17, 24)):
        assert target.tiles[p].elevation_steps == 2
    # The new banks are separated from all house wall owners by six cells.
    assert min(max(abs(t.position[0]-obj.placement.position[0]),
                   abs(t.position[1]-obj.placement.position[1]))
               for t in high_floor for obj in target.objects.values()
               if obj.item.boundary_structure is not None) >= 6


@pytest.mark.parametrize("q,pose", enumerate("swne"))
def test_whole_stair_frame_retains_contacts_and_individual_support_knowledge(rendering, q, pose):
    original, screen, catalog, cache = rendering
    target = deepcopy(original)
    low, mid, high = STAIR_POSITIONS
    target.senses = replace(
        target.senses,
        visible={low}, seen={low, mid}, objects={},
        effective_light_levels={low: LightLevel.BRIGHT_LIGHT},
    )
    camera = Camera(quadrant=q, zoom=1.0, viewport=screen.get_size()).with_focus(mid, elevation_steps=1)
    evidence = draw_frame(screen, target, catalog, cache, camera, .2,
                          show_grid=False, mouse_position=None)
    assert evidence.matches
    flights = [row for row in evidence.actual_draws if len(row) > 6 and row[6] == "stairs"]
    assert len(flights) == 1
    flight = flights[0]
    assert flight[2] == f"terrain.stairs.{pose}"
    assert flight[3:6] == ("structural", None, "world.authored")
    assert flight[7] == tuple(
        (target.tiles[p].tile_uuid, p, h, state, level)
        for p, h, state, level in zip(
            STAIR_POSITIONS, range(3), ("current", "memory", "authored"), (3, None, None), strict=True
        )
    )
    assert flight[8] == tuple(project_screen(p, camera, elevation_steps=h)
                              for h, p in enumerate(STAIR_POSITIONS))
    # Calibrated contacts belong to the PNG, independently of the evidence.
    contacts = {
        "e": ((160, 224), (96, 128), (32, 32)),
        "s": ((96, 224), (160, 128), (224, 32)),
        "w": ((96, 192), (160, 160), (224, 128)),
        "n": ((160, 192), (96, 160), (32, 128)),
    }[pose]
    origin = cache.blit_position(flight[2], camera.zoom, flight[8][0])
    assert tuple((origin[0] + x, origin[1] + y) for x, y in contacts) == flight[8]
    assert tuple(map(tuple, catalog.bindings["terrain_stairs"]["contacts_px"][pose])) == contacts
    for h, p in enumerate(STAIR_POSITIONS):
        chosen, heights = pick_support(project_screen(p, camera, elevation_steps=h), camera,
                                      (target.tiles[p],))
        assert chosen.tile_uuid == target.tiles[p].tile_uuid
        assert heights == (h,)
    mid_id = target.tiles[mid].tile_uuid
    assert not any(row[0] == mid_id and len(row) == 6 for row in evidence.actual_draws)
    assert any(row[0] == mid_id and row[6] == "terrain_bed" for row in evidence.actual_draws)


@pytest.mark.parametrize("q", range(4))
def test_terrace_frames_have_cliff_corners_and_no_void_below_the_flight(rendering, q):
    target, screen, catalog, cache = rendering
    camera = Camera(quadrant=q, zoom=1.0, viewport=screen.get_size()).with_focus((16, 22))
    evidence = draw_frame(screen, target, catalog, cache, camera, .2,
                          show_grid=False, mouse_position=None)
    cliffs = [row for row in evidence.actual_draws if len(row) > 6 and row[6] == "cliff"]
    assert len(cliffs) == 21  # 19 outer-rim owners plus two inner bank faces
    assert sum("corner" in row[2] for row in cliffs) == 6
    assert all(row[3:6] == ("structural", None, "world.authored") for row in cliffs)
    # Interior of the solid base around the opening must contain actual
    # terrain/flight/cliff pixels, not exposed framebuffer background.
    for position in ((15.5, 22.5), (16, 23), (16.5, 22.5)):
        x, y = map(round, project_screen(position, camera))
        assert tuple(screen.get_at((x, y)))[:3] != BACKGROUND
    lower = target.tiles[STAIR_POSITIONS[0]]
    middle = target.tiles[STAIR_POSITIONS[1]]
    for bank in ((15, 23), (17, 23)):
        face = next(row for row in cliffs if row[0] == target.tiles[bank].tile_uuid)
        assert face[7:9] == (0, 2)
        assert {fact[0] for fact in face[9]} >= {lower.tile_uuid, middle.tile_uuid}
    assert all(row[2].startswith("terrain.earth.") for row in evidence.actual_draws
               if len(row) > 6 and row[6] == "terrain_bed")
    assert any(row[2].startswith("terrain.wood.") for row in evidence.actual_draws if len(row) == 6)


@pytest.mark.parametrize("q", range(4))
def test_hover_picks_actual_raised_support_in_the_complete_world(rendering, q):
    target, screen, _, _ = rendering
    position = (16, 20)
    tile = target.tiles[position]
    camera = Camera(quadrant=q, zoom=.5, viewport=screen.get_size()).with_focus(
        position, elevation_steps=2).with_screen_pan((57, -31))
    chosen, heights = pick_support(
        project_screen(position, camera, elevation_steps=2), camera, target.tiles.values())
    assert chosen.tile_uuid == tile.tile_uuid
    assert (chosen.position, chosen.elevation_steps) == (position, 2)
    assert heights == (0, 1, 2)


@pytest.mark.parametrize("wall_position,foreground", [((19, 20), "floor"), ((20, 21), "wall")])
def test_raised_floor_and_lower_wall_occlude_in_physical_depth_order(rendering, wall_position, foreground):
    original, screen, catalog, cache = rendering
    target = deepcopy(original)
    floor_position = (20, 20)
    tile = target.tiles[floor_position].model_copy(update={"elevation_steps": 2})
    target.tiles = {floor_position: tile}
    wall = next(obj for obj in target.objects.values()
                if obj.item.boundary_structure is not None
                and obj.item.boundary_structure.structure is BoundaryStructureKind.WALL
                and obj.item.boundary_structure.material is Material.STONE)
    wall = wall.model_copy(update={"placement": wall.placement.model_copy(update={
        "position": wall_position, "base_height_steps": 0,
        "boundary_direction": CardinalDirection.EAST,
    })})
    target.objects = {wall.item.item_uuid: wall}
    target.senses = replace(target.senses, visible=set(), seen=set(), objects={})
    # Keep the sprite overlap away from the screen-center debug reticle.
    camera = Camera(zoom=1.0, viewport=screen.get_size()).with_focus(
        floor_position, elevation_steps=2).with_screen_pan((120, 60))
    evidence = draw_frame(screen, target, catalog, cache, camera, .2,
                          show_grid=False, mouse_position=None)
    assert evidence.matches
    layers = {}
    authored_rgb = tuple(catalog.bindings["treatments"]["authored"]["rgb"])
    for label, asset, position, height in (
        ("floor", catalog.bindings["terrain"]["earth"]["e"], floor_position, 2),
        ("wall", catalog.bindings["stone_wall_straight"]["e"], wall_position, 0),
    ):
        layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        layer.blit(cache.treated(asset, 1.0, authored_rgb), cache.blit_position(
            asset, 1.0, project_screen(position, camera, elevation_steps=height)))
        layers[label] = layer
    overlap = (pygame.surfarray.array_alpha(layers["floor"]) == 255) & (
        pygame.surfarray.array_alpha(layers["wall"]) == 255)
    # Hundreds of real opaque art pixels overlap in each direction, not
    # transparent canvas margins or an ordering-key-only assertion.
    assert np.count_nonzero(overlap) > 250
    actual = pygame.surfarray.array3d(screen)
    expected = pygame.surfarray.array3d(layers[foreground])
    assert np.array_equal(actual[overlap], expected[overlap])


def test_missing_stair_middle_is_not_silently_drawn_as_floor(rendering):
    original, screen, catalog, cache = rendering
    target = deepcopy(original)
    target.tiles.pop(STAIR_POSITIONS[1])
    with pytest.raises(RuntimeError, match="three-support stair run"):
        draw_frame(screen, target, catalog, cache, Camera(viewport=screen.get_size()),
                   .2, show_grid=False, mouse_position=None)


def test_continuous_six_support_slope_is_not_two_complete_flights(rendering):
    original, screen, catalog, cache = rendering
    target = deepcopy(original)
    # Two adjacent three-support sprites would leave the 2->3 riser unshown.
    # The public renderer must reject this unsupported shape, not fill it in.
    target.tiles = {
        (16, 24 - h): target.tiles[(16, 24 - h)].model_copy(update={
            "elevation_steps": h, "surface_kind": ElevationSurfaceKind.STAIRS,
            "slope_axis": SlopeAxis.NORTH_SOUTH,
            "surface": target.tiles[STAIR_POSITIONS[0]].surface,
        }) for h in range(6)
    }
    target.objects = {}
    with pytest.raises(RuntimeError, match="unsupported"):
        draw_frame(screen, target, catalog, cache, Camera(viewport=screen.get_size()),
                   .2, show_grid=False, mouse_position=None)
