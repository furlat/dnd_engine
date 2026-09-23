"""Authored fields preserve observed receiving cells, phase clocks and depth."""

from dataclasses import replace

import pygame
import pytest

from dnd.core.presentation_geometry import CubePresentationGeometry, SpherePresentationGeometry
from devtools.animation_review.control_cases import control_spell_history
from game.animation_data import load_animation_data
from game.animation_types import SpatialMediaBinding, SpatialMediaLayer
from game.maintained_media import maintained_media_frame, maintained_removal_duration
from game.player_reduction import reduce_lineage
from game.projection import Camera, HEIGHT_STEP_PIXELS
from game.spatial_field_media import field_media_commands
from game.spatial_media_draw import spatial_media_draw_commands
from game.spatial_media_lifetime import SpatialMediaLifetime
from tests.game.player_helpers import player_history


FLOOR_APPLY = "liquid.water.s0.floor.application"
FLOOR_HOLD = "liquid.water.s0.floor.sustain"
AIR = "liquid.water.s0.air.application"


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    pygame.display.set_mode((640, 480))
    data = load_animation_data()
    before, roots = player_history(control_spell_history(program="silence"))
    state = reduce_lineage(before, roots[0])
    yield data, state
    pygame.quit()


def picture(commands):
    surface = pygame.Surface((640, 480), pygame.SRCALPHA)
    for command in sorted(commands, key=lambda item: item.key):
        surface.blit(command.surface, command.destination, special_flags=command.blend)
    return pygame.image.tobytes(surface, "RGBA")


def binding(layer):
    return SpatialMediaBinding(layers=(layer,), holdStartFrame=0, holdFrames=288, fps=144., scale=1.)


def test_explicit_application_hold_clear_windows_and_stagger_have_one_clock(rendering):
    data, _ = rendering
    layer = SpatialMediaLayer(assetId=FLOOR_HOLD, applicationAssetId=FLOOR_APPLY,
        removalAssetId=FLOOR_APPLY, composition="floor", delayMs=250.)
    authored = binding(layer)
    assert maintained_media_frame(data, authored, layer, 1200., 1000.) is None
    assert maintained_media_frame(data, authored, layer, 1250., 1000.) == (FLOOR_APPLY, 0)
    assert maintained_media_frame(data, authored, layer, 1750., 1000.) == (FLOOR_APPLY, 72)
    assert maintained_media_frame(data, authored, layer, 7250., 1000.) == (FLOOR_HOLD, 0)
    assert maintained_media_frame(data, authored, layer, 9250., 1000.) == (FLOOR_HOLD, 0)
    # Removal uses the authored clear, not a restarted intro or frozen hold.
    assert maintained_media_frame(data, authored, layer, 10250., 1000., 10000.) == (FLOOR_APPLY, 0)
    assert maintained_media_frame(data, authored, layer, 10750., 1000., 10000.) == (FLOOR_APPLY, 72)
    assert maintained_media_frame(data, authored, layer, 16250., 1000., 10000.) is None
    assert maintained_removal_duration(data, authored) == 6250.
    # A cold observer enters a loop directly, not the six-second formation.
    assert maintained_media_frame(data, authored, layer, 1500., None) == (FLOOR_HOLD, 216)


@pytest.mark.parametrize("quadrant", range(4))
def test_floor_uses_received_cells_and_cube_offset_without_moving_native_footprint(rendering, quadrant):
    data, state = rendering
    identity, effect = next(iter(state.senses.spatial_effects.items()))
    center = effect.area_geometry.center
    geometry = CubePresentationGeometry(origin=center, size_feet=10, centered=True)
    cells = tuple((center[0]+x, center[1]+y) for x in (-1, 0) for y in (-1, 0))
    layer = SpatialMediaLayer(assetId=FLOOR_HOLD, composition="floor", offsetCells=(-.5, -.5))
    authored = binding(layer)
    camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(center)
    commands = field_media_commands(state, data, identity, geometry, cells,
        authored, layer, 0, FLOOR_HOLD, 0, camera, 1.)
    assert commands and {row.evidence[1] for row in commands} == set(cells)
    remaining = cells[:-1]
    partial = field_media_commands(state, data, identity, geometry, remaining,
        authored, layer, 0, FLOOR_HOLD, 0, camera, 1.)
    assert {row.evidence[1] for row in partial} == set(remaining)
    assert picture(partial) != picture(commands)
    assert picture(partial) == picture(tuple(row for row in commands if row.evidence[1] in remaining))
    hidden = replace(state, senses=replace(state.senses, visible=frozenset(state.senses.visible) - set(cells)))
    assert not field_media_commands(hidden, data, identity, geometry, cells,
        authored, layer, 0, FLOOR_HOLD, 0, camera, 1.)


@pytest.mark.parametrize("quadrant", range(4))
def test_volume_uses_raw_ownership_on_actual_cells_and_carries_aligned_painter_depth(rendering, quadrant):
    data, state = rendering
    identity, effect = next(iter(state.senses.spatial_effects.items()))
    geometry = effect.area_geometry
    assert isinstance(geometry, SpherePresentationGeometry)
    layer = SpatialMediaLayer(assetId=AIR, composition="volume")
    authored = binding(layer)
    camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(geometry.center)
    commands = field_media_commands(state, data, identity, geometry, effect.positions,
        authored, layer, 0, AIR, 28, camera, 1.)
    assert commands
    assert all(row.world_depth is not None and row.world_depth.shape == row.surface.get_size() for row in commands)
    used = {row.evidence[1] for row in commands}
    assert used <= set(effect.positions) & set(state.senses.visible)
    removed = next(iter(used))
    partial = field_media_commands(state, data, identity, geometry,
        tuple(point for point in effect.positions if point != removed), authored, layer, 0, AIR, 28, camera, 1.)
    assert picture(partial) == picture(tuple(row for row in commands if row.evidence[1] != removed))
    raised = replace(state, tiles={point: tile.model_copy(update={"elevation_steps": tile.elevation_steps + 2})
                                  for point, tile in state.tiles.items()})
    higher = field_media_commands(raised, data, identity, geometry, effect.positions,
        authored, layer, 0, AIR, 28, camera, 1.)
    assert len(higher) == len(commands)
    for low, high in zip(commands, higher):
        assert high.destination == (low.destination[0], low.destination[1] - 2*HEIGHT_STEP_PIXELS*camera.zoom)
        assert pygame.image.tobytes(high.surface, "RGBA") == pygame.image.tobytes(low.surface, "RGBA")


def test_clump_anchor_is_independent_depth_and_removed_field_plays_finite_authored_clear(rendering):
    data, state = rendering
    identity, effect = next(iter(state.senses.spatial_effects.items()))
    center = effect.area_geometry.center
    layer = SpatialMediaLayer(assetId=FLOOR_HOLD, applicationAssetId=FLOOR_APPLY,
        removalAssetId=FLOOR_APPLY, composition="clump", offsetCells=(.2, .1))
    authored = binding(layer)
    selected = replace(data, spatial_media={effect.content_ref.content_id: authored})
    camera = Camera(viewport=(640, 480)).with_focus(center)
    active = spatial_media_draw_commands(state, selected, 6500., camera,
        lifetimes={identity: SpatialMediaLifetime(effect, 0.)})
    assert active and {row.evidence[1] for row in active} == {center}
    absent = replace(state, senses=replace(state.senses, spatial_effects={}))
    records = {identity: SpatialMediaLifetime(effect, 0., 7000.)}
    clearing = spatial_media_draw_commands(absent, selected, 7500., camera, lifetimes=records)
    assert clearing and {row.evidence[2] for row in clearing} == {FLOOR_APPLY}
    assert not spatial_media_draw_commands(absent, selected, 13000., camera, lifetimes=records)
    assert not spatial_media_draw_commands(absent, selected, 7500., camera), "Visibility loss alone creates no clear"


def test_observed_volume_surface_does_not_require_sight_of_its_ground_contents(rendering):
    data, state = rendering
    identity, effect = next(iter(state.senses.spatial_effects.items()))
    geometry = effect.area_geometry
    layer = SpatialMediaLayer(assetId=AIR, composition="volume")
    authored = binding(layer)
    camera = Camera(viewport=(640, 480)).with_focus(geometry.center)
    visible = field_media_commands(state, data, identity, geometry, effect.positions,
        authored, layer, 0, AIR, 28, camera, 1.)
    obscured = replace(state, senses=replace(state.senses, visible=frozenset()))
    surface = field_media_commands(obscured, data, identity, geometry, effect.positions,
        authored, layer, 0, AIR, 28, camera, 1.)
    assert visible and picture(surface) == picture(visible)
    assert not field_media_commands(obscured, data, identity, geometry, (),
        authored, layer, 0, AIR, 28, camera, 1.)
    # A surface can be seen at range while its center's support was never
    # observed. Registration uses each receiving cell's actual known height.
    without_center = replace(obscured, tiles={cell: tile for cell, tile in obscured.tiles.items()
                                               if cell != geometry.center})
    edge = field_media_commands(without_center, data, identity, geometry, effect.positions,
        authored, layer, 0, AIR, 28, camera, 1.)
    expected = tuple(row for row in surface if row.evidence[1] != geometry.center)
    assert edge and picture(edge) == picture(expected)
