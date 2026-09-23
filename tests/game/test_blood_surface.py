"""Saved cold injury and retained deposits share one seekable floor clock."""

from dataclasses import replace
import os
from uuid import uuid4

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from dnd.core.events import EventQueue
from dnd.types.residues import ResidueContribution, ResidueEllipse, TileResidueState
from game.animation_data import load_animation_data
from game.animation_types import ParticleMediaAsset
from game.choreography import bind_choreography
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.residue_media import (
    ResidueReveal, ResidueRevealSample, landing_template, particle_schedule, sample_residue_reveals,
    surface_start_time,
)
from game.surface_residue import ResidueSurfaceCache, geometric_residue_image
from tests.game.spell_handoff_scenarios import spell_handoff_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((800, 600))
    yield load_animation_data()
    pygame.quit()


def pixels(image):
    return pygame.image.tobytes(image, "RGBA")


def test_real_cold_injury_deposits_gradually_after_landing_then_matches_retained_floor(data):
    history = spell_handoff_history(program="ray")
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views["caster"])))
    groups = []
    for root in roots:
        group = bind_choreography(state, root, data)
        if group.residue_reveals:
            groups.append(group)
        state = reduce_lineage(state, root)
    group, = groups
    cue, = group.strips
    assert cue.response == data.blood_responses["Cold"]
    assert isinstance(cue.asset, ParticleMediaAsset) and cue.asset.region is not None
    assert cue.release is not None
    position = cue.release.position
    residue, = group.after.tiles[position].residues
    row = next(row for row in group.residue_reveals if row.position == position)
    assert row.response == cue.response
    schedules = [particle_schedule(p, cue.asset.region.families[row.pattern], row.response)
                 for region in cue.release.regions
                 for p in landing_template(cue.asset.region, region.ellipse).particles]
    first = min(delay + flight for delay, flight, _ in schedules)
    last_landing = max(delay + flight for delay, flight, _ in schedules)
    last_melt = max(delay + flight + melt for delay, flight, melt in schedules)
    assert last_melt > last_landing
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1)
        cache = ResidueSurfaceCache()

        def at(age):
            return geometric_residue_image(cache, cue.asset, position, residue, camera, (1, 1, 1),
                sample_residue_reveals(group.residue_reveals, cue.start_ms + age * 1000 / row.rate))

        early = at(first - .001)
        partial = at(last_landing)
        final = at(last_melt + .001)
        retained = geometric_residue_image(cache, cue.asset, position, residue, camera, (1, 1, 1))
        assert not pygame.surfarray.array_alpha(early).any()
        assert 0 < pygame.surfarray.array_alpha(partial).sum() < pygame.surfarray.array_alpha(final).sum()
        assert pixels(final) == pixels(retained)
        # Rendering/rewinding uses saved values after the native engine is gone.
        assert pixels(at(last_landing)) == pixels(partial)
    assert EventQueue.event_cursor() == 0


def test_real_acid_floor_treatment_finishes_inside_its_finite_blood_cue(data):
    saved = spell_handoff_history(program="acid")
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(saved.views["caster"])))
    checked = 0
    for root in roots:
        group = bind_choreography(state, root, data)
        for cue in group.strips:
            if cue.release is None or cue.response is None:
                continue
            assert cue.response == data.blood_responses["Acid"]
            assert isinstance(cue.asset, ParticleMediaAsset)
            finish = surface_start_time(cue.asset.assetId, cue.release.pattern or "blunt", cue.response) + cue.response.surfaceSeconds
            assert cue.end_ms >= cue.start_ms + finish * 1000 * cue.asset.defaultFps / cue.track.fps
            row = next(row for row in group.residue_reveals if row.position == cue.release.position)
            residue = next(residue for residue in group.after.tiles[row.position].residues
                           if residue.condition_uuid == row.after.condition_uuid)
            camera, cache = Camera(zoom=1), ResidueSurfaceCache()
            ended = geometric_residue_image(cache, cue.asset, row.position, residue, camera, (1, 1, 1),
                (ResidueRevealSample(row, finish * 1000 + .001),))
            retained = geometric_residue_image(cache, cue.asset, row.position, residue, camera, (1, 1, 1))
            assert pixels(ended) == pixels(retained)
            checked += 1
        state = reduce_lineage(state, root)
    assert checked


def test_second_cold_deposit_does_not_finish_or_restart_first_melt(data):
    asset = data.action_media_assets[data.body_release_media["body.blood"][0].assetId]
    assert isinstance(asset, ParticleMediaAsset)
    ellipse = ResidueEllipse(center=(0, 0), radius_x=1.5, radius_y=1.5)
    first = TileResidueState(condition_uuid=uuid4(), residue_id="residue.blood", description="Blood",
        amount=1, max_amount=5, contributions=(ResidueContribution(ellipses=(ellipse,), amount=1),))
    second = first.model_copy(update={"amount": 2,
        "contributions": (ResidueContribution(ellipses=(ellipse,), amount=2),)})
    cold = data.blood_responses["Cold"]
    first_reveal = ResidueReveal((0, 0), None, first, asset, "blunt", 0, 4000, 1, cold)
    second_reveal = ResidueReveal((0, 0), first, second, asset, "blunt", 900, 4900, 1, cold)
    camera, cache = Camera(zoom=1), ResidueSurfaceCache()
    for age in (900, 1000):
        one = geometric_residue_image(cache, asset, (0, 0), first, camera, (1, 1, 1),
            sample_residue_reveals((first_reveal,), age))
        both = geometric_residue_image(cache, asset, (0, 0), second, camera, (1, 1, 1),
            sample_residue_reveals((first_reveal, second_reveal), age))
        assert pixels(one) == pixels(both)
    both = geometric_residue_image(cache, asset, (0, 0), second, camera, (1, 1, 1),
        sample_residue_reveals((first_reveal, second_reveal), 4900))
    retained = geometric_residue_image(cache, asset, (0, 0), second, camera, (1, 1, 1))
    assert pixels(both) == pixels(retained)


@pytest.mark.parametrize("damage_type", ("Acid", "Fire", "Lightning", "Necrotic", "Poison", "Psychic", "Radiant", "Thunder"))
def test_fresh_treatment_preserves_alpha_and_older_blood_then_fades(data, damage_type):
    asset = data.action_media_assets[data.body_release_media["body.blood"][0].assetId]
    assert isinstance(asset, ParticleMediaAsset)
    left = ResidueContribution(ellipses=(ResidueEllipse(center=(-.32, 0), radius_x=.3, radius_y=.7),))
    right = ResidueContribution(ellipses=(ResidueEllipse(center=(.32, 0), radius_x=.3, radius_y=.7),), amount=3)
    before = TileResidueState(condition_uuid=uuid4(), residue_id="residue.blood", description="Blood",
        amount=1, max_amount=5, contributions=(left,))
    after = before.model_copy(update={"amount": 4, "contributions": (left, right)})
    response = data.blood_responses[damage_type]
    assert response is not None
    reveal = ResidueReveal((0, 0), before, after, asset, "blunt", 0, 5000, 1, response)
    assert asset.region is not None
    first_landing = min(sum(particle_schedule(p, asset.region.families["blunt"], response)[:2])
                        for template in asset.region.templates for p in template.particles)
    age = (first_landing + response.surfaceSeconds * .65) * 1000
    plain = replace(reveal, response=response.model_copy(update={"detail": "none", "surfaceSeconds": 0}))
    camera, cache = Camera(zoom=1), ResidueSurfaceCache()
    colored = geometric_residue_image(cache, asset, (0, 0), after, camera, (1, 1, 1), (ResidueRevealSample(reveal, age),))
    ordinary = geometric_residue_image(cache, asset, (0, 0), after, camera, (1, 1, 1), (ResidueRevealSample(plain, age),))
    old = geometric_residue_image(cache, asset, (0, 0), before, camera, (1, 1, 1))
    assert np.array_equal(pygame.surfarray.array_alpha(colored), pygame.surfarray.array_alpha(ordinary))
    # The left deposit belongs to an earlier hit and the new splat is on the right.
    unchanged = (pygame.surfarray.array_alpha(old) > 0) & np.all(
        pygame.surfarray.array3d(old) == pygame.surfarray.array3d(ordinary), axis=2)
    assert unchanged.any()
    assert np.array_equal(pygame.surfarray.array3d(colored)[unchanged], pygame.surfarray.array3d(old)[unchanged])
    assert pixels(colored) != pixels(ordinary)
    settled = geometric_residue_image(cache, asset, (0, 0), after, camera, (1, 1, 1), (ResidueRevealSample(reveal, 5000),))
    retained = geometric_residue_image(cache, asset, (0, 0), after, camera, (1, 1, 1))
    assert pixels(settled) == pixels(retained)
    assert pixels(geometric_residue_image(cache, asset, (0, 0), after, camera, (1, 1, 1),
        (ResidueRevealSample(reveal, age),))) == pixels(colored)
