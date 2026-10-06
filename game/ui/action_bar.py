"""Group exact native variants for display; selections retain their original rows."""

from dataclasses import dataclass

import pygame

from dnd.core.base_actions import AvailableActionInfo, AvailableActionsResult
from game.player_facts import PlayerActor
from game.ui.layout import UILayout
from game.ui.media import UIPresentationCatalog, UIReference, action_reference, item_reference, ui_image
from game.ui.primitives import UIFonts, GOLD, TEXT, MUTED, text
from game.ui.skin import UISkin
from game.ui.types import UIHit, ActionFamilyKey


@dataclass(frozen=True, slots=True)
class ActionFamily:
    key: ActionFamilyKey
    indices: tuple[int, ...]


def action_families(actions: AvailableActionsResult,
                    previous: tuple[ActionFamilyKey, ...] = ()) -> tuple[ActionFamily, ...]:
    grouped: dict[ActionFamilyKey, list[int]] = {}
    for index, row in enumerate(actions.all_actions):
        if row.interaction_affordance.surface == 'world':
            continue
        key = ActionFamilyKey(row.behavior_id, row.configured_action_ref, row.source_item_uuid, row.weapon_slot)
        grouped.setdefault(key, []).append(index)
    order = [key for key in previous if key in grouped]
    # Native-owned facts choose ordering. Execution names/tokens are never parsed.
    new = sorted((key for key in grouped if key not in order), key=lambda key: (
        3 if key.source_item_uuid else 2 if actions.all_actions[grouped[key][0]].is_spell
        else 1 if actions.all_actions[grouped[key][0]].is_attack else 0,
        actions.all_actions[grouped[key][0]].spell_level or 0,
        actions.all_actions[grouped[key][0]].display_name))
    return tuple(ActionFamily(key, tuple(grouped[key])) for key in (*order, *new))


def family_at(families: tuple[ActionFamily, ...], index: int) -> ActionFamily | None:
    return families[index] if 0 <= index < len(families) else None


def default_shortcuts(actions: AvailableActionsResult, families: tuple[ActionFamily, ...],
                      *, capacity: int = 10) -> tuple[ActionFamilyKey, ...]:
    # World clicking owns ordinary movement/attacks and all environmental use.
    # This is a starting UI preference; the ability library can pin any family.
    excluded = {'action.move', 'action.swim', 'action.core.drop', 'action.pick_up'}
    candidates = [family for family in families if family.key.behavior_id not in excluded
        and actions.all_actions[family.indices[0]].interaction_affordance.surface == 'action_bar'
        and not actions.all_actions[family.indices[0]].is_attack
        and any(actions.all_actions[index].valid_targets for index in family.indices)]
    # Prefer class powers and a small spell selection over per-item utilities.
    candidates.sort(key=lambda family: (
        actions.all_actions[family.indices[0]].source_item_uuid is not None,
        0 if family.key.behavior_id in ('action.dash','action.disengage','action.dodge','action.jump')
        else 1 if actions.all_actions[family.indices[0]].provided_by_id.startswith('class_feature.')
        else 2 if actions.all_actions[family.indices[0]].is_spell else 3,
        actions.all_actions[family.indices[0]].spell_level or 0,
    ))
    return tuple(family.key for family in candidates[:capacity])


def shortcut_indices(families: tuple[ActionFamily, ...], shortcuts: tuple[ActionFamilyKey, ...]) -> tuple[int | None, ...]:
    by_key = {family.key:index for index, family in enumerate(families)}
    return tuple(by_key.get(key) for key in shortcuts)


def shortcut_page(page: int, count: int, capacity: int) -> int:
    return max(0, min(page, max(0, (count-1)//capacity)))


def variant_label(row: AvailableActionInfo) -> str:
    values = ([f'Rank {row.cast_at_level}'] if row.cast_at_level else [])
    values.extend(facet.label for facet in row.variant_facets)
    if row.weapon_slot:
        values.append(row.weapon_slot.replace('_', ' ').title())
    if row.source_item_uuid:
        values.append('Item power')
    return ' · '.join(values) or row.display_name


def cost_label(row: AvailableActionInfo) -> str:
    costs = row.costs
    return ' · '.join(f'{cost.cost} {cost.cost_type.replace("_", " ")}'
        + (f' + {cost.resource_cost} {cost.resource_name.replace("_", " ")}' if cost.resource_name else '') for cost in costs
    ) or f'{row.cost_amount} {row.cost_type.replace("_", " ")}'


def draw_action_bar(screen: pygame.Surface, geometry: UILayout, font: UIFonts,
                    skin: UISkin, media: UIPresentationCatalog,
                    images: dict[tuple[str, tuple[int, int]], pygame.Surface],
                    actions: AvailableActionsResult | None, families: tuple[ActionFamily, ...],
                    actor: PlayerActor | None, *, page: int, selected: int | None,
                    ready: bool, mouse: tuple[int, int],
                    shortcuts: tuple[ActionFamilyKey, ...]) -> tuple[UIHit, ...]:
    hits = []
    indices = shortcut_indices(families, shortcuts)
    capacity = geometry.columns
    start = shortcut_page(page, len(indices), capacity)*capacity
    shown = indices[start:start+capacity]
    left = geometry.bar.centerx-(len(shown)+1)*geometry.slot//2
    frame = pygame.transform.scale(skin['pixel_slot']['normal'].image,(geometry.slot,geometry.slot))
    for offset, family_index in enumerate(shown):
        rect = pygame.Rect(left+offset*geometry.slot,geometry.bar.bottom-geometry.slot,geometry.slot,geometry.slot)
        if family_index is None:
            pygame.draw.rect(screen,(13,16,20),rect)
            key=shortcuts[start+offset]
            image=ui_image(media,action_reference(media,key.behavior_id,key.configured_ref),rect.size,images)
            if image is not None:
                screen.blit(image,image.get_rect(center=rect.center))
            veil=pygame.Surface(rect.size,pygame.SRCALPHA);veil.fill((0,0,0,165));screen.blit(veil,rect)
            screen.blit(frame,rect)
            text(screen,font.small,'×',rect.topleft,MUTED)
            hits.append(UIHit(rect,'pin',family_key=key,label='Unavailable. Right-click to remove this shortcut.',enabled=False))
            continue
        family = families[family_index]
        assert actions is not None
        row = actions.all_actions[family.indices[0]]
        # A depleted family remains inspectable, including its disabled ranks.
        enabled = ready and any(actions.all_actions[index].valid_targets for index in family.indices)
        pygame.draw.rect(screen,(13,16,20),rect)
        reference = action_reference(media, row.behavior_id, row.configured_action_ref,
                                     provided_by_id=row.provided_by_id)
        if row.is_attack and actor is not None and row.weapon_slot:
            item = next((item for item in actor.visual_loadout.layers if item.slot == row.weapon_slot), None)
            if item is not None:
                reference = item_reference(media, item.item_id)
        image = ui_image(media, reference, rect.size, images)
        if image is not None:
            screen.blit(image, image.get_rect(center=rect.center))
        else:
            text(screen, font.small, row.display_name[:3], (rect.left+round(4*geometry.scale), rect.centery-font.small.get_height()//2),
                 TEXT if enabled else MUTED)
        if not enabled:
            veil=pygame.Surface(rect.size,pygame.SRCALPHA);veil.fill((0,0,0,140));screen.blit(veil,rect)
        screen.blit(frame,rect)
        if selected in family.indices or rect.collidepoint(mouse):
            pygame.draw.rect(screen,GOLD,rect,width=max(1,round(geometry.scale)))
        if len(family.indices)>1:
            text(screen, font.small, '+', (rect.right-round(12*geometry.scale), rect.top+round(2*geometry.scale)), GOLD)
        if row.source_item_uuid:
            text(screen, font.small, 'i', (rect.left+round(3*geometry.scale), rect.top+round(2*geometry.scale)), GOLD)
        text(screen,font.small,str(offset+1) if offset<9 else '0',(rect.left+round(4*geometry.scale),rect.bottom-font.small.get_height()),TEXT)
        hits.append(UIHit(rect, 'family', family_index, label=row.display_name,
                          discovery_generation=actions.discovery_generation,family_key=family.key))
    end_rect=pygame.Rect(left+len(shown)*geometry.slot,geometry.bar.bottom-geometry.slot,geometry.slot,geometry.slot)
    end=ui_image(media,UIReference('common','end_turn' if ready else 'waiting'),end_rect.size,images)
    if end is not None:
        screen.blit(end,end.get_rect(center=end_rect.center))
    else:
        text(screen,font.small,'End',(end_rect.left+round(5*geometry.scale),end_rect.centery-font.small.get_height()//2),GOLD)
    hits.append(UIHit(end_rect,'end',label='End turn [Space]',enabled=ready))
    if len(indices)>capacity:
        for sign,label in ((-1,'‹'),(1,'›')):
            rect=pygame.Rect(left+len(shown)*geometry.slot+round((0 if sign<0 else 17)*geometry.scale),geometry.bar.top-round(24*geometry.scale),round(17*geometry.scale),round(22*geometry.scale))
            text(screen,font.small,label,rect.topleft,MUTED)
            hits.append(UIHit(rect,'page',sign,label=label))
    return tuple(hits)
