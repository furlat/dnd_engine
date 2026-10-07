"""Shared cues follow owned conditions; stone freezes the actual accepted pose."""

from dataclasses import replace
from uuid import uuid4

import numpy as np
import pygame
import pytest

from game.animation import BodySample
from game.animation_data import load_animation_data
from game.animation_types import Facing8
from game.body_presentation import sample_body_presentation
from game.choreography import bind_choreography
from game.condition_animation import condition_body_pose, resolve_condition_appearance
from game.condition_draw import condition_body_ramp
from game.condition_media_lifetime import ConditionMediaLifetime, register_condition_lifetimes, sample_condition_lifetimes
from dnd.player.reduction import reduce_lineage
from game.spell_palette import palette_noise
from tests.game.player_helpers import player_history
from tests.game.shared_condition_scenarios import shared_condition_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize("program", ("petrified", "restrained", "incapacitated", "stunned", "sickened", "marked", "field_focus", "life_drain", "no_reactions", "guiding_mark", "no_healing"))
def test_condition_application_and_removal_keep_shared_presentation_owned(data, program):
    state, roots = player_history(shared_condition_history(program=program), role="recipient")
    identity = {"sickened": "condition.spell.eyebite.sickened", "marked": "trait.skeleton_archer_marked",
                "life_drain": "condition.wight.life_drain", "guiding_mark": "condition.spell.guiding_bolt.marked",
                "no_healing": "condition.spell.no_healing"}.get(program, "condition." + program)
    clock, records, witnessed = 1234., {}, False
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps
        records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
            lineage=root, choreography=group, facings={str(a.uuid): "NE" for a in state.actors.values()})
        after = reduce_lineage(state, root)
        actor = next(iter(after.actors.values()))
        appearance = resolve_condition_appearance(actor.conditions, data.condition_recipes, data.condition_media)
        current = sample_condition_lifetimes({str(actor.uuid): appearance}, records, data,
                                             clock + group.complete_ms)[str(actor.uuid)]
        if identity in appearance.matched_behavior_ids:
            witnessed = True
            if program == "petrified":
                assert current.frozen_body is not None
                frame = sample_body_presentation(state, after, data, group.complete_ms, clock, {}, choreography=group)
                contact = next(row.contact for row in frame.actors)
                assert condition_body_pose(data, BodySample(str(actor.uuid), "Idle", 9, "W"), contact, current) == current.frozen_body
                later = sample_condition_lifetimes({str(actor.uuid): appearance}, records, data, clock+5000)[str(actor.uuid)]
                assert later.frozen_body == current.frozen_body
            elif program == "marked":
                assert not current.layers  # Rejected crimson reticle remains unbound.
            else:
                assert current.layers
        state = after
        clock += group.complete_ms + 2000
    assert witnessed
    assert identity not in appearance.matched_behavior_ids
    if program == "marked":
        assert not any(row.behavior_id == identity for row in records.values())
    else:
        assert next(row for row in records.values() if row.behavior_id == identity).removed_ms is not None


def test_stone_material_preserves_alpha_and_uses_cell_local_texture(data):
    ramp = data.condition_recipes["condition.petrified"].persistent.bodyRamp
    assert ramp is not None and ramp.texture is not None
    frame = pygame.Surface((24, 24), pygame.SRCALPHA)
    frame.fill((190, 60, 80, 128))
    pygame.draw.rect(frame, (0, 0, 0, 0), (0, 0, 5, 24))
    row = pygame.Surface((48, 24), pygame.SRCALPHA)
    row.blit(frame, (0, 0)); row.blit(frame, (24, 0))
    mapped = condition_body_ramp(row, ramp, texture=palette_noise(data.resources[ramp.texture]), cell_size=(24, 24))
    assert np.array_equal(pygame.surfarray.array_alpha(row), pygame.surfarray.array_alpha(mapped))
    pixels = pygame.surfarray.array3d(mapped)
    assert np.array_equal(pixels[:24], pixels[24:])
    assert not np.array_equal(pixels, pygame.surfarray.array3d(row))


@pytest.mark.parametrize("prior", ("prone", "paralyzed"))
def test_petrification_keeps_previously_displayed_pose_after_earlier_condition_ends(data, prior):
    state, roots = player_history(shared_condition_history(program="petrified", prior=prior), role="recipient")
    facings: dict[str, Facing8] = {str(a.uuid): "NE" for a in state.actors.values()}
    frame = sample_body_presentation(state, None, data, 0, 0, facings)
    original = frame.poses[0]
    expected = condition_body_pose(data, original.body, original.actor.contact, original.actor.condition)
    records, clock, captures = {}, 1000., []
    for root in roots:
        group = bind_choreography(state, root, data)
        records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
            lineage=root, choreography=group, facings=facings)
        state = reduce_lineage(state, root)
        actor = next(iter(state.actors.values()))
        appearance = resolve_condition_appearance(actor.conditions, data.condition_recipes, data.condition_media)
        sampled = sample_condition_lifetimes({str(actor.uuid): appearance}, records, data, clock+group.complete_ms)[str(actor.uuid)]
        if appearance.frozen_owner_uuid is not None and "condition.petrified" in appearance.matched_behavior_ids:
            assert sampled.frozen_body == expected
            captures.append(sampled.frozen_body)
        clock += group.complete_ms + 500
    assert len(captures) >= 2  # Includes the removal of the earlier pose condition.


def test_future_owner_cannot_replace_current_statue_pose_and_hidden_onset_stays_fallback(data):
    state, roots = player_history(shared_condition_history(program="petrified"), role="recipient")
    for root in roots:
        state = reduce_lineage(state, root)
        actor = next(iter(state.actors.values()))
        appearance = resolve_condition_appearance(actor.conditions, data.condition_recipes, data.condition_media)
        if appearance.frozen_owner_uuid is not None:
            break
    owner = appearance.frozen_owner_uuid
    assert owner is not None
    body = BodySample(str(actor.uuid), "Idle", 4, "NE")
    first = ConditionMediaLifetime(actor.uuid, owner, "condition.petrified", applied_ms=500, removed_ms=3000, frozen_body=body)
    future = replace(first, owner_uuid=uuid4(), applied_ms=4000, removed_ms=None, frozen_body=replace(body, frame=8))
    visible = sample_condition_lifetimes({str(actor.uuid): appearance}, {owner:first, future.owner_uuid:future}, data, 2000)[str(actor.uuid)]
    assert visible.frozen_body == body
    assert visible.ramp_strength == 1.
    # A hidden onset was admitted without an observable pose. Its authored quiet
    # fallback remains selected when an unrelated later head receives the actor.
    unknown = replace(first, frozen_body=None, removed_ms=None)
    admitted = register_condition_lifetimes({owner:unknown}, state, data, absolute_start_ms=5000)
    assert admitted[owner].frozen_body is None
