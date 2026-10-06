"""Present dimensions of native variants without constructing an executable row."""

from dataclasses import dataclass

import pygame

from dnd.core.base_actions import AvailableActionInfo, AvailableActionsResult
from game.ui.action_bar import ActionFamily, cost_label
from game.ui.layout import UILayout
from game.ui.media import UIPresentationCatalog, choice_image
from game.ui.primitives import UIFonts, GOLD, MUTED, TEXT, panel, text, button
from game.ui.skin import UISkin
from game.ui.types import UIFocus, UIFrame, UIHit


@dataclass(frozen=True, slots=True)
class VariantChoice:
    dimension: str
    value: str
    label: str
    row_index: int
    selected: bool


def variant_values(row: AvailableActionInfo) -> dict[str,str]:
    values={facet.key:facet.value for facet in row.variant_facets}
    if row.cast_at_level is not None:
        values={'rank':str(row.cast_at_level),**values}
    return values


def initial_variant(actions: AvailableActionsResult, family: ActionFamily, selected: int | None) -> int:
    if selected in family.indices:
        assert selected is not None
        return selected
    return next((index for index in family.indices if actions.all_actions[index].valid_targets),family.indices[0])


def variant_choices(actions: AvailableActionsResult, family: ActionFamily, selected: int) -> tuple[tuple[VariantChoice,...],...]:
    values=variant_values(actions.all_actions[selected])
    dimensions=tuple(dict.fromkeys(key for index in family.indices for key in variant_values(actions.all_actions[index])))
    groups=[]
    for offset,dimension in enumerate(dimensions):
        candidates=[index for index in family.indices if all(
            variant_values(actions.all_actions[index]).get(key)==values.get(key) for key in dimensions[:offset])]
        choices=[]
        options=tuple(dict.fromkeys(variant_values(actions.all_actions[index])[dimension]
            for index in candidates if dimension in variant_values(actions.all_actions[index])))
        for value in options:
            matching=[index for index in candidates if variant_values(actions.all_actions[index]).get(dimension)==value]
            # Prefer preserving later choices, then an admitted row. Every pick
            # still returns one exact discovery index, including depleted ranks.
            index=min(matching,key=lambda index:(
                sum(variant_values(actions.all_actions[index]).get(key)!=values.get(key) for key in dimensions[offset+1:]),
                not bool(actions.all_actions[index].valid_targets)))
            row=actions.all_actions[index]
            label=(f'Level {value}' if dimension=='rank' else
                next(facet.label for facet in row.variant_facets if facet.key==dimension))
            choices.append(VariantChoice(dimension,value,label,index,values.get(dimension)==value))
        if choices:
            groups.append(tuple(choices))
    residual=[index for index in family.indices if variant_values(actions.all_actions[index])==values]
    if len(residual)>1:
        groups.append(tuple(VariantChoice('option',str(index),actions.all_actions[index].display_name,
            index,index==selected) for index in residual))
    return tuple(groups)


def draw_variants(screen: pygame.Surface, geometry: UILayout, font: UIFonts, skin: UISkin,
                  media: UIPresentationCatalog, images: dict[tuple[str,tuple[int,int]],pygame.Surface],
                  actions: AvailableActionsResult, family: ActionFamily, focus: UIFocus,
                  *, ready: bool, mouse: tuple[int,int]) -> UIFrame:
    px=lambda value:round(value*geometry.scale)
    selected=initial_variant(actions,family,focus.variant_index)
    row=actions.all_actions[selected]
    groups=variant_choices(actions,family,selected)
    width=min(px(540),screen.width-px(24))
    cell_width=px(116)
    columns=max(1,(width-px(24))//cell_width)
    group_heights=tuple(px(27)+((len(group)+columns-1)//columns)*px(57) for group in groups)
    height=min(px(115)+sum(group_heights),geometry.bar.top-px(100))
    rect=pygame.Rect(geometry.bar.left,0,width,height);rect.bottom=geometry.bar.top-px(8)
    rect.clamp_ip(geometry.viewport)
    panel(screen,rect,skin,scale=geometry.scale)
    text(screen,font.body,row.display_name,(rect.left+px(12),rect.top+px(10)),max_width=rect.width-px(24))
    content=pygame.Rect(rect.left+px(12),rect.top+px(38),rect.width-px(24),rect.height-px(103))
    previous=screen.get_clip();screen.set_clip(content)
    y=content.top-min(focus.popup_scroll*px(28),max(0,sum(group_heights)-content.height))
    hits=[]
    for group,group_height in zip(groups,group_heights):
        text(screen,font.small,group[0].dimension.replace('_',' ').title(),(content.left,y),MUTED)
        for offset,choice in enumerate(group):
            choice_rect=pygame.Rect(content.left+(offset%columns)*cell_width,y+px(23)+(offset//columns)*px(57),cell_width-px(5),px(51))
            candidate=actions.all_actions[choice.row_index]
            image_size=28*max(1,round(geometry.scale))
            image=choice_image(media,candidate.configured_action_ref,choice.dimension,choice.value,
                variant_values(candidate),(image_size,image_size),images)
            if choice.selected:
                pygame.draw.rect(screen,(43,46,41),choice_rect,border_radius=px(3))
                pygame.draw.line(screen,GOLD,choice_rect.bottomleft,choice_rect.bottomright,max(1,px(1)))
            if image is not None:
                screen.blit(image,(choice_rect.left,choice_rect.top))
            label_point=(choice_rect.left,choice_rect.bottom-font.small.get_linesize())
            text(screen,font.small,choice.label,label_point,TEXT if candidate.valid_targets else MUTED,max_width=choice_rect.width)
            clipped=choice_rect.clip(content)
            if clipped.height:
                hits.append(UIHit(clipped,'variant_pick',choice.row_index,label=choice.label,
                    discovery_generation=actions.discovery_generation))
        y+=group_height
    screen.set_clip(previous)
    reason=cost_label(row) if row.valid_targets else row.availability_status.value.replace('_',' ')
    text(screen,font.small,reason,(rect.left+px(12),rect.bottom-px(58)),MUTED,max_width=rect.width-px(24))
    choose=UIHit(pygame.Rect(rect.left+px(12),rect.bottom-px(36),rect.width-px(24),px(28)),
        'variant',selected,label='Select',enabled=ready and bool(row.valid_targets),discovery_generation=actions.discovery_generation)
    hits.append(button(screen,font.small,choose,mouse,skin,scale=geometry.scale))
    return UIFrame(tuple(hits),(rect,))
