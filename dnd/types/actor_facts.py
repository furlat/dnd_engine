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

    The owner's item operations: `items_set` upserts (an item entering or moving within the owner's
    holdings), `item_resources` writes charges and stack only, `items_removed` takes items out of the
    inventory and every layer, `layers_removed` takes the named items' layers off, `layers_set` puts each
    item on its slot. `released_item` leaves every holder but the owner; `replaced_item` replaces the copy
    of every actor holding it.
    """

    owner_uuid: UUID | None
    values: ActorFieldValues = field(default_factory=lambda: ActorFieldValues())
    conditions_set: tuple[ConditionFact, ...] = ()
    conditions_removed: tuple[UUID, ...] = ()
    items_set: tuple[ItemPresentationState, ...] = ()
    item_resources: ItemResources | None = None
    items_removed: tuple[UUID, ...] = ()
    layers_removed: tuple[UUID, ...] = ()
    layers_set: tuple[tuple[str, UUID], ...] = ()
    released_item: UUID | None = None
    replaced_item: ItemPresentationState | None = None
