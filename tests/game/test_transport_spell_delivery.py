"""Committed doorway groups retain endpoints, timing and body clipping in replay."""

import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.portal_art import DoorwayArt
from game.portal_animation import portal_body
from game.portal_draw import portal_draw_commands
from game.absence_media import absence_poses, absence_draw_commands
from game.body_presentation import sample_body_presentation
from game.condition_media_lifetime import register_condition_lifetimes
from dnd.types.actor import SpatialDisposition
from dnd.core.events import EventType
from game.player_facts import ConditionChangeFact, SpatialFact
from dnd.core.events import SpatialChangeType
from game.player_reduction import reduce_lineage
from game.projection import Camera
from tests.game.player_helpers import player_history
from tests.game.transport_spell_scenarios import transport_spell_history


@pytest.fixture(scope='module')
def data():
    pygame.init()
    pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('program,count',[('door',1),('door_passenger',2),('door_mishap',0)])
def test_native_transfer_group_opens_and_arrives_together_after_byte_replay(data,program,count):
    history=transport_spell_history(program=program)
    for role in history.views:
        state,roots=player_history(history,role=role)
        cues=[]
        for root in roots:
            group=bind_choreography(state,root,data)
            assert not group.gaps,group.gaps
            cues.extend(group.portals)
            for cue in group.portals:
                assert isinstance(cue.art,DoorwayArt)
                middle=(cue.fall_start_ms+cue.disappear_ms)/2
                body=portal_body(cue,middle)
                assert body is not None and body.clip != 'Idle'
                sample=sample_choreography(group,middle)
                sample_choreography(group,group.complete_ms)
                assert sample_choreography(group,middle)==sample
                for q in range(4):
                    commands=portal_draw_commands(sample.displayed,data,middle,Camera(quadrant=q),(),sample.portals)
                    assert commands
                    assert all(command.surface.get_bounding_rect().width for command in commands)
            state=reduce_lineage(state,root)
        assert len(cues)==count
        assert len({cue.start_ms for cue in cues}) <= 1
        assert len({cue.arrival_ms for cue in cues}) <= 1


@pytest.mark.parametrize('saved',[False,True])
def test_absence_echo_uses_actual_departure_pose_and_actual_return_after_replay(data,saved):
    history=transport_spell_history(program='banish_saved' if saved else 'banish_return')
    for role in history.views:
        state,roots=player_history(history,role=role)
        records={};clock=1000.;departures=[];returns=[];absent_seen=False
        for root in roots:
            group=bind_choreography(state,root,data)
            assert not group.gaps,group.gaps
            records=register_condition_lifetimes(records,state,data,absolute_start_ms=clock,
                lineage=root,choreography=group)
            after=reduce_lineage(state,root)
            absent_seen |= any(a.spatial_disposition is not SpatialDisposition.PRESENT for a in after.actors.values())
            for record in records.values():
                assert record.absence_pose is not None
                departures.append(record.applied_ms)
                if record.returned_ms is not None:
                    returns.append(record.returned_ms)
                start=record.returned_ms or record.applied_ms
                assert start is not None
                when=start+600
                if clock<=when<=clock+group.complete_ms:
                    frame=sample_body_presentation(state,after,data,when-clock,when,{},choreography=group)
                    poses=absence_poses(frame.poses,frame.displayed,records,data,when)
                    selected=[p for p in poses if p.body.actor_uuid==str(record.actor_uuid)]
                    assert len(selected)==1
                    assert selected[0].appearance_override is not None
                    assert selected[0].appearance_override.absence is not None
                    first=selected[0].body
                    frozen=absence_poses((),frame.displayed,records,data,when+100)
                    assert next(p.body for p in frozen if p.body.actor_uuid==str(record.actor_uuid))==first
                    for q in range(4):
                        assert absence_draw_commands(frame.displayed,records,data,when,Camera(quadrant=q))
            state=after;clock+=group.complete_ms+500
        assert absent_seen is not saved
        assert bool(departures) is not saved and bool(returns) is not saved
        if not saved:
            assert len(set(departures))==len(set(returns))==1
            assert returns[0]>departures[0]


@pytest.mark.parametrize('program,returns',[('banish_foreign_return',True),
    ('banish_permanent',False),('banish_pending',True)])
def test_return_echo_requires_actual_return_and_survives_pending_placement(data,program,returns):
    history=transport_spell_history(program=program)
    state,roots=player_history(history,role='caster')
    records={};clock=1000.;seen_return=False;seen_pending=False;had_departure=False
    own_removals=[]
    for root in roots:
        group=bind_choreography(state,root,data)
        assert not group.gaps,group.gaps
        records=register_condition_lifetimes(records,state,data,absolute_start_ms=clock,
            lineage=root,choreography=group)
        after=reduce_lineage(state,root)
        had_departure |= bool(records)
        own_removals.extend(node.fact.condition for node in root.events
            if isinstance(node.fact,ConditionChangeFact)
            and node.fact.event_type is EventType.CONDITION_REMOVAL
            and node.fact.condition.behavior_id == 'condition.spell.banishment')
        seen_pending |= any(a.spatial_disposition is SpatialDisposition.RETURN_PENDING for a in after.actors.values())
        seen_return |= any(record.returned_ms is not None for record in records.values())
        if any(a.spatial_disposition is SpatialDisposition.HOME_PLANE for a in after.actors.values()):
            assert all(record.returned_ms is None for record in records.values())
        state=after
        clock+=group.complete_ms+5000
    assert had_departure
    assert seen_return is returns
    # Pending occupancy is private; the caster only learns the eventual arrival.
    assert not seen_pending
    if not returns:
        assert own_removals
        assert all(member.resulting_stats is None and member.resulting_tile is None
            and member.resulting_item is None and member.resulting_max_hp is None
            and member.resulting_ac is None for member in own_removals)
        assert not absence_poses((),state,records,data,clock+5000)
        assert not absence_draw_commands(state,records,data,clock+5000,Camera())


def test_reacquiring_an_unseen_return_does_not_replay_the_return_portal(data):
    history=transport_spell_history(program='banish_hidden_return')
    state,roots=player_history(history,role='caster')
    records={};clock=1000.;departed=set();reacquired=False
    for root in roots:
        group=bind_choreography(state,root,data)
        assert not group.gaps,group.gaps
        records=register_condition_lifetimes(records,state,data,absolute_start_ms=clock,
            lineage=root,choreography=group)
        departed.update(record.actor_uuid for record in records.values())
        after=reduce_lineage(state,root)
        for identity in departed:
            actor=after.actors.get(identity)
            if actor is not None and actor.spatial_disposition is SpatialDisposition.PRESENT:
                reacquired=True
        assert not any(isinstance(node.fact,SpatialFact)
            and node.fact.change_type is SpatialChangeType.ENTITY_ENTERED
            and node.fact.entity_uuid in departed for node in root.events)
        assert all(record.returned_ms is None for record in records.values())
        state=after;clock+=group.complete_ms+500
    assert departed and reacquired
    assert not absence_draw_commands(state,records,data,clock+5000,Camera())
