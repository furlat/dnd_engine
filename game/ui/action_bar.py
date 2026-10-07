"""Group exact native variants for display; selections retain their original rows."""

from dataclasses import dataclass

import pygame

from dnd.core.base_actions import AvailableActionInfo, AvailableActionsResult
from dnd.player.facts import PlayerActor
from game.ui.layout import UILayout
from game.ui.media import UIPresentationCatalog, UIReference, action_reference, item_reference, ui_image
from game.ui.primitives import UIFonts, GOLD, MUTED, text, icon_control
from game.ui.skin import UISkin
from game.ui.types import UIHit, UIVerb, ActionFamilyKey


@dataclass(frozen=True, slots=True)
class ActionFamily:
    key: ActionFamilyKey
    indices: tuple[int, ...]


def variant_values(row: AvailableActionInfo) -> dict[str, str]:
    values = {facet.key: facet.value for facet in row.variant_facets}
    if row.cast_at_level is not None:
        values = {'rank': str(row.cast_at_level), **values}
    return values


def family_has_choices(actions: AvailableActionsResult, family: ActionFamily) -> bool:
    """Budget alternatives do not add a second gameplay verb or choice strip."""
    ordinary = [actions.all_actions[i] for i in family.indices
                if actions.all_actions[i].restricted_action_budget is None]
    return len(ordinary) > 1 or len({tuple(variant_values(actions.all_actions[i]).items())
                                    for i in family.indices}) > 1


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


def default_shortcuts(actions: AvailableActionsResult, families: tuple[ActionFamily, ...]) -> tuple[ActionFamilyKey, ...]:
    # Groups own their pages. A known spell must not vanish just because its
    # rank lost a contest for eight global pins or currently has no target.
    excluded = {'action.move', 'action.swim', 'action.core.drop', 'action.pick_up'}
    return tuple(family.key for family in families
        if family.key.behavior_id not in excluded
        and (family.key.source_item_uuid is None or actions.all_actions[family.indices[0]].is_attack)
        and not (family.key.weapon_slot in ('MELEE_MAIN','RANGED_MAIN')
                 and family.key.behavior_id in ('action.attack','action.feature.extra_attack'))
        and actions.all_actions[family.indices[0]].interaction_affordance.surface == 'action_bar')


@dataclass(frozen=True, slots=True)
class ActionBlock:
    label: str
    families: tuple[int, ...]


def action_blocks(actions: AvailableActionsResult | None, families: tuple[ActionFamily, ...],
                  shortcuts: tuple[ActionFamilyKey, ...], actor: PlayerActor | None) -> tuple[ActionBlock, ...]:
    groups: list[list[int]] = [[], [], [], []]
    owned = {item.item_uuid for item in actor.controlled_items or ()} if actor else set()
    if actions is not None:
        for index, family in enumerate(families):
            row = actions.all_actions[family.indices[0]]
            if row.interaction_affordance.surface == 'world' or row.behavior_id in ('action.core.drop','action.pick_up') or (row.weapon_slot in ('MELEE_MAIN','RANGED_MAIN') and row.behavior_id in ('action.attack','action.feature.extra_attack')):
                continue
            if row.source_item_uuid is not None and not row.is_attack:
                if row.source_item_uuid in owned:
                    groups[3].append(index)
                continue
            if family.key not in shortcuts:
                continue
            group = (1 if row.is_spell else 2 if row.provided_by_id.startswith(('class_feature.','metamagic.','feat.'))
                     or row.behavior_id.startswith('action.class.')
                     or (row.origin_root_id or '').startswith('class_feature.') else 0)
            groups[group].append(index)
    base_order=('action.dash','action.dodge','action.disengage','action.jump','action.hide','action.shove')
    groups[0].sort(key=lambda i:base_order.index(families[i].key.behavior_id)
                   if families[i].key.behavior_id in base_order else len(base_order))
    return tuple(ActionBlock(label, tuple(indices)) for label, indices in
                 zip(('Actions','Spells','Class abilities','Items'),groups,strict=True))


def weapon_modes(actor: PlayerActor | None) -> tuple[tuple[str,str], ...]:
    return (('MELEE_MAIN','Melee'),) + ((('RANGED_MAIN','Ranged'),)
        if actor is not None and any(item.slot=='RANGED_MAIN' for item in actor.visual_loadout.layers) else ())


def block_counts(blocks: tuple[ActionBlock, ...], actor: PlayerActor | None) -> tuple[int, ...]:
    return tuple(len(block.families)+(len(weapon_modes(actor)) if index==0 else 0)
                 for index,block in enumerate(blocks))


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
                    actor: PlayerActor | None, *, pages: tuple[int, int, int, int], selected: int | None,
                    ready: bool, mouse: tuple[int, int],
                    shortcuts: tuple[ActionFamilyKey, ...],
                    attack_preference: str = 'MELEE_MAIN') -> tuple[UIHit, ...]:
    hits: list[UIHit] = []
    px = lambda value: round(value * geometry.scale)
    blocks = action_blocks(actions,families,shortcuts,actor)
    modes = weapon_modes(actor)
    slot = geometry.slot
    column_offset = 0
    labels = ('1','2','3','4','5','6','7','8','9','0','−','=')
    for group, (block, bounds, columns) in enumerate(zip(blocks,geometry.blocks,geometry.block_columns,strict=True)):
        if not columns:
            continue
        fixed = len(modes) if group==0 else 0
        capacity = max(1,columns*2-fixed)
        page = shortcut_page(pages[group],len(block.families),capacity)
        start = page*capacity
        shown = block.families[start:start+capacity]
        header = pygame.Rect(bounds.left,bounds.top,bounds.width,px(25))
        paging = len(block.families)>capacity
        header_reference=(UIReference('common','unarmed'),UIReference('common','abilities'),
                          UIReference('common','reactions'),UIReference('common','inventory'))[group]
        if group==0 and actor is not None:
            main=next((item for item in actor.visual_loadout.layers if item.slot=='MELEE_MAIN'),None)
            if main is not None:
                header_reference=item_reference(media,main.item_id)
        size=min(28,px(24))
        header_icon=ui_image(media,header_reference,(size,size),images)
        header_hit=pygame.Rect(header.left,header.top,size,size)
        if header_icon is not None:
            screen.blit(header_icon,header_hit)
        hits.append(UIHit(header_hit,'bar_label',label=block.label,bar_group=group))
        if paging:
            for sign, label in ((-1,'‹'),(1,'›')):
                rect=pygame.Rect(header.right-px(32)+(0 if sign<0 else px(17)),header.top,px(16),px(21))
                enabled=page>0 if sign<0 else start+capacity<len(block.families)
                text(screen,font.small,label,rect.topleft,GOLD if enabled else MUTED)
                hits.append(UIHit(rect,'page',sign,bar_group=group,enabled=enabled,
                    label=f'{block.label}: page {page+1} of {(len(block.families)+capacity-1)//capacity}'))
        for offset in range(fixed+len(shown)):
            row_index,col=divmod(offset,columns)
            rect=pygame.Rect(bounds.left+col*slot,bounds.top+px(25)+row_index*(slot+px(4)),slot,slot)
            shortcut=row_index*12+column_offset+col
            if offset<fixed:
                weapon_slot,label=modes[offset]
                item=next((item for item in actor.visual_loadout.layers if item.slot==weapon_slot),None) if actor else None
                reference=item_reference(media,item.item_id) if item else UIReference('common','unarmed')
                hit=UIHit(rect,'attack_mode',offset,label=label+' attack [X to switch]',bar_group=group,shortcut=shortcut)
                active=weapon_slot==attack_preference
            else:
                family_index=shown[offset-fixed]
                family=families[family_index]
                assert actions is not None
                row=actions.all_actions[family.indices[0]]
                reference=action_reference(media,row.behavior_id,row.configured_action_ref,provided_by_id=row.provided_by_id)
                if row.source_item_uuid is not None and actor is not None:
                    item=next((item for item in actor.controlled_items or () if item.item_uuid==row.source_item_uuid),None)
                    if item is not None:
                        reference=item_reference(media,item.item_id)
                elif row.is_attack and actor is not None and row.weapon_slot:
                    item=next((item for item in actor.visual_loadout.layers if item.slot==row.weapon_slot),None)
                    if item is not None:
                        reference=item_reference(media,item.item_id)
                hit=UIHit(rect,'family',family_index,label=row.display_name,
                    discovery_generation=actions.discovery_generation,family_key=family.key,bar_group=group,shortcut=shortcut,
                    enabled=ready and any(actions.all_actions[i].valid_targets for i in family.indices))
                active=selected in family.indices
            image=ui_image(media,reference,rect.size,images)
            icon_control(screen,rect,image,selected=active,hover=rect.collidepoint(mouse),scale=geometry.scale)
            key=('⇧' if row_index else '')+labels[column_offset+col]
            # Only the small key legend receives a backing; icon colors stay intact.
            label_image=font.small.render(key,True,(231,229,221))
            label_rect=label_image.get_rect(topright=(rect.right-px(3),rect.top+px(2)))
            pygame.draw.rect(screen,(17,22,28),label_rect.inflate(px(3),0))
            screen.blit(label_image,label_rect)
            if offset>=fixed and actions is not None and family_has_choices(actions,families[shown[offset-fixed]]):
                x,y=rect.right-px(5),rect.bottom-px(5)
                pygame.draw.polygon(screen,GOLD,((x-px(4),y),(x,y),(x,y-px(4))))
            hits.append(hit)
        column_offset+=columns
    left=geometry.bar.right-slot
    # Utilities are separate from the four gameplay categories.
    controls: tuple[tuple[str, UIVerb, str], ...]=(
        ('abilities','panel','Abilities [K]'),
        ('end_turn' if ready else 'waiting','end','End turn [Space]' if ready else 'Resolving turn'))
    for index,(identity,verb,label) in enumerate(controls):
        rect=pygame.Rect(left,geometry.bar.top+px(25)+index*(slot+px(4)),slot,slot)
        image=ui_image(media,UIReference('common',identity),rect.size,images)
        icon_control(screen,rect,image,hover=rect.collidepoint(mouse),scale=geometry.scale)
        hits.append(UIHit(rect,verb,2 if verb=='panel' else 0,label=label,enabled=verb=='panel' or ready))
    return tuple(hits)
