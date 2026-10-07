"""Actual dome owners select finite source formation, break and intact removal."""

from dataclasses import replace

import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.construction_media import construction_media_draw_commands
from game.construction_media_lifetime import register_construction_lifetimes
from dnd.player.recorded import project_sequence
from dnd.player.reduction import decode_player_sequence,encode_player_sequence,reduce_lineage
from game.projection import Camera
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.spatial_media_draw import spatial_media_draw_commands
from tests.game.construction_scenarios import construction_history


@pytest.mark.parametrize('radius,broken',((5,False),(10,False),(5,True),(10,True)))
def test_actual_ice_dome_keeps_shared_owner_and_finite_material(radius,broken):
    pygame.init();pygame.display.set_mode((1,1))
    try:
        data=load_animation_data();history=construction_history(dome_radius=radius,break_section=broken)
        observed=retired=fractured=air_seen=air_removed=False
        for role in ('caster','recipient'):
            before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views[role])))
            records={};air_records={};now=0.
            for root in roots:
                group=bind_choreography(before,root,data);assert not group.gaps
                records=register_construction_lifetimes(records,before,data,absolute_start_ms=now,choreography=group)
                air_records=register_spatial_lifetimes(air_records,before,data,absolute_start_ms=now,lineage=root,choreography=group)
                after=reduce_lineage(before,root)
                for identity,record in records.items():
                    if record.applied_ms is not None and record.destroyed_ms is None and record.removed_ms is None:
                        observed=True
                        for q in range(4):
                            camera=Camera(quadrant=q,zoom=.5).with_focus((9,8))
                            held=construction_media_draw_commands(after,data,record.applied_ms+2000,camera,records)
                            assert any(c.owner==str(identity) for c in held)
                        assert after.senses is not None
                        hidden=replace(after,senses=replace(after.senses,objects={},visible=()))
                        assert not construction_media_draw_commands(hidden,data,record.applied_ms+2000,Camera().with_focus((9,8)),records)
                    if record.destroyed_ms is not None:
                        fractured=True
                        assert record.removed_ms is None
                        for q in range(4):
                            active=construction_media_draw_commands(after,data,record.destroyed_ms+500,Camera(quadrant=q,zoom=.5).with_focus((9,8)),records)
                            assert any(c.owner==str(identity) for c in active)
                        assert not construction_media_draw_commands(after,data,record.destroyed_ms+2300,Camera().with_focus((9,8)),records)
                    if record.removed_ms is not None:
                        retired=True
                        assert record.destroyed_ms is None
                        active=construction_media_draw_commands(after,data,record.removed_ms+100,Camera(zoom=.5).with_focus((9,8)),records)
                        assert any(c.owner==str(identity) for c in active)
                        assert not construction_media_draw_commands(after,data,record.removed_ms+750,Camera().with_focus((9,8)),records)
                for identity,record in air_records.items():
                    if record.effect.content_ref.content_id!='spatial_effect.spell.frigid_air':continue
                    assert broken
                    if record.removed_ms is None:
                        air_seen=True
                        at=max(now+group.complete_ms,(record.applied_ms or now)+1000)
                        for q in range(4):
                            commands=spatial_media_draw_commands(after,data,at,Camera(quadrant=q,zoom=.5).with_focus((9,8)),lifetimes=air_records)
                            own=[c for c in commands if c.owner==str(identity)]
                            assert own and all(c.volume is not None and set(c.volume.admitted or ())<=set(record.effect.positions) for c in own)
                    else:
                        air_removed=True
                        commands=spatial_media_draw_commands(after,data,record.removed_ms+850,Camera().with_focus((9,8)),lifetimes=air_records)
                        assert all(c.owner!=str(identity) for c in commands)
                before=after;now+=group.complete_ms+250
        assert observed and fractured==broken and retired!=broken
        assert air_seen==broken and air_removed==broken
    finally:
        pygame.quit()


def test_native_flat_ice_break_retains_only_actual_cold_air_until_concentration_ends():
    pygame.init();pygame.display.set_mode((1,1))
    try:
        data=load_animation_data();history=construction_history(material='ice')
        before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views['caster'])))
        records={};now=0.;seen=removed=False
        for root in roots:
            group=bind_choreography(before,root,data);assert not group.gaps
            records=register_spatial_lifetimes(records,before,data,absolute_start_ms=now,lineage=root,choreography=group)
            after=reduce_lineage(before,root)
            for identity,record in records.items():
                if record.effect.content_ref.content_id!='spatial_effect.spell.frigid_air':continue
                if record.removed_ms is None:
                    seen=True
                    for q in range(4):
                        at=(record.applied_ms or now)+1000
                        commands=spatial_media_draw_commands(after,data,at,Camera(quadrant=q,zoom=.5).with_focus((9,8)),lifetimes=records)
                        own=[c for c in commands if c.owner==str(identity)]
                        assert own and all(c.volume is not None and set(c.volume.admitted or ())<=set(record.effect.positions) for c in own)
                    assert after.senses is not None
                    hidden=replace(after,senses=replace(after.senses,visible=(),spatial_effects={}))
                    assert not spatial_media_draw_commands(hidden,data,at,Camera().with_focus((9,8)),lifetimes=records)
                else:
                    removed=True
                    assert not any(c.owner==str(identity) for c in spatial_media_draw_commands(after,data,record.removed_ms+850,Camera().with_focus((9,8)),lifetimes=records))
            before=after;now+=group.complete_ms+250
        assert seen and removed
    finally:
        pygame.quit()
