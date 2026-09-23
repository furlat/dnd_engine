"""A real moving cloud retains its owner and commits contacts at visual arrival."""

from dataclasses import replace
import json
from math import floor

import numpy as np
import pygame
import pytest

from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import SpherePresentationGeometry
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entity import Entity
from dnd.spells.conjuration import Cloudkill, FogCloud
from game.animation import view_facing
from game.animation_data import load_animation_data
from game.animation_types import ProjectileStorage, SpatialMediaBinding, SpatialMediaLayer
from game.choreography import bind_choreography, sample_choreography
from game.maintained_media import maintained_media_alpha, maintained_media_frame
from game.player_reduction import decode_player_sequence, reduce_lineage
from game.projection import Camera
from game.projection import HEIGHT_STEP_PIXELS, project_screen, project_world
from game.spatial_media_draw import spatial_media_draw_commands
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.world_animation import sample_world_transitions
from tests.game.test_spell14_native_facts import actors, saved_views
from tests.engine.test_spell_families import create_family_target


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield load_animation_data()
    pygame.quit()


def test_saved_native_cloud_displacement_holds_received_membership_until_arrival(rendering):
    caster, witness = actors()
    start = EventQueue.event_cursor()
    cast = Cloudkill(source_entity_uuid=caster.uuid, end_position=(7, 4), template=False).apply()
    assert cast is not None and not cast.canceled
    zone, = get_map().get_spatial_conditions()
    caster.on_turn_start(round_number=2, turn_index=0)
    views = saved_views((caster, witness), start)
    for payload in views.values():
        before, heads = decode_player_sequence(payload)
        cast_root, root = heads
        before = reduce_lineage(before, cast_root)
        assert before.senses is not None
        effect = before.senses.spatial_effects[zone.uuid]
        # Small known media isolates the shared movement contract; source Cloudkill
        # art is tested separately after its missing volume export is delivered.
        authored = SpatialMediaBinding(layers=(SpatialMediaLayer(
            assetId="liquid.water.s0.air.application", applicationAssetId="liquid.water.s0.air.application",
            composition="volume", offsetCells=(-4., 0.)),),
            holdStartFrame=0, holdFrames=68, fps=144., scale=1., movementSpeedCellsPerSecond=2.)
        data = replace(rendering, spatial_media={effect.content_ref.content_id: authored})
        group = bind_choreography(before, root, data)
        motion, = (change for change in group.world_transitions if change.spatial_motion is not None)
        assert motion.spatial_motion is not None
        assert motion.duration_ms == 1000.
        start_ms = motion.start_ms
        midpoint = sample_choreography(group, start_ms + 500.)
        final = sample_choreography(group, start_ms + 1000.)
        assert midpoint.displayed.senses is not None and final.displayed.senses is not None
        middle_geometry = midpoint.displayed.senses.spatial_effects[zone.uuid].area_geometry
        final_geometry = final.displayed.senses.spatial_effects[zone.uuid].area_geometry
        assert isinstance(middle_geometry, SpherePresentationGeometry) and middle_geometry.center == (7, 4)
        assert isinstance(final_geometry, SpherePresentationGeometry) and final_geometry.center == (9, 4)
        assert group.complete_ms >= start_ms + 1000.
        records = register_spatial_lifetimes({}, before, data, absolute_start_ms=0., lineage=root, choreography=group)
        assert records[zone.uuid].applied_ms is None
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((6, 4))
            commands = spatial_media_draw_commands(midpoint.displayed, data, 200., camera,
                sample_world_transitions(group.world_transitions, start_ms + 500.), records)
            assert commands, (quadrant, effect.positions, motion.spatial_motion.after.positions)
            assert {command.evidence[0] for command in commands} == {str(zone.uuid)}
    assert EventQueue.event_cursor() == 0


def test_cold_volume_uses_observed_elevation_without_disclosing_ground(rendering):
    pictures = []
    for height in (0, 2):
        caster, _ = actors()
        get_map().set_tile_elevation((7, 4), height=height,
            surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
        cast = Cloudkill(source_entity_uuid=caster.uuid, end_position=(7, 4), template=False).apply()
        assert cast is not None and not cast.canceled
        observer = create_family_target(name="Cold cloud observer", position=(2, 7))
        payload, = saved_views((observer,), EventQueue.event_cursor()).values()
        state, heads = decode_player_sequence(payload)
        assert not heads
        assert state.senses is not None
        effect, = state.senses.spatial_effects.values()
        assert effect.anchor_elevation_steps == height
        assert effect.visible_volume_positions
        assert not set(effect.visible_volume_positions) & set(state.senses.visible)
        assert not set(effect.visible_volume_positions) & set(state.tiles)
        layer = SpatialMediaLayer(assetId="liquid.water.s0.air.application", composition="volume")
        binding = SpatialMediaBinding(layers=(layer,), holdStartFrame=0, holdFrames=68, fps=144., scale=1.)
        data = replace(rendering, spatial_media={effect.content_ref.content_id: binding})
        camera = Camera(viewport=(640, 480)).with_focus((7, 4))
        commands = spatial_media_draw_commands(state, data, 200., camera)
        assert commands and {row.evidence[7] for row in commands} == {height}
        assert {row.evidence[1] for row in commands} <= set(effect.visible_volume_positions)
        pictures.append(commands)
    assert len(pictures[0]) == len(pictures[1])
    for low, raised in zip(*pictures):
        assert raised.destination == (low.destination[0], low.destination[1]-2*HEIGHT_STEP_PIXELS*.5)
        assert pygame.image.tobytes(low.surface, "RGBA") == pygame.image.tobytes(raised.surface, "RGBA")
    assert EventQueue.event_cursor() == 0


@pytest.mark.parametrize("delay_ms", (0., 7000.))
def test_native_cloud_removal_fades_continuing_application_or_hold(rendering, delay_ms):
    caster, _ = actors()
    start = EventQueue.event_cursor()
    cast = Cloudkill(source_entity_uuid=caster.uuid, end_position=(7, 4), template=False).apply()
    assert cast is not None and not cast.canceled
    caster.remove_condition("Concentrating")
    payload, = saved_views((caster,), start).values()
    state, heads = decode_player_sequence(payload)
    layer = SpatialMediaLayer(assetId="liquid.water.s0.floor.sustain",
        applicationAssetId="liquid.water.s0.air.application", composition="volume")
    binding = SpatialMediaBinding(layers=(layer,), holdStartFrame=0, holdFrames=288,
        fps=144., scale=1., removalFadeMs=630., removalEasing="smoothstep")
    data = replace(rendering, spatial_media={"spatial_effect.spell.cloudkill": binding})
    records, clock = {}, 0.
    for head in heads:
        group = bind_choreography(state, head, data)
        records = register_spatial_lifetimes(records, state, data, absolute_start_ms=clock,
            lineage=head, choreography=group)
        state = reduce_lineage(state, head)
        clock += group.complete_ms + delay_ms
    record, = records.values()
    assert record.applied_ms is not None and record.removed_ms is not None
    assert state.senses is not None
    assert not state.senses.spatial_effects
    for fraction in (0., .25, .5, .75, 1.):
        now = record.removed_ms + 630. * fraction
        ongoing = maintained_media_frame(data, binding, layer, now, record.applied_ms)
        clearing = maintained_media_frame(data, binding, layer, now, record.applied_ms, record.removed_ms)
        assert clearing == ongoing
        assert maintained_media_alpha(binding, layer, now, record.removed_ms) == pytest.approx(
            1. - fraction * fraction * (3. - 2. * fraction))
    at_removal = maintained_media_frame(data, binding, layer, record.removed_ms, record.applied_ms)
    assert at_removal is not None
    assert at_removal[0] == (layer.applicationAssetId if delay_ms == 0. else layer.assetId)
    assert maintained_media_alpha(binding, layer, record.removed_ms + 631., record.removed_ms) == 0.
    # Existing fields retain their linear envelope unless explicitly authored otherwise.
    linear = binding.model_copy(update={"removalEasing": "linear"})
    assert maintained_media_alpha(linear, layer, record.removed_ms + 157.5, record.removed_ms) == .75
    assert EventQueue.event_cursor() == 0


def test_saved_fog_upcast_scales_pixels_registration_and_world_ownership_together(rendering, tmp_path):
    """Four colored probes have known world positions, independent of the sampler."""
    identity = "test.fog.radius"
    probes = (((3., 0.), (255, 0, 0)), ((-3., 0.), (0, 255, 0)),
              ((0., 3.), (0, 0, 255)), ((0., -3.), (255, 255, 0)))
    by_facing = {}
    for quadrant in range(4):
        color = pygame.Surface((448, 448), pygame.SRCALPHA)
        raw = pygame.Surface((448, 448), pygame.SRCALPHA)
        zero_x, zero_y = project_world((0, 0), quadrant=quadrant)
        for point, rgb in probes:
            x, y = project_world(point, quadrant=quadrant)
            region = pygame.Rect(round(224+(x-zero_x)/2)-1, round(224+(y-zero_y)/2)-1, 3, 3)
            color.fill((*rgb, 255), region)
            encoded = tuple(round((axis+4)*65535/8) for axis in point)
            raw.fill((encoded[0]//256, encoded[0]%256, encoded[1]//256, encoded[1]%256), region)
        color_file, raw_file = tmp_path/f"color-{quadrant}.png", tmp_path/f"raw-{quadrant}.png"
        pygame.image.save(color, color_file)
        pygame.image.save(raw, raw_file)
        by_facing[view_facing("E", quadrant, rendering)] = [[{
            "file": str(color_file), "rect": [0, 0, 448, 448], "offset": [0, 0],
            "footpoint": {"file": str(raw_file), "bounds": [-4., 4.]}}]]
    source = rendering.projectile_assets["liquid.water.s0.air.application"]
    asset = source.model_copy(update={"assetId": identity,
        "frame": source.frame.model_copy(update={"width": 448, "height": 448, "cols": 1}),
        "anchor": source.anchor.model_copy(update={"x": .5, "y": .5}), "anchorsByFacing": None})
    storage = ProjectileStorage.model_validate_json(json.dumps({"phases": {
        "impact": {"layers": [{"blendMode": "normal", "partsByFacing": by_facing}]}}}))
    binding = SpatialMediaBinding(layers=(SpatialMediaLayer(assetId=identity, composition="volume",
        offsetCells=(.125, .125)),), holdStartFrame=0, holdFrames=1, fps=144., scale=1., referenceRadiusFeet=20.)
    data = replace(rendering, projectile_assets={**rendering.projectile_assets, identity: asset},
        projectile_storage={**rendering.projectile_storage, identity: storage},
        spatial_media={"spatial_effect.spell.fog_cloud": binding})
    for slot in (1, 2):
        caster, _ = actors()
        Entity.update_entity_position(caster, (7, 7))
        start = EventQueue.event_cursor()
        cast = FogCloud(source_entity_uuid=caster.uuid, end_position=(7, 7), cast_at_level=slot, template=False).apply()
        assert cast is not None and not cast.canceled
        payload, = saved_views((caster,), start).values()
        state, heads = decode_player_sequence(payload)
        for head in heads:
            state = reduce_lineage(state, head)
        assert state.senses is not None
        effect, = state.senses.spatial_effects.values()
        assert isinstance(effect.area_geometry, SpherePresentationGeometry)
        assert effect.area_geometry.radius_feet == slot * 20
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(1000, 1000)).with_focus((7, 7))
            commands = spatial_media_draw_commands(state, data, 0., camera)
            expected_cells = {(floor(7+(point[0]+.125)*slot+.5), floor(7+(point[1]+.125)*slot+.5))
                              for point, _ in probes}
            assert expected_cells <= set(effect.positions)
            assert {row.evidence[1] for row in commands} == expected_cells, (
                slot, quadrant, effect.content_ref.content_id, effect.anchor_elevation_steps,
                len(effect.visible_volume_positions), len(state.tiles))
            for point, rgb in probes:
                world_point = 7+(point[0]+.125)*slot, 7+(point[1]+.125)*slot
                pixels = []
                for row in commands:
                    image_rgb = pygame.surfarray.array3d(row.surface)
                    mask = np.all(image_rgb == rgb, axis=2) & (pygame.surfarray.array_alpha(row.surface) != 0)
                    xs, ys = np.nonzero(mask)
                    pixels.extend(zip(xs+row.destination[0], ys+row.destination[1]))
                    if len(xs):
                        assert row.world_depth is not None
                        assert row.world_depth[mask] == pytest.approx(
                            project_world(world_point, quadrant=quadrant)[1], abs=.01)
                assert len(pixels) == 9 * slot * slot
                expected = project_screen(world_point, camera)
                assert np.mean(pixels, axis=0) == pytest.approx(expected, abs=1.)
            if slot == 1:
                unchanged = replace(data, spatial_media={"spatial_effect.spell.fog_cloud":
                    binding.model_copy(update={"referenceRadiusFeet": None})})
                baseline = spatial_media_draw_commands(state, unchanged, 0., camera)
                assert [(r.destination, pygame.image.tobytes(r.surface, "RGBA")) for r in commands] == [
                    (r.destination, pygame.image.tobytes(r.surface, "RGBA")) for r in baseline]
    assert EventQueue.event_cursor() == 0
