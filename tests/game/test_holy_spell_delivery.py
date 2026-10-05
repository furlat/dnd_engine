"""Native holy owners, admitted contact timing and original component rendering."""

from dataclasses import replace
from typing import cast

import numpy as np
import pygame
import pytest

from game.animation_data import load_animation_data
from game.animation_draw import LoadedBodyRows
from game.choreography import BoundChoreography, bind_choreography, walk_bound_timelines
from game.choreography_draw import load_choreography_media
from game.playback_frame import sample_playback_frame
from game.player_reduction import reduce_lineage
from game.orbit_media import orbit_point
from game.combat import actor_contact
from game.condition_draw import condition_body_ramp
from game.projection import Camera
from game.scene import load_scene_media
from game.scene_actors import scene_actors
from game.spatial_media_draw import spatial_media_draw_commands
from game.stationary_draw import stationary_media_draw_commands
from tests.game.holy_spell_scenarios import holy_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope='module')
def data():
    pygame.init();pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('program', ['spirit_radiant','spirit_necrotic','guardian','feast'])
def test_native_holy_history_binds_real_owners_without_gaps(data, program):
    history=holy_spell_history(program=program,expire=program=='feast')
    for role in ('caster','recipient'):
        state,roots=player_history(history,role=role)
        responses=[];materials=[];eating=[];observed=[]
        for root in roots:
            group=bind_choreography(state,root,data)
            assert not group.gaps,group.gaps
            for visit in walk_bound_timelines(group):
                if isinstance(visit.timeline, BoundChoreography):
                    responses.extend(visit.timeline.spatial_responses)
                    materials.extend(visit.timeline.finite_materials)
            eating.extend(row for row in group.body_actions if row.recipe_id=='action.environment.heroes_feast.eat')
            state=reduce_lineage(state,root)
            if state.senses is not None:observed.extend(state.senses.spatial_effects.values())
        assert observed
        assert materials,program
        if program=='guardian':
            assert responses
            for response in responses:
                assert response.contact_ms-response.media.start_ms==406.25
                assert response.owner_uuid is not None
        elif program=='feast':
            assert eating and eating[0].clip=='Taunt' and eating[0].enabled
        else:
            wanted='Radiant' if program=='spirit_radiant' else 'Necrotic'
            assert any(row.energy_type is not None and row.energy_type.value==wanted for row in observed)


def test_guardian_immune_contact_still_strikes_without_damage_material(data):
    state,roots=player_history(holy_spell_history(program='guardian',immune=True),role='caster')
    responses=[];materials=[]
    for root in roots:
        group=bind_choreography(state,root,data)
        assert not group.gaps
        for visit in walk_bound_timelines(group):
            if isinstance(visit.timeline,BoundChoreography):
                responses.extend(visit.timeline.spatial_responses)
                materials.extend(visit.timeline.finite_materials)
        state=reduce_lineage(state,root)
    assert len(responses)==3
    assert len({row.owner_uuid for row in responses})==1
    assert not materials
    assert state.senses is not None and responses[0].owner_uuid in state.senses.spatial_effects


def test_guardian_actual_positive_contact_drives_strike_material_and_retirement(data):
    state,roots=player_history(holy_spell_history(program='guardian'),role='caster')
    responses=[]
    for root in roots:
        group=bind_choreography(state,root,data)
        for visit in walk_bound_timelines(group):
            if not isinstance(visit.timeline,BoundChoreography):
                continue
            nested=visit.timeline
            for response in nested.spatial_responses:
                material=next(row for row in nested.finite_materials if row.event_uuid==response.media.event_uuid)
                assert material.start_ms==response.contact_ms
                assert material.actor_uuid==response.recipient.actor_uuid
                assert any(cue.timing.start_ms==response.contact_ms for cue in nested.damage)
                responses.append(response)
        state=reduce_lineage(state,root)
    assert len(responses)==3
    assert responses[-1].media.fade_out_ms==(1000,2150)
    assert state.senses is not None and responses[0].owner_uuid not in state.senses.spatial_effects


def test_spirit_source_loop_and_wakes_remain_in_current_owner_space(data):
    from_recipe=data.spatial_media['spatial_effect.spell.spirit_guardians'].layers[0].orbit
    assert from_recipe is not None
    first=sorted(tuple(round(v,9) for v in orbit_point(from_recipe,index,1234,age_ms=233)) for index in range(7))
    second=sorted(tuple(round(v,9) for v in orbit_point(from_recipe,index,3234,age_ms=233)) for index in range(7))
    assert first==second
    state,roots=player_history(holy_spell_history(program='spirit_radiant'),role='caster')
    for root in roots:
        state=reduce_lineage(state,root)
        if state.senses is not None and state.senses.spatial_effects:
            break
    assert state.senses is not None
    effect=next(iter(state.senses.spatial_effects.values()))
    assert effect.anchor_entity_uuid==state.observer_uuid
    contact=actor_contact(state,state.actors[state.observer_uuid],data)
    moved=replace(contact,grid=(contact.grid[0]+.3,contact.grid[1]+.2))
    camera=Camera(zoom=1).with_focus(contact.grid)
    commands=spatial_media_draw_commands(state,data,1500,camera,anchors={state.observer_uuid:moved})
    components=[row for row in commands if len(row.evidence)>1 and row.evidence[1]=='orbit_component']
    assert len(components)==7
    radius=from_recipe.radiusCells
    for row in components:
        world=cast(tuple[float,float],row.evidence[3])
        assert (world[0]-moved.grid[0])**2+(world[1]-moved.grid[1])**2==pytest.approx(radius**2)
    assert any(row.evidence[1]=='orbit_wake' for row in commands)


def test_holy_body_operators_preserve_current_alpha_and_use_authored_palette(data):
    source=pygame.Surface((128,128),pygame.SRCALPHA)
    pygame.draw.rect(source,(80,70,60,170),(35,25,55,80))
    ramps=[data.spatial_media['spatial_effect.spell.guardian_of_faith'].damageMaterials['Radiant'].material,
        data.spatial_media['spatial_effect.spell.spirit_guardians'].damageMaterials['Necrotic'].material,
        data.action_materials['action.environment.heroes_feast.eat'].material]
    for ramp in ramps:
        first=condition_body_ramp(source,ramp,strength=.7,age_ms=240)
        second=condition_body_ramp(source,ramp.model_copy(update={'colors':tuple(0xffffff-value for value in ramp.colors)}),strength=.7,age_ms=240)
        assert np.array_equal(pygame.surfarray.array_alpha(first),pygame.surfarray.array_alpha(source))
        assert not np.array_equal(pygame.surfarray.array3d(first),pygame.surfarray.array3d(second))


def test_spirit_contact_reuses_one_bank_in_authored_back_front_layers(data):
    state,roots=player_history(holy_spell_history(program='spirit_radiant'),role='caster')
    contacts=[]
    for root in roots:
        group=bind_choreography(state,root,data)
        for visit in walk_bound_timelines(group):
            if isinstance(visit.timeline,BoundChoreography):
                contacts.extend(cue for cue in visit.timeline.contact_media if cue.track.assetId=='holy.contact.radiant')
        state=reduce_lineage(state,root)
    assert contacts
    assert {cue.track.depth for cue in contacts}=={'behind_body','front_body'}
    assert {cue.track.alpha for cue in contacts}=={.6,.38}
    assert {cue.track.blendMode for cue in contacts}=={'normal'}
    by_event={cue.event_uuid for cue in contacts}
    for event in by_event:
        pair=[cue for cue in contacts if cue.event_uuid==event]
        assert len(pair)==2 and pair[0].position==pair[1].position and pair[0].start_ms==pair[1].start_ms
    cue=contacts[0]
    for quadrant in range(4):
        camera=Camera(quadrant=quadrant,zoom=1).with_focus(cue.position)
        authored=stationary_media_draw_commands((cue,),cue.start_ms+250,camera)
        baseline=stationary_media_draw_commands((replace(cue,track=cue.track.model_copy(update={'emissionPointByFacing':None})),),cue.start_ms+250,camera)
        assert len(authored)==len(baseline)>0
        assert baseline[0].destination[1]-authored[0].destination[1]==pytest.approx(6.9,abs=1)


def test_native_feast_intake_draws_toward_current_gesture_in_every_camera(data):
    state,roots=player_history(holy_spell_history(program='feast'),role='recipient')
    font=pygame.font.Font(None,14)
    for root in roots:
        group=bind_choreography(state,root,data)
        eating=next((cue for cue in group.body_actions if cue.recipe_id=='action.environment.heroes_feast.eat'),None)
        if eating is None:
            state=reduce_lineage(state,root)
            continue
        rows: LoadedBodyRows={}
        bodies=load_scene_media(scene_actors(state,data,{}),data,body_rows=rows)
        media=load_choreography_media(group,body_rows=rows)
        assert eating.interaction_object_uuid in group.before.objects
        for quadrant in range(4):
            camera=Camera(quadrant=quadrant)
            rendered=[]
            for progress in (.35,.75,1.4):
                time=eating.start_ms+(eating.effect_ms-eating.start_ms)*progress
                frame=sample_playback_frame(group.before,group.after,data,time,time,camera,{},bodies,font,font,
                    choreography=group,choreography_media=media)
                particles=[command for command in frame.commands if 'object_intake' in command.evidence]
                visible=[command for command in particles if command.surface.get_bounding_rect().width]
                assert bool(visible) is (progress<1.36)
                rendered.append([command.destination for command in visible])
            assert rendered[0]!=rendered[1]
        return
    pytest.fail('Native Feast consumption was not disclosed')
