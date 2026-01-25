"""Weapon factory functions for D&D 5e weapons."""

from uuid import UUID
from dnd.blocks.equipment import Weapon, WeaponProperty, Range
from dnd.core.modifiers import DamageType
from dnd.core.values import ModifiableValue
from dnd.core.events import RangeType


# =============================================================================
# SIMPLE MELEE WEAPONS
# =============================================================================

def create_club(source_id: UUID) -> Weapon:
    """Club - 1d4 bludgeoning, light"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Club",
        description="A simple wooden club.",
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_dagger(source_id: UUID) -> Weapon:
    """Dagger - 1d4 piercing, finesse, light, thrown (20/60)"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Dagger",
        description="A simple blade for quick strikes.",
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT, WeaponProperty.THROWN],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_handaxe(source_id: UUID) -> Weapon:
    """Handaxe - 1d6 slashing, light, thrown (20/60)"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Handaxe",
        description="A small axe that can be thrown.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.LIGHT, WeaponProperty.THROWN],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_javelin(source_id: UUID) -> Weapon:
    """Javelin - 1d6 piercing, thrown (30/120)"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Javelin",
        description="A light spear designed for throwing.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.THROWN],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_mace(source_id: UUID) -> Weapon:
    """Mace - 1d6 bludgeoning"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Mace",
        description="A heavy headed club.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_quarterstaff(source_id: UUID) -> Weapon:
    """Quarterstaff - 1d6 bludgeoning, versatile (1d8)"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Quarterstaff",
        description="A wooden staff used as a weapon.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_spear(source_id: UUID) -> Weapon:
    """Spear - 1d6 piercing, thrown (20/60), versatile (1d8)"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Spear",
        description="A pole weapon with a pointed tip.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.THROWN, WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


# =============================================================================
# SIMPLE RANGED WEAPONS
# =============================================================================

def create_light_crossbow(source_id: UUID) -> Weapon:
    """Light crossbow - 1d8 piercing, ammunition (80/320), loading, two-handed"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Light Crossbow",
        description="A mechanical bow that fires bolts.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.RANGED, WeaponProperty.TWO_HANDED],
        range=Range(type=RangeType.RANGE, normal=80, long=320),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_shortbow(source_id: UUID) -> Weapon:
    """Shortbow - 1d6 piercing, ammunition (80/320), two-handed"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Shortbow",
        description="A small bow suitable for quick shots.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.RANGED, WeaponProperty.TWO_HANDED],
        range=Range(type=RangeType.RANGE, normal=80, long=320),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


# =============================================================================
# MARTIAL MELEE WEAPONS
# =============================================================================

def create_battleaxe(source_id: UUID) -> Weapon:
    """Battleaxe - 1d8 slashing, versatile (1d10)"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Battleaxe",
        description="A large axe suitable for battle.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.VERSATILE, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_greatsword(source_id: UUID) -> Weapon:
    """Greatsword - 2d6 slashing, heavy, two-handed"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Greatsword",
        description="A massive two-handed sword.",
        damage_dice=6,
        dice_numbers=2,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.HEAVY, WeaponProperty.TWO_HANDED, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_longsword(source_id: UUID) -> Weapon:
    """Longsword - 1d8 slashing, versatile (1d10)"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Longsword",
        description="A versatile one-handed sword.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.VERSATILE, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_rapier(source_id: UUID) -> Weapon:
    """Rapier - 1d8 piercing, finesse"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Rapier",
        description="A slender thrusting sword.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_scimitar(source_id: UUID) -> Weapon:
    """Scimitar - 1d6 slashing, finesse, light"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Scimitar",
        description="A curved slashing sword favored by goblins.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_shortsword(source_id: UUID) -> Weapon:
    """Shortsword - 1d6 piercing, finesse, light"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Shortsword",
        description="A short blade suitable for quick strikes.",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_warhammer(source_id: UUID) -> Weapon:
    """Warhammer - 1d8 bludgeoning, versatile (1d10)"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Warhammer",
        description="A heavy hammer designed for combat.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.VERSATILE, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


# =============================================================================
# MARTIAL RANGED WEAPONS
# =============================================================================

def create_longbow(source_id: UUID) -> Weapon:
    """Longbow - 1d8 piercing, ammunition (150/600), heavy, two-handed"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Longbow",
        description="A tall bow capable of long-range shots.",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.RANGED, WeaponProperty.TWO_HANDED, WeaponProperty.HEAVY, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.RANGE, normal=150, long=600),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )


def create_heavy_crossbow(source_id: UUID) -> Weapon:
    """Heavy crossbow - 1d10 piercing, ammunition (100/400), heavy, loading, two-handed"""
    return Weapon(
        source_entity_uuid=source_id,
        name="Heavy Crossbow",
        description="A powerful mechanical crossbow.",
        damage_dice=10,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.RANGED, WeaponProperty.TWO_HANDED, WeaponProperty.HEAVY, WeaponProperty.MARTIAL],
        range=Range(type=RangeType.RANGE, normal=100, long=400),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[]
    )
