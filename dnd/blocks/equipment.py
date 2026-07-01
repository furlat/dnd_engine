"""Equipment, armor, weapon, and shield models for entity combat gear."""

from typing import Optional, List, Self, Literal, Union, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator
from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier, DamageType
from dnd.blocks.abilities import AbilityScores
from dnd.core.events import Event, EventType, EventPhase, Range, WeaponSlot, AbilityName, Damage, BodyPart, RingSlot

from enum import Enum

import copy

from dnd.core.base_block import BaseBlock
from dnd.blocks.base_item import EquippableItem


class EquipmentEvent(Event):
    """Base event for equipment slot transitions."""

    name: str = Field(default="Equipment Event", description="An equipment event")
    slot: Union['BodyPart', 'RingSlot', 'WeaponSlot'] = Field(description="The slot being affected")


class WeaponEquipEvent(EquipmentEvent):
    """Event emitted when a weapon is equipped."""

    name: str = Field(default="Weapon Equip", description="A weapon equip event")
    event_type: EventType = Field(default=EventType.WEAPON_EQUIP, description="The type of event")
    item_uuid: UUID = Field(description="UUID of the weapon being equipped")


class WeaponUnequipEvent(EquipmentEvent):
    """Event emitted when a weapon is unequipped."""

    name: str = Field(default="Weapon Unequip", description="A weapon unequip event")
    event_type: EventType = Field(default=EventType.WEAPON_UNEQUIP, description="The type of event")
    item_uuid: UUID = Field(description="UUID of the weapon being unequipped")


class ArmorEquipEvent(EquipmentEvent):
    """Event emitted when armor is equipped."""

    name: str = Field(default="Armor Equip", description="An armor equip event")
    event_type: EventType = Field(default=EventType.ARMOR_EQUIP, description="The type of event")
    item_uuid: UUID = Field(description="UUID of the armor being equipped")


class ArmorUnequipEvent(EquipmentEvent):
    """Event emitted when armor is unequipped."""

    name: str = Field(default="Armor Unequip", description="An armor unequip event")
    event_type: EventType = Field(default=EventType.ARMOR_UNEQUIP, description="The type of event")
    item_uuid: UUID = Field(description="UUID of the armor being unequipped")


class ShieldEquipEvent(EquipmentEvent):
    """Event emitted when a shield is equipped."""

    name: str = Field(default="Shield Equip", description="A shield equip event")
    event_type: EventType = Field(default=EventType.SHIELD_EQUIP, description="The type of event")
    item_uuid: UUID = Field(description="UUID of the shield being equipped")


class ShieldUnequipEvent(EquipmentEvent):
    """Event emitted when a shield is unequipped."""

    name: str = Field(default="Shield Unequip", description="A shield unequip event")
    event_type: EventType = Field(default=EventType.SHIELD_UNEQUIP, description="The type of event")
    item_uuid: UUID = Field(description="UUID of the shield being unequipped")


class UnarmoredAc(str, Enum):
    """Supported unarmored Armor Class formulas."""

    BARBARIAN = "Barbarian"
    MONK = "Monk"
    DRACONIC_SORCERER = "Draconic Sorcerer"
    MAGIC_ARMOR = "Magic Armor"
    NONE = "None"


class ArmorType(str, Enum):
    """Armor weight categories used by AC and movement rules."""

    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"
    CLOTH = "Cloth"


class WeaponProperty(str, Enum):
    """Weapon properties used by attack, damage, and equipment validation."""

    FINESSE = "Finesse"
    VERSATILE = "Versatile"
    RANGED = "Ranged"
    THROWN = "Thrown"
    TWO_HANDED = "Two-Handed"
    LIGHT = "Light"
    HEAVY = "Heavy"
    MARTIAL = "Martial"
    SIMPLE = "Simple"


class Armor(EquippableItem):
    """Equippable armor item with AC and slot metadata."""

    name: str = Field(default="Armor", description="Name of the armor.")
    map_char: str = Field(default="\u03b4", description="Character to display on the map grid")
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
    """Armor item for the head slot."""

    body_part: BodyPart = Field(
        default=BodyPart.HEAD,
        description="Head slot armor"
    )


class BodyArmor(Armor):
    """Armor item for the body slot."""

    body_part: BodyPart = Field(
        default=BodyPart.BODY,
        description="Body slot armor"
    )


class Gauntlets(Armor):
    """Armor item for the hands slot."""

    body_part: BodyPart = Field(
        default=BodyPart.HANDS,
        description="Hand slot armor"
    )


class Greaves(Armor):
    """Armor item for the legs slot."""

    body_part: BodyPart = Field(
        default=BodyPart.LEGS,
        description="Leg slot armor"
    )


class Boots(Armor):
    """Armor item for the feet slot."""

    body_part: BodyPart = Field(
        default=BodyPart.FEET,
        description="Feet slot armor"
    )


class Amulet(Armor):
    """Equippable item for the amulet slot."""

    body_part: BodyPart = Field(
        default=BodyPart.AMULET,
        description="Amulet slot armor"
    )


class Ring(Armor):
    """Equippable item for a ring slot."""

    body_part: BodyPart = Field(
        default=BodyPart.RING,
        description="Ring slot armor"
    )


class Cloak(Armor):
    """Equippable item for the cloak slot."""

    body_part: BodyPart = Field(
        default=BodyPart.CLOAK,
        description="Cloak slot armor"
    )


class Shield(EquippableItem):
    """Equippable shield that occupies the melee off-hand slot."""

    name: str = Field(default="Shield", description="Name of the shield")
    map_char: str = Field(default="\u03a3", description="Character to display on the map grid")
    description: Optional[str] = Field(
        default=None,
        description="Detailed description of the shield"
    )
    ac_bonus: ModifiableValue = Field(
        description="Armor Class bonus provided by the shield"
    )


class Weapon(EquippableItem):
    """Equippable weapon with attack, damage, range, and property metadata."""

    name: str = Field(default="Weapon", description="Name of the weapon")
    map_char: str = Field(default="\u2020", description="Character to display on the map grid")
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
        ),
        description="Weapon-specific attack roll bonus.",
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
        description="Extra damage type for the weapon",
    )

    @model_validator(mode="after")
    def check_extra_damage_consistency(self) -> Self:
        """Validate that every extra-damage payload list has matching length."""
        targets = [
            self.extra_damage_dices,
            self.extra_damage_dices_numbers,
            self.extra_damage_bonus,
            self.extra_damage_type,
        ]
        first_len = len(targets[0])
        for target in targets[1:]:
            if len(target) != first_len:
                raise ValueError("All extra damage targets must be of the same length")
        return self

    def get_base_damage(self, equipment_block: 'Equipment', ability_block: AbilityScores,
                        is_off_hand: bool = False,
                        off_hand_ability_bonus: Optional[ModifiableValue] = None,
                        override_ability: Optional[AbilityName] = None) -> Damage:
        """Get base damage for this weapon.

        Args:
            equipment_block: Equipment block providing global and typed bonuses.
            ability_block: Ability scores used to derive STR or DEX damage.
            is_off_hand: Whether to use the off-hand ability bonus path.
            off_hand_ability_bonus: Optional ability bonus value for off-hand attacks.
            override_ability: Optional ability to use instead of weapon-derived STR/DEX.

        Returns:
            Damage model for the weapon's primary damage payload.
        """
        bonuses = []
        if self.damage_bonus is not None:
            bonuses.append(self.damage_bonus)
        if equipment_block.damage_bonus is not None:
            bonuses.append(equipment_block.damage_bonus)

        if override_ability is not None:
            ability = ability_block.get_ability(override_ability)
            bonuses.append(ability.get_combined_values())
        elif not is_off_hand:
            if WeaponProperty.RANGED in self.properties:
                dex_bonus = ability_block.dexterity.get_combined_values()
                bonuses.append(dex_bonus)
            elif WeaponProperty.FINESSE in self.properties:
                dex_bonus = ability_block.dexterity.get_combined_values()
                strength_bonus = ability_block.strength.get_combined_values()
                if dex_bonus.normalized_score > strength_bonus.normalized_score:
                    bonuses.append(dex_bonus)
                else:
                    bonuses.append(strength_bonus)
            else:
                strength_bonus = ability_block.strength.get_combined_values()
                bonuses.append(strength_bonus)
        else:
            if off_hand_ability_bonus is not None:
                bonuses.append(off_hand_ability_bonus)

        if WeaponProperty.RANGED in self.properties:
            ranged_bonus = equipment_block.ranged_damage_bonus
            bonuses.append(ranged_bonus)
        else:
            melee_bonus = equipment_block.melee_damage_bonus
            bonuses.append(melee_bonus)

        combined_bonuses = bonuses[0].combine_values(bonuses[1:])
        return Damage(source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.target_entity_uuid, damage_dice=self.damage_dice, dice_numbers=self.dice_numbers, damage_bonus=combined_bonuses, damage_type=self.damage_type)

    def get_extra_damages(self) -> List[Damage]:
        """Return extra damage payloads attached directly to this weapon."""
        damages = []
        for i in range(len(self.extra_damage_dices)):
            damages.append(Damage(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, damage_dice=self.extra_damage_dices[i], dice_numbers=self.extra_damage_dices_numbers[i], damage_bonus=self.extra_damage_bonus[i], damage_type=self.extra_damage_type[i]))
        return damages

    def get_all_weapon_damages(self, equipment_block: 'Equipment', ability_block: AbilityScores) -> List[Damage]:
        """Return primary plus extra weapon damage payloads."""
        damages = [self.get_base_damage(equipment_block, ability_block)]
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
    """Configuration payload for equipment-wide combat modifiers."""

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
    """Container for equipped items and equipment-derived combat values."""

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
    weapon_melee_main: Optional[Weapon] = Field(default=None, description="Main melee weapon slot")
    weapon_melee_off: Optional[Union[Weapon, Shield]] = Field(default=None, description="Off-hand melee weapon or shield slot")
    weapon_ranged_main: Optional[Weapon] = Field(default=None, description="Main ranged weapon slot")
    weapon_ranged_off: Optional[Weapon] = Field(default=None, description="Off-hand ranged weapon slot")
    unarmored_ac_type: UnarmoredAc = Field(
        default=UnarmoredAc.NONE,
        description="Unarmored AC formula active for this equipment block.",
    )
    unarmed_properties: List[WeaponProperty] = Field(
        default_factory=list,
        description="Special properties of the unarmed attack like finesse for monks"
    )

    unarmored_ac: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=10,
        value_name="Unarmored Armor Class"
    ), description="Base Armor Class value used while unarmored.")

    ac_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Armor Class Bonus"
    ), description="General Armor Class bonus applied to armored and unarmored AC.")

    damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Damage Bonus"
    ), description="General damage bonus for attacks made with this equipment.")

    attack_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Attack Bonus"
    ), description="General attack roll bonus for attacks made with this equipment.")

    melee_attack_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Melee Attack Bonus"
    ), description="Attack roll bonus for melee attacks.")

    ranged_attack_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Ranged Attack Bonus"
    ), description="Attack roll bonus for ranged attacks.")

    melee_damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Melee Damage Bonus"
    ), description="Damage bonus for melee attacks.")

    ranged_damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Ranged Damage Bonus"
    ), description="Damage bonus for ranged attacks.")
    unarmed_attack_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Unarmed Attack Bonus"
    ), description="Attack roll bonus for unarmed attacks.")

    unarmed_damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Unarmed Damage Bonus"
    ), description="Damage bonus for unarmed attacks.")

    off_hand_melee_ability_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Off-Hand Melee Ability Bonus"
    ), description="Ability modifier contribution for off-hand melee damage.")
    off_hand_ranged_ability_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Off-Hand Ranged Ability Bonus"
    ), description="Ability modifier contribution for off-hand ranged damage.")

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
        description="Extra damage type for the weapon",
    )

    unarmed_damage_type: DamageType = Field(
        default=DamageType.BLUDGEONING,
        description="Damage type used by unarmed attacks.",
    )

    unarmed_damage_dice: Literal[4,6,8,10,12,20] = Field(
        default=4,
        description="Die size used by unarmed damage.",
    )

    unarmed_dice_numbers: int = Field(
        default=1,
        description="Number of dice rolled for unarmed damage.",
    )

    crit_threshold: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Crit Threshold"
    ), description="General critical-threshold bonus for all attacks.")
    crit_threshold_melee: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Melee Crit Threshold"
    ), description="Critical-threshold bonus for melee attacks.")
    crit_threshold_ranged: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Ranged Crit Threshold"
    ), description="Critical-threshold bonus for ranged attacks.")

    crit_extra_dice: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Critical Extra Dice"
    ), description="General extra dice added on critical hits.")
    crit_extra_dice_melee: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Melee Critical Extra Dice"
    ), description="Extra dice added on melee critical hits.")
    crit_extra_dice_ranged: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(
        source_entity_uuid=uuid4(),
        base_value=0,
        value_name="Ranged Critical Extra Dice"
    ), description="Extra dice added on ranged critical hits.")

    def get_all_equipped_items(self) -> List[Union[Weapon, Shield, Armor]]:
        """Return all equipped items across all slots."""
        items: List[Union[Weapon, Shield, Armor]] = []
        for slot_item in [self.weapon_melee_main, self.weapon_melee_off,
                          self.weapon_ranged_main, self.weapon_ranged_off]:
            if slot_item is not None:
                items.append(slot_item)
        for attr in ['helmet', 'body_armor', 'gauntlets', 'greaves', 'boots',
                     'amulet', 'ring_left', 'ring_right', 'cloak']:
            item = getattr(self, attr, None)
            if item is not None:
                items.append(item)
        return items

    def _get_weapon_by_slot(self, slot: WeaponSlot) -> Optional[Union[Weapon, Shield]]:
        """Helper to get weapon/shield by slot."""
        return {
            WeaponSlot.MELEE_MAIN: self.weapon_melee_main,
            WeaponSlot.MELEE_OFF: self.weapon_melee_off,
            WeaponSlot.RANGED_MAIN: self.weapon_ranged_main,
            WeaponSlot.RANGED_OFF: self.weapon_ranged_off,
        }.get(slot)

    def get_item_by_slot(self, slot: Union[BodyPart, RingSlot, WeaponSlot]) -> Optional[Union['Armor', 'Weapon', 'Shield']]:
        """Get the item in any equipment slot."""
        if isinstance(slot, WeaponSlot):
            return self._get_weapon_by_slot(slot)
        elif isinstance(slot, RingSlot):
            return self.ring_left if slot == RingSlot.LEFT else self.ring_right
        elif isinstance(slot, BodyPart):
            if slot not in slot_mapping:
                return None
            return getattr(self, slot_mapping[slot], None)
        return None

    def remove_contained_item(self, item_uuid: UUID) -> None:
        """Remove an equipped item by UUID during item-owned cleanup.

        Destruction cleanup must not be cancelable, but item unequip hooks still
        need to run so equipped modifiers and handlers are removed.

        Args:
            item_uuid: UUID of the equipped item to remove.
        """
        slots: List[Tuple[Union[BodyPart, RingSlot, WeaponSlot], str]] = [
            (WeaponSlot.MELEE_MAIN, "weapon_melee_main"),
            (WeaponSlot.MELEE_OFF, "weapon_melee_off"),
            (WeaponSlot.RANGED_MAIN, "weapon_ranged_main"),
            (WeaponSlot.RANGED_OFF, "weapon_ranged_off"),
            (BodyPart.HEAD, "helmet"),
            (BodyPart.BODY, "body_armor"),
            (BodyPart.HANDS, "gauntlets"),
            (BodyPart.LEGS, "greaves"),
            (BodyPart.FEET, "boots"),
            (BodyPart.AMULET, "amulet"),
            (BodyPart.CLOAK, "cloak"),
            (RingSlot.LEFT, "ring_left"),
            (RingSlot.RIGHT, "ring_right"),
        ]
        for slot, attribute_name in slots:
            item = getattr(self, attribute_name)
            if item is not None and item.uuid == item_uuid:
                item.unequip(slot, self.source_entity_uuid)
                setattr(self, attribute_name, None)
                return

    def is_unarmed(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> bool:
        """Return whether the slot attacks as unarmed."""
        weapon = self._get_weapon_by_slot(weapon_slot)
        return weapon is None or isinstance(weapon, Shield)

    def is_ranged(self, weapon_slot: WeaponSlot) -> bool:
        """Ranged slots are always ranged, melee slots are never ranged."""
        return weapon_slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF)

    def _get_main_unarmed_damage(self, ability_block: AbilityScores, override_ability: Optional[AbilityName] = None) -> Damage:
        """Combine unarmed, melee, equipment, and ability bonuses into one damage."""
        unarmed_damage_bonus = self.unarmed_damage_bonus
        if override_ability is not None:
            ability_bonus = ability_block.get_ability(override_ability).get_combined_values()
        else:
            strength_bonus = ability_block.strength.get_combined_values()
            ability_bonus = strength_bonus
            if WeaponProperty.FINESSE in self.unarmed_properties:
                dexterity_bonus = ability_block.dexterity.get_combined_values()
                if dexterity_bonus.normalized_score > strength_bonus.normalized_score:
                    ability_bonus = dexterity_bonus
        combined_bonus = unarmed_damage_bonus.combine_values([self.damage_bonus,self.melee_damage_bonus, ability_bonus])
        unarmed_damage = Damage(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, damage_dice=self.unarmed_damage_dice, dice_numbers=self.unarmed_dice_numbers, damage_bonus=combined_bonus, damage_type=self.unarmed_damage_type)
        return unarmed_damage

    def _get_weapon_base_damage(self, weapon_slot: WeaponSlot, ability_block: AbilityScores, override_ability: Optional[AbilityName] = None) -> Optional[Damage]:
        """Return the primary damage payload for a weapon slot, if it holds a weapon."""
        weapon = self._get_weapon_by_slot(weapon_slot)
        if isinstance(weapon, Weapon):
            is_off_hand = weapon_slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF)
            is_ranged = weapon_slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF)

            off_hand_ability_bonus = None
            if is_off_hand:
                off_hand_ability_bonus = self.off_hand_ranged_ability_bonus if is_ranged else self.off_hand_melee_ability_bonus

            return weapon.get_base_damage(self, ability_block, is_off_hand=is_off_hand,
                                          off_hand_ability_bonus=off_hand_ability_bonus,
                                          override_ability=override_ability)
        return None

    def _get_extra_weapon_damages(self, weapon_slot: WeaponSlot) -> List[Damage]:
        """Return extra damage payloads attached to the weapon in the slot."""
        weapon = self._get_weapon_by_slot(weapon_slot)
        if isinstance(weapon, Weapon):
            return weapon.get_extra_damages()
        return []

    def get_extra_attack_damage(self, weapon_slot: Optional[WeaponSlot] = None) -> List[Damage]:
        """Return equipment-level extra damage, plus weapon extras for a slot."""
        damages: List[Damage] = []
        for dice, dice_numbers, bonus, damage_type in zip(self.extra_attack_damage_dices, self.extra_attack_damage_dices_numbers, self.extra_attack_damage_bonus, self.extra_attack_damage_type):
            damages.append(Damage(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, damage_dice=dice, dice_numbers=dice_numbers, damage_bonus=bonus, damage_type=damage_type))
        if weapon_slot is not None:
            return damages+self._get_extra_weapon_damages(weapon_slot)
        else:
            return damages

    def get_damages(self, weapon_slot: WeaponSlot, ability_block: AbilityScores, override_ability: Optional[AbilityName] = None) -> List[Damage]:
        """Return all damage payloads for an attack from a weapon slot."""
        if self.is_unarmed(weapon_slot):
            return [self._get_main_unarmed_damage(ability_block, override_ability=override_ability)]+self.get_extra_attack_damage()
        else:
            outs = []
            base_damage = self._get_weapon_base_damage(weapon_slot, ability_block, override_ability=override_ability)
            if base_damage is not None:
                outs.append(base_damage)
            outs.extend(self.get_extra_attack_damage(weapon_slot))
            return outs

    def get_main_damage_type(self, weapon_slot: WeaponSlot) -> DamageType:
        """Return the primary damage type for a weapon slot."""
        weapon = self._get_weapon_by_slot(weapon_slot)
        if isinstance(weapon, Weapon):
            return weapon.damage_type
        return self.unarmed_damage_type

    def get_unarmored_abilities(self) -> List[AbilityName]:
        """Return ability modifiers included in the active unarmored AC formula."""
        if self.unarmored_ac_type == UnarmoredAc.BARBARIAN:
            return ["dexterity", "constitution"]
        elif self.unarmored_ac_type == UnarmoredAc.MONK:
            return ["dexterity", "strength"]
        else:
            return["dexterity"]

    def is_unarmored(self) -> bool:
        """Return whether body armor is absent or cloth-only."""
        return self.body_armor is None or self.body_armor.type == ArmorType.CLOTH

    def get_unarmored_ac_values(self) -> List[ModifiableValue]:
        """Return modifiable values that contribute to unarmored AC."""
        values = [self.ac_bonus]
        if self.unarmored_ac_type in [UnarmoredAc.DRACONIC_SORCERER, UnarmoredAc.MAGIC_ARMOR]:
            unarmored_ac_static_modifier = NumericalModifier.create(source_entity_uuid=self.source_entity_uuid, name="unarmored_ac_bonus", value=3)
            temporary_value = copy.deepcopy(self.unarmored_ac)
            temporary_value.self_static.add_value_modifier(unarmored_ac_static_modifier)
            values.append(temporary_value)
        else:
            values.append(self.unarmored_ac)
        if self.weapon_melee_off and isinstance(self.weapon_melee_off, Shield):
            values.append(self.weapon_melee_off.ac_bonus)
        return values

    def get_armored_ac_values(self) -> List[ModifiableValue]:
        """Return modifiable values that contribute to armored AC."""
        values = [self.ac_bonus]
        if self.body_armor is not None and self.body_armor.type != ArmorType.CLOTH:
            values.append(self.body_armor.ac)
        if self.weapon_melee_off and isinstance(self.weapon_melee_off, Shield):
            values.append(self.weapon_melee_off.ac_bonus)
        return values

    def get_armored_max_dex_bonus(self) -> Optional[ModifiableValue]:
        """Return the current armor's maximum Dexterity bonus value, if any."""
        if self.body_armor is not None and self.body_armor.type != ArmorType.CLOTH:
            return self.body_armor.max_dex_bonus
        return None

    @staticmethod
    def _is_two_handed_melee_weapon(item: Optional[Union[Weapon, Shield]]) -> bool:
        """Return whether an item occupies both melee hands."""
        return (
            isinstance(item, Weapon)
            and WeaponProperty.TWO_HANDED in item.properties
            and WeaponProperty.RANGED not in item.properties
        )

    def _get_melee_hand_conflict_slots(
        self,
        item: Union[Weapon, Shield],
        slot: WeaponSlot,
    ) -> List[WeaponSlot]:
        """Return melee slots displaced by this equip operation.

        Args:
            item: Weapon or shield being equipped.
            slot: Weapon slot targeted by the equip operation.

        Returns:
            Slots that must be unequipped before the new item can be assigned.
        """
        conflicts: List[WeaponSlot] = []
        if slot == WeaponSlot.MELEE_OFF and self._is_two_handed_melee_weapon(self.weapon_melee_main):
            conflicts.append(WeaponSlot.MELEE_MAIN)
        if (
            slot == WeaponSlot.MELEE_MAIN
            and self._is_two_handed_melee_weapon(item)
            and self.weapon_melee_off is not None
        ):
            conflicts.append(WeaponSlot.MELEE_OFF)
        return conflicts

    def equip(self, item: Union[Armor, Weapon, Shield], slot: Optional[Union[BodyPart, RingSlot, WeaponSlot]] = None) -> bool:
        """Equip an item in an equipment slot.

        Direct equipment calls validate and assign slots, fire equip events, and
        call item hooks. They do not move replaced items into inventory, and a
        canceled equip event returns `False` without assigning the slot.

        Args:
            item: The item to equip.
            slot: Optional slot specification, required for rings and weapons.

        Returns:
            True when the item is assigned to the slot, False when an equip
            event cancels before assignment.

        Raises:
            ValueError: If the slot is invalid or incompatible with the item.
        """
        item.source_entity_uuid = self.source_entity_uuid

        def _reparent_modifiable_value(mv: ModifiableValue) -> None:
            """Update a modifiable value and its channels to this equipment owner."""
            mv.source_entity_uuid = self.source_entity_uuid
            mv.self_static.source_entity_uuid = self.source_entity_uuid
            mv.to_target_static.source_entity_uuid = self.source_entity_uuid
            mv.self_contextual.source_entity_uuid = self.source_entity_uuid
            mv.to_target_contextual.source_entity_uuid = self.source_entity_uuid

        for _, field_value in item.__dict__.items():
            if isinstance(field_value, ModifiableValue):
                _reparent_modifiable_value(field_value)
            elif isinstance(field_value, list):
                for value in field_value:
                    if isinstance(value, ModifiableValue):
                        _reparent_modifiable_value(value)

        if isinstance(item, Ring):
            if slot not in (RingSlot.LEFT, RingSlot.RIGHT):
                raise ValueError("Must specify LEFT or RIGHT slot for rings")
            assert slot is not None

            event = ArmorEquipEvent(
                name=item.name,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                item_uuid=item.uuid,
                slot=slot
            )
            if event.phase_to(EventPhase.EXECUTION).canceled:
                return False

            if slot == RingSlot.LEFT and self.ring_left is not None:
                self.unequip(RingSlot.LEFT,)
            elif slot == RingSlot.RIGHT and self.ring_right is not None:
                self.unequip(RingSlot.RIGHT)

            if slot == RingSlot.LEFT:
                self.ring_left = item
            else:
                self.ring_right = item

            item.owner_uuid = self.source_entity_uuid
            item.stored_in_uuid = self.uuid
            item.equip(slot, self.source_entity_uuid)
            event.phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
            return True

        if isinstance(item, Shield):
            if slot is not None and slot != WeaponSlot.MELEE_OFF:
                raise ValueError("Shields can only be equipped in MELEE_OFF slot")
            slot = WeaponSlot.MELEE_OFF
            conflict_slots = self._get_melee_hand_conflict_slots(item, slot)

            event = ShieldEquipEvent(
                name=item.name,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                item_uuid=item.uuid,
                slot=slot
            )

            if event.phase_to(EventPhase.EXECUTION).canceled:
                return False

            for conflict_slot in conflict_slots:
                self.unequip(conflict_slot)

            if self.weapon_melee_off is not None:
                self.unequip(WeaponSlot.MELEE_OFF)

            self.weapon_melee_off = item
            item.owner_uuid = self.source_entity_uuid
            item.stored_in_uuid = self.uuid
            item.equip(slot, self.source_entity_uuid)
            event.phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
            return True

        if isinstance(item, Weapon):
            is_ranged_weapon = WeaponProperty.RANGED in item.properties

            is_light_weapon = WeaponProperty.LIGHT in item.properties

            if slot is None:
                slot = WeaponSlot.RANGED_MAIN if is_ranged_weapon else WeaponSlot.MELEE_MAIN
            elif isinstance(slot, WeaponSlot):
                slot_is_ranged = slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF)
                if is_ranged_weapon and not slot_is_ranged:
                    raise ValueError(f"Ranged weapon cannot be equipped in melee slot {slot}")
                if not is_ranged_weapon and slot_is_ranged:
                    raise ValueError(f"Melee weapon cannot be equipped in ranged slot {slot}")
                if slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF) and not is_light_weapon:
                    raise ValueError(f"Only LIGHT weapons can be equipped in off-hand slot {slot}")

            assert isinstance(slot, WeaponSlot)
            conflict_slots = self._get_melee_hand_conflict_slots(item, slot)
            current_weapon = self._get_weapon_by_slot(slot)

            event = WeaponEquipEvent(
                name=item.name,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                item_uuid=item.uuid,
                slot=slot
            )

            if event.phase_to(EventPhase.EXECUTION).canceled:
                return False

            for conflict_slot in conflict_slots:
                self.unequip(conflict_slot)

            if current_weapon is not None:
                self.unequip(slot)

            if slot == WeaponSlot.MELEE_MAIN:
                self.weapon_melee_main = item
            elif slot == WeaponSlot.MELEE_OFF:
                self.weapon_melee_off = item
            elif slot == WeaponSlot.RANGED_MAIN:
                self.weapon_ranged_main = item
            elif slot == WeaponSlot.RANGED_OFF:
                self.weapon_ranged_off = item

            item.owner_uuid = self.source_entity_uuid
            item.stored_in_uuid = self.uuid
            item.equip(slot, self.source_entity_uuid)
            event.phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
            return True

        if slot is None and isinstance(item, Armor):
            slot = item.body_part

        if slot not in slot_mapping:
            raise ValueError(f"Invalid equipment slot: {slot}")
        assert slot is not None

        current_armor = self.get_item_by_slot(slot)

        event = ArmorEquipEvent(
            name=item.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            item_uuid=item.uuid,
            slot=slot
        )

        if event.phase_to(EventPhase.EXECUTION).canceled:
            return False

        if current_armor is not None:
            self.unequip(slot)

        assert isinstance(slot, BodyPart)
        attribute_name = slot_mapping[slot]
        setattr(self, attribute_name, item)

        item.owner_uuid = self.source_entity_uuid
        item.stored_in_uuid = self.uuid
        item.equip(slot, self.source_entity_uuid)
        event.phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
        return True

    def unequip(self, slot: Union[BodyPart, RingSlot, WeaponSlot], parent_event_uuid: Optional[UUID] = None) -> Optional[Union[Armor, Weapon, Shield]]:
        """Unequip the item in the specified slot.

        Direct equipment calls clear the slot and call item hooks, but leave
        owner and storage fields for the caller to update.

        Args:
            slot: The slot to unequip from.
            parent_event_uuid: Optional parent event for the unequip event.

        Returns:
            The unequipped item, or None if slot was empty or event was canceled.

        Raises:
            ValueError: If the slot is invalid
        """
        if isinstance(slot, RingSlot):
            attribute_name = "ring_left" if slot == RingSlot.LEFT else "ring_right"
        elif isinstance(slot, WeaponSlot):
            weapon_slot_mapping = {
                WeaponSlot.MELEE_MAIN: "weapon_melee_main",
                WeaponSlot.MELEE_OFF: "weapon_melee_off",
                WeaponSlot.RANGED_MAIN: "weapon_ranged_main",
                WeaponSlot.RANGED_OFF: "weapon_ranged_off",
            }
            attribute_name = weapon_slot_mapping[slot]
        elif isinstance(slot, BodyPart):
            if slot not in slot_mapping:
                raise ValueError(f"Invalid equipment slot: {slot}")
            attribute_name = slot_mapping[slot]
        else:
            raise ValueError(f"Invalid equipment slot: {slot}")

        current_item = getattr(self, attribute_name)
        if current_item is None:
            return None

        if isinstance(current_item, Weapon):
            event = WeaponUnequipEvent(
                name=current_item.name,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                item_uuid=current_item.uuid,
                slot=slot,
                parent_event=parent_event_uuid
            )
        elif isinstance(current_item, Shield):
            event = ShieldUnequipEvent(
                name=current_item.name,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                item_uuid=current_item.uuid,
                slot=slot,
                parent_event=parent_event_uuid
            )
        else:
            event = ArmorUnequipEvent(
                name=current_item.name,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                item_uuid=current_item.uuid,
                slot=slot,
                parent_event=parent_event_uuid
            )

        if event.phase_to(EventPhase.EXECUTION).canceled:
            return None

        current_item.unequip(slot, self.source_entity_uuid)
        setattr(self, attribute_name, None)

        event.phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
        return current_item

    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "Equipped", source_entity_name: Optional[str] = None,
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None,
                config: Optional[EquipmentConfig] = None) -> 'Equipment':
        """Create an equipment block from an optional modifier configuration.

        Args:
            source_entity_uuid: UUID of the entity that owns this equipment block.
            name: Display name for the equipment block.
            source_entity_name: Optional source entity display name.
            target_entity_uuid: Optional target entity UUID for inherited block metadata.
            target_entity_name: Optional target entity display name.
            config: Optional static configuration for equipment values.

        Returns:
            Equipment block with configured modifiable values.
        """
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
