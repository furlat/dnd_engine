"""Protection reaches a cold client as real observed state and causal facts."""
import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.player_facts import SpellFact
from game.presentation_group import presentation_groups, reduce_presentation_group
from game.spatial_media_draw import spatial_media_draw_commands
from game.projection import Camera
from tests.game.globe_scenarios import globe_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module', params=['fireball', 'fire_bolt', 'ice_knife'])
def history(request):
    # Producer resets the whole native engine before returning these saved inputs.
    return request.param, globe_history(spell=request.param)


@pytest.mark.parametrize('role', ['caster', 'target'])
def test_cold_replay_has_observed_globe_shell_and_attributable_contact(history, role):
    spell, recorded = history
    data = load_animation_data()
    state, heads = player_history(recorded, role=role)
    found = False
    for group in presentation_groups(heads):
        fact = group.primary.root.fact
        if isinstance(fact, SpellFact) and fact.behavior_id == 'spell.' + spell:
            found = True
            assert state.senses and state.senses.spatial_effects
            bound = bind_choreography(state, group.primary, data, reactions=group.reactions)
            assert not bound.gaps
            casts = [cue.bound for cue in bound.nodes if isinstance(cue.bound, BoundCast)]
            assert any(cast.timeline.source.protections for cast in casts)
            assert bound.contact_media
            providers = set(state.senses.spatial_effects)
            assert all(suppression.provider_uuid in providers for node in group.primary.events
                if isinstance(node.fact, SpellFact) for suppression in node.fact.suppressions)
            if spell == 'fire_bolt':
                assert group.primary.root.canceled and not bound.damage
        state = reduce_presentation_group(state, group)
    assert found and state.senses and not state.senses.spatial_effects


def test_observed_globe_produces_front_and_back_pixels_in_each_camera(history):
    _, recorded = history
    pygame.init(); pygame.display.set_mode((8, 8))
    try:
        data = load_animation_data()
        state, heads = player_history(recorded)
        state = reduce_presentation_group(state, presentation_groups(heads)[0])
        for quadrant in range(4):
            commands = spatial_media_draw_commands(state, data, 1500., Camera(quadrant=quadrant))
            assert {command.evidence[2] for command in commands} == {'globe.hold.back', 'globe.hold.front'}
            assert all(command.surface.get_bounding_rect().width > 20 for command in commands)
    finally:
        pygame.quit()
