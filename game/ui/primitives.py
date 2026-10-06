"""Small measured drawing functions; text is never part of pixel artwork."""

from dataclasses import dataclass

import pygame

from game.ui.types import UIHit
from game.ui.skin import UISkin


PANEL=(21,25,31)
BORDER=(72,74,77)
TEXT=(231,229,221)
MUTED=(150,157,167)
GOLD=(219,181,96)
GREEN=(109,191,140)
RED=(222,114,102)
BLUE=(127,178,223)


@dataclass(frozen=True, slots=True)
class UIFonts:
    body: pygame.font.Font
    small: pygame.font.Font
    heading: pygame.font.Font
    mono: pygame.font.Font
    small_bold: pygame.font.Font


def fonts(scale: float) -> UIFonts:
    family='segoeui,dejavusans,arial'
    return UIFonts(pygame.font.SysFont(family,round(18*scale)),pygame.font.SysFont(family,round(16*scale)),
        pygame.font.SysFont(family,round(21*scale),bold=True),pygame.font.SysFont('consolas,dejavusansmono',round(16*scale)),
        pygame.font.SysFont(family,round(16*scale),bold=True))


def panel(screen: pygame.Surface, rect: pygame.Rect, skin: UISkin, *, scale: float = 1., tooltip: bool = False) -> None:
    pygame.draw.rect(screen,PANEL,rect)
    pygame.draw.rect(screen,BORDER,rect,max(1,round(scale)))
    pygame.draw.line(screen,GOLD,rect.topleft,rect.topright,max(1,round(scale)))


def text(screen: pygame.Surface, font: pygame.font.Font, value: str, position: tuple[int,int],
         color: tuple[int,int,int] = TEXT, *, max_width: int | None = None) -> pygame.Rect:
    if max_width is not None:
        while len(value)>1 and font.size(value)[0]>max_width:
            value=value[:-2]+'…'
    image=font.render(value,True,color)
    return screen.blit(image,position)


def button(screen: pygame.Surface, font: pygame.font.Font, hit: UIHit, mouse: tuple[int,int],
           skin: UISkin, *, scale: float = 1.) -> UIHit:
    state = 'disabled' if not hit.enabled else 'pressed' if hit.rect.collidepoint(mouse) and pygame.mouse.get_pressed()[0] else 'hover' if hit.rect.collidepoint(mouse) else 'normal'
    pygame.draw.rect(screen,(36,41,46) if state in ('hover','pressed') else PANEL,hit.rect)
    pygame.draw.rect(screen,GOLD if state in ('hover','pressed') else BORDER,hit.rect,max(1,round(scale)))
    image=font.render(hit.label,True,TEXT if hit.enabled else MUTED)
    screen.blit(image,image.get_rect(center=hit.rect.center))
    return hit


def wrap(value: str, font: pygame.font.Font, width: int) -> tuple[str,...]:
    result=[]
    for paragraph in value.splitlines() or ('',):
        line=''
        for word in paragraph.split():
            candidate=line+' '+word if line else word
            if line and font.size(candidate)[0]>width:
                result.append(line);line=''
            elif line:
                line+=' '
            for char in word:
                if line and font.size(line+char)[0]>width:
                    result.append(line);line=''
                line+=char
        result.append(line)
    return tuple(result)
