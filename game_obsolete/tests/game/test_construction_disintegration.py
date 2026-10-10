"""A real ray opens only its native wall cube, with finite material dust."""
from dataclasses import replace

import pygame
import pytest

from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry
from game.animation_data import load_animation_data
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.construction_media import construction_media_draw_commands
from game.construction_media_lifetime import register_construction_lifetimes
from dnd.player.recorded import project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.world_animation import WorldTransitionSample
from tests.game.construction_scenarios import construction_history


@pytest.mark.parametrize('material,fracture_after_cut',(('stone',False),('ice',False),('stone',True)))
def test_native_wall_disintegration_keeps_cut_and_dust_on_ray_contact(material,fracture_after_cut):
    pygame.init();pygame.display.set_mode((1,1))
    try:
        data=load_animation_data();history=construction_history(material=material,disintegrate=True,fracture_after_cut=fracture_after_cut)
        seen=ray_bound=fractured=False
        for role in ('caster','recipient'):
            before,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views[role])))
            records={};now=0.
            for root in roots:
                group=bind_choreography(before,root,data);assert not group.gaps
                records=register_construction_lifetimes(records,before,data,absolute_start_ms=now,choreography=group)
                after=reduce_lineage(before,root)
                for transition in group.world_transitions:
                    if transition.object_dust is None:continue
                    seen=True;dust=transition.object_dust
                    nodes=[node for node in group.nodes if isinstance(node.bound,BoundCast)]
                    if nodes:
                        node,=nodes
                        assert isinstance(node.bound,BoundCast)
                        application,=node.bound.timeline.applications
                        assert transition.start_ms==node.start_ms+application.travel_end_ms
                        ray_bound=True
                    assert transition.duration_ms is not None
                    if material=='stone':
                        assert dust.partial and dust.affected_volume is not None
                        assert after.objects[transition.identity].item.construction_geometry is not None
                        assert records[transition.identity].destroyed_ms is None
                    else:
                        assert not dust.partial and transition.identity not in after.objects
                    for q in range(4):
                        camera=Camera(quadrant=q,zoom=1)
                        active=WorldTransitionSample(transition,150.)
                        baseline=construction_media_draw_commands(after,data,now+transition.start_ms+150,camera,records)
                        commands=construction_media_draw_commands(after,data,now+transition.start_ms+150,camera,records,(active,))
                        assert len(commands)>len(baseline)
                        assert all('.destruction.' not in str(c.evidence[2]) for c in commands)
                        ended=WorldTransitionSample(transition,transition.duration_ms)
                        assert len(construction_media_draw_commands(after,data,now+transition.start_ms+150,camera,records,(ended,)))==len(baseline)
                        assert after.senses is not None
                        hidden=replace(after,senses=replace(after.senses,visible=(),objects={}))
                        assert not construction_media_draw_commands(hidden,data,now+transition.start_ms+150,camera,records,(active,))
                    if material=='stone':
                        original=replace(after,objects={**after.objects,transition.identity:dust.object})
                        for q in range(4):
                            retained=[]
                            for zoom in (.35,.5,1):
                                camera=Camera(quadrant=q,zoom=zoom)
                                cut=construction_media_draw_commands(after,data,now+transition.start_ms+150,camera,records)
                                intact=construction_media_draw_commands(original,data,now+transition.start_ms+150,camera,{})
                                cut_alpha=sum(int(pygame.surfarray.array_alpha(c.surface).sum()) for c in cut)
                                intact_alpha=sum(int(pygame.surfarray.array_alpha(c.surface).sum()) for c in intact)
                                assert 0<cut_alpha<intact_alpha
                                retained.append(cut_alpha/intact_alpha)
                            # Zoom changes pixel sampling, never the removed world volume.
                            assert max(retained)-min(retained)<.03,retained
                for identity,record in records.items():
                    if record.destroyed_ms is None or not fracture_after_cut:continue
                    geometry=record.object.item.construction_geometry
                    assert isinstance(geometry,WallAssemblyPresentationGeometry) and geometry.removed_sections
                    fractured=True
                    intact=replace(record,object=replace(record.object,item=replace(record.object.item,construction_geometry=geometry.model_copy(update={'removed_sections':()}))))
                    for q in range(4):
                        for age in (0,500,1000):
                            when=record.destroyed_ms+age;camera=Camera(quadrant=q,zoom=1)
                            cut=construction_media_draw_commands(after,data,when,camera,records)
                            whole=construction_media_draw_commands(after,data,when,camera,{**records,identity:intact})
                            assert cut and all('.destruction.' in str(c.evidence[2]) for c in cut)
                            cut_alpha=sum(int(pygame.surfarray.array_alpha(c.surface).sum()) for c in cut)
                            whole_alpha=sum(int(pygame.surfarray.array_alpha(c.surface).sum()) for c in whole)
                            assert 0<cut_alpha<whole_alpha
                before=after;now+=group.complete_ms+250
        assert seen and ray_bound
        assert fractured==fracture_after_cut
    finally:
        pygame.quit()
