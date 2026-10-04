"""Received joined Wind geometry, current body contact and retained-owner clocks."""
from dataclasses import replace

import numpy as np
import pygame
import pytest

from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry
from game.animation_data import load_animation_data
from game.combat import actor_contact, actor_is_visible
from game.choreography import bind_choreography
from game.player_facts import DamageResultFact
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.wall_assembly_media import assembly_media_draw_commands
from game.wind_flow_media import joined_sheets
from tests.game.assembly_scenarios import assembly_history


@pytest.fixture(scope='module')
def received():
    pygame.init();pygame.display.set_mode((1,1));data=load_animation_data()
    # Native formation damages its real recipients, later passage does not;
    # the existing scenario asserts these outcomes before capturing the bytes.
    history=assembly_history(program='wind',form='corner')
    before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views['caster'])))
    selected=None
    for root in roots:
        group=bind_choreography(before,root,data)
        records=register_spatial_lifetimes({},before,data,absolute_start_ms=0,lineage=root,choreography=group)
        before=reduce_lineage(before,root)
        if before.senses is not None:
            selected=next(((before,owner,effect) for owner,effect in before.senses.spatial_effects.items()
                if effect.content_ref.content_id=='spatial_effect.spell.wind_wall'),None)
            if selected:break
    assert selected is not None
    yield data,*selected,records[selected[1]],root
    pygame.quit()


def pixels(commands,camera):
    image=pygame.Surface(camera.viewport,pygame.SRCALPHA)
    for command in commands:image.blit(command.surface,command.destination)
    return pygame.image.tobytes(image,'RGBA')


def test_shared_corner_boundaries_and_full_path_texture_phase():
    # The stable pure geometry boundary exposes native XYZ and UV, not a
    # renderer's internal calls. Every layer must meet on the same shared edge.
    sheets,_=joined_sheets(((0.,0.),(1.,0.),(1.,1.)),2.121320344)
    assert len(sheets)==6
    for layer in range(3):
        incoming,outgoing=sheets[layer],sheets[3+layer]
        assert np.allclose(incoming.vertices[-25:],outgoing.vertices[:25],atol=1e-8)
        assert np.allclose(incoming.normals[-25:],outgoing.normals[:25],atol=1e-8)
        assert np.allclose(incoming.uv[-25:],outgoing.uv[:25],atol=1e-8)
        assert outgoing.uv[-1,0]>outgoing.uv[0,0]>0
    # Native diagonal length determines segmentation; no screen-angle bank or
    # chopped texture reset is involved.
    diagonal,_=joined_sheets(((0.,0.),(2.,2.)),2.121320344)
    assert len(diagonal)==9
    for layer in range(3):assert np.allclose(diagonal[layer].uv[-25:],diagonal[3+layer].uv[:25])


def test_received_native_path_parts_around_real_current_bodies_and_seeks(received):
    data,state,owner,effect,_,_=received
    assert isinstance(effect.area_geometry,WallAssemblyPresentationGeometry)
    binding=data.spatial_media[effect.content_ref.content_id]
    contacts=tuple(actor_contact(state,actor,data,'S') for actor in state.actors.values() if actor_is_visible(state,actor))
    assert contacts
    for q in range(4):
        camera=Camera(quadrant=q,zoom=.5).with_focus((9,8))
        def draw(at,body_contacts):
            return assembly_media_draw_commands(effect,owner,data,binding,at,camera,0,None,contacts=body_contacts)
        initial=draw(700,contacts);quiet=draw(2700,contacts);clear=draw(2700,())
        assert initial and quiet and clear
        assert all(command.owner==str(owner) and command.volume is not None for command in quiet)
        assert pixels(quiet,camera)!=pixels(clear,camera)
        lifted=draw(2700,tuple(replace(c,body_lift_px=80) for c in contacts))
        assert pixels(lifted,camera)!=pixels(quiet,camera)
        assert pixels(quiet,camera)==pixels(draw(2700,contacts),camera)
        assert pixels(initial,camera)==pixels(draw(700,contacts),camera)


def test_hidden_cells_do_not_acquire_flow_and_retirement_does_not_restart(received):
    data,_,owner,effect,_,_=received;binding=data.spatial_media[effect.content_ref.content_id]
    camera=Camera(zoom=.5).with_focus((9,8))
    original=assembly_media_draw_commands(effect,owner,data,binding,3000,camera,0,None)
    sample=next(command for command in original if command.volume is not None)
    volume=sample.volume;assert volume is not None
    pixel=np.argwhere(pygame.surfarray.array_alpha(sample.surface)>0)[0]
    local=volume.positions[pixel[0],pixel[1]]
    cell=(int(np.floor(local[0]+volume.center[0]+.5)),int(np.floor(local[2]+volume.center[1]+.5)))
    restricted=effect.model_copy(update={'positions':(cell,)})
    commands=assembly_media_draw_commands(restricted,owner,data,binding,3000,camera,0,None)
    assert commands
    for command in commands:
        assert command.volume is not None
        volume=command.volume;visible=pygame.surfarray.array_alpha(command.surface)>0
        world_x=volume.positions[...,0]+volume.center[0]
        world_z=volume.positions[...,2]+volume.center[1]
        assert np.all(np.floor(world_x[visible]+.5)==restricted.positions[0][0])
        assert np.all(np.floor(world_z[visible]+.5)==restricted.positions[0][1])
    present=assembly_media_draw_commands(effect,owner,data,binding,3500,camera,0,None)
    onset=assembly_media_draw_commands(effect,owner,data,binding,3500,camera,0,3500)
    assert pixels(present,camera)==pixels(onset,camera)
    assert not assembly_media_draw_commands(effect,owner,data,binding,4500,camera,0,3500)


def test_formation_contacts_are_exact_committed_recipients_not_nearby_bodies(received):
    data,state,owner,effect,record,root=received
    expected={str(node.fact.target_entity_uuid) for node in root.events
        if not node.canceled and isinstance(node.fact,DamageResultFact)
        and node.fact.applied_damage>0 and node.fact.spatial_source is not None
        and node.fact.spatial_source.spatial_effect_uuid==owner}
    assert len(expected)==2
    formation=tuple(row.recipient for row in record.damage_contacts if row.formation)
    assert {contact.actor_uuid for contact in formation}==expected
    assert len({row.event_uuid for row in record.damage_contacts})==2
    assert all(row.at_ms>=record.applied_ms for row in record.damage_contacts)
    camera=Camera(zoom=.5).with_focus((9,8));binding=data.spatial_media[effect.content_ref.content_id]
    # The same visible body can part the sheet without a damage receipt. Only
    # admitted formation recipients gain the original finite hit mesh/pulse.
    contacts=tuple(actor_contact(state,actor,data,'S') for actor in state.actors.values() if actor_is_visible(state,actor))
    quiet=assembly_media_draw_commands(effect,owner,data,binding,700,camera,0,None,contacts=contacts)
    hit=assembly_media_draw_commands(effect,owner,data,binding,700,camera,0,None,
        contacts=contacts,formation_contacts=formation)
    assert hit and quiet and pixels(hit,camera)!=pixels(quiet,camera)
    late=assembly_media_draw_commands(effect,owner,data,binding,2700,camera,0,None,
        contacts=contacts,formation_contacts=formation)
    late_quiet=assembly_media_draw_commands(effect,owner,data,binding,2700,camera,0,None,contacts=contacts)
    assert pixels(late,camera)==pixels(late_quiet,camera)
    cold=register_spatial_lifetimes({},state,data,absolute_start_ms=0)
    assert cold[owner].applied_ms is None and not cold[owner].damage_contacts
    # An unrelated later head cannot reassign the formation recipients.
    kept=register_spatial_lifetimes({owner:record},state,data,absolute_start_ms=10000)
    assert kept[owner].damage_contacts==record.damage_contacts


def test_later_spatial_damage_reuses_exact_owner_and_committed_contact_dates():
    pygame.init();pygame.display.set_mode((1,1));data=load_animation_data()
    history=assembly_history(program='thorns')
    state,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views['recipient'])))
    retained={};clock=0.;expected=set();received={}
    for root in roots:
        group=bind_choreography(state,root,data);assert not group.gaps
        expected.update(node.uuid for node in root.events if not node.canceled
            and isinstance(node.fact,DamageResultFact) and node.fact.applied_damage>0
            and node.fact.spatial_source is not None)
        retained=register_spatial_lifetimes(retained,state,data,absolute_start_ms=clock,
            lineage=root,choreography=group)
        for owner,record in retained.items():
            for contact in record.damage_contacts:
                received[contact.event_uuid]=contact
                packet=next((node.fact for node in root.events if node.uuid==contact.event_uuid),None)
                if isinstance(packet,DamageResultFact):
                    assert packet.spatial_source is not None and packet.spatial_source.spatial_effect_uuid==owner
                    assert contact.recipient.actor_uuid==str(packet.target_entity_uuid)
                    assert contact.recipient.grid==packet.spatial_source.target_position
                    assert clock<=contact.at_ms<=clock+group.complete_ms
        state=reduce_lineage(state,root);clock+=group.complete_ms+2500
    assert expected and set(received)==expected
    assert any(row.formation for row in received.values())
    repeated=[row for row in received.values() if not row.formation]
    assert repeated and min(row.at_ms for row in repeated)>max(row.at_ms for row in received.values() if row.formation)
    pygame.quit()
