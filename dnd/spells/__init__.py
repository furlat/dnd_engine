"""Spell system for D&D 5e engine.

Provides spell classes organized by school, plus registration utilities.
"""
from dnd.spells.base import SpellAction, SpellEvent
from dnd.spells.evocation import (
    FireBolt, SacredFlame, MagicMissile, Fireball,
    BurningHands, LightningBolt, Thunderwave, Shatter
)
from dnd.spells.abjuration import MageArmor
from dnd.spells.enchantment import HoldPerson
from dnd.spells.conjuration import CallLightning, CallLightningStrike

# Lookup dictionaries (like dnd/items/__init__.py)
CANTRIPS = {
    "Fire Bolt": FireBolt,
    "Sacred Flame": SacredFlame,
}

LEVEL_1_SPELLS = {
    "Magic Missile": MagicMissile,
    "Mage Armor": MageArmor,
    "Burning Hands": BurningHands,
    "Thunderwave": Thunderwave,
}

LEVEL_2_SPELLS = {
    "Hold Person": HoldPerson,
    "Shatter": Shatter,
}

LEVEL_3_SPELLS = {
    "Call Lightning": CallLightning,
    "Fireball": Fireball,
    "Lightning Bolt": LightningBolt,
}

ALL_SPELLS = {**CANTRIPS, **LEVEL_1_SPELLS, **LEVEL_2_SPELLS, **LEVEL_3_SPELLS}

__all__ = [
    # Base classes
    "SpellAction",
    "SpellEvent",
    # Cantrips
    "FireBolt",
    "SacredFlame",
    # Level 1
    "MagicMissile",
    "MageArmor",
    "BurningHands",
    "Thunderwave",
    # Level 2
    "HoldPerson",
    "Shatter",
    # Level 3
    "CallLightning",
    "CallLightningStrike",
    "Fireball",
    "LightningBolt",
    # Lookup dicts
    "CANTRIPS",
    "LEVEL_1_SPELLS",
    "LEVEL_2_SPELLS",
    "LEVEL_3_SPELLS",
    "ALL_SPELLS",
]
