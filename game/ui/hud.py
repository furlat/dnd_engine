"""HUD drawing uses only detached permitted facts and exact discovery rows."""

from typing import Mapping

import pygame

from dnd.core.base_actions import AvailableActionsResult, AvailableSelectionPreview
from game.controls import MenuState, targeting_values
from game.player_facts import PlayerState, PlayerHUDSnapshot
from game.ui.action_bar import ActionFamily, draw_action_bar
from game.ui.layout import UILayout
from game.ui.media import UIPresentationCatalog, actor_portrait_reference, ui_image
from game.ui.primitives import UIFonts, TEXT, MUTED, GOLD, GREEN, panel, text, button, wrap
from game.ui.skin import UISkin, draw_skin
from game.ui.types import UIHit, UIFocus, UIVerb, UIFrame, ActionFamilyKey
from game.ui.variants import draw_variants
from game.ui.panels import draw_panels


def draw_hud(screen: pygame.Surface, geometry: UILayout, font: UIFonts, skin: UISkin,
             media: UIPresentationCatalog, images: dict[tuple[str, tuple[int, int]], pygame.Surface],
             state: PlayerState, hud: PlayerHUDSnapshot | None, actions: AvailableActionsResult | None,
             families: tuple[ActionFamily, ...], menu: MenuState, focus: UIFocus,
             preview: AvailableSelectionPreview | None, *, ready: bool, mouse: tuple[int, int],
             status: str, shown_hp: Mapping[str, int | None], shortcuts: tuple[ActionFamilyKey,...]) -> UIFrame:
    scale=geometry.scale
    px=lambda value:round(value*scale)
    active=state.actors.get(state.current_actor_uuid) if state.current_actor_uuid else None
    selected=state.actors.get(focus.selected_actor or state.current_actor_uuid or state.observer_uuid)
    hits=list(draw_action_bar(screen,geometry,font,skin,media,images,actions,families,active,
        page=focus.bar_page,selected=menu.selected_action if menu.active else None,ready=ready,mouse=mouse,shortcuts=shortcuts))
    blocked=[hit.rect for hit in hits]+[geometry.vitals]
    detail_scroll_max=None
    detail_scroll_rect=None
    portrait_multiple=max(1,int(scale))
    portrait_width=36*portrait_multiple+px(8)
    portrait_height=48*portrait_multiple+px(16)
    text(screen,font.small,f'Round {state.round_number} · {status}',
        (px(16),max(px(90),px(12)+portrait_height+px(10))),MUTED)
    if hud is not None:
        # Only the authorized order; omitted identities create no empty gaps.
        members=[state.actors[identity] for identity in hud.initiative if identity in state.actors]
        step=portrait_width+px(6)
        available=max(1,(geometry.initiative.width-px(96))//step)
        current=next((i for i,actor in enumerate(members) if actor.uuid==state.current_actor_uuid),0)
        start=max(0,min(current-available//2,len(members)-available))
        displayed=members[start:start+available]
        left=screen.width//2-len(displayed)*step//2
        for offset, actor in enumerate(displayed):
            rect=pygame.Rect(left+offset*step,px(12),portrait_width,portrait_height)
            draw_skin(screen,rect,skin['slot']['selected' if actor.uuid==state.current_actor_uuid else 'hover' if actor.uuid==focus.selected_actor else 'normal'],scale=scale)
            reference=actor_portrait_reference(media,actor)
            image=ui_image(media,reference,(rect.width-px(8),rect.height-px(16)),images,portrait=True,portrait_role='initiative')
            if image is not None:
                screen.blit(image,image.get_rect(midtop=(rect.centerx,rect.top+px(4))))
            else:
                text(screen,font.small,actor.name[:3],(rect.left+px(7),rect.top+px(14)))
            hp=shown_hp.get(str(actor.uuid),actor.normal_hp)
            text(screen,font.small,'?' if hp is None else str(hp),(rect.left+px(5),rect.bottom-px(15)),GOLD if actor.uuid==state.current_actor_uuid else TEXT)
            hits.append(UIHit(rect,'inspect',identity=actor.uuid,label=actor.name))
            blocked.append(rect)
    if selected is not None:
        x,y=geometry.vitals.topleft
        portrait=ui_image(media,actor_portrait_reference(media,selected),
            (px(48),px(64)),images,portrait=True,portrait_role='hud')
        if portrait is not None:
            portrait_rect=portrait.get_rect(bottomright=(x-px(8),geometry.bar.top))
            screen.blit(portrait,portrait_rect)
            hits.append(UIHit(portrait_rect,'inspect',identity=selected.uuid,label=selected.name))
            blocked.append(portrait_rect)
        hp=shown_hp.get(str(selected.uuid),selected.normal_hp)
        text(screen,font.body,selected.name,(x,y),max_width=geometry.vitals.width)
        text(screen,font.small,f'{hp if hp is not None else "?"}/{selected.maximum_hp} HP · AC {selected.armor_class}',(x,y+px(21)),GREEN)
        sheet=next((sheet for sheet in hud.sheets if sheet.actor_uuid==selected.uuid),None) if hud else None
        if sheet is not None:
            resources={row.key:row for row in sheet.resources}
            values=[f'{label} {resources[key].current}' for key,label in
                (('actions','Action'),('bonus_actions','Bonus'),('reactions','Reaction'),('movement','Move')) if key in resources]
            text(screen,font.small,' · '.join(values),(geometry.vitals.right+px(12),y+px(21)),MUTED,
                max_width=geometry.bar.right-geometry.vitals.right-px(12))
    log_rect=pygame.Rect(screen.width-px(66),px(14),px(52),px(25))
    text(screen,font.small,'Log',log_rect.topleft,MUTED)
    hits.append(UIHit(log_rect,'log',label='Combat log'))
    blocked.append(log_rect)
    if menu.active and actions is not None:
        blocked.append(geometry.targeting)
        row=actions.all_actions[menu.selected_action]
        x,y=geometry.targeting.left+px(6),geometry.targeting.top+px(8)
        values=targeting_values(menu,row)
        allocations=len(values)+len(menu.selected_positions)
        text(screen,font.body,row.display_name+(f' · {allocations}' if allocations else ''),(x,y),max_width=geometry.targeting.width-px(92))
        target_buttons: tuple[tuple[UIVerb,str,bool],...] = (('confirm','✓',preview is not None and preview.can_confirm),('cancel','×',True))
        for offset,(verb,label,enabled) in enumerate(target_buttons):
            rect=pygame.Rect(geometry.targeting.right-px(76)+offset*px(38),geometry.targeting.top+px(3),px(32),px(32))
            hits.append(button(screen,font.small,UIHit(rect,verb,label=label,enabled=enabled),mouse,skin,scale=scale))
    if focus.family is not None and actions is not None and 0<=focus.family<len(families):
        frame=draw_variants(screen,geometry,font,skin,media,images,actions,families[focus.family],focus,ready=ready,mouse=mouse)
        hits.extend(frame.hits);blocked.extend(frame.blocked)
    if focus.context:
        rect=pygame.Rect(focus.context_position,(px(285),px(40+len(focus.context)*37)))
        rect.clamp_ip(geometry.viewport)
        panel(screen,rect,skin,scale=scale)
        blocked.append(rect)
        for index,option in enumerate(focus.context):
            hit=UIHit(pygame.Rect(rect.left+px(8),rect.top+px(9)+index*px(37),rect.width-px(16),px(30)),
                'world',index,label=option.label,enabled=ready and option.reason is None,
                discovery_generation=actions.discovery_generation if actions else None)
            hits.append(button(screen,font.small,hit,mouse,skin,scale=scale))
    if focus.panel=='menu':
        hits=[]
        rect=pygame.Rect(0,0,px(330),px(468));rect.center=geometry.viewport.center
        panel(screen,rect,skin,scale=scale)
        blocked.append(geometry.viewport)
        text(screen,font.heading,'Encounter menu',(rect.left+px(20),rect.top+px(16)))
        menu_buttons: tuple[tuple[UIVerb,str,int],...] = (('close','Resume',0),('panel','Inventory [I]',0),('panel','Character [N]',1),
            ('panel','Abilities [K]',2),('panel','Reactions [L]',3),('scale','UI scale',0),('fullscreen','Fullscreen [Alt+Enter]',0),('retry','Restart encounter',0),('quit','Quit',0))
        for offset,(verb,label,index) in enumerate(menu_buttons):
            hit=UIHit(pygame.Rect(rect.left+px(16),rect.top+px(53+offset*44),rect.width-px(32),px(36)),verb,index,label=label)
            hits.append(button(screen,font.body,hit,mouse,skin,scale=scale))
    elif focus.panel is not None:
        frame=draw_panels(screen,geometry,font,skin,media,images,state,hud,actions,families,focus,shortcuts,ready=ready,mouse=mouse)
        hits=list(frame.hits)
        blocked.extend(frame.blocked)
        detail_scroll_max=frame.detail_scroll_max
        detail_scroll_rect=frame.detail_scroll_rect
    return UIFrame(tuple(hits),tuple(blocked),detail_scroll_max,detail_scroll_rect)


def draw_tooltip(screen: pygame.Surface, geometry: UILayout, font: UIFonts, skin: UISkin,
                 lines: tuple[str, ...], position: tuple[int, int]) -> None:
    if not lines:
        return
    width=min(geometry.viewport.width-round(24*geometry.scale),round(320*geometry.scale))
    wrapped=[line for value in lines for line in wrap(value,font.small,width-round(24*geometry.scale))]
    maximum=max(1,(geometry.viewport.height-round(32*geometry.scale))//font.small.get_linesize())
    if len(wrapped)>maximum:
        wrapped=wrapped[:maximum-1]+['…']
    height=len(wrapped)*font.small.get_linesize()+round(24*geometry.scale)
    rect=pygame.Rect(position,(width,height));rect.clamp_ip(geometry.viewport)
    panel(screen,rect,skin,scale=geometry.scale,tooltip=True)
    for index,line in enumerate(wrapped):
        text(screen,font.small,line,(rect.left+round(12*geometry.scale),rect.top+round(10*geometry.scale)+index*font.small.get_linesize()))
