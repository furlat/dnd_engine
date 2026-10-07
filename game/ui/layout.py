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
    party: pygame.Rect
    art_scale: int
    portrait_scale: int
    scale: float
    columns: int
    slot: int
    gap: int
    blocks: tuple[pygame.Rect, ...]
    block_columns: tuple[int, ...]
    supported: bool


def layout(viewport: tuple[int,int], ui_scale: float = 1., *, log_open: bool = False,
           bar_counts: tuple[int, ...] = (6, 0, 0, 0)) -> UILayout:
    width,height=viewport
    scale=max(.85,min(width/1600,height/900)*ui_scale)
    px=lambda value:max(1,round(value*scale))
    art_scale=max(1,round(2*scale))
    portrait_scale=max(1,int(min(width/1280,height/720)*ui_scale))
    slot,gap=28*art_scale,0
    log_width=min(px(420),width//3)
    log=pygame.Rect(width-log_width,0,log_width,height)
    play_width=width
    # Fixed two-row blocks; allocate columns, never resize the authored icons.
    # A narrow viewport pages a block instead of mixing it into another block.
    spacing=px(16)
    present=sum(count>0 for count in bar_counts)
    budget=max(present,min(12,(play_width-px(32)-slot-present*spacing)//slot))
    limits=(3,6,4,3)
    wanted=[min(limit,max(2,(count+1)//2)) if count else 0
            for count,limit in zip(bar_counts,limits,strict=True)]
    columns=[min(2,want) for want in wanted]
    while sum(columns)>budget:
        index=max((i for i,c in enumerate(columns) if c>1),key=lambda i:columns[i])
        columns[index]-=1
    while sum(columns)<min(budget,sum(wanted)):
        index=max((i for i,c in enumerate(columns) if c<wanted[i]),key=lambda i:wanted[i]-columns[i])
        columns[index]+=1
    label_height=px(25)
    row_gap=px(4)
    rows=2
    bar=pygame.Rect(0,0,(sum(columns)+1)*slot+present*spacing,rows*slot+(rows-1)*row_gap+label_height)
    bar.midbottom=(play_width//2,height-px(18))
    blocks=[]
    x=bar.left
    for col in columns:
        blocks.append(pygame.Rect(x,bar.top,col*slot,bar.height))
        if col:
            x+=col*slot+spacing
    vitals=pygame.Rect(bar.left,bar.top-px(29),bar.width,px(22))
    # The log overlays the battlefield above the fixed controls; opening it
    # never changes action positions, wrapping or keyboard bindings.
    log.height=vitals.top
    targeting=pygame.Rect(0,0,min(px(390),play_width-px(32)),px(38));targeting.midbottom=(play_width//2,vitals.top-px(12))
    initiative=pygame.Rect(px(12),px(16),play_width-px(24),48*portrait_scale+px(6))
    party=pygame.Rect(px(20),max(initiative.bottom+px(32),height//3),48*portrait_scale,2*(64*portrait_scale+px(38)))
    modal=pygame.Rect(0,0,min(width-px(48),px(920)),min(height-px(48),px(620)));modal.center=(width//2,height//2)
    return UILayout(pygame.Rect(0,0,width,height),bar,log,vitals,targeting,initiative,modal,party,art_scale,portrait_scale,
        scale,sum(columns),slot,gap,tuple(blocks),tuple(columns),width>=960 and height>=540)
