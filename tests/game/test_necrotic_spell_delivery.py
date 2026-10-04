"""Finite current-pose materials and native outcome gating share cast timing."""

import numpy as np
import pygame
import pytest

from game.animation_data import load_animation_data
from game.cast_media import sample_cast_body_materials
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.condition_draw import condition_body_ramp
from game.player_reduction import reduce_lineage
from game.spell_palette import palette_noise
from tests.game.necrotic_spell_scenarios import necrotic_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('program', ['blight', 'harm', 'circle_of_death'])
@pytest.mark.parametrize('saved,immune', [(False, False), (True, False), (False, True)])
def test_native_necrotic_outcomes_select_finite_media(data, program, saved, immune):
    history = necrotic_spell_history(program=program, saved=saved, immune=immune)
    for role in ('caster', 'recipient'):
        state, roots = player_history(history, role=role)
        casts = []
        for root in roots:
            group = bind_choreography(state, root, data)
            assert not group.gaps, group.gaps
            casts.extend(node.bound.timeline for node in group.nodes if isinstance(node.bound, BoundCast))
            state = reduce_lineage(state, root)
        assert casts
        timeline = next(row for row in casts if row.recipe.definitionRef.content_id == 'spell.' + program)
        if timeline.recipe.bodyMaterials:
            at = timeline.release_ms + timeline.recipe.contact.delayMs + 450
            samples = sample_cast_body_materials(timeline, at)
            harmed = {row.target.actor_uuid for row in timeline.source.applications if row.damage_applied}
            assert {identity for identity, _ in samples} == harmed
            assert not sample_cast_body_materials(timeline, timeline.complete_ms + 1)
            assert not sample_cast_body_materials(timeline, timeline.release_ms - 1)
            if samples:
                assert timeline.complete_ms >= timeline.release_ms + timeline.recipe.contact.delayMs + max(track.points[-1].elapsedMs for track in timeline.recipe.bodyMaterials)


def test_wither_operator_preserves_alpha_and_clears_without_mutating_current_pose(data):
    ramp = data.drafts['spell.blight'].bodyMaterials[0].material
    texture = palette_noise(data.resources[ramp.texture])
    for shape in ('standing', 'prone'):
        source = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.ellipse(source, (140, 95, 75, 230), (21, 8, 19, 50) if shape == 'standing' else (5, 43, 53, 16))
        original = pygame.image.tobytes(source, 'RGBA')
        treated = condition_body_ramp(source, ramp, texture=texture, strength=1, pulse=.7)
        assert np.array_equal(pygame.surfarray.array_alpha(treated), pygame.surfarray.array_alpha(source))
        assert not np.array_equal(pygame.surfarray.array3d(treated), pygame.surfarray.array3d(source))
        clear = condition_body_ramp(source, ramp, texture=texture, strength=0)
        assert pygame.image.tobytes(clear, 'RGBA') == original
        assert pygame.image.tobytes(source, 'RGBA') == original


@pytest.mark.parametrize('spell', ['blight', 'harm'])
def test_finite_material_uses_its_authored_palette(data, spell):
    ramp = data.drafts['spell.' + spell].bodyMaterials[0].material
    texture = palette_noise(data.resources[ramp.texture]) if ramp.texture else None
    source = pygame.Surface((48, 64), pygame.SRCALPHA)
    source.fill((140, 95, 75, 230))
    replacement = ramp.model_copy(update={'colors': tuple(0x2080FF for _ in ramp.colors)})
    first = condition_body_ramp(source, ramp, texture=texture, strength=1, pulse=.7)
    second = condition_body_ramp(source, replacement, texture=texture, strength=1, pulse=.7)
    assert not np.array_equal(pygame.surfarray.array3d(first), pygame.surfarray.array3d(second))
    assert np.array_equal(pygame.surfarray.array_alpha(second), pygame.surfarray.array_alpha(source))
