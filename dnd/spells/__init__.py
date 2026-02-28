"""Spell system for D&D 5e engine.

Provides spell classes organized by school, plus registration utilities.
"""
from dnd.spells.base import SpellAction, SpellEvent
from dnd.spells.evocation import (
    FireBolt, SacredFlame, MagicMissile, Fireball,
    BurningHands, LightningBolt, Thunderwave, Shatter, Sunburst,
    ConeOfCold, CircleOfDeath, RayOfFrost, ScorchingRay,
    ShockingGrasp, GuidingBolt, GuidingBoltMarked, EldritchBlast,
    GustOfWind, IceStorm, Sunbeam, ChainLightning, PrismaticSpray,
    TrueStrike, register_true_strike,
    FlameStrike, Light, LightEffect, ContinualFlame, ContinualFlameObject,
    CureWounds, HealingWord, PrayerOfHealing, MassHealingWord,
    MassCureWounds, HealSpell, MassHeal
)
from dnd.spells.abjuration import MageArmor, ProtectionFromEnergy, Stoneskin, register_shield_reaction, register_counterspell_reaction, GlobeOfInvulnerability, Banishment, LesserRestoration, GreaterRestoration
from dnd.spells.enchantment import HoldPerson, HoldMonster, PowerWordKill, PowerWordStun, PowerWordStunEffect, CharmPerson, Sleep, Bane, BaneEffect, Bless, BlessEffect, Command, CommandGrovelEffect, CommandHaltEffect, CommandFleeEffect
from dnd.spells.conjuration import CallLightning, CallLightningStrike, PoisonSpray, AcidSplash, MistyStep, Grease, Web, Cloudkill, SpiritGuardians, FogCloud, Darkness, Daylight, InsectPlague, IncendiaryCloud, StinkingCloud, SleetStorm, DimensionDoor, GuardianOfFaith, GuardianOfFaithObject, GuardianWarded
from dnd.spells.necromancy import Blight, BlindnessDeafness, FalseLife, ChillTouch, NoHealing, NecroticBless, Eyebite, FingerOfDeath
from dnd.spells.illusion import Blur, Fear, HypnoticPattern, ColorSpray, Invisibility, GreaterInvisibility, MirrorImage, Silence, SilenceZone
from dnd.spells.transmutation import SpikeGrowth, Slow, Haste, DarkvisionSpell, Disintegrate, JumpSpell, ExpeditiousRetreat, EnhanceAbility, EnlargeReduce, Telekinesis, Regenerate, RegeneratingEffect
from dnd.spells.divination import SeeInvisibility, TrueSeeing, Guidance, GuidanceEffect

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
    "True Strike": TrueStrike,
    "Guidance": Guidance,
    "Light": Light,
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
    "Bane": Bane,
    "Bless": Bless,
    "Jump": JumpSpell,
    "Expeditious Retreat": ExpeditiousRetreat,
    "Command": Command,
    "Cure Wounds": CureWounds,
    "Healing Word": HealingWord,
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
    "Mirror Image": MirrorImage,
    "Necrotic Bless": NecroticBless,
    "Darkvision": DarkvisionSpell,
    "See Invisibility": SeeInvisibility,
    "Gust of Wind": GustOfWind,
    "Enhance Ability": EnhanceAbility,
    "Enlarge/Reduce": EnlargeReduce,
    "Silence": Silence,
    "Continual Flame": ContinualFlame,
    "Prayer of Healing": PrayerOfHealing,
    "Lesser Restoration": LesserRestoration,
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
    "Slow": Slow,
    "Haste": Haste,
    "Stinking Cloud": StinkingCloud,
    "Sleet Storm": SleetStorm,
    "Mass Healing Word": MassHealingWord,
}

LEVEL_4_SPELLS = {
    "Blight": Blight,
    "Stoneskin": Stoneskin,
    "Greater Invisibility": GreaterInvisibility,
    "Ice Storm": IceStorm,
    "Dimension Door": DimensionDoor,
    "Banishment": Banishment,
    "Guardian of Faith": GuardianOfFaith,
}

LEVEL_5_SPELLS = {
    "Hold Monster": HoldMonster,
    "Cone of Cold": ConeOfCold,
    "Cloudkill": Cloudkill,
    "Insect Plague": InsectPlague,
    "Telekinesis": Telekinesis,
    "Flame Strike": FlameStrike,
    "Mass Cure Wounds": MassCureWounds,
    "Greater Restoration": GreaterRestoration,
}

LEVEL_6_SPELLS = {
    "Circle of Death": CircleOfDeath,
    "Disintegrate": Disintegrate,
    "True Seeing": TrueSeeing,
    "Sunbeam": Sunbeam,
    "Chain Lightning": ChainLightning,
    "Eyebite": Eyebite,
    "Globe of Invulnerability": GlobeOfInvulnerability,
    "Heal": HealSpell,
}

LEVEL_7_SPELLS = {
    "Prismatic Spray": PrismaticSpray,
    "Finger of Death": FingerOfDeath,
    "Regenerate": Regenerate,
}

LEVEL_8_SPELLS = {
    "Sunburst": Sunburst,
    "Power Word Stun": PowerWordStun,
    "Incendiary Cloud": IncendiaryCloud,
}

LEVEL_9_SPELLS = {
    "Power Word Kill": PowerWordKill,
    "Mass Heal": MassHeal,
}

ALL_SPELLS = {
    **CANTRIPS,
    **LEVEL_1_SPELLS,
    **LEVEL_2_SPELLS,
    **LEVEL_3_SPELLS,
    **LEVEL_4_SPELLS,
    **LEVEL_5_SPELLS,
    **LEVEL_6_SPELLS,
    **LEVEL_7_SPELLS,
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
    "TrueStrike",
    "Guidance",
    "Light",
    # Spell-specific conditions
    "NoHealing",
    "GuidingBoltMarked",
    "PowerWordStunEffect",
    "LightEffect",
    "ContinualFlameObject",
    "GuidanceEffect",
    "CommandGrovelEffect",
    "CommandHaltEffect",
    "CommandFleeEffect",
    "SilenceZone",
    "GuardianOfFaithObject",
    "GuardianWarded",
    "RegeneratingEffect",
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
    "Bane",
    "BaneEffect",
    "Bless",
    "BlessEffect",
    "JumpSpell",
    "ExpeditiousRetreat",
    "Command",
    "CureWounds",
    "HealingWord",
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
    "MirrorImage",
    "NecroticBless",
    "DarkvisionSpell",
    "SeeInvisibility",
    "GustOfWind",
    "EnhanceAbility",
    "EnlargeReduce",
    "Silence",
    "ContinualFlame",
    "PrayerOfHealing",
    "LesserRestoration",
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
    "Slow",
    "Haste",
    "StinkingCloud",
    "SleetStorm",
    "MassHealingWord",
    # Level 4
    "Blight",
    "Stoneskin",
    "GreaterInvisibility",
    "IceStorm",
    "DimensionDoor",
    "Banishment",
    "GuardianOfFaith",
    # Level 5
    "HoldMonster",
    "ConeOfCold",
    "Cloudkill",
    "InsectPlague",
    "Telekinesis",
    "FlameStrike",
    "MassCureWounds",
    "GreaterRestoration",
    # Level 6
    "CircleOfDeath",
    "Disintegrate",
    "TrueSeeing",
    "Sunbeam",
    "ChainLightning",
    "Eyebite",
    "GlobeOfInvulnerability",
    "HealSpell",
    # Level 7
    "PrismaticSpray",
    "FingerOfDeath",
    "Regenerate",
    # Level 8
    "Sunburst",
    "PowerWordStun",
    "IncendiaryCloud",
    # Level 9
    "PowerWordKill",
    "MassHeal",
    # Lookup dicts
    "CANTRIPS",
    "LEVEL_1_SPELLS",
    "LEVEL_2_SPELLS",
    "LEVEL_3_SPELLS",
    "LEVEL_4_SPELLS",
    "LEVEL_5_SPELLS",
    "LEVEL_6_SPELLS",
    "LEVEL_7_SPELLS",
    "LEVEL_8_SPELLS",
    "LEVEL_9_SPELLS",
    "ALL_SPELLS",
    # Reaction spells
    "register_shield_reaction",
    "register_counterspell_reaction",
    "register_true_strike",
]
