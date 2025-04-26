from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier

from enum import Enum
from random import randint
from functools import cached_property
from typing import Literal as TypeLiteral


from dnd.blocks.base_block import BaseBlock


class RingSlot(str, Enum):
    LEFT = "Left Ring"
    RIGHT = "Right Ring"

class WeaponSlot(str, Enum):
    MAIN_HAND = "Main Hand"
    OFF_HAND = "Off Hand"

class UnarmoredAc(str, Enum):
    BARBARIAN = "Barbarian"
    MONK = "Monk"
    DRACONIC_SORCER = "Draconic Sorcerer"
    MAGIC_ARMOR = "Magic Armor"
    NONE = "None"

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
        
class Armor(BaseBlock):
    name: str = Field(default="Armor")
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

class Shield(BaseBlock):
    name: str = Field(default="Shield",   description="Name of the shield"
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description of the shield"
    )
    ac_bonus: ModifiableValue = Field(
        description="Armor Class bonus provided by the shield"
    )

class Weapon(BaseBlock):
    name: str = Field(default="Weapon", description="Name of the weapon")
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
    attack_bonus: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,
            value_name="Attack Bonus"
        )
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
    extra_damage_bonus: List[ModifiableValue] = Field(
        default_factory=list,
        description="Extra damage bonus for the weapon"
    )
    extra_damage_type: List[DamageType] = Field(
        default_factory=list,
        description="Extra damage type for the weapon")
    
    #validator to ensure both extra damage bonus and extra damage type are of the same length
    @model_validator(mode="after")
    def check_extra_damage_consistency(self) -> Self:
        if len(self.extra_damage_bonus) != len(self.extra_damage_type):
            raise ValueError("Extra damage bonus and extra damage type must be of the same length")
        return self
    
slot_mapping = {
        BodyPart.HEAD: "helmet",
        BodyPart.BODY: "body_armor",
        BodyPart.HANDS: "gauntlets",
        BodyPart.LEGS: "greaves",


        BodyPart.FEET: "boots",
        BodyPart.AMULET: "amulet",
        BodyPart.CLOAK: "cloak",
    }

class EquipmentConfig(BaseModel):
    """ ignores the actual equipment and only focuses on the modifiers """
    unarmored_ac: UnarmoredAc = Field(default=UnarmoredAc.NONE, description="Unarmored Armor Class")
    ac: int = Field(default=10, description="Armor Class")
    ac_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the armor class")
    damage_bonus: int = Field(default=0, description="Damage Bonus")
    damage_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the damage bonus")
    attack_bonus: int = Field(default=0, description="Attack Bonus")
    attack_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the attack bonus")
    melee_attack_bonus: int = Field(default=0, description="Melee Attack Bonus")
    melee_attack_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the melee attack bonus")
    ranged_attack_bonus: int = Field(default=0, description="Ranged Attack Bonus")
    ranged_attack_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the ranged attack bonus")
    melee_damage_bonus: int = Field(default=0, description="Melee Damage Bonus")
    melee_damage_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the melee damage bonus")
    ranged_damage_bonus: int = Field(default=0, description="Ranged Damage Bonus")
    ranged_damage_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the ranged damage bonus")
    unarmed_attack_bonus: int = Field(default=0, description="Unarmed Attack Bonus")
    unarmed_attack_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the unarmed attack bonus")
    unarmed_damage_bonus: int = Field(default=0, description="Unarmed Damage Bonus")
    unarmed_damage_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the unarmed damage bonus")
    unarmed_damage_type: DamageType = Field(default=DamageType.BLUDGEONING, description="Unarmed Damage Type")
    unarmed_damage_dice: int = Field(default=4, description="Unarmed Damage Dice")
    unarmed_dice_numbers: int = Field(default=1, description="Unarmed Dice Numbers")
    

class Equipment(BaseBlock):
    """
    Represents all equipped items on an entity in the game system.
    """
    name: str = Field(default="Equipped", description="Equipment slots for an entity")
    helmet: Optional[Helmet] = Field(default=None, description="Head slot armor")
    body_armor: Optional[BodyArmor] = Field(default=None, description="Body slot armor")
    gauntlets: Optional[Gauntlets] = Field(default=None, description="Hand slot armor")
    greaves: Optional[Greaves] = Field(default=None, description="Leg slot armor")
    boots: Optional[Boots] = Field(default=None, description="Feet slot armor")
    amulet: Optional[Amulet] = Field(default=None, description="Amulet slot item")
    ring_left: Optional[Ring] = Field(default=None, description="Left ring slot")
    ring_right: Optional[Ring] = Field(default=None, description="Right ring slot")
    cloak: Optional[Cloak] = Field(default=None, description="Cloak slot item")
    weapon_main_hand: Optional[Weapon] = Field(default=None, description="Main hand weapon slot")
    weapon_off_hand: Optional[Union[Weapon, Shield]] = Field(default=None, description="Off-hand weapon or shield slot")
    unarmored_ac: UnarmoredAc = Field(default=UnarmoredAc.NONE)
    
    ac: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=10,
        value_name="Armor Class"
    ))

    damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Damage Bonus"
    ))

    attack_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Attack Bonus"
    ))

    melee_attack_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Melee Attack Bonus"
    ))

    ranged_attack_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Ranged Attack Bonus"
    ))

    melee_damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Melee Damage Bonus"
    ))

    ranged_damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Ranged Damage Bonus"
    ))
    unarmed_attack_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Unarmed Attack Bonus"
    ))

    unarmed_damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Unarmed Damage Bonus"
    ))

    unarmed_damage_type: DamageType = Field(default=DamageType.BLUDGEONING)

    unarmed_damage_dice: int = Field(default=4)

    unarmed_dice_numbers: int = Field(default=1)

    

    def equip(self, item: Union[Armor, Weapon, Shield], slot: Optional[Union[BodyPart, RingSlot, WeaponSlot]] = None) -> None:
        """
        Equip an item in the specified slot. For most items, the slot can be automatically
        determined from the item type. For rings and weapons, the slot must be specified.

        Args:
            item: The item to equip
            slot: Optional slot specification, required for rings and weapons

        Raises:
            ValueError: If the slot is invalid or if a ring/weapon is equipped without specifying the slot
        """
        if isinstance(item, Ring):
            if slot not in (RingSlot.LEFT, RingSlot.RIGHT):
                raise ValueError("Must specify LEFT or RIGHT slot for rings")
            if slot == RingSlot.LEFT:
                self.ring_left = item
            else:
                self.ring_right = item
            return

        if isinstance(item, (Weapon, Shield)):
            if slot not in (WeaponSlot.MAIN_HAND, WeaponSlot.OFF_HAND):
                # Default to main hand if not specified
                slot = WeaponSlot.MAIN_HAND
            
            if slot == WeaponSlot.MAIN_HAND and isinstance(item, Weapon):
                self.weapon_main_hand = item
            else:
                self.weapon_off_hand = item
            return

        # For armor pieces, get the slot from the item's body_part if not specified
        if slot is None and isinstance(item, Armor):
            slot = item.body_part

        if slot not in slot_mapping:
            raise ValueError(f"Invalid equipment slot: {slot}")

        attribute_name = slot_mapping[slot]
        setattr(self, attribute_name, item)

    def unequip(self, slot: Union[BodyPart, RingSlot, WeaponSlot]) -> None:
        """
        Unequip the item in the specified slot.

        Args:
            slot: The slot to unequip from

        Raises:
            ValueError: If the slot is invalid
        """
        if isinstance(slot, RingSlot):
            attribute_name = "ring_left" if slot == RingSlot.LEFT else "ring_right"
        elif isinstance(slot, WeaponSlot):
            attribute_name = "weapon_main_hand" if slot == WeaponSlot.MAIN_HAND else "weapon_off_hand"
        elif isinstance(slot, BodyPart):
            if slot not in slot_mapping:
                raise ValueError(f"Invalid equipment slot: {slot}")
            attribute_name = slot_mapping[slot]
        else:
            raise ValueError(f"Invalid equipment slot: {slot}")

        setattr(self, attribute_name, None)
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "Equipped", source_entity_name: Optional[str] = None, 
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
                config: Optional[EquipmentConfig] = None) -> 'Equipment':
        if config is None:
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name)
        else:
            ac = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.ac, value_name="Armor Class")
            for modifier in config.ac_modifiers:
                ac.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            damage_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.damage_bonus, value_name="Damage Bonus")
            for modifier in config.damage_bonus_modifiers:
                damage_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            attack_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.attack_bonus, value_name="Attack Bonus")
            for modifier in config.attack_bonus_modifiers:
                attack_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            melee_attack_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.melee_attack_bonus, value_name="Melee Attack Bonus")
            for modifier in config.melee_attack_bonus_modifiers:
                melee_attack_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            ranged_attack_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.ranged_attack_bonus, value_name="Ranged Attack Bonus")
            for modifier in config.ranged_attack_bonus_modifiers:
                ranged_attack_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            melee_damage_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.melee_damage_bonus, value_name="Melee Damage Bonus")
            for modifier in config.melee_damage_bonus_modifiers:
                melee_damage_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            ranged_damage_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.ranged_damage_bonus, value_name="Ranged Damage Bonus")
            for modifier in config.ranged_damage_bonus_modifiers:
                ranged_damage_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            unarmed_attack_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.unarmed_attack_bonus, value_name="Unarmed Attack Bonus")
            for modifier in config.unarmed_attack_bonus_modifiers:
                unarmed_attack_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            unarmed_damage_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.unarmed_damage_bonus, value_name="Unarmed Damage Bonus")
            for modifier in config.unarmed_damage_bonus_modifiers:
                unarmed_damage_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, 
                       target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, 
                       ac=ac, damage_bonus=damage_bonus, attack_bonus=attack_bonus, melee_attack_bonus=melee_attack_bonus, ranged_attack_bonus=ranged_attack_bonus, 
                       melee_damage_bonus=melee_damage_bonus, ranged_damage_bonus=ranged_damage_bonus, unarmed_attack_bonus=unarmed_attack_bonus, unarmed_damage_bonus=unarmed_damage_bonus)
            
                
                
            
