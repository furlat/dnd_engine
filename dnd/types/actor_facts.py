"""Passive actor values shared by recorded reduction and presentation."""

from dataclasses import dataclass
from uuid import UUID

from dnd.blocks.appearance import AppearanceConfig
from dnd.core.condition_types import ConditionCategory
from dnd.core.creature_types import Size
from dnd.core.equipment_types import WeaponSet
from dnd.core.item_types import ItemPresentationState
from dnd.core.life_types import LifeState
from dnd.core.events import WorldTileState
from dnd.types.actor import ConditionState, EntityStatsState, TemporaryHitPointsGrant
from dnd.types.world import OccupancyLayer


@dataclass(frozen=True, slots=True)
class ConditionFact:
    """A condition's presentation facts, without its live rules/ownership graph."""

    event_uuid: UUID
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
