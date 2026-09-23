"""An observed Silence sphere owns its presentation lifetime between actions."""

from dataclasses import replace

import pygame
import pytest

from dnd.core.events import EventQueue
from dnd.core.presentation_geometry import SpherePresentationGeometry
from devtools.animation_review.control_cases import control_spell_history
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, bind_motion
from game.player_reduction import reduce_lineage
from game.projection import Camera, painter_key
from game.spatial_media_draw import spatial_media_draw_commands
from game.spatial_media_lifetime import register_spatial_lifetimes
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield load_animation_data(), control_spell_history(program="silence")
    pygame.quit()


def _picture(commands):
    image = pygame.Surface((640, 480), pygame.SRCALPHA)
    for command in sorted(commands, key=lambda row: row.key):
        image.blit(command.surface, command.destination, special_flags=command.blend)
    return pygame.image.tobytes(image, "RGBA")


@pytest.mark.parametrize("role", ("caster", "recipient"))
def test_real_silence_application_sustain_and_continuing_removal_fade(rendering, role):
    data, history = rendering
    before, roots = player_history(history, role=role)
    initial = before
    records, clock = {}, 0.
    active = None
    applied = None
    for root in roots:
        motion = bind_motion(before, root, data)
        group = None if motion is not None else bind_choreography(before, root, data)
        records = register_spatial_lifetimes(records, before, data, absolute_start_ms=clock,
            lineage=root, choreography=group, motion=motion)
        before = reduce_lineage(before, root)
        if before.senses.spatial_effects:
            active = before
            if applied is None:
                applied = next(iter(records.values())).applied_ms
                assert applied is not None and applied > 0  # Actual caster release, not head admission.
        clock += (motion.complete_ms if motion is not None else group.complete_ms) + 1800
    assert active is not None and applied is not None
    identity, lifetime = next(iter(records.items()))
    assert lifetime.removed_ms is not None
    assert before.senses is not None and not before.senses.spatial_effects
    assert initial.senses is not None and not initial.senses.spatial_effects
    geometry = lifetime.effect.area_geometry
    assert isinstance(geometry, SpherePresentationGeometry)
    assert (geometry.center, geometry.radius_feet) == ((9, 6), 20)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.35, viewport=(640, 480)).with_focus(geometry.center)
        def sample(state, at):
            return spatial_media_draw_commands(state, data, at, camera, lifetimes=records)
        first = sample(active, applied + 500)
        assert first and all(".application." in row.evidence[2] for row in first)
        assert {row.evidence[-1] for row in first} == {72}
        hold = sample(active, applied + 2000)
        assert hold and all(".sustain." in row.evidence[2] for row in hold)
        assert {row.evidence[-1] for row in hold} == {72}
        assert _picture(sample(active, applied + 6000)) == _picture(hold)
        # Whole rear/front surfaces surround occupants and retain their tall art.
        center_depth = painter_key(geometry.center, elevation_steps=0, quadrant=quadrant,
                                   role="actor", identity="recipient")
        assert all(row.key < center_depth for row in hold if row.evidence[2].endswith("back"))
        assert all(row.key > center_depth for row in hold if row.evidence[2].endswith("front"))
        assert all(row.area is None for row in hold)
        end = lifetime.removed_ms
        at_end = sample(before, end)
        fading = sample(before, end + 300)
        assert at_end and fading
        assert _picture(at_end) != _picture(fading)
        assert {row.evidence[-1] for row in at_end} != {row.evidence[-1] for row in fading}
        assert not sample(before, end + 600)
        assert _picture(sample(active, applied + 2000)) == _picture(hold), "Backward seeking is pure"
    assert EventQueue.event_cursor() == 0


def test_cold_acquisition_and_lost_origin_do_not_replay_or_guess_a_sphere(rendering):
    data, history = rendering
    before, roots = player_history(history)
    state = reduce_lineage(before, roots[0])
    assert state.senses is not None
    identity, effect = next(iter(state.senses.spatial_effects.items()))
    geometry = effect.area_geometry
    assert isinstance(geometry, SpherePresentationGeometry)
    camera = Camera(viewport=(640, 480)).with_focus(geometry.center)
    records = register_spatial_lifetimes({}, state, data, absolute_start_ms=4200)
    assert records[identity].applied_ms is None
    cold = spatial_media_draw_commands(state, data, 4200, camera, lifetimes=records)
    assert cold and all(".sustain." in row.evidence[2] for row in cold)
    unknown = replace(state, senses=replace(state.senses,
        spatial_effects={identity: effect.model_copy(update={"area_geometry": None})}))
    assert not spatial_media_draw_commands(unknown, data, 4200, camera, lifetimes=records)
    empty = replace(state, senses=replace(state.senses,
        spatial_effects={identity: effect.model_copy(update={"positions": ()})}))
    assert not spatial_media_draw_commands(empty, data, 4200, camera, lifetimes=records)
    hidden = replace(state, senses=replace(state.senses,
        visible=frozenset(state.senses.visible) - {geometry.center}))
    assert not spatial_media_draw_commands(hidden, data, 4200, camera, lifetimes=records)
    absent = replace(state, senses=replace(state.senses, spatial_effects={}))
    assert not spatial_media_draw_commands(absent, data, 4200, camera, lifetimes=records)
    lost = register_spatial_lifetimes(records, absent, data, absolute_start_ms=4400)
    assert not lost
    reacquired = register_spatial_lifetimes(lost, state, data, absolute_start_ms=4600)
    assert reacquired[identity].applied_ms is None
    # Known declared radius keeps the same fixed registration even when only
    # one support cell is disclosed. No actor/cell state is manufactured.
    partial = replace(state, senses=replace(state.senses,
        spatial_effects={identity: effect.model_copy(update={"positions": (geometry.center,)})}))
    assert _picture(spatial_media_draw_commands(partial, data, 4600, camera, lifetimes=reacquired)) == _picture(
        spatial_media_draw_commands(state, data, 4600, camera, lifetimes=reacquired))
