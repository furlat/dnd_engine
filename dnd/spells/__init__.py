"""Spell system for D&D 5e engine.

Provides spell classes organized by school, plus registration utilities.
"""
from dnd.spells.base import SpellAction, SpellEvent
from dnd.spells.evocation import FireBolt, SacredFlame, MagicMissile
from dnd.spells.abjuration import MageArmor

# Lookup dictionaries (like dnd/items/__init__.py)
CANTRIPS = {
    "Fire Bolt": FireBolt,
    "Sacred Flame": SacredFlame,
}

LEVEL_1_SPELLS = {
    "Magic Missile": MagicMissile,
    "Mage Armor": MageArmor,
}

ALL_SPELLS = {**CANTRIPS, **LEVEL_1_SPELLS}

__all__ = [
    # Base classes
    "SpellAction",
    "SpellEvent",
    # Spells
    "FireBolt",
    "SacredFlame",
    "MagicMissile",
    "MageArmor",
    # Lookup dicts
    "CANTRIPS",
    "LEVEL_1_SPELLS",
    "ALL_SPELLS",
]
