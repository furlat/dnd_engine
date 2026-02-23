"""Spell system for D&D 5e engine.

Provides spell classes organized by school, plus registration utilities.
"""
from dnd.spells.base import SpellAction, SpellEvent
from dnd.spells.evocation import (
    FireBolt, SacredFlame, MagicMissile, Fireball,
    BurningHands, LightningBolt, Thunderwave, Shatter, Sunburst,
    ConeOfCold, CircleOfDeath, RayOfFrost, ScorchingRay,
    ShockingGrasp, GuidingBolt, GuidingBoltMarked, EldritchBlast
)
from dnd.spells.abjuration import MageArmor, ProtectionFromEnergy, Stoneskin, register_shield_reaction
from dnd.spells.enchantment import HoldPerson, HoldMonster, PowerWordKill, PowerWordStun, PowerWordStunEffect, CharmPerson, Sleep
from dnd.spells.conjuration import CallLightning, CallLightningStrike, PoisonSpray, AcidSplash, MistyStep, Grease, Web, Cloudkill, SpiritGuardians, FogCloud, Darkness, Daylight
from dnd.spells.necromancy import Blight, BlindnessDeafness, FalseLife, ChillTouch, NoHealing
from dnd.spells.illusion import Blur, Fear, HypnoticPattern, ColorSpray, Invisibility, GreaterInvisibility
from dnd.spells.transmutation import SpikeGrowth

# Lookup dictionaries (like dnd/items/__init__.py)
CANTRIPS = {
    "Fire Bolt": FireBolt,
    "Sacred Flame": SacredFlame,
    "Poison Spray": PoisonSpray,
    "Ray of Frost": RayOfFrost,
    "Acid Splash": AcidSplash,
    "Chill Touch": ChillTouch,
    "Shocking Grasp": ShockingGrasp,
    "Eldritch Blast": EldritchBlast,
}

LEVEL_1_SPELLS = {
    "Magic Missile": MagicMissile,
    "Mage Armor": MageArmor,
    "Burning Hands": BurningHands,
    "Thunderwave": Thunderwave,
    "False Life": FalseLife,
    "Charm Person": CharmPerson,
    "Sleep": Sleep,
    "Color Spray": ColorSpray,
    "Guiding Bolt": GuidingBolt,
    "Grease": Grease,
    "Fog Cloud": FogCloud,
}

LEVEL_2_SPELLS = {
    "Hold Person": HoldPerson,
    "Shatter": Shatter,
    "Scorching Ray": ScorchingRay,
    "Blur": Blur,
    "Misty Step": MistyStep,
    "Blindness/Deafness": BlindnessDeafness,
    "Spike Growth": SpikeGrowth,
    "Web": Web,
    "Invisibility": Invisibility,
    "Darkness": Darkness,
}

LEVEL_3_SPELLS = {
    "Call Lightning": CallLightning,
    "Fireball": Fireball,
    "Lightning Bolt": LightningBolt,
    "Protection from Energy": ProtectionFromEnergy,
    "Fear": Fear,
    "Hypnotic Pattern": HypnoticPattern,
    "Spirit Guardians": SpiritGuardians,
    "Daylight": Daylight,
}

LEVEL_4_SPELLS = {
    "Blight": Blight,
    "Stoneskin": Stoneskin,
    "Greater Invisibility": GreaterInvisibility,
}

LEVEL_5_SPELLS = {
    "Hold Monster": HoldMonster,
    "Cone of Cold": ConeOfCold,
    "Cloudkill": Cloudkill,
}

LEVEL_6_SPELLS = {
    "Circle of Death": CircleOfDeath,
}

LEVEL_8_SPELLS = {
    "Sunburst": Sunburst,
    "Power Word Stun": PowerWordStun,
}

LEVEL_9_SPELLS = {
    "Power Word Kill": PowerWordKill,
}

ALL_SPELLS = {
    **CANTRIPS,
    **LEVEL_1_SPELLS,
    **LEVEL_2_SPELLS,
    **LEVEL_3_SPELLS,
    **LEVEL_4_SPELLS,
    **LEVEL_5_SPELLS,
    **LEVEL_6_SPELLS,
    **LEVEL_8_SPELLS,
    **LEVEL_9_SPELLS
}

__all__ = [
    # Base classes
    "SpellAction",
    "SpellEvent",
    # Cantrips
    "FireBolt",
    "SacredFlame",
    "PoisonSpray",
    "RayOfFrost",
    "AcidSplash",
    "ChillTouch",
    "ShockingGrasp",
    "EldritchBlast",
    # Spell-specific conditions
    "NoHealing",
    "GuidingBoltMarked",
    "PowerWordStunEffect",
    # Level 1
    "MagicMissile",
    "MageArmor",
    "BurningHands",
    "Thunderwave",
    "FalseLife",
    "CharmPerson",
    "Sleep",
    "ColorSpray",
    "GuidingBolt",
    "Grease",
    "FogCloud",
    # Level 2
    "HoldPerson",
    "Shatter",
    "ScorchingRay",
    "Blur",
    "MistyStep",
    "BlindnessDeafness",
    "SpikeGrowth",
    "Web",
    "Invisibility",
    "Darkness",
    # Level 3
    "CallLightning",
    "CallLightningStrike",
    "Fireball",
    "LightningBolt",
    "ProtectionFromEnergy",
    "Fear",
    "HypnoticPattern",
    "SpiritGuardians",
    "Daylight",
    # Level 4
    "Blight",
    "Stoneskin",
    "GreaterInvisibility",
    # Level 5
    "HoldMonster",
    "ConeOfCold",
    "Cloudkill",
    # Level 6
    "CircleOfDeath",
    # Level 8
    "Sunburst",
    "PowerWordStun",
    # Level 9
    "PowerWordKill",
    # Lookup dicts
    "CANTRIPS",
    "LEVEL_1_SPELLS",
    "LEVEL_2_SPELLS",
    "LEVEL_3_SPELLS",
    "LEVEL_4_SPELLS",
    "LEVEL_5_SPELLS",
    "LEVEL_6_SPELLS",
    "LEVEL_8_SPELLS",
    "LEVEL_9_SPELLS",
    "ALL_SPELLS",
    # Reaction spells
    "register_shield_reaction",
]
