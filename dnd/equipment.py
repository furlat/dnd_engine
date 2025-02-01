from pydantic import BaseModel
from typing import Optional
from enum import Enum
from uuid import UUID
from dnd.values import ModifiableValue, StaticValue
from dnd.modifiers import DamageType
from pydantic import Field
from typing import List

class ArmorType(str, Enum):
    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"

class WeaponProperty(str, Enum):
    FINESSE = "Finesse"
    VERSATILE = "Versatile"
    RANGED = "Ranged"
    THROWN = "Thrown"
    TWO_HANDED = "Two-Handed"
    LIGHT = "Light"
    HEAVY = "Heavy"
    MARTIAL = "Martial"
    SIMPLE = "Simple"

class BodyPart(str, Enum):
    HEAD = "Head"
    BODY = "Body"
    HANDS = "Hands"
    LEGS = "Legs"
    FEET = "Feet"
    AMULET = "Amulet"
    RING = "Ring"
    CLOAK = "Cloak"

class RangeType(str, Enum):
    REACH = "Reach"
    RANGE = "Range"

class Range(BaseModel):
    type: RangeType = Field(
        description="The type of range (Reach or Range)"
    )
    normal: int = Field(
        description="Normal range in feet"
    )
    long: Optional[int] = Field(
        default=None,
        description="Long range in feet, only applicable for ranged weapons"
    )

    def __str__(self):
        if self.type == RangeType.REACH:
            return f"{self.normal} ft."
        elif self.type == RangeType.RANGE:
            return f"{self.normal}/{self.long} ft." if self.long else f"{self.normal} ft."
        
class Armor(BaseModel):
    uuid: UUID = Field(
        description="Unique identifier for the armor"
    )
    name: str = Field(
        description="Name of the armor piece"
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description of the armor"
    )
    type: ArmorType = Field(
        description="Type of armor (Light, Medium, or Heavy)"
    )
    body_part: BodyPart = Field(
        description="Body part where the armor is worn"
    )
    base_ac: Optional[int] = Field(
        default=None,
        description="Base Armor Class provided by the armor"
    )
    bonus_ac: Optional[ModifiableValue] = Field(
        default=None,
        description="Bonus Armor Class provided by the armor"
    )
    max_dex_bonus: Optional[int] = Field(
        default=None,
        description="Maximum Dexterity bonus that can be added to AC"
    )
    strength_requirement: Optional[int] = Field(
        default=None,
        description="Minimum Strength score required to wear the armor"
    )
    dexterity_requirement: Optional[int] = Field(
        default=None,
        description="Minimum Dexterity score required to wear the armor"
    )
    intelligence_requirement: Optional[int] = Field(
        default=None,
        description="Minimum Intelligence score required to wear the armor"
    )
    constitution_requirement: Optional[int] = Field(
        default=None,
        description="Minimum Constitution score required to wear the armor"
    )
    charisma_requirement: Optional[int] = Field(
        default=None,
        description="Minimum Charisma score required to wear the armor"
    )
    wisdom_requirement: Optional[int] = Field(
        default=None,
        description="Minimum Wisdom score required to wear the armor"
    )
    stealth_disadvantage: Optional[bool] = Field(
        default=None,
        description="Whether the armor imposes disadvantage on Stealth checks"
    )

class Helmet(Armor):
    body_part: BodyPart = Field(
        default=BodyPart.HEAD,
        
        description="Head slot armor"
    )

class BodyArmor(Armor):
    body_part: BodyPart = Field(
        default=BodyPart.BODY,
        
        description="Body slot armor"
    )

class Gauntlets(Armor):
    body_part: BodyPart = Field(
        default=BodyPart.HANDS,
        
        description="Hand slot armor"
    )

class Greaves(Armor):
    body_part: BodyPart = Field(
        default=BodyPart.LEGS,
        
        description="Leg slot armor"
    )

class Boots(Armor):
    body_part: BodyPart = Field(
        default=BodyPart.FEET,
        
        description="Feet slot armor"
    )

class Amulet(Armor):
    body_part: BodyPart = Field(
        default=BodyPart.AMULET,
        
        description="Amulet slot armor"
    )

class Ring(Armor):
    body_part: BodyPart = Field(
        default=BodyPart.RING,
        
        description="Ring slot armor"
    )

class Cloak(Armor):
    body_part: BodyPart = Field(
        default=BodyPart.CLOAK,
        
        description="Cloak slot armor"
    )

class Shield(BaseModel):
    uuid: UUID = Field(
        description="Unique identifier for the shield"
    )
    name: str = Field(
        description="Name of the shield"
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description of the shield"
    )
    ac_bonus: ModifiableValue = Field(
        description="Armor Class bonus provided by the shield"
    )

class Weapon(BaseModel):
    uuid: UUID = Field(
        description="Unique identifier for the weapon"
    )
    name: str = Field(
        description="Name of the weapon"
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description of the weapon"
    )
    damage_dice: int = Field(
        description="Number of sides on the damage dice (e.g., 6 for d6)"
    )
    dice_numbers: int = Field(
        description="Number of dice to roll for damage (e.g., 2 for 2d6)"
    )
    damage_bonus: Optional[ModifiableValue] = Field(
        default=None,
        description="Fixed bonus to damage rolls"
    )
    attack_bonus: Optional[ModifiableValue] = Field(
        default=None,
        description="Fixed bonus to attack rolls"
    )
    damage_type: DamageType = Field(
        description="Type of damage dealt by the weapon"
    )
    properties: List[WeaponProperty] = Field(
        default_factory=list,
        description="Special properties of the weapon (e.g., Finesse, Versatile)"
    )
    range: Range = Field(
        description="Weapon's reach or range capabilities"
    )