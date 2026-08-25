"""Item state, placement, finite-resource, and equipment-transition facts."""

from typing import Optional, Protocol, Tuple, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.core.events.events_registry import Event, EventType
from dnd.types.damage import DamageType
from dnd.types.equipment import ArmorType, EquipmentSlot, WeaponProperty
from dnd.types.items import (
    ItemChargeState,
    ItemKind,
    ItemLightSourceState,
    ItemLocation,
    ItemRarity,
)
from dnd.types.world_placement import BoundaryStructure
from dnd.types.rolls import DieSize
from dnd.types.world_placement import WorldObjectPlacement


class ItemState(BaseModel):
    """Renderer-independent state of one concrete item instance.

    This is the item data carried by authoritative events. It deliberately
    excludes content contracts and client asset/rendering vocabulary.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_uuid: UUID
    semantic_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: Optional[str] = None
    item_kind: ItemKind = ItemKind.ITEM
    rarity: ItemRarity = ItemRarity.COMMON
    weight: float = 0.0
    value: int = 0
    tags: Tuple[str, ...] = ()
    is_pickable: bool = True
    is_equippable: bool = False
    is_usable: bool = False
    is_consumable: bool = False
    is_targetable: bool = False
    stack_id: Optional[str] = None
    stack_count: int = Field(default=1, ge=0)
    max_stack: int = Field(default=1, ge=1)
    current_hit_points: Optional[int] = Field(default=None, ge=0)
    maximum_hit_points: Optional[int] = Field(default=None, ge=0)
    charge_state: Optional[ItemChargeState] = None
    boundary_structure: Optional[BoundaryStructure] = None
    light_source: Optional[ItemLightSourceState] = None
    is_open: Optional[bool] = None
    blocks_movement: bool = False
    blocks_optics: bool = False
    blocks_propagation: bool = False
    damage_die: Optional[DieSize] = None
    damage_dice_count: Optional[int] = Field(default=None, ge=1)
    damage_bonus: Optional[int] = None
    attack_bonus: Optional[int] = None
    damage_type: Optional[DamageType] = None
    weapon_properties: Tuple[WeaponProperty, ...] = ()
    range_kind: Optional[str] = None
    normal_range_feet: Optional[int] = Field(default=None, ge=0)
    long_range_feet: Optional[int] = Field(default=None, ge=0)
    armor_type: Optional[ArmorType] = None
    armor_class: Optional[int] = Field(default=None, ge=0)
    shield_armor_class_bonus: Optional[int] = None


@runtime_checkable
class ItemStateProvider(Protocol):
    """Structural boundary for capturing an authoritative item fact."""

    def to_item_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemState:
        """Return the item's renderer-independent state."""
        ...

class ItemLocationStateEvent(Event):
    """Post-commit, idempotent item state and placement fact."""

    name: str = Field(default="Item Location State", description="Item location-state fact label.")
    event_type: EventType = Field(
        default=EventType.ITEM_LOCATION_STATE,
        description="Event category for authoritative item location snapshots.",
    )
    item_state: ItemState = Field(
        description="Complete renderer-independent item state after the mutation."
    )
    location: ItemLocation = Field(description="Authoritative item placement after the mutation.")
    owner_uuid: Optional[UUID] = Field(
        default=None,
        description="Owning entity or container item UUID after the mutation.",
    )
    container_uuid: Optional[UUID] = Field(
        default=None,
        description="Inventory or equipment block UUID after the mutation.",
    )
    world_placement: Optional[WorldObjectPlacement] = Field(
        default=None,
        description="Exact committed floor placement after the mutation.",
    )
    equipment_slot: Optional[EquipmentSlot] = Field(
        default=None,
        description="Occupied equipment slot when location is equipment.",
    )
    merged_into_item_uuid: Optional[UUID] = Field(
        default=None,
        description="Surviving stack UUID when this item was fully merged.",
    )
    entity_armor_class_after: Optional[int] = Field(
        default=None,
        ge=0,
        description="Exact aggregate owner AC after an entity-owned mutation.",
    )

    @model_validator(mode="after")
    def validate_location_placement(self) -> "ItemLocationStateEvent":
        """Keep floor and non-floor facts mutually exclusive and exact."""
        if self.location is ItemLocation.FLOOR:
            if self.world_placement is None:
                raise ValueError("floor item facts require world_placement")
            if self.world_placement.object_uuid != self.item_state.item_uuid:
                raise ValueError(
                    "world_placement.object_uuid must match item_state.item_uuid",
                )
        elif self.world_placement is not None:
            raise ValueError("non-floor item facts cannot define world_placement")
        return self

class ItemChargeConsumptionEvent(Event):
    """Finite usable-item resource consumption owned by the item domain."""

    name: str = Field(
        default="Item Charge Consumption",
        description="Human-readable item-resource event label.",
    )
    event_type: EventType = Field(
        default=EventType.ITEM_CHARGE_CONSUMPTION,
        description="Event category for finite item-resource consumption.",
    )
    item_uuid: UUID = Field(description="Usable item whose finite resource changes.")
    item_semantic_key: str = Field(
        default="item.unclassified",
        description="Stable semantic identity of the consumed item.",
    )
    item_name: str = Field(default="Item", description="Human-readable consumed item name.")
    amount: int = Field(default=1, ge=1, description="Number of charges consumed.")
    charges_before: int = Field(ge=0, description="Active-item charges before consumption.")
    charges_after: int = Field(ge=0, description="Active-item charges after consumption.")
    stack_count_before: int = Field(ge=1, description="Represented item copies before consumption.")
    stack_count_after: int = Field(ge=1, description="Represented item copies after consumption.")
    item_destroyed: bool = Field(
        default=False,
        description="Whether consumption removed the final item from engine registries.",
    )

class EquipmentEvent(Event):
    """Base event for equipment slot transitions."""

    name: str = Field(default="Equipment Event", description="An equipment event")
    slot: EquipmentSlot = Field(description="The slot being affected")
    item_uuid: UUID = Field(description="UUID of the item being transitioned")

class WeaponEquipEvent(EquipmentEvent):
    """Event emitted when a weapon is equipped."""

    name: str = Field(default="Weapon Equip", description="A weapon equip event")
    event_type: EventType = Field(default=EventType.WEAPON_EQUIP, description="The type of event")

class WeaponUnequipEvent(EquipmentEvent):
    """Event emitted when a weapon is unequipped."""

    name: str = Field(default="Weapon Unequip", description="A weapon unequip event")
    event_type: EventType = Field(default=EventType.WEAPON_UNEQUIP, description="The type of event")

class ArmorEquipEvent(EquipmentEvent):
    """Event emitted when armor is equipped."""

    name: str = Field(default="Armor Equip", description="An armor equip event")
    event_type: EventType = Field(default=EventType.ARMOR_EQUIP, description="The type of event")

class ArmorUnequipEvent(EquipmentEvent):
    """Event emitted when armor is unequipped."""

    name: str = Field(default="Armor Unequip", description="An armor unequip event")
    event_type: EventType = Field(default=EventType.ARMOR_UNEQUIP, description="The type of event")

class ShieldEquipEvent(EquipmentEvent):
    """Event emitted when a shield is equipped."""

    name: str = Field(default="Shield Equip", description="A shield equip event")
    event_type: EventType = Field(default=EventType.SHIELD_EQUIP, description="The type of event")

class ShieldUnequipEvent(EquipmentEvent):
    """Event emitted when a shield is unequipped."""

    name: str = Field(default="Shield Unequip", description="A shield unequip event")
    event_type: EventType = Field(default=EventType.SHIELD_UNEQUIP, description="The type of event")


__all__ = [
    "ArmorEquipEvent",
    "ArmorUnequipEvent",
    "EquipmentEvent",
    "ItemChargeConsumptionEvent",
    "ItemLocationStateEvent",
    "ItemState",
    "ItemStateProvider",
    "ShieldEquipEvent",
    "ShieldUnequipEvent",
    "WeaponEquipEvent",
    "WeaponUnequipEvent",
]
