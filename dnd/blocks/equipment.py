from typing import Dict, Optional, Any, List, Self, Literal,ClassVar, Union, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator, computed_field,field_validator
from dnd.core.values import ModifiableValue, StaticValue
from dnd.core.dice import Dice, DiceRoll, RollType, AttackOutcome
from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier
from dnd.blocks.abilities import  AbilityScores
from dnd.core.events import Damage, Range, WeaponSlot, AbilityName, SkillName
from enum import Enum
from random import randint
from functools import cached_property
from typing import Literal as TypeLiteral
import copy

from dnd.blocks.base_block import BaseBlock


class RingSlot(str, Enum):
    LEFT = "Left Ring"
    RIGHT = "Right Ring"



class UnarmoredAc(str, Enum):
    BARBARIAN = "Barbarian"
    MONK = "Monk"
    DRACONIC_SORCERER = "Draconic Sorcerer"
    MAGIC_ARMOR = "Magic Armor"
    NONE = "None"

class ArmorType(str, Enum):
    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"
    CLOTH = "Cloth"

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

    ac: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=0,
            value_name="Armor Class"
        ),
        description="Armor Class provided by the armor, the base value is the base armor ac and the modifiers are the modifiers to the ac"
    )
    max_dex_bonus: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=uuid4(),
            base_value=5,
            value_name="Max Dex Bonus"
        ),
        description="Max Dex Bonus provided by the armor, the base value is the base max dex bonus and the modifiers are the modifiers to the max dex bonus"
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
    damage_dice: Literal[4,6,8,10,12,20] = Field(
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
    extra_damage_dices: List[Literal[4,6,8,10,12,20]] = Field(
        default_factory=list,
        description="Extra damage dice for the weapon"
    )
    extra_damage_dices_numbers: List[int] = Field(
        default_factory=list,
        description="Extra damage dice numbers for the weapon"
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
        targets = [self.extra_damage_dices, self.extra_damage_dices_numbers, self.extra_damage_bonus, self.extra_damage_type]
        for target in targets:
            for i in range(len(target)):
                if len(target[i]) != len(targets[0]):
                    raise ValueError("All extra damage targets must be of the same length")
        return self
    
    def get_main_damage(self, equipment_block: 'Equipment', ability_block: AbilityScores) -> Damage:
        bonuses = []
        if self.damage_bonus is not None:
            bonuses.append(self.damage_bonus)
        if equipment_block.damage_bonus is not None:
            bonuses.append(equipment_block.damage_bonus)
        if WeaponProperty.RANGED in self.properties:
            #get dex bonuses
            dex_bonus = ability_block.dexterity.get_combined_values()
            bonuses.append(dex_bonus)
            #get ranged bonuses
            ranged_bonus = equipment_block.ranged_damage_bonus
            bonuses.append(ranged_bonus)
        elif WeaponProperty.FINESSE in self.properties:
            dex_bonus = ability_block.dexterity.get_combined_values()
            strength_bonus = ability_block.strength.get_combined_values()
            if dex_bonus.normalized_score > strength_bonus.normalized_score:
                bonuses.append(dex_bonus)
            else:
                bonuses.append(strength_bonus)
            melee_bonus = equipment_block.melee_damage_bonus
            bonuses.append(melee_bonus)
        else:
            strength_bonus = ability_block.strength.get_combined_values()
            bonuses.append(strength_bonus)
            melee_bonus = equipment_block.melee_damage_bonus
            bonuses.append(melee_bonus)

        bonuses.append(equipment_block.damage_bonus)
        combined_bonuses= bonuses[0].combine_values(bonuses[1:])
        return Damage(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, damage_dice=self.damage_dice, dice_numbers=self.dice_numbers, damage_bonus=combined_bonuses, damage_type=self.damage_type)
    def get_extra_damages(self) -> List[Damage]:
        damages = []
        for i in range(len(self.extra_damage_dices)):
            damages.append(Damage(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, damage_dice=self.extra_damage_dices[i], dice_numbers=self.extra_damage_dices_numbers[i], damage_bonus=self.extra_damage_bonus[i], damage_type=self.extra_damage_type[i]))
        return damages
    def get_all_weapon_damages(self, equipment_block: 'Equipment', ability_block: AbilityScores) -> List[Damage]:
        damages = [self.get_main_damage(equipment_block, ability_block)]
        damages.extend(self.get_extra_damages())
        return damages
    
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
    unarmored_ac_type: UnarmoredAc = Field(default=UnarmoredAc.NONE, description="Unarmored Armor Class")
    unarmored_ac: int = Field(default=10, description="Unarmored Armor Class")
    unarmored_ac_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the unarmored  armor class")
    ac_bonus: int = Field(default=0, description="Armor Class Bonus")
    ac_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list, description="Any additional static modifiers applied to the armor class bonus")
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
    unarmored_ac_type: UnarmoredAc = Field(default=UnarmoredAc.NONE)
    unarmed_properties: List[WeaponProperty] = Field(
        default_factory=list,
        description="Special properties of the unarmed attack like finesse for monks"
    )
    
    unarmored_ac: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=10,
        value_name="Unarmored Armor Class"
    ))

    ac_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Armor Class Bonus"
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

    extra_attack_damage_dices: List[Literal[4,6,8,10,12,20]] = Field(
        default_factory=list,
        description="Extra damage dice for the weapon"
    )
    extra_attack_damage_dices_numbers: List[int] = Field(
        default_factory=list,
        description="Extra damage dice numbers for the weapon"
    )
    extra_attack_damage_bonus: List[ModifiableValue] = Field(
        default_factory=list,
        description="Extra damage bonus for the weapon"
    )
    extra_attack_damage_type: List[DamageType] = Field(
        default_factory=list,
        description="Extra damage type for the weapon")

    unarmed_damage_type: DamageType = Field(default=DamageType.BLUDGEONING)

    unarmed_damage_dice: Literal[4,6,8,10,12,20] = Field(default=4)

    unarmed_dice_numbers: int = Field(default=1)

    def is_unarmed(self, weapon_slot: WeaponSlot = WeaponSlot.MAIN_HAND) -> bool:
        if weapon_slot == WeaponSlot.MAIN_HAND:
            return self.weapon_main_hand is None
        elif weapon_slot == WeaponSlot.OFF_HAND:
            return self.weapon_off_hand is None
    
    def is_ranged(self, weapon_slot: WeaponSlot) -> bool:
        if weapon_slot == WeaponSlot.MAIN_HAND and isinstance(self.weapon_main_hand, Weapon):
            return WeaponProperty.RANGED  in self.weapon_main_hand.properties
        elif weapon_slot == WeaponSlot.OFF_HAND and isinstance(self.weapon_off_hand, Weapon):
            return WeaponProperty.RANGED in self.weapon_off_hand.properties
        else:
            return False
        
    def _get_main_unarmed_damage(self, ability_block: AbilityScores) -> Damage:
        """ combines the unarmed damage bonus with the damage bonus and melee damage bonus into a single damage block"""
        unarmed_damage_bonus = self.unarmed_damage_bonus
        strength_bonus = ability_block.strength.get_combined_values()
        ability_bonus = strength_bonus
        if WeaponProperty.FINESSE in self.unarmed_properties:
            dexterity_bonus = ability_block.dexterity.get_combined_values()
            if dexterity_bonus.normalized_score > strength_bonus.normalized_score:
                ability_bonus = dexterity_bonus
        combined_bonus = unarmed_damage_bonus.combine_values([self.damage_bonus,self.melee_damage_bonus, ability_bonus])
        unarmed_damage = Damage(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, damage_dice=self.unarmed_damage_dice, dice_numbers=self.unarmed_dice_numbers, damage_bonus=combined_bonus, damage_type=self.unarmed_damage_type)
        return unarmed_damage
    
    def _get_main_weapon_damage(self, weapon_slot: WeaponSlot, ability_block: AbilityScores) -> Optional[Damage]:
        """ combines the weapon damage bonus with the damage bonus and melee damage bonus into a single damage block"""
        if weapon_slot == WeaponSlot.MAIN_HAND and isinstance(self.weapon_main_hand, Weapon):
            damage= self.weapon_main_hand.get_main_damage(self, ability_block)
        elif weapon_slot == WeaponSlot.OFF_HAND and isinstance(self.weapon_off_hand, Weapon):
            damage = self.weapon_off_hand.get_main_damage(self, ability_block)
        else:
            return None

        return damage
 
    def get_extra_attack_damage(self) -> List[Damage]:
        damages = []
        for dice, dice_numbers, bonus, damage_type in zip(self.extra_attack_damage_dices, self.extra_attack_damage_dices_numbers, self.extra_attack_damage_bonus, self.extra_attack_damage_type):
            damages.append(Damage(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, damage_dice=dice, dice_numbers=dice_numbers, damage_bonus=bonus, damage_type=damage_type))
        return damages

    def get_damages(self, weapon_slot: WeaponSlot, ability_block: AbilityScores) -> List[Damage]:
        if self.is_unarmed(weapon_slot):
            return [self._get_main_unarmed_damage(ability_block)]+self.get_extra_attack_damage()
        else:
            outs = []
            main_damage = self._get_main_weapon_damage(weapon_slot, ability_block)
            if main_damage is not None:
                outs.append(main_damage)
            outs.extend(self.get_extra_attack_damage())
            return outs
        
    def get_main_damage_type(self, weapon_slot: WeaponSlot) -> DamageType:
        if weapon_slot == WeaponSlot.MAIN_HAND and isinstance(self.weapon_main_hand, Weapon):
            return self.weapon_main_hand.damage_type
        elif weapon_slot == WeaponSlot.OFF_HAND and isinstance(self.weapon_off_hand, Weapon):
            return self.weapon_off_hand.damage_type
        else:
            return self.unarmed_damage_type

    def get_unarmored_abilities(self) -> List[AbilityName]:
        if self.unarmored_ac_type == UnarmoredAc.BARBARIAN:
            return ["dexterity", "constitution"]
        elif self.unarmored_ac_type == UnarmoredAc.MONK:
            return ["dexterity", "strength"]
        else:
            return["dexterity"]
    def is_unarmored(self) -> bool:
        return self.body_armor is None or self.body_armor.type == ArmorType.CLOTH
    
    def get_unarmored_ac_values(self) -> List[ModifiableValue]:
        values = [self.ac_bonus]
        if self.unarmored_ac_type in [UnarmoredAc.DRACONIC_SORCERER, UnarmoredAc.MAGIC_ARMOR]:
            unarmored_ac_static_modifier = NumericalModifier.create(source_entity_uuid=self.source_entity_uuid, name="unarmored_ac_bonus", value=3)
            temporary_value = copy.deepcopy(self.unarmored_ac)
            temporary_value.self_static.add_value_modifier(unarmored_ac_static_modifier)
            values.append(temporary_value)
        else:
            values.append(self.unarmored_ac)
        if self.weapon_off_hand and isinstance(self.weapon_off_hand, Shield):
            values.append(self.weapon_off_hand.ac_bonus)
        return values

    def get_armored_ac_values(self) -> List[ModifiableValue]:
        values = [self.ac_bonus]
        if self.body_armor is not None and self.body_armor.type != ArmorType.CLOTH:
            values.append(self.body_armor.ac)
        if self.weapon_off_hand and isinstance(self.weapon_off_hand, Shield):
            values.append(self.weapon_off_hand.ac_bonus)
        return values
    
    def get_armored_max_dex_bonus(self) -> Optional[ModifiableValue]:
        if self.body_armor is not None and self.body_armor.type != ArmorType.CLOTH:
            return self.body_armor.max_dex_bonus
        return None
     
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
            unarmored_ac = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.unarmored_ac, value_name="Unarmored Armor Class")
            for modifier in config.unarmored_ac_modifiers:
                unarmored_ac.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
            ac_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid, base_value=config.ac_bonus, value_name="Armor Class Bonus")
            for modifier in config.ac_bonus_modifiers:
                ac_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid, name=modifier[0], value=modifier[1]))
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
                       unarmored_ac=unarmored_ac, ac_bonus=ac_bonus,unarmored_ac_type=config.unarmored_ac_type, damage_bonus=damage_bonus, attack_bonus=attack_bonus, melee_attack_bonus=melee_attack_bonus, ranged_attack_bonus=ranged_attack_bonus, 
                       melee_damage_bonus=melee_damage_bonus, ranged_damage_bonus=ranged_damage_bonus, unarmed_attack_bonus=unarmed_attack_bonus, unarmed_damage_bonus=unarmed_damage_bonus)
            
                
                
            
