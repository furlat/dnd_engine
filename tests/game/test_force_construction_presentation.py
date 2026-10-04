"""Actual admitted Force owners retain impacts and finite whole-owner retirement."""

from dataclasses import replace

import numpy as np
import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.construction_media import construction_media_draw_commands
from game.construction_media_lifetime import register_construction_lifetimes
from game.player_projection import project_sequence, begin_projection, project_lineage
from game.player_facts import SpatialFact
from dnd.core.events import SpatialChangeEvent, SpatialChangeType
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.animation import ObjectContact
from game.directed_contacts import recorded_surface_contact
from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallDome
from tests.game.construction_scenarios import construction_history


@pytest.mark.parametrize('radius,disintegrate',((None,False),(None,True),(5,True),(10,True)))
def test_native_force_contact_and_whole_owner_retirement(radius,disintegrate):
    pygame.init();pygame.display.set_mode((1,1))
    try:
        data=load_animation_data();history=construction_history(material='force',dome_radius=radius,disintegrate=disintegrate)
        observed=impact=retired=collapsed=False
        for role in ('caster','recipient'):
            before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views[role])))
            records={};now=0.
            if role=='recipient':
                assert not any(isinstance(node.fact,SpatialFact) and node.fact.object_uuid is not None for root in roots for node in root.events)
            for root in roots:
                group=bind_choreography(before,root,data);assert not group.gaps, group.gaps
                records=register_construction_lifetimes(records,before,data,absolute_start_ms=now,choreography=group)
                after=reduce_lineage(before,root)
                if role=='recipient':assert not records
                if records:
                    record=next(iter(records.values()))
                    if record.applied_ms is not None and record.destroyed_ms is None and record.removed_ms is None:
                        observed=True
                        # A received current owner without its birth clock is
                        # a quiet acquisition, never a replayed formation.
                        camera=Camera(zoom=.5).with_focus((9,8))
                        assert construction_media_draw_commands(after,data,0,camera,{})
                        for q in range(4):
                            camera=Camera(quadrant=q,zoom=.5).with_focus((9,8))
                            assert construction_media_draw_commands(after,data,record.applied_ms+1500,camera,records)
                    if record.membrane_impulses and record.destroyed_ms is None and record.removed_ms is None:
                        impact=True
                        at=record.membrane_impulses[-1][0]+100
                        if radius==10:
                            geometry=record.object.item.construction_geometry
                            assert isinstance(geometry,WallAssemblyPresentationGeometry) and isinstance(geometry.path,WallDome)
                            center=np.array((geometry.path.center[0],geometry.base_height_steps,geometry.path.center[1]))
                            assert np.linalg.norm(np.array(record.membrane_impulses[-1][1])-center)==pytest.approx(radius/5+geometry.width_feet/10)
                        changed=[]
                        for q in range(4):
                            camera=Camera(quadrant=q,zoom=1).with_focus((9,8))
                            active=construction_media_draw_commands(after,data,at,camera,records)
                            quiet=construction_media_draw_commands(after,data,at,camera,{key:replace(row,membrane_impulses=()) for key,row in records.items()})
                            assert active and quiet
                            changed.append(any(not np.array_equal(pygame.surfarray.array3d(a.surface),pygame.surfarray.array3d(b.surface)) for a,b in zip(active,quiet)))
                        # A dome's near shell can hide the far-side impulse.
                        assert any(changed)
                    if record.destroyed_ms is not None:
                        collapsed=True
                        if role=='caster':assert len(record.collapse_contacts)==4
                        if radius==10:
                            geometry=record.object.item.construction_geometry
                            assert isinstance(geometry,WallAssemblyPresentationGeometry) and isinstance(geometry.path,WallDome)
                            center=np.array((geometry.path.center[0],geometry.base_height_steps,geometry.path.center[1]))
                            assert all(np.linalg.norm(np.array(point)-center)==pytest.approx(radius/5+geometry.width_feet/10) for point in record.collapse_contacts)
                        assert all(row.destroyed_ms==record.destroyed_ms and row.removed_ms is None for row in records.values())
                        assert not any(t.object_dust is not None for t in group.world_transitions)
                        for q in range(4):
                            camera=Camera(quadrant=q,zoom=.5).with_focus((9,8))
                            assert construction_media_draw_commands(after,data,record.destroyed_ms+100,camera,records)
                            assert not construction_media_draw_commands(after,data,record.destroyed_ms+1200,camera,records)
                    if record.removed_ms is not None:
                        retired=True
                        assert record.destroyed_ms is None
                        assert all(row.removed_ms==record.removed_ms for row in records.values())
                        camera=Camera(zoom=.5).with_focus((9,8))
                        assert construction_media_draw_commands(after,data,record.removed_ms+100,camera,records)
                        assert not construction_media_draw_commands(after,data,record.removed_ms+850,camera,records)
                    assert after.senses is not None
                    hidden=replace(after,senses=replace(after.senses,objects={},visible=()))
                    assert not construction_media_draw_commands(hidden,data,now+group.complete_ms,Camera().with_focus((9,8)),records)
                before=after;now+=group.complete_ms+250
        assert observed and impact and collapsed==disintegrate and retired!=disintegrate, (observed,impact,collapsed,retired,disintegrate)
    finally:
        pygame.quit()


@pytest.fixture(scope='module')
def force_capture():
    data=load_animation_data()
    return data, construction_history(material='force',break_section=False)


def test_known_sections_acquired_without_birth_keep_quiet_clock(force_capture):
    data,history=force_capture
    before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views['caster'])))
    checked=False
    for root in roots:
        if any(isinstance(n.fact,SpatialFact) and n.fact.change_type is SpatialChangeType.OBJECT_PLACED for n in root.events):
            for canceled in (False,True):
                changed_rows=[]
                for node in root.events:
                    if isinstance(node.fact,SpatialFact) and node.fact.object_uuid is not None:
                        node=replace(node,canceled=True) if canceled else replace(node,fact=None)
                    changed_rows.append(node)
                changed=replace(root,events=tuple(changed_rows))
                group=bind_choreography(before,changed,data)
                records=register_construction_lifetimes({},before,data,absolute_start_ms=0,choreography=group)
                assert not any(t.field=='creation' for t in group.world_transitions)
                assert all(row.applied_ms is None for row in records.values())
            checked=True
        before=reduce_lineage(before,root)
    assert checked


@pytest.mark.parametrize('lost_contact,canceled',((True,False),(False,True)))
def test_unwitnessed_or_canceled_native_section_removal_has_no_retirement_fact(force_capture,lost_contact,canceled):
    _,history=force_capture
    state,_=begin_projection(history.views['caster'].initialization)
    checked=False
    for root in history.views['caster'].lineages:
        removals=tuple(event for event in root.events if isinstance(event,SpatialChangeEvent)
            and event.change_type is SpatialChangeType.OBJECT_REMOVED)
        if removals:
            if lost_contact:
                assert state.world.senses is not None
                state.world.senses=replace(state.world.senses,objects={},visible=set())
            if canceled:
                root=replace(root,events=tuple(event.model_copy(update={'canceled':True}) if event in removals else event for event in root.events))
            projected=project_lineage(state,root)
            assert projected is None or not any(isinstance(n.fact,SpatialFact) and n.fact.object_uuid is not None for n in projected.events)
            checked=True
        else:
            project_lineage(state,root)
    assert checked


@pytest.mark.parametrize('quarter',range(4))
def test_rounded_dome_footprint_contact_reaches_original_shell(quarter):
    # The native grid contact is before the continuous shell on every heading.
    direction=np.array(((1.,0.,1.),(1.,0.,-1.),(-1.,0.,-1.),(-1.,0.,1.))[quarter])
    geometry=WallAssemblyPresentationGeometry(path=WallDome(center=(0,0),radius_feet=5),
        base_height_steps=0,width_feet=.1,height_feet=5)
    contact=ObjectContact('received-owner',(float(-direction[0]),float(-direction[2])),0,geometry)
    source=-2*direction;target=-direction
    point=recorded_surface_contact(contact,source,target)
    assert np.linalg.norm(point)==pytest.approx(1.01)
    assert np.dot(point-source,target-source)>np.dot(target-source,target-source)
    assert np.linalg.norm(np.cross(point-source,target-source))<1e-9


@pytest.mark.parametrize('quarter',range(4))
def test_grazing_radius10_cell_registers_on_received_shell(quarter):
    geometry=WallAssemblyPresentationGeometry(path=WallDome(center=(0,0),radius_feet=10),
        base_height_steps=0,width_feet=.1,height_feet=10)
    source=np.array(((-2.,1.,-2.),(-2.,1.,2.),(2.,1.,2.),(2.,1.,-2.))[quarter])
    target=np.array(((-2.,1.,-1.),(-1.,1.,2.),(2.,1.,1.),(1.,1.,-2.))[quarter])
    contact=ObjectContact('received-owner',(float(target[0]),float(target[2])),1,geometry)
    point=recorded_surface_contact(contact,source,target)
    nearest=target*2.01/np.linalg.norm(target)
    assert np.linalg.norm(point)==pytest.approx(2.01)
    assert np.linalg.norm(np.cross(point-source,nearest-source))<1e-9
    assert np.dot(point-source,nearest-source)>0
