"""Equipment, armor, weapon, and shield models for entity combat gear."""

from dataclasses import dataclass
from typing import Callable, Iterable, Optional, List, Self, TypeVar, Union, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from dnd.core.values import ModifiableValue
from dnd.types.damage import DamageType
from dnd.core.modifiers import NumericalModifier
from dnd.blocks.abilities import Ability, AbilityScores
from dnd.core.events.events_registry import (
    Event,
    EventQueue,
    EventType,
    EventPhase,
)
from dnd.core.events.resolution_events import (
    Range,
    RangeType,
    Damage,
)
from dnd.core.events.item_events import (
    ArmorEquipEvent,
    ArmorUnequipEvent,
    EquipmentEvent,
    ShieldEquipEvent,
    ShieldUnequipEvent,
    WeaponEquipEvent,
    WeaponUnequipEvent,
    ItemState,
)
from dnd.types.abilities import AbilityName
from dnd.types.equipment import (
    ArmorType,
    BodyPart,
    EquipmentSlot,
    RingSlot,
    UnarmoredAc,
    WeaponProperty,
    WeaponSet,
    WeaponSlot,
)
from dnd.types.items import ItemKind
from dnd.types.rolls import DieSize

import copy

from dnd.core.base_block import BaseBlock
from dnd.blocks.base_item import (
    EquippableItem,
)
from dnd.blocks.inventory import Inventory


_EQUIPMENT_EVENT_CLASS_BY_TYPE: dict[EventType, type[EquipmentEvent]] = {
    EventType.WEAPON_EQUIP: WeaponEquipEvent,
    EventType.WEAPON_UNEQUIP: WeaponUnequipEvent,
    EventType.ARMOR_EQUIP: ArmorEquipEvent,
    EventType.ARMOR_UNEQUIP: ArmorUnequipEvent,
    EventType.SHIELD_EQUIP: ShieldEquipEvent,
    EventType.SHIELD_UNEQUIP: ShieldUnequipEvent,
}


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

    def compatible_equipment_slots(self) -> Tuple[EquipmentSlot, ...]:
        """Armor and accessories occupy their declared body slot."""
        return (self.body_part,)

    def equipment_event_type(self, *, equipping: bool) -> EventType:
        """Classify armor transitions for public event routing."""
        return EventType.ARMOR_EQUIP if equipping else EventType.ARMOR_UNEQUIP

    def default_equipment_slot(self) -> Optional[EquipmentSlot]:
        """Body-part gear has one unambiguous default slot."""
        return self.body_part

    def to_item_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemState:
        """Add armor mechanics to the renderer-independent item fact."""
        return super().to_item_state(stack_count=stack_count).model_copy(update={
            "item_kind": ItemKind.ARMOR,
            "armor_type": self.type,
            "armor_class": self.ac.normalized_score,
        })

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

    def compatible_equipment_slots(self) -> Tuple[EquipmentSlot, ...]:
        """Rings may use either concrete ring slot."""
        return (RingSlot.LEFT, RingSlot.RIGHT)

    def default_equipment_slot(self) -> Optional[EquipmentSlot]:
        """Do not guess which occupied ring slot a caller intended."""
        return None


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

    def compatible_equipment_slots(self) -> Tuple[EquipmentSlot, ...]:
        """Shields occupy the melee off hand."""
        return (WeaponSlot.MELEE_OFF,)

    def equipment_event_type(self, *, equipping: bool) -> EventType:
        """Classify shield transitions for public event routing."""
        return EventType.SHIELD_EQUIP if equipping else EventType.SHIELD_UNEQUIP

    def default_equipment_slot(self) -> Optional[EquipmentSlot]:
        """Return the shield's sole compatible slot."""
        return WeaponSlot.MELEE_OFF

    def incompatible_equipment_slot_message(self, slot: EquipmentSlot) -> str:
        """Preserve the domain-specific shield validation diagnostic."""
        return "Shields can only be equipped in MELEE_OFF slot"

    def to_item_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemState:
        """Add shield mechanics to the renderer-independent item fact."""
        return super().to_item_state(stack_count=stack_count).model_copy(update={
            "item_kind": ItemKind.SHIELD,
            "shield_armor_class_bonus": self.ac_bonus.normalized_score,
        })


class Weapon(EquippableItem):
    """Equippable weapon with attack, damage, range, and property metadata."""

    name: str = Field(default="Weapon", description="Name of the weapon")
    map_char: str = Field(default="\u2020", description="Character to display on the map grid")
    description: Optional[str] = Field(
        default=None,
        description="Detailed description of the weapon"
    )
    damage_dice: DieSize = Field(
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
    extra_damage_dices: List[DieSize] = Field(
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

    def compatible_equipment_slots(self) -> Tuple[EquipmentSlot, ...]:
        """Return slots allowed by the weapon's ranged and light properties."""
        if WeaponProperty.RANGED in self.properties:
            slots: List[EquipmentSlot] = [WeaponSlot.RANGED_MAIN]
            if WeaponProperty.LIGHT in self.properties:
                slots.append(WeaponSlot.RANGED_OFF)
            return tuple(slots)
        slots = [WeaponSlot.MELEE_MAIN]
        if WeaponProperty.LIGHT in self.properties:
            slots.append(WeaponSlot.MELEE_OFF)
        return tuple(slots)

    def equipment_event_type(self, *, equipping: bool) -> EventType:
        """Classify weapon transitions for public event routing."""
        return EventType.WEAPON_EQUIP if equipping else EventType.WEAPON_UNEQUIP

    def default_equipment_slot(self) -> Optional[EquipmentSlot]:
        """Choose the matching main-hand loadout when no slot is supplied."""
        if WeaponProperty.RANGED in self.properties:
            return WeaponSlot.RANGED_MAIN
        return WeaponSlot.MELEE_MAIN

    def occupied_equipment_slots(
        self,
        selected_slot: EquipmentSlot,
    ) -> frozenset[EquipmentSlot]:
        """Declare that a two-handed melee main weapon also occupies its off hand."""
        if (
            selected_slot == WeaponSlot.MELEE_MAIN
            and WeaponProperty.TWO_HANDED in self.properties
            and WeaponProperty.RANGED not in self.properties
        ):
            return frozenset((WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF))
        return super().occupied_equipment_slots(selected_slot)

    def incompatible_equipment_slot_message(self, slot: EquipmentSlot) -> str:
        """Return a precise weapon-slot validation diagnostic."""
        if not isinstance(slot, WeaponSlot):
            return f"Weapon cannot be equipped in non-weapon slot {slot}"
        is_ranged = WeaponProperty.RANGED in self.properties
        slot_is_ranged = slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF)
        if is_ranged and not slot_is_ranged:
            return f"Ranged weapon cannot be equipped in melee slot {slot}"
        if not is_ranged and slot_is_ranged:
            return f"Melee weapon cannot be equipped in ranged slot {slot}"
        if (
            slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF)
            and WeaponProperty.LIGHT not in self.properties
        ):
            return f"Only LIGHT weapons can be equipped in off-hand slot {slot}"
        return super().incompatible_equipment_slot_message(slot)

    def to_item_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemState:
        """Add weapon mechanics to the renderer-independent item fact."""
        return super().to_item_state(stack_count=stack_count).model_copy(update={
            "item_kind": ItemKind.WEAPON,
            "damage_die": self.damage_dice,
            "damage_dice_count": self.dice_numbers,
            "damage_bonus": (
                self.damage_bonus.normalized_score
                if self.damage_bonus is not None
                else None
            ),
            "attack_bonus": self.attack_bonus.normalized_score,
            "damage_type": self.damage_type,
            "weapon_properties": tuple(self.properties),
            "range_kind": self.range.type.value,
            "normal_range_feet": self.range.normal,
            "long_range_feet": self.range.long,
        })

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

_SLOT_ATTRIBUTE_BY_SLOT = {
    WeaponSlot.MELEE_MAIN: "weapon_melee_main",
    WeaponSlot.MELEE_OFF: "weapon_melee_off",
    WeaponSlot.RANGED_MAIN: "weapon_ranged_main",
    WeaponSlot.RANGED_OFF: "weapon_ranged_off",
    BodyPart.HEAD: "helmet",
    BodyPart.BODY: "body_armor",
    BodyPart.HANDS: "gauntlets",
    BodyPart.LEGS: "greaves",
    BodyPart.FEET: "boots",
    BodyPart.AMULET: "amulet",
    RingSlot.LEFT: "ring_left",
    RingSlot.RIGHT: "ring_right",
    BodyPart.CLOAK: "cloak",
}
_MELEE_WEAPON_SLOTS = (
    WeaponSlot.MELEE_MAIN,
    WeaponSlot.MELEE_OFF,
)
_RANGED_WEAPON_SLOTS = (
    WeaponSlot.RANGED_MAIN,
    WeaponSlot.RANGED_OFF,
)


@dataclass(frozen=True)
class EquipmentEquipResult:
    """Result of one atomic equipment-slot transaction."""

    succeeded: bool
    selected_slot: Optional[EquipmentSlot] = None
    displaced_items: Tuple[EquippableItem, ...] = ()


@dataclass(frozen=True)
class _PreparedEquipmentTransition:
    """One accepted but unpublished gear transition."""

    slot: EquipmentSlot
    item: EquippableItem
    equipping: bool
    declaration: EquipmentEvent
    execution: EquipmentEvent


DamageProfileT = TypeVar("DamageProfileT")


class ArmorClassFormulaCandidate(BaseModel):
    """One exact source-owned unarmored Armor Class formula."""

    model_config = ConfigDict(frozen=True)

    source_id: UUID = Field(description="Owning progression grant UUID.")
    base_ac: int = Field(ge=0, description="Formula base before ability modifiers.")
    ability_names: Tuple[AbilityName, ...] = Field(
        default_factory=tuple,
        description="Ability modifiers included by this formula.",
    )
    requires_unarmored: bool = Field(
        default=True,
        description="Whether ordinary body armor makes this formula ineligible.",
    )
    allows_shield: bool = Field(
        default=True,
        description="Whether an equipped shield contributes to this formula.",
    )


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
    active_weapon_set: WeaponSet = Field(
        default=WeaponSet.NONE,
        description=(
            "Persisted melee/ranged stance selected by accepted attack and "
            "equipment transitions."
        ),
    )
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
    armor_class_formula_candidates: dict[UUID, ArmorClassFormulaCandidate] = Field(
        default_factory=dict,
        description="Unarmored AC formulas keyed by exact progression source.",
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

    extra_attack_damage_dices: List[DieSize] = Field(
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

    unarmed_damage_dice: DieSize = Field(
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

    def get_all_equipped_items(self) -> List[EquippableItem]:
        """Return all equipped items across all slots in stable slot order."""
        return [
            item
            for attribute_name in _SLOT_ATTRIBUTE_BY_SLOT.values()
            if (item := getattr(self, attribute_name)) is not None
        ]

    @staticmethod
    def weapon_set_for_slot(slot: WeaponSlot) -> WeaponSet:
        """Return the stance selected when an accepted attack uses ``slot``."""
        if slot in _MELEE_WEAPON_SLOTS:
            return WeaponSet.MELEE
        return WeaponSet.RANGED

    def _weapon_set_has_equipment(self, weapon_set: WeaponSet) -> bool:
        """Return whether a stance currently has at least one equipped layer."""
        if weapon_set is WeaponSet.MELEE:
            slots = _MELEE_WEAPON_SLOTS
        elif weapon_set is WeaponSet.RANGED:
            slots = _RANGED_WEAPON_SLOTS
        else:
            return False
        return any(self.get_item_by_slot(slot) is not None for slot in slots)

    def activate_weapon_slot(self, slot: WeaponSlot) -> None:
        """Persist the stance used by an accepted weapon-attack effect."""
        self.active_weapon_set = self.weapon_set_for_slot(slot)

    def _reconcile_active_weapon_set(
        self,
        *,
        preferred_slot: Optional[WeaponSlot] = None,
    ) -> None:
        """Keep stance valid after an accepted equipment transition.

        Equipping a second, inactive loadout does not silently draw it.  The
        first equipped set establishes a stance, while removal of the active
        set falls back to the preferred surviving set, then melee, then ranged.
        """
        if self._weapon_set_has_equipment(self.active_weapon_set):
            return
        preferred_set = (
            self.weapon_set_for_slot(preferred_slot)
            if preferred_slot is not None
            else WeaponSet.NONE
        )
        if self._weapon_set_has_equipment(preferred_set):
            self.active_weapon_set = preferred_set
        elif self._weapon_set_has_equipment(WeaponSet.MELEE):
            self.active_weapon_set = WeaponSet.MELEE
        elif self._weapon_set_has_equipment(WeaponSet.RANGED):
            self.active_weapon_set = WeaponSet.RANGED
        else:
            self.active_weapon_set = WeaponSet.NONE

    def _get_weapon_by_slot(self, slot: WeaponSlot) -> Optional[Union[Weapon, Shield]]:
        """Helper to get weapon/shield by slot."""
        item = self.get_item_by_slot(slot)
        return item if isinstance(item, (Weapon, Shield)) else None

    def get_weapon(self, slot: WeaponSlot) -> Optional[Weapon]:
        """Return the actual weapon in ``slot``; shields and empty slots are unarmed."""
        item = self.get_item_by_slot(slot)
        return item if isinstance(item, Weapon) else None

    def get_item_by_slot(self, slot: EquipmentSlot) -> Optional[EquippableItem]:
        """Get the item in any equipment slot."""
        attribute_name = _SLOT_ATTRIBUTE_BY_SLOT.get(slot)
        return getattr(self, attribute_name) if attribute_name is not None else None

    def get_weapon_range(self, slot: WeaponSlot) -> Range:
        """Return a weapon's range or ordinary reach for an unarmed/shield slot."""
        weapon = self.get_weapon(slot)
        if weapon is None:
            return Range(type=RangeType.REACH, normal=5)
        return weapon.range

    @staticmethod
    def _select_weapon_attack_ability(
        ability_block: AbilityScores,
        weapon: Optional[Weapon],
        override_ability: Optional[AbilityName],
    ) -> Ability:
        """Select the ability used by a weapon attack roll."""
        if override_ability is not None:
            return ability_block.get_ability(override_ability)
        if weapon is None:
            return ability_block.strength
        if weapon.range.type == RangeType.RANGE:
            return ability_block.dexterity
        if WeaponProperty.FINESSE in weapon.properties:
            strength = ability_block.strength
            dexterity = ability_block.dexterity
            return strength if strength.modifier >= dexterity.modifier else dexterity
        return ability_block.strength

    def _select_weapon_damage_ability(
        self,
        ability_block: AbilityScores,
        weapon: Optional[Weapon],
        override_ability: Optional[AbilityName],
    ) -> Ability:
        """Select the ability used by a weapon damage roll."""
        if override_ability is not None:
            return ability_block.get_ability(override_ability)
        if weapon is None:
            strength = ability_block.strength
            if WeaponProperty.FINESSE in self.unarmed_properties:
                dexterity = ability_block.dexterity
                return strength if strength.modifier >= dexterity.modifier else dexterity
            return strength
        if WeaponProperty.RANGED in weapon.properties:
            return ability_block.dexterity
        if WeaponProperty.FINESSE in weapon.properties:
            strength = ability_block.strength
            dexterity = ability_block.dexterity
            return strength if strength.modifier >= dexterity.modifier else dexterity
        return ability_block.strength

    def get_weapon_attack_ability_name(
        self,
        ability_block: AbilityScores,
        weapon_slot: WeaponSlot,
        override_ability: Optional[AbilityName] = None,
    ) -> str:
        """Return the exact ability selected for one weapon attack."""
        return self._select_weapon_attack_ability(
            ability_block,
            self.get_weapon(weapon_slot),
            override_ability,
        ).name

    def get_attack_bonus_components(
        self,
        ability_block: AbilityScores,
        weapon_slot: WeaponSlot,
        override_ability: Optional[AbilityName] = None,
    ) -> Tuple[ModifiableValue, List[ModifiableValue], List[ModifiableValue], Range]:
        """Return weapon, equipment, ability, and range attack components."""
        weapon = self.get_weapon(weapon_slot)
        ability_bonuses: List[ModifiableValue] = []
        attack_bonuses = [self.attack_bonus]
        if weapon is None:
            weapon_bonus = self.unarmed_attack_bonus
            attack_bonuses.append(self.melee_attack_bonus)
            weapon_range = self.get_weapon_range(weapon_slot)
        else:
            weapon_bonus = weapon.attack_bonus
            weapon_range = weapon.range
            attack_bonuses.append(
                self.ranged_attack_bonus
                if weapon.range.type == RangeType.RANGE
                else self.melee_attack_bonus
            )
        ability = self._select_weapon_attack_ability(
            ability_block,
            weapon,
            override_ability,
        )
        ability_bonuses.append(ability.get_combined_values())
        return weapon_bonus, attack_bonuses, ability_bonuses, weapon_range

    def get_weapon_attack_baseline(
        self,
        ability_block: AbilityScores,
        weapon_slot: WeaponSlot,
        override_ability: Optional[AbilityName] = None,
    ) -> Tuple[int, int]:
        """Return actor-side attack bonus and advantage contributions."""
        weapon = self.get_weapon(weapon_slot)
        ability = self._select_weapon_attack_ability(
            ability_block,
            weapon,
            override_ability,
        )
        weapon_bonus = weapon.attack_bonus if weapon is not None else self.unarmed_attack_bonus
        typed_bonus = (
            self.ranged_attack_bonus
            if weapon is not None and weapon.range.type == RangeType.RANGE
            else self.melee_attack_bonus
        )
        components = (weapon_bonus, self.attack_bonus, typed_bonus)
        return (
            ability.modifier + sum(component.normalized_score for component in components),
            ability.modifier_bonus.advantage_sum
            + sum(component.advantage_sum for component in components),
        )

    def get_weapon_damage_profiles(
        self,
        ability_block: AbilityScores,
        weapon_slot: WeaponSlot,
        profile_factory: Callable[..., DamageProfileT],
        override_ability: Optional[AbilityName] = None,
    ) -> List[DamageProfileT]:
        """Build damage formulas without importing the higher-level action DTO."""
        weapon = self.get_weapon(weapon_slot)
        profiles: List[DamageProfileT] = []
        if weapon is not None:
            base_bonuses = [
                value
                for value in (weapon.damage_bonus, self.damage_bonus)
                if value is not None
            ]
            ability_bonus = 0
            if weapon_slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF):
                base_bonuses.append(
                    self.off_hand_ranged_ability_bonus
                    if weapon_slot == WeaponSlot.RANGED_OFF
                    else self.off_hand_melee_ability_bonus
                )
            else:
                ability_bonus = self._select_weapon_damage_ability(
                    ability_block,
                    weapon,
                    override_ability,
                ).modifier
            base_bonuses.append(
                self.ranged_damage_bonus
                if WeaponProperty.RANGED in weapon.properties
                else self.melee_damage_bonus
            )
            profiles.append(profile_factory(
                dice_count=weapon.dice_numbers,
                die_size=weapon.damage_dice,
                flat_bonus=(
                    sum(value.normalized_score for value in base_bonuses)
                    + ability_bonus
                ),
                damage_type=weapon.damage_type.value,
            ))
            profiles.extend(
                profile_factory(
                    dice_count=dice_count,
                    die_size=die_size,
                    flat_bonus=bonus.normalized_score,
                    damage_type=damage_type.value,
                )
                for die_size, dice_count, bonus, damage_type in zip(
                    weapon.extra_damage_dices,
                    weapon.extra_damage_dices_numbers,
                    weapon.extra_damage_bonus,
                    weapon.extra_damage_type,
                )
            )
        else:
            ability = self._select_weapon_damage_ability(
                ability_block,
                None,
                override_ability,
            )
            base_bonuses = (
                self.unarmed_damage_bonus,
                self.damage_bonus,
                self.melee_damage_bonus,
            )
            profiles.append(profile_factory(
                dice_count=self.unarmed_dice_numbers,
                die_size=self.unarmed_damage_dice,
                flat_bonus=(
                    sum(value.normalized_score for value in base_bonuses)
                    + ability.modifier
                ),
                damage_type=self.unarmed_damage_type.value,
            ))
        profiles.extend(
            profile_factory(
                dice_count=dice_count,
                die_size=die_size,
                flat_bonus=bonus.normalized_score,
                damage_type=damage_type.value,
            )
            for die_size, dice_count, bonus, damage_type in zip(
                self.extra_attack_damage_dices,
                self.extra_attack_damage_dices_numbers,
                self.extra_attack_damage_bonus,
                self.extra_attack_damage_type,
            )
        )
        return profiles

    def snapshot_attack_event_metadata(
        self,
        slot: WeaponSlot,
    ) -> Tuple[str, Tuple[DamageType, ...]]:
        """Return immutable equipped or unarmed facts for an attack event.

        The ordered damage categories mirror ``get_damages()``: the primary
        weapon/unarmed component, temporary equipment-level components, then
        weapon-owned components.  Declarations need the complete potential
        palette because a miss has no damage packets from which to recover it.
        """
        weapon = self.get_weapon(slot)
        if weapon is None:
            weapon_name = "Unarmed"
            damage_types = (
                self.unarmed_damage_type,
                *self.extra_attack_damage_type,
            )
        else:
            weapon_name = weapon.name
            damage_types = (
                weapon.damage_type,
                *self.extra_attack_damage_type,
                *weapon.extra_damage_type,
            )
        return (
            weapon_name,
            tuple(dict.fromkeys(damage_types)),
        )

    def get_weapon_metadata(self, slot: WeaponSlot) -> Optional[Tuple[str, List[str]]]:
        """Return equipped-weapon discovery metadata as transport strings."""
        if self.get_weapon(slot) is None:
            return None
        weapon_name, damage_types = self.snapshot_attack_event_metadata(slot)
        return weapon_name, [
            damage_type.value
            for damage_type in damage_types
        ]

    def remove_contained_item(self, item_uuid: UUID) -> None:
        """Remove an equipped item by UUID during item-owned cleanup.

        Destruction cleanup must not be cancelable, but item unequip hooks still
        need to run so equipped modifiers and handlers are removed.

        Args:
            item_uuid: UUID of the equipped item to remove.
        """
        for slot, attribute_name in _SLOT_ATTRIBUTE_BY_SLOT.items():
            item = getattr(self, attribute_name)
            if item is not None and item.uuid == item_uuid:
                declaration = self._create_equipment_event(
                    item,
                    slot,
                    equipping=False,
                    use_register=False,
                )
                execution = declaration.phase_to(
                    EventPhase.EXECUTION,
                    status_message="Equipped item destruction committed",
                )
                item.unequip(slot, self.source_entity_uuid)
                setattr(self, attribute_name, None)
                if isinstance(slot, WeaponSlot):
                    self._reconcile_active_weapon_set()
                effect = execution.phase_to(
                    EventPhase.EFFECT,
                    status_message="Destroyed item removed from equipment",
                )
                effect.phase_to(
                    EventPhase.COMPLETION,
                    status_message="Destroyed item equipment state completed",
                    use_register=True,
                )
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
            ability = ability_block.get_ability(override_ability)
            ability_bonus = ability.get_combined_values()
        else:
            ability = ability_block.strength
            strength_bonus = ability.get_combined_values()
            ability_bonus = strength_bonus
            if WeaponProperty.FINESSE in self.unarmed_properties:
                dexterity = ability_block.dexterity
                dexterity_bonus = dexterity.get_combined_values()
                if dexterity_bonus.normalized_score > strength_bonus.normalized_score:
                    ability = dexterity
                    ability_bonus = dexterity_bonus
        combined_bonus = unarmed_damage_bonus.combine_values([self.damage_bonus,self.melee_damage_bonus, ability_bonus])
        combined_bonus.set_context({
            "attack_ability": ability.name,
            "range_type": RangeType.REACH.value,
        })
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

            damage = weapon.get_base_damage(
                self,
                ability_block,
                is_off_hand=is_off_hand,
                off_hand_ability_bonus=off_hand_ability_bonus,
                override_ability=override_ability,
            )
            if damage.damage_bonus is not None:
                ability = self._select_weapon_damage_ability(
                    ability_block,
                    weapon,
                    override_ability,
                )
                damage.damage_bonus.set_context({
                    "attack_ability": ability.name,
                    "range_type": weapon.range.type.value,
                })
            return damage
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

    def add_armor_class_formula_candidate(
        self,
        candidate: ArmorClassFormulaCandidate,
    ) -> None:
        """Add one formula, rejecting source identity reuse with new rules."""
        existing = self.armor_class_formula_candidates.get(candidate.source_id)
        if existing is not None and existing != candidate:
            raise ValueError(
                f"armor class formula source {candidate.source_id} "
                "already exists with a different contract"
            )
        self.armor_class_formula_candidates[candidate.source_id] = candidate

    def remove_armor_class_formula_candidate(self, source_id: UUID) -> bool:
        """Remove exactly one source-owned Armor Class formula."""
        return self.armor_class_formula_candidates.pop(source_id, None) is not None

    def _legacy_armor_class_formula_candidate(
        self,
    ) -> ArmorClassFormulaCandidate:
        """Represent the existing singleton mode as a compatibility candidate."""
        base_modifier = self.unarmored_ac.get_base_modifier()
        base_ac = base_modifier.normalized_value if base_modifier is not None else 10
        if self.unarmored_ac_type == UnarmoredAc.BARBARIAN:
            abilities: Tuple[AbilityName, ...] = (
                AbilityName.DEXTERITY,
                AbilityName.CONSTITUTION,
            )
        elif self.unarmored_ac_type == UnarmoredAc.MONK:
            abilities = (AbilityName.DEXTERITY, AbilityName.STRENGTH)
        else:
            abilities = (AbilityName.DEXTERITY,)
        if self.unarmored_ac_type in (
            UnarmoredAc.DRACONIC_SORCERER,
            UnarmoredAc.MAGIC_ARMOR,
        ):
            base_ac += 3
        return ArmorClassFormulaCandidate(
            source_id=self.uuid,
            base_ac=base_ac,
            ability_names=abilities,
            requires_unarmored=True,
            allows_shield=True,
        )

    def resolve_armor_class_formula_candidate(
        self,
        ability_block: AbilityScores,
    ) -> Optional[ArmorClassFormulaCandidate]:
        """Select the highest applicable formula, with stable first-source ties."""
        candidates = [
            self._legacy_armor_class_formula_candidate(),
            *self.armor_class_formula_candidates.values(),
        ]
        applicable = [
            candidate
            for candidate in candidates
            if not candidate.requires_unarmored or self.is_unarmored()
        ]
        if not applicable:
            return None

        def score(candidate: ArmorClassFormulaCandidate) -> int:
            total = candidate.base_ac
            total += sum(
                ability_block.get_ability(
                    ability_name
                ).get_combined_values().normalized_score
                for ability_name in candidate.ability_names
            )
            if (
                candidate.allows_shield
                and isinstance(self.weapon_melee_off, Shield)
            ):
                total += self.weapon_melee_off.ac_bonus.normalized_score
            return total

        return max(applicable, key=score)

    def get_unarmored_abilities(
        self,
        candidate: Optional[ArmorClassFormulaCandidate] = None,
    ) -> List[AbilityName]:
        """Return ability modifiers included in the active unarmored AC formula."""
        if candidate is not None:
            return list(candidate.ability_names)
        if self.unarmored_ac_type == UnarmoredAc.BARBARIAN:
            return [AbilityName.DEXTERITY, AbilityName.CONSTITUTION]
        elif self.unarmored_ac_type == UnarmoredAc.MONK:
            return [AbilityName.DEXTERITY, AbilityName.STRENGTH]
        else:
            return[AbilityName.DEXTERITY]

    def is_unarmored(self) -> bool:
        """Return whether body armor is absent or cloth-only."""
        return self.body_armor is None or self.body_armor.type == ArmorType.CLOTH

    def get_unarmored_ac_values(
        self,
        candidate: Optional[ArmorClassFormulaCandidate] = None,
    ) -> List[ModifiableValue]:
        """Return modifiable values that contribute to unarmored AC."""
        values = [self.ac_bonus]
        if candidate is not None:
            temporary_value = copy.deepcopy(self.unarmored_ac)
            base_modifier = self.unarmored_ac.get_base_modifier()
            current_base = (
                base_modifier.normalized_value
                if base_modifier is not None
                else 0
            )
            base_delta = candidate.base_ac - current_base
            if base_delta:
                temporary_value.self_static.add_value_modifier(
                    NumericalModifier.create(
                        source_entity_uuid=self.source_entity_uuid,
                        name="armor_class_formula_base",
                        value=base_delta,
                    )
                )
            values.append(temporary_value)
        elif self.unarmored_ac_type in [UnarmoredAc.DRACONIC_SORCERER, UnarmoredAc.MAGIC_ARMOR]:
            unarmored_ac_static_modifier = NumericalModifier.create(source_entity_uuid=self.source_entity_uuid, name="unarmored_ac_bonus", value=3)
            temporary_value = copy.deepcopy(self.unarmored_ac)
            temporary_value.self_static.add_value_modifier(unarmored_ac_static_modifier)
            values.append(temporary_value)
        else:
            values.append(self.unarmored_ac)
        if (
            self.weapon_melee_off
            and isinstance(self.weapon_melee_off, Shield)
            and (candidate is None or candidate.allows_shield)
        ):
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

    def resolve_equipment_slot(
        self,
        item: EquippableItem,
        slot: Optional[EquipmentSlot] = None,
    ) -> EquipmentSlot:
        """Resolve an optional slot and validate it against item-owned policy."""
        selected_slot = slot if slot is not None else item.default_equipment_slot()
        if selected_slot is None:
            raise ValueError(f"{item.name} requires an explicit equipment slot")
        if selected_slot not in _SLOT_ATTRIBUTE_BY_SLOT:
            raise ValueError(f"Invalid equipment slot: {selected_slot}")
        if selected_slot not in item.compatible_equipment_slots():
            raise ValueError(item.incompatible_equipment_slot_message(selected_slot))
        return selected_slot

    def _install_initial_item(
        self,
        inventory: Inventory,
        item: EquippableItem,
        slot: Optional[EquipmentSlot] = None,
    ) -> Callable[[], None]:
        """Equip one starting inventory item without publishing transitions.

        Slot policy, physical footprints, and item hooks remain the same as a
        gameplay equip. A collision is an authored-loadout error during birth;
        construction never silently displaces another starting item.
        """
        if inventory.items.get(item.uuid) is not item:
            raise ValueError("starting equipment must first be in inventory")
        selected_slot = self.resolve_equipment_slot(item, slot)
        conflicts = self._get_conflicts(item, selected_slot)
        if conflicts:
            occupied = ", ".join(row[0].value for row in conflicts)
            raise ValueError(
                f"starting equipment collides with occupied slots: {occupied}",
            )

        attribute_name = _SLOT_ATTRIBUTE_BY_SLOT[selected_slot]
        previous_active_set = self.active_weapon_set
        inventory.remove_item(item.uuid)
        self._reparent_equippable_item(item)
        setattr(self, attribute_name, item)
        item.owner_uuid = self.source_entity_uuid
        item.stored_in_uuid = self.uuid
        try:
            item.equip(selected_slot, self.source_entity_uuid)
            if isinstance(selected_slot, WeaponSlot):
                self._reconcile_active_weapon_set(preferred_slot=selected_slot)
        except Exception:
            if item.is_equipped:
                item.unequip(selected_slot, self.source_entity_uuid)
            setattr(self, attribute_name, None)
            self.active_weapon_set = previous_active_set
            item.owner_uuid = self.source_entity_uuid
            item.stored_in_uuid = inventory.uuid
            inventory.items[item.uuid] = item
            raise

        def undo() -> None:
            if getattr(self, attribute_name) is not item:
                raise RuntimeError(
                    f"starting item {item.uuid} is no longer in {selected_slot.value}",
                )
            item.unequip(selected_slot, self.source_entity_uuid)
            setattr(self, attribute_name, None)
            self.active_weapon_set = previous_active_set
            item.owner_uuid = self.source_entity_uuid
            item.stored_in_uuid = inventory.uuid
            inventory.items[item.uuid] = item

        return undo

    def _get_conflicts(
        self,
        item: EquippableItem,
        selected_slot: EquipmentSlot,
    ) -> List[Tuple[EquipmentSlot, EquippableItem]]:
        """Return occupied slots and items overlapping the proposed footprint."""
        new_footprint = item.occupied_equipment_slots(selected_slot)
        conflicts: List[Tuple[EquipmentSlot, EquippableItem]] = []
        seen_item_uuids: set[UUID] = set()
        for occupied_slot in _SLOT_ATTRIBUTE_BY_SLOT:
            current_item = self.get_item_by_slot(occupied_slot)
            if current_item is None or current_item.uuid in seen_item_uuids:
                continue
            current_footprint = current_item.occupied_equipment_slots(occupied_slot)
            if new_footprint & current_footprint:
                conflicts.append((occupied_slot, current_item))
                seen_item_uuids.add(current_item.uuid)
        return conflicts

    def get_equipment_displacement(
        self,
        item: EquippableItem,
        slot: Optional[EquipmentSlot] = None,
    ) -> Tuple[EquipmentSlot, Tuple[EquippableItem, ...]]:
        """Return the selected slot and current pure displacement result."""
        selected_slot = self.resolve_equipment_slot(item, slot)
        displaced_items = tuple(
            conflicting_item
            for _conflicting_slot, conflicting_item in self._get_conflicts(
                item,
                selected_slot,
            )
        )
        return selected_slot, displaced_items

    def _reparent_equippable_item(self, item: EquippableItem) -> None:
        """Update item-owned values and channels to this equipment owner."""
        item.source_entity_uuid = self.source_entity_uuid
        for field_value in item.__dict__.values():
            values = field_value if isinstance(field_value, list) else (field_value,)
            for value in values:
                if not isinstance(value, ModifiableValue):
                    continue
                value.source_entity_uuid = self.source_entity_uuid
                value.self_static.source_entity_uuid = self.source_entity_uuid
                value.to_target_static.source_entity_uuid = self.source_entity_uuid
                value.self_contextual.source_entity_uuid = self.source_entity_uuid
                value.to_target_contextual.source_entity_uuid = self.source_entity_uuid

    def _create_equipment_event(
        self,
        item: EquippableItem,
        slot: EquipmentSlot,
        *,
        equipping: bool,
        parent_event_uuid: Optional[UUID] = None,
        use_register: bool = True,
    ) -> EquipmentEvent:
        """Create the concrete public event associated with a gear transition."""
        common_fields = {
            "name": item.name,
            "source_entity_uuid": self.source_entity_uuid,
            "target_entity_uuid": self.target_entity_uuid,
            "item_uuid": item.uuid,
            "slot": slot,
            "parent_event": parent_event_uuid,
            "use_register": use_register,
        }
        event_type = item.equipment_event_type(equipping=equipping)
        event_class = _EQUIPMENT_EVENT_CLASS_BY_TYPE.get(event_type)
        if event_class is None:
            raise ValueError(f"Unsupported equipment event type: {event_type}")
        return event_class(**common_fields)

    def _preflight_equipment_transition(
        self,
        item: EquippableItem,
        slot: EquipmentSlot,
        *,
        equipping: bool,
        parent_event_uuid: Optional[UUID] = None,
    ) -> Optional[_PreparedEquipmentTransition]:
        """Run pure declaration/execution validators without publishing events."""
        declaration = self._create_equipment_event(
            item,
            slot,
            equipping=equipping,
            parent_event_uuid=parent_event_uuid,
            use_register=False,
        )
        declaration = EventQueue.preflight(declaration)
        if declaration.canceled:
            return None
        execution = EventQueue.preflight(declaration.phase_to(EventPhase.EXECUTION))
        if execution.canceled:
            return None

        for proposed in (declaration, execution):
            if (
                proposed.item_uuid != item.uuid
                or proposed.slot != slot
                or proposed.source_entity_uuid != self.source_entity_uuid
            ):
                raise RuntimeError(
                    "Equipment validators may cancel or annotate a transition, "
                    "but cannot replace its item, slot, or owner"
                )
        return _PreparedEquipmentTransition(
            slot=slot,
            item=item,
            equipping=equipping,
            declaration=declaration,
            execution=execution,
        )

    @staticmethod
    def _publish_prepared_transition(
        transition: _PreparedEquipmentTransition,
    ) -> _PreparedEquipmentTransition:
        """Publish accepted declaration/execution versions without redispatch."""
        declaration = EventQueue.publish_preflighted(transition.declaration)
        execution = EventQueue.publish_preflighted(transition.execution)
        return _PreparedEquipmentTransition(
            slot=transition.slot,
            item=transition.item,
            equipping=transition.equipping,
            declaration=declaration,
            execution=execution,
        )

    def equip_transaction(
        self,
        item: EquippableItem,
        slot: Optional[EquipmentSlot] = None,
    ) -> EquipmentEquipResult:
        """Atomically validate, displace conflicts, and equip one item.

        All execution-phase events are accepted before any slot or hook state is
        mutated.  This keeps canceled conflict removals from leaving a partially
        changed loadout.
        """
        selected_slot = self.resolve_equipment_slot(item, slot)
        conflicts = self._get_conflicts(item, selected_slot)

        prepared_equip = self._preflight_equipment_transition(
            item,
            selected_slot,
            equipping=True,
        )
        if prepared_equip is None:
            return EquipmentEquipResult(succeeded=False, selected_slot=selected_slot)

        prepared_unequips: List[_PreparedEquipmentTransition] = []
        for conflict_slot, current_item in conflicts:
            prepared_unequip = self._preflight_equipment_transition(
                current_item,
                conflict_slot,
                equipping=False,
            )
            if prepared_unequip is None:
                return EquipmentEquipResult(succeeded=False, selected_slot=selected_slot)
            prepared_unequips.append(prepared_unequip)

        published_unequips = [
            self._publish_prepared_transition(transition)
            for transition in prepared_unequips
        ]
        published_equip = self._publish_prepared_transition(prepared_equip)

        displaced_items: List[EquippableItem] = []
        for transition in published_unequips:
            transition.item.unequip(transition.slot, self.source_entity_uuid)
            setattr(self, _SLOT_ATTRIBUTE_BY_SLOT[transition.slot], None)
            if transition.item.uuid != item.uuid:
                displaced_items.append(transition.item)

        self._reparent_equippable_item(item)
        setattr(self, _SLOT_ATTRIBUTE_BY_SLOT[selected_slot], item)
        item.owner_uuid = self.source_entity_uuid
        item.stored_in_uuid = self.uuid
        item.equip(selected_slot, self.source_entity_uuid)
        if isinstance(selected_slot, WeaponSlot):
            self._reconcile_active_weapon_set(preferred_slot=selected_slot)

        for transition in published_unequips:
            transition.execution.phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
        published_equip.execution.phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
        return EquipmentEquipResult(
            succeeded=True,
            selected_slot=selected_slot,
            displaced_items=tuple(displaced_items),
        )

    def equip(
        self,
        item: EquippableItem,
        slot: Optional[EquipmentSlot] = None,
    ) -> bool:
        """Equip an item, preserving the historical boolean direct-call API."""
        return self.equip_transaction(item, slot).succeeded

    def unequip(self, slot: EquipmentSlot, parent_event_uuid: Optional[UUID] = None) -> Optional[EquippableItem]:
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
        attribute_name = _SLOT_ATTRIBUTE_BY_SLOT.get(slot)
        if attribute_name is None:
            raise ValueError(f"Invalid equipment slot: {slot}")

        current_item = getattr(self, attribute_name)
        if current_item is None:
            return None

        prepared = self._preflight_equipment_transition(
            current_item,
            slot,
            equipping=False,
            parent_event_uuid=parent_event_uuid,
        )
        if prepared is None:
            return None
        published = self._publish_prepared_transition(prepared)

        current_item.unequip(slot, self.source_entity_uuid)
        setattr(self, attribute_name, None)
        if isinstance(slot, WeaponSlot):
            self._reconcile_active_weapon_set(preferred_slot=slot)

        published.execution.phase_to(EventPhase.EFFECT).phase_to(EventPhase.COMPLETION)
        return current_item

    def group_equippable_items(
        self,
        items: Iterable[object],
    ) -> dict[str, list[dict[str, object]]]:
        """Group candidates with every item their footprint would displace."""
        result: dict[str, list[dict[str, object]]] = {}
        for item in items:
            if not isinstance(item, EquippableItem):
                continue
            for slot in item.compatible_equipment_slots():
                attribute_name = _SLOT_ATTRIBUTE_BY_SLOT.get(slot)
                if attribute_name is None:
                    continue
                conflicts = self._get_conflicts(item, slot)
                result.setdefault(attribute_name, []).append({
                    "item_uuid": str(item.uuid),
                    "item_name": item.name,
                    "displaced_items": [
                        {
                            "item_uuid": str(conflicting_item.uuid),
                            "item_name": conflicting_item.name,
                            "slot": conflicting_slot.value,
                        }
                        for conflicting_slot, conflicting_item in conflicts
                    ],
                })
        return result

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
