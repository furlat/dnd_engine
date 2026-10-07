"""Present dimensions of native variants without constructing an executable row."""

from dataclasses import dataclass

import pygame

from dnd.core.base_actions import AvailableActionInfo, AvailableActionsResult
from game.ui.action_bar import ActionFamily, variant_values
from game.ui.layout import UILayout
from game.ui.media import UIPresentationCatalog, choice_image, action_reference, ui_image
from game.ui.primitives import UIFonts, GOLD, MUTED, TEXT, panel, text, icon_control
from game.ui.skin import UISkin
from game.ui.types import UIFocus, UIFrame, UIHit


@dataclass(frozen=True, slots=True)
class VariantChoice:
    dimension: str
    value: str
    label: str
    row_index: int
    selected: bool


def initial_variant(actions: AvailableActionsResult, family: ActionFamily, selected: int | None) -> int:
    if selected in family.indices:
        assert selected is not None
        return selected
    return min(family.indices, key=lambda index: (
        not bool(actions.all_actions[index].valid_targets),
        actions.all_actions[index].restricted_action_budget is None))


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
                not bool(actions.all_actions[index].valid_targets),
                actions.all_actions[index].restricted_action_budget is None))
            row=actions.all_actions[index]
            label=(f'Level {value}' if dimension=='rank' else
                next(facet.label for facet in row.variant_facets if facet.key==dimension))
            choices.append(VariantChoice(dimension,value,label,index,values.get(dimension)==value))
        if choices:
            groups.append(tuple(choices))
    residual=[index for index in family.indices if variant_values(actions.all_actions[index])==values
        and actions.all_actions[index].restricted_action_budget is None]
    if len(residual)>1:
        groups.append(tuple(VariantChoice('option',str(index),actions.all_actions[index].display_name,
            index,index==selected) for index in residual))
    return tuple(groups)


def draw_variants(screen: pygame.Surface, geometry: UILayout, font: UIFonts, skin: UISkin,
                  media: UIPresentationCatalog, images: dict[tuple[str,tuple[int,int]],pygame.Surface],
                  actions: AvailableActionsResult, family: ActionFamily, focus: UIFocus,
                  *, ready: bool, mouse: tuple[int,int], anchor: pygame.Rect | None = None) -> UIFrame:
    """A compact choice strip: shared level symbols, authored variant artwork."""
    px=lambda value:round(value*geometry.scale)
    selected=initial_variant(actions,family,focus.variant_index)
    groups=tuple(group for group in variant_choices(actions,family,selected) if len(group)>1)
    if not groups:
        return UIFrame()
    cell,gap,padding=geometry.slot,px(4),px(6)
    columns=min(6,max(len(group) for group in groups),max(1,(screen.width-2*padding)//(cell+gap)))
    widths=tuple(min(columns,len(group))*(cell+gap)-gap for group in groups)
    heights=tuple(((len(group)+columns-1)//columns)*(cell+gap) for group in groups)
    width=max(widths)+2*padding
    height=min(sum(heights)-gap+2*padding,max(cell+2*padding,geometry.vitals.top-px(32)))
    rect=pygame.Rect(anchor.left if anchor else geometry.bar.left,0,width,height)
    rect.bottom=geometry.vitals.top-px(4)
    rect.clamp_ip(geometry.viewport)
    panel(screen,rect,skin,scale=geometry.scale,mouse=mouse)
    content=rect.inflate(-2*padding,-2*padding)
    previous=screen.get_clip();screen.set_clip(content)
    y=content.top-min(focus.popup_scroll*(cell+gap),max(0,sum(heights)-gap-content.height))
    hits=[UIHit(rect,'surface')]
    for group,group_height in zip(groups,heights,strict=True):
        for offset,choice in enumerate(group):
            choice_rect=pygame.Rect(content.left+(offset%columns)*(cell+gap),y+(offset//columns)*(cell+gap),cell,cell)
            candidate=actions.all_actions[choice.row_index]
            following=tuple(g for g in variant_choices(actions,family,choice.row_index) if len(g)>1)
            terminal=choice.dimension==following[-1][0].dimension
            enabled=ready and (not terminal or bool(candidate.valid_targets))
            if choice.dimension=='rank':
                icon_control(screen,choice_rect,None,selected=choice.selected,hover=choice_rect.collidepoint(mouse),scale=geometry.scale)
                color=GOLD if choice.selected else TEXT if enabled else MUTED
                centre=choice_rect.center
                radius=cell//3
                pygame.draw.polygon(screen,color,((centre[0],centre[1]-radius),(centre[0]+radius,centre[1]),
                    (centre[0],centre[1]+radius),(centre[0]-radius,centre[1])),max(1,px(1)))
                symbols={'1':'I','2':'II','3':'III','4':'IV','5':'V','6':'VI','7':'VII','8':'VIII','9':'IX'}
                label=font.small.render(symbols.get(choice.value,choice.value),True,color)
                screen.blit(label,label.get_rect(center=centre))
            else:
                image=choice_image(media,candidate.configured_action_ref,choice.dimension,choice.value,
                    variant_values(candidate),choice_rect.size,images)
                if image is None:
                    image=ui_image(media,action_reference(media,candidate.behavior_id,candidate.configured_action_ref,
                        provided_by_id=candidate.provided_by_id),choice_rect.size,images)
                icon_control(screen,choice_rect,image,selected=choice.selected,hover=choice_rect.collidepoint(mouse),scale=geometry.scale)
                if image is None:
                    text(screen,font.small,str(offset+1),choice_rect.move(px(5),px(3)).topleft,MUTED)
            clipped=choice_rect.clip(content)
            if clipped.height:
                hits.append(UIHit(clipped,'variant' if terminal else 'variant_pick',choice.row_index,
                    label=choice.label,enabled=enabled,discovery_generation=actions.discovery_generation))
        y+=group_height
    screen.set_clip(previous)
    # The pointer can cross the small gap from its source button to the strip.
    bridge=rect.union(anchor) if anchor else rect
    return UIFrame(tuple(hits),(rect,bridge))
