"""Passive actor values shared by recorded reduction and presentation."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Literal, TypedDict, TypeVar
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

    Item operations. The owner's: `held_item` upserts the item, takes it out of every equipment slot and
    equips it on its slot; `used_item` writes charges and stack only, to the copy the owner holds;
    `released_by_owner` leaves the owner's inventory and equipment. Other holders': `released_by_others`
    leaves every holder but the owner; `replaced_item` replaces the copy of every actor holding it.
    """

    owner_uuid: UUID | None
    values: ActorFieldValues = field(default_factory=lambda: ActorFieldValues())
    conditions_set: tuple[ConditionFact, ...] = ()
    conditions_removed: tuple[UUID, ...] = ()
    held_item: HeldItem | None = None
    used_item: ItemResources | None = None
    released_by_owner: UUID | None = None
    released_by_others: UUID | None = None
    replaced_item: ItemPresentationState | None = None


class ChangeField(StrEnum):
    """One changed field of an actor, or of an item it holds: the tag of a change row and the key of its disclosure.

    The engine-only fields (healing blocked, damage affinities) have no row. The fields an event's own
    presentation fact carries (faction, life state, remains, occupancy) are not change fields.
    """

    NORMAL_HP = "normal_hp"
    MAXIMUM_HP = "maximum_hp"
    TEMPORARY_HP = "temporary_hp"
    TEMPORARY_HP_GRANT = "temporary_hp_grant"
    ARMOR_CLASS = "armor_class"
    RESOLVED_SIZE = "resolved_size"
    SPATIAL_DISPOSITION = "spatial_disposition"
    WEAPON_SET = "active_weapon_set"
    CONDITION = "condition"
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
