"""Recorded nature ownership drives shared materials and contact timing."""
import numpy as np
import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import BoundChoreography, bind_choreography, walk_bound_timelines
from game.condition_animation import resolve_condition_appearance
from game.condition_media_lifetime import register_condition_lifetimes
from game.condition_draw import condition_body_ramp
from game.combat import BoundCast
from game.player_reduction import reduce_lineage
from game.spell_palette import palette_noise
from tests.game.nature_spell_scenarios import nature_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('program', ['shillelagh','barkskin','warm','chill','produce_hit','produce_miss','produce_initial'])
def test_native_nature_lifecycle_has_no_presentation_gaps(data,program):
    history=nature_spell_history(program=program)
    for role in ('caster','recipient'):
        state,roots=player_history(history,role=role)
        responses=[]
        seen_owned_item=False
        for root in roots:
            group=bind_choreography(state,root,data)
            assert not group.gaps,group.gaps
            responses.extend(cue for visit in walk_bound_timelines(group,None) if isinstance(visit.timeline, BoundChoreography) for cue in visit.timeline.condition_responses)
            state=reduce_lineage(state,root)
            for actor in state.actors.values():
                appearance=resolve_condition_appearance(actor.conditions,data.condition_recipes,data.condition_media)
                seen_owned_item |= bool(appearance.item_modifiers)
        if program=='shillelagh':
            assert seen_owned_item
            assert not any(resolve_condition_appearance(a.conditions,data.condition_recipes,data.condition_media).item_modifiers for a in state.actors.values())
        if program in ('warm','chill'):
            assert {cue.trigger for cue in responses}=={'damage_requested','damage_applied'}
            assert len({cue.owner_uuid for cue in responses})==1
            assert all(cue.actor_uuid!=cue.recipient_uuid for cue in responses)
            assert all(('warm' if program=='warm' else 'chill') in effect.assetId for cue in responses for effect in cue.effects)


@pytest.mark.parametrize('program', ['warm','chill'])
def test_immune_attacker_still_shows_shield_contact_but_no_damage_burst(data,program):
    state,roots=player_history(nature_spell_history(program=program,immune=True),role='caster')
    responses=[]
    for root in roots:
        group=bind_choreography(state,root,data)
        assert not group.gaps
        responses.extend(cue for visit in walk_bound_timelines(group,None) if isinstance(visit.timeline, BoundChoreography) for cue in visit.timeline.condition_responses)
        state=reduce_lineage(state,root)
    assert [cue.trigger for cue in responses]==['damage_requested']


def test_bark_operator_follows_current_alpha_and_cell_uv(data):
    recipe=data.condition_recipes['condition.spell.barkskin']
    ramp=recipe.persistent.bodyRamp
    assert ramp is not None and ramp.texture is not None
    source=pygame.Surface((32,32),pygame.SRCALPHA)
    pygame.draw.circle(source,(130,80,60,178),(16,16),10)
    texture=palette_noise(data.resources[ramp.texture])
    applied=condition_body_ramp(source,ramp,texture=texture,cell_size=(32,32))
    clear=condition_body_ramp(source,ramp,texture=texture,cell_size=(32,32),strength=0)
    assert np.array_equal(pygame.surfarray.array_alpha(applied),pygame.surfarray.array_alpha(source))
    assert np.array_equal(pygame.surfarray.array3d(clear),pygame.surfarray.array3d(source))
    assert not np.array_equal(pygame.surfarray.array3d(applied),pygame.surfarray.array3d(source))


@pytest.mark.parametrize('program', ['produce_hit', 'produce_miss', 'produce_recast'])
def test_retained_flame_is_consumed_at_source_release_before_contact(data, program):
    state, roots = player_history(nature_spell_history(program=program), role='caster')
    lifetimes = {}
    clock = 0.
    checked = False
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps
        lifetimes = register_condition_lifetimes(lifetimes, state, data,
            absolute_start_ms=clock, lineage=root, choreography=group)
        for node in group.nodes:
            if not isinstance(node.bound, BoundCast):
                continue
            timeline = node.bound.timeline
            if not any(row.source.hit is not None for row in timeline.applications):
                continue
            flame = next(row for row in lifetimes.values()
                if row.behavior_id == 'condition.spell.produce_flame')
            release = node.start_ms + timeline.release_ms
            assert flame.consumed_ms == pytest.approx(clock + release)
            assert flame.removed_ms == flame.consumed_ms
            assert all(row.travel_end_ms > timeline.release_ms for row in timeline.applications)
            assert not any(interval.name == 'prepare' for row in timeline.applications
                for interval in row.projectile_intervals)
            checked = True
        state = reduce_lineage(state, root)
        clock += group.complete_ms + 25
    assert checked


def test_compatible_nature_buffs_all_keep_their_authored_treatment(data):
    state, roots = player_history(nature_spell_history(program='coexist'), role='caster')
    for root in roots:
        state = reduce_lineage(state, root)
    actor = state.actors[state.observer_uuid]
    appearance = resolve_condition_appearance(actor.conditions, data.condition_recipes, data.condition_media)
    expected = {'condition.spell.' + name for name in ('shillelagh', 'barkskin', 'fire_shield', 'produce_flame')}
    assert expected <= set(appearance.matched_behavior_ids)
    assert appearance.item_modifiers
