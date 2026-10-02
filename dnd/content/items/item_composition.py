"""Pure creation-time transformations over immutable authored definitions."""
from dataclasses import replace
from typing import TypeVar

from dnd.content.items.authored_item_definitions import WeaponDefinition, WearableDefinition
from dnd.core.content.identities import validate_namespaced_id
from dnd.core.item_properties import AdditionalDamage, ArmorPenalties, UnseenStrike, WearerBonus, WearerValue

Definition = TypeVar("Definition", WeaponDefinition, WearableDefinition)


def named_item(definition: Definition, *, item_id: str, name: str) -> Definition:
    validate_namespaced_id(item_id, "item_id")
    return replace(definition, item_id=item_id, name=name)


def with_weapon_bonus(definition: WeaponDefinition, *, bonus: int) -> WeaponDefinition:
    """Replace the authored attack/damage enhancement; repeated calls do not add."""
    return replace(definition, attack_bonus=bonus, damage_bonus=bonus)


def with_extra_damage(definition: WeaponDefinition, *, packet: AdditionalDamage) -> WeaponDefinition:
    """Append a distinct damage packet, rejecting accidental duplicate composition."""
    existing = definition.additional_damage
    if definition.extra_damage_die is not None and definition.extra_damage_type is not None:
        existing = (AdditionalDamage(definition.extra_damage_die,
            definition.extra_damage_dice_count, definition.extra_damage_type), *existing)
    if packet in existing:
        raise ValueError("Duplicate additional damage property")
    return replace(definition, additional_damage=(*definition.additional_damage, packet))


def with_wearer_bonus(definition: Definition, *, target: WearerValue, bonus: int, name: str) -> Definition:
    properties = tuple(property for property in definition.item_properties
        if not (isinstance(property, WearerBonus) and property.target is target))
    return replace(definition, item_properties=(*properties, WearerBonus(target, bonus, name)))


def with_unseen_strike(definition: WeaponDefinition, *, property: UnseenStrike = UnseenStrike()) -> WeaponDefinition:
    properties = tuple(value for value in definition.item_properties if not isinstance(value, UnseenStrike))
    return replace(definition, item_properties=(*properties, property))


def with_armor_penalties(definition: WearableDefinition, *, stealth_disadvantage: bool,
                         strength_requirement: int | None = None) -> WearableDefinition:
    properties = tuple(value for value in definition.item_properties if not isinstance(value, ArmorPenalties))
    return replace(definition, stealth_disadvantage=stealth_disadvantage,
        strength_requirement=strength_requirement,
        item_properties=(*properties, ArmorPenalties(stealth_disadvantage, strength_requirement)))
