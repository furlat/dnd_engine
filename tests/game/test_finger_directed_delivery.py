"""Native Finger outcomes share original delivery, finite cleanup, and contact clocks."""
from dataclasses import replace

import numpy as np
import pygame
import pytest

from game.animation import sample_cast
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.directed_media import directed_draw_commands
from game.directed_mesh_media import _source
from game.interruption_draw import reaction_media_draw_commands
from game.player_reduction import reduce_lineage
from game.presentation_group import presentation_groups, reduce_presentation_group
from game.projection import Camera
from game.stationary_media import stationary_media_draw_commands
from tests.game.directed_spell_scenarios import directed_spell_history
from tests.game.interruption_scenarios import interruption_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


def _casts(history,role,data):
    state,roots=player_history(history,role=role)
    result=[]
    for root in roots:
        group=bind_choreography(state,root,data)
        assert not group.gaps,group.gaps
        result.extend((group,node.bound) for node in group.nodes if isinstance(node.bound,BoundCast))
        state=reduce_lineage(state,root)
    return result


@pytest.mark.parametrize('saved,lethal,prone',[(False,False,False),(True,False,False),(False,True,False),(False,False,True)])
def test_committed_damage_arrives_after_original_hand_discharge(data,saved,lethal,prone):
    history=directed_spell_history(program='Finger of Death',saved=saved,lethal=lethal,prone=prone,target_position=(7,6))
    for role in ('caster','recipient'):
        (group,cast),=_casts(history,role,data)
        timeline=cast.timeline
        application,=timeline.applications
        assert application.source.save_succeeded is saved
        assert application.source.damage_applied
        assert application.travel_start_ms==pytest.approx(1500)
        assert application.travel_end_ms==pytest.approx(2150)
        assert timeline.body_end_ms==pytest.approx(2150)
        caster=next(body for body in sample_cast(timeline,1800).bodies if body.actor_uuid==timeline.source.caster.actor_uuid)
        assert caster.clip=='Attack5' and caster.frame==14
        assert application.damage_start_ms is not None and application.damage_start_ms>=application.travel_end_ms
        for quarter in range(4):
            camera=Camera(viewport=(1000,700),zoom=1,quadrant=quarter).with_focus((5,6))
            assert not directed_draw_commands(timeline,sample_cast(timeline,1400),camera,None)
            commands=directed_draw_commands(timeline,sample_cast(timeline,1850),camera,None)
            assert commands and all(row.volume is not None for row in commands)
            assert any('splinter:' in str(row.evidence) for row in commands)
            assert not directed_draw_commands(timeline,sample_cast(timeline,2250),camera,None)
        assert not group.contact_media


@pytest.mark.parametrize('blocked',[True,False])
def test_counterspell_cameo_is_exact_native_interruption_only(data,blocked):
    history=interruption_history(blocker='counterspell',spell='finger_of_death',blocked=blocked)
    for role in ('caster','defender'):
        state,roots=player_history(history,role=role)
        found=False
        for presentation in presentation_groups(roots):
            if not presentation.reactions:
                state=reduce_presentation_group(state,presentation)
                continue
            found=True
            group=bind_choreography(state,presentation.primary,data,reactions=presentation.reactions)
            assert not group.gaps,group.gaps
            assert group.after==reduce_presentation_group(state,presentation)
            cue,=group.reaction_media
            cast=next(node.bound for node in group.nodes if node.event_uuid==cue.incoming_event_uuid)
            assert isinstance(cast,BoundCast)
            assert cue.start_ms==pytest.approx(1275)
            assert cue.source_point is not None
            assert cue.succeeded is blocked
            gesture = next(row for row in group.body_actions if row.event_uuid == cue.event_uuid)
            assert gesture.clip == "Special1"
            assert gesture.start_ms == pytest.approx(1275-8000/12)
            assert gesture.effect_ms == pytest.approx(1275)
            assert bool(group.contact_media) is blocked
            assert any(row.source.damage_applied for row in cast.timeline.applications) is not blocked
            if blocked:
                assert not group.conditions and not group.lifecycle
                assert cast.timeline.complete_ms==pytest.approx(1275)
                assert group.complete_ms>=3650
                assert all(at<=1275 for at,_ in group.states)
                assert all(row.start_ms==pytest.approx(1275) and row.end_ms==pytest.approx(3650) for row in group.contact_media)
                for quarter in range(4):
                    camera=Camera(viewport=(1000,700),zoom=1,quadrant=quarter).with_focus((4,6))
                    assert stationary_media_draw_commands(group.contact_media,1450,camera)
                    assert reaction_media_draw_commands(cue,1300,None,camera)
                    assert not stationary_media_draw_commands(group.contact_media,3651,camera)
            else:
                assert cast.timeline.complete_ms>2150
            state=reduce_presentation_group(state,presentation)
        assert found


def test_delayed_launch_is_opt_in_and_native_socket_rotates_with_world_facing(data):
    history=directed_spell_history(program='Finger of Death',target_position=(7,6))
    (_,bound),=_casts(history,'caster',data)
    timeline=bound.timeline
    recipe=timeline.recipe
    assert recipe.directed is not None and recipe.directed.material=='darkness_mesh'
    points=[]
    for facing in data.rig.AUTHORED_PROJECTILE_ROW_ORDER:
        points.append(_source(replace(timeline,facing=facing),recipe.directed))
    source=np.array((timeline.source.caster.grid[0],0,timeline.source.caster.grid[1]))
    distances=[np.linalg.norm((p-source)[[0,2]]) for p in points]
    assert max(distances)-min(distances)<1e-9
    assert len({tuple(np.round(p,6)) for p in points})==8
    for draft in data.drafts.values():
        if draft.definitionRef.content_id!='spell.finger_of_death':
            assert not draft.cast.holdUntilContact
            assert draft.contact is None or draft.contact.launchDelayMs==0
