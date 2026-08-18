"""Direct semantic spell-ID to runtime behavior constructors.

This is construction dispatch, not a catalog and not persistence authority.
The authored character definitions remain cold and never import this module.
"""

from collections.abc import Callable
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from dnd.actions.standard import SpellAction
from dnd.core.events.events_registry import EventHandler
import dnd.spells.abjuration as abjuration
import dnd.spells.conjuration as conjuration
import dnd.spells.divination as divination
import dnd.spells.enchantment as enchantment
import dnd.spells.evocation as evocation
import dnd.spells.illusion as illusion
import dnd.spells.necromancy as necromancy
import dnd.spells.transmutation as transmutation


SPELL_ACTION_TYPES_BY_ID: Mapping[str, type[SpellAction]] = MappingProxyType({
    "spell.acid_splash": conjuration.AcidSplash,
    "spell.chill_touch": necromancy.ChillTouch,
    "spell.fire_bolt": evocation.FireBolt,
    "spell.sacred_flame": evocation.SacredFlame,
    "spell.light": evocation.Light,
    "spell.poison_spray": conjuration.PoisonSpray,
    "spell.ray_of_frost": evocation.RayOfFrost,
    "spell.shocking_grasp": evocation.ShockingGrasp,
    "spell.true_strike": evocation.TrueStrike,
    "spell.burning_hands": evocation.BurningHands,
    "spell.charm_person": enchantment.CharmPerson,
    "spell.color_spray": illusion.ColorSpray,
    "spell.expeditious_retreat": transmutation.ExpeditiousRetreat,
    "spell.false_life": necromancy.FalseLife,
    "spell.fog_cloud": conjuration.FogCloud,
    "spell.jump": transmutation.JumpSpell,
    "spell.mage_armor": abjuration.MageArmor,
    "spell.magic_missile": evocation.MagicMissile,
    "spell.healing_word": evocation.HealingWord,
    "spell.bless": enchantment.Bless,
    "spell.bane": enchantment.Bane,
    "spell.aid": abjuration.Aid,
    "spell.command": enchantment.Command,
    "spell.cure_wounds": evocation.CureWounds,
    "spell.guiding_bolt": evocation.GuidingBolt,
    "spell.inflict_wounds": necromancy.InflictWounds,
    "spell.sanctuary": abjuration.Sanctuary,
    "spell.shield_of_faith": abjuration.ShieldOfFaith,
    "spell.sleep": enchantment.Sleep,
    "spell.thunderwave": evocation.Thunderwave,
    "spell.blindness_deafness": necromancy.BlindnessDeafness,
    "spell.blur": illusion.Blur,
    "spell.darkness": conjuration.Darkness,
    "spell.darkvision": transmutation.DarkvisionSpell,
    "spell.enhance_ability": transmutation.EnhanceAbility,
    "spell.enlarge_reduce": transmutation.EnlargeReduce,
    "spell.gust_of_wind": evocation.GustOfWind,
    "spell.hold_person": enchantment.HoldPerson,
    "spell.invisibility": illusion.Invisibility,
    "spell.mirror_image": illusion.MirrorImage,
    "spell.misty_step": conjuration.MistyStep,
    "spell.lesser_restoration": abjuration.LesserRestoration,
    "spell.scorching_ray": evocation.ScorchingRay,
    "spell.see_invisibility": divination.SeeInvisibility,
    "spell.shatter": evocation.Shatter,
    "spell.web": conjuration.Web,
    "spell.grease": conjuration.Grease,
    "spell.spike_growth": transmutation.SpikeGrowth,
    "spell.silence": illusion.Silence,
    "spell.daylight": conjuration.Daylight,
    "spell.fear": illusion.Fear,
    "spell.fireball": evocation.Fireball,
    "spell.guardian_of_faith": conjuration.GuardianOfFaith,
    "spell.mass_healing_word": evocation.MassHealingWord,
    "spell.flame_strike": evocation.FlameStrike,
    "spell.spirit_guardians": conjuration.SpiritGuardians,
    "spell.haste": transmutation.Haste,
    "spell.hypnotic_pattern": illusion.HypnoticPattern,
    "spell.lightning_bolt": evocation.LightningBolt,
    "spell.eldritch_blast": evocation.EldritchBlast,
    "spell.protection_from_energy": abjuration.ProtectionFromEnergy,
    "spell.sleet_storm": conjuration.SleetStorm,
    "spell.slow": transmutation.Slow,
    "spell.stinking_cloud": conjuration.StinkingCloud,
    "spell.banishment": abjuration.Banishment,
    "spell.beacon_of_hope": abjuration.BeaconOfHope,
    "spell.bestow_curse": necromancy.BestowCurse,
    "spell.blight": necromancy.Blight,
    "spell.dimension_door": conjuration.DimensionDoor,
    "spell.greater_invisibility": illusion.GreaterInvisibility,
    "spell.necrotic_bless": necromancy.NecroticBless,
    "spell.ice_storm": evocation.IceStorm,
    "spell.stoneskin": abjuration.Stoneskin,
    "spell.cloudkill": conjuration.Cloudkill,
    "spell.cone_of_cold": evocation.ConeOfCold,
    "spell.harm": necromancy.Harm,
    "spell.greater_restoration": abjuration.GreaterRestoration,
    "spell.hold_monster": enchantment.HoldMonster,
    "spell.insect_plague": conjuration.InsectPlague,
    "spell.telekinesis": transmutation.Telekinesis,
    "spell.chain_lightning": evocation.ChainLightning,
    "spell.circle_of_death": evocation.CircleOfDeath,
    "spell.disintegrate": transmutation.Disintegrate,
    "spell.eyebite": necromancy.Eyebite,
    "spell.globe_of_invulnerability": abjuration.GlobeOfInvulnerability,
    "spell.sunbeam": evocation.Sunbeam,
    "spell.true_seeing": divination.TrueSeeing,
    "spell.finger_of_death": necromancy.FingerOfDeath,
    "spell.prismatic_spray": evocation.PrismaticSpray,
    "spell.incendiary_cloud": conjuration.IncendiaryCloud,
    "spell.power_word_stun": enchantment.PowerWordStun,
    "spell.sunburst": evocation.Sunburst,
    "spell.power_word_kill": enchantment.PowerWordKill,
})


def _learned_counterspell(entity_uuid: UUID) -> EventHandler:
    return abjuration.create_counterspell_reaction_handler(
        entity_uuid,
        learned_spell_id="spell.counterspell",
    )


REACTION_HANDLER_FACTORIES_BY_SPELL_ID: Mapping[
    str,
    Callable[[UUID], EventHandler],
] = MappingProxyType({
    "spell.shield": abjuration.create_shield_reaction_handler,
    "spell.counterspell": _learned_counterspell,
})


__all__ = [
    "REACTION_HANDLER_FACTORIES_BY_SPELL_ID",
    "SPELL_ACTION_TYPES_BY_ID",
]
