"""Item placement, finite-resource, and equipment-transition event facts."""

from typing import Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.events.events_registry import Event, EventType
from dnd.presentation import ItemPresentationState
from dnd.types.equipment import EquipmentSlot
from dnd.types.items import ItemLocation

class ItemLocationStateEvent(Event):
    """Post-commit, idempotent item placement and presentation fact."""

    name: str = Field(default="Item Location State", description="Item location-state fact label.")
    event_type: EventType = Field(
        default=EventType.ITEM_LOCATION_STATE,
        description="Event category for authoritative item location snapshots.",
    )
    item_state: ItemPresentationState = Field(
        description="Cold item presentation/state required to materialize this item."
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
    tile_uuid: Optional[UUID] = Field(default=None, description="Floor tile UUID after the mutation.")
    position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Floor position after the mutation.",
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
