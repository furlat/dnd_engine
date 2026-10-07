"""On-demand views of permitted sheet/item facts and exact native discovery."""

from dataclasses import replace

import pygame

from dnd.core.base_actions import AvailableActionsResult
from dnd.core.equipment_types import BodyPart, WeaponSlot, RingSlot, EquipmentSlot
from dnd.player.facts import PlayerState, PlayerHUDSnapshot, PlayerActor, PlayerCharacterSheet
from game.ui.action_bar import ActionFamily, ActionFamilyKey, cost_label
from game.ui.layout import UILayout
from game.ui.media import UIPresentationCatalog, action_reference, item_reference, reference_label, actor_portrait_reference, ui_image
from game.ui.primitives import UIFonts, GOLD, MUTED, TEXT, BORDER, panel, text, button, wrap, icon_control
from game.ui.skin import UISkin
from game.ui.types import UIFocus, UIFrame, UIHit


_SLOTS: dict[str,EquipmentSlot] = {slot.value:slot for slot in (*BodyPart,*WeaponSlot,*RingSlot)}


def library_families(actions: AvailableActionsResult, families: tuple[ActionFamily,...],
                     category: str, search: str) -> tuple[tuple[int,ActionFamily],...]:
    return tuple((index,family) for index,family in enumerate(families)
        if actions.all_actions[family.indices[0]].interaction_affordance.surface=='action_bar'
        and (category=='all' or category=='spells' and actions.all_actions[family.indices[0]].is_spell
             or category=='items' and family.key.source_item_uuid is not None
             or category=='actions' and not actions.all_actions[family.indices[0]].is_spell and family.key.source_item_uuid is None)
        and search.casefold() in actions.all_actions[family.indices[0]].display_name.casefold())


def draw_panels(screen: pygame.Surface, geometry: UILayout, font: UIFonts, skin: UISkin,
                media: UIPresentationCatalog, images: dict[tuple[str,tuple[int,int]],pygame.Surface],
                state: PlayerState, hud: PlayerHUDSnapshot | None, actions: AvailableActionsResult | None,
                families: tuple[ActionFamily,...], focus: UIFocus, shortcuts: tuple[ActionFamilyKey,...],
                *, ready: bool, mouse: tuple[int,int]) -> UIFrame:
    if focus.panel not in ('inventory','sheet','spellbook','reactions'):
        return UIFrame()
    px=lambda value:round(value*geometry.scale)
    selected=state.actors.get(focus.selected_actor or state.current_actor_uuid or state.observer_uuid)
    sheet=next((sheet for sheet in hud.sheets if selected is not None and sheet.actor_uuid==selected.uuid),None) if hud else None
    own_turn=ready and selected is not None and actions is not None and selected.uuid==actions.entity_uuid
    library_rows=(library_families(actions,families,focus.library_filter,focus.search_text)
        if actions is not None and selected is not None and selected.uuid==actions.entity_uuid else ())
    handler_rows=(actions.handler_details if actions is not None and selected is not None and selected.uuid==actions.entity_uuid else ())
    left=geometry.party.right+px(16)
    width=min(geometry.viewport.width-left-px(16),px(920 if focus.panel=='inventory' else 460))
    sheet_values=_sheet_lines(media,selected,sheet) if selected is not None else ()
    sheet_width=width-px(36+112)
    sheet_lines=tuple(line for value in sheet_values for line in wrap(value,font.body,max(px(80),sheet_width)))
    desired=(px(142+min(6,max(1,len(library_rows)))*59) if focus.panel=='spellbook' else
        px(80+min(6,max(1,len(handler_rows)))*60) if focus.panel=='reactions' else
        px(80)+max(px(128),len(sheet_lines)*font.body.get_linesize()) if focus.panel=='sheet' else
        px(100+min(6,max(4,len(selected.controlled_items or ()) if selected else 0))*53))
    height=min(px(440),geometry.viewport.height-px(130)) if focus.panel=='inventory' else min(desired,max(px(180),geometry.vitals.top-px(112)))
    rect=pygame.Rect(left,px(100),width,height)
    panel(screen,rect,skin,scale=geometry.scale,mouse=mouse)
    title={'inventory':'Inventory','sheet':'Character','spellbook':'Abilities','reactions':'Automatic reactions'}[focus.panel]
    text(screen,font.heading,title+(f' — {selected.name}' if selected else ''),(rect.left+px(18),rect.top+px(16)),max_width=rect.width-px(90))
    hits=[button(screen,font.body,UIHit(pygame.Rect(rect.right-px(55),rect.top+px(12),px(38),px(32)),
        'close',label='×'),mouse,skin,scale=geometry.scale)]
    content=pygame.Rect(rect.left+px(18),rect.top+px(62),rect.width-px(36),rect.height-px(80))
    previous=screen.get_clip();screen.set_clip(content)
    detail_scroll_max=None
    detail_scroll_rect=None
    if focus.panel=='spellbook':
        categories=('all','spells','actions','items')
        for index,category in enumerate(categories):
            hit=UIHit(pygame.Rect(content.left+index*px(88),content.top,px(82),px(28)),
                'library_filter',index,label=category.title())
            hits.append(button(screen,font.small,hit,mouse,skin,scale=geometry.scale))
        search=pygame.Rect(content.left,content.top+px(35),content.width,px(28))
        text(screen,font.small,'Search: '+(focus.search_text or 'type to filter'),search.topleft,MUTED)
        if actions is not None and selected is not None and selected.uuid==actions.entity_uuid:
            rows=library_rows
            visible=max(1,(content.height-px(80))//px(59))
            start=min(focus.popup_scroll,max(0,len(rows)-visible))
            for offset,(index,family) in enumerate(rows[start:start+visible]):
                row=actions.all_actions[family.indices[0]]
                row_rect=pygame.Rect(content.left,content.top+px(70)+offset*px(59),content.width,px(54))
                reference=action_reference(media,row.behavior_id,row.configured_action_ref,provided_by_id=row.provided_by_id)
                if row.is_attack and selected is not None and row.weapon_slot is not None:
                    item=next((item for item in selected.visual_loadout.layers if item.slot==row.weapon_slot),None)
                    if item is not None:
                        reference=item_reference(media,item.item_id)
                image=ui_image(media,reference,(px(45),px(45)),images)
                if image is not None:
                    screen.blit(image,image.get_rect(center=(row_rect.left+px(23),row_rect.centery)))
                label=row.display_name
                if family.key.source_item_uuid is not None:
                    label+=' · item power'
                text(screen,font.body,label,(row_rect.left+px(55),row_rect.top+px(3)),max_width=row_rect.width-px(130))
                reason=cost_label(row) if row.valid_targets else row.availability_status.value.replace('_',' ')
                text(screen,font.small,reason,(row_rect.left+px(55),row_rect.top+px(29)),MUTED,max_width=row_rect.width-px(130))
                hits.append(UIHit(row_rect,'family',index,label=row.description,enabled=own_turn,
                    discovery_generation=actions.discovery_generation))
                if family.key.source_item_uuid is None:
                    pin=UIHit(pygame.Rect(row_rect.right-px(65),row_rect.top+px(9),px(60),px(30)),
                        'pin',label='Unpin' if family.key in shortcuts else 'Pin',family_key=family.key,
                        discovery_generation=actions.discovery_generation)
                    hits.append(button(screen,font.small,pin,mouse,skin,scale=geometry.scale))
            if not rows:
                text(screen,font.body,'No matching abilities',(content.left,content.top+px(80)),MUTED)
        else:
            text(screen,font.body,'Abilities become selectable on this character’s turn.',(content.left,content.top+px(80)),MUTED)
    elif focus.panel=='inventory' and selected is not None:
        inventory_hits,detail_scroll_max=_inventory(screen,content,font,skin,media,images,selected,sheet,actions,focus,
            ready=own_turn,mouse=mouse,scale=geometry.scale)
        hits.extend(inventory_hits)
        detail_scroll_rect=pygame.Rect(content.left+px(490),content.top,content.width-px(490),content.height)
    elif focus.panel=='sheet' and selected is not None:
        portrait=ui_image(media,actor_portrait_reference(media,selected),
            (px(96),px(128)),images,portrait=True,portrait_role='sheet')
        if portrait is not None:
            screen.blit(portrait,content.topleft)
            content.width-=portrait.width+px(16)
            content.left+=portrait.width+px(16)
        wrapped=tuple(line for value in sheet_values for line in wrap(value,font.body,content.width))
        start=min(focus.popup_scroll,max(0,len(wrapped)-content.height//font.body.get_linesize()))
        capacity=max(1,content.height//font.body.get_linesize())
        for offset,line in enumerate(wrapped[start:start+capacity]):
            text(screen,font.body,line,(content.left,content.top+offset*font.body.get_linesize()),TEXT)
    elif focus.panel=='reactions':
        rows=handler_rows
        for offset,row in enumerate(rows[focus.popup_scroll:]):
            y=content.top+offset*px(60)
            if y>=content.bottom:
                break
            text(screen,font.body,row.name,(content.left,y),max_width=content.width-px(130))
            text(screen,font.small,row.trigger_event.replace('_',' ').title(),(content.left,y+px(25)),MUTED,max_width=content.width-px(130))
            hit=UIHit(pygame.Rect(content.right-px(110),y,px(105),px(34)),'handler',
                identity=row.uuid,label='Enabled' if row.enabled else 'Disabled',enabled=own_turn,
                discovery_generation=actions.discovery_generation if actions else None)
            hits.append(button(screen,font.small,hit,mouse,skin,scale=geometry.scale))
        if not rows:
            text(screen,font.body,'No reaction preferences disclosed for this character.',content.topleft,MUTED)
    screen.set_clip(previous)
    return UIFrame((hits[0],*(replace(hit,rect=hit.rect.clip(content)) for hit in hits[1:] if hit.rect.colliderect(content))),(rect,),detail_scroll_max,detail_scroll_rect)


def _sheet_lines(media: UIPresentationCatalog, actor: PlayerActor, sheet: PlayerCharacterSheet | None) -> tuple[str,...]:
    label=lambda value:value.replace('_',' ').title()
    lines=[f'HP {actor.normal_hp}/{actor.maximum_hp} · AC {actor.armor_class}']
    if sheet is not None:
        lines.extend((f'{label(sheet.species.name) if sheet.species else "—"} · {label(sheet.background.name) if sheet.background else "—"}',
            ' · '.join(f'{label(level.class_id.name)} {sum(row.class_id==level.class_id for row in sheet.class_levels)}'
                for index,level in enumerate(sheet.class_levels) if not any(row.class_id==level.class_id for row in sheet.class_levels[:index])),
            ' · '.join(f'{name.title()} {score}' for name,score in sheet.abilities),f'Proficiency +{sheet.proficiency_bonus}',
            'Skills: '+(', '.join(map(label,sheet.skills)) or '—'),
            'Expertise: '+(', '.join(map(label,sheet.expertise)) or '—'),
            'Saves: '+', '.join(map(label,sheet.saves))))
        lines.extend(f'{resource.label}: {resource.current}/{resource.maximum}' for resource in sheet.resources)
    names={item.item_uuid:item.name for item in actor.controlled_items or ()}
    lines.extend(f'{label(item.slot)}: {names.get(item.item_uuid) or reference_label(media,item_reference(media,item.item_id))}'
        for item in actor.visual_loadout.layers)
    return tuple(lines)


def _inventory(screen: pygame.Surface, content: pygame.Rect, font: UIFonts, skin: UISkin,
               media: UIPresentationCatalog, images: dict[tuple[str,tuple[int,int]],pygame.Surface],
               actor: PlayerActor, sheet: PlayerCharacterSheet | None, actions: AvailableActionsResult | None,
               focus: UIFocus, *, ready: bool, mouse: tuple[int,int], scale: float) -> tuple[tuple[UIHit,...],int]:
    px=lambda value:round(value*scale)
    if actor.controlled_items is None:
        text(screen,font.body,'Inventory is not disclosed to the current observer.',content.topleft,MUTED)
        return (),0
    hits=[]
    equipped={item.item_uuid:item.slot for item in actor.visual_loadout.layers}
    items=actor.controlled_items
    selected=next((item for item in items if item.item_uuid==focus.selected_item),items[0] if items else None)
    gear=pygame.Rect(content.left,content.top,px(210),content.height)
    cell=px(40);gap=px(8)
    pairs=((BodyPart.HEAD,BodyPart.AMULET),(BodyPart.CLOAK,BodyPart.BODY),
           (BodyPart.HANDS,BodyPart.LEGS),(RingSlot.LEFT,RingSlot.RIGHT),
           (BodyPart.BACKPACK,BodyPart.FEET),(WeaponSlot.MELEE_MAIN,WeaponSlot.MELEE_OFF),
           (WeaponSlot.RANGED_MAIN,WeaponSlot.RANGED_OFF))
    portrait=ui_image(media,actor_portrait_reference(media,actor),(px(96),px(128)),images,
        portrait=True,portrait_role='sheet')
    if portrait is not None:
        screen.blit(portrait,portrait.get_rect(midtop=(gear.centerx,gear.top+px(54))))
    for row,pair in enumerate(pairs):
        for side,slot in enumerate(pair):
            rect=pygame.Rect(gear.left if side==0 else gear.right-cell,gear.top+row*(cell+gap),cell,cell)
            layer=next((layer for layer in actor.visual_loadout.layers if layer.slot==slot.value),None)
            image=ui_image(media,item_reference(media,layer.item_id),(28,28),images) if layer else None
            icon_control(screen,rect,image,selected=focus.equipment_slot==slot,hover=rect.collidepoint(mouse),scale=scale)
            if layer is None:
                pygame.draw.circle(screen,BORDER,rect.center,max(1,px(2)))
            name=next((item.name for item in items if layer is not None and item.item_uuid==layer.item_uuid),'Empty')
            hits.append(UIHit(rect,'equipment_slot',equipment_slot=slot,label=slot.value.replace('_',' ').title()+' · '+name))
    bag=pygame.Rect(gear.right+px(24),content.top,px(232),content.height)
    cell=px(52);gap=px(5);columns=max(1,(bag.width+gap)//(cell+gap))
    visible_rows=max(1,bag.height//(cell+gap))
    start=min(focus.popup_scroll,max(0,(len(items)+columns-1)//columns-visible_rows))*columns
    for offset,item in enumerate(items[start:start+columns*visible_rows]):
        rect=pygame.Rect(bag.left+(offset%columns)*(cell+gap),bag.top+(offset//columns)*(cell+gap),cell,cell)
        image=ui_image(media,item_reference(media,item.item_id),(28*max(1,int(scale)),28*max(1,int(scale))),images)
        icon_control(screen,rect,image,selected=focus.equipment_slot is None and selected is not None and selected.item_uuid==item.item_uuid,
            hover=rect.collidepoint(mouse),scale=scale)
        if item.stack_count>1:
            label=font.small.render(str(item.stack_count),True,TEXT)
            screen.blit(label,label.get_rect(bottomright=(rect.right-px(3),rect.bottom-px(2))))
        if item.item_uuid in equipped:
            pygame.draw.circle(screen,GOLD,(rect.left+px(5),rect.top+px(5)),max(2,px(2)))
        hits.append(UIHit(rect,'inventory_item',identity=item.item_uuid,label=item.name+'\n'+(item.description or '')))
    x=content.left+px(490)
    pygame.draw.line(screen,BORDER,(x-px(12),content.top),(x-px(12),content.bottom))
    if focus.equipment_slot is not None:
        slot=focus.equipment_slot
        text(screen,font.body,slot.value.replace('_',' ').title(),(x,content.top),GOLD)
        compatible={identity for identity,slots in sheet.compatible_item_slots if slot.value in slots} if sheet else set()
        candidates=tuple(item for item in items if item.item_uuid in compatible)
        maximum=max(0,len(candidates)*px(54)+px(75)-content.height)
        y=content.top+px(38)-min(focus.item_detail_scroll,maximum)
        for item in candidates:
            rect=pygame.Rect(x,y,content.right-x,px(48))
            current=equipped.get(item.item_uuid)==slot.value
            if current or rect.collidepoint(mouse):
                pygame.draw.rect(screen,(34,40,45),rect)
            image=ui_image(media,item_reference(media,item.item_id),(28*max(1,int(scale)),28*max(1,int(scale))),images)
            if image is not None:
                screen.blit(image,image.get_rect(midleft=(rect.left+px(5),rect.centery)))
            text(screen,font.small,item.name,(rect.left+px(45),rect.top+px(14)),GOLD if current else TEXT,max_width=rect.width-px(48))
            hits.append(UIHit(rect,'equip',identity=item.item_uuid,equipment_slot=slot,
                label=item.name,enabled=ready and not current))
            y+=px(54)
        if not candidates:
            text(screen,font.small,'No compatible items',(x,y),MUTED)
        equipped_layer=next((layer for layer in actor.visual_loadout.layers if layer.slot==slot.value),None)
        if equipped_layer is not None:
            control=UIHit(pygame.Rect(x,y+px(8),content.right-x,px(30)),'unequip',identity=equipped_layer.item_uuid,equipment_slot=slot,label='Unequip',enabled=ready)
            hits.append(button(screen,font.small,control,mouse,skin,scale=scale))
        return tuple(hits),maximum
    if selected is None:
        text(screen,font.body,'No items in inventory.',content.topleft,MUTED)
        return tuple(hits),0
    lines=[selected.description or '',f'{selected.rarity.value.title()} · {selected.weight:g} lb']
    if selected.charges is not None:
        lines.append('Unlimited charges' if selected.charges<0 else f'Charges: {selected.charges}/{selected.max_charges}')
    if selected.damage_dice:
        lines.append(f'{selected.damage_dice} {(selected.damage_type or "").title()} · '+', '.join(value.replace('_',' ').title() for value in selected.weapon_properties))
    lines.extend(effect.display_name+(' (suppressed)' if effect.suppression_provider_uuids else '') for effect in selected.item_effects)
    native_rows=tuple((index,row) for index,row in enumerate(actions.all_actions)
        if row.source_item_uuid==selected.item_uuid and row.interaction_affordance.surface!='world') if actions is not None else ()
    slot=equipped.get(selected.item_uuid)
    compatible=next((slots for identity,slots in sheet.compatible_item_slots if identity==selected.item_uuid),()) if sheet else ()
    wrapped=tuple(line for value in lines if value for line in wrap(value,font.small,content.right-x))
    controls=len(native_rows)+(1 if slot in _SLOTS else sum(value in _SLOTS for value in compatible))
    title_lines=wrap(selected.name,font.body,content.right-x)
    title_height=len(title_lines)*font.body.get_linesize()+px(12)
    maximum=max(0,title_height+len(wrapped)*font.small.get_linesize()+px(18)+controls*px(35)-content.height)
    y=content.top-min(focus.item_detail_scroll,maximum)
    for line in title_lines:
        text(screen,font.body,line,(x,y),GOLD);y+=font.body.get_linesize()
    y+=px(12)
    for line in wrapped:
        text(screen,font.small,line,(x,y),MUTED);y+=font.small.get_linesize()
    y+=px(18)
    # Item action variants still go through the same family/row selector.
    for index,row in native_rows:
        hit=UIHit(pygame.Rect(x,y,content.right-x,px(30)),'variant',index,
            label=row.display_name,enabled=ready and bool(row.valid_targets),
            discovery_generation=actions.discovery_generation if actions else None)
        hits.append(button(screen,font.small,hit,mouse,skin,scale=scale));y+=px(35)
    if slot is not None and slot in _SLOTS:
        hit=UIHit(pygame.Rect(x,y,content.right-x,px(30)),'unequip',identity=selected.item_uuid,
            equipment_slot=_SLOTS[slot],label='Unequip to inventory',enabled=ready)
        hits.append(button(screen,font.small,hit,mouse,skin,scale=scale))
    elif sheet is not None:
        for slot in compatible:
            if slot not in _SLOTS:
                continue
            hit=UIHit(pygame.Rect(x,y,content.right-x,px(30)),'equip',identity=selected.item_uuid,
                equipment_slot=_SLOTS[slot],label=f'Equip: {slot.replace("_"," ").title()}',enabled=ready)
            hits.append(button(screen,font.small,hit,mouse,skin,scale=scale));y+=px(35)
    return tuple(hits),maximum
