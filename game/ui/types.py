"""Passive player UI intents and focus, independent of engine executors."""

from dataclasses import dataclass
from typing import Literal, TypeAlias
from uuid import UUID

import pygame

from dnd.core.base_actions import AvailableWorldInteraction
from dnd.core.content.identities import ContentRef
from dnd.core.equipment_types import EquipmentSlot
from game.interaction_types import WorldHit
from dnd.player.commands import EquipItem as EquipItem, UnequipItem as UnequipItem, ToggleHandler as ToggleHandler


UIVerb: TypeAlias = Literal['surface','bar_label','equipment_slot','family','variant','world','confirm','cancel','end','panel','inspect','focus','close','page','menu','attack_mode','all_here','scale','fullscreen','retry','quit','log','log_row','log_expand','log_row_detail','log_text','log_scrollbar','log_detail','log_filter','log_actor','log_follow','log_copy','pin','variant_pick','equip','unequip','use_item','drop_item','handler','inventory_item','library_filter']


@dataclass(frozen=True, slots=True)
class ActionFamilyKey:
    behavior_id: str
    configured_ref: ContentRef | None
    source_item_uuid: UUID | None
    weapon_slot: str | None


@dataclass(frozen=True, slots=True)
class LogKey:
    generation: UUID
    observer_uuid: UUID
    kind: Literal['event','append']
    identity: str


@dataclass(frozen=True, slots=True)
class UIHit:
    rect: pygame.Rect
    verb: UIVerb
    index: int = 0
    identity: UUID | None = None
    label: str = ''
    enabled: bool = True
    discovery_generation: int | None = None
    log_key: LogKey | None = None
    family_key: ActionFamilyKey | None = None
    equipment_slot: EquipmentSlot | None = None
    world_hit: WorldHit | None = None
    bar_group: int | None = None
    shortcut: int | None = None


@dataclass(frozen=True, slots=True)
class UIFrame:
    hits: tuple[UIHit, ...] = ()
    blocked: tuple[pygame.Rect, ...] = ()
    detail_scroll_max: int | None = None
    detail_scroll_rect: pygame.Rect | None = None


@dataclass(frozen=True, slots=True)
class PendingInteraction:
    actor_uuid: UUID
    subject_uuid: UUID
    descriptor: AvailableWorldInteraction
    move_generation: int


@dataclass(frozen=True, slots=True)
class UIFocus:
    selected_actor: UUID | None = None
    panel: Literal['inventory','sheet','spellbook','reactions','menu'] | None = None
    family: int | None = None
    hover_family: bool = False
    variant_index: int | None = None
    selected_item: UUID | None = None
    equipment_slot: EquipmentSlot | None = None
    library_filter: Literal['all','spells','actions','items'] = 'all'
    search_text: str = ''
    context: tuple[AvailableWorldInteraction,...] = ()
    context_position: tuple[int,int] = (0,0)
    pending: PendingInteraction | None = None
    bar_pages: tuple[int, int, int, int] = (0, 0, 0, 0)
    popup_scroll: int = 0
    item_detail_scroll: int = 0
    ui_scale: float = 1.
    log_open: bool = False
    attack_preference: Literal['MELEE_MAIN','RANGED_MAIN'] = 'MELEE_MAIN'
    pinned_tooltip: tuple[str, ...] = ()
    tooltip_position: tuple[int, int] = (0, 0)
