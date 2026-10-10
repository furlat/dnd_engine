"""Native formation/disclosure/removal select actual registered wall phases."""

from dataclasses import replace

import pygame
import pytest

from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from dnd.player.recorded import project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.wall_assembly_media import assembly_media_draw_commands, assembly_media_limitation
from tests.game.assembly_scenarios import assembly_history

DIRECTIONS=((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))


@pytest.fixture(scope='module')
def data():
    pygame.init();pygame.display.set_mode((1,1))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize('program',('thorns','wind'))
@pytest.mark.parametrize('direction',DIRECTIONS)
def test_native_eight_heading_wall_phases_and_subjective_replay(data,program,direction):
    history=assembly_history(program=program,direction=direction)
    observed=False;removed=False
    for observer in ('caster','recipient'):
        before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views[observer])))
        retained={};now=0.
        for root in roots:
            group=bind_choreography(before,root,data);assert not group.gaps
            retained=register_spatial_lifetimes(retained,before,data,absolute_start_ms=now,lineage=root,choreography=group)
            after=reduce_lineage(before,root)
            for owner,record in retained.items():
                binding=data.spatial_media[record.effect.content_ref.content_id]
                if not any(layer.wallAssembly is not None for layer in binding.layers):continue
                effect=(after.senses.spatial_effects.get(owner) if after.senses is not None else None) or record.effect
                assert isinstance(effect.area_geometry,WallAssemblyPresentationGeometry)
                assert assembly_media_limitation(effect,binding) is None
                if record.applied_ms is not None and record.removed_ms is None:
                    observed=True
                    for q in range(4):
                        for offset,phase in ((750,'application'),(3000,'hold')):
                            commands=assembly_media_draw_commands(effect,owner,data,binding,record.applied_ms+offset,
                                Camera(quadrant=q,zoom=1).with_focus(effect.positions[0]),record.applied_ms,None)
                            assert commands, (observer, q, offset, effect.positions)
                            assert all('.'+phase+'.' in str(c.evidence[2]) for c in commands)
                            assert sum(pygame.surfarray.array_alpha(c.surface).sum() for c in commands)>0
                    # Unknown owner keeps its clock; sight loss cannot become fracture or retirement.
                    assert after.senses is not None
                    unknown=replace(after,senses=replace(after.senses,spatial_effects={}))
                    kept=register_spatial_lifetimes(retained,unknown,data,absolute_start_ms=now)
                    assert kept[owner].applied_ms==record.applied_ms and kept[owner].removed_ms is None
                if record.removed_ms is not None:
                    removed=True
                    for q in range(4):
                        commands=assembly_media_draw_commands(record.effect,owner,data,binding,record.removed_ms+250,
                            Camera(quadrant=q,zoom=1).with_focus(effect.positions[0]),record.applied_ms,record.removed_ms)
                        assert commands and all('.removal.' in str(c.evidence[2]) for c in commands)
                        assert not assembly_media_draw_commands(record.effect,owner,data,binding,record.removed_ms+1100,
                            Camera(quadrant=q,zoom=1).with_focus(effect.positions[0]),record.applied_ms,record.removed_ms)
            before=after;now+=group.complete_ms+2500
    assert observed and removed


@pytest.mark.parametrize('program,form',(('thorns','ring'),('wind','corner')))
def test_native_closed_ring_and_ordered_connected_path(data,program,form):
    history=assembly_history(program=program,form=form)
    before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views['caster'])))
    witnessed=False
    for root in roots:
        after=reduce_lineage(before,root)
        if after.senses is not None:
            for owner,effect in after.senses.spatial_effects.items():
                binding=data.spatial_media.get(effect.content_ref.content_id)
                if binding is None or not any(l.wallAssembly for l in binding.layers):continue
                limitation=assembly_media_limitation(effect,binding)
                if limitation is None:
                    for q in range(4):assert assembly_media_draw_commands(effect,owner,data,binding,3000,Camera(quadrant=q,zoom=1).with_focus(effect.positions[0]),0,None)
                    witnessed=True
        before=after
    # Thorns may disclose only the near opaque shell; its whole-ring bank must not reveal unseen cells.
    if program=='wind':assert witnessed
