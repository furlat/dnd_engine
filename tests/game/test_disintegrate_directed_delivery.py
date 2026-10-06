"""Recorded Disintegrate casts retain one delivery and their committed dust outcome."""
import pygame
import pytest

from dnd.core.life_types import RemainsDisposition
from game.animation import sample_cast
from game.animation_data import load_animation_data
from game.app import draw_frame
from game.assets import load_catalog, SurfaceCache
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.directed_media import directed_draw_commands
from game.player_facts import LifeFact, ObjectDestroyedFact
from game.player_reduction import reduce_lineage
from game.projection import Camera
from game.world_animation import sample_world_transitions
from tests.game.directed_spell_scenarios import directed_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module')
def media():
    pygame.init()
    pygame.display.set_mode((1,1))
    data,catalog=load_animation_data(),load_catalog()
    yield data,catalog,SurfaceCache(catalog)
    pygame.quit()


@pytest.mark.parametrize('saved,lethal',[(True,True),(False,False),(False,True)])
def test_recorded_creature_outcome_controls_contact_and_dust(media,saved,lethal):
    data,_,_=media
    history=directed_spell_history(program='Disintegrate',saved=saved,lethal=lethal,magical_weapon=True)
    for role in ('caster','recipient'):
        state,roots=player_history(history,role=role)
        deliveries=0
        for root in roots:
            group=bind_choreography(state,root,data)
            assert not group.gaps,group.gaps
            casts=[node.bound for node in group.nodes if isinstance(node.bound,BoundCast)]
            for cast in casts:
                deliveries+=1
                row,=cast.timeline.applications
                assert row.source.save_succeeded is saved
                camera=Camera(viewport=(1000,700),zoom=1).with_focus(cast.timeline.source.caster.grid)
                # Original opening poses may have no exposed hand. Charge
                # sampling must honor that absence without inventing a socket.
                directed_draw_commands(cast.timeline,sample_cast(cast.timeline,0),camera,None)
                middle=(row.travel_start_ms+row.travel_end_ms)/2
                for quarter in range(4):
                    camera=Camera(viewport=(1000,700),zoom=1,quadrant=quarter).with_focus(cast.timeline.source.caster.grid)
                    commands=directed_draw_commands(cast.timeline,sample_cast(cast.timeline,middle),camera,None)
                    assert commands and all(command.volume is not None for command in commands)
                contact=directed_draw_commands(cast.timeline,sample_cast(cast.timeline,row.travel_end_ms+500),camera,None)
                assert bool(contact) is not saved
                assert not directed_draw_commands(cast.timeline,sample_cast(cast.timeline,cast.timeline.complete_ms+1),camera,None)
            dust=[cue for cue in group.lifecycle if isinstance(cue.event.fact,LifeFact)
                and cue.event.fact.remains_disposition is RemainsDisposition.DISINTEGRATED]
            if casts:
                assert bool(dust) is (lethal and not saved)
                if dust:assert dust[0].start_ms>=casts[0].timeline.applications[0].travel_end_ms
            state=reduce_lineage(state,root)
        assert deliveries==1


@pytest.mark.parametrize('item_id',['environment.furniture.clay_stove','environment.trap_lever'])
def test_real_object_retains_its_silhouette_only_for_committed_dust_tail(media,item_id):
    data,catalog,cache=media
    history=directed_spell_history(program='Disintegrate',target_item_id=item_id)
    state,roots=player_history(history,role='caster')
    witnessed=0
    for root in roots:
        group=bind_choreography(state,root,data)
        assert not group.gaps,group.gaps
        for cue in group.world_transitions:
            if cue.object_dust is None:continue
            witnessed+=1
            facts=[row.fact for row in root.events if isinstance(row.fact,ObjectDestroyedFact)]
            assert len(facts)==1 and facts[0].remains_disposition is RemainsDisposition.DISINTEGRATED
            assert facts[0].previous_item is not None and facts[0].previous_item.item_id==item_id
            assert cue.identity not in group.after.objects
            assert not cue.object_dust.partial and cue.destruction is None
            cast,= [node for node in group.nodes if isinstance(node.bound,BoundCast)]
            assert isinstance(cast.bound,BoundCast)
            assert cue.start_ms==cast.start_ms+cast.bound.timeline.applications[0].travel_end_ms
            for quarter in range(4):
                camera=Camera(viewport=(640,480),zoom=1,quadrant=quarter).with_focus(cue.object_dust.object.placement.position)
                def render(elapsed,transitions):
                    screen=pygame.Surface(camera.viewport,pygame.SRCALPHA)
                    evidence=draw_frame(screen,group.after,catalog,cache,camera,elapsed/1000,
                        show_grid=False,show_debug=False,mouse_position=None,collect_evidence=True,
                        animation_data=data,world_transitions=transitions).evidence
                    assert evidence is not None and evidence.matches
                    return pygame.image.tobytes(screen,'RGBA')
                at=cue.start_ms+450
                dust=render(at,sample_world_transitions(group.world_transitions,at))
                empty=render(at,())
                assert dust!=empty
                after=cue.start_ms+2600
                assert render(after,sample_world_transitions(group.world_transitions,after))==render(after,())
        state=reduce_lineage(state,root)
    assert witnessed==1
