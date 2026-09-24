"""Real recorded Gust owns its maintained flow beyond the finite cast front."""

from dataclasses import replace
from uuid import uuid4
from zipfile import ZipFile

import pygame
import numpy as np
import pytest

from dnd.core.events import EventQueue
from dnd.core.presentation_geometry import LinePresentationGeometry
from game.animation import facing_for_delta, view_facing
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.maintained_media import maintained_media_frame
from game.player_facts import SpellFact
from game.player_reduction import reduce_lineage
from game.projection import Camera, TILE_WIDTH, project_screen
from game.registered_media import registered_media_samples
from game.spatial_field import line_field_supports
from game.spatial_media_draw import spatial_media_draw_commands
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.world_animation import sample_world_transitions
from game.volume_media import compose_volume
from tests.game.area_spell_scenarios import area_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield load_animation_data()
    pygame.quit()


@pytest.fixture(scope="module", params=(False, True), ids=("axial", "diagonal"))
def captured(request):
    return area_spell_history(program="gust_of_wind", diagonal=request.param)


def _picture(commands, camera=Camera()):
    image = pygame.Surface((640, 480))
    for command in commands:
        surface = compose_volume(command.surface, command.volume, camera)[0] if command.volume is not None else command.surface
        image.blit(surface, command.destination, special_flags=command.blend)
    return pygame.image.tobytes(image, "RGBA")


def test_native_line_directions_keep_every_maintained_frame_in_the_release(rendering, captured):
    data = rendering
    state, roots = player_history(captured, role="caster")
    state = reduce_lineage(state, next(root for root in roots if isinstance(root.root.fact, SpellFact)))
    assert state.senses is not None
    effect = next(iter(state.senses.spatial_effects.values()))
    geometry = effect.area_geometry
    assert isinstance(geometry, LinePresentationGeometry)
    binding = data.spatial_media[effect.content_ref.content_id]
    for layer in binding.layers:
        frames = set()
        for index in range(binding.holdFrames):
            selected = maintained_media_frame(data, binding, layer,
                (index + .25) * 1000 / binding.fps, None)
            assert selected is not None
            frames.add(selected)
        assert frames == {(layer.assetId, binding.holdStartFrame + index)
                          for index in range(binding.holdFrames)}
        packet = data.projectile_storage[layer.assetId].phases[binding.assetPhase].surfaceFrames
        assert packet is not None and packet.componentsByFacing is not None
        for quadrant in range(4):
            # Use the native line's direction, exactly as spatial_media_draw
            # does; a world-fixed E/viewFacing assumption loses half the banks.
            facing = view_facing(facing_for_delta(geometry.direction, data), quadrant, data)
            for part in packet.componentsByFacing[facing]:
                requested = {packet.frameIndices[frame] for _, frame in frames}
                if part.archive is not None:
                    with ZipFile(data.media_root / part.archive.file) as archive:
                        expected = {part.archive.memberPattern.format(direction=facing, frame=frame)
                                    for frame in requested}
                        available = set(archive.namelist())
                        assert expected <= available, (facing, sorted(expected - available))
                else:
                    assert part.pattern is not None
                    assert all((data.media_root / part.pattern.format(direction=facing, frame=frame)).is_file()
                               for frame in requested)


@pytest.mark.parametrize("role", ("caster", "target"))
def test_native_gust_intro_only_once_then_hold_until_observed_cleanup(rendering, captured, role):
    data = rendering
    before, roots = player_history(captured, role=role)
    cast = next(root for root in roots if isinstance(root.root.fact, SpellFact))
    assert isinstance(cast.root.fact, SpellFact) and isinstance(cast.root.fact.area_geometry, LinePresentationGeometry)
    group = bind_choreography(before, cast, data)
    assert not group.gaps
    transition, = (row for row in group.world_transitions if row.duration_ms is not None)
    assert transition.duration_ms is not None
    intro_end = transition.start_ms + transition.duration_ms
    contact = sample_choreography(group, transition.start_ms).displayed
    assert contact.senses is not None
    after = reduce_lineage(before, cast)
    records = register_spatial_lifetimes({}, before, data, absolute_start_ms=1234,
                                         lineage=cast, choreography=group)
    assert after.senses is not None
    effect = after.senses.spatial_effects[transition.identity]
    assert isinstance(effect.area_geometry, LinePresentationGeometry)
    assert effect.area_geometry.origin == cast.root.fact.area_geometry.origin
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((7, 5))
        active = sample_world_transitions(group.world_transitions, intro_end - .001)
        assert not spatial_media_draw_commands(contact, data, 0, camera, active)
        # One already-existing zone must not be suppressed by another's intro.
        other = replace(contact, senses=replace(contact.senses, spatial_effects={uuid4(): effect}))
        assert spatial_media_draw_commands(other, data, 0, camera, active)
        finished = sample_world_transitions(group.world_transitions, intro_end)
        first = spatial_media_draw_commands(after, data, 0, camera, finished)
        assert first and {row.evidence[-1] for row in first} == {56}
        later = spatial_media_draw_commands(after, data, 375, camera)
        assert _picture(spatial_media_draw_commands(after, data, 375, camera, lifetimes=records), camera) == _picture(later, camera)
        assert {row.evidence[-1] for row in later} == {68}
        assert _picture(first, camera) != _picture(later, camera)
        assert _picture(spatial_media_draw_commands(after, data, 750, camera), camera) == _picture(first, camera)
        assert _picture(spatial_media_draw_commands(after, data, 0, camera), camera) == _picture(first, camera)
    state = before
    for root in roots:
        state = reduce_lineage(state, root)
    assert state.senses is not None and not state.senses.spatial_effects
    assert not spatial_media_draw_commands(state, data, 1250, Camera())
    assert EventQueue.event_cursor() == 0, "Repeated visual flow cannot replay native saves"


def test_missing_geometry_hidden_support_and_partial_cleanup_remain_private(rendering, captured):
    data = rendering
    state, roots = player_history(captured, role="caster")
    for root in roots:
        state = reduce_lineage(state, root)
        if isinstance(root.root.fact, SpellFact):
            break
    assert state.senses is not None
    identity, effect = next(iter(state.senses.spatial_effects.items()))
    camera = Camera(viewport=(640, 480)).with_focus((7, 5))
    unknown = replace(state, senses=replace(state.senses,
        spatial_effects={identity: effect.model_copy(update={"area_geometry": None})}))
    assert not spatial_media_draw_commands(unknown, data, 0, camera)
    empty = replace(state, senses=replace(state.senses,
        spatial_effects={identity: effect.model_copy(update={"positions": ()})}))
    assert not spatial_media_draw_commands(empty, data, 0, camera)
    visible = frozenset(position for position in state.senses.visible if position[0] < 7)
    partial = replace(state, senses=replace(state.senses, visible=visible))
    commands = spatial_media_draw_commands(partial, data, 0, camera)
    assert commands and all(row.volume is not None and row.volume.admitted is not None
                            and set(row.volume.admitted) <= visible for row in commands)
    assert _picture(commands) != _picture(spatial_media_draw_commands(state, data, 0, camera))
    geometry = effect.area_geometry
    assert isinstance(geometry, LinePresentationGeometry)
    if geometry.direction == (1, 1):
        # (6,5) is a diagonal lattice gap equally near three owners. Its stable
        # full-geometry owner is (5,5); removing that cell cannot lend it anew
        # to an observed neighboring cell and conceal a genuine partial removal.
        owners = frozenset(effect.positions)
        visible_supports = frozenset(state.senses.visible)
        def supports(received):
            return line_field_supports((1000, 1000), (500, 500), geometry.origin,
                geometry.direction, 12, 2, received, visible_supports, 0, 1)
        assert (6, 5) in supports(owners)
        assert (6, 5) not in supports(owners - {(5, 5)})
        assert (6, 6) in supports(owners - {(5, 5)})


def test_fully_disclosed_line_preserves_the_delivered_hold_silhouette(rendering, captured):
    data = rendering
    state, roots = player_history(captured, role="caster")
    state = reduce_lineage(state, next(root for root in roots if isinstance(root.root.fact, SpellFact)))
    assert state.senses is not None
    effect = next(iter(state.senses.spatial_effects.values()))
    geometry = effect.area_geometry
    assert isinstance(geometry, LinePresentationGeometry)
    binding = data.spatial_media[effect.content_ref.content_id]
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((7, 5))
        facing = view_facing(facing_for_delta(geometry.direction, data), quadrant, data)
        anchor = project_screen(geometry.origin, camera)
        reference = pygame.Surface((640, 480))
        for sample in registered_media_samples(data, binding.layers[0].assetId, binding.assetPhase,
                binding.holdStartFrame, facing, scale=binding.scale * TILE_WIDTH / data.rig.TILE_W * camera.zoom,
                anchor=anchor, rows={}, zoom=camera.zoom):
            # Full disclosure preserves source color at every owned above-floor
            # sample on this flat map. Use XYZ receiving cells, not a flattened
            # screen-diamond stencil that would cut airborne wind incorrectly.
            assert sample.positions is not None and sample.ownership is not None
            x, z = sample.positions[:, :, 0], sample.positions[:, :, 2]
            offsets = ((x, z), (z, -x), (-x, -z), (-z, x))[quadrant]
            cx = np.floor(offsets[0] + geometry.origin[0] + .5).astype(int)
            cz = np.floor(offsets[1] + geometry.origin[1] + .5).astype(int)
            known = np.zeros(cx.shape, dtype=bool)
            for position in state.senses.visible:
                known |= (cx == position[0]) & (cz == position[1])
            keep = known & (sample.ownership != 0) & (sample.positions[:, :, 1]*sample.vertical_scale >= -.001)
            image = sample.image.copy()
            pygame.surfarray.pixels_alpha(image)[:] *= keep
            pygame.surfarray.pixels3d(image)[:] *= keep[:, :, None]
            reference.blit(image, sample.destination, special_flags=sample.blend)
        actual = _picture(spatial_media_draw_commands(state, data, 0, camera), camera)

        assert actual == pygame.image.tobytes(reference, "RGBA"), "Disclosure partition must not manufacture an envelope mask"
