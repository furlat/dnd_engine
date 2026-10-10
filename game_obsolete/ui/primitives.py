"""Small measured drawing functions; text is never part of pixel artwork."""

from dataclasses import dataclass
from functools import lru_cache

import pygame

from game.ui.types import UIHit
from game.ui.skin import UISkin
from game.ui.media_types import UI_FONT_FAMILIES


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
    family=','.join(UI_FONT_FAMILIES['body'])
    return UIFonts(pygame.font.SysFont(family,max(15,round(17*scale))),pygame.font.SysFont(family,max(14,round(15*scale))),
        pygame.font.SysFont(family,max(19,round(21*scale)),bold=True),pygame.font.SysFont(','.join(UI_FONT_FAMILIES['mono']),max(14,round(15*scale))),
        pygame.font.SysFont(family,max(14,round(15*scale)),bold=True))


@lru_cache(maxsize=16)
def _glass_surface(size: tuple[int,int], active: bool) -> pygame.Surface:
    surface=pygame.Surface(size,pygame.SRCALPHA)
    surface.fill((12,17,23,145 if active else 94))
    return surface


def glass(screen: pygame.Surface, rect: pygame.Rect, *, active: bool = False) -> None:
    screen.blit(_glass_surface(rect.size,active),rect)


def panel(screen: pygame.Surface, rect: pygame.Rect, skin: UISkin, *, scale: float = 1., tooltip: bool = False,
          mouse: tuple[int,int] = (-1,-1)) -> None:
    glass(screen,rect,active=tooltip or rect.collidepoint(mouse))
    pygame.draw.rect(screen,BORDER,rect,max(1,round(scale)))


def icon_control(screen: pygame.Surface, rect: pygame.Rect, image: pygame.Surface | None,
                 *, selected: bool = False, hover: bool = False, scale: float = 1.) -> None:
    """One chrome treatment; authored pixels are never tinted or dimmed."""
    pygame.draw.rect(screen,(12,16,21),rect)
    if image is not None:
        screen.blit(image,image.get_rect(center=rect.center))
    pygame.draw.rect(screen,GOLD if selected else TEXT if hover else BORDER,rect,max(1,round(scale)))


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
