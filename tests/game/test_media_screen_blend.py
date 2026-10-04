"""Canvas screen/source-over parity at the ordinary draw-command blit boundary."""

import numpy as np
import pygame
import pytest

from game.media_blend import SCREEN_BLEND, blit_media, blit_media_commands
from game.draw_commands import DrawCommand
from game.fixture_depth import split_world_depth


@pytest.mark.parametrize('source,destination,global_alpha', [
    ((140,60,210,255),(50,120,200,255),255),
    ((240,180,80,96),(30,40,50,255),180),
    ((80,220,160,180),(200,30,40,90),255),
    ((240,100,80,120),(0,0,0,0),255),
    ((200,160,220,0),(60,80,100,120),255),
])
def test_screen_matches_source_over_equation_without_mutating_source(source,destination,global_alpha):
    front=pygame.Surface((1,1),pygame.SRCALPHA);front.fill(source);front.set_alpha(global_alpha)
    back=pygame.Surface((1,1),pygame.SRCALPHA);back.fill(destination)
    original=pygame.image.tobytes(front,'RGBA')
    blit_media(back,front,(0,0),SCREEN_BLEND)
    a,b=source[3]/255*global_alpha/255,destination[3]/255
    out_a=a+b*(1-a)
    expected=[]
    for s,d in zip(source[:3],destination[:3]):
        blend=1-(1-s/255)*(1-d/255)
        premultiplied=(1-a)*b*d/255+a*((1-b)*s/255+b*blend)
        expected.append(round(255*premultiplied/out_a) if out_a else 0)
    assert tuple(back.get_at((0,0)))==(*expected,round(out_a*255))
    assert pygame.image.tobytes(front,'RGBA')==original


def test_screen_respects_negative_placement_destination_clip_and_normal_flags():
    front=pygame.Surface((4,4),pygame.SRCALPHA);front.fill((80,60,40,127))
    back=pygame.Surface((4,4),pygame.SRCALPHA);back.fill((25,35,45,255));back.set_clip((1,1,2,2))
    before=pygame.surfarray.array3d(back)
    rect=blit_media(back,front,(-1,-1),SCREEN_BLEND)
    assert rect==pygame.Rect(1,1,2,2)
    changed=np.any(pygame.surfarray.array3d(back)!=before,axis=2)
    assert changed.sum()==4 and changed[1:3,1:3].all()
    for flag in (0,pygame.BLEND_RGB_ADD,pygame.BLEND_RGBA_MULT):
        actual=back.copy();expected=back.copy()
        blit_media(actual,front,(0,0),flag);expected.blit(front,(0,0),special_flags=flag)
        assert pygame.image.tobytes(actual,'RGBA')==pygame.image.tobytes(expected,'RGBA')


@pytest.mark.parametrize('color', [(220,80,20,128),(180,120,90,40),(255,200,0,255)])
def test_complementary_source_frames_keep_original_opacity(color):
    original=pygame.Surface((2,2),pygame.SRCALPHA);original.fill(color)
    samples=[]
    for index,weight in enumerate((64,191)):
        part=original.copy();part.set_alpha(weight)
        samples.append(DrawCommand((100,0.,0.,1,(str(index),)),part,(1,1),0,(),media_mix_group=('owner','cell')))
    target=pygame.Surface((4,4),pygame.SRCALPHA)
    blit_media_commands(target,samples)
    assert tuple(target.get_at((1,1)))==color
    assert target.get_at((0,0)).a==0
    assert tuple(original.get_at((0,0)))==color


def test_crossfade_frames_keep_their_distinct_depths_around_an_actor():
    first=pygame.Surface((2,1),pygame.SRCALPHA);first.fill((255,0,0,255));first.set_alpha(128)
    second=pygame.Surface((2,1),pygame.SRCALPHA);second.fill((0,0,255,255));second.set_alpha(127)
    actor=pygame.Surface((2,1),pygame.SRCALPHA);actor.fill((0,255,0,255))
    commands=[DrawCommand((100,0.,0.,1,('source',str(i))),sample,(0,0),0,(),
        world_depth=np.array(depth)[:,None],world_depth_group=('same-source',),media_mix_group=('same-frame-mix',))
        for i,sample,depth in ((0,first,(-1.,1.)),(1,second,(1.,-1.)))]
    commands.append(DrawCommand((100,0.,0.,1,('actor',)),actor,(0,0),0,(),role='actor'))
    target=pygame.Surface((2,1),pygame.SRCALPHA)
    blit_media_commands(target,sorted(split_world_depth(commands),key=lambda c:c.key))
    # First pixel keeps only the blue sample in front, second only red. Mixing
    # both samples before the physical cuts would incorrectly make both purple.
    assert tuple(target.get_at((0,0)))==(0,128,127,255)
    assert tuple(target.get_at((1,0)))==(128,127,0,255)
