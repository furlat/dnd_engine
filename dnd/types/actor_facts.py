"""Passive actor values shared by recorded reduction and presentation."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, TypeVar
from uuid import UUID

from pydantic import Field

from dnd.types.appearance import AppearanceConfig
from dnd.core.condition_types import ConditionCategory, ConditionDurationSummary
from dnd.core.creature_types import Size
from dnd.core.equipment_types import WeaponSet
from dnd.core.item_types import ItemEffectPresentationState, ItemPresentationState
from dnd.core.life_types import LifeState, RemainsDisposition
from dnd.types.event_facts import WorldTileState
from dnd.types.actor import ConditionState, EntityStatsState, TemporaryHitPointsGrant, SpatialDisposition
from dnd.types.world import OccupancyLayer
from dnd.types.summoning import SummonOrigin
from dnd.types.item_parts import ItemStateChanges, VisualItem


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


class ChangeField(StrEnum):
    """One changed field of an actor, or of an item it holds: the tag of a change row and the key of its disclosure."""

    NORMAL_HP = "normal_hp"
    MAXIMUM_HP = "maximum_hp"
    TEMPORARY_HP = "temporary_hp"
    TEMPORARY_HP_GRANT = "temporary_hp_grant"
    ARMOR_CLASS = "armor_class"
    RESOLVED_SIZE = "resolved_size"
    SPATIAL_DISPOSITION = "spatial_disposition"
    WEAPON_SET = "active_weapon_set"
    LIFE_STATE = "life_state"
    REMAINS = "remains_disposition"
    FACTION = "faction"
    OCCUPANCY = "occupancy_layer"
    HEALING_BLOCKED = "healing_blocked"
    DAMAGE_AFFINITIES = "damage_affinities"
    CONDITION = "condition"
    INTERNAL_CONDITION = "internal_condition"
    CONDITION_DURATION = "condition_duration"
    LAYER = "layer"
    INVENTORY = "inventory"
    ITEM_EFFECTS = "item_effects"
    ITEM_EFFECT_DURATION = "item_effect_duration"
    ITEM_STATE = "item_state"


@dataclass(frozen=True, slots=True, kw_only=True)
class ConditionMember:
    """A condition an actor holds: its identity and committed state, without any event's change payload."""

    condition_uuid: UUID
    name: str
    category: ConditionCategory
    behavior_id: str | None
    state: ConditionState | None = None


# A change's rows, one class per value shape. Each row names its field; a keyed
# row its key, and a removal carries no value.

@dataclass(frozen=True, slots=True, kw_only=True)
class NumberRow:
    field: Literal[ChangeField.NORMAL_HP, ChangeField.MAXIMUM_HP, ChangeField.TEMPORARY_HP, ChangeField.ARMOR_CLASS]
    value: int


@dataclass(frozen=True, slots=True, kw_only=True)
class GrantRow:
    field: Literal[ChangeField.TEMPORARY_HP_GRANT] = ChangeField.TEMPORARY_HP_GRANT
    value: TemporaryHitPointsGrant | None


@dataclass(frozen=True, slots=True, kw_only=True)
class SizeRow:
    field: Literal[ChangeField.RESOLVED_SIZE] = ChangeField.RESOLVED_SIZE
    value: Size | None


@dataclass(frozen=True, slots=True, kw_only=True)
class DispositionRow:
    field: Literal[ChangeField.SPATIAL_DISPOSITION] = ChangeField.SPATIAL_DISPOSITION
    value: SpatialDisposition


@dataclass(frozen=True, slots=True, kw_only=True)
class WeaponSetRow:
    field: Literal[ChangeField.WEAPON_SET] = ChangeField.WEAPON_SET
    value: WeaponSet


def _unset(value: object) -> bool:
    return value is None


def _unflagged(flag: bool) -> bool:
    return not flag


@dataclass(frozen=True, slots=True, kw_only=True)
class ConditionRow:
    """A membership set (applied or changed) or, without a member, ended; `consumed` tells how it ended."""

    field: Literal[ChangeField.CONDITION] = ChangeField.CONDITION
    condition_uuid: UUID
    member: Annotated[ConditionMember | None, Field(exclude_if=_unset)] = None
    consumed: Annotated[bool, Field(exclude_if=_unflagged)] = False


@dataclass(frozen=True, slots=True, kw_only=True)
class DurationRow:
    """The new duration of a held condition (`key` its uuid) or of an item's effect (`key` the effect, of `item_uuid`)."""

    field: Literal[ChangeField.CONDITION_DURATION, ChangeField.ITEM_EFFECT_DURATION]
    key: UUID
    item_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    duration: ConditionDurationSummary | None


@dataclass(frozen=True, slots=True, kw_only=True)
class LayerRow:
    """The equipped layer of `slot`, or without a layer the slot emptied."""

    field: Literal[ChangeField.LAYER] = ChangeField.LAYER
    slot: str
    layer: Annotated[VisualItem | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class InventoryRow:
    """An item entering (`held`) or leaving the actor's inventory."""

    field: Literal[ChangeField.INVENTORY] = ChangeField.INVENTORY
    item_uuid: UUID
    held: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemEffectsRow:
    """An item's effects, whole: the item's own snapshot order."""

    field: Literal[ChangeField.ITEM_EFFECTS] = ChangeField.ITEM_EFFECTS
    item_uuid: UUID
    effects: tuple[ItemEffectPresentationState, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemStateRow:
    field: Literal[ChangeField.ITEM_STATE] = ChangeField.ITEM_STATE
    item_uuid: UUID
    changes: ItemStateChanges


ChangeRow = Annotated[NumberRow | GrantRow | SizeRow | DispositionRow | WeaponSetRow | ConditionRow | DurationRow
    | LayerRow | InventoryRow | ItemEffectsRow | ItemStateRow, Field(discriminator="field")]


Row = TypeVar("Row")
Key = TypeVar("Key")


def upserted(rows: tuple[Row, ...], key: Callable[[Row], Key], value: Row) -> tuple[Row, ...]:
    """`rows` with `value` in place of the row of its key, else appended: a dict's assignment order."""
    identity = key(value)
    for index, row in enumerate(rows):
        if key(row) == identity:
            return (*rows[:index], value, *rows[index + 1:])
    return (*rows, value)


def dropped(rows: tuple[Row, ...], key: Callable[[Row], Key], identity: Key) -> tuple[Row, ...]:
    """`rows` without the row of `identity`; the same rows when none has it."""
    return tuple(row for row in rows if key(row) != identity)
