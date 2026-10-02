"""Attack-local source data shared by authoring and resolution."""
from pydantic import BaseModel
from dnd.core.events import Range
from dnd.core.creature_types import DamageType
from typing import Literal
from uuid import UUID
from dnd.core.equipment_types import WeaponSlot

DamageDieValue = Literal[4, 6, 8, 10, 12, 20]


class NaturalWeaponSpec(BaseModel):
    name: str
    dice_numbers: int
    damage_dice: DamageDieValue
    damage_type: DamageType
    range: Range
    missile_size: Literal["ordinary", "large"] = "ordinary"


class AttackSourceMetadata(BaseModel):
    kind: Literal["equipped", "unarmed", "natural"]
    weapon_slot: WeaponSlot
    name: str
    damage_types: tuple[DamageType, ...]
    item_uuid: UUID | None = None
