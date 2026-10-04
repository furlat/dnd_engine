"""Actual Eyebite casts and repeats feed the shared directed/condition operators."""
import pygame
import pytest

from game.animation import sample_cast
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.directed_media import directed_draw_commands
from game.condition_animation import resolve_condition_appearance
from game.player_reduction import reduce_lineage
from game.projection import Camera
from tests.game.directed_spell_scenarios import directed_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('mode',['asleep','sickened','panicked'])
def test_initial_and_repeat_gazes_retain_one_actual_delivery_each(data,mode):
    history=directed_spell_history(mode=mode,repeat=True)
    for role in ('caster','recipient'):
        state,roots=player_history(history,role=role)
        timelines=[]
        for root in roots:
            group=bind_choreography(state,root,data)
            assert not group.gaps,group.gaps
            timelines.extend(node.bound.timeline for node in group.nodes if isinstance(node.bound,BoundCast))
            state=reduce_lineage(state,root)
        gazes=[timeline for timeline in timelines if timeline.recipe.definitionRef.content_id=='spell.eyebite']
        assert len(gazes)==(1 if role=="recipient" and mode=="asleep" else 2), (role, len(gazes))
        for timeline in gazes:
            row,=timeline.applications
            midpoint=(row.travel_start_ms+row.travel_end_ms)/2
            sample=sample_cast(timeline,midpoint)
            for quarter in range(4):
                camera=Camera(quadrant=quarter,zoom=1,viewport=(1600,1000)).with_focus(timeline.source.caster.grid)
                commands=directed_draw_commands(timeline,sample,camera,None)
                assert commands
                assert all(command.volume is not None for command in commands)
            assert not directed_draw_commands(timeline,sample_cast(timeline,timeline.complete_ms+1),camera,None)


@pytest.mark.parametrize('mode',['asleep','sickened','panicked'])
def test_eye_and_recipient_visuals_are_owned_until_native_concentration_cleanup(data,mode):
    history=directed_spell_history(mode=mode,cleanup=True)
    state,roots=player_history(history,role='caster')
    saw_eye=False
    saw_recipient=False
    for root in roots:
        group=bind_choreography(state,root,data)
        assert not group.gaps,group.gaps
        for _,stage in group.states:
            for actor in stage.actors.values():
                appearance=resolve_condition_appearance(actor.conditions,data.condition_recipes,data.condition_media)
                if actor.name=='Caster':
                    saw_eye |= any(layer.layer.assetId=='control.eyebite_eye.front' for layer in appearance.layers)
                if actor.name=='Recipient':
                    if mode=='panicked' and 'condition.spell.eyebite.panicked' in appearance.matched_behavior_ids:
                        marks=[layer for layer in appearance.layers if layer.layer.assetId=='control.frightened.front']
                        assert len(marks)==1 and marks[0].layer.phaseOffsetMs==220
                        saw_recipient=True
                    elif mode!='panicked':
                        saw_recipient |= f'condition.spell.eyebite.{mode}' in appearance.matched_behavior_ids
        state=reduce_lineage(state,root)
    assert saw_eye and saw_recipient
    assert not any(member.behavior_id and member.behavior_id.startswith('condition.spell.eyebite.')
        for actor in state.actors.values() for member in actor.conditions)


@pytest.mark.parametrize('target',[(5,6),(3,10),(0,7),(5,2)])
def test_actual_gaze_endpoints_work_for_multiple_headings_and_ranges(data,target):
    history=directed_spell_history(target_position=target)
    state,roots=player_history(history,role='caster')
    count=0
    for root in roots:
        group=bind_choreography(state,root,data)
        for node in group.nodes:
            if not isinstance(node.bound,BoundCast):
                continue
            timeline=node.bound.timeline
            row,=timeline.applications
            assert row.source.target.grid==target
            at=(row.travel_start_ms+row.travel_end_ms)/2
            for q in range(4):
                camera=Camera(quadrant=q,zoom=1,viewport=(1000,700)).with_focus(timeline.source.caster.grid)
                commands=directed_draw_commands(timeline,sample_cast(timeline,at),camera,None)
                assert len(commands)==2
                assert all(command.volume is not None for command in commands)
            count+=1
        state=reduce_lineage(state,root)
    assert count==1
