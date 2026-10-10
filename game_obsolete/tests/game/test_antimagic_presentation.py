"""Received retained suppression controls art without replacing effect owners."""

from dataclasses import replace
from uuid import UUID

import pygame
import pytest

from game.animation_data import load_animation_data
from game.body_presentation import sample_body_presentation
from game.choreography import bind_choreography, bind_motion
from game.condition_animation import resolve_condition_appearance
from game.condition_media_lifetime import register_condition_lifetimes
from dnd.player.reduction import reduce_lineage
from game.projection import Camera, project_screen
from game.spatial_media_draw import spatial_media_draw_commands
from tests.game.antimagic_scenarios import antimagic_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


def test_same_barkskin_owner_and_clock_survive_field_entry_and_exit(data):
    state, roots = player_history(antimagic_history(), role='recipient')
    records, clock, observed, identities, dates = {}, 1000., [], set(), set()
    for root in roots:
        motion = bind_motion(state, root, data)
        group = None if motion is not None else bind_choreography(state, root, data)
        if group is not None:
            assert not group.gaps, group.gaps
        records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
            lineage=root, choreography=group, motion=motion)
        after = reduce_lineage(state, root)
        recipient = after.actors[after.observer_uuid]
        bark = next((member for member in recipient.conditions
            if member.behavior_id == 'condition.spell.barkskin'), None)
        if bark is not None:
            assert bark.state is not None
            suppressed = bool(bark.state.suppression_provider_uuids)
            appearance = resolve_condition_appearance(recipient.conditions, data.condition_recipes, data.condition_media)
            assert ('condition.spell.barkskin' in appearance.matched_behavior_ids) is not suppressed
            identities.add(bark.condition_uuid)
            dates.add(records[bark.condition_uuid].applied_ms)
            if not observed or observed[-1] != suppressed:
                observed.append(suppressed)
        state = after
        clock += (group.complete_ms if group is not None else motion.complete_ms) + 1000
    assert observed == [False, True, False]
    assert len(identities) == len(dates) == 1
    assert not state.senses.spatial_effects


def test_field_layers_follow_actual_sampled_caster_position_in_every_camera(data):
    state, roots = player_history(antimagic_history(), role='caster')
    for root in roots:
        state = reduce_lineage(state, root)
        if state.senses and state.senses.spatial_effects:
            break
    field = next(iter(state.senses.spatial_effects.values()))
    assert field.anchor_entity_uuid == state.observer_uuid
    frame = sample_body_presentation(state, None, data, 0, 2000, {})
    caster = next(actor.contact for actor in frame.actors if actor.contact.actor_uuid == str(state.observer_uuid))
    moved = replace(caster, grid=(caster.grid[0] + .375, caster.grid[1]))
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant).with_focus(caster.grid)
        commands = spatial_media_draw_commands(state, data, 2000, camera, anchors={UUID(caster.actor_uuid): caster})
        shifted = spatial_media_draw_commands(state, data, 2000, camera, anchors={UUID(caster.actor_uuid): moved})
        assert len(commands) == len(shifted) == 2
        p, q = project_screen(caster.grid, camera), project_screen(moved.grid, camera)
        for old, new in zip(commands, shifted, strict=True):
            assert new.destination[0] - old.destination[0] == pytest.approx(q[0] - p[0], abs=1)
            assert new.destination[1] - old.destination[1] == pytest.approx(q[1] - p[1], abs=1)
            assert pygame.image.tobytes(old.surface, 'RGBA') == pygame.image.tobytes(new.surface, 'RGBA')
