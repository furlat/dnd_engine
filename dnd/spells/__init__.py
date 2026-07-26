"""Spell catalog exports organized by school and spell level."""
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
    MassCureWounds, HealSpell, MassHeal,
    DivineWord, DivineWordEffect,
)
from dnd.spells.abjuration import MageArmor, ProtectionFromEnergy, Stoneskin, register_shield_reaction, register_counterspell_reaction, GlobeOfInvulnerability, Banishment, LesserRestoration, GreaterRestoration, RemoveCurse, ProtectionFromPoison, DeathWard, FreedomOfMovement, Resistance, ResistanceEffect, ShieldOfFaith, ShieldOfFaithEffect, Aid, AidEffect, Sanctuary, SanctuaryEffect, BeaconOfHope, BeaconOfHopeEffect, AntimagicField
from dnd.spells.enchantment import HoldPerson, HoldMonster, PowerWordKill, PowerWordStun, PowerWordStunEffect, CharmPerson, Sleep, Bane, BaneEffect, Bless, BlessEffect, Command, CommandGrovelEffect, CommandHaltEffect, CommandFleeEffect
from dnd.spells.conjuration import CallLightning, CallLightningStrike, PoisonSpray, AcidSplash, MistyStep, Grease, Web, Cloudkill, SpiritGuardians, FogCloud, Darkness, Daylight, InsectPlague, IncendiaryCloud, StinkingCloud, SleetStorm, DimensionDoor, GuardianOfFaith, GuardianOfFaithObject, GuardianWarded, HeroesFeast, HeroesFeastObject, HeroesFeastBuff, EatFromFeast
from dnd.spells.necromancy import Blight, BlindnessDeafness, FalseLife, ChillTouch, NoHealing, NecroticBless, Eyebite, FingerOfDeath, InflictWounds, Harm, BestowCurse, AbilityCurseEffect, AttackCurseEffect, InactionCurseEffect, DamageCurseEffect
from dnd.spells.illusion import Blur, Fear, HypnoticPattern, ColorSpray, Invisibility, GreaterInvisibility, MirrorImage, Silence, SilenceZone
from dnd.spells.transmutation import SpikeGrowth, Slow, Haste, DarkvisionSpell, Disintegrate, JumpSpell, ExpeditiousRetreat, EnhanceAbility, EnlargeReduce, Telekinesis, Regenerate, RegeneratingEffect
from dnd.spells.divination import SeeInvisibility, TrueSeeing, Guidance, GuidanceEffect
from dnd.spells.catalog_content import (
    SPELL_CATALOG_METADATA_BY_CLASS,
    SPELL_CATALOG_METADATA_BY_ID,
    SPELL_CATALOG_METADATA_BY_NAME,
    SPELL_CATALOG_METADATA_SPECS,
    SPELL_CONTENT_DECLARATIONS,
    SPELL_CONTENT_DECLARATIONS_BY_CLASS,
    SPELL_CONTENT_DECLARATIONS_BY_NAME,
    SPELL_CONTENT_IDENTITY_BY_CLASS,
    SPELL_CONTENT_IDENTITY_BY_NAME,
    SPELL_CONTENT_IDENTITY_BY_REF_KEY,
    SPELL_CONTENT_IDENTITY_SPECS,
)

def _spell_map_for_level(
    level: int | None,
) -> dict[str, type[SpellAction]]:
    """Project the authored identity table into the legacy public map shape."""
    return {
        spec.display_name: spec.spell_type
        for spec in SPELL_CONTENT_IDENTITY_SPECS
        if level is None or spec.level == level
    }


CANTRIPS = _spell_map_for_level(0)
LEVEL_1_SPELLS = _spell_map_for_level(1)
LEVEL_2_SPELLS = _spell_map_for_level(2)
LEVEL_3_SPELLS = _spell_map_for_level(3)
LEVEL_4_SPELLS = _spell_map_for_level(4)
LEVEL_5_SPELLS = _spell_map_for_level(5)
LEVEL_6_SPELLS = _spell_map_for_level(6)
LEVEL_7_SPELLS = _spell_map_for_level(7)
LEVEL_8_SPELLS = _spell_map_for_level(8)
LEVEL_9_SPELLS = _spell_map_for_level(9)
ALL_SPELLS = _spell_map_for_level(None)

__all__ = [

    "SpellAction",
    "SpellEvent",

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

    "NoHealing",
    "GuidingBoltMarked",
    "PowerWordStunEffect",
    "LightEffect",
    "ContinualFlameObject",
    "GuidanceEffect",
    "ResistanceEffect",
    "ShieldOfFaithEffect",
    "AidEffect",
    "SanctuaryEffect",
    "BeaconOfHopeEffect",
    "DivineWordEffect",
    "AbilityCurseEffect",
    "AttackCurseEffect",
    "InactionCurseEffect",
    "DamageCurseEffect",
    "HeroesFeastObject",
    "HeroesFeastBuff",
    "EatFromFeast",
    "CommandGrovelEffect",
    "CommandHaltEffect",
    "CommandFleeEffect",
    "SilenceZone",
    "GuardianOfFaithObject",
    "GuardianWarded",
    "RegeneratingEffect",

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
    "InflictWounds",
    "ShieldOfFaith",
    "Sanctuary",
    "Resistance",

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
    "ProtectionFromPoison",
    "Aid",

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
    "BeaconOfHope",
    "RemoveCurse",
    "BestowCurse",

    "Blight",
    "Stoneskin",
    "GreaterInvisibility",
    "IceStorm",
    "DimensionDoor",
    "Banishment",
    "GuardianOfFaith",
    "DeathWard",
    "FreedomOfMovement",

    "HoldMonster",
    "ConeOfCold",
    "Cloudkill",
    "InsectPlague",
    "Telekinesis",
    "FlameStrike",
    "MassCureWounds",
    "GreaterRestoration",

    "CircleOfDeath",
    "Disintegrate",
    "TrueSeeing",
    "Sunbeam",
    "ChainLightning",
    "Eyebite",
    "GlobeOfInvulnerability",
    "HealSpell",
    "Harm",
    "HeroesFeast",

    "PrismaticSpray",
    "FingerOfDeath",
    "Regenerate",
    "DivineWord",

    "Sunburst",
    "PowerWordStun",
    "IncendiaryCloud",
    "AntimagicField",

    "PowerWordKill",
    "MassHeal",

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
    "SPELL_CATALOG_METADATA_BY_CLASS",
    "SPELL_CATALOG_METADATA_BY_ID",
    "SPELL_CATALOG_METADATA_BY_NAME",
    "SPELL_CATALOG_METADATA_SPECS",
    "SPELL_CONTENT_DECLARATIONS",
    "SPELL_CONTENT_DECLARATIONS_BY_CLASS",
    "SPELL_CONTENT_DECLARATIONS_BY_NAME",
    "SPELL_CONTENT_IDENTITY_BY_CLASS",
    "SPELL_CONTENT_IDENTITY_BY_NAME",
    "SPELL_CONTENT_IDENTITY_BY_REF_KEY",
    "SPELL_CONTENT_IDENTITY_SPECS",

    "register_shield_reaction",
    "register_counterspell_reaction",
    "register_true_strike",
]
