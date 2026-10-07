"""Native weather ownership, contact timing and disclosure reach the renderer."""

import pygame
import pytest
from math import floor
from math import cos, pi, sin, sqrt

import numpy as np

from dnd.actions import SpellEvent
from dnd.core.presentation_geometry import LinePresentationGeometry

from game.animation import facing_for_delta, sample_cast, view_facing
from game.animation_data import load_animation_data
from game.cast_media import cast_media_draw_commands
from game.area_media import AreaMedia
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.condition_animation import resolve_condition_appearance
from dnd.player.reduction import reduce_lineage
from dnd.player.facts import SpellFact
from game.projection import Camera, rotate_position
from game.presentation_coverage import lineage_coverage, missing_observed_bindings, presentation_inventory
from game.registered_media import registered_media_samples
from game.spatial_media_draw import spatial_media_draw_commands
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.volume_media import SurfaceVolume, compose_volume
from tests.game.player_helpers import player_history
from tests.game.weather_solar_scenarios import weather_solar_history


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('empty,hidden', [(False, False), (True, False), (False, True)])
def test_ice_storm_contact_endpoints_and_native_expiry(data, empty, hidden):
    history = weather_solar_history(program='ice_storm', empty=empty, hidden=hidden, expire=True)
    state, roots = player_history(history, role='caster')
    retained, at, witnessed = {}, 0., False
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        retained = register_spatial_lifetimes(retained, state, data, absolute_start_ms=at,
            lineage=root, choreography=group)
        state = reduce_lineage(state, root)
        cast = next((node for node in group.nodes if isinstance(node.bound, BoundCast)), None)
        if cast is not None:
            assert isinstance(cast.bound, BoundCast)
            timeline = cast.bound.timeline
            active = [row for row in retained.values() if row.removed_ms is None]
            assert len(active) == 1
            lifetime = active[0]
            assert len(lifetime.recipient_endpoints) == (0 if empty else 2 if hidden else 4)
            assert all(app.damage_start_ms is None or app.damage_start_ms >= timeline.release_ms + 1000
                       for app in timeline.applications)
            first_cells = timeline.source.resolved_area_positions
            assert first_cells is not None
            formation = AreaMedia(cast.bound.area_boundaries, cast.bound.area_solids,
                cast.bound.area_supports, admitted=first_cells)
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant).with_focus((7, 7))
                falling = cast_media_draw_commands(timeline, sample_cast(timeline, timeline.release_ms+700),
                    camera, formation, {})
                chunks = [row for row in falling if str(row.evidence[-2]).startswith('ground-')]
                assert chunks, 'admitted ground modules must form before damage contact'
                assert all(row.area is None for row in chunks), 'falling clumps have source depth, not a flat floor projection'
                for row in chunks:
                    anchor = row.evidence[1]
                    assert isinstance(anchor, tuple)
                    assert (floor(anchor[0]+.5), floor(anchor[1]+.5)) in first_cells
                commands = spatial_media_draw_commands(state, data, at+group.complete_ms+1, camera, lifetimes=retained)
                assert commands, 'settled hail must retain the native terrain owner'
                assert all(command.evidence[1] in lifetime.effect.positions for command in commands)
            cold = register_spatial_lifetimes({}, state, data, absolute_start_ms=at+group.complete_ms+1)
            assert all(not row.recipient_endpoints and row.applied_ms is None for row in cold.values())
            witnessed = True
        at += group.complete_ms
    assert witnessed
    assert state.senses is not None
    assert not state.senses.spatial_effects
    for quadrant in range(4):
        assert not spatial_media_draw_commands(state, data, at+1, Camera(quadrant=quadrant), lifetimes=retained)


def test_countered_ice_storm_has_no_terrain_or_post_cast_endpoints(data):
    history = weather_solar_history(program='ice_storm', countered=True)
    state, roots = player_history(history, role='caster')
    retained = {}
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        retained = register_spatial_lifetimes(retained, state, data, absolute_start_ms=0,
            lineage=root, choreography=group)
        state = reduce_lineage(state, root)
    assert state.senses is not None
    assert not retained and not state.senses.spatial_effects


def test_sunburst_self_blindness_preserves_witnessed_cells_without_disclosing_unseen_cells():
    history = weather_solar_history(program='sunburst')
    state, roots = player_history(history, role='caster')
    assert state.senses is not None
    before_visible = set(state.senses.visible)
    native = next(root.root for root in history.views['caster'].lineages if isinstance(root.root, SpellEvent))
    cast = next(root.root.fact for root in roots if isinstance(root.root.fact, SpellFact))
    for root in roots:
        state = reduce_lineage(state, root)
    assert state.senses is not None
    after_visible = set(state.senses.visible)
    admitted = set(cast.resolved_area_positions or ())
    observed = before_visible | after_visible
    native_cells = set(native.resolved_area_positions or ())
    assert (14, 14) in admitted and (14, 14) not in after_visible
    assert admitted == native_cells & observed
    assert native_cells-observed, 'the native radius must also cover genuinely unseen cells'
    assert not admitted & (native_cells-observed)


@pytest.mark.parametrize('program,repeat', [('sleet_storm', False), ('sunbeam', True), ('sunburst', False)])
def test_weather_solar_native_lifetimes_and_surface_delivery(data, program, repeat):
    history = weather_solar_history(program=program, expire=True, repeat=repeat)
    state, roots = player_history(history, role='caster')
    retained, at, casts, terrain_seen, surfaces = {}, 0., [], False, 0
    hand_owners = set()
    coverage = []
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, group.gaps
        coverage.extend(lineage_coverage(root, group=group))
        retained = register_spatial_lifetimes(retained, state, data, absolute_start_ms=at,
            lineage=root, choreography=group)
        state = reduce_lineage(state, root)
        for node in group.nodes:
            if not isinstance(node.bound, BoundCast):
                continue
            timeline = node.bound.timeline
            casts.append(timeline)
            area = AreaMedia(node.bound.area_boundaries, node.bound.area_solids,
                node.bound.area_supports, admitted=timeline.source.resolved_area_positions)
            if program != 'sleet_storm':
                contact_delay = 375 if program == 'sunbeam' else 750
                assert all(app.damage_start_ms is None or app.damage_start_ms >= timeline.release_ms+contact_delay
                           for app in timeline.applications)
                for quadrant in range(4):
                    camera = Camera(quadrant=quadrant).with_focus((14, 14))
                    commands = cast_media_draw_commands(timeline,
                        sample_cast(timeline, timeline.release_ms+contact_delay), camera, area, {})
                    volume_commands = [row for row in commands if row.volume is not None]
                    assert volume_commands
                    for command in volume_commands:
                        assert command.volume is not None
                        composed, _ = compose_volume(command.surface, command.volume, camera)
                        surfaces += bool(composed.get_bounding_rect().width)
        if program == 'sunbeam':
            actor = state.actors[state.observer_uuid]
            owners = {condition.condition_uuid for condition in actor.conditions
                      if condition.behavior_id == 'condition.spell.sunbeam'}
            appearance = resolve_condition_appearance(actor.conditions,
                data.condition_recipes, data.condition_media)
            layers = [layer for layer in appearance.layers
                      if layer.layer.assetId == 'solar.sunbeam.hand']
            assert bool(layers) == bool(owners)
            assert all(layer.layer.attachment == 'hand' for layer in layers)
            hand_owners.update(owners)
        assert state.senses is not None
        if program == 'sleet_storm' and state.senses.spatial_effects:
            terrain_seen = True
            for quadrant in range(4):
                commands = spatial_media_draw_commands(state, data, at+group.complete_ms+1200,
                    Camera(quadrant=quadrant).with_focus((14, 14)), lifetimes=retained)
                assert commands and all(row.volume is not None for row in commands)
        at += group.complete_ms
    assert state.senses is not None
    if program == 'sleet_storm':
        assert terrain_seen and not state.senses.spatial_effects
        assert not spatial_media_draw_commands(state, data, at+1200, Camera(), lifetimes=retained)
    else:
        assert len(casts) == (2 if repeat else 1)
        assert surfaces >= 4
    if repeat:
        assert len(hand_owners) == 1, 'both beams retain the same disclosed hand owner'
        observed = [row for row in coverage if row['identity'] == 'action.spell.sunbeam.strike']
        assert observed and all(row['observed'] == 'bound' for row in observed)
        assert not missing_observed_bindings(presentation_inventory(data), observed)
        without_repeat = [row for row in presentation_inventory(data)
                          if row['identity'] != 'action.spell.sunbeam.strike']
        assert missing_observed_bindings(without_repeat, observed)
        assert not any(condition.behavior_id == 'condition.spell.sunbeam'
                       for condition in state.actors[state.observer_uuid].conditions)
        assert casts[0].source.root_event_uuid != casts[1].source.root_event_uuid
        assert casts[0].source.area_direction != casts[1].source.area_direction


@pytest.mark.parametrize('heading', range(8))
def test_sunbeam_source_banks_follow_all_native_headings_and_camera_orbits(data, heading):
    direction = (cos(heading*pi/4), sin(heading*pi/4))
    native_direction = round(direction[0]), round(direction[1])
    line = LinePresentationGeometry(origin=(0, 0), direction=native_direction, length_feet=60, width_feet=5)
    reference = 64*sqrt(2)/(512/17)
    for quadrant in range(4):
        viewed = view_facing(facing_for_delta(direction, data), quadrant, data)
        origin = rotate_position((0., 0.), quadrant)
        end = rotate_position((direction[0]*6, direction[1]*6), quadrant)
        samples = registered_media_samples(data, 'solar.sunbeam.surface', 'impact', 20, viewed,
            scale=reference*.35, zoom=.35, anchor=(0, 0), rows={})
        assert len(samples) == 1
        sample = samples[0]
        assert sample.positions is not None and sample.ownership is not None
        volume = SurfaceVolume((0, 0), 0, 12, sample.positions, sample.ownership, sample.vertical_scale,
            translation=(end[0]-origin[0], 1., end[1]-origin[1]), line_geometry=line)
        image, _ = compose_volume(sample.image, volume, Camera(quadrant=quadrant, zoom=.35))
        mask = pygame.surfarray.array_alpha(image) > 0
        assert mask.any(), 'every authored bank must reach the native corridor after camera rotation'
        # A misregistered 90-degree bank can leave a tiny crossing near the
        # center, but cannot deliver the long portion of the native beam.
        local = sample.positions[mask]
        axis = ((end[0]-origin[0])/6, (end[1]-origin[1])/6)
        along = local[:, 0]*axis[0]+local[:, 2]*axis[1]+6
        assert np.quantile(along, .95)-np.quantile(along, .05) > 7
