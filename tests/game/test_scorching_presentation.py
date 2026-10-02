"""Actual ray events and source pixels share contact, direction and painter order."""

from math import hypot

import numpy as np
import pygame
import pytest

from game.animation import ActorContact, BodySample, ProjectileSample, sample_cast, project_projectile
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, animation_draw_commands, load_animation_media
from game.animation_types import RigLayer
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence,encode_player_sequence,reduce_lineage
from game.projectile_media import projectile_frame_layers
from game.projection import Camera, painter_key, project_screen
from tests.game.scorching_scenarios import scorching_history

DIRECTIONS=((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))


@pytest.fixture(scope='module')
def data():
    pygame.init(); pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('direction',DIRECTIONS)
@pytest.mark.parametrize('split,miss',((False,False),(True,False),(True,True)))
def test_native_rays_keep_allocation_contacts_and_finite_frames(data,direction,split,miss):
    history=scorching_history(direction=direction,split=split,miss=miss)
    checked=0
    for observer in ('caster','recipient'):
        before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
        for root in roots:
            group=bind_choreography(before,root,data); assert not group.gaps
            for node in group.nodes:
                if not isinstance(node.bound,BoundCast): continue
                checked+=1; timeline=node.bound.timeline
                assert timeline.recipe.definitionRef.content_id=='spell.scorching_ray'
                assert len(timeline.applications)==3
                assert all(a.source.hit is not miss for a in timeline.applications)
                assert all(isinstance(a.source.target,ActorContact) for a in timeline.applications)
                assert len({a.source.target.actor_uuid for a in timeline.applications
                    if isinstance(a.source.target,ActorContact)})==(2 if split else 1)
                projectile=timeline.recipe.projectile; assert projectile is not None
                assert projectile.sourceSockets is not None and projectile.travel.fitDuration
                for row in timeline.applications:
                    travel=next(p for p in row.projectile_intervals if p.name=='travel')
                    assert not travel.phase.loop and travel.phase.frames==14
                    assert travel.start_ms==row.travel_start_ms and travel.end_ms==row.travel_end_ms
                    impact=tuple(p for p in row.projectile_intervals if p.name=='impact')
                    assert bool(impact) is not miss
                    if impact:
                        assert impact[0].start_ms==row.travel_end_ms and impact[0].phase.frames==32
                    if miss:
                        assert row.hp_ms is None
                    else:
                        assert row.hp_ms is not None and row.hp_ms >= row.travel_end_ms
            before=reduce_lineage(before,root)
    assert checked==2


@pytest.mark.parametrize('direction',DIRECTIONS)
def test_actual_eight_heading_trail_pixels_point_toward_the_native_contact(data,direction):
    history=scorching_history(direction=direction)
    before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views['caster'])))
    timeline=next(node.bound.timeline for root in roots for node in bind_choreography(before,root,data).nodes
        if isinstance(node.bound,BoundCast))
    row=timeline.applications[0]; age=row.travel_start_ms+.8*(row.travel_end_ms-row.travel_start_ms)
    sample=sample_cast(timeline,age)
    for q in range(4):
        effect=next(p for p in sample.projectiles if isinstance(p,ProjectileSample) and p.application_id==row.source.application_id)
        effect=project_projectile(timeline,effect,q)
        assert effect.rotation_radians==0
        asset=data.projectile_assets[effect.asset_id]; projectile=timeline.recipe.projectile
        assert projectile is not None and projectile.sprite is not None
        layer,=projectile_frame_layers(data,asset,'travel',effect.column,asset.rowOrder[effect.row],projectile.sprite,{})
        alpha=pygame.surfarray.array_alpha(layer.image).astype(float);x,y=np.indices(alpha.shape)
        # The original physical root is the leading head. Its retained emitter
        # history trails backward, independently of gameplay distance or sockets.
        centroid=np.array([(alpha*(x+layer.offset[0]-192)).sum(),(alpha*(y+layer.offset[1]-192)).sum()])/alpha.sum()
        camera=Camera(quadrant=q,zoom=1);origin=project_screen((0,0),camera);end=project_screen(direction,camera)
        expected=np.array(end)-origin
        cosine=-np.dot(centroid,expected)/(hypot(*centroid)*hypot(*expected))
        assert cosine>.93,(direction,q,centroid,expected)


def test_paired_contact_layers_bracket_recipient_in_every_camera_without_global_overlay(data):
    history=scorching_history()
    before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views['caster'])))
    timeline=next(node.bound.timeline for root in roots for node in bind_choreography(before,root,data).nodes
        if isinstance(node.bound,BoundCast))
    appearance=(RigLayer('body','NakedBody'),RigLayer('head','Head10'))
    media=load_animation_media(timeline,{a.actor_uuid:appearance for a in
        (timeline.source.caster,*(r.target for r in timeline.source.applications))
        if isinstance(a,ActorContact)})
    row=timeline.applications[0]; sample=sample_cast(timeline,row.travel_end_ms+6*1000/32)
    for q in range(4):
        camera=Camera(quadrant=q,zoom=.5).with_focus(row.source.target.grid)
        commands=animation_draw_commands(timeline,sample,media,camera)
        layers=[c for c in commands if len(c.evidence)>10 and c.evidence[2]=='fire.scorching.impact'
            and c.evidence[10]==row.source.application_id]
        assert len(layers)==2
        target=row.source.target
        assert isinstance(target,ActorContact)
        actor_key=painter_key(target.grid,elevation_steps=target.elevation_steps,
            quadrant=q,role='actor',identity=target.actor_uuid)
        assert layers[0].key[:3]==layers[1].key[:3]==actor_key[:3]
        assert layers[0].key<actor_key<layers[1].key
        foreground=ActorContact('unrelated',(target.grid[0]+1,target.grid[1]+1),'S',1)
        extra=actor_draw_commands(data,BodySample('unrelated','Idle',frame=0,facing='S'),foreground,appearance,media.body_rows,camera)
        assert extra and all(c.key[0]==100 for c in layers)
        # Local rear/front changes keep the ordinary scene depth bands.
        assert all(c.key[:3]!=extra[-1].key[:3] for c in layers)
