"""One logical HUD scale, measured against the current framebuffer."""

from dataclasses import dataclass

import pygame


@dataclass(frozen=True, slots=True)
class UILayout:
    viewport: pygame.Rect
    bar: pygame.Rect
    log: pygame.Rect
    vitals: pygame.Rect
    targeting: pygame.Rect
    initiative: pygame.Rect
    modal: pygame.Rect
    scale: float
    columns: int
    slot: int
    gap: int
    supported: bool


def layout(viewport: tuple[int,int], ui_scale: float = 1.) -> UILayout:
    width,height=viewport
    scale=min(width/1280,height/720)*ui_scale
    scale=max(.75,scale)
    px=lambda value:max(1,round(value*scale))
    columns=10 if width>=px(900) else 8
    slot,gap=28*max(1,round(2*scale)),0
    bar=pygame.Rect(0,0,columns*(slot+gap)+slot+px(12),slot+px(10))
    bar.midbottom=(width//2,height-px(12))
    vitals=pygame.Rect(bar.left,bar.top-px(52),min(px(280),bar.width//2),px(43))
    targeting=pygame.Rect(0,0,min(px(390),width-px(32)),px(38));targeting.midbottom=(width//2,vitals.top-px(8))
    log=pygame.Rect(width-px(372),px(92),px(360),max(px(60),targeting.top-px(104)))
    initiative=pygame.Rect(px(12),px(12),width-px(24),px(68))
    modal=pygame.Rect(0,0,min(width-px(48),px(920)),min(height-px(48),px(620)));modal.center=(width//2,height//2)
    return UILayout(pygame.Rect(0,0,width,height),bar,log,vitals,targeting,initiative,modal,
        scale,columns,slot,gap,width>=960 and height>=540)
