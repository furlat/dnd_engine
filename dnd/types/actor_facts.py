"""Passive actor values shared by recorded reduction and presentation."""

from dataclasses import dataclass, field
from typing import TypedDict
from uuid import UUID

from dnd.types.appearance import AppearanceConfig
from dnd.core.condition_types import ConditionCategory
from dnd.core.creature_types import Size
from dnd.core.equipment_types import WeaponSet
from dnd.core.item_types import ItemPresentationState
from dnd.core.life_types import LifeState, RemainsDisposition
from dnd.types.event_facts import WorldTileState
from dnd.types.actor import ConditionState, EntityStatsState, TemporaryHitPointsGrant, SpatialDisposition
from dnd.types.world import OccupancyLayer
from dnd.types.summoning import SummonOrigin


@dataclass(frozen=True, slots=True)
class ConditionFact:
    """A condition's presentation facts, without its live rules/ownership graph."""

    event_uuid: UUID | None
    condition_uuid: UUID
    name: str
    category: ConditionCategory
    behavior_id: str | None
    resulting_max_hp: int | None
    resulting_ac: int | None
    state: ConditionState | None = None
    resulting_stats: EntityStatsState | None = None
    resulting_tile: WorldTileState | None = None
    resulting_item: ItemPresentationState | None = None
    consumed: bool = False


@dataclass(frozen=True, slots=True)
class ActorState:
    """Retained actor facts; appearance remains independent of the drawer."""

    uuid: UUID
    name: str
    character_body_id: str | None
    creature_content_ref: str | None
    appearance: AppearanceConfig
    items: tuple[ItemPresentationState, ...]
    equipment: tuple[tuple[str, UUID], ...]
    active_weapon_set: WeaponSet
    normal_hp: int
    maximum_hp: int
    temporary_hp: int
    life_state: LifeState
    remains_disposition: RemainsDisposition = RemainsDisposition.INTACT
    armor_class: int = 10
    conditions: tuple[ConditionFact, ...] = ()
    last_visual_position: tuple[int, int] | None = None
    faction: str | None = None
    creature_type: str | None = None
    healing_blocked: bool = False
    damage_affinities: tuple[tuple[str, str], ...] = ()
    occupancy_layer: OccupancyLayer | None = None
    temporary_hp_grant: TemporaryHitPointsGrant | None = None
    resolved_size: Size | None = None
    structural_base_size: Size | None = None
    summon_origin: SummonOrigin | None = None
    spatial_disposition: SpatialDisposition = SpatialDisposition.PRESENT


class ActorFieldValues(TypedDict, total=False):
    """The actor values one fact writes, as after-values: present fields replace, omitted fields are unchanged."""

    normal_hp: int
    temporary_hp: int
    temporary_hp_grant: TemporaryHitPointsGrant | None
    maximum_hp: int
    armor_class: int
    life_state: LifeState
    remains_disposition: RemainsDisposition
    resolved_size: Size
    spatial_disposition: SpatialDisposition
    faction: str | None
    occupancy_layer: OccupancyLayer
    active_weapon_set: WeaponSet
    healing_blocked: bool
    damage_affinities: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class HeldItem:
    """An item entering or moving within its holder's holdings: its after-value, and its slot when equipped."""

    item: ItemPresentationState
    slot: str | None


@dataclass(frozen=True, slots=True)
class ItemResources:
    """A used item's charges and stack after the use; a holder writes them only to the copy it holds."""

    item_uuid: UUID
    charges: int | None
    stack_count: int
    destroyed: bool


@dataclass(frozen=True, slots=True)
class ActorFactChange:
    """One committed event's actor change (plan §4): what it writes to its owner, and how the item it moves
    or changes leaves or changes in the actors holding it. Data only; `apply_actor_fact_change` folds it.

    Item operations. The owner's: `held_item` upserts the item, takes its layers off and puts it on its slot;
    `used_item` writes charges and stack only, to the copy the owner holds; `dropped_item` leaves the
    owner's inventory and layers. Other holders': `released_item` leaves every holder but the owner;
    `replaced_item` replaces the copy of every actor holding it.
    """

    owner_uuid: UUID | None
    values: ActorFieldValues = field(default_factory=lambda: ActorFieldValues())
    conditions_set: tuple[ConditionFact, ...] = ()
    conditions_removed: tuple[UUID, ...] = ()
    held_item: HeldItem | None = None
    used_item: ItemResources | None = None
    dropped_item: UUID | None = None
    released_item: UUID | None = None
    replaced_item: ItemPresentationState | None = None
