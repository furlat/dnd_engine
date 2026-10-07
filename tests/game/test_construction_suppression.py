"""Moving native Antimagic clips retained wall surfaces without rebirth."""

from dataclasses import replace

import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography, bind_motion
from game.construction_media import construction_media_draw_commands
from game.construction_media_lifetime import register_construction_lifetimes
from dnd.player.recorded import project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.volume_media import compose_volume
from tests.game.construction_scenarios import construction_history


@pytest.mark.parametrize('material',('ice','force','stone'))
def test_native_moving_field_masks_exact_sections_and_restores_same_clock(material):
    pygame.init();pygame.display.set_mode((1,1))
    try:
        data=load_animation_data()
        history=construction_history(material=material,break_section=False,antimagic=True)
        state,roots=decode_player_sequence(encode_player_sequence(project_sequence(history.views['caster'])))
        records={};now=0.;seen_mask=False;seen_restore=False;owner_dates={};owners=set()
        for root in roots:
            motion=bind_motion(state,root,data)
            group=None if motion is not None else bind_choreography(state,root,data)
            records=register_construction_lifetimes(records,state,data,absolute_start_ms=now,choreography=group,motion=motion)
            after=reduce_lineage(state,root)
            active={identity:obj for identity,obj in after.objects.items() if obj.item.construction_geometry is not None}
            if active:
                owners.update(active)
                for identity in active:
                    previous=owner_dates.setdefault(identity,records[identity].applied_ms)
                    assert records[identity].applied_ms==previous
                suppressed=any(obj.item.construction_suppressions for obj in active.values())
                if suppressed:
                    assert material!='stone'
                    quiet=replace(after,objects={identity:replace(obj,item=replace(obj.item,construction_suppressions=()))
                        for identity,obj in after.objects.items()})
                    lost=[]
                    for q in range(4):
                        camera=Camera(quadrant=q,zoom=.5).with_focus((10,7))
                        clipped=construction_media_draw_commands(after,data,now+2500,camera,records)
                        full=construction_media_draw_commands(quiet,data,now+2500,camera,records)
                        def alpha(commands):
                            return sum(int(pygame.surfarray.array_alpha(compose_volume(c.surface,c.volume,camera,
                                destination=c.destination)[0] if c.volume is not None else c.surface).sum()) for c in commands)
                        lost.append(alpha(full)-alpha(clipped))
                    assert all(value>=0 for value in lost),lost
                    seen_mask |= any(value>0 for value in lost)
                elif seen_mask:
                    seen_restore=True
            timeline=motion if motion is not None else group
            assert timeline is not None
            state=after;now+=timeline.complete_ms+250
        assert owners and seen_mask==(material!='stone') and seen_restore==(material!='stone')
    finally:
        pygame.quit()
