"""Explicit authored identities for active condition-backed behaviors.

The concrete classes remain beside the rules that implement them.  This module
is the built-in composition inventory: every row names its class and durable
identity explicitly, without deriving identity from a Python path or display
label.  Metadata-only declarations do not make conditions independently
constructible or persist live condition instances.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import dnd.classes.barbarian as barbarian
import dnd.classes.feats as feats
import dnd.classes.fighter as fighter
import dnd.classes.rage as rage
import dnd.classes.sorcerer as sorcerer
import dnd.conditions as conditions
import dnd.extensions.aegis_spark as aegis_spark
import dnd.extensions.field_focus as field_focus
import dnd.items.consumables as consumables
import dnd.monsters.circus_fighter_conditions as circus_conditions
import dnd.monsters.skeleton_abilities as skeleton_abilities
import dnd.monsters.traits as monster_traits
import dnd.spells.abjuration as abjuration
import dnd.spells.conjuration as conjuration
import dnd.spells.divination as divination
import dnd.spells.enchantment as enchantment
import dnd.spells.evocation as evocation
import dnd.spells.illusion as illusion
import dnd.spells.necromancy as necromancy
import dnd.spells.transmutation as transmutation
import dnd.tile_conditions as tile_conditions
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_actions import BaseAction
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
    resolve_content_icon_key,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    ContentDeclaration,
    behavior_identity,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.content_system.action_definitions import (
    ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.content_system.reaction_definitions import (
    PARRY_REACTION_DECLARATION,
    PROTECTION_REACTION_DECLARATION,
    RETALIATION_REACTION_DECLARATION,
)


SRD_5_1_PACK_ID = "content.srd_5_1_cc"
NEURODRAGON_PACK_ID = "content.neurodragon"


@dataclass(frozen=True, slots=True)
class ConditionBehaviorIdentitySpec:
    """One explicit class-to-content association for a live condition."""

    condition_type: type[BaseCondition]
    definition_kind: ContentDefinitionKind
    pack_id: str
    content_id: str
    visibility: ContentVisibility = ContentVisibility.PUBLIC
    dependencies: tuple[ContentDependency, ...] = ()


def _srd(
    condition_type: type[BaseCondition],
    definition_kind: ContentDefinitionKind,
    content_id: str,
    *,
    dependencies: tuple[ContentDependency, ...] = (),
) -> ConditionBehaviorIdentitySpec:
    return ConditionBehaviorIdentitySpec(
        condition_type=condition_type,
        definition_kind=definition_kind,
        pack_id=SRD_5_1_PACK_ID,
        content_id=content_id,
        dependencies=dependencies,
    )


def _original(
    condition_type: type[BaseCondition],
    definition_kind: ContentDefinitionKind,
    content_id: str,
    *,
    visibility: ContentVisibility = ContentVisibility.PUBLIC,
) -> ConditionBehaviorIdentitySpec:
    return ConditionBehaviorIdentitySpec(
        condition_type=condition_type,
        definition_kind=definition_kind,
        pack_id=NEURODRAGON_PACK_ID,
        content_id=content_id,
        visibility=visibility,
    )


CONDITION_BEHAVIOR_IDENTITY_SPECS: tuple[
    ConditionBehaviorIdentitySpec,
    ...,
] = (
    # SRD class and feat behaviors represented by persistent conditions.
    _srd(barbarian.BrutalCritical, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.brutal_critical"),
    _srd(barbarian.DangerSense, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.danger_sense"),
    _srd(barbarian.FastMovement, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.fast_movement"),
    _srd(barbarian.FeralInstinct, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.feral_instinct"),
    _srd(barbarian.IndomitableMight, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.indomitable_might"),
    _srd(barbarian.IntimidatingPresenceFeature, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.intimidating_presence"),
    _srd(barbarian.IntimidatingPresenceImmunity, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.intimidating_presence_immunity"),
    _srd(barbarian.MindlessRage, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.mindless_rage"),
    _srd(barbarian.PersistentRage, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.persistent_rage"),
    _srd(barbarian.PrimalChampion, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.primal_champion"),
    _srd(barbarian.RecklessAttackFeature, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.reckless_attack"),
    _srd(barbarian.RecklessAttacking, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.reckless_attacking"),
    _srd(barbarian.RelentlessRage, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.relentless_rage"),
    _srd(
        barbarian.Retaliation,
        ContentDefinitionKind.CLASS_FEATURE,
        "class_feature.barbarian.retaliation",
        dependencies=(
            ContentDependency(
                relation=ContentDependencyRelation.INSTALLS_HANDLER,
                target_ref=RETALIATION_REACTION_DECLARATION.ref,
                phase=ContentDependencyPhase.RUNTIME_REFERENCE,
                notes=(
                    "The persistent class feature installs the independently "
                    "authored Retaliation reaction."
                ),
            ),
        ),
    ),
    _srd(feats.LuckyFeature, ContentDefinitionKind.FEAT, "feat.lucky"),
    _srd(fighter.ActionSurgeFeature, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.action_surge"),
    _srd(fighter.ExtraAttackFeature, ContentDefinitionKind.CLASS_FEATURE, "class_feature.extra_attack"),
    _srd(fighter.FightingStyleArchery, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.fighting_style.archery"),
    _srd(fighter.FightingStyleDefense, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.fighting_style.defense"),
    _srd(fighter.FightingStyleDueling, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.fighting_style.dueling"),
    _srd(
        fighter.FightingStyleProtection,
        ContentDefinitionKind.CLASS_FEATURE,
        "class_feature.fighter.fighting_style.protection",
        dependencies=(
            ContentDependency(
                relation=ContentDependencyRelation.INSTALLS_HANDLER,
                target_ref=PROTECTION_REACTION_DECLARATION.ref,
                phase=ContentDependencyPhase.RUNTIME_REFERENCE,
                notes=(
                    "The persistent fighting style installs the independently "
                    "authored Protection reaction."
                ),
            ),
        ),
    ),
    _srd(fighter.FightingStyleTwoWeaponFighting, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.fighting_style.two_weapon_fighting"),
    _srd(fighter.GreatWeaponFighting, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.fighting_style.great_weapon_fighting"),
    _srd(fighter.ImprovedCritical, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.improved_critical"),
    _srd(fighter.Indomitable, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.indomitable"),
    _srd(fighter.SecondWindFeature, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.second_wind"),
    _srd(fighter.SuperiorCritical, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.superior_critical"),
    _srd(fighter.Survivor, ContentDefinitionKind.CLASS_FEATURE, "class_feature.fighter.survivor"),
    _srd(rage.Frenzied, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.frenzied"),
    _srd(rage.FrenzyFeature, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.frenzy"),
    _srd(rage.RageFeature, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.rage"),
    _srd(rage.Raging, ContentDefinitionKind.CLASS_FEATURE, "class_feature.barbarian.raging"),
    _srd(sorcerer.DraconicResilience, ContentDefinitionKind.CLASS_FEATURE, "class_feature.sorcerer.draconic_resilience"),
    _srd(sorcerer.DraconicPresenceAura, ContentDefinitionKind.CLASS_FEATURE, "class_feature.sorcerer.draconic_presence.aura"),
    _srd(sorcerer.DraconicPresenceImmunity, ContentDefinitionKind.CLASS_FEATURE, "class_feature.sorcerer.draconic_presence.immunity"),
    _srd(sorcerer.DragonWingsActive, ContentDefinitionKind.CLASS_FEATURE, "class_feature.sorcerer.dragon_wings.active"),
    _srd(sorcerer.ElementalAffinityResistance, ContentDefinitionKind.CLASS_FEATURE, "class_feature.sorcerer.elemental_affinity.resistance"),
    _srd(sorcerer.MetamagicActive, ContentDefinitionKind.CLASS_FEATURE, "class_feature.sorcerer.metamagic_active"),
    _srd(sorcerer.SorceryPointsFeature, ContentDefinitionKind.CLASS_FEATURE, "class_feature.sorcerer.sorcery_points"),

    # Core condition wrappers whose mechanics are supplied by SRD spells.
    _srd(conditions.InvisibilityEffect, ContentDefinitionKind.CONDITION, "condition.spell.invisibility"),
    _srd(conditions.GreaterInvisibilityEffect, ContentDefinitionKind.CONDITION, "condition.spell.greater_invisibility"),

    # Original extension and item-owned condition behaviors.
    _original(
        aegis_spark.AegisSparkEffect,
        ContentDefinitionKind.CONDITION,
        "condition.aegis_spark",
    ),
    _original(aegis_spark.AegisTrainingFeature, ContentDefinitionKind.CLASS_FEATURE, "class_feature.aegis_training", visibility=ContentVisibility.DEVELOPER),
    _original(field_focus.FieldFocus, ContentDefinitionKind.CONDITION, "condition.field_focus"),
    _original(
        consumables._FireWeaponCoatCondition,
        ContentDefinitionKind.CONDITION,
        "condition.consumable.weapon_coat.fire",
    ),
    _original(
        consumables._LightningWeaponCoatCondition,
        ContentDefinitionKind.CONDITION,
        "condition.consumable.weapon_coat.lightning",
    ),
    _original(
        consumables._ConcentrationFireWeaponCoatCondition,
        ContentDefinitionKind.CONDITION,
        "condition.consumable.weapon_coat.concentration_fire",
    ),
    _original(
        consumables._TimedFireWeaponCoatCondition,
        ContentDefinitionKind.CONDITION,
        "condition.consumable.weapon_coat.timed_fire",
    ),

    # Original circus and skeleton behaviors.
    _original(circus_conditions.CircusPerformer, ContentDefinitionKind.TRAIT, "trait.circus_performer"),
    _original(circus_conditions.DualWielder, ContentDefinitionKind.TRAIT, "trait.circus_dual_wielder"),
    _original(circus_conditions.ElementalAffinity, ContentDefinitionKind.TRAIT, "trait.circus_elemental_affinity"),
    _original(circus_conditions.ElementalWeaponMastery, ContentDefinitionKind.TRAIT, "trait.circus_elemental_weapon_mastery"),
    _original(circus_conditions.Tired, ContentDefinitionKind.TRAIT, "trait.circus_tired"),
    _original(skeleton_abilities.Marked, ContentDefinitionKind.TRAIT, "trait.skeleton_archer_marked"),

    # Reusable SRD monster/NPC traits represented by conditions.
    _srd(monster_traits.BraveFeature, ContentDefinitionKind.TRAIT, "trait.brave"),
    _srd(monster_traits.BruteFeature, ContentDefinitionKind.TRAIT, "trait.brute"),
    _srd(monster_traits.DarkDevotionFeature, ContentDefinitionKind.TRAIT, "trait.dark_devotion"),
    _srd(monster_traits.DireWolfBiteProneRiderFeature, ContentDefinitionKind.TRAIT, "trait.dire_wolf_bite_prone"),
    _srd(monster_traits.DivineEminenceActive, ContentDefinitionKind.TRAIT, "trait.divine_eminence_active"),
    _srd(monster_traits.GhoulClawsParalysisFeature, ContentDefinitionKind.TRAIT, "trait.ghoul_claws_paralysis"),
    _srd(monster_traits.GhoulParalysisEffect, ContentDefinitionKind.TRAIT, "trait.ghoul_paralysis"),
    _srd(monster_traits.KeenHearingAndSightFeature, ContentDefinitionKind.TRAIT, "trait.keen_hearing_and_sight"),
    _srd(monster_traits.KeenHearingAndSmellFeature, ContentDefinitionKind.TRAIT, "trait.keen_hearing_and_smell"),
    _srd(monster_traits.LeadershipAura, ContentDefinitionKind.TRAIT, "trait.leadership_aura"),
    _srd(monster_traits.MartialAdvantageFeature, ContentDefinitionKind.TRAIT, "trait.martial_advantage"),
    _srd(monster_traits.PackTacticsFeature, ContentDefinitionKind.TRAIT, "trait.pack_tactics"),
    _srd(
        monster_traits.ParryFeature,
        ContentDefinitionKind.TRAIT,
        "trait.parry",
        dependencies=(
            ContentDependency(
                relation=ContentDependencyRelation.INSTALLS_HANDLER,
                target_ref=PARRY_REACTION_DECLARATION.ref,
                phase=ContentDependencyPhase.RUNTIME_REFERENCE,
                notes=(
                    "The persistent monster trait installs the independently "
                    "authored Parry reaction."
                ),
            ),
        ),
    ),
    _srd(monster_traits.RampageAvailable, ContentDefinitionKind.TRAIT, "trait.rampage_available"),
    _srd(monster_traits.RampageFeature, ContentDefinitionKind.TRAIT, "trait.rampage"),
    _srd(monster_traits.SneakAttackFeature, ContentDefinitionKind.TRAIT, "trait.sneak_attack"),
    _srd(monster_traits.SunlightSensitivityFeature, ContentDefinitionKind.TRAIT, "trait.sunlight_sensitivity"),
    _srd(monster_traits.SurpriseAttackFeature, ContentDefinitionKind.TRAIT, "trait.surprise_attack"),
    _srd(monster_traits.UndeadFortitudeFeature, ContentDefinitionKind.TRAIT, "trait.undead_fortitude"),
    _srd(monster_traits.WolfBiteProneRiderFeature, ContentDefinitionKind.TRAIT, "trait.wolf_bite_prone"),

    # SRD spell effects and zones.
    _srd(abjuration.AidEffect, ContentDefinitionKind.CONDITION, "condition.spell.aid"),
    _srd(abjuration.AntimagicFieldZone, ContentDefinitionKind.CONDITION, "condition.spell.antimagic_field.zone"),
    _srd(abjuration.BanishedCondition, ContentDefinitionKind.CONDITION, "condition.spell.banishment"),
    _srd(abjuration.BeaconOfHopeEffect, ContentDefinitionKind.CONDITION, "condition.spell.beacon_of_hope"),
    _srd(abjuration.DeathWardEffect, ContentDefinitionKind.CONDITION, "condition.spell.death_ward"),
    _srd(abjuration.FreedomOfMovementEffect, ContentDefinitionKind.CONDITION, "condition.spell.freedom_of_movement"),
    _srd(abjuration.GlobeZone, ContentDefinitionKind.CONDITION, "condition.spell.globe_of_invulnerability.zone"),
    _srd(abjuration.MageArmorCondition, ContentDefinitionKind.CONDITION, "condition.spell.mage_armor"),
    _srd(abjuration.ProtectionFromEnergyEffect, ContentDefinitionKind.CONDITION, "condition.spell.protection_from_energy"),
    _srd(abjuration.ProtectionFromPoisonEffect, ContentDefinitionKind.CONDITION, "condition.spell.protection_from_poison"),
    _srd(abjuration.ResistanceEffect, ContentDefinitionKind.CONDITION, "condition.spell.resistance"),
    _srd(abjuration.SanctuaryEffect, ContentDefinitionKind.CONDITION, "condition.spell.sanctuary"),
    _srd(abjuration.ShieldBuff, ContentDefinitionKind.CONDITION, "condition.spell.shield"),
    _srd(abjuration.ShieldOfFaithEffect, ContentDefinitionKind.CONDITION, "condition.spell.shield_of_faith"),
    _srd(abjuration.StoneskinEffect, ContentDefinitionKind.CONDITION, "condition.spell.stoneskin"),
    _srd(conjuration.CloudkillZone, ContentDefinitionKind.CONDITION, "condition.spell.cloudkill.zone"),
    _srd(conjuration.DarknessZone, ContentDefinitionKind.CONDITION, "condition.spell.darkness.zone"),
    _srd(conjuration.DaylightZone, ContentDefinitionKind.CONDITION, "condition.spell.daylight.zone"),
    _srd(conjuration.FogCloudZone, ContentDefinitionKind.CONDITION, "condition.spell.fog_cloud.zone"),
    _srd(conjuration.GreaseZone, ContentDefinitionKind.CONDITION, "condition.spell.grease.zone"),
    _srd(conjuration.HeroesFeastBuff, ContentDefinitionKind.CONDITION, "condition.spell.heroes_feast"),
    _srd(conjuration.IncendiaryCloudZone, ContentDefinitionKind.CONDITION, "condition.spell.incendiary_cloud.zone"),
    _srd(conjuration.InsectPlagueZone, ContentDefinitionKind.CONDITION, "condition.spell.insect_plague.zone"),
    _srd(conjuration.NauseatedCondition, ContentDefinitionKind.CONDITION, "condition.spell.stinking_cloud.nauseated"),
    _srd(conjuration.SleetStormZone, ContentDefinitionKind.CONDITION, "condition.spell.sleet_storm.zone"),
    _srd(conjuration.SpiritGuardiansSlowed, ContentDefinitionKind.CONDITION, "condition.spell.spirit_guardians.slowed"),
    _srd(conjuration.SpiritGuardiansZone, ContentDefinitionKind.CONDITION, "condition.spell.spirit_guardians.zone"),
    _srd(conjuration.StinkingCloudZone, ContentDefinitionKind.CONDITION, "condition.spell.stinking_cloud.zone"),
    _srd(conjuration.WebRestrained, ContentDefinitionKind.CONDITION, "condition.spell.web.restrained"),
    _srd(conjuration.WebZone, ContentDefinitionKind.CONDITION, "condition.spell.web.zone"),
    _srd(divination.GuidanceEffect, ContentDefinitionKind.CONDITION, "condition.spell.guidance"),
    _srd(divination.SeeInvisibilityEffect, ContentDefinitionKind.CONDITION, "condition.spell.see_invisibility"),
    _srd(divination.TrueSeeingEffect, ContentDefinitionKind.CONDITION, "condition.spell.true_seeing"),
    _srd(enchantment.BaneEffect, ContentDefinitionKind.CONDITION, "condition.spell.bane"),
    _srd(enchantment.BlessEffect, ContentDefinitionKind.CONDITION, "condition.spell.bless"),
    _srd(enchantment.CommandFleeEffect, ContentDefinitionKind.CONDITION, "condition.spell.command.flee"),
    _srd(enchantment.CommandGrovelEffect, ContentDefinitionKind.CONDITION, "condition.spell.command.grovel"),
    _srd(enchantment.CommandHaltEffect, ContentDefinitionKind.CONDITION, "condition.spell.command.halt"),
    _srd(enchantment.HoldMonsterEffect, ContentDefinitionKind.CONDITION, "condition.spell.hold_monster"),
    _srd(enchantment.HoldPersonEffect, ContentDefinitionKind.CONDITION, "condition.spell.hold_person"),
    _srd(enchantment.PowerWordStunEffect, ContentDefinitionKind.CONDITION, "condition.spell.power_word_stun"),
    _srd(enchantment.SleepEffect, ContentDefinitionKind.CONDITION, "condition.spell.sleep"),
    _srd(evocation.DivineWordEffect, ContentDefinitionKind.CONDITION, "condition.spell.divine_word"),
    _srd(evocation.GuidingBoltMarked, ContentDefinitionKind.CONDITION, "condition.spell.guiding_bolt.marked"),
    _srd(evocation.GustOfWindZone, ContentDefinitionKind.CONDITION, "condition.spell.gust_of_wind.zone"),
    _srd(evocation.IceStormTerrain, ContentDefinitionKind.CONDITION, "condition.spell.ice_storm.terrain"),
    _srd(evocation.LightEffect, ContentDefinitionKind.CONDITION, "condition.spell.light"),
    _srd(evocation.PrismaticRestrained, ContentDefinitionKind.CONDITION, "condition.spell.prismatic_spray.restrained"),
    _srd(evocation.RayOfFrostEffect, ContentDefinitionKind.CONDITION, "condition.spell.ray_of_frost"),
    _srd(evocation.SunburstBlindedEffect, ContentDefinitionKind.CONDITION, "condition.spell.sunburst.blinded"),
    _srd(illusion.BlurEffect, ContentDefinitionKind.CONDITION, "condition.spell.blur"),
    _srd(illusion.ColorSprayEffect, ContentDefinitionKind.CONDITION, "condition.spell.color_spray"),
    _srd(illusion.FearEffect, ContentDefinitionKind.CONDITION, "condition.spell.fear"),
    _srd(illusion.HypnoticPatternEffect, ContentDefinitionKind.CONDITION, "condition.spell.hypnotic_pattern"),
    _srd(illusion.MirrorImageEffect, ContentDefinitionKind.CONDITION, "condition.spell.mirror_image"),
    _srd(illusion.SilenceZone, ContentDefinitionKind.CONDITION, "condition.spell.silence.zone"),
    _srd(illusion._SilenceDeafened, ContentDefinitionKind.CONDITION, "condition.spell.silence.deafened"),
    _srd(necromancy.AbilityCurseEffect, ContentDefinitionKind.CONDITION, "condition.spell.bestow_curse.ability"),
    _srd(necromancy.AttackCurseEffect, ContentDefinitionKind.CONDITION, "condition.spell.bestow_curse.attack"),
    _srd(necromancy.BlindnessDeafnessEffect, ContentDefinitionKind.CONDITION, "condition.spell.blindness_deafness"),
    _srd(necromancy.ChillTouchEffect, ContentDefinitionKind.CONDITION, "condition.spell.chill_touch"),
    _srd(necromancy.DamageCurseEffect, ContentDefinitionKind.CONDITION, "condition.spell.bestow_curse.damage"),
    _srd(necromancy.EyebiteAsleepEffect, ContentDefinitionKind.CONDITION, "condition.spell.eyebite.asleep"),
    _srd(necromancy.EyebitePanickedEffect, ContentDefinitionKind.CONDITION, "condition.spell.eyebite.panicked"),
    _srd(necromancy.InactionCurseEffect, ContentDefinitionKind.CONDITION, "condition.spell.bestow_curse.inaction"),
    _srd(necromancy.NoHealing, ContentDefinitionKind.CONDITION, "condition.spell.no_healing"),
    _srd(necromancy.SickenedCondition, ContentDefinitionKind.CONDITION, "condition.spell.eyebite.sickened"),
    _srd(transmutation.DarkvisionEffect, ContentDefinitionKind.CONDITION, "condition.spell.darkvision"),
    _srd(transmutation.EnhanceAbilityEffect, ContentDefinitionKind.CONDITION, "condition.spell.enhance_ability"),
    _srd(transmutation.EnlargeReduceEffect, ContentDefinitionKind.CONDITION, "condition.spell.enlarge_reduce"),
    _srd(transmutation.ExpeditiousRetreatEffect, ContentDefinitionKind.CONDITION, "condition.spell.expeditious_retreat"),
    _srd(transmutation.HasteEffect, ContentDefinitionKind.CONDITION, "condition.spell.haste"),
    _srd(transmutation.HasteLethargyEffect, ContentDefinitionKind.CONDITION, "condition.spell.haste.lethargy"),
    _srd(transmutation.JumpEffect, ContentDefinitionKind.CONDITION, "condition.spell.jump"),
    _srd(transmutation.RegeneratingEffect, ContentDefinitionKind.CONDITION, "condition.spell.regenerate"),
    _srd(transmutation.SlowedEffect, ContentDefinitionKind.CONDITION, "condition.spell.slow"),
    _srd(transmutation.SpikeGrowthZone, ContentDefinitionKind.CONDITION, "condition.spell.spike_growth.zone"),

    # Original map-authored conditions.
    _original(tile_conditions.SpikeTrapCondition, ContentDefinitionKind.CONDITION, "condition.tile.spike_trap"),
    _original(tile_conditions.ZoneMarkerCondition, ContentDefinitionKind.CONDITION, "condition.tile.zone_marker"),
)


_GRANTED_ACTION_TYPES_BY_CONDITION: Mapping[
    type[BaseCondition],
    tuple[type[BaseAction], ...],
] = MappingProxyType({
    barbarian.IntimidatingPresenceFeature: (
        barbarian.IntimidatingPresence,
        barbarian.ExtendIntimidatingPresence,
    ),
    barbarian.RecklessAttackFeature: (barbarian.RecklessAttack,),
    fighter.ActionSurgeFeature: (fighter.ActionSurge,),
    fighter.ExtraAttackFeature: (fighter.ExtraAttack,),
    fighter.SecondWindFeature: (fighter.SecondWind,),
    rage.Frenzied: (rage.FrenziedStrike,),
    rage.FrenzyFeature: (rage.Frenzy,),
    rage.RageFeature: (rage.Rage, rage.EndRage),
    sorcerer.SorceryPointsFeature: (
        sorcerer.ConvertSPToSlot,
        sorcerer.ConvertSlotToSP,
        sorcerer.DistantSpell,
        sorcerer.QuickenedSpell,
        sorcerer.TwinnedSpell,
    ),
    aegis_spark.AegisTrainingFeature: (aegis_spark.AegisSpark,),
    monster_traits.RampageAvailable: (monster_traits.NaturalAttack,),
    conjuration.WebRestrained: (conjuration.EscapeWebAction,),
    transmutation.ExpeditiousRetreatEffect: (transmutation.BonusDash,),
})

_ROOT_OWNED_CONDITION_TYPES = frozenset({
    barbarian.IntimidatingPresenceFeature,
    barbarian.RecklessAttackFeature,
    fighter.ActionSurgeFeature,
    fighter.ExtraAttackFeature,
    fighter.SecondWindFeature,
    rage.FrenzyFeature,
    rage.RageFeature,
    sorcerer.SorceryPointsFeature,
})


def _granted_action_dependencies(
    condition_type: type[BaseCondition],
) -> tuple[ContentDependency, ...]:
    """Return the exact actions this condition can admit at runtime."""
    return tuple(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[
                action_type
            ].ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Registered while this condition is the active provider.",
        )
        for action_type in _GRANTED_ACTION_TYPES_BY_CONDITION.get(
            condition_type,
            (),
        )
    )


def _field_default(
    condition_type: type[BaseCondition],
    field_name: str,
) -> str:
    value = condition_type.model_fields[field_name].default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{condition_type.__module__}.{condition_type.__qualname__} "
            f"requires a non-empty authored {field_name}",
        )
    return value


def _provenance(
    spec: ConditionBehaviorIdentitySpec,
    display_name: str,
) -> ContentProvenance:
    if spec.pack_id == SRD_5_1_PACK_ID:
        return ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=(
                "SRD 5.1 (CC-BY-4.0), existing rules-behavior inventory: "
                f"{display_name}"
            ),
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.UNREVIEWED,
            notes=(
                "Identity preserves an existing playable implementation; "
                "exact source parity remains ledger-reviewed separately."
            ),
        )
    if spec.pack_id == NEURODRAGON_PACK_ID:
        return ContentProvenance(
            primary_source_id="neurodragon.original_b2b3930",
            source_anchor=(
                "Neurodragon original content baseline: "
                f"{display_name}"
            ),
            relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
            notes="Existing runtime behavior preserved as authored content.",
        )
    raise ValueError(f"Unsupported condition behavior pack {spec.pack_id}")


def _declare_condition_behavior(
    spec: ConditionBehaviorIdentitySpec,
    sort_order: int,
) -> ContentDeclaration:
    try:
        declaration = get_content_declaration(spec.condition_type)
    except ValueError:
        declaration = None
    else:
        display_name = _field_default(spec.condition_type, "name")
        description = _field_default(spec.condition_type, "description")
        if (
            declaration.descriptor.display_name != display_name
            or declaration.descriptor.description != description
        ):
            raise ValueError(
                f"Co-located declaration for {spec.condition_type!r} has "
                "unexpected display identity",
            )

    display_name = _field_default(spec.condition_type, "name")
    description = _field_default(spec.condition_type, "description")
    group = spec.definition_kind.value
    if declaration is None:
        decorator = behavior_identity(
            definition_kind=spec.definition_kind,
            runtime_behavior_kind=RuntimeBehaviorKind.CONDITION,
            pack_id=spec.pack_id,
            content_id=spec.content_id,
            version=1,
            descriptor=ContentDescriptorSpec(
                display_name=display_name,
                description=description,
                tags=(
                    "condition",
                    group,
                    *(
                        ("root_owned",)
                        if spec.condition_type in _ROOT_OWNED_CONDITION_TYPES
                        else ()
                    ),
                ),
                visibility=spec.visibility,
                presentation=ContentPresentation(
                    icon_key=spec.content_id,
                    visual_variant_key=spec.content_id,
                    vfx_profile=spec.content_id,
                    ui_group=f"conditions.{group}",
                ),
                ordering=ContentOrdering(
                    sort_group=f"conditions.{group}",
                    sort_order=sort_order,
                ),
            ),
            provenance=_provenance(spec, display_name),
            dependencies=(
                *_granted_action_dependencies(spec.condition_type),
                *spec.dependencies,
            ),
        )
        decorator(spec.condition_type)
        declaration = get_content_declaration(spec.condition_type)
    if (
        declaration.ref.pack_id != spec.pack_id
        or declaration.ref.definition_kind is not spec.definition_kind
        or declaration.ref.content_id != spec.content_id
        or declaration.runtime_behavior_kind is not RuntimeBehaviorKind.CONDITION
        or declaration.descriptor.visibility is not spec.visibility
        or declaration.descriptor.presentation.icon_key
        != resolve_content_icon_key(
            declaration.ref,
            spec.content_id,
        )[0]
    ):
        raise ValueError(
            "Condition behavior declaration disagrees with its explicit spec "
            f"for {spec.condition_type!r}",
        )
    return declaration


CONDITION_BEHAVIOR_DECLARATIONS: tuple[ContentDeclaration, ...] = tuple(
    _declare_condition_behavior(spec, sort_order)
    for sort_order, spec in enumerate(
        CONDITION_BEHAVIOR_IDENTITY_SPECS,
        start=1,
    )
)
CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS = MappingProxyType({
    spec.condition_type: declaration
    for spec, declaration in zip(
        CONDITION_BEHAVIOR_IDENTITY_SPECS,
        CONDITION_BEHAVIOR_DECLARATIONS,
        strict=True,
    )
})

if (
    len(CONDITION_BEHAVIOR_DECLARATIONS)
    != len(CONDITION_BEHAVIOR_IDENTITY_SPECS)
    or len({
        declaration.ref.identity_key
        for declaration in CONDITION_BEHAVIOR_DECLARATIONS
    }) != len(CONDITION_BEHAVIOR_DECLARATIONS)
):
    raise ValueError("Condition behavior identity inventory is not one-to-one")


__all__ = [
    "CONDITION_BEHAVIOR_DECLARATIONS",
    "CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS",
    "CONDITION_BEHAVIOR_IDENTITY_SPECS",
    "ConditionBehaviorIdentitySpec",
]
