"""HUD drawing uses only detached permitted facts and exact discovery rows."""

from typing import Mapping

import pygame

from dnd.core.base_actions import AvailableActionsResult, AvailableSelectionPreview
from game.controls import MenuState, targeting_values
from game.player_facts import PlayerState, PlayerHUDSnapshot
from game.ui.action_bar import ActionFamily, draw_action_bar
from game.ui.layout import UILayout
from game.ui.media import UIPresentationCatalog, UIReference, actor_portrait_reference, ui_image
from game.ui.primitives import UIFonts, TEXT, GOLD, GREEN, RED, BLUE, BORDER, panel, text, button, wrap
from game.ui.skin import UISkin
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
    if focus.panel=='menu':
        hits=[]
        rect=pygame.Rect(0,0,px(330),min(px(468),geometry.viewport.height-px(32)));rect.center=geometry.viewport.center
        panel(screen,rect,skin,scale=scale,mouse=mouse)
        text(screen,font.heading,'Encounter menu',(rect.left+px(20),rect.top+px(16)))
        menu_buttons: tuple[tuple[UIVerb,str,int],...] = (('close','Resume',0),('panel','Inventory [I]',0),('panel','Character [N]',1),
            ('panel','Abilities [K]',2),('panel','Reactions [L]',3),('scale','UI scale',0),('fullscreen','Fullscreen [Alt+Enter]',0),('retry','Restart encounter',0),('quit','Quit',0))
        pitch=(rect.height-px(64))//len(menu_buttons)
        for offset,(verb,label,index) in enumerate(menu_buttons):
            hit=UIHit(pygame.Rect(rect.left+px(16),rect.top+px(53)+offset*pitch,rect.width-px(32),min(px(36),pitch-px(4))),verb,index,label=label)
            hits.append(button(screen,font.body,hit,mouse,skin,scale=scale))
        return UIFrame(tuple(hits),(geometry.viewport,))
    active=state.actors.get(actions.entity_uuid) if actions is not None else None
    hits=list(draw_action_bar(screen,geometry,font,skin,media,images,actions,families,active,
        pages=focus.bar_pages,selected=menu.selected_action if menu.active else None,ready=ready,mouse=mouse,shortcuts=shortcuts,attack_preference=focus.attack_preference))
    blocked=[geometry.bar,geometry.vitals]
    detail_scroll_max=None
    detail_scroll_rect=None
    # Role-specific portraits stay deliberately smaller than action icons.
    # Each bank uses integer scaling; text is measured independently.
    unit=geometry.portrait_scale
    if hud is not None:
        members=[state.actors[identity] for identity in hud.initiative if identity in state.actors]
        step=36*unit+px(8)
        available=max(1,(geometry.initiative.width-px(160))//step)
        current=next((i for i,actor in enumerate(members) if actor.uuid==state.current_actor_uuid),0)
        start=max(0,min(current-available//2,len(members)-available))
        displayed=members[start:start+available]
        left=geometry.initiative.centerx-(len(displayed)*step-px(8))//2
        party_ids={sheet.actor_uuid for sheet in hud.sheets}
        for offset,actor in enumerate(displayed):
            rect=pygame.Rect(left+offset*step,geometry.initiative.top,36*unit,48*unit)
            image=ui_image(media,actor_portrait_reference(media,actor),rect.size,images,portrait=True,portrait_role='initiative')
            if image is not None:
                screen.blit(image,rect)
            current_turn=actor.uuid==state.current_actor_uuid
            pygame.draw.rect(screen,GOLD if current_turn else BORDER,rect,max(1,px(2 if current_turn else 1)))
            hp=shown_hp.get(str(actor.uuid),actor.normal_hp)
            track=pygame.Rect(rect.left,rect.bottom+px(3),rect.width,px(3))
            pygame.draw.rect(screen,(22,27,32),track)
            if hp is not None and actor.maximum_hp:
                pygame.draw.rect(screen,GREEN if actor.uuid in party_ids else RED,
                    (track.left,track.top,round(track.width*max(0,min(1,hp/actor.maximum_hp))),track.height))
            hits.append(UIHit(rect,'inspect',identity=actor.uuid,label=actor.name+(' · Current turn' if current_turn else '')))
            blocked.append(rect)
        for offset,sheet in enumerate(hud.sheets):
            rect=pygame.Rect(geometry.party.left,geometry.party.top+offset*(64*unit+font.small.get_linesize()+px(20)),48*unit,64*unit)
            image=ui_image(media,UIReference('portrait_choice',sheet.portrait_key or ''),rect.size,images,portrait=True,portrait_role='hud')
            if image is not None:
                screen.blit(image,rect)
            current_turn=sheet.actor_uuid==state.current_actor_uuid
            color=GOLD if current_turn else TEXT if sheet.actor_uuid==focus.selected_actor else BORDER
            pygame.draw.rect(screen,color,rect,max(1,px(2 if current_turn else 1)))
            hp=shown_hp.get(str(sheet.actor_uuid),sheet.normal_hp)
            track=pygame.Rect(rect.left,rect.bottom+px(4),rect.width,px(5))
            pygame.draw.rect(screen,(22,27,32),track)
            if hp is not None and sheet.maximum_hp:
                fraction=max(0,min(1,hp/sheet.maximum_hp))
                pygame.draw.rect(screen,GREEN if fraction>.5 else GOLD if fraction>.25 else RED,
                    (track.left,track.top,round(track.width*fraction),track.height))
            hp_label=f'{hp if hp is not None else "?"} / {sheet.maximum_hp}'
            # Health sits on one quiet baseline, not on top of the portrait art.
            value=font.small.render(hp_label,True,TEXT)
            screen.blit(value,value.get_rect(midtop=(rect.centerx,track.bottom+px(3))))
            hit_rect=rect.union(track).inflate(0,px(16))
            hits.append(UIHit(hit_rect,'inspect',identity=sheet.actor_uuid,label=f'{sheet.name} · {hp_label} HP · F{offset+1}'))
            blocked.append(hit_rect)
        if active is not None:
            sheet=next((sheet for sheet in hud.sheets if sheet.actor_uuid==active.uuid),None)
            if sheet is not None:
                x,y=geometry.vitals.centerx-px(65),geometry.vitals.centery
                for key,color,label in (('actions',GREEN,'Action'),('bonus_actions',GOLD,'Bonus action'),('reactions',BLUE,'Reaction')):
                    resource=next((row for row in sheet.resources if row.key==key),None)
                    if resource is None:
                        continue
                    radius=max(2,px(3))
                    for index in range(max(1,resource.maximum)):
                        pygame.draw.circle(screen,color if index<resource.current else BORDER,(x,y),radius)
                        x+=px(10)
                    region=pygame.Rect(x-px(12),y-px(10),px(12),px(20))
                    hits.append(UIHit(region,'inspect',identity=active.uuid,label=f'{label}: {resource.current} / {resource.maximum}'))
                    x+=px(8)
                movement=next((row for row in sheet.resources if row.key=='movement'),None)
                if movement is not None:
                    text(screen,font.small,f'{movement.current} ft',(x+px(4),y-font.small.get_height()//2),TEXT)
    if not focus.log_open:
        log_rect=pygame.Rect(screen.width-px(94),px(20),px(74),px(28))
        pygame.draw.rect(screen,(17,22,28),log_rect)
        text(screen,font.small,'Log',log_rect.move(px(12),px(4)).topleft,TEXT)
        hits.append(UIHit(log_rect,'log',label='Combat log'))
        blocked.append(log_rect)
    # Routine round/history text stays out of the scene. Errors and actual end
    # states remain visible so a rejected command never looks like a dead button.
    if status not in ('Your turn','Playing history'):
        status_image=font.body.render(status,True,TEXT)
        rect=status_image.get_rect(midbottom=(geometry.bar.centerx,geometry.targeting.top-px(16)))
        backdrop=rect.inflate(px(24),px(12))
        pygame.draw.rect(screen,(17,22,28),backdrop)
        screen.blit(status_image,rect)
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
        anchor=next((hit.rect for hit in hits if hit.verb=='family' and hit.index==focus.family),None)
        frame=draw_variants(screen,geometry,font,skin,media,images,actions,families[focus.family],focus,ready=ready,mouse=mouse,anchor=anchor)
        hits.extend(frame.hits);blocked.extend(frame.blocked)
    if focus.context:
        rect=pygame.Rect(focus.context_position,(px(285),px(40+len(focus.context)*37)))
        rect.clamp_ip(geometry.viewport)
        panel(screen,rect,skin,scale=scale,mouse=mouse)
        blocked.append(rect)
        for index,option in enumerate(focus.context):
            hit=UIHit(pygame.Rect(rect.left+px(8),rect.top+px(9)+index*px(37),rect.width-px(16),px(30)),
                'world',index,label=option.label,enabled=ready and option.reason is None,
                discovery_generation=actions.discovery_generation if actions else None)
            hits.append(button(screen,font.small,hit,mouse,skin,scale=scale))
    if focus.panel is not None:
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
