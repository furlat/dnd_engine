"""Authored fields preserve observed receiving cells, phase clocks and depth."""

from dataclasses import replace
from uuid import uuid4

import pygame
import pytest
import numpy as np

from dnd.core.presentation_geometry import CubePresentationGeometry, SpherePresentationGeometry
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementKind
from devtools.animation_review.control_cases import control_spell_history
from game.animation_data import load_animation_data
from game.animation_types import SpatialMediaBinding, SpatialMediaLayer
from game.area_media import AreaMedia, AreaSolid
from game.maintained_media import maintained_media_alpha, maintained_media_frame, maintained_removal_duration
from game.player_reduction import reduce_lineage
from game.projection import Camera, HEIGHT_STEP_PIXELS, inverse_rotate_position
from game.spatial_field_media import field_media_commands
from game.spatial_media_draw import spatial_media_draw_commands
from game.spatial_media_lifetime import SpatialMediaLifetime
from game.volume_media import compose_volume
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


def picture(commands, camera=None):
    surface = pygame.Surface((640, 480), pygame.SRCALPHA)
    for command in sorted(commands, key=lambda item: item.key):
        image = command.surface
        if command.volume is not None:
            assert camera is not None
            image, _ = compose_volume(image, command.volume, camera, destination=command.destination)
        surface.blit(image, command.destination, special_flags=command.blend)
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


@pytest.mark.parametrize("spell,application_frames,hold_frames", (
    ("fog_cloud", 64, 64), ("darkness", 64, 64),
    ("stinking_cloud", 64, 64), ("cloudkill", 64, 64),
    ("incendiary_cloud", 64, 64), ("insect_plague", 64, 192),
))
def test_production_cloud_clocks_cover_application_two_loops_and_continuing_removal(
        rendering, spell, application_frames, hold_frames):
    data, _ = rendering
    authored = data.spatial_media[f"spatial_effect.spell.{spell}"]
    layer, = authored.layers
    assert layer.applicationAssetId == f"persistent.{spell}.apply"
    assert layer.assetId == f"persistent.{spell}.hold"
    assert layer.composition == "xyz_volume" and layer.removalAssetId is None
    assert authored.holdStartFrame == 0 and authored.holdFrames == hold_frames
    assert authored.fps == 32 and authored.scale == .5
    assert authored.referenceRadiusFeet == (15 if spell == "darkness" else 20)
    assert authored.movementSpeedCellsPerSecond == (2 if spell in ("cloudkill", "incendiary_cloud") else None)
    for identity, frames in ((layer.applicationAssetId, application_frames), (layer.assetId, hold_frames)):
        asset = data.projectile_assets[identity]
        phase = asset.phases.impact
        assert phase is not None and phase.frames == frames and (phase.fps or asset.fps) == 32
        bank = data.projectile_storage[identity].phases["impact"].surfaceFrames
        assert bank is not None and len(bank.frameIndices) == frames
        first = 0 if identity == layer.applicationAssetId else application_frames
        assert bank.frameIndices == tuple(range(first, first + frames))
        assert bank.componentsByFacing is not None and set(bank.componentsByFacing) == {"E", "S", "W", "N"}
    frame_ms, start = 1000 / 32, 1000.
    application_ms, period_ms = application_frames * frame_ms, hold_frames * frame_ms
    assert maintained_media_frame(data, authored, layer, start - 1, start) is None
    assert maintained_media_frame(data, authored, layer, start, start) == (layer.applicationAssetId, 0)
    assert maintained_media_frame(data, authored, layer, start + frame_ms, start) == (layer.applicationAssetId, 1)
    assert maintained_media_frame(data, authored, layer, start + application_ms - 1, start) == (
        layer.applicationAssetId, application_frames - 1)
    for cycle in range(3):
        boundary = start + application_ms + cycle * period_ms
        assert maintained_media_frame(data, authored, layer, boundary, start) == (layer.assetId, 0)
        assert maintained_media_frame(data, authored, layer, boundary + frame_ms, start) == (layer.assetId, 1)
        assert maintained_media_frame(data, authored, layer, boundary + period_ms - 1, start) == (
            layer.assetId, hold_frames - 1)
    # An observer first seeing the existing field enters its hold, without an intro.
    assert maintained_media_frame(data, authored, layer, 0, None) == (layer.assetId, 0)
    assert maintained_media_frame(data, authored, layer, 2 * period_ms + 3 * frame_ms, None) == (layer.assetId, 3)
    removed = start + application_ms + 2 * period_ms + 7 * frame_ms
    assert authored.removalEasing == "smoothstep" and maintained_removal_duration(data, authored) == 630.
    for fraction in (0., .25, .5, .75, 1.):
        now = removed + 630 * fraction
        assert maintained_media_frame(data, authored, layer, now, start, removed) == maintained_media_frame(
            data, authored, layer, now, start)
        assert maintained_media_alpha(authored, layer, now, removed) == pytest.approx(
            1 - fraction * fraction * (3 - 2 * fraction))


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


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("height", (0, 2))
@pytest.mark.parametrize("xyz,translation", ((False, (0., 0.)), (False, (1.2, -.3)),
                                           (False, (-1.2, .3)), (True, (0., 0.))))
def test_cloud_art_overhangs_map_edges_without_adding_received_cells(rendering, quadrant, height, translation, xyz):
    data, state = rendering
    identity, effect = next(iter(state.senses.spatial_effects.items()))
    center = effect.area_geometry.center
    state = replace(state, tiles={p: tile.model_copy(update={"elevation_steps": height})
                                  for p, tile in state.tiles.items()})
    asset_id = "persistent.cloudkill.hold" if xyz else AIR
    layer = SpatialMediaLayer(assetId=asset_id, composition="xyz_volume" if xyz else "xy_volume")
    authored = data.spatial_media["spatial_effect.spell.cloudkill"] if xyz else binding(layer)
    camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(center)
    radius = 1 if abs(translation[0]) > 1 else 0
    bounds = center[0]-radius, center[1]-radius, center[0]+radius, center[1]+radius
    cells = tuple(p for p in effect.positions if bounds[0] <= p[0] <= bounds[2]
                  and bounds[1] <= p[1] <= bounds[3])
    small_map = replace(state, world=replace(state.world, bounds=bounds, width=2*radius+1, height=2*radius+1),
                        tiles={p: state.tiles[p] for p in cells})
    # The reference admits the complete authored fringe too; a cloud's native
    # circle alone omits decorative pixels in known adjacent tiles.
    reference_positions = tuple(state.tiles) if xyz else effect.positions
    full = field_media_commands(state, data, identity, effect.area_geometry, reference_positions,
        authored, layer, 0, asset_id, 28, camera, 1., translation, anchor_elevation_steps=height)
    clipped = field_media_commands(state, data, identity, effect.area_geometry, cells,
        authored, layer, 0, asset_id, 28, camera, 1., translation, anchor_elevation_steps=height)
    overhang = field_media_commands(small_map, data, identity, effect.area_geometry, cells,
        authored, layer, 0, asset_id, 28, camera, 1., translation, anchor_elevation_steps=height)
    if not radius:
        assert picture(full, camera) != picture(clipped, camera), "The authored volume extends beyond these cells"
    assert picture(overhang, camera) == picture(full, camera), "A map edge is not a physical wall"
    assert {row.evidence[1] for row in overhang} <= set(effect.positions)
    assert tuple(small_map.tiles) == cells, "Rendering must not invent ground or occupancy"
    cold = replace(small_map, tiles={})
    assert picture(field_media_commands(cold, data, identity, effect.area_geometry, cells,
        authored, layer, 0, asset_id, 28, camera, 1., translation, anchor_elevation_steps=height), camera) == picture(overhang, camera)
    assert not field_media_commands(small_map, data, identity, effect.area_geometry, (),
        authored, layer, 0, asset_id, 28, camera, 1., translation, anchor_elevation_steps=height)


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("barrier", ("boundary", "solid"))
def test_real_map_edge_barriers_still_stop_cloud_overhang(rendering, quadrant, barrier):
    data, state = rendering
    identity, effect = next(iter(state.senses.spatial_effects.items()))
    center = effect.area_geometry.center
    layer = SpatialMediaLayer(assetId=AIR, composition="xy_volume")
    authored = binding(layer)
    camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(center)
    bounded = replace(state, world=replace(state.world, bounds=(*center, *center), width=1, height=1))
    walls = tuple(WorldObjectPlacement(object_uuid=uuid4(), tile_uuid=uuid4(), position=center,
        kind=WorldPlacementKind.BOUNDARY, occupies_bands=True, boundary_direction=direction,
        base_height_steps=0, top_height_steps=3) for direction in CardinalDirection)
    area = AreaMedia(walls if barrier == "boundary" else (),
                     (AreaSolid(center, 0, 3),) if barrier == "solid" else ())
    clipped = field_media_commands(state, data, identity, effect.area_geometry, (center,),
        authored, layer, 0, AIR, 28, camera, 1.)
    blocked = field_media_commands(bounded, data, identity, effect.area_geometry, (center,),
        authored, layer, 0, AIR, 28, camera, 1., area=area)
    assert picture(blocked) == picture(clipped)
    opened = field_media_commands(bounded, data, identity, effect.area_geometry, (center,),
        authored, layer, 0, AIR, 28, camera, 1., area=AreaMedia(()))
    assert picture(opened) != picture(blocked)


@pytest.mark.parametrize("quadrant", range(4))
def test_cloud_exclusion_uses_genuine_height_without_cutting_whole_tile_columns(rendering, quadrant):
    data, state = rendering
    identity, effect = next(iter(state.senses.spatial_effects.items()))
    center = effect.area_geometry.center
    # Put the sphere through the represented near surface in each view. The
    # export holds one visible surface, not hidden layers inside the cloud.
    zero = inverse_rotate_position((0., 0.), quadrant)
    toward_camera = np.subtract(inverse_rotate_position((1.5, 1.5), quadrant), zero)
    provider = tuple(round(center[i] + toward_camera[i]) for i in (0, 1))
    geometry = SpherePresentationGeometry(center=center, radius_feet=20)
    omitted = tuple(p for p in effect.positions if (p[0]-provider[0])**2+(p[1]-provider[1])**2 <= 4)
    remaining = tuple(p for p in effect.positions if p not in omitted)
    suppression = SpellSuppression(provider_uuid=uuid4(), positions=omitted,
        provider_content_ref=effect.content_ref.model_copy(update={"content_id": "spatial_effect.spell.globe_of_invulnerability"}),
        area_geometry=SpherePresentationGeometry(center=provider, radius_feet=10), anchor_elevation_steps=0)
    observed = effect.model_copy(update={"content_ref": effect.content_ref.model_copy(update={"content_id": "spatial_effect.spell.cloudkill"}),
        "positions": remaining, "visible_volume_positions": remaining,
        "area_geometry": geometry, "anchor_elevation_steps": 0, "suppressions": (suppression,)})
    state = replace(state, senses=replace(state.senses, spatial_effects={identity: observed}))
    camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(center)
    commands = spatial_media_draw_commands(state, data, 1000., camera)
    assert commands
    axis0 = np.subtract(inverse_rotate_position((1., 0.), quadrant), inverse_rotate_position((0., 0.), quadrant))
    axis2 = np.subtract(inverse_rotate_position((0., 1.), quadrant), inverse_rotate_position((0., 0.), quadrant))
    exterior_count = interior_count = 0
    for row in commands:
        volume = row.volume
        assert volume is not None and volume.exclusions
        output, _ = compose_volume(row.surface, volume, camera, destination=row.destination)
        xyz = volume.positions
        horizontal = xyz[:, :, 0, None]*axis0 + xyz[:, :, 2, None]*axis2 + np.array(volume.center)
        height = xyz[:, :, 1]*volume.vertical_scale + volume.elevation
        sphere, = volume.exclusions
        inside = (np.sum((horizontal-np.array(provider))**2, axis=2)
                  + ((height-sphere.elevation)/sphere.vertical_scale)**2 <= 4)
        source = pygame.surfarray.array_alpha(row.surface) != 0
        alpha = pygame.surfarray.array_alpha(output) != 0
        interior_count += np.count_nonzero(inside & source)
        assert not np.any(alpha & inside), "No genuine surface inside the protecting sphere survives"
        if row.evidence[1] in omitted:
            exterior_count += np.count_nonzero(alpha & ~inside)
    assert interior_count > 0, "Exercise genuine surfaces inside the sphere"
    assert exterior_count > 0, "Cloud above/outside the sphere survives within suppressed tile columns"
    assert state.senses.spatial_effects[identity].positions == remaining, "Visual geometry never adds gameplay occupancy"
    undisclosed = suppression.model_copy(update={"provider_content_ref": None, "area_geometry": None})
    hidden = replace(state, senses=replace(state.senses, spatial_effects={identity:
        observed.model_copy(update={"suppressions": (undisclosed,)})}))
    assert all(row.evidence[1] not in omitted for row in spatial_media_draw_commands(hidden, data, 1000., camera)), (
        "A missing footprint cell is not permission to invent a protection boundary")


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("surface_only", (False, True))
def test_observed_shell_does_not_require_seeing_its_center_ground(rendering, quadrant, surface_only):
    data, state = rendering
    identity, original = next(iter(state.senses.spatial_effects.items()))
    center = original.area_geometry.center
    edge = center[0]+1, center[1]
    effect = original.model_copy(update={
        "content_ref": original.content_ref.model_copy(update={"content_id": "spatial_effect.spell.globe_of_invulnerability"}),
        "area_geometry": SpherePresentationGeometry(center=center, radius_feet=10),
        "anchor_elevation_steps": 0, "positions": (center, edge),
        "visible_volume_positions": (edge,) if surface_only else ()})
    observed = replace(state, tiles={cell: tile for cell, tile in state.tiles.items() if cell != center},
        senses=replace(state.senses, spatial_effects={identity: effect},
            visible=frozenset() if surface_only else frozenset((edge,))))
    camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus(center)
    commands = spatial_media_draw_commands(observed, data, 1000., camera)
    assert commands, "A currently observed shield surface must be submitted for geometric occlusion"
    assert center not in observed.senses.visible and center not in observed.tiles
    hidden = replace(observed, senses=replace(observed.senses, visible=frozenset(),
        spatial_effects={identity: effect.model_copy(update={"visible_volume_positions": ()})}))
    assert not spatial_media_draw_commands(hidden, data, 1000., camera), "Remembered shell geometry alone does not grant visibility"
