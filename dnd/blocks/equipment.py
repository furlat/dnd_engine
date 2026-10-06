from dnd.types.materials import Material
from dnd.core.attack_types import AttackSourceMetadata, NaturalWeaponSpec, WeaponAttackOverride
"""Equipment, armor, weapon, and shield models for entity combat gear."""

from dataclasses import dataclass
from typing import Callable, Iterable, Optional, List, Self, Literal, TypeVar, Union, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from dnd.core.values import ModifiableValue
from dnd.core.creature_types import DamageType
from dnd.core.base_object import BaseObject
from dnd.core.modifiers import NumericalModifier
from dnd.blocks.abilities import Ability, AbilityScores
from dnd.core.events import Event, EventQueue, EventType, EventPhase, Range, RangeType, Damage
from dnd.types.abilities import AbilityName
from dnd.core.equipment_types import (
    ArmorType,
    BodyPart,
    EquipmentSlot,
    RingSlot,
    UnarmoredAc,
    WeaponKind,
    WeaponUsage,
    WeaponProperty,
    WeaponSet,
    WeaponSlot,
)
from dnd.core.item_types import ItemEffectPresentationState, ItemPresentationKind, ItemPresentationState, ItemReleaseReason
from dnd.types.summoning import TerminalOwnerRelease

import copy

from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import get_map
from dnd.blocks.base_item import EquippableItem


class EquipmentEvent(Event):
    """Base event for equipment slot transitions."""

    name: str = Field(default="Equipment Event", description="An equipment event")
    slot: EquipmentSlot = Field(description="The slot being affected")
    item_uuid: UUID = Field(description="UUID of the item being transitioned")
    release_reason: ItemReleaseReason | None = None
    active_weapon_set_after: Optional[WeaponSet] = Field(
        default=None,
        description="Exact owner stance after the accepted equipment completion.",
    )


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

    def to_item_presentation_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemPresentationState:
        """Add armor-owned presentation facts to the common item payload."""
        state = super().to_item_presentation_state(stack_count=stack_count)
        return state.model_copy(update={
            "item_kind": ItemPresentationKind.ARMOR,
            "armor_type": self.type.value,
            "armor_ac": self.ac.score,
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

    def to_item_presentation_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemPresentationState:
        """Add shield-owned presentation facts to the common item payload."""
        state = super().to_item_presentation_state(stack_count=stack_count)
        return state.model_copy(update={
            "item_kind": ItemPresentationKind.SHIELD,
            "shield_ac_bonus": self.ac_bonus.score,
        })


class Weapon(EquippableItem):
    usage: WeaponUsage = WeaponUsage.HELD

    @property
    def is_body_attack(self) -> bool:
        """Explicit anatomy use, never inferred from the name or hand position."""
        return self.usage is WeaponUsage.BODY

    @model_validator(mode="after")
    def validate_body_usage(self) -> Self:
        if self.is_body_attack and (self.intrinsic_owner_uuid is None or "natural" not in self.tags):
            raise ValueError("Body attacks require explicitly owned intrinsic natural weapons")
        return self

    weapon_kind: WeaponKind | None = None
    material: Material | None = None
    attack_overrides: dict[UUID, WeaponAttackOverride] = Field(default_factory=dict)

    def attack_override(self, wielder_uuid: UUID) -> WeaponAttackOverride | None:
        return next((value for identity, value in self.attack_overrides.items()
            if value.wielder_uuid == wielder_uuid and (owner := BaseObject.get(identity)) is not None
            and owner.contributions_active()), None)

    def attack_damage_die(self, wielder_uuid: UUID):
        override = self.attack_override(wielder_uuid)
        return override.damage_die if override else self.damage_dice

    def attack_is_magical(self, wielder_uuid: UUID) -> bool:
        override = self.attack_override(wielder_uuid)
        return (self.is_magical and self.contributions_active()) or (override is not None and override.magical)

    def selected_attack_ability(self, abilities: AbilityScores, requested: AbilityName | None) -> AbilityName | None:
        override = self.attack_override(abilities.source_entity_uuid)
        if requested is not None or override is None:
            return requested
        candidate = abilities.get_ability(override.optional_ability)
        return override.optional_ability if candidate.modifier > abilities.strength.modifier else "strength"

    """Equippable weapon with attack, damage, range, and property metadata."""

    missile_size: Literal["ordinary", "large"] = Field(default="ordinary",
        description="Physical ranged missile category; large covers siege/giant projectiles.")
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
        if self.is_magical:
            for value in (self.attack_bonus, self.damage_bonus):
                modifier = value.get_base_modifier() if value is not None else None
                if modifier is not None:
                    modifier.contribution_owner_uuid = self.uuid
        return self

    def owned_values(self) -> tuple[ModifiableValue, ...]:
        return (*super().owned_values(), *self.extra_damage_bonus)

    def compatible_equipment_slots(self) -> Tuple[EquipmentSlot, ...]:
        """Return slots allowed by the weapon's ranged and light properties."""
        if self.is_body_attack:
            return (WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF)
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
        """Two-handed main weapons reserve both hands of their own loadout."""
        if WeaponProperty.TWO_HANDED in self.properties:
            if selected_slot == WeaponSlot.MELEE_MAIN:
                return frozenset((WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF))
            if selected_slot == WeaponSlot.RANGED_MAIN:
                return frozenset((WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF))
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

    def to_item_presentation_state(
        self,
        *,
        stack_count: Optional[int] = None,
    ) -> ItemPresentationState:
        """Add weapon-owned presentation facts to the common item payload."""
        state = super().to_item_presentation_state(stack_count=stack_count)
        owned = {effect.contribution_uuid for effect in state.item_effects}
        effects = (*state.item_effects, *(ItemEffectPresentationState(
            effect_uuid=bonus.uuid, contribution_uuid=bonus.uuid,
            behavior_id="item.property.additional_damage", damage_type=damage_type,
            display_name=bonus.name,
            suppression_provider_uuids=tuple(sorted(self.suppression_provider_uuids, key=str)) if self.is_magical else (),
        ) for bonus, damage_type in zip(self.extra_damage_bonus, self.extra_damage_type)
            if bonus.uuid not in owned))
        return state.model_copy(update={
            "item_kind": ItemPresentationKind.WEAPON,
            "damage_dice": f"{self.dice_numbers}d{self.damage_dice}",
            "damage_type": self.damage_type.value,
            "weapon_properties": tuple(prop.value for prop in self.properties),
            "item_effects": effects,
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

        is_off_hand = is_off_hand and not self.is_body_attack
        override_ability = self.selected_attack_ability(ability_block, override_ability)
        if override_ability is not None and not is_off_hand:
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
        return Damage(source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.target_entity_uuid, damage_dice=self.attack_damage_die(equipment_block.source_entity_uuid), dice_numbers=self.dice_numbers, damage_bonus=combined_bonuses, damage_type=self.damage_type)

    def get_extra_damages(self) -> List[Damage]:
        """Return extra damage payloads attached directly to this weapon."""
        damages = []
        if self.is_magical and not self.contributions_active():
            return damages
        for i in range(len(self.extra_damage_dices)):
            damages.append(Damage(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, damage_dice=self.extra_damage_dices[i], dice_numbers=self.extra_damage_dices_numbers[i], damage_bonus=self.extra_damage_bonus[i], damage_type=self.extra_damage_type[i]))
        return damages

    def get_all_weapon_damages(self, equipment_block: 'Equipment', ability_block: AbilityScores) -> List[Damage]:
        """Return primary plus extra weapon damage payloads."""
        damages = [self.get_base_damage(equipment_block, ability_block)]
        damages.extend(self.get_extra_damages())
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
    BodyPart.BACKPACK: "backpack",
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


@dataclass
class PreparedEquipmentRelease:
    """An admitted release of one exact slot, retaining ordinary unequip hooks."""

    owner: 'Equipment'
    transition: _PreparedEquipmentTransition
    reason: ItemReleaseReason
    committed: bool = False
    published: bool = False


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

    one_handed_offhand_grants: set[UUID] = Field(default_factory=set,
        description="Owned talent receipts installed before initial equipment admission.")
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
    one_handed_offhand_grants: set[UUID] = Field(
        default_factory=set,
        description="Actor-owned receipts permitting non-light one-handed melee weapons offhand.",
    )
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
    backpack: Optional[Armor] = Field(default=None, description="Backpack slot accessory")
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

    def owned_values(self) -> tuple[ModifiableValue, ...]:
        return (*super().owned_values(), *self.extra_attack_damage_bonus)

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
        *, magical_properties_active: bool = True,
    ) -> Ability:
        """Select the ability used by a weapon attack roll."""
        if weapon is not None and magical_properties_active:
            override_ability = weapon.selected_attack_ability(ability_block, override_ability)
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
        if weapon is not None:
            override_ability = weapon.selected_attack_ability(ability_block, override_ability)
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
        natural_weapon: Optional[NaturalWeaponSpec] = None,
    ) -> str:
        """Return the exact ability selected for one weapon attack."""
        return self._select_weapon_attack_ability(
            ability_block,
            None if natural_weapon else self.get_weapon(weapon_slot),
            override_ability,
        ).name

    def get_attack_bonus_components(
        self,
        ability_block: AbilityScores,
        weapon_slot: WeaponSlot,
        override_ability: Optional[AbilityName] = None,
        natural_weapon: Optional[NaturalWeaponSpec] = None,
    ) -> Tuple[ModifiableValue, List[ModifiableValue], List[ModifiableValue], Range]:
        """Return weapon, equipment, ability, and range attack components."""
        weapon = None if natural_weapon else self.get_weapon(weapon_slot)
        ability_bonuses: List[ModifiableValue] = []
        attack_bonuses = [self.attack_bonus]
        if weapon is None:
            weapon_bonus = self.unarmed_attack_bonus
            attack_bonuses.append(self.melee_attack_bonus)
            weapon_range = natural_weapon.range if natural_weapon else self.get_weapon_range(weapon_slot)
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
        natural_weapon: Optional[NaturalWeaponSpec] = None,
    ) -> Tuple[int, int]:
        """Return actor-side attack bonus and advantage contributions."""
        weapon = None if natural_weapon else self.get_weapon(weapon_slot)
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
            (natural_weapon.fixed_attack_bonus if natural_weapon is not None and natural_weapon.fixed_attack_bonus is not None
                else ability.modifier) + sum(component.normalized_score for component in components),
            ability.modifier_bonus.advantage_sum
            + sum(component.advantage_sum for component in components),
        )

    def get_weapon_damage_profiles(
        self,
        ability_block: AbilityScores,
        weapon_slot: WeaponSlot,
        profile_factory: Callable[..., DamageProfileT],
        override_ability: Optional[AbilityName] = None,
        natural_weapon: Optional[NaturalWeaponSpec] = None,
    ) -> List[DamageProfileT]:
        """Build damage formulas without importing the higher-level action DTO."""
        weapon = None if natural_weapon else self.get_weapon(weapon_slot)
        profiles: List[DamageProfileT] = []
        if weapon is not None:
            base_bonuses = [
                value
                for value in (weapon.damage_bonus, self.damage_bonus)
                if value is not None
            ]
            ability_bonus = 0
            if weapon_slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF) and not weapon.is_body_attack:
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
                die_size=weapon.attack_damage_die(self.source_entity_uuid),
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
                ) if not weapon.is_magical or weapon.contributions_active()
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
                dice_count=natural_weapon.dice_numbers if natural_weapon else self.unarmed_dice_numbers,
                die_size=natural_weapon.damage_dice if natural_weapon else self.unarmed_damage_dice,
                flat_bonus=(
                    sum(value.normalized_score for value in base_bonuses)
                    + (natural_weapon.fixed_damage_bonus if natural_weapon is not None and natural_weapon.fixed_damage_bonus is not None
                        else ability.modifier)
                ),
                damage_type=(natural_weapon.damage_type if natural_weapon else self.unarmed_damage_type).value,
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

    def snapshot_attack_source_metadata(self, slot: WeaponSlot) -> AttackSourceMetadata:
        """Retain the same selected source identity for discovery and execution."""
        name, damage_types = self.snapshot_attack_event_metadata(slot)
        weapon = self.get_weapon(slot)
        return AttackSourceMetadata(kind="equipped" if weapon else "unarmed",
            weapon_slot=slot, name=name, damage_types=damage_types,
            item_uuid=weapon.uuid if weapon else None, magical=weapon.attack_is_magical(self.source_entity_uuid) if weapon else False)

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

    def prepare_item_release(self, item_uuid: UUID, *, parent_event: Event | None = None,
                             reason: ItemReleaseReason = ItemReleaseReason.OWNER_DEPARTED,
                             terminal_release: TerminalOwnerRelease | None = None
                             ) -> PreparedEquipmentRelease | None:
        """Admit a retirement release without mutating the slot or item."""
        if terminal_release is not None and terminal_release.entity_uuid != self.source_entity_uuid:
            raise ValueError("Terminal release belongs to another equipment owner")
        for slot in _SLOT_ATTRIBUTE_BY_SLOT:
            item = self.get_item_by_slot(slot)
            if item is None or item.uuid != item_uuid:
                continue
            if item.intrinsic_owner_uuid is not None and (
                    terminal_release is None or item.intrinsic_owner_uuid != terminal_release.entity_uuid):
                return None
            declaration = self._create_equipment_event(item, slot, equipping=False,
                parent_event_uuid=parent_event.uuid if parent_event is not None else None,
                use_register=False)
            declaration.release_reason = reason
            mandatory = terminal_release is not None and terminal_release.mandatory
            if not mandatory:
                declaration = EventQueue.preflight(declaration)
                if declaration.canceled:
                    return None
            execution = declaration.phase_to(EventPhase.EXECUTION)
            if not mandatory:
                execution = EventQueue.preflight(execution)
                if execution.canceled:
                    return None
            for event in (declaration, execution):
                if (event.item_uuid != item.uuid or event.slot != slot
                        or event.source_entity_uuid != self.source_entity_uuid):
                    raise RuntimeError("Release admission cannot replace owner, item or slot")
            return PreparedEquipmentRelease(self,
                _PreparedEquipmentTransition(slot, item, False, declaration, execution), reason)
        return None

    def validate_item_release(self, prepared: PreparedEquipmentRelease) -> bool:
        """The admitted item must still occupy this exact owner and slot."""
        transition = prepared.transition
        return (prepared.owner is self
                and self.get_item_by_slot(transition.slot) is transition.item
                and transition.item.owner_uuid == self.source_entity_uuid
                and transition.item.stored_in_uuid == self.uuid)

    def commit_item_release(self, prepared: PreparedEquipmentRelease) -> None:
        """Run the item's ordinary unequip hook exactly once before releasing its slot."""
        if prepared.owner is not self:
            raise ValueError("Equipment release token belongs to another owner")
        if prepared.committed:
            return
        transition = prepared.transition
        if not self.validate_item_release(prepared):
            raise RuntimeError("Admitted equipment release changed before commitment")
        transition.item.unequip(transition.slot, self.source_entity_uuid)
        setattr(self, _SLOT_ATTRIBUTE_BY_SLOT[transition.slot], None)
        if isinstance(transition.slot, WeaponSlot):
            self._reconcile_active_weapon_set()
        prepared.committed = True

    def publish_item_release(self, prepared: PreparedEquipmentRelease) -> None:
        if prepared.owner is not self or not prepared.committed:
            raise ValueError("Equipment release must commit before publication")
        if prepared.published:
            return
        prepared.published = True
        transition = self._publish_prepared_transition(prepared.transition)
        transition.execution.phase_to(EventPhase.EFFECT,
            status_message=f"Equipment released: {prepared.reason.value}").phase_to(
                EventPhase.COMPLETION, active_weapon_set_after=self.active_weapon_set)

    def remove_contained_item(self, item_uuid: UUID, *, parent_event: Event | None = None,
                              reason: ItemReleaseReason = ItemReleaseReason.TRANSFERRED) -> bool:
        """Release an already-committed transfer/retirement through unequip hooks."""
        for slot in _SLOT_ATTRIBUTE_BY_SLOT:
            item = self.get_item_by_slot(slot)
            if item is None or item.uuid != item_uuid:
                continue
            declaration = self._create_equipment_event(item, slot, equipping=False,
                parent_event_uuid=parent_event.uuid if parent_event is not None else None,
                use_register=False)
            declaration.release_reason = reason
            token = PreparedEquipmentRelease(self, _PreparedEquipmentTransition(
                slot, item, False, declaration, declaration.phase_to(EventPhase.EXECUTION)), reason)
            self.commit_item_release(token)
            self.publish_item_release(token)
            return True
        return False

    def is_unarmed(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> bool:
        """Return whether the slot attacks as unarmed."""
        weapon = self._get_weapon_by_slot(weapon_slot)
        return weapon is None or isinstance(weapon, Shield)

    def is_ranged(self, weapon_slot: WeaponSlot) -> bool:
        """Ranged slots are always ranged, melee slots are never ranged."""
        return weapon_slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF)

    def _get_main_unarmed_damage(self, ability_block: AbilityScores, override_ability: Optional[AbilityName] = None, natural_weapon: Optional[NaturalWeaponSpec] = None) -> Damage:
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
        if natural_weapon is not None and natural_weapon.fixed_damage_bonus is not None:
            ability_bonus = ModifiableValue.create(source_entity_uuid=self.source_entity_uuid,
                value_name="Intrinsic damage bonus",base_value=natural_weapon.fixed_damage_bonus)
        combined_bonus = unarmed_damage_bonus.combine_values([self.damage_bonus,self.melee_damage_bonus, ability_bonus])
        combined_bonus.set_context({
            "attack_ability": ability.name,
            "range_type": RangeType.REACH.value,
        })
        unarmed_damage = Damage(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=self.target_entity_uuid, damage_dice=natural_weapon.damage_dice if natural_weapon else self.unarmed_damage_dice, dice_numbers=natural_weapon.dice_numbers if natural_weapon else self.unarmed_dice_numbers, damage_bonus=combined_bonus, damage_type=natural_weapon.damage_type if natural_weapon else self.unarmed_damage_type)
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

    def get_damages(self, weapon_slot: WeaponSlot, ability_block: AbilityScores, override_ability: Optional[AbilityName] = None, natural_weapon: Optional[NaturalWeaponSpec] = None) -> List[Damage]:
        """Return all damage payloads for an attack from a weapon slot."""
        if natural_weapon or self.is_unarmed(weapon_slot):
            return [self._get_main_unarmed_damage(ability_block, override_ability=override_ability, natural_weapon=natural_weapon)]+self.get_extra_attack_damage()
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
                "dexterity",
                "constitution",
            )
        elif self.unarmored_ac_type == UnarmoredAc.MONK:
            abilities = ("dexterity", "strength")
        else:
            abilities = ("dexterity",)
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
            return ["dexterity", "constitution"]
        elif self.unarmored_ac_type == UnarmoredAc.MONK:
            return ["dexterity", "strength"]
        else:
            return["dexterity"]

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

    def compatible_slots_for_actor(self, item: EquippableItem) -> Tuple[EquipmentSlot, ...]:
        """Combine an item's unchanged baseline with this actor's hand capability."""
        slots = item.compatible_equipment_slots()
        if (self.one_handed_offhand_grants
                and WeaponSlot.MELEE_MAIN in slots
                and WeaponSlot.MELEE_OFF not in slots
                and item.occupied_equipment_slots(WeaponSlot.MELEE_MAIN)
                    == frozenset((WeaponSlot.MELEE_MAIN,))):
            return (*slots, WeaponSlot.MELEE_OFF)
        return slots

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
        if selected_slot not in self.compatible_slots_for_actor(item):
            raise ValueError(item.incompatible_equipment_slot_message(selected_slot))
        return selected_slot

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

    def validate_initial_items(
        self,
        items: Iterable[Tuple[EquippableItem, Optional[EquipmentSlot]]],
    ) -> Tuple[Tuple[EquippableItem, EquipmentSlot], ...]:
        """Resolve and validate a complete unpublished equipment loadout."""
        occupied: dict[EquipmentSlot, UUID] = {}
        seen_existing: set[UUID] = set()
        for slot in _SLOT_ATTRIBUTE_BY_SLOT:
            current = self.get_item_by_slot(slot)
            if current is None or current.uuid in seen_existing:
                continue
            seen_existing.add(current.uuid)
            for footprint_slot in current.occupied_equipment_slots(slot):
                occupied[footprint_slot] = current.uuid

        resolved: list[Tuple[EquippableItem, EquipmentSlot]] = []
        seen_new: set[UUID] = set()
        for item, requested_slot in items:
            if item.uuid in seen_new or item.uuid in seen_existing:
                raise ValueError(f"duplicate initial equipment UUID {item.uuid}")
            seen_new.add(item.uuid)
            if item.intrinsic_owner_uuid not in (None, self.source_entity_uuid):
                raise ValueError("Intrinsic anatomy belongs to another entity")
            if item.source_entity_uuid != self.source_entity_uuid:
                raise ValueError(
                    f"initial equipment {item.item_id} belongs to another entity",
                )
            if (
                item.owner_uuid is not None
                or item.stored_in_uuid is not None
                or item.tile_uuid is not None
                or item.is_equipped
                or item.equipped_slot is not None
            ):
                raise ValueError(
                    f"initial equipment {item.item_id} is already placed",
                )
            selected_slot = self.resolve_equipment_slot(item, requested_slot)
            footprint = item.occupied_equipment_slots(selected_slot)
            conflicts = footprint & occupied.keys()
            if conflicts:
                conflict = min(conflicts, key=lambda candidate: candidate.value)
                raise ValueError(
                    f"initial equipment collision in {conflict.value}",
                )
            for footprint_slot in footprint:
                occupied[footprint_slot] = item.uuid
            resolved.append((item, selected_slot))
        return tuple(resolved)

    def _commit_equipped_item(
        self,
        item: EquippableItem,
        selected_slot: EquipmentSlot,
    ) -> None:
        """Commit one already-validated item through equipment-owned hooks."""
        previous_owner_uuid = item.owner_uuid
        previous_container_uuid = item.stored_in_uuid
        if item.stored_in_uuid is not None and item.stored_in_uuid != self.uuid:
            previous_container = BaseBlock.get(item.stored_in_uuid)
            if previous_container is not None:
                previous_container.remove_contained_item(item.uuid)
        self._reparent_equippable_item(item)
        setattr(self, _SLOT_ATTRIBUTE_BY_SLOT[selected_slot], item)
        item.owner_uuid = self.source_entity_uuid
        item.stored_in_uuid = self.uuid
        item.equip(selected_slot, self.source_entity_uuid)
        if isinstance(selected_slot, WeaponSlot):
            self._reconcile_active_weapon_set(preferred_slot=selected_slot)
        if (previous_owner_uuid is not None and previous_container_uuid is not None
                and previous_owner_uuid != self.source_entity_uuid):
            item.publish_holdings_release(previous_owner_uuid, previous_container_uuid)

    def install_initial_items(
        self,
        items: Iterable[Tuple[EquippableItem, Optional[EquipmentSlot]]],
    ) -> None:
        """Install initial equipment through ordinary hooks without Events."""
        resolved = self.validate_initial_items(items)
        for item, selected_slot in resolved:
            self._commit_equipped_item(item, selected_slot)

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
        if equipping and item.is_equipped and item.stored_in_uuid != self.uuid:
            return None
        if item.intrinsic_owner_uuid is not None and (
            not equipping or item.intrinsic_owner_uuid != self.source_entity_uuid
        ):
            return None
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
        *,
        admit_displacements: Optional[Callable[[Tuple[EquippableItem, ...]], bool]] = None,
        commit_displacements: Optional[Callable[[], None]] = None,
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

        displaced = tuple(transition.item for transition in prepared_unequips
                          if transition.item.uuid != item.uuid)
        grid = get_map()
        floor_removals = None
        if grid.get_object_position(item.uuid) is not None:
            floor_removals = grid.prepare_object_removals((item.uuid,))
            if floor_removals is None:
                return EquipmentEquipResult(succeeded=False, selected_slot=selected_slot)
        if admit_displacements is not None and not admit_displacements(displaced):
            if floor_removals is not None:
                grid.cancel_object_removals(floor_removals, "Equipment destination rejected")
            return EquipmentEquipResult(succeeded=False, selected_slot=selected_slot)
        if any(self.get_item_by_slot(conflict_slot) is not current
               for conflict_slot, current in conflicts):
            if floor_removals is not None:
                grid.cancel_object_removals(floor_removals, "Equipment changed during admission")
            return EquipmentEquipResult(succeeded=False, selected_slot=selected_slot)

        if floor_removals is not None and any(
            grid.get_object_placement(obj.uuid) != previous or BaseBlock.get(obj.uuid) is not obj
            for obj, previous, _ in floor_removals
        ):
            grid.cancel_object_removals(floor_removals, "Incoming floor item changed during destination admission")
            return EquipmentEquipResult(succeeded=False, selected_slot=selected_slot)

        if floor_removals is not None:
            grid.commit_object_removals(floor_removals)

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

        self._commit_equipped_item(item, selected_slot)
        if commit_displacements is not None:
            commit_displacements()

        for transition in published_unequips:
            transition.execution.phase_to(EventPhase.EFFECT).phase_to(
                EventPhase.COMPLETION, active_weapon_set_after=self.active_weapon_set,
            )
        published_equip.execution.phase_to(EventPhase.EFFECT).phase_to(
            EventPhase.COMPLETION, active_weapon_set_after=self.active_weapon_set,
        )
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

    def unequip(
        self, slot: EquipmentSlot, parent_event_uuid: Optional[UUID] = None, *,
        admit_destination: Optional[Callable[[EquippableItem], bool]] = None,
        commit_destination: Optional[Callable[[], None]] = None,
    ) -> Optional[EquippableItem]:
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
        if admit_destination is not None and not admit_destination(current_item):
            return None
        if self.get_item_by_slot(slot) is not current_item:
            return None
        published = self._publish_prepared_transition(prepared)

        current_item.unequip(slot, self.source_entity_uuid)
        setattr(self, attribute_name, None)
        if isinstance(slot, WeaponSlot):
            self._reconcile_active_weapon_set(preferred_slot=slot)

        if commit_destination is not None:
            commit_destination()

        published.execution.phase_to(EventPhase.EFFECT).phase_to(
            EventPhase.COMPLETION, active_weapon_set_after=self.active_weapon_set,
        )
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
            for slot in self.compatible_slots_for_actor(item):
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
                       one_handed_offhand_grants=set(config.one_handed_offhand_grants),
                       unarmored_ac=unarmored_ac, ac_bonus=ac_bonus,unarmored_ac_type=config.unarmored_ac_type, damage_bonus=damage_bonus, attack_bonus=attack_bonus, melee_attack_bonus=melee_attack_bonus, ranged_attack_bonus=ranged_attack_bonus,
                       melee_damage_bonus=melee_damage_bonus, ranged_damage_bonus=ranged_damage_bonus, unarmed_attack_bonus=unarmed_attack_bonus, unarmed_damage_bonus=unarmed_damage_bonus)
