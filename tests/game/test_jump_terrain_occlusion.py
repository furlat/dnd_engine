"""Actual terrain pixels must not bury body pixels above its top plane.

The native uphill/downhill histories share an above-terrace contact. Their
real lower-ground endpoints remain legitimate rear-view occlusion controls.
"""

from typing import Iterator

import numpy as np
import pygame
import pytest

from game.animation import body_elevation_steps
from game.animation_draw import BodyRows
from game.animation_data import load_animation_data
from game.animation_types import AnimationData
from game.app import draw_frame
from game.assets import AssetCatalog, SurfaceCache, load_catalog
from game.motion import MotionTimeline, bind_motion, sample_motion
from game.playback_frame import sample_playback_frame
from game.player_facts import PlayerState
from game.player_reduction import reduce_lineage
from game.projection import Camera, painter_key, project_screen
from game.scene import load_scene_media, scene_actors
from game.animation_draw import LoadedBodyRows
from game.choreography_draw import load_motion_media
from tests.game.movement_scenarios import movement_history
from tests.game.player_helpers import player_history, visible_contact


@pytest.fixture(scope="module")
def renderer() -> Iterator[tuple[AnimationData, AssetCatalog, SurfaceCache]]:
    pygame.init()
    pygame.display.set_mode((640, 480))
    try:
        data, catalog = load_animation_data(), load_catalog()
        yield data, catalog, SurfaceCache(catalog)
    finally:
        pygame.quit()


@pytest.fixture(scope="module")
def histories(renderer: tuple[AnimationData, AssetCatalog, SurfaceCache]) -> dict[
    str, tuple[PlayerState, PlayerState, MotionTimeline, BodyRows]
]:
    data = renderer[0]
    result = {}
    for name, route in (("uphill", ((13, 20), (14, 20))), ("downhill", ((14, 20), (13, 20)))):
        captured = movement_history(route=route, battlefield_id="battlefield.visual_vertical_seam",
                                         behavior="action.jump")
        before, roots = player_history(captured)
        lineage, = roots
        after = reduce_lineage(before, lineage)
        motion = bind_motion(before, lineage, data)
        assert motion is not None
        assert before.tiles[(14, 20)].elevation_steps == 2
        assert before.tiles[(13, 20)].elevation_steps == 0
        body_rows: LoadedBodyRows = {}
        media = load_scene_media(scene_actors(before, data, {}), data, body_rows=body_rows)
        load_motion_media(motion, data, body_rows=body_rows)
        result[name] = before, after, motion, media
    return result


class RaisedTerrainOcclusion(AssertionError):
    """Only this known pixel defect may satisfy its narrow expected failure."""


@pytest.mark.parametrize(("name", "elapsed", "airborne", "quadrant"), [
    pytest.param(name, elapsed, airborne, quadrant,
        id=f"{name}-{'air' if airborne else 'ground'}-q{quadrant}",
        marks=pytest.mark.xfail(strict=True, raises=RaisedTerrainOcclusion,
            reason="Known raised floor/cliff painter hides above-plane body pixels in rear views")
        if airborne and quadrant in (0, 1) else ())
    for name, air_time, ground_time in (("uphill", 500.0, 0.0), ("downhill", 250.0, 750.0))
    for elapsed, airborne in ((air_time, True), (ground_time, False))
    for quadrant in range(4)
])
def test_native_jump_terrain_pixels(
    renderer: tuple[AnimationData, AssetCatalog, SurfaceCache],
    histories: dict[str, tuple[PlayerState, PlayerState, MotionTimeline, BodyRows]],
    name: str, elapsed: float, airborne: bool, quadrant: int,
) -> None:
    data, catalog, cache = renderer
    before, after, motion, media = histories[name]
    height = body_elevation_steps(visible_contact(sample_motion(motion, data, elapsed)), data)
    assert height > 2 if airborne else height == 0
    number, badge = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                     for style in (data.number_style, data.badge_style))
    screen = pygame.Surface((640, 480))
    tiles_by_uuid = {tile.tile_uuid: tile for tile in before.tiles.values()}
    camera = Camera(quadrant=quadrant, zoom=0.75, viewport=screen.get_size()).with_focus(
        (13.5, 20), elevation_steps=1)
    frame = sample_playback_frame(before, after, data, elapsed, elapsed, camera, {}, media,
        number, badge, motion=motion)
    body, = (command for command in frame.commands if command[4][6] == "actor")
    evidence = draw_frame(screen, frame.displayed, catalog, cache, camera, elapsed / 1000,
        collect_evidence=True, show_grid=False, mouse_position=None, show_debug=False, extra_commands=frame.commands)
    assert evidence is not None
    assert evidence.matches
    assert screen.get_rect().contains(body[1].get_bounding_rect().move(body[2]))

    # Compare the complete real frame to the actual authored opaque
    # body pixels, not a painter key or an independently painted proxy.
    pixels = pygame.surfarray.array3d(body[1])
    opaque = pygame.surfarray.array_alpha(body[1]) == 255
    rendered = pygame.surfarray.array3d(screen)[
        body[2][0]:body[2][0] + body[1].get_width(),
        body[2][1]:body[2][1] + body[1].get_height(),
    ]
    missing = opaque & np.any(rendered != pixels, axis=2)
    missing_count = int(np.count_nonzero(missing))
    assert np.count_nonzero(opaque) > 100
    contact = visible_contact(sample_motion(motion, data, elapsed))
    floor_y = project_screen(contact.grid, camera, elevation_steps=2)[1]
    pivot_y = project_screen(contact.grid, camera,
        elevation_steps=body_elevation_steps(contact, data))[1]
    pixel_y = body[2][1] + np.arange(body[1].get_height())[None, :]
    # Billboard pixels above the local flat plane are in front of its
    # surface. A rig frame may place feet below its contact; those
    # pixels are not guaranteed clearance merely by the contact height.
    above_floor = pixel_y + 1 < floor_y
    missing_above_floor = int(np.count_nonzero(missing & above_floor))
    if airborne:
        assert np.count_nonzero(opaque & above_floor) > 100

    # Actual draw evidence identifies the native floor candidates.
    # Deduplicate bands of one asset; the screen comparison above is
    # the authority on which opaque pixels were really covered.
    occluders = []
    body_index = evidence.actual_draws.index(body[4])
    missing_surface = pygame.Surface(body[1].get_size(), pygame.SRCALPHA)
    missing_alpha = pygame.surfarray.pixels_alpha(missing_surface)
    missing_alpha[:] = (missing & above_floor if airborne else missing) * 255
    del missing_alpha
    missing_mask = pygame.mask.from_surface(missing_surface, threshold=254)
    floor_rows = dict.fromkeys(row for row in evidence.actual_draws[body_index + 1:]
                              if len(row) == 6 or (len(row) > 6 and row[6] == "cliff"))
    for row in floor_rows:
        tile = next((tile for identity, tile in tiles_by_uuid.items() if identity == row[0]), None)
        if tile is None:
            continue
        asset_id = row[2]
        assert isinstance(asset_id, str)
        base_height = tile.elevation_steps if len(row) == 6 else row[7]
        assert isinstance(base_height, (int, float))
        surface = cache.scaled(asset_id, camera.zoom)
        destination = cache.blit_position(asset_id, camera.zoom,
            project_screen(tile.position, camera, elevation_steps=base_height))
        offset = destination[0] - body[2][0], destination[1] - body[2][1]
        overlap = missing_mask.overlap_mask(pygame.mask.from_surface(surface, threshold=254), offset)
        if not overlap.count():
            continue
        point = overlap.outline()[0]
        occluders.append({"tile": tile.position, "height": tile.elevation_steps,
            "role": "floor" if len(row) == 6 else "cliff", "asset": asset_id,
            "potential_sheet_overlap": overlap.count(),
            "pixel": (body[2][0] + point[0], body[2][1] + point[1]),
            "key": painter_key(tile.position, elevation_steps=tile.elevation_steps,
                quadrant=quadrant, role="terrain", identity=tile.tile_uuid)})
    detail = str({"airborne": airborne, "quadrant": quadrant,
        "missing": missing_count, "body_height": body[4][7], "body_key": body[0],
        "missing_above_floor": missing_above_floor,
        "opaque_below_pivot": int(np.count_nonzero(opaque & (pixel_y > pivot_y))),
        "opaque_below_floor": int(np.count_nonzero(opaque & ~above_floor)),
        "occluders": occluders})
    if airborne:
        if missing_above_floor:
            raise RaisedTerrainOcclusion(detail)
    else:
        assert (missing_count == 0) == (quadrant in (2, 3)), detail
