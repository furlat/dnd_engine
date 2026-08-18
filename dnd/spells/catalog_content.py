"""Exact authored content identities for every public spell-catalog root.

The table in this module is intentionally explicit.  Display names and Python
paths are not transformed into durable identity.  The eight spell classes
whose declarations live beside their implementations remain authoritative;
this module verifies those declarations and supplies declarations for the
remaining catalog classes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from dnd.actions.standard import (
    SpellAction,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import resolve_content_icon_key
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.registration import (
    ContentDeclaration,
    get_content_declaration,
)
from dnd.types.behaviors import RuntimeBehaviorKind
from dnd.types.abilities import AbilityName
from dnd.types.damage import DamageType
import dnd.spells.abjuration as abjuration
import dnd.spells.conjuration as conjuration
import dnd.spells.divination as divination
import dnd.spells.enchantment as enchantment
import dnd.spells.evocation as evocation
import dnd.spells.illusion as illusion
import dnd.spells.necromancy as necromancy
import dnd.spells.transmutation as transmutation
from dnd.spells.content_metadata import (
    SpellCatalogAoeShapeType,
    SpellCatalogAoeSpec,
    SpellCatalogDelivery,
    SpellCatalogMetadata,
    SpellCatalogMultiTargetSpec,
    SpellCatalogProjectileType,
    SpellCatalogRangeType,
    SpellCatalogSavingThrowSpec,
    SpellCatalogTargetType,
    attach_spell_catalog_metadata,
    get_spell_catalog_metadata,
    neurodragon_spell_identity,
    srd_spell_identity,
)


SRD_SPELL_PACK_ID = "content.srd_5_1_cc"
NEURODRAGON_SPELL_PACK_ID = "content.neurodragon"


@dataclass(frozen=True, slots=True)
class SpellContentIdentitySpec:
    """One checked-in public spell name/class/content-identity association."""

    display_name: str
    spell_type: type[SpellAction]
    pack_id: str
    content_id: str
    school: str
    level: int
    source_page: int | None
    sort_order: int
    icon_key: str | None = None


def _saving_throws(
    *abilities: AbilityName,
) -> tuple[SpellCatalogSavingThrowSpec, ...]:
    """Build the authored ordered save list for one catalog row."""
    return tuple(
        SpellCatalogSavingThrowSpec(
            ability=ability,
            dc_source="caster_spell_save_dc",
        )
        for ability in abilities
    )


def _area(
    shape: SpellCatalogAoeShapeType,
    *,
    radius_ft: int | None = None,
    length_ft: int | None = None,
    width_ft: int | None = None,
    height_ft: int | None = None,
) -> SpellCatalogAoeSpec:
    """Build one explicitly dimensioned primary spell area."""
    return SpellCatalogAoeSpec(
        shape=shape,
        radius_ft=radius_ft,
        length_ft=length_ft,
        width_ft=width_ft,
        height_ft=height_ft,
    )


def _multi_target(
    min_targets: int,
    max_targets: int,
    allow_same_target: bool,
    *,
    projectiles_per_cast: int | None = None,
) -> SpellCatalogMultiTargetSpec:
    """Build exact base-cast allocation metadata for a multi-target spell."""
    return SpellCatalogMultiTargetSpec(
        min_targets=min_targets,
        max_targets=max_targets,
        allow_same_target=allow_same_target,
        projectiles_per_cast=projectiles_per_cast,
    )


def _catalog(
    catalog_id: str,
    description: str,
    target_type: SpellCatalogTargetType,
    range_type: SpellCatalogRangeType,
    range_ft: int,
    delivery: SpellCatalogDelivery,
    *,
    projectile: SpellCatalogProjectileType | None = None,
    area: SpellCatalogAoeSpec | None = None,
    damage: tuple[DamageType, ...] = (),
    healing: bool = False,
    attack_roll: bool = False,
    saves: tuple[SpellCatalogSavingThrowSpec, ...] = (),
    concentration: bool = False,
    ritual: bool = False,
    verbal: bool = True,
    somatic: bool | None = None,
    material: bool | None = None,
    classes: tuple[str, ...] = (),
    subclasses: tuple[str, ...] = (),
    multi_target: SpellCatalogMultiTargetSpec | None = None,
    tags: tuple[str, ...] = (),
) -> SpellCatalogMetadata:
    """Compose one complete reviewed row without inspecting runtime code."""
    return SpellCatalogMetadata(
        catalog_id=catalog_id,
        description=description,
        target_type=target_type,
        range_type=range_type,
        range_ft=range_ft,
        delivery=delivery,
        projectile_type=projectile,
        aoe=area,
        damage_types=damage,
        healing=healing,
        attack_roll=attack_roll,
        saving_throws=saves,
        concentration=concentration,
        ritual=ritual,
        verbal=verbal,
        somatic=somatic,
        material=material,
        classes=classes,
        subclasses=subclasses,
        multi_target=multi_target,
        recommended_asset_tags=tags,
    )


SPELL_CONTENT_IDENTITY_SPECS: tuple[SpellContentIdentitySpec, ...] = (
    SpellContentIdentitySpec("Fire Bolt", evocation.FireBolt, SRD_SPELL_PACK_ID, "spell.fire_bolt", "evocation", 0, 144, 10),
    SpellContentIdentitySpec("Sacred Flame", evocation.SacredFlame, SRD_SPELL_PACK_ID, "spell.sacred_flame", "evocation", 0, 176, 20),
    SpellContentIdentitySpec("Poison Spray", conjuration.PoisonSpray, SRD_SPELL_PACK_ID, "spell.poison_spray", "conjuration", 0, 169, 30),
    SpellContentIdentitySpec("Ray of Frost", evocation.RayOfFrost, SRD_SPELL_PACK_ID, "spell.ray_of_frost", "evocation", 0, 174, 40),
    SpellContentIdentitySpec("Acid Splash", conjuration.AcidSplash, SRD_SPELL_PACK_ID, "spell.acid_splash", "conjuration", 0, 114, 50),
    SpellContentIdentitySpec("Chill Touch", necromancy.ChillTouch, SRD_SPELL_PACK_ID, "spell.chill_touch", "necromancy", 0, 124, 60),
    SpellContentIdentitySpec("Shocking Grasp", evocation.ShockingGrasp, SRD_SPELL_PACK_ID, "spell.shocking_grasp", "evocation", 0, 179, 70),
    SpellContentIdentitySpec("Eldritch Blast", evocation.EldritchBlast, SRD_SPELL_PACK_ID, "spell.eldritch_blast", "evocation", 0, 139, 80),
    SpellContentIdentitySpec("True Strike", evocation.TrueStrike, SRD_SPELL_PACK_ID, "spell.true_strike", "evocation", 0, 189, 90),
    SpellContentIdentitySpec("Guidance", divination.Guidance, SRD_SPELL_PACK_ID, "spell.guidance", "divination", 0, 151, 100),
    SpellContentIdentitySpec("Light", evocation.Light, SRD_SPELL_PACK_ID, "spell.light", "evocation", 0, 159, 110),
    SpellContentIdentitySpec("Resistance", abjuration.Resistance, SRD_SPELL_PACK_ID, "spell.resistance", "abjuration", 0, 175, 120),
    SpellContentIdentitySpec("Magic Missile", evocation.MagicMissile, SRD_SPELL_PACK_ID, "spell.magic_missile", "evocation", 1, 161, 130),
    SpellContentIdentitySpec("Mage Armor", abjuration.MageArmor, SRD_SPELL_PACK_ID, "spell.mage_armor", "abjuration", 1, 160, 140),
    SpellContentIdentitySpec("Burning Hands", evocation.BurningHands, SRD_SPELL_PACK_ID, "spell.burning_hands", "evocation", 1, 123, 150, "spell.burning-hands"),
    SpellContentIdentitySpec("Thunderwave", evocation.Thunderwave, SRD_SPELL_PACK_ID, "spell.thunderwave", "evocation", 1, 187, 160),
    SpellContentIdentitySpec("False Life", necromancy.FalseLife, SRD_SPELL_PACK_ID, "spell.false_life", "necromancy", 1, 142, 170),
    SpellContentIdentitySpec("Charm Person", enchantment.CharmPerson, SRD_SPELL_PACK_ID, "spell.charm_person", "enchantment", 1, 124, 180),
    SpellContentIdentitySpec("Sleep", enchantment.Sleep, SRD_SPELL_PACK_ID, "spell.sleep", "enchantment", 1, 180, 190),
    SpellContentIdentitySpec("Color Spray", illusion.ColorSpray, SRD_SPELL_PACK_ID, "spell.color_spray", "illusion", 1, 125, 200),
    SpellContentIdentitySpec("Guiding Bolt", evocation.GuidingBolt, SRD_SPELL_PACK_ID, "spell.guiding_bolt", "evocation", 1, 151, 210),
    SpellContentIdentitySpec("Grease", conjuration.Grease, SRD_SPELL_PACK_ID, "spell.grease", "conjuration", 1, 150, 220),
    SpellContentIdentitySpec("Entangle", conjuration.Entangle, SRD_SPELL_PACK_ID, "spell.entangle", "conjuration", 1, 138, 225),
    SpellContentIdentitySpec("Fog Cloud", conjuration.FogCloud, SRD_SPELL_PACK_ID, "spell.fog_cloud", "conjuration", 1, 146, 230),
    SpellContentIdentitySpec("Bane", enchantment.Bane, SRD_SPELL_PACK_ID, "spell.bane", "enchantment", 1, 120, 240),
    SpellContentIdentitySpec("Bless", enchantment.Bless, SRD_SPELL_PACK_ID, "spell.bless", "enchantment", 1, 122, 250),
    SpellContentIdentitySpec("Jump", transmutation.JumpSpell, SRD_SPELL_PACK_ID, "spell.jump", "transmutation", 1, 158, 260),
    SpellContentIdentitySpec("Expeditious Retreat", transmutation.ExpeditiousRetreat, SRD_SPELL_PACK_ID, "spell.expeditious_retreat", "transmutation", 1, 141, 270),
    SpellContentIdentitySpec("Command", enchantment.Command, SRD_SPELL_PACK_ID, "spell.command", "enchantment", 1, 125, 280),
    SpellContentIdentitySpec("Cure Wounds", evocation.CureWounds, SRD_SPELL_PACK_ID, "spell.cure_wounds", "evocation", 1, 132, 290),
    SpellContentIdentitySpec("Healing Word", evocation.HealingWord, SRD_SPELL_PACK_ID, "spell.healing_word", "evocation", 1, 153, 300),
    SpellContentIdentitySpec("Inflict Wounds", necromancy.InflictWounds, SRD_SPELL_PACK_ID, "spell.inflict_wounds", "necromancy", 1, 157, 310),
    SpellContentIdentitySpec("Shield of Faith", abjuration.ShieldOfFaith, SRD_SPELL_PACK_ID, "spell.shield_of_faith", "abjuration", 1, 179, 320),
    SpellContentIdentitySpec("Sanctuary", abjuration.Sanctuary, SRD_SPELL_PACK_ID, "spell.sanctuary", "abjuration", 1, 176, 330),
    SpellContentIdentitySpec("Hold Person", enchantment.HoldPerson, SRD_SPELL_PACK_ID, "spell.hold_person", "enchantment", 2, 154, 340),
    SpellContentIdentitySpec("Shatter", evocation.Shatter, SRD_SPELL_PACK_ID, "spell.shatter", "evocation", 2, 178, 350),
    SpellContentIdentitySpec("Scorching Ray", evocation.ScorchingRay, SRD_SPELL_PACK_ID, "spell.scorching_ray", "evocation", 2, 176, 360),
    SpellContentIdentitySpec("Blur", illusion.Blur, SRD_SPELL_PACK_ID, "spell.blur", "illusion", 2, 123, 370),
    SpellContentIdentitySpec("Misty Step", conjuration.MistyStep, SRD_SPELL_PACK_ID, "spell.misty_step", "conjuration", 2, 165, 380),
    SpellContentIdentitySpec("Blindness/Deafness", necromancy.BlindnessDeafness, SRD_SPELL_PACK_ID, "spell.blindness_deafness", "necromancy", 2, 122, 390),
    SpellContentIdentitySpec("Spike Growth", transmutation.SpikeGrowth, SRD_SPELL_PACK_ID, "spell.spike_growth", "transmutation", 2, 182, 400),
    SpellContentIdentitySpec("Web", conjuration.Web, SRD_SPELL_PACK_ID, "spell.web", "conjuration", 2, 192, 410),
    SpellContentIdentitySpec("Invisibility", illusion.Invisibility, SRD_SPELL_PACK_ID, "spell.invisibility", "illusion", 2, 157, 420),
    SpellContentIdentitySpec("Darkness", conjuration.Darkness, SRD_SPELL_PACK_ID, "spell.darkness", "evocation", 2, 133, 430),
    SpellContentIdentitySpec("Mirror Image", illusion.MirrorImage, SRD_SPELL_PACK_ID, "spell.mirror_image", "illusion", 2, 165, 440),
    SpellContentIdentitySpec("Necrotic Bless", necromancy.NecroticBless, NEURODRAGON_SPELL_PACK_ID, "spell.necrotic_bless", "necromancy", 2, None, 450),
    SpellContentIdentitySpec("Darkvision", transmutation.DarkvisionSpell, SRD_SPELL_PACK_ID, "spell.darkvision", "transmutation", 2, 133, 460),
    SpellContentIdentitySpec("See Invisibility", divination.SeeInvisibility, SRD_SPELL_PACK_ID, "spell.see_invisibility", "divination", 2, 177, 470),
    SpellContentIdentitySpec("Gust of Wind", evocation.GustOfWind, SRD_SPELL_PACK_ID, "spell.gust_of_wind", "evocation", 2, 152, 480),
    SpellContentIdentitySpec("Enhance Ability", transmutation.EnhanceAbility, SRD_SPELL_PACK_ID, "spell.enhance_ability", "transmutation", 2, 139, 490),
    SpellContentIdentitySpec("Enlarge/Reduce", transmutation.EnlargeReduce, SRD_SPELL_PACK_ID, "spell.enlarge_reduce", "transmutation", 2, 140, 500),
    SpellContentIdentitySpec("Silence", illusion.Silence, SRD_SPELL_PACK_ID, "spell.silence", "illusion", 2, 179, 510),
    SpellContentIdentitySpec("Continual Flame", evocation.ContinualFlame, SRD_SPELL_PACK_ID, "spell.continual_flame", "evocation", 2, 130, 520),
    SpellContentIdentitySpec("Prayer of Healing", evocation.PrayerOfHealing, SRD_SPELL_PACK_ID, "spell.prayer_of_healing", "evocation", 2, 170, 530),
    SpellContentIdentitySpec("Lesser Restoration", abjuration.LesserRestoration, SRD_SPELL_PACK_ID, "spell.lesser_restoration", "abjuration", 2, 158, 540),
    SpellContentIdentitySpec("Protection from Poison", abjuration.ProtectionFromPoison, SRD_SPELL_PACK_ID, "spell.protection_from_poison", "abjuration", 2, 173, 550),
    SpellContentIdentitySpec("Aid", abjuration.Aid, SRD_SPELL_PACK_ID, "spell.aid", "abjuration", 2, 114, 560),
    SpellContentIdentitySpec("Call Lightning", conjuration.CallLightning, SRD_SPELL_PACK_ID, "spell.call_lightning", "conjuration", 3, 123, 570),
    SpellContentIdentitySpec("Fireball", evocation.Fireball, SRD_SPELL_PACK_ID, "spell.fireball", "evocation", 3, 144, 580),
    SpellContentIdentitySpec("Lightning Bolt", evocation.LightningBolt, SRD_SPELL_PACK_ID, "spell.lightning_bolt", "evocation", 3, 159, 590, "spell.lightning-bolt"),
    SpellContentIdentitySpec("Protection from Energy", abjuration.ProtectionFromEnergy, SRD_SPELL_PACK_ID, "spell.protection_from_energy", "abjuration", 3, 173, 600),
    SpellContentIdentitySpec("Fear", illusion.Fear, SRD_SPELL_PACK_ID, "spell.fear", "illusion", 3, 142, 610),
    SpellContentIdentitySpec("Hypnotic Pattern", illusion.HypnoticPattern, SRD_SPELL_PACK_ID, "spell.hypnotic_pattern", "illusion", 3, 155, 620),
    SpellContentIdentitySpec("Spirit Guardians", conjuration.SpiritGuardians, SRD_SPELL_PACK_ID, "spell.spirit_guardians", "conjuration", 3, 182, 630),
    SpellContentIdentitySpec("Daylight", conjuration.Daylight, SRD_SPELL_PACK_ID, "spell.daylight", "evocation", 3, 133, 640),
    SpellContentIdentitySpec("Slow", transmutation.Slow, SRD_SPELL_PACK_ID, "spell.slow", "transmutation", 3, 180, 650),
    SpellContentIdentitySpec("Haste", transmutation.Haste, SRD_SPELL_PACK_ID, "spell.haste", "transmutation", 3, 153, 660),
    SpellContentIdentitySpec("Stinking Cloud", conjuration.StinkingCloud, SRD_SPELL_PACK_ID, "spell.stinking_cloud", "conjuration", 3, 182, 670),
    SpellContentIdentitySpec("Sleet Storm", conjuration.SleetStorm, SRD_SPELL_PACK_ID, "spell.sleet_storm", "conjuration", 3, 180, 680),
    SpellContentIdentitySpec("Mass Healing Word", evocation.MassHealingWord, SRD_SPELL_PACK_ID, "spell.mass_healing_word", "evocation", 3, 163, 690),
    SpellContentIdentitySpec("Beacon of Hope", abjuration.BeaconOfHope, SRD_SPELL_PACK_ID, "spell.beacon_of_hope", "abjuration", 3, 121, 700),
    SpellContentIdentitySpec("Remove Curse", abjuration.RemoveCurse, SRD_SPELL_PACK_ID, "spell.remove_curse", "abjuration", 3, 174, 710),
    SpellContentIdentitySpec("Bestow Curse", necromancy.BestowCurse, SRD_SPELL_PACK_ID, "spell.bestow_curse", "necromancy", 3, 121, 720),
    SpellContentIdentitySpec("Blight", necromancy.Blight, SRD_SPELL_PACK_ID, "spell.blight", "necromancy", 4, 122, 730),
    SpellContentIdentitySpec("Stoneskin", abjuration.Stoneskin, SRD_SPELL_PACK_ID, "spell.stoneskin", "abjuration", 4, 183, 740),
    SpellContentIdentitySpec("Greater Invisibility", illusion.GreaterInvisibility, SRD_SPELL_PACK_ID, "spell.greater_invisibility", "illusion", 4, 150, 750),
    SpellContentIdentitySpec("Ice Storm", evocation.IceStorm, SRD_SPELL_PACK_ID, "spell.ice_storm", "evocation", 4, 155, 760),
    SpellContentIdentitySpec("Dimension Door", conjuration.DimensionDoor, SRD_SPELL_PACK_ID, "spell.dimension_door", "conjuration", 4, 135, 770),
    SpellContentIdentitySpec("Banishment", abjuration.Banishment, SRD_SPELL_PACK_ID, "spell.banishment", "abjuration", 4, 120, 780),
    SpellContentIdentitySpec("Guardian of Faith", conjuration.GuardianOfFaith, SRD_SPELL_PACK_ID, "spell.guardian_of_faith", "conjuration", 4, 150, 790),
    SpellContentIdentitySpec("Evard's Black Tentacles", conjuration.EvardsBlackTentacles, SRD_SPELL_PACK_ID, "spell.evards_black_tentacles", "conjuration", 4, 123, 795),
    SpellContentIdentitySpec("Death Ward", abjuration.DeathWard, SRD_SPELL_PACK_ID, "spell.death_ward", "abjuration", 4, 133, 800),
    SpellContentIdentitySpec("Freedom of Movement", abjuration.FreedomOfMovement, SRD_SPELL_PACK_ID, "spell.freedom_of_movement", "abjuration", 4, 147, 810),
    SpellContentIdentitySpec("Hold Monster", enchantment.HoldMonster, SRD_SPELL_PACK_ID, "spell.hold_monster", "enchantment", 5, 154, 820),
    SpellContentIdentitySpec("Cone of Cold", evocation.ConeOfCold, SRD_SPELL_PACK_ID, "spell.cone_of_cold", "evocation", 5, 127, 830),
    SpellContentIdentitySpec("Cloudkill", conjuration.Cloudkill, SRD_SPELL_PACK_ID, "spell.cloudkill", "conjuration", 5, 125, 840),
    SpellContentIdentitySpec("Insect Plague", conjuration.InsectPlague, SRD_SPELL_PACK_ID, "spell.insect_plague", "conjuration", 5, 157, 850),
    SpellContentIdentitySpec("Telekinesis", transmutation.Telekinesis, SRD_SPELL_PACK_ID, "spell.telekinesis", "transmutation", 5, 185, 860),
    SpellContentIdentitySpec("Flame Strike", evocation.FlameStrike, SRD_SPELL_PACK_ID, "spell.flame_strike", "evocation", 5, 145, 870),
    SpellContentIdentitySpec("Mass Cure Wounds", evocation.MassCureWounds, SRD_SPELL_PACK_ID, "spell.mass_cure_wounds", "evocation", 5, 162, 880),
    SpellContentIdentitySpec("Greater Restoration", abjuration.GreaterRestoration, SRD_SPELL_PACK_ID, "spell.greater_restoration", "abjuration", 5, 150, 890),
    SpellContentIdentitySpec("Circle of Death", evocation.CircleOfDeath, SRD_SPELL_PACK_ID, "spell.circle_of_death", "necromancy", 6, 124, 900),
    SpellContentIdentitySpec("Disintegrate", transmutation.Disintegrate, SRD_SPELL_PACK_ID, "spell.disintegrate", "transmutation", 6, 135, 910),
    SpellContentIdentitySpec("True Seeing", divination.TrueSeeing, SRD_SPELL_PACK_ID, "spell.true_seeing", "divination", 6, 189, 920),
    SpellContentIdentitySpec("Sunbeam", evocation.Sunbeam, SRD_SPELL_PACK_ID, "spell.sunbeam", "evocation", 6, 184, 930),
    SpellContentIdentitySpec("Chain Lightning", evocation.ChainLightning, SRD_SPELL_PACK_ID, "spell.chain_lightning", "evocation", 6, 124, 940),
    SpellContentIdentitySpec("Eyebite", necromancy.Eyebite, SRD_SPELL_PACK_ID, "spell.eyebite", "necromancy", 6, 141, 950),
    SpellContentIdentitySpec("Globe of Invulnerability", abjuration.GlobeOfInvulnerability, SRD_SPELL_PACK_ID, "spell.globe_of_invulnerability", "abjuration", 6, 149, 960),
    SpellContentIdentitySpec("Heal", evocation.HealSpell, SRD_SPELL_PACK_ID, "spell.heal", "evocation", 6, 153, 970),
    SpellContentIdentitySpec("Harm", necromancy.Harm, SRD_SPELL_PACK_ID, "spell.harm", "necromancy", 6, 153, 980),
    SpellContentIdentitySpec("Heroes' Feast", conjuration.HeroesFeast, SRD_SPELL_PACK_ID, "spell.heroes_feast", "conjuration", 6, 154, 990),
    SpellContentIdentitySpec("Prismatic Spray", evocation.PrismaticSpray, SRD_SPELL_PACK_ID, "spell.prismatic_spray", "evocation", 7, 170, 1000),
    SpellContentIdentitySpec("Finger of Death", necromancy.FingerOfDeath, SRD_SPELL_PACK_ID, "spell.finger_of_death", "necromancy", 7, 144, 1010),
    SpellContentIdentitySpec("Regenerate", transmutation.Regenerate, SRD_SPELL_PACK_ID, "spell.regenerate", "transmutation", 7, 174, 1020),
    SpellContentIdentitySpec("Divine Word", evocation.DivineWord, SRD_SPELL_PACK_ID, "spell.divine_word", "evocation", 7, 137, 1030),
    SpellContentIdentitySpec("Sunburst", evocation.Sunburst, SRD_SPELL_PACK_ID, "spell.sunburst", "evocation", 8, 184, 1040),
    SpellContentIdentitySpec("Power Word Stun", enchantment.PowerWordStun, SRD_SPELL_PACK_ID, "spell.power_word_stun", "enchantment", 8, 170, 1050),
    SpellContentIdentitySpec("Incendiary Cloud", conjuration.IncendiaryCloud, SRD_SPELL_PACK_ID, "spell.incendiary_cloud", "conjuration", 8, 157, 1060),
    SpellContentIdentitySpec("Antimagic Field", abjuration.AntimagicField, SRD_SPELL_PACK_ID, "spell.antimagic_field", "abjuration", 8, 117, 1070),
    SpellContentIdentitySpec("Power Word Kill", enchantment.PowerWordKill, SRD_SPELL_PACK_ID, "spell.power_word_kill", "enchantment", 9, 170, 1080),
    SpellContentIdentitySpec("Mass Heal", evocation.MassHeal, SRD_SPELL_PACK_ID, "spell.mass_heal", "evocation", 9, 163, 1090),
)

SPELL_CONTENT_IDENTITY_BY_CLASS = MappingProxyType({
    spec.spell_type: spec
    for spec in SPELL_CONTENT_IDENTITY_SPECS
})
SPELL_CONTENT_IDENTITY_BY_NAME = MappingProxyType({
    spec.display_name: spec
    for spec in SPELL_CONTENT_IDENTITY_SPECS
})
SPELL_CONTENT_IDENTITY_BY_REF_KEY = MappingProxyType({
    (spec.pack_id, spec.content_id, 1): spec
    for spec in SPELL_CONTENT_IDENTITY_SPECS
})
if (
    len(SPELL_CONTENT_IDENTITY_BY_CLASS)
    != len(SPELL_CONTENT_IDENTITY_SPECS)
    or len(SPELL_CONTENT_IDENTITY_BY_NAME)
    != len(SPELL_CONTENT_IDENTITY_SPECS)
    or len(SPELL_CONTENT_IDENTITY_BY_REF_KEY)
    != len(SPELL_CONTENT_IDENTITY_SPECS)
):
    raise ValueError("Spell content identity table contains duplicate keys")

SPELL_CATALOG_METADATA_SPECS: tuple[
    tuple[type[SpellAction], SpellCatalogMetadata],
    ...,
] = (
    (evocation.FireBolt, _catalog(
        'fire_bolt', 'Hurl a mote of fire at a target', 'entity', 'ranged', 120, 'single_projectile',
        projectile='bolt', damage=(DamageType.FIRE,), attack_roll=True, classes=('wizard', 'sorcerer', 'warlock'), tags=('fire', 'bolt'),
    )),
    (evocation.SacredFlame, _catalog(
        'sacred_flame', 'Target must succeed on DEX save or take radiant damage', 'entity', 'ranged', 60, 'single_projectile',
        projectile='radiance', damage=(DamageType.RADIANT,), saves=_saving_throws(AbilityName.DEXTERITY), tags=('radiant', 'radiance'),
    )),
    (conjuration.PoisonSpray, _catalog(
        'poison_spray', 'CON save or 1d12 poison (10ft range)', 'entity', 'ranged', 10, 'single_projectile',
        projectile='spray', damage=(DamageType.POISON,), saves=_saving_throws(AbilityName.CONSTITUTION), tags=('poison', 'spray'),
    )),
    (evocation.RayOfFrost, _catalog(
        'ray_of_frost', 'Ranged spell attack, 1d8 cold, target speed -10ft', 'entity', 'ranged', 60, 'ray',
        projectile='ray', damage=(DamageType.COLD,), attack_roll=True, tags=('cold', 'ray'),
    )),
    (conjuration.AcidSplash, _catalog(
        'acid_splash', '1-2 targets within 5ft of each other, DEX save or 1d6 acid', 'multi_entity', 'ranged', 60, 'missile_volley',
        projectile='orb', damage=(DamageType.ACID,), saves=_saving_throws(AbilityName.DEXTERITY), multi_target=_multi_target(1, 2, False, projectiles_per_cast=2), tags=('acid', 'orb'),
    )),
    (necromancy.ChillTouch, _catalog(
        'chill_touch', "1d8 necrotic, target can't heal. Undead: disadvantage vs caster.", 'entity', 'ranged', 120, 'single_projectile',
        projectile='orb', damage=(DamageType.NECROTIC,), attack_roll=True, tags=('necrotic', 'orb'),
    )),
    (evocation.ShockingGrasp, _catalog(
        'shocking_grasp', 'Melee spell attack, 1d8 lightning, advantage vs metal armor, no reactions', 'entity', 'touch', 5, 'touch',
        projectile='touch', damage=(DamageType.LIGHTNING,), attack_roll=True, tags=('lightning', 'touch'),
    )),
    (evocation.EldritchBlast, _catalog(
        'eldritch_blast', 'A beam of crackling force energy', 'entity', 'ranged', 120, 'beam',
        projectile='beam', damage=(DamageType.FORCE,), attack_roll=True, tags=('force', 'beam'),
    )),
    (evocation.TrueStrike, _catalog(
        'true_strike', 'Weapon attack using spellcasting ability, +radiant damage at higher levels', 'entity', 'touch', 5, 'touch',
        damage=(DamageType.RADIANT,), tags=('radiant',),
    )),
    (divination.Guidance, _catalog(
        'guidance', 'Touch: +1d4 to one ability check (concentration)', 'entity', 'touch', 5, 'touch',
        concentration=True, tags=('concentration',),
    )),
    (evocation.Light, _catalog(
        'light', 'Touch: object sheds 20ft bright + 20ft dim light (concentration)', 'entity', 'touch', 5, 'touch',
        concentration=True, tags=('concentration',),
    )),
    (abjuration.Resistance, _catalog(
        'resistance', 'Add 1d4 to one saving throw (one use)', 'entity', 'touch', 5, 'touch',
        concentration=True, tags=('concentration',),
    )),
    (evocation.MagicMissile, _catalog(
        'magic_missile', 'Three darts of force that automatically hit', 'multi_entity', 'ranged', 120, 'missile_volley',
        projectile='dart', damage=(DamageType.FORCE,), classes=('wizard', 'sorcerer'), multi_target=_multi_target(1, 3, True, projectiles_per_cast=3), tags=('force', 'dart'),
    )),
    (abjuration.MageArmor, _catalog(
        'mage_armor', "Target's AC becomes 13 + DEX modifier", 'entity', 'touch', 5, 'touch',
    )),
    (evocation.BurningHands, _catalog(
        'burning_hands', '15ft cone of fire dealing 3d6 fire damage (DEX save half)', 'position_aoe', 'self', 0, 'aoe',
        area=_area('cone', length_ft=15), damage=(DamageType.FIRE,), saves=_saving_throws(AbilityName.DEXTERITY), tags=('fire', 'cone'),
    )),
    (evocation.Thunderwave, _catalog(
        'thunderwave', '15ft cube dealing 2d8 thunder + 10ft push on fail (CON save)', 'position_aoe', 'self', 0, 'aoe',
        area=_area('cube', length_ft=15, width_ft=15, height_ft=15), damage=(DamageType.THUNDER,), saves=_saving_throws(AbilityName.CONSTITUTION), tags=('thunder', 'cube'),
    )),
    (necromancy.FalseLife, _catalog(
        'false_life', 'Gain 1d4+4 temporary hit points (+5 per upcast level)', 'self', 'self', 0, 'self',
    )),
    (enchantment.CharmPerson, _catalog(
        'charm_person', 'WIS save or charmed. Advantage if fighting.', 'multi_entity', 'ranged', 30, 'none',
        saves=_saving_throws(AbilityName.WISDOM), multi_target=_multi_target(1, 1, False),
    )),
    (enchantment.Sleep, _catalog(
        'sleep', 'Roll 5d8 HP pool. Affects creatures in order of lowest HP.', 'position_aoe', 'ranged', 90, 'aoe',
        area=_area('sphere', radius_ft=20), tags=('sphere',),
    )),
    (illusion.ColorSpray, _catalog(
        'color_spray', 'Roll 6d10 HP pool. Affects creatures in order of lowest HP.', 'position_aoe', 'self', 0, 'aoe',
        area=_area('cone', length_ft=15), tags=('cone',),
    )),
    (evocation.GuidingBolt, _catalog(
        'guiding_bolt', 'Ranged spell attack, 4d6 radiant, next attack has advantage', 'entity', 'ranged', 120, 'single_projectile',
        projectile='bolt', damage=(DamageType.RADIANT,), attack_roll=True, tags=('radiant', 'bolt'),
    )),
    (conjuration.Grease, _catalog(
        'grease', '10ft square difficult terrain, DEX save or prone', 'position', 'ranged', 60, 'aoe',
        area=_area('cube', length_ft=10, width_ft=10, height_ft=10), saves=_saving_throws(AbilityName.DEXTERITY), tags=('cube',),
    )),
    (conjuration.Entangle, _catalog(
        'entangle', '20ft square difficult terrain; STR save or restrained', 'position', 'ranged', 90, 'aoe',
        area=_area('cube', length_ft=20, width_ft=20, height_ft=20), saves=_saving_throws(AbilityName.STRENGTH), concentration=True, tags=('cube', 'concentration'),
    )),
    (conjuration.FogCloud, _catalog(
        'fog_cloud', '20ft sphere heavily obscured fog (blocks darkvision)', 'position', 'ranged', 120, 'aoe',
        area=_area('sphere', radius_ft=20), concentration=True, tags=('sphere', 'concentration'),
    )),
    (enchantment.Bane, _catalog(
        'bane', 'Up to 3 enemies: CHA save or -1d4 on attacks and saves', 'multi_entity', 'ranged', 30, 'none',
        saves=_saving_throws(AbilityName.CHARISMA), concentration=True, multi_target=_multi_target(1, 3, False), tags=('concentration',),
    )),
    (enchantment.Bless, _catalog(
        'bless', 'Up to 3 allies: +1d4 on attacks and saves', 'multi_entity', 'ranged', 30, 'none',
        concentration=True, multi_target=_multi_target(1, 3, False), tags=('concentration',),
    )),
    (transmutation.JumpSpell, _catalog(
        'jump', "Triple a creature's jump distance", 'entity', 'touch', 5, 'touch',
    )),
    (transmutation.ExpeditiousRetreat, _catalog(
        'expeditious_retreat', 'Bonus action Dash each turn', 'self', 'self', 0, 'self',
        concentration=True, tags=('concentration',),
    )),
    (enchantment.Command, _catalog(
        'command', 'WIS save or follow a one-word command (Grovel/Flee/Halt)', 'entity', 'ranged', 60, 'none',
        saves=_saving_throws(AbilityName.WISDOM),
    )),
    (evocation.CureWounds, _catalog(
        'cure_wounds', 'Touch a creature to restore 1d8 + modifier HP', 'entity', 'touch', 5, 'touch',
        healing=True,
    )),
    (evocation.HealingWord, _catalog(
        'healing_word', 'Bonus action: heal a creature for 1d4 + modifier HP at 60ft', 'entity', 'ranged', 60, 'none',
        healing=True,
    )),
    (necromancy.InflictWounds, _catalog(
        'inflict_wounds', 'Melee spell attack, 3d10 necrotic', 'entity', 'touch', 5, 'touch',
        projectile='touch', damage=(DamageType.NECROTIC,), attack_roll=True, tags=('necrotic', 'touch'),
    )),
    (abjuration.ShieldOfFaith, _catalog(
        'shield_of_faith', '+2 AC bonus (concentration)', 'entity', 'ranged', 60, 'none',
        concentration=True, tags=('concentration',),
    )),
    (abjuration.Sanctuary, _catalog(
        'sanctuary', 'Ward: attackers must WIS save; breaks on offensive action', 'entity', 'ranged', 30, 'none',
        saves=_saving_throws(AbilityName.WISDOM),
    )),
    (enchantment.HoldPerson, _catalog(
        'hold_person', 'Target must succeed on WIS save or be paralyzed', 'entity', 'ranged', 60, 'none',
        saves=_saving_throws(AbilityName.WISDOM), concentration=True, tags=('concentration',),
    )),
    (evocation.Shatter, _catalog(
        'shatter', '10ft radius sphere dealing 3d8 thunder damage (CON save half)', 'position_aoe', 'ranged', 60, 'aoe_projectile',
        projectile='orb', area=_area('sphere', radius_ft=10), damage=(DamageType.THUNDER,), saves=_saving_throws(AbilityName.CONSTITUTION), tags=('thunder', 'orb', 'sphere'),
    )),
    (evocation.ScorchingRay, _catalog(
        'scorching_ray', '3 rays, each 2d6 fire, ranged spell attack per ray', 'multi_entity', 'ranged', 120, 'ray',
        projectile='ray', damage=(DamageType.FIRE,), attack_roll=True, multi_target=_multi_target(1, 3, True, projectiles_per_cast=3), tags=('fire', 'ray'),
    )),
    (illusion.Blur, _catalog(
        'blur', 'Concentration. Attackers have disadvantage against you.', 'self', 'self', 0, 'self',
        concentration=True, tags=('concentration',),
    )),
    (conjuration.MistyStep, _catalog(
        'misty_step', 'Bonus action teleport up to 30ft to a visible space', 'position', 'self', 0, 'self',
    )),
    (necromancy.BlindnessDeafness, _catalog(
        'blindness_deafness', 'CON save or Blinded/Deafened. Repeat save each turn.', 'multi_entity', 'ranged', 30, 'none',
        saves=_saving_throws(AbilityName.CONSTITUTION), multi_target=_multi_target(1, 1, False),
    )),
    (transmutation.SpikeGrowth, _catalog(
        'spike_growth', '20ft radius difficult terrain, 2d4 piercing per 5ft traveled', 'position', 'ranged', 150, 'aoe',
        area=_area('sphere', radius_ft=20), damage=(DamageType.PIERCING,), concentration=True, tags=('piercing', 'sphere', 'concentration'),
    )),
    (conjuration.Web, _catalog(
        'web', '20ft cube of webs, DEX save or restrained, can escape with STR check', 'position', 'ranged', 60, 'aoe',
        area=_area('cube', length_ft=20, width_ft=20, height_ft=20), saves=_saving_throws(AbilityName.DEXTERITY), concentration=True, tags=('cube', 'concentration'),
    )),
    (illusion.Invisibility, _catalog(
        'invisibility', 'Concentration. Touch target becomes invisible until attacking or casting.', 'entity', 'touch', 5, 'touch',
        concentration=True, tags=('concentration',),
    )),
    (conjuration.Darkness, _catalog(
        'darkness', '15ft sphere magical darkness (blocks darkvision)', 'position', 'ranged', 60, 'aoe',
        area=_area('sphere', radius_ft=15), concentration=True, tags=('sphere', 'concentration'),
    )),
    (illusion.MirrorImage, _catalog(
        'mirror_image', '3 duplicates, +3 AC each, lost on evade', 'self', 'self', 0, 'self',
    )),
    (necromancy.NecroticBless, _catalog(
        'necrotic_bless', '4 targets: undead get +1d4, others CHA save or -1d4', 'multi_entity', 'ranged', 30, 'none',
        saves=_saving_throws(AbilityName.CHARISMA), concentration=True, multi_target=_multi_target(1, 4, False), tags=('concentration',),
    )),
    (transmutation.DarkvisionSpell, _catalog(
        'darkvision', 'Grant 60ft darkvision to a willing creature', 'entity', 'touch', 5, 'touch',
    )),
    (divination.SeeInvisibility, _catalog(
        'see_invisibility', 'See invisible creatures and objects', 'self', 'self', 0, 'self',
    )),
    (evocation.GustOfWind, _catalog(
        'gust_of_wind', '60ft line of wind, STR save or pushed 15ft, difficult terrain', 'position_aoe', 'self', 0, 'aoe',
        area=_area('line', length_ft=60, width_ft=10), saves=_saving_throws(AbilityName.STRENGTH), concentration=True, tags=('line', 'concentration'),
    )),
    (transmutation.EnhanceAbility, _catalog(
        'enhance_ability', "Advantage on one ability's checks (concentration)", 'entity', 'touch', 5, 'touch',
        concentration=True, tags=('concentration',),
    )),
    (transmutation.EnlargeReduce, _catalog(
        'enlarge_reduce', 'Change creature size, STR advantage/disadvantage, +/-1d4 weapon damage', 'entity', 'ranged', 30, 'none',
        saves=_saving_throws(AbilityName.CONSTITUTION), concentration=True, tags=('concentration',),
    )),
    (illusion.Silence, _catalog(
        'silence', '20ft sphere: no sound, blocks verbal spells, deafens (concentration)', 'position', 'ranged', 120, 'aoe',
        area=_area('sphere', radius_ft=20), concentration=True, tags=('sphere', 'concentration'),
    )),
    (evocation.ContinualFlame, _catalog(
        'continual_flame', 'Touch: permanent 20ft bright + 20ft dim light on object', 'position', 'touch', 5, 'touch',
    )),
    (evocation.PrayerOfHealing, _catalog(
        'prayer_of_healing', 'Heal up to 6 allies for 2d8 + modifier HP', 'multi_entity', 'ranged', 30, 'none',
        healing=True, multi_target=_multi_target(1, 6, False),
    )),
    (abjuration.LesserRestoration, _catalog(
        'lesser_restoration', 'Touch: remove one disease or one of blinded, deafened, paralyzed, or poisoned', 'entity', 'touch', 5, 'touch',
    )),
    (abjuration.ProtectionFromPoison, _catalog(
        'protection_from_poison', 'Touch: resist poison damage, immune to Poisoned', 'entity', 'touch', 5, 'touch',
    )),
    (abjuration.Aid, _catalog(
        'aid', 'Increase max HP by 5 per level above 1st for 3 targets', 'multi_entity', 'ranged', 30, 'none',
        multi_target=_multi_target(1, 1, True),
    )),
    (conjuration.CallLightning, _catalog(
        'call_lightning', 'Summon storm cloud, strike with lightning each turn', 'entity', 'ranged', 120, 'single_projectile',
        projectile='bolt', damage=(DamageType.LIGHTNING,), saves=_saving_throws(AbilityName.DEXTERITY), concentration=True, tags=('lightning', 'bolt', 'concentration'),
    )),
    (evocation.Fireball, _catalog(
        'fireball', '20ft radius explosion dealing 8d6 fire damage (DEX save half)', 'position_aoe', 'ranged', 150, 'aoe_projectile',
        projectile='orb', area=_area('sphere', radius_ft=20), damage=(DamageType.FIRE,), saves=_saving_throws(AbilityName.DEXTERITY), classes=('wizard', 'sorcerer'), tags=('fire', 'orb', 'explosion'),
    )),
    (evocation.LightningBolt, _catalog(
        'lightning_bolt', '100ft×5ft line dealing 8d6 lightning damage (DEX save half)', 'position_aoe', 'self', 0, 'aoe',
        area=_area('line', length_ft=100, width_ft=5), damage=(DamageType.LIGHTNING,), saves=_saving_throws(AbilityName.DEXTERITY), tags=('lightning', 'line'),
    )),
    (abjuration.ProtectionFromEnergy, _catalog(
        'protection_from_energy', 'Grant resistance to one energy type (acid/cold/fire/lightning/thunder)', 'entity', 'touch', 5, 'touch',
        concentration=True, tags=('concentration',),
    )),
    (illusion.Fear, _catalog(
        'fear', '30ft cone, WIS save or Frightened + must Dash away', 'position_aoe', 'self', 0, 'aoe',
        area=_area('cone', length_ft=30), saves=_saving_throws(AbilityName.WISDOM), concentration=True, tags=('cone', 'concentration'),
    )),
    (illusion.HypnoticPattern, _catalog(
        'hypnotic_pattern', '30ft cube, WIS save or Charmed + Incapacitated', 'position_aoe', 'ranged', 120, 'aoe_projectile',
        projectile='orb', area=_area('cube', length_ft=30, width_ft=30, height_ft=30), saves=_saving_throws(AbilityName.WISDOM), concentration=True, tags=('orb', 'cube', 'concentration'),
    )),
    (conjuration.SpiritGuardians, _catalog(
        'spirit_guardians', '15ft sphere around caster, enemies take 3d8 radiant (WIS half), speed halved', 'self', 'self', 0, 'aoe',
        area=_area('sphere', radius_ft=15), damage=(DamageType.RADIANT,), saves=_saving_throws(AbilityName.WISDOM), concentration=True, tags=('radiant', 'sphere', 'concentration'),
    )),
    (conjuration.Daylight, _catalog(
        'daylight', '60ft sphere very bright light, reveals hidden, dispels darkness', 'position', 'ranged', 60, 'aoe',
        area=_area('sphere', radius_ft=60), tags=('sphere',),
    )),
    (transmutation.Slow, _catalog(
        'slow', '40ft cube, WIS save or Slowed', 'position_aoe', 'ranged', 120, 'aoe',
        area=_area('cube', length_ft=40, width_ft=40, height_ft=40), saves=_saving_throws(AbilityName.WISDOM), concentration=True, tags=('cube', 'concentration'),
    )),
    (transmutation.Haste, _catalog(
        'haste', 'Double speed, +2 AC, DEX advantage, and one restricted action', 'entity', 'ranged', 30, 'none',
        concentration=True, tags=('concentration',),
    )),
    (conjuration.StinkingCloud, _catalog(
        'stinking_cloud', '20ft sphere nauseating fog, CON save or spend action', 'position', 'ranged', 90, 'aoe',
        area=_area('sphere', radius_ft=20), saves=_saving_throws(AbilityName.CONSTITUTION), concentration=True, tags=('sphere', 'concentration'),
    )),
    (conjuration.SleetStorm, _catalog(
        'sleet_storm', '40ft cylinder: difficult terrain, heavily obscured, DEX save/prone, conc disruption', 'position', 'ranged', 150, 'aoe',
        area=_area('cylinder', radius_ft=40, height_ft=20), saves=_saving_throws(AbilityName.DEXTERITY, AbilityName.CONSTITUTION), concentration=True, tags=('cylinder', 'concentration'),
    )),
    (evocation.MassHealingWord, _catalog(
        'mass_healing_word', 'Bonus action: heal up to 6 allies for 1d4 + modifier HP', 'multi_entity', 'ranged', 60, 'none',
        healing=True, multi_target=_multi_target(1, 6, False),
    )),
    (abjuration.BeaconOfHope, _catalog(
        'beacon_of_hope', 'Advantage on WIS saves; maximize healing received', 'multi_entity', 'ranged', 30, 'none',
        concentration=True, multi_target=_multi_target(1, 1, True), tags=('concentration',),
    )),
    (abjuration.RemoveCurse, _catalog(
        'remove_curse', 'Touch: remove all curses from a creature', 'entity', 'touch', 5, 'touch',
    )),
    (necromancy.BestowCurse, _catalog(
        'bestow_curse', 'Touch: WIS save or be cursed (concentration)', 'entity', 'touch', 5, 'touch',
        projectile='touch', saves=_saving_throws(AbilityName.WISDOM), concentration=True, tags=('touch', 'concentration'),
    )),
    (necromancy.Blight, _catalog(
        'blight', '8d8 necrotic, CON save half. No effect on undead/constructs. Plants: disadvantage + max damage.', 'entity', 'ranged', 30, 'ray',
        projectile='ray', damage=(DamageType.NECROTIC,), saves=_saving_throws(AbilityName.CONSTITUTION), tags=('necrotic', 'ray'),
    )),
    (abjuration.Stoneskin, _catalog(
        'stoneskin', 'Grant resistance to B/P/S damage', 'entity', 'touch', 5, 'touch',
        concentration=True, tags=('concentration',),
    )),
    (illusion.GreaterInvisibility, _catalog(
        'greater_invisibility', 'Concentration. Touch target becomes invisible, Stealth check to maintain on attack/cast.', 'entity', 'touch', 5, 'touch',
        concentration=True, tags=('concentration',),
    )),
    (evocation.IceStorm, _catalog(
        'ice_storm', '20ft cylinder: 2d8 bludg + 4d6 cold (DEX half), difficult terrain 1 round', 'position_aoe', 'ranged', 60, 'aoe_projectile',
        projectile='rain', area=_area('cylinder', radius_ft=20, height_ft=40), damage=(DamageType.BLUDGEONING, DamageType.COLD), saves=_saving_throws(AbilityName.DEXTERITY), tags=('ice', 'hail', 'storm'),
    )),
    (conjuration.DimensionDoor, _catalog(
        'dimension_door', 'Teleport to a visible position within 500ft', 'position', 'ranged', 500, 'none',
    )),
    (abjuration.Banishment, _catalog(
        'banishment', 'CHA save or banished (removed from play), concentration', 'entity', 'ranged', 60, 'none',
        saves=_saving_throws(AbilityName.CHARISMA), concentration=True, tags=('concentration',),
    )),
    (conjuration.GuardianOfFaith, _catalog(
        'guardian_of_faith', 'Summon spectral guardian: 20 radiant (DEX half), 60 damage budget', 'position', 'ranged', 30, 'aoe',
        area=_area('sphere', radius_ft=10), damage=(DamageType.RADIANT,), saves=_saving_throws(AbilityName.DEXTERITY), tags=('radiant', 'sphere'),
    )),
    (conjuration.EvardsBlackTentacles, _catalog(
        'evards_black_tentacles', '20ft square difficult terrain; DEX save or 3d6 bludgeoning and restrained', 'position', 'ranged', 90, 'aoe',
        area=_area('cube', length_ft=20, width_ft=20, height_ft=20), damage=(DamageType.BLUDGEONING,), saves=_saving_throws(AbilityName.DEXTERITY), concentration=True, tags=('bludgeoning', 'cube', 'concentration'),
    )),
    (abjuration.DeathWard, _catalog(
        'death_ward', 'Touch: once, survive lethal damage at 1 HP', 'entity', 'touch', 5, 'touch',
    )),
    (abjuration.FreedomOfMovement, _catalog(
        'freedom_of_movement', 'Touch: ignores terrain, magical speed reduction, underwater penalties, and key movement-impairing conditions', 'entity', 'touch', 5, 'touch',
    )),
    (enchantment.HoldMonster, _catalog(
        'hold_monster', 'Target must succeed on WIS save or be paralyzed (not undead)', 'multi_entity', 'ranged', 90, 'none',
        saves=_saving_throws(AbilityName.WISDOM), concentration=True, multi_target=_multi_target(1, 1, False), tags=('concentration',),
    )),
    (evocation.ConeOfCold, _catalog(
        'cone_of_cold', '60ft cone dealing 8d8 cold damage (CON save half)', 'position_aoe', 'self', 0, 'aoe',
        area=_area('cone', length_ft=60), damage=(DamageType.COLD,), saves=_saving_throws(AbilityName.CONSTITUTION), tags=('cold', 'cone'),
    )),
    (conjuration.Cloudkill, _catalog(
        'cloudkill', '20ft sphere poison fog, 5d8 poison (CON half), moves away from caster', 'position', 'ranged', 120, 'aoe_projectile',
        projectile='orb', area=_area('sphere', radius_ft=20), damage=(DamageType.POISON,), saves=_saving_throws(AbilityName.CONSTITUTION), concentration=True, tags=('poison', 'orb', 'sphere', 'concentration'),
    )),
    (conjuration.InsectPlague, _catalog(
        'insect_plague', '20ft sphere swarming locusts, 4d10 piercing (CON half)', 'position', 'ranged', 60, 'aoe_projectile',
        projectile='orb', area=_area('sphere', radius_ft=20), damage=(DamageType.PIERCING,), saves=_saving_throws(AbilityName.CONSTITUTION), concentration=True, tags=('piercing', 'orb', 'sphere', 'concentration'),
    )),
    (transmutation.Telekinesis, _catalog(
        'telekinesis', 'Telekinetically grab, move, or restrain a creature (STR save)', 'entity', 'ranged', 60, 'ray',
        projectile='ray', saves=_saving_throws(AbilityName.STRENGTH), concentration=True, tags=('ray', 'concentration'),
    )),
    (evocation.FlameStrike, _catalog(
        'flame_strike', '10ft cylinder: 4d6 fire + 4d6 radiant (DEX half)', 'position_aoe', 'ranged', 60, 'aoe_projectile',
        projectile='radiance', area=_area('cylinder', radius_ft=10, height_ft=40), damage=(DamageType.FIRE, DamageType.RADIANT), saves=_saving_throws(AbilityName.DEXTERITY), tags=('fire', 'radiant', 'cylinder'),
    )),
    (evocation.MassCureWounds, _catalog(
        'mass_cure_wounds', 'AoE heal up to 6 allies in 30ft sphere for 3d8 + modifier HP', 'position_aoe', 'ranged', 60, 'aoe',
        area=_area('sphere', radius_ft=30), healing=True, tags=('sphere',),
    )),
    (abjuration.GreaterRestoration, _catalog(
        'greater_restoration', 'Touch: remove one major condition or one curse', 'entity', 'touch', 5, 'touch',
    )),
    (evocation.CircleOfDeath, _catalog(
        'circle_of_death', '60ft radius sphere dealing 8d6 necrotic damage (CON save half)', 'position_aoe', 'ranged', 150, 'aoe_projectile',
        projectile='orb', area=_area('sphere', radius_ft=60), damage=(DamageType.NECROTIC,), saves=_saving_throws(AbilityName.CONSTITUTION), tags=('necrotic', 'orb', 'sphere'),
    )),
    (transmutation.Disintegrate, _catalog(
        'disintegrate', 'DEX save or 10d6+40 force damage. 0 on save.', 'entity', 'ranged', 60, 'ray',
        projectile='ray', damage=(DamageType.FORCE,), saves=_saving_throws(AbilityName.DEXTERITY), tags=('force', 'ray'),
    )),
    (divination.TrueSeeing, _catalog(
        'true_seeing', 'Grant truesight 120ft', 'entity', 'touch', 5, 'touch',
    )),
    (evocation.Sunbeam, _catalog(
        'sunbeam', '60ft line beam, 6d8 radiant + Blinded (CON half), repeatable', 'self', 'self', 0, 'beam',
        projectile='beam', area=_area('line', length_ft=60, width_ft=5), damage=(DamageType.RADIANT,), saves=_saving_throws(AbilityName.CONSTITUTION), concentration=True, tags=('radiant', 'beam', 'line', 'concentration'),
    )),
    (evocation.ChainLightning, _catalog(
        'chain_lightning', '10d8 lightning to primary + up to 3 secondaries (DEX half)', 'entity', 'ranged', 150, 'single_projectile',
        projectile='bolt', damage=(DamageType.LIGHTNING,), saves=_saving_throws(AbilityName.DEXTERITY), tags=('lightning', 'bolt'),
    )),
    (necromancy.Eyebite, _catalog(
        'eyebite', 'WIS save or Asleep/Panicked/Sickened, repeatable each turn', 'self', 'self', 0, 'ray',
        projectile='ray', saves=_saving_throws(AbilityName.WISDOM), concentration=True, tags=('ray', 'concentration'),
    )),
    (abjuration.GlobeOfInvulnerability, _catalog(
        'globe_of_invulnerability', '10ft sphere blocks spells L5 or lower, concentration', 'self', 'self', 0, 'aoe',
        area=_area('sphere', radius_ft=10), concentration=True, tags=('sphere', 'concentration'),
    )),
    (evocation.HealSpell, _catalog(
        'heal', 'Restore 70 HP and remove blindness/deafness', 'entity', 'ranged', 60, 'none',
        healing=True,
    )),
    (necromancy.Harm, _catalog(
        'harm', 'CON save, 14d6 necrotic, half on save, min 1 HP', 'entity', 'ranged', 60, 'touch',
        projectile='touch', damage=(DamageType.NECROTIC,), saves=_saving_throws(AbilityName.CONSTITUTION), tags=('necrotic', 'touch'),
    )),
    (conjuration.HeroesFeast, _catalog(
        'heroes_feast', 'Summon feast: eat for poison/fear immunity, WIS save advantage, +HP', 'position', 'ranged', 30, 'none',
    )),
    (evocation.PrismaticSpray, _catalog(
        'prismatic_spray', '60ft cone, random color effect per target', 'position_aoe', 'self', 0, 'aoe',
        area=_area('cone', length_ft=60), damage=(DamageType.FIRE, DamageType.ACID, DamageType.LIGHTNING, DamageType.POISON, DamageType.COLD), saves=_saving_throws(AbilityName.DEXTERITY, AbilityName.CONSTITUTION, AbilityName.WISDOM), tags=('fire', 'acid', 'lightning', 'poison', 'cold', 'cone'),
    )),
    (necromancy.FingerOfDeath, _catalog(
        'finger_of_death', '7d8+30 necrotic, CON save half', 'entity', 'ranged', 60, 'ray',
        projectile='ray', damage=(DamageType.NECROTIC,), saves=_saving_throws(AbilityName.CONSTITUTION), tags=('necrotic', 'ray'),
    )),
    (transmutation.Regenerate, _catalog(
        'regenerate', 'Heal 4d8+15 instantly, then 1 HP/round for 10 rounds', 'entity', 'touch', 5, 'touch',
        healing=True,
    )),
    (evocation.DivineWord, _catalog(
        'divine_word', 'HP-threshold effects: deafen/blind/stun/kill', 'multi_entity', 'ranged', 30, 'none',
        multi_target=_multi_target(1, 1, True),
    )),
    (evocation.Sunburst, _catalog(
        'sunburst', '60ft sphere, 12d6 radiant, CON save or blinded', 'position_aoe', 'ranged', 150, 'aoe',
        area=_area('sphere', radius_ft=60), damage=(DamageType.RADIANT,), saves=_saving_throws(AbilityName.CONSTITUTION), tags=('radiant', 'sphere'),
    )),
    (enchantment.PowerWordStun, _catalog(
        'power_word_stun', 'If target has <=150 HP, it is stunned. CON save each turn to end.', 'entity', 'ranged', 60, 'none',
        saves=_saving_throws(AbilityName.CONSTITUTION),
    )),
    (conjuration.IncendiaryCloud, _catalog(
        'incendiary_cloud', '20ft sphere fire cloud, 10d8 fire (DEX half), heavily obscured', 'position', 'ranged', 60, 'aoe',
        area=_area('sphere', radius_ft=20), damage=(DamageType.FIRE,), saves=_saving_throws(AbilityName.DEXTERITY), concentration=True, tags=('fire', 'sphere', 'concentration'),
    )),
    (abjuration.AntimagicField, _catalog(
        'antimagic_field', '10ft sphere suppresses all magic, concentration', 'self', 'self', 0, 'aoe',
        area=_area('sphere', radius_ft=10), concentration=True, tags=('sphere', 'concentration'),
    )),
    (enchantment.PowerWordKill, _catalog(
        'power_word_kill', 'If target has <=100 HP, it dies instantly. No save.', 'entity', 'ranged', 60, 'none',
        damage=(DamageType.FORCE,), tags=('force',),
    )),
    (evocation.MassHeal, _catalog(
        'mass_heal', 'Distribute 700 HP of healing among visible allies, remove blindness/deafness', 'multi_entity', 'ranged', 60, 'none',
        healing=True, multi_target=_multi_target(1, 20, False), tags=('healing', 'radiance'),
    )),
)

_spell_catalog_metadata_by_class = dict(SPELL_CATALOG_METADATA_SPECS)
if len(_spell_catalog_metadata_by_class) != len(
    SPELL_CATALOG_METADATA_SPECS
):
    raise ValueError("Spell catalog metadata table contains duplicate classes")

_identity_classes = {
    spec.spell_type
    for spec in SPELL_CONTENT_IDENTITY_SPECS
}
if set(_spell_catalog_metadata_by_class) != _identity_classes:
    missing_metadata = sorted(
        spell_type.__name__
        for spell_type in _identity_classes
        if spell_type not in _spell_catalog_metadata_by_class
    )
    unexpected_metadata = sorted(
        spell_type.__name__
        for spell_type in _spell_catalog_metadata_by_class
        if spell_type not in _identity_classes
    )
    raise ValueError(
        "Spell catalog metadata roots disagree with content identity roots: "
        f"missing={missing_metadata}, unexpected={unexpected_metadata}",
    )

SPELL_CATALOG_METADATA_BY_CLASS = MappingProxyType(
    _spell_catalog_metadata_by_class,
)
SPELL_CATALOG_METADATA_BY_NAME = MappingProxyType({
    spec.display_name: SPELL_CATALOG_METADATA_BY_CLASS[spec.spell_type]
    for spec in SPELL_CONTENT_IDENTITY_SPECS
})
SPELL_CATALOG_METADATA_BY_ID = MappingProxyType({
    metadata.catalog_id: metadata
    for metadata in SPELL_CATALOG_METADATA_BY_CLASS.values()
})
if (
    len(SPELL_CATALOG_METADATA_BY_NAME)
    != len(SPELL_CONTENT_IDENTITY_SPECS)
    or len(SPELL_CATALOG_METADATA_BY_ID)
    != len(SPELL_CONTENT_IDENTITY_SPECS)
):
    raise ValueError("Spell catalog metadata table contains duplicate keys")

_SPELL_OBJECT_DEPENDENCIES_BY_CLASS: Mapping[
    type[SpellAction],
    tuple[ContentDependency, ...],
] = MappingProxyType({
    conjuration.HeroesFeast: (
        ContentDependency(
            relation=ContentDependencyRelation.CREATES_OBJECT,
            target_ref=conjuration.HEROES_FEAST_OBJECT_REF,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
        ),
    ),
})

_SPELL_GRANTED_ACTION_TYPES_BY_CLASS: Mapping[
    type[SpellAction],
    tuple[type[object], ...],
] = MappingProxyType({
    abjuration.FreedomOfMovement: (
        abjuration.FreedomOfMovementEscape,
    ),
    conjuration.CallLightning: (
        conjuration.CallLightningStrike,
    ),
    evocation.Sunbeam: (
        evocation.SunbeamStrike,
    ),
    necromancy.Eyebite: (
        necromancy.EyebiteStrike,
    ),
    transmutation.Telekinesis: (
        transmutation.TelekinesisGrab,
    ),
})


def _spell_runtime_dependencies(
    spell_type: type[SpellAction],
) -> tuple[ContentDependency, ...]:
    """Return the spell's complete explicit runtime behavior closure."""
    action_dependencies = tuple(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=get_content_declaration(action_type).ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Registered while this exact maintained spell is active.",
        )
        for action_type in _SPELL_GRANTED_ACTION_TYPES_BY_CLASS.get(
            spell_type,
            (),
        )
    )
    return (
        *_SPELL_OBJECT_DEPENDENCIES_BY_CLASS.get(spell_type, ()),
        *action_dependencies,
    )


def _get_optional_declaration(
    spell_type: type[SpellAction],
) -> ContentDeclaration | None:
    try:
        return get_content_declaration(spell_type)
    except ValueError:
        return None


def _declare_spell(spec: SpellContentIdentitySpec) -> ContentDeclaration:
    """Verify a co-located declaration or attach the explicit table identity."""
    metadata = SPELL_CATALOG_METADATA_BY_CLASS[spec.spell_type]
    attach_spell_catalog_metadata(spec.spell_type, metadata)
    if get_spell_catalog_metadata(spec.spell_type) != metadata:
        raise ValueError(
            f"Spell catalog metadata attachment failed for {spec.display_name}",
        )

    declaration = _get_optional_declaration(spec.spell_type)
    if declaration is None:
        description = f"Playable implementation of {spec.display_name}."
        if spec.pack_id == SRD_SPELL_PACK_ID:
            if spec.source_page is None:
                raise ValueError(
                    f"SRD spell {spec.display_name} requires a source page",
                )
            decorator = srd_spell_identity(
                content_id=spec.content_id,
                display_name=spec.display_name,
                description=description,
                school=spec.school,
                level=spec.level,
                source_page=spec.source_page,
                sort_order=spec.sort_order,
                icon_key=spec.icon_key,
                dependencies=_spell_runtime_dependencies(spec.spell_type),
            )
        elif spec.pack_id == NEURODRAGON_SPELL_PACK_ID:
            if spec.source_page is not None:
                raise ValueError(
                    f"Original spell {spec.display_name} cannot cite an SRD page",
                )
            decorator = neurodragon_spell_identity(
                content_id=spec.content_id,
                display_name=spec.display_name,
                description=description,
                school=spec.school,
                level=spec.level,
                sort_order=spec.sort_order,
                icon_key=spec.icon_key,
            )
        else:
            raise ValueError(
                f"Unsupported built-in spell pack {spec.pack_id}",
            )
        decorator(spec.spell_type)
        declaration = get_content_declaration(spec.spell_type)

    ref = declaration.ref
    expected_level_tag = (
        "cantrip" if spec.level == 0 else f"level_{spec.level}"
    )
    if (
        ref.pack_id != spec.pack_id
        or ref.definition_kind != ContentDefinitionKind.SPELL
        or ref.content_id != spec.content_id
        or ref.content_version != 1
        or declaration.runtime_behavior_kind != RuntimeBehaviorKind.SPELL
        or declaration.descriptor.display_name != spec.display_name
        or declaration.descriptor.presentation.icon_key
        != resolve_content_icon_key(
            declaration.ref,
            spec.icon_key or spec.content_id,
        )[0]
        or spec.school not in declaration.descriptor.tags
        or expected_level_tag not in declaration.descriptor.tags
    ):
        raise ValueError(
            "Spell content declaration disagrees with explicit catalog table "
            f"for {spec.display_name}",
        )
    return declaration


SPELL_CONTENT_DECLARATIONS: tuple[ContentDeclaration, ...] = tuple(
    _declare_spell(spec)
    for spec in SPELL_CONTENT_IDENTITY_SPECS
)
SPELL_CONTENT_DECLARATIONS_BY_NAME = MappingProxyType({
    spec.display_name: declaration
    for spec, declaration in zip(
        SPELL_CONTENT_IDENTITY_SPECS,
        SPELL_CONTENT_DECLARATIONS,
        strict=True,
    )
})
SPELL_CONTENT_DECLARATIONS_BY_CLASS = MappingProxyType({
    spec.spell_type: declaration
    for spec, declaration in zip(
        SPELL_CONTENT_IDENTITY_SPECS,
        SPELL_CONTENT_DECLARATIONS,
        strict=True,
    )
})

if (
    len(SPELL_CONTENT_DECLARATIONS_BY_NAME)
    != len(SPELL_CONTENT_IDENTITY_SPECS)
    or len(SPELL_CONTENT_DECLARATIONS_BY_CLASS)
    != len(SPELL_CONTENT_IDENTITY_SPECS)
):
    raise ValueError("Spell content identity table contains duplicate roots")


__all__ = [
    "NEURODRAGON_SPELL_PACK_ID",
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
    "SRD_SPELL_PACK_ID",
    "SpellContentIdentitySpec",
]
