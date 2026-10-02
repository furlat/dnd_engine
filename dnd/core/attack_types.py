"""Attack-local source data shared by authoring and resolution."""
from pydantic import BaseModel, ConfigDict
from dnd.core.events import Range
from dnd.core.creature_types import DamageType
from typing import Literal
from uuid import UUID
from dnd.core.equipment_types import WeaponSlot
from dnd.types.abilities import AbilityName


DamageDieValue = Literal[4, 6, 8, 10, 12, 20]


class WeaponAttackOverride(BaseModel):
    """An exact temporary item effect, scoped to its wielder."""
    wielder_uuid: UUID
    damage_die: DamageDieValue = 8
    optional_ability: AbilityName
    magical: bool = True




class NaturalWeaponSpec(BaseModel):
    name: str
    dice_numbers: int
    damage_dice: DamageDieValue
    damage_type: DamageType
    range: Range
    missile_size: Literal["ordinary", "large"] = "ordinary"
    magical: bool = False
    fixed_attack_bonus: int | None = None
    fixed_damage_bonus: int | None = None


class AttackSourceMetadata(BaseModel):
    kind: Literal["equipped", "unarmed", "natural"]
    weapon_slot: WeaponSlot
    name: str
    damage_types: tuple[DamageType, ...]
    item_uuid: UUID | None = None
    magical: bool = False


class AttackAmmunitionPayload(BaseModel):
    """Immutable single-release payload; no inventory or equipment slot owner."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    item_id: str
    damage_type: DamageType
    damage_die: DamageDieValue
    dice_count: int = 1
    save_dc: int | None = None


class AttackAmmunitionMetadata(BaseModel):
    """Selected inventory possession and packet exposed to action discovery."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    item_uuid: UUID
    payload: AttackAmmunitionPayload
