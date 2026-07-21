"""SRD-derived monster and NPC roster for validation play.

The factories in this module prioritize mechanically useful SRD coverage for
AI evaluation. Each creature preserves the SRD stat identity that the current
engine can represent directly: ability scores, hit dice, armor, movement,
creature type, senses, weapons, basic spellcasting, and condition immunities.
Special traits that require dedicated handlers are recorded in metadata instead
of being silently approximated as different behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from dnd.actions_functional import register_spells_by_name, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.base_item import EquippedVisualPolicy
from dnd.blocks.equipment import BodyArmor, Weapon, WeaponSlot, ArmorType, Range, WeaponProperty
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.skills import SkillConfig, SkillSetConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.base_block import SenseMode, SensesType
from dnd.core.events import AbilityName, BodyPart, RangeType
from dnd.core.modifiers import CreatureType, DamageType, Size
from dnd.core.values import ModifiableValue
from dnd.entity import Entity, EntityConfig
from dnd.items import (
    create_chain_mail,
    create_chain_shirt,
    create_club,
    create_dagger,
    create_greataxe,
    create_greatsword,
    create_heavy_crossbow,
    create_hide_armor,
    create_leather_armor,
    create_light_crossbow,
    create_longbow,
    create_longsword,
    create_mace,
    create_plate_armor,
    create_scimitar,
    create_shield,
    create_shortsword,
    create_spear,
    create_splint_armor,
    create_studded_leather,
)
from dnd.monsters.traits import (
    register_aggressive,
    register_bite_prone_rider,
    register_brave,
    register_brute,
    register_cunning_action,
    register_dark_devotion,
    register_divine_eminence,
    register_ghoul_claws_paralysis,
    register_keen_perception,
    register_leadership,
    register_martial_advantage,
    register_multiattack,
    register_natural_bite,
    register_pack_tactics,
    register_parry,
    register_rampage,
    register_reckless,
    register_sneak_attack,
    register_sunlight_sensitivity,
    register_surprise_attack,
    register_undead_fortitude,
)
from dnd.spells.abjuration import register_counterspell_reaction, register_shield_reaction


MonsterFactory = Callable[[Optional[UUID], str, tuple[int, int], Optional[str]], Entity]
HitDieValue = Literal[4, 6, 8, 10, 12]
WeaponDieValue = Literal[4, 6, 8, 10, 12, 20]


_VISUAL_SCALE_BY_SIZE: dict[Size, float] = {
    Size.TINY: 0.68,
    Size.SMALL: 0.82,
    Size.MEDIUM: 1.0,
    Size.LARGE: 1.28,
    Size.HUGE: 1.55,
    Size.GARGANTUAN: 2.0,
}


class SrdMonsterSpec(BaseModel):
    """Stable metadata for one SRD-derived creature factory."""

    monster_id: str = Field(description="Stable snake-case monster identifier.")
    display_name: str = Field(description="SRD display name.")
    challenge_rating: str = Field(description="SRD challenge rating text.")
    source_path: str = Field(description="Local markdown source used for the stat identity.")
    role_tags: tuple[str, ...] = Field(description="AI evaluation role tags.")
    represented_traits: tuple[str, ...] = Field(
        default_factory=tuple,
        description="SRD traits implemented directly by current engine mechanics.",
    )
    pending_traits: tuple[str, ...] = Field(
        default_factory=tuple,
        description="SRD traits intentionally not approximated yet.",
    )


def create_commoner(
    source_id: Optional[UUID] = None,
    name: str = "Commoner",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Commoner."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A noncombatant pressed into danger.",
        position=position,
        faction=faction,
        abilities=(10, 10, 10, 10, 10, 10),
        hit_die_value=8,
        hit_die_count=1,
        proficiency_bonus=2,
    )
    _equip(entity, melee=create_club(entity.uuid))
    return entity


def create_bandit(
    source_id: Optional[UUID] = None,
    name: str = "Bandit",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Bandit."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A lightly armored raider with melee and crossbow pressure.",
        position=position,
        faction=faction,
        abilities=(11, 12, 12, 10, 10, 10),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
    )
    _equip(entity, armor=create_leather_armor(entity.uuid), melee=create_scimitar(entity.uuid), ranged=create_light_crossbow(entity.uuid))
    return entity


def create_cultist(
    source_id: Optional[UUID] = None,
    name: str = "Cultist",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Cultist."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A zealot with a scimitar and social skill pressure.",
        position=position,
        faction=faction,
        abilities=(11, 12, 10, 10, 11, 10),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        skills={"deception": True, "religion": True},
    )
    _equip(entity, armor=create_leather_armor(entity.uuid), melee=create_scimitar(entity.uuid))
    register_dark_devotion(entity)
    return entity


def create_guard(
    source_id: Optional[UUID] = None,
    name: str = "Guard",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Guard."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A defensive sentry with shielded spear pressure.",
        position=position,
        faction=faction,
        abilities=(13, 12, 12, 10, 11, 10),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        skills={"perception": True},
    )
    _equip(entity, armor=create_chain_shirt(entity.uuid), melee=create_spear(entity.uuid), shield=True)
    return entity


def create_tribal_warrior(
    source_id: Optional[UUID] = None,
    name: str = "Tribal Warrior",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Tribal Warrior."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A light skirmisher that pressures pack-melee scenarios.",
        position=position,
        faction=faction,
        abilities=(13, 11, 12, 8, 11, 8),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
    )
    _equip(entity, armor=create_hide_armor(entity.uuid), melee=create_spear(entity.uuid))
    register_pack_tactics(entity)
    return entity


def create_kobold(
    source_id: Optional[UUID] = None,
    name: str = "Kobold",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Kobold."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A fragile darkvision skirmisher.",
        position=position,
        faction=faction,
        abilities=(7, 15, 9, 8, 7, 8),
        hit_die_value=6,
        hit_die_count=2,
        proficiency_bonus=2,
        size=Size.SMALL,
        weight=35,
        darkvision=True,
    )
    _equip(entity, melee=create_dagger(entity.uuid), ranged=_simple_weapon(entity.uuid, "Sling", 4, 1, DamageType.BLUDGEONING, RangeType.RANGE, 30, 120, (WeaponProperty.RANGED,), visual_item_name="Sling"))
    register_pack_tactics(entity)
    register_sunlight_sensitivity(entity)
    return entity


def create_acolyte(
    source_id: Optional[UUID] = None,
    name: str = "Acolyte",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Acolyte-style low priest."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A junior divine caster useful for low-CR support tests.",
        position=position,
        faction=faction,
        abilities=(10, 10, 10, 10, 14, 11),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        spellcasting_ability="wisdom",
        spell_slots={1: 3},
        skills={"medicine": True, "religion": True},
    )
    register_spells_by_name(entity, ["Sacred Flame", "Bless", "Cure Wounds"], caster_level=1)
    _equip(entity, melee=create_club(entity.uuid))
    return entity


def create_scout(
    source_id: Optional[UUID] = None,
    name: str = "Scout",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Scout."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A perception-heavy ranged scout.",
        position=position,
        faction=faction,
        abilities=(11, 14, 12, 11, 13, 11),
        hit_die_value=8,
        hit_die_count=3,
        proficiency_bonus=2,
        skills={"nature": True, "perception": True, "stealth": True, "survival": True},
    )
    _equip(entity, armor=create_leather_armor(entity.uuid), melee=create_shortsword(entity.uuid), ranged=create_longbow(entity.uuid))
    register_keen_perception(entity, name="Keen Hearing and Sight", modes=("hearing", "sight"))
    register_multiattack(entity, "Scout Multiattack: Shortsword", ((WeaponSlot.MELEE_MAIN, 2),))
    register_multiattack(entity, "Scout Multiattack: Longbow", ((WeaponSlot.RANGED_MAIN, 2),))
    return entity


def create_thug(
    source_id: Optional[UUID] = None,
    name: str = "Thug",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Thug."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A durable low-CR bruiser with crossbow fallback.",
        position=position,
        faction=faction,
        abilities=(15, 11, 14, 10, 10, 11),
        hit_die_value=8,
        hit_die_count=5,
        proficiency_bonus=2,
        skills={"intimidation": True},
    )
    _equip(entity, armor=create_leather_armor(entity.uuid), melee=create_mace(entity.uuid), ranged=create_heavy_crossbow(entity.uuid))
    register_pack_tactics(entity)
    register_multiattack(entity, "Thug Multiattack", ((WeaponSlot.MELEE_MAIN, 2),))
    return entity


def create_spy(
    source_id: Optional[UUID] = None,
    name: str = "Spy",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Spy."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A mobile infiltrator with shortsword and hand-crossbow pressure.",
        position=position,
        faction=faction,
        abilities=(10, 15, 10, 12, 14, 16),
        hit_die_value=8,
        hit_die_count=6,
        proficiency_bonus=2,
        skills={"deception": True, "insight": True, "investigation": True, "perception": True, "persuasion": True, "sleight_of_hand": True, "stealth": True},
    )
    _equip(entity, melee=create_shortsword(entity.uuid), ranged=_simple_weapon(entity.uuid, "Hand Crossbow", 6, 1, DamageType.PIERCING, RangeType.RANGE, 30, 120, (WeaponProperty.RANGED,), visual_item_name="Light Crossbow"))
    register_cunning_action(entity)
    register_sneak_attack(entity)
    register_multiattack(entity, "Spy Multiattack", ((WeaponSlot.MELEE_MAIN, 2),))
    return entity


def create_berserker(
    source_id: Optional[UUID] = None,
    name: str = "Berserker",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Berserker."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A high-HP axe charger for melee pressure tests.",
        position=position,
        faction=faction,
        abilities=(16, 12, 17, 9, 11, 9),
        hit_die_value=8,
        hit_die_count=9,
        proficiency_bonus=2,
    )
    _equip(entity, armor=create_hide_armor(entity.uuid), melee=create_greataxe(entity.uuid))
    register_reckless(entity)
    return entity


def create_bandit_captain(
    source_id: Optional[UUID] = None,
    name: str = "Bandit Captain",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Bandit Captain."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A durable duelist leader with melee and thrown-dagger pressure.",
        position=position,
        faction=faction,
        abilities=(15, 16, 14, 14, 11, 14),
        hit_die_value=8,
        hit_die_count=10,
        proficiency_bonus=2,
        skills={"athletics": True, "deception": True},
    )
    _equip(
        entity,
        armor=create_studded_leather(entity.uuid),
        melee=create_scimitar(entity.uuid),
        offhand=create_dagger(entity.uuid),
        ranged=_simple_weapon(entity.uuid, "Thrown Dagger", 4, 1, DamageType.PIERCING, RangeType.RANGE, 20, 60, (WeaponProperty.RANGED,), visual_item_name="Dagger"),
    )
    register_multiattack(entity, "Bandit Captain Multiattack: Melee", ((WeaponSlot.MELEE_MAIN, 2), (WeaponSlot.MELEE_OFF, 1)))
    register_multiattack(entity, "Bandit Captain Multiattack: Ranged", ((WeaponSlot.RANGED_MAIN, 2),))
    register_parry(entity)
    return entity


def create_priest(
    source_id: Optional[UUID] = None,
    name: str = "Priest",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Priest."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A divine support caster with healing, radiant pressure, and aura options.",
        position=position,
        faction=faction,
        abilities=(10, 10, 12, 13, 16, 13),
        hit_die_value=8,
        hit_die_count=5,
        proficiency_bonus=2,
        spellcasting_ability="wisdom",
        spell_slots={1: 4, 2: 3, 3: 2},
        skills={"medicine": True, "persuasion": True, "religion": True},
    )
    register_spells_by_name(entity, ["Sacred Flame", "Cure Wounds", "Guiding Bolt", "Sanctuary", "Lesser Restoration", "Spirit Guardians"], caster_level=5)
    _equip(entity, armor=create_chain_shirt(entity.uuid), melee=create_mace(entity.uuid))
    register_divine_eminence(entity)
    return entity


def create_cult_fanatic(
    source_id: Optional[UUID] = None,
    name: str = "Cult Fanatic",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Cult Fanatic."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A low-mid control caster with dagger fallback.",
        position=position,
        faction=faction,
        abilities=(11, 14, 12, 10, 13, 14),
        hit_die_value=8,
        hit_die_count=6,
        proficiency_bonus=2,
        spellcasting_ability="wisdom",
        spell_slots={1: 4, 2: 3},
        skills={"deception": True, "persuasion": True, "religion": True},
    )
    register_spells_by_name(entity, ["Sacred Flame", "Command", "Inflict Wounds", "Shield of Faith", "Hold Person"], caster_level=4)
    _equip(entity, armor=create_leather_armor(entity.uuid), melee=create_dagger(entity.uuid))
    register_dark_devotion(entity)
    register_multiattack(entity, "Cult Fanatic Multiattack", ((WeaponSlot.MELEE_MAIN, 2),))
    return entity


def create_knight(
    source_id: Optional[UUID] = None,
    name: str = "Knight",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Knight."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A plate-armored heavy melee combatant.",
        position=position,
        faction=faction,
        abilities=(16, 11, 14, 11, 11, 15),
        hit_die_value=8,
        hit_die_count=8,
        proficiency_bonus=2,
    )
    _equip(entity, armor=create_plate_armor(entity.uuid), melee=create_greatsword(entity.uuid), ranged=create_heavy_crossbow(entity.uuid))
    register_brave(entity)
    register_leadership(entity)
    register_parry(entity)
    register_multiattack(entity, "Knight Multiattack", ((WeaponSlot.MELEE_MAIN, 2),))
    return entity


def create_veteran(
    source_id: Optional[UUID] = None,
    name: str = "Veteran",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Veteran."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A disciplined martial enemy with melee and heavy-crossbow modes.",
        position=position,
        faction=faction,
        abilities=(16, 13, 14, 10, 11, 10),
        hit_die_value=8,
        hit_die_count=9,
        proficiency_bonus=2,
        skills={"athletics": True, "perception": True},
    )
    _equip(entity, armor=create_splint_armor(entity.uuid), melee=create_longsword(entity.uuid), offhand=create_shortsword(entity.uuid), ranged=create_heavy_crossbow(entity.uuid))
    register_multiattack(entity, "Veteran Multiattack: Melee", ((WeaponSlot.MELEE_MAIN, 2), (WeaponSlot.MELEE_OFF, 1)))
    register_multiattack(entity, "Veteran Multiattack: Ranged", ((WeaponSlot.RANGED_MAIN, 2),))
    return entity


def create_mage(
    source_id: Optional[UUID] = None,
    name: str = "Mage",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Mage."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A high-slot arcane caster for resource and counterspell pressure.",
        position=position,
        faction=faction,
        abilities=(9, 14, 11, 17, 12, 11),
        hit_die_value=8,
        hit_die_count=9,
        proficiency_bonus=3,
        spellcasting_ability="intelligence",
        spell_slots={1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
        skills={"arcana": True, "history": True},
    )
    register_spells_by_name(entity, ["Fire Bolt", "Magic Missile", "Mage Armor", "Misty Step", "Fireball", "Greater Invisibility", "Ice Storm", "Cone of Cold"], caster_level=9)
    register_shield_reaction(entity)
    register_counterspell_reaction(entity)
    _equip(entity, melee=create_dagger(entity.uuid))
    return entity


def create_orc(
    source_id: Optional[UUID] = None,
    name: str = "Orc",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Orc."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A strong darkvision charger with axe and javelin pressure.",
        position=position,
        faction=faction,
        abilities=(16, 12, 16, 7, 11, 10),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        skills={"intimidation": True},
        darkvision=True,
    )
    _equip(
        entity,
        armor=create_hide_armor(entity.uuid),
        melee=create_greataxe(entity.uuid),
        ranged=_simple_weapon(entity.uuid, "Thrown Javelin", 6, 1, DamageType.PIERCING, RangeType.RANGE, 30, 120, (WeaponProperty.RANGED,), visual_item_name="Javelin"),
    )
    register_aggressive(entity)
    return entity


def create_hobgoblin(
    source_id: Optional[UUID] = None,
    name: str = "Hobgoblin",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Hobgoblin."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A heavily armored goblinoid soldier with sword and bow.",
        position=position,
        faction=faction,
        abilities=(13, 12, 12, 10, 10, 9),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        darkvision=True,
    )
    _equip(entity, armor=create_chain_mail(entity.uuid), melee=create_longsword(entity.uuid), ranged=create_longbow(entity.uuid), shield=True)
    register_martial_advantage(entity)
    return entity


def create_bugbear(
    source_id: Optional[UUID] = None,
    name: str = "Bugbear",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Bugbear."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A stealthy goblinoid bruiser.",
        position=position,
        faction=faction,
        abilities=(15, 14, 13, 8, 11, 9),
        hit_die_value=8,
        hit_die_count=5,
        proficiency_bonus=2,
        skills={"stealth": True, "survival": True},
        darkvision=True,
    )
    _equip(
        entity,
        armor=create_hide_armor(entity.uuid),
        melee=_simple_weapon(entity.uuid, "Morningstar", 8, 1, DamageType.PIERCING, visual_item_name="Morningstar"),
        ranged=_simple_weapon(entity.uuid, "Thrown Javelin", 6, 1, DamageType.PIERCING, RangeType.RANGE, 30, 120, (WeaponProperty.RANGED,), visual_item_name="Javelin"),
        shield=True,
    )
    register_brute(entity)
    register_surprise_attack(entity)
    return entity


def create_gnoll(
    source_id: Optional[UUID] = None,
    name: str = "Gnoll",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Gnoll."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A shielded savage with spear and longbow choices.",
        position=position,
        faction=faction,
        abilities=(14, 12, 11, 6, 10, 7),
        hit_die_value=8,
        hit_die_count=5,
        proficiency_bonus=2,
        darkvision=True,
    )
    _equip(
        entity,
        armor=create_hide_armor(entity.uuid),
        melee=create_spear(entity.uuid),
        ranged=create_longbow(entity.uuid),
        shield=True,
    )
    register_natural_bite(entity)
    register_rampage(entity)
    return entity


def create_ogre(
    source_id: Optional[UUID] = None,
    name: str = "Ogre",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Ogre."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A large giant with high HP and heavy bludgeoning pressure.",
        position=position,
        faction=faction,
        abilities=(19, 8, 16, 5, 7, 7),
        hit_die_value=10,
        hit_die_count=7,
        proficiency_bonus=2,
        creature_type=CreatureType.GIANT,
        size=Size.LARGE,
        weight=600,
        movement=40,
        darkvision=True,
    )
    _equip(
        entity,
        armor=create_hide_armor(entity.uuid),
        melee=_simple_weapon(entity.uuid, "Greatclub", 8, 2, DamageType.BLUDGEONING, visual_item_name="Club"),
        ranged=_simple_weapon(entity.uuid, "Thrown Javelin", 6, 2, DamageType.PIERCING, RangeType.RANGE, 30, 120, (WeaponProperty.RANGED,), visual_item_name="Javelin"),
    )
    return entity


def create_wolf(
    source_id: Optional[UUID] = None,
    name: str = "Wolf",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Wolf."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A fast beast with natural bite pressure.",
        position=position,
        faction=faction,
        abilities=(12, 15, 12, 3, 12, 6),
        hit_die_value=8,
        hit_die_count=2,
        proficiency_bonus=2,
        creature_type=CreatureType.BEAST,
        movement=40,
        skills={"perception": True, "stealth": True},
    )
    _equip(entity, armor=_fixed_ac_armor(entity.uuid, "Natural Armor", 13), melee=_simple_weapon(entity.uuid, "Bite", 4, 2, DamageType.PIERCING, equipped_visual_policy=EquippedVisualPolicy.HIDDEN))
    register_keen_perception(entity, name="Keen Hearing and Smell", modes=("hearing", "smell"))
    register_pack_tactics(entity)
    register_bite_prone_rider(entity, dc=11)
    return entity


def create_dire_wolf(
    source_id: Optional[UUID] = None,
    name: str = "Dire Wolf",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Dire Wolf."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A large fast beast for melee-pack and pursuit tests.",
        position=position,
        faction=faction,
        abilities=(17, 15, 15, 3, 12, 7),
        hit_die_value=10,
        hit_die_count=5,
        proficiency_bonus=2,
        creature_type=CreatureType.BEAST,
        size=Size.LARGE,
        movement=50,
        weight=250,
        skills={"perception": True, "stealth": True},
    )
    _equip(entity, armor=_fixed_ac_armor(entity.uuid, "Natural Armor", 14), melee=_simple_weapon(entity.uuid, "Bite", 6, 2, DamageType.PIERCING, equipped_visual_policy=EquippedVisualPolicy.HIDDEN))
    register_keen_perception(entity, name="Keen Hearing and Smell", modes=("hearing", "smell"))
    register_pack_tactics(entity)
    register_bite_prone_rider(entity, dc=13)
    return entity


def create_zombie(
    source_id: Optional[UUID] = None,
    name: str = "Zombie",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Zombie."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A slow undead body that stresses pursuit and poison immunity.",
        position=position,
        faction=faction,
        abilities=(13, 6, 16, 3, 6, 5),
        hit_die_value=8,
        hit_die_count=3,
        proficiency_bonus=2,
        creature_type=CreatureType.UNDEAD,
        movement=20,
        darkvision=True,
        immunities=(DamageType.POISON,),
    )
    entity.add_condition_immunity("Poisoned", immunity_name="Zombie")
    _equip(entity, melee=_simple_weapon(entity.uuid, "Slam", 6, 1, DamageType.BLUDGEONING, equipped_visual_policy=EquippedVisualPolicy.HIDDEN))
    register_undead_fortitude(entity)
    return entity


def create_ogre_zombie(
    source_id: Optional[UUID] = None,
    name: str = "Ogre Zombie",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Ogre Zombie."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A large undead bruiser with huge HP and slow cognition.",
        position=position,
        faction=faction,
        abilities=(19, 6, 18, 3, 6, 5),
        hit_die_value=10,
        hit_die_count=9,
        proficiency_bonus=2,
        creature_type=CreatureType.UNDEAD,
        size=Size.LARGE,
        weight=650,
        darkvision=True,
        immunities=(DamageType.POISON,),
    )
    entity.add_condition_immunity("Poisoned", immunity_name="Ogre Zombie")
    _equip(entity, melee=_simple_weapon(entity.uuid, "Morningstar", 8, 2, DamageType.BLUDGEONING, visual_item_name="Morningstar"))
    register_undead_fortitude(entity)
    return entity


def create_ghoul(
    source_id: Optional[UUID] = None,
    name: str = "Ghoul",
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create an SRD Ghoul."""
    entity = _create_srd_entity(
        source_id=source_id,
        name=name,
        description="A fast undead attacker with bite and claw modes.",
        position=position,
        faction=faction,
        abilities=(13, 15, 10, 7, 10, 6),
        hit_die_value=8,
        hit_die_count=5,
        proficiency_bonus=2,
        creature_type=CreatureType.UNDEAD,
        darkvision=True,
        immunities=(DamageType.POISON,),
    )
    entity.add_condition_immunity("Charmed", immunity_name="Ghoul")
    entity.add_condition_immunity("Exhaustion", immunity_name="Ghoul")
    entity.add_condition_immunity("Poisoned", immunity_name="Ghoul")
    _equip(
        entity,
        melee=_simple_weapon(entity.uuid, "Claws", 4, 2, DamageType.SLASHING, equipped_visual_policy=EquippedVisualPolicy.HIDDEN),
        offhand=_simple_weapon(entity.uuid, "Bite", 6, 2, DamageType.PIERCING, properties=(WeaponProperty.LIGHT,), equipped_visual_policy=EquippedVisualPolicy.HIDDEN),
    )
    register_ghoul_claws_paralysis(entity)
    return entity


SRD_MONSTER_SPECS: tuple[SrdMonsterSpec, ...] = (
    SrdMonsterSpec(monster_id="commoner", display_name="Commoner", challenge_rating="0", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("civilian", "melee")),
    SrdMonsterSpec(monster_id="bandit", display_name="Bandit", challenge_rating="1/8", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "ranged", "melee")),
    SrdMonsterSpec(monster_id="cultist", display_name="Cultist", challenge_rating="1/8", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "melee", "social"), represented_traits=("Dark Devotion",)),
    SrdMonsterSpec(monster_id="guard", display_name="Guard", challenge_rating="1/8", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "defender", "shield")),
    SrdMonsterSpec(monster_id="tribal_warrior", display_name="Tribal Warrior", challenge_rating="1/8", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "melee", "pack"), represented_traits=("Pack Tactics",)),
    SrdMonsterSpec(monster_id="kobold", display_name="Kobold", challenge_rating="1/8", source_path="to_archive/interactive_ruleset/Monsters/Kobold.md", role_tags=("humanoid", "small", "darkvision", "ranged"), represented_traits=("Pack Tactics", "Sunlight Sensitivity")),
    SrdMonsterSpec(monster_id="acolyte", display_name="Acolyte", challenge_rating="1/4", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "support", "caster"), represented_traits=("Spellcasting",)),
    SrdMonsterSpec(monster_id="zombie", display_name="Zombie", challenge_rating="1/4", source_path="to_archive/interactive_ruleset/Monsters (Alt)/Monsters Z.md", role_tags=("undead", "slow", "melee"), represented_traits=("Poison immunity", "Undead Fortitude")),
    SrdMonsterSpec(monster_id="wolf", display_name="Wolf", challenge_rating="1/4", source_path="to_archive/interactive_ruleset/Monsters/Wolf (Creature).md", role_tags=("beast", "fast", "pack"), represented_traits=("Keen Hearing and Smell", "Pack Tactics", "Bite prone rider")),
    SrdMonsterSpec(monster_id="scout", display_name="Scout", challenge_rating="1/2", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "ranged", "perception"), represented_traits=("Keen Hearing and Sight", "Multiattack")),
    SrdMonsterSpec(monster_id="thug", display_name="Thug", challenge_rating="1/2", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "bruiser", "ranged"), represented_traits=("Pack Tactics", "Multiattack")),
    SrdMonsterSpec(monster_id="orc", display_name="Orc", challenge_rating="1/2", source_path="to_archive/interactive_ruleset/Monsters/Orc.md", role_tags=("humanoid", "darkvision", "charger"), represented_traits=("Aggressive",)),
    SrdMonsterSpec(monster_id="hobgoblin", display_name="Hobgoblin", challenge_rating="1/2", source_path="to_archive/interactive_ruleset/Monsters/Hobgoblin.md", role_tags=("humanoid", "shield", "ranged", "darkvision"), represented_traits=("Martial Advantage",)),
    SrdMonsterSpec(monster_id="gnoll", display_name="Gnoll", challenge_rating="1/2", source_path="to_archive/interactive_ruleset/Monsters/Gnoll.md", role_tags=("humanoid", "shield", "ranged", "darkvision"), represented_traits=("Bite", "Rampage")),
    SrdMonsterSpec(monster_id="spy", display_name="Spy", challenge_rating="1", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "skirmisher", "ranged"), represented_traits=("Cunning Action", "Sneak Attack", "Multiattack")),
    SrdMonsterSpec(monster_id="bugbear", display_name="Bugbear", challenge_rating="1", source_path="to_archive/interactive_ruleset/Monsters/Bugbear.md", role_tags=("humanoid", "bruiser", "stealth", "darkvision"), represented_traits=("Brute", "Surprise Attack")),
    SrdMonsterSpec(monster_id="dire_wolf", display_name="Dire Wolf", challenge_rating="1", source_path="to_archive/interactive_ruleset/Monsters/Dire Wolf (Creature).md", role_tags=("beast", "large", "fast", "pack"), represented_traits=("Keen Hearing and Smell", "Pack Tactics", "Bite prone rider")),
    SrdMonsterSpec(monster_id="ghoul", display_name="Ghoul", challenge_rating="1", source_path="to_archive/interactive_ruleset/Monsters/Ghoul.md", role_tags=("undead", "melee", "condition-threat"), represented_traits=("Poison immunity", "condition immunities", "Claws paralysis rider")),
    SrdMonsterSpec(monster_id="berserker", display_name="Berserker", challenge_rating="2", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "bruiser", "melee"), represented_traits=("Reckless",)),
    SrdMonsterSpec(monster_id="bandit_captain", display_name="Bandit Captain", challenge_rating="2", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "leader", "duelist"), represented_traits=("Multiattack", "Parry")),
    SrdMonsterSpec(monster_id="cult_fanatic", display_name="Cult Fanatic", challenge_rating="2", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "control", "caster"), represented_traits=("Spellcasting", "Dark Devotion", "Multiattack")),
    SrdMonsterSpec(monster_id="priest", display_name="Priest", challenge_rating="2", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "support", "healing", "caster"), represented_traits=("Spellcasting", "Divine Eminence")),
    SrdMonsterSpec(monster_id="ogre", display_name="Ogre", challenge_rating="2", source_path="to_archive/interactive_ruleset/Monsters/Ogre.md", role_tags=("giant", "large", "bruiser", "darkvision")),
    SrdMonsterSpec(monster_id="ogre_zombie", display_name="Ogre Zombie", challenge_rating="2", source_path="to_archive/interactive_ruleset/Monsters (Alt)/Monsters Z.md", role_tags=("undead", "large", "bruiser"), represented_traits=("Poison immunity", "Undead Fortitude")),
    SrdMonsterSpec(monster_id="knight", display_name="Knight", challenge_rating="3", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "elite", "heavy-armor"), represented_traits=("Brave", "Leadership", "Parry", "Multiattack")),
    SrdMonsterSpec(monster_id="veteran", display_name="Veteran", challenge_rating="3", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "elite", "weapon-modes"), represented_traits=("Multiattack",)),
    SrdMonsterSpec(monster_id="mage", display_name="Mage", challenge_rating="6", source_path="to_archive/interactive_ruleset/Monsters (Alt)/NPCs.md", role_tags=("humanoid", "arcane", "caster", "counterspell"), represented_traits=("Spellcasting", "Shield reaction", "Counterspell reaction")),
)

SRD_MONSTER_FACTORIES: dict[str, MonsterFactory] = {
    "commoner": create_commoner,
    "bandit": create_bandit,
    "cultist": create_cultist,
    "guard": create_guard,
    "tribal_warrior": create_tribal_warrior,
    "kobold": create_kobold,
    "acolyte": create_acolyte,
    "scout": create_scout,
    "thug": create_thug,
    "spy": create_spy,
    "berserker": create_berserker,
    "bandit_captain": create_bandit_captain,
    "priest": create_priest,
    "cult_fanatic": create_cult_fanatic,
    "knight": create_knight,
    "veteran": create_veteran,
    "mage": create_mage,
    "orc": create_orc,
    "hobgoblin": create_hobgoblin,
    "bugbear": create_bugbear,
    "gnoll": create_gnoll,
    "ogre": create_ogre,
    "wolf": create_wolf,
    "dire_wolf": create_dire_wolf,
    "zombie": create_zombie,
    "ogre_zombie": create_ogre_zombie,
    "ghoul": create_ghoul,
}


def list_srd_monster_specs() -> tuple[SrdMonsterSpec, ...]:
    """Return the SRD-derived roster metadata."""
    return SRD_MONSTER_SPECS


def create_srd_monster(
    monster_id: str,
    source_id: Optional[UUID] = None,
    name: Optional[str] = None,
    position: tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
) -> Entity:
    """Create one SRD-derived monster by stable roster id.

    Args:
        monster_id: Stable id from `SRD_MONSTER_FACTORIES`.
        source_id: Optional explicit entity UUID.
        name: Optional display name override.
        position: Starting grid position.
        faction: Optional faction identifier.

    Returns:
        Configured entity.

    Raises:
        ValueError: If the roster id is unknown.
    """
    factory = SRD_MONSTER_FACTORIES.get(monster_id)
    if factory is None:
        raise ValueError(f"Unknown SRD monster id: {monster_id}")
    display_name = name or next(spec.display_name for spec in SRD_MONSTER_SPECS if spec.monster_id == monster_id)
    return factory(source_id, display_name, position, faction)


def _create_srd_entity(
    *,
    source_id: Optional[UUID],
    name: str,
    description: str,
    position: tuple[int, int],
    faction: Optional[str],
    abilities: tuple[int, int, int, int, int, int],
    hit_die_value: HitDieValue,
    hit_die_count: int,
    proficiency_bonus: int,
    skills: Optional[dict[str, bool]] = None,
    spellcasting_ability: Optional[AbilityName] = None,
    spell_slots: Optional[dict[int, int]] = None,
    creature_type: CreatureType = CreatureType.HUMANOID,
    size: Size = Size.MEDIUM,
    weight: int = 150,
    movement: int = 30,
    darkvision: bool = False,
    immunities: tuple[DamageType, ...] = (),
) -> Entity:
    """Create a configured entity using shared SRD roster defaults."""
    entity_uuid = source_id or uuid4()
    strength, dexterity, constitution, intelligence, wisdom, charisma = abilities
    skill_config = {
        skill_name: SkillConfig(proficiency=True)
        for skill_name, enabled in (skills or {}).items()
        if enabled
    }
    entity = Entity.create(
        name=name,
        source_entity_uuid=entity_uuid,
        description=description,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=strength),
                dexterity=AbilityConfig(ability_score=dexterity),
                constitution=AbilityConfig(ability_score=constitution),
                intelligence=AbilityConfig(ability_score=intelligence),
                wisdom=AbilityConfig(ability_score=wisdom),
                charisma=AbilityConfig(ability_score=charisma),
            ),
            skill_set=SkillSetConfig(**skill_config),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=hit_die_value,
                        hit_dice_count=hit_die_count,
                        mode="average",
                        ignore_first_level=False,
                    )
                ],
                immunities=list(immunities),
            ),
            action_economy=ActionEconomyConfig(
                movement=movement,
                spell_slots=spell_slots or {},
            ),
            spellcasting=SpellcastingConfig(spellcasting_ability=spellcasting_ability) if spellcasting_ability else None,
            proficiency_bonus=proficiency_bonus,
            position=position,
            faction=faction,
            weight=weight,
            creature_type=creature_type,
            size=size,
            appearance=_default_srd_appearance(creature_type, size),
        ),
    )
    setup_standard_actions(entity)
    if darkvision:
        entity.senses.sense_modes.append(SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))
    return entity


def _equip(
    entity: Entity,
    *,
    armor: Optional[BodyArmor] = None,
    melee: Optional[Weapon] = None,
    offhand: Optional[Weapon] = None,
    ranged: Optional[Weapon] = None,
    shield: bool = False,
) -> None:
    """Equip common SRD loadout pieces on an entity."""
    if armor is not None:
        entity.equipment.equip(armor)
    if melee is not None:
        entity.equipment.equip(melee, WeaponSlot.MELEE_MAIN)
    if offhand is not None:
        entity.equipment.equip(offhand, WeaponSlot.MELEE_OFF)
    if shield:
        entity.equipment.equip(create_shield(entity.uuid), WeaponSlot.MELEE_OFF)
    if ranged is not None:
        entity.equipment.equip(ranged, WeaponSlot.RANGED_MAIN)


def _simple_weapon(
    source_id: UUID,
    name: str,
    damage_dice: WeaponDieValue,
    dice_numbers: int,
    damage_type: DamageType,
    range_type: RangeType = RangeType.REACH,
    normal_range: int = 5,
    long_range: Optional[int] = None,
    properties: tuple[WeaponProperty, ...] = (),
    *,
    visual_item_name: Optional[str] = None,
    equipped_visual_policy: EquippedVisualPolicy = EquippedVisualPolicy.VISIBLE,
) -> Weapon:
    """Create a direct weapon for natural attacks and SRD gaps."""
    return Weapon(
        source_entity_uuid=source_id,
        name=name,
        description=f"SRD-derived {name.lower()} attack.",
        damage_dice=damage_dice,
        dice_numbers=dice_numbers,
        damage_type=damage_type,
        properties=list(properties),
        range=Range(type=range_type, normal=normal_range, long=long_range),
        attack_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Attack Bonus"),
        extra_damage_dices=[],
        extra_damage_dices_numbers=[],
        extra_damage_bonus=[],
        extra_damage_type=[],
        visual_item_name=visual_item_name,
        equipped_visual_policy=equipped_visual_policy,
    )


def _fixed_ac_armor(source_id: UUID, name: str, armor_class: int) -> BodyArmor:
    """Create fixed-AC pseudo-armor for natural armor."""
    return BodyArmor(
        source_entity_uuid=source_id,
        name=name,
        description=f"Fixed AC {armor_class} natural protection.",
        type=ArmorType.LIGHT,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(source_entity_uuid=source_id, base_value=armor_class, value_name="Armor Class"),
        max_dex_bonus=ModifiableValue.create(source_entity_uuid=source_id, base_value=0, value_name="Max Dex Bonus"),
        equipped_visual_policy=EquippedVisualPolicy.HIDDEN,
    )


def _default_srd_appearance(creature_type: CreatureType, size: Size) -> AppearanceConfig:
    """Return the temporary presentation contract for an SRD creature.

    Humanoids use NeuroClient's layered paper doll so their equipped gear drives
    their appearance. Other creature families retain normal animation behavior
    through a conspicuous placeholder until full-entity manifests are assigned.

    Args:
        creature_type: Rules-level creature classification.
        size: Rules-level creature size.

    Returns:
        Presentation metadata independent from the creature's grid footprint.
    """
    visual_scale = _VISUAL_SCALE_BY_SIZE[size]
    if creature_type == CreatureType.HUMANOID:
        return AppearanceConfig(visual_scale=visual_scale)
    return AppearanceConfig(
        presentation_kind="placeholder",
        visual_scale=visual_scale,
        placeholder_tint=0x36FF62,
    )
