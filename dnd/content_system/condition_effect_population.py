"""Single authored inventory for built-in condition producers.

The concrete rules remain beside their actions, spells, handlers, and
conditions.  This cold-start composition table supplies their exact static
condition contract only after every source and target declaration exists.
No runtime path consults Python names or display labels.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

import dnd.actions as actions
import dnd.classes.barbarian as barbarian
import dnd.classes.fighter as fighter
import dnd.classes.rage as rage
import dnd.conditions as conditions
import dnd.extensions.aegis_spark as aegis_spark
import dnd.extensions.field_focus as field_focus
import dnd.items.consumables as consumables
import dnd.items.environment_interactables as environment_interactables
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
from dnd.content_system.action_definitions import (
    ACTION_BEHAVIOR_IDENTITY_SPECS,
)
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_IDENTITY_SPECS,
)
from dnd.content_system.reaction_definitions import (
    REACTION_BEHAVIOR_IDENTITY_SPECS,
)
from dnd.core.condition_types import ConditionRemovalTrigger, ConditionTag
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.effects import (
    ActionOutcomeConditionEffectGate,
    AttackOutcomeConditionEffectGate,
    AuthoredConditionEffect,
    AuthoredConditionEffectBranch,
    AuthoredConditionEffectProfile,
    AutomaticConditionEffectGate,
    ConditionActionOutcome,
    ConditionAttackOutcome,
    ConditionEffectCoverage,
    ConditionEffectDisposition,
    ConditionEffectGate,
    ConditionEffectOperation,
    ConditionEffectSelector,
    ConditionEffectTarget,
    ConditionSaveDCSource,
    ConditionSaveOutcome,
    ConfigurationConditionEffectGate,
    OriginRootConditionEffectGate,
    SavingThrowConditionEffectGate,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.registration import (
    ContentDeclaration,
    get_content_declaration,
    replace_content_declaration_at_cold_startup,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.types.abilities import AbilityName
from dnd.spells.catalog_content import (
    SPELL_CATALOG_METADATA_BY_CLASS,
    SPELL_CONTENT_IDENTITY_SPECS,
)


_Definition: TypeAlias = type[object] | Callable[..., object]


@dataclass(frozen=True, slots=True)
class _ExactMutation:
    effect_id: str
    condition_type: _Definition
    operation: ConditionEffectOperation
    target: ConditionEffectTarget


@dataclass(frozen=True, slots=True)
class _SelectorMutation:
    effect_id: str
    operation: ConditionEffectOperation
    target: ConditionEffectTarget
    required_tags: tuple[ConditionTag, ...] = ()
    required_removal_triggers: tuple[ConditionRemovalTrigger, ...] = ()


_Mutation: TypeAlias = _ExactMutation | _SelectorMutation


@dataclass(frozen=True, slots=True)
class _Branch:
    branch_id: str
    disposition: ConditionEffectDisposition
    gates: tuple[ConditionEffectGate, ...]
    effects: tuple[_Mutation, ...]
    included_creature_types: tuple[str, ...] = ()
    excluded_creature_types: tuple[str, ...] = ()


_AUTOMATIC = (AutomaticConditionEffectGate(),)
_ACTION_SUCCEEDED = (
    ActionOutcomeConditionEffectGate(
        outcomes=(ConditionActionOutcome.SUCCEEDED,),
    ),
)
_ATTACK_HIT = (
    AttackOutcomeConditionEffectGate(
        outcomes=(
            ConditionAttackOutcome.HIT,
            ConditionAttackOutcome.CRITICAL,
        ),
    ),
)


def _failed_save(
    ability: AbilityName,
    *,
    dc_source: ConditionSaveDCSource = (
        ConditionSaveDCSource.ACTOR_SPELL_SAVE_DC
    ),
    fixed_dc: int | None = None,
) -> tuple[SavingThrowConditionEffectGate, ...]:
    return (
        SavingThrowConditionEffectGate(
            ability=ability,
            outcome=ConditionSaveOutcome.FAILED,
            dc_source=dc_source,
            fixed_dc=fixed_dc,
        ),
    )


def _config(
    key: str,
    *values: str,
) -> tuple[ConfigurationConditionEffectGate, ...]:
    return (
        ConfigurationConditionEffectGate(
            configuration_key=key,
            values=values,
        ),
    )


def _origin_root(
    *root_ids: str,
) -> tuple[OriginRootConditionEffectGate, ...]:
    return (OriginRootConditionEffectGate(origin_root_ids=root_ids),)


def _apply(
    effect_id: str,
    condition_type: _Definition,
    target: ConditionEffectTarget,
) -> _ExactMutation:
    return _ExactMutation(
        effect_id=effect_id,
        condition_type=condition_type,
        operation=ConditionEffectOperation.APPLY,
        target=target,
    )


def _remove(
    effect_id: str,
    condition_type: _Definition,
    target: ConditionEffectTarget,
    *,
    cleanse: bool = False,
) -> _ExactMutation:
    return _ExactMutation(
        effect_id=effect_id,
        condition_type=condition_type,
        operation=(
            ConditionEffectOperation.CLEANSE
            if cleanse
            else ConditionEffectOperation.REMOVE
        ),
        target=target,
    )


def _cleanse_tags(
    effect_id: str,
    target: ConditionEffectTarget,
    *tags: ConditionTag,
) -> _SelectorMutation:
    return _SelectorMutation(
        effect_id=effect_id,
        operation=ConditionEffectOperation.CLEANSE,
        target=target,
        required_tags=tuple(sorted(tags, key=lambda tag: tag.value)),
    )


def _cleanse_triggers(
    effect_id: str,
    target: ConditionEffectTarget,
    *triggers: ConditionRemovalTrigger,
) -> _SelectorMutation:
    return _SelectorMutation(
        effect_id=effect_id,
        operation=ConditionEffectOperation.CLEANSE,
        target=target,
        required_removal_triggers=tuple(sorted(
            triggers,
            key=lambda trigger: trigger.value,
        )),
    )


def _branch(
    branch_id: str,
    disposition: ConditionEffectDisposition,
    effects: tuple[_Mutation, ...],
    *,
    gates: tuple[ConditionEffectGate, ...] = _AUTOMATIC,
    included: tuple[str, ...] = (),
    excluded: tuple[str, ...] = (),
) -> _Branch:
    return _Branch(
        branch_id=branch_id,
        disposition=disposition,
        gates=gates,
        effects=effects,
        included_creature_types=tuple(sorted(included)),
        excluded_creature_types=tuple(sorted(excluded)),
    )


def _single_apply(
    condition_type: _Definition,
    *,
    target: ConditionEffectTarget = ConditionEffectTarget.SELECTED_TARGET,
    disposition: ConditionEffectDisposition = (
        ConditionEffectDisposition.BENEFICIAL
    ),
    gates: tuple[ConditionEffectGate, ...] = _AUTOMATIC,
    effect_id: str = "condition.apply",
) -> tuple[_Branch, ...]:
    return (
        _branch(
            "condition",
            disposition,
            (_apply(effect_id, condition_type, target),),
            gates=gates,
        ),
    )


_SPELL_BRANCHES: dict[_Definition, tuple[_Branch, ...]] = {
    # These roots expose only concentration publicly; their other public
    # effects belong to exact granted-action definitions below.
    conjuration.CallLightning: (),
    evocation.Sunbeam: (),
    necromancy.Eyebite: (),
    transmutation.Telekinesis: (),

    # Abjuration.
    abjuration.Resistance: _single_apply(abjuration.ResistanceEffect),
    abjuration.MageArmor: _single_apply(abjuration.MageArmorCondition),
    abjuration.ShieldOfFaith: _single_apply(abjuration.ShieldOfFaithEffect),
    abjuration.Sanctuary: _single_apply(abjuration.SanctuaryEffect),
    abjuration.LesserRestoration: (
        _branch(
            "exact-condition-cleanse",
            ConditionEffectDisposition.BENEFICIAL,
            tuple(
                _remove(
                    "cleanse."
                    + get_content_declaration(
                        condition_type,
                    ).ref.content_id,
                    condition_type,
                    ConditionEffectTarget.SELECTED_TARGET,
                    cleanse=True,
                )
                for condition_type in (
                    conditions.Blinded,
                    conditions.Deafened,
                    conditions.Paralyzed,
                    conditions.Poisoned,
                )
            ),
        ),
        _branch(
            "disease-cleanse",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _cleanse_tags(
                    "cleanse.disease",
                    ConditionEffectTarget.SELECTED_TARGET,
                    ConditionTag.DISEASE,
                ),
            ),
        ),
    ),
    abjuration.ProtectionFromPoison: (
        _branch(
            "poison-cleanse",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _remove(
                    "cleanse.poisoned",
                    conditions.Poisoned,
                    ConditionEffectTarget.SELECTED_TARGET,
                    cleanse=True,
                ),
                _apply(
                    "condition.protection_from_poison",
                    abjuration.ProtectionFromPoisonEffect,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
        ),
    ),
    abjuration.Aid: _single_apply(
        abjuration.AidEffect,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
    ),
    abjuration.ProtectionFromEnergy: _single_apply(
        abjuration.ProtectionFromEnergyEffect,
    ),
    abjuration.BeaconOfHope: _single_apply(
        abjuration.BeaconOfHopeEffect,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
    ),
    abjuration.RemoveCurse: (
        _branch(
            "curse-cleanse",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _cleanse_tags(
                    "cleanse.curse",
                    ConditionEffectTarget.SELECTED_TARGET,
                    ConditionTag.CURSE,
                ),
            ),
        ),
    ),
    abjuration.Stoneskin: _single_apply(abjuration.StoneskinEffect),
    abjuration.Banishment: _single_apply(
        abjuration.BanishedCondition,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_failed_save("charisma"),
    ),
    abjuration.DeathWard: _single_apply(abjuration.DeathWardEffect),
    abjuration.FreedomOfMovement: _single_apply(
        abjuration.FreedomOfMovementEffect,
    ),
    abjuration.GreaterRestoration: (
        _branch(
            "exact-condition-cleanse",
            ConditionEffectDisposition.BENEFICIAL,
            tuple(
                _remove(
                    "cleanse."
                    + get_content_declaration(
                        condition_type,
                    ).ref.content_id,
                    condition_type,
                    ConditionEffectTarget.SELECTED_TARGET,
                    cleanse=True,
                )
                for condition_type in (
                    conditions.Charmed,
                    conditions.Poisoned,
                    conditions.Blinded,
                    conditions.Deafened,
                    conditions.Paralyzed,
                    conditions.Stunned,
                    conditions.Frightened,
                )
            ),
        ),
        *tuple(
            _branch(
                f"{tag.value}-cleanse",
                ConditionEffectDisposition.BENEFICIAL,
                (
                    _cleanse_tags(
                        f"cleanse.{tag.value}",
                        ConditionEffectTarget.SELECTED_TARGET,
                        tag,
                    ),
                ),
            )
            for tag in (
                ConditionTag.PETRIFICATION,
                ConditionTag.CURSE,
                ConditionTag.ABILITY_SCORE_REDUCTION,
                ConditionTag.HIT_POINT_MAXIMUM_REDUCTION,
            )
        ),
        _branch(
            "exhaustion-reduction",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _ExactMutation(
                    effect_id="reduce.exhaustion",
                    condition_type=conditions.Exhaustion,
                    operation=ConditionEffectOperation.REDUCE,
                    target=ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
        ),
    ),
    abjuration.GlobeOfInvulnerability: _single_apply(
        abjuration.GlobeZone,
        target=ConditionEffectTarget.WORLD_POSITION,
        disposition=ConditionEffectDisposition.NEUTRAL,
    ),
    abjuration.AntimagicField: _single_apply(
        abjuration.AntimagicFieldZone,
        target=ConditionEffectTarget.WORLD_POSITION,
        disposition=ConditionEffectDisposition.NEUTRAL,
    ),

    # Conjuration.
    conjuration.Grease: (
        _branch(
            "zone",
            ConditionEffectDisposition.NEUTRAL,
            (
                _apply(
                    "condition.grease_zone",
                    conjuration.GreaseZone,
                    ConditionEffectTarget.WORLD_POSITION,
                ),
            ),
        ),
        _branch(
            "failed-save-prone",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.prone",
                    conditions.Prone,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=_failed_save("dexterity"),
        ),
    ),
    conjuration.FogCloud: _single_apply(
        conjuration.FogCloudZone,
        target=ConditionEffectTarget.WORLD_POSITION,
        disposition=ConditionEffectDisposition.NEUTRAL,
    ),
    conjuration.Web: (
        _branch(
            "zone",
            ConditionEffectDisposition.NEUTRAL,
            (
                _apply(
                    "condition.web_zone",
                    conjuration.WebZone,
                    ConditionEffectTarget.WORLD_POSITION,
                ),
            ),
        ),
        _branch(
            "failed-save-restrained",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.web_restrained",
                    conjuration.WebRestrained,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=_failed_save("dexterity"),
        ),
    ),
    conjuration.SpiritGuardians: (
        _branch(
            "zone",
            ConditionEffectDisposition.NEUTRAL,
            (
                _apply(
                    "condition.spirit_guardians_zone",
                    conjuration.SpiritGuardiansZone,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
        ),
        _branch(
            "occupant-slow",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.spirit_guardians_slowed",
                    conjuration.SpiritGuardiansSlowed,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
        ),
    ),
    conjuration.StinkingCloud: (
        _branch(
            "zone",
            ConditionEffectDisposition.NEUTRAL,
            (
                _apply(
                    "condition.stinking_cloud_zone",
                    conjuration.StinkingCloudZone,
                    ConditionEffectTarget.WORLD_POSITION,
                ),
            ),
        ),
    ),
    conjuration.SleetStorm: (
        _branch(
            "zone",
            ConditionEffectDisposition.NEUTRAL,
            (
                _apply(
                    "condition.sleet_storm_zone",
                    conjuration.SleetStormZone,
                    ConditionEffectTarget.WORLD_POSITION,
                ),
            ),
        ),
        _branch(
            "failed-dexterity-save",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.prone",
                    conditions.Prone,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=_failed_save("dexterity"),
        ),
    ),
    conjuration.Cloudkill: _single_apply(
        conjuration.CloudkillZone,
        target=ConditionEffectTarget.WORLD_POSITION,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    conjuration.InsectPlague: _single_apply(
        conjuration.InsectPlagueZone,
        target=ConditionEffectTarget.WORLD_POSITION,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    conjuration.IncendiaryCloud: _single_apply(
        conjuration.IncendiaryCloudZone,
        target=ConditionEffectTarget.WORLD_POSITION,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),

    # Divination.
    divination.Guidance: _single_apply(divination.GuidanceEffect),
    divination.SeeInvisibility: _single_apply(
        divination.SeeInvisibilityEffect,
        target=ConditionEffectTarget.ACTOR,
    ),
    divination.TrueSeeing: _single_apply(divination.TrueSeeingEffect),

    # Enchantment.
    enchantment.CharmPerson: _single_apply(
        conditions.Charmed,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_failed_save("wisdom"),
    ),
    enchantment.Sleep: _single_apply(
        enchantment.SleepEffect,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    enchantment.Bane: _single_apply(
        enchantment.BaneEffect,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_failed_save("charisma"),
    ),
    enchantment.Bless: _single_apply(
        enchantment.BlessEffect,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
    ),
    enchantment.Command: tuple(
        _branch(
            command,
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    f"condition.command.{command}",
                    condition_type,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=(
                *_failed_save("wisdom"),
                *_config("command", command),
            ),
            excluded=("undead",),
        )
        for command, condition_type in (
            ("grovel", enchantment.CommandGrovelEffect),
            ("halt", enchantment.CommandHaltEffect),
            ("flee", enchantment.CommandFleeEffect),
        )
    ),
    enchantment.HoldPerson: (
        _branch(
            "failed-save",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.hold_person",
                    enchantment.HoldPersonEffect,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=_failed_save("wisdom"),
            included=("humanoid",),
        ),
    ),
    enchantment.HoldMonster: (
        _branch(
            "failed-save",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.hold_monster",
                    enchantment.HoldMonsterEffect,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=_failed_save("wisdom"),
            excluded=("undead",),
        ),
    ),
    enchantment.PowerWordStun: (
        _branch(
            "hp-threshold",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.power_word_stun",
                    enchantment.PowerWordStunEffect,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=_ACTION_SUCCEEDED,
        ),
    ),

    # Evocation.
    evocation.RayOfFrost: _single_apply(
        evocation.RayOfFrostEffect,
        target=ConditionEffectTarget.SELECTED_TARGET,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_ATTACK_HIT,
    ),
    evocation.ShockingGrasp: _single_apply(
        conditions.NoReactions,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_ATTACK_HIT,
    ),
    evocation.Light: _single_apply(
        evocation.LightEffect,
        target=ConditionEffectTarget.SELECTED_OBJECT,
        disposition=ConditionEffectDisposition.NEUTRAL,
    ),
    evocation.GuidingBolt: _single_apply(
        evocation.GuidingBoltMarked,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_ATTACK_HIT,
    ),
    conjuration.Darkness: _single_apply(
        conjuration.DarknessZone,
        target=ConditionEffectTarget.WORLD_POSITION,
        disposition=ConditionEffectDisposition.NEUTRAL,
    ),
    evocation.GustOfWind: _single_apply(
        evocation.GustOfWindZone,
        target=ConditionEffectTarget.WORLD_POSITION,
        disposition=ConditionEffectDisposition.NEUTRAL,
    ),
    conjuration.Daylight: (
        _branch(
            "zone-and-darkness-removal",
            ConditionEffectDisposition.NEUTRAL,
            (
                _apply(
                    "condition.daylight_zone",
                    conjuration.DaylightZone,
                    ConditionEffectTarget.WORLD_POSITION,
                ),
                _remove(
                    "condition.darkness_zone.remove",
                    conjuration.DarknessZone,
                    ConditionEffectTarget.WORLD_POSITION,
                    cleanse=True,
                ),
            ),
        ),
    ),
    evocation.IceStorm: _single_apply(
        evocation.IceStormTerrain,
        target=ConditionEffectTarget.WORLD_POSITION,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    evocation.HealSpell: (
        _branch(
            "condition-cleanse",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _remove(
                    "cleanse.blinded",
                    conditions.Blinded,
                    ConditionEffectTarget.SELECTED_TARGET,
                    cleanse=True,
                ),
                _remove(
                    "cleanse.deafened",
                    conditions.Deafened,
                    ConditionEffectTarget.SELECTED_TARGET,
                    cleanse=True,
                ),
            ),
        ),
    ),
    evocation.PrismaticSpray: (
        _branch(
            "indigo",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.prismatic_restrained",
                    evocation.PrismaticRestrained,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=(
                *_failed_save("dexterity"),
                *_config("prismatic_roll", "7"),
            ),
        ),
        _branch(
            "violet",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.blinded",
                    conditions.Blinded,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=(
                *_failed_save("dexterity"),
                *_config("prismatic_roll", "8"),
            ),
        ),
    ),
    evocation.DivineWord: (
        _branch(
            "wrapper",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.divine_word",
                    evocation.DivineWordEffect,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
        ),
    ),
    evocation.Sunburst: (
        _branch(
            "failed-save",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.sunburst_blinded",
                    evocation.SunburstBlindedEffect,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=_failed_save("constitution"),
        ),
    ),
    evocation.MassHeal: (
        _branch(
            "condition-cleanse",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _remove(
                    "cleanse.blinded",
                    conditions.Blinded,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                    cleanse=True,
                ),
                _remove(
                    "cleanse.deafened",
                    conditions.Deafened,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                    cleanse=True,
                ),
            ),
        ),
    ),

    # Illusion.
    illusion.ColorSpray: (
        _branch(
            "hp-pool",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.color_spray",
                    illusion.ColorSprayEffect,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
        ),
    ),
    illusion.Blur: _single_apply(
        illusion.BlurEffect,
        target=ConditionEffectTarget.ACTOR,
    ),
    illusion.Invisibility: _single_apply(conditions.InvisibilityEffect),
    illusion.MirrorImage: _single_apply(
        illusion.MirrorImageEffect,
        target=ConditionEffectTarget.ACTOR,
    ),
    illusion.Silence: (
        _branch(
            "zone",
            ConditionEffectDisposition.NEUTRAL,
            (
                _apply(
                    "condition.silence_zone",
                    illusion.SilenceZone,
                    ConditionEffectTarget.WORLD_POSITION,
                ),
            ),
        ),
    ),
    illusion.Fear: (
        _branch(
            "failed-save",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.fear",
                    illusion.FearEffect,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=_failed_save("wisdom"),
        ),
    ),
    illusion.HypnoticPattern: (
        _branch(
            "failed-save",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.hypnotic_pattern",
                    illusion.HypnoticPatternEffect,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=_failed_save("wisdom"),
        ),
    ),
    illusion.GreaterInvisibility: _single_apply(
        conditions.GreaterInvisibilityEffect,
    ),

    # Necromancy.
    necromancy.ChillTouch: (
        _branch(
            "hit",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.chill_touch_tracker",
                    necromancy.ChillTouchEffect,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
                _apply(
                    "condition.no_healing",
                    necromancy.NoHealing,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=_ATTACK_HIT,
        ),
    ),
    necromancy.BlindnessDeafness: tuple(
        _branch(
            variant,
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    f"condition.blindness_deafness.{variant}",
                    necromancy.BlindnessDeafnessEffect,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=(
                *_failed_save("constitution"),
                *_config("affliction", variant),
            ),
        )
        for variant in ("blinded", "deafened")
    ),
    necromancy.NecroticBless: (
        _branch(
            "undead",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _apply(
                    "condition.bless",
                    enchantment.BlessEffect,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            included=("undead",),
        ),
        _branch(
            "living",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.bane",
                    enchantment.BaneEffect,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=_failed_save("charisma"),
            excluded=("undead",),
        ),
    ),
    necromancy.BestowCurse: tuple(
        _branch(
            option,
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    f"condition.bestow_curse.{option}",
                    condition_type,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=(
                *_failed_save("wisdom"),
                *_config("curse_option", option),
            ),
        )
        for option, condition_type in (
            ("ability", necromancy.AbilityCurseEffect),
            ("attack", necromancy.AttackCurseEffect),
            ("inaction", necromancy.InactionCurseEffect),
            ("damage", necromancy.DamageCurseEffect),
        )
    ),

    # Transmutation.
    transmutation.JumpSpell: _single_apply(transmutation.JumpEffect),
    transmutation.ExpeditiousRetreat: _single_apply(
        transmutation.ExpeditiousRetreatEffect,
        target=ConditionEffectTarget.ACTOR,
    ),
    transmutation.SpikeGrowth: _single_apply(
        transmutation.SpikeGrowthZone,
        target=ConditionEffectTarget.WORLD_POSITION,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    transmutation.DarkvisionSpell: _single_apply(
        transmutation.DarkvisionEffect,
    ),
    transmutation.EnhanceAbility: tuple(
        _branch(
            ability,
            ConditionEffectDisposition.BENEFICIAL,
            (
                _apply(
                    f"condition.enhance_ability.{ability}",
                    transmutation.EnhanceAbilityEffect,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=_config("ability", ability),
        )
        for ability in (
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        )
    ),
    transmutation.EnlargeReduce: tuple(
        _branch(
            mode,
            (
                ConditionEffectDisposition.BENEFICIAL
                if mode == "enlarge"
                else ConditionEffectDisposition.HARMFUL
            ),
            (
                _apply(
                    f"condition.enlarge_reduce.{mode}",
                    transmutation.EnlargeReduceEffect,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=_config("mode", mode),
        )
        for mode in ("enlarge", "reduce")
    ),
    transmutation.Slow: _single_apply(
        transmutation.SlowedEffect,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_failed_save("wisdom"),
    ),
    transmutation.Haste: _single_apply(transmutation.HasteEffect),
    transmutation.Regenerate: _single_apply(
        transmutation.RegeneratingEffect,
    ),
}


def _succeeded_save(
    ability: AbilityName,
    *,
    dc_source: ConditionSaveDCSource = (
        ConditionSaveDCSource.ACTOR_ACTION_DC
    ),
    fixed_dc: int | None = None,
) -> tuple[SavingThrowConditionEffectGate, ...]:
    return (
        SavingThrowConditionEffectGate(
            ability=ability,
            outcome=ConditionSaveOutcome.SUCCEEDED,
            dc_source=dc_source,
            fixed_dc=fixed_dc,
        ),
    )


_ACTION_AND_REACTION_BRANCHES: dict[_Definition, tuple[_Branch, ...]] = {
    # Core actions.
    actions.Dash: _single_apply(
        conditions.Dashing,
        target=ConditionEffectTarget.ACTOR,
    ),
    actions.Dodge: _single_apply(
        conditions.Dodging,
        target=ConditionEffectTarget.ACTOR,
    ),
    actions.Disengage: _single_apply(
        conditions.Disengaging,
        target=ConditionEffectTarget.ACTOR,
    ),
    actions.Hide: _single_apply(
        conditions.Hidden,
        target=ConditionEffectTarget.ACTOR,
    ),
    actions.DropProne: _single_apply(
        conditions.Prone,
        target=ConditionEffectTarget.ACTOR,
        disposition=ConditionEffectDisposition.NEUTRAL,
    ),
    actions.Shove: (
        _branch(
            "successful-prone-shove",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.prone",
                    conditions.Prone,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=(
                *_ACTION_SUCCEEDED,
                *_config("shove_mode", "prone"),
            ),
        ),
    ),
    actions.DropConcentration: (
        _branch(
            "drop-concentration",
            ConditionEffectDisposition.NEUTRAL,
            (
                _remove(
                    "condition.concentrating.remove",
                    conditions.Concentrating,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
        ),
    ),
    actions.StandUp: (
        _branch(
            "stand-up",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _remove(
                    "condition.prone.remove",
                    conditions.Prone,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
        ),
    ),
    actions.ShakeAwake: (
        _branch(
            "shake-awake",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _cleanse_triggers(
                    "condition.shake_awake.cleanse",
                    ConditionEffectTarget.SELECTED_TARGET,
                    ConditionRemovalTrigger.SHAKE_AWAKE,
                ),
            ),
        ),
    ),

    # Barbarian actions and lifecycle feature.
    barbarian.RecklessAttack: _single_apply(
        barbarian.RecklessAttacking,
        target=ConditionEffectTarget.ACTOR,
        disposition=ConditionEffectDisposition.NEUTRAL,
    ),
    rage.Rage: _single_apply(
        rage.Raging,
        target=ConditionEffectTarget.ACTOR,
    ),
    rage.Frenzy: (
        _branch(
            "frenzy",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _apply(
                    "condition.raging",
                    rage.Raging,
                    ConditionEffectTarget.ACTOR,
                ),
                _apply(
                    "condition.frenzied",
                    rage.Frenzied,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
        ),
    ),
    rage.EndRage: (
        _branch(
            "end-rage",
            ConditionEffectDisposition.NEUTRAL,
            (
                _remove(
                    "condition.raging.remove",
                    rage.Raging,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
        ),
    ),
    barbarian.IntimidatingPresence: (
        _branch(
            "failed-save",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.frightened",
                    conditions.Frightened,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=_failed_save(
                "wisdom",
                dc_source=ConditionSaveDCSource.ACTOR_ACTION_DC,
            ),
        ),
        _branch(
            "successful-save",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _apply(
                    "condition.intimidating_presence_immunity",
                    barbarian.IntimidatingPresenceImmunity,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=_succeeded_save("wisdom"),
        ),
    ),
    # Items and original extensions.
    field_focus.DeployFieldFocus: _single_apply(
        field_focus.FieldFocus,
        target=ConditionEffectTarget.SOURCE_ITEM,
        disposition=ConditionEffectDisposition.NEUTRAL,
    ),
    consumables._DrinkGreaterInvisibilityPotionAction: _single_apply(
        conditions.GreaterInvisibilityEffect,
        target=ConditionEffectTarget.ACTOR,
    ),
    consumables._DrinkHastePotionAction: _single_apply(
        transmutation.HasteEffect,
        target=ConditionEffectTarget.ACTOR,
    ),
    consumables._ApplyWeaponCoatAction: tuple(
        _branch(
            branch_id,
            ConditionEffectDisposition.BENEFICIAL,
            (
                _apply(
                    f"condition.weapon_coat.{branch_id}",
                    condition_type,
                    ConditionEffectTarget.EQUIPPED_ITEM,
                ),
                *(
                    (
                        _apply(
                            "condition.concentrating",
                            conditions.Concentrating,
                            ConditionEffectTarget.ACTOR,
                        ),
                    )
                    if condition_type
                    is consumables._ConcentrationFireWeaponCoatCondition
                    else ()
                ),
            ),
            gates=_origin_root(origin_root_ref),
        )
        for branch_id, condition_type, origin_root_ref in (
            (
                "fire",
                consumables._FireWeaponCoatCondition,
                "consumable.weapon_coat.fire",
            ),
            (
                "lightning",
                consumables._LightningWeaponCoatCondition,
                "consumable.weapon_coat.lightning",
            ),
            (
                "concentration_fire",
                consumables._ConcentrationFireWeaponCoatCondition,
                "consumable.weapon_coat.concentration_fire",
            ),
            (
                "timed_fire",
                consumables._TimedFireWeaponCoatCondition,
                "consumable.weapon_coat.timed_fire",
            ),
        )
    ),
    aegis_spark.AegisSpark: (
        _branch(
            "ward",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _apply(
                    "condition.aegis_spark",
                    aegis_spark.AegisSparkEffect,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
        ),
    ),
    skeleton_abilities.MarkTargetAction: (
        _branch(
            "mark",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.concentrating",
                    conditions.Concentrating,
                    ConditionEffectTarget.ACTOR,
                ),
                _apply(
                    "condition.marked",
                    skeleton_abilities.Marked,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
        ),
    ),
    environment_interactables.PullLeverAction: (
        _branch(
            "deactivate-trap",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _remove(
                    "condition.spike_trap.remove",
                    tile_conditions.SpikeTrapCondition,
                    ConditionEffectTarget.WORLD_POSITION,
                ),
            ),
        ),
    ),

    # Spell-granted actions.
    transmutation.BonusDash: _single_apply(
        conditions.Dashing,
        target=ConditionEffectTarget.ACTOR,
    ),
    abjuration.FreedomOfMovementEscape: (
        _branch(
            "nonmagical-restraint",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _remove(
                    "condition.grappled.remove",
                    conditions.Grappled,
                    ConditionEffectTarget.ACTOR,
                ),
                _remove(
                    "condition.restrained.remove",
                    conditions.Restrained,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
            gates=_config("restraint_origin", "nonmagical"),
        ),
    ),
    conjuration.EscapeWebAction: (
        _branch(
            "escape",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _remove(
                    "condition.web_restrained.remove",
                    conjuration.WebRestrained,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
            gates=_ACTION_SUCCEEDED,
        ),
    ),
    conjuration.EatFromFeast: (
        _branch(
            "feast",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _apply(
                    "condition.heroes_feast",
                    conjuration.HeroesFeastBuff,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
        ),
    ),
    evocation.SunbeamStrike: _single_apply(
        conditions.Blinded,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_failed_save("constitution"),
    ),
    necromancy.EyebiteStrike: (
        _branch(
            "asleep",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.eyebite_asleep",
                    necromancy.EyebiteAsleepEffect,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=(
                *_failed_save("wisdom"),
                *_config("eyebite_mode", "asleep"),
            ),
        ),
        _branch(
            "panicked",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.eyebite_panicked",
                    necromancy.EyebitePanickedEffect,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=(
                *_failed_save("wisdom"),
                *_config("eyebite_mode", "panicked"),
            ),
        ),
        _branch(
            "sickened",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.eyebite_sickened",
                    necromancy.SickenedCondition,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=(
                *_failed_save("wisdom"),
                *_config("eyebite_mode", "sickened"),
            ),
        ),
    ),
    transmutation.TelekinesisRestrain: _single_apply(
        conditions.Restrained,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_ACTION_SUCCEEDED,
    ),

    # Monster/NPC actions and traits.
    monster_traits.DivineEminenceAction: _single_apply(
        monster_traits.DivineEminenceActive,
        target=ConditionEffectTarget.ACTOR,
    ),
    monster_traits.LeadershipAction: _single_apply(
        monster_traits.LeadershipAura,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
    ),
    monster_traits.WolfBiteProneRiderFeature: (
        _branch(
            "bite-rider",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.prone",
                    conditions.Prone,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=(
                *_ATTACK_HIT,
                *_failed_save(
                    "strength",
                    dc_source=ConditionSaveDCSource.FIXED,
                    fixed_dc=11,
                ),
            ),
        ),
    ),
    monster_traits.DireWolfBiteProneRiderFeature: (
        _branch(
            "bite-rider",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.prone",
                    conditions.Prone,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=(
                *_ATTACK_HIT,
                *_failed_save(
                    "strength",
                    dc_source=ConditionSaveDCSource.FIXED,
                    fixed_dc=13,
                ),
            ),
        ),
    ),
    monster_traits.GhoulClawsParalysisFeature: (
        _branch(
            "claws-rider",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.ghoul_paralysis",
                    monster_traits.GhoulParalysisEffect,
                    ConditionEffectTarget.SELECTED_TARGET,
                ),
            ),
            gates=(
                *_ATTACK_HIT,
                *_failed_save(
                    "constitution",
                    dc_source=ConditionSaveDCSource.FIXED,
                    fixed_dc=10,
                ),
            ),
            excluded=("undead", "elf"),
        ),
    ),
    monster_traits.RampageFeature: (
        _branch(
            "melee-kill",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _apply(
                    "condition.rampage_available",
                    monster_traits.RampageAvailable,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
            gates=_config("trigger", "melee_kill"),
        ),
    ),

    # Reaction handler with a genuine condition child.
    abjuration.ShieldReactionHandler: _single_apply(
        abjuration.ShieldBuff,
        target=ConditionEffectTarget.ACTOR,
    ),

    # Public condition/zone behaviors that directly create child conditions.
    conjuration.GreaseZone: _single_apply(
        conditions.Prone,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_failed_save("dexterity"),
    ),
    conjuration.WebRestrained: _single_apply(
        conditions.Restrained,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    conjuration.WebZone: _single_apply(
        conjuration.WebRestrained,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_failed_save("dexterity"),
    ),
    conjuration.SpiritGuardiansZone: _single_apply(
        conjuration.SpiritGuardiansSlowed,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    conjuration.StinkingCloudZone: _single_apply(
        conjuration.NauseatedCondition,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
        disposition=ConditionEffectDisposition.HARMFUL,
        gates=_failed_save("constitution"),
    ),
    conjuration.SleetStormZone: (
        _branch(
            "failed-dexterity-save",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.prone",
                    conditions.Prone,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=_failed_save("dexterity"),
        ),
        _branch(
            "failed-concentration-save",
            ConditionEffectDisposition.HARMFUL,
            (
                _remove(
                    "condition.concentrating.remove",
                    conditions.Concentrating,
                    ConditionEffectTarget.EACH_AFFECTED_ENTITY,
                ),
            ),
            gates=_failed_save("constitution"),
        ),
    ),
    conjuration.HeroesFeastBuff: (
        _branch(
            "condition-cleanse",
            ConditionEffectDisposition.BENEFICIAL,
            (
                _remove(
                    "cleanse.poisoned",
                    conditions.Poisoned,
                    ConditionEffectTarget.ACTOR,
                    cleanse=True,
                ),
                _remove(
                    "cleanse.frightened",
                    conditions.Frightened,
                    ConditionEffectTarget.ACTOR,
                    cleanse=True,
                ),
            ),
        ),
    ),
    enchantment.HoldPersonEffect: _single_apply(
        conditions.Paralyzed,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    enchantment.HoldMonsterEffect: _single_apply(
        conditions.Paralyzed,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    enchantment.PowerWordStunEffect: _single_apply(
        conditions.Stunned,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    enchantment.CommandGrovelEffect: _single_apply(
        conditions.Prone,
        target=ConditionEffectTarget.ACTOR,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    evocation.SunburstBlindedEffect: _single_apply(
        conditions.Blinded,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    evocation.PrismaticRestrained: _single_apply(
        conditions.Restrained,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    evocation.DivineWordEffect: (
        _branch(
            "hp-21-30",
            ConditionEffectDisposition.HARMFUL,
            tuple(
                _apply(
                    "condition.hp_21_30."
                    + get_content_declaration(
                        condition_type,
                    ).ref.content_id,
                    condition_type,
                    ConditionEffectTarget.ACTOR,
                )
                for condition_type in (
                    conditions.Blinded,
                    conditions.Deafened,
                    conditions.Stunned,
                )
            ),
            gates=_config("target_hp_band", "21_30"),
        ),
        _branch(
            "hp-31-40",
            ConditionEffectDisposition.HARMFUL,
            tuple(
                _apply(
                    "condition.hp_31_40."
                    + get_content_declaration(
                        condition_type,
                    ).ref.content_id,
                    condition_type,
                    ConditionEffectTarget.ACTOR,
                )
                for condition_type in (
                    conditions.Blinded,
                    conditions.Deafened,
                )
            ),
            gates=_config("target_hp_band", "31_40"),
        ),
        _branch(
            "hp-41-50",
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    "condition.hp_41_50.deafened",
                    conditions.Deafened,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
            gates=_config("target_hp_band", "41_50"),
        ),
    ),
    illusion.FearEffect: _single_apply(
        conditions.Frightened,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    illusion.HypnoticPatternEffect: _single_apply(
        conditions.Charmed,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    illusion.ColorSprayEffect: _single_apply(
        conditions.Blinded,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    illusion.SilenceZone: _single_apply(
        illusion._SilenceDeafened,
        target=ConditionEffectTarget.EACH_AFFECTED_ENTITY,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    illusion._SilenceDeafened: _single_apply(
        conditions.Deafened,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    necromancy.BlindnessDeafnessEffect: tuple(
        _branch(
            variant,
            ConditionEffectDisposition.HARMFUL,
            (
                _apply(
                    f"condition.{variant}",
                    condition_type,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
            gates=_config("affliction", variant),
        )
        for variant, condition_type in (
            ("blinded", conditions.Blinded),
            ("deafened", conditions.Deafened),
        )
    ),
    necromancy.EyebitePanickedEffect: _single_apply(
        conditions.Frightened,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
    monster_traits.GhoulParalysisEffect: _single_apply(
        conditions.Paralyzed,
        disposition=ConditionEffectDisposition.HARMFUL,
    ),
}


NO_CONDITION_EFFECT_SPELL_TYPES: tuple[_Definition, ...] = (
    evocation.FireBolt,
    evocation.SacredFlame,
    conjuration.PoisonSpray,
    conjuration.AcidSplash,
    evocation.EldritchBlast,
    evocation.TrueStrike,
    evocation.MagicMissile,
    evocation.BurningHands,
    evocation.Thunderwave,
    necromancy.FalseLife,
    evocation.CureWounds,
    evocation.HealingWord,
    necromancy.InflictWounds,
    evocation.Shatter,
    evocation.ScorchingRay,
    conjuration.MistyStep,
    evocation.ContinualFlame,
    evocation.PrayerOfHealing,
    evocation.Fireball,
    evocation.LightningBolt,
    evocation.MassHealingWord,
    necromancy.Blight,
    conjuration.DimensionDoor,
    evocation.ConeOfCold,
    evocation.FlameStrike,
    evocation.MassCureWounds,
    evocation.CircleOfDeath,
    transmutation.Disintegrate,
    evocation.ChainLightning,
    necromancy.Harm,
    necromancy.FingerOfDeath,
    enchantment.PowerWordKill,
    conjuration.GuardianOfFaith,
)
INDIRECT_CONDITION_EFFECT_SPELL_TYPES: tuple[_Definition, ...] = (
    conjuration.HeroesFeast,
)
INTERNAL_CONDITION_PRODUCER_TYPES: tuple[_Definition, ...] = (
    fighter.ActionSurging,
    fighter.ExtraAttacksGranted,
    conditions.ConcentrationActionMarker,
    necromancy.EyebiteCastingState,
    abjuration.AntimagicSuppression,
    skeleton_abilities.MarkCooldown,
    monster_traits.SimpleMarkerCondition,
)
INTERNAL_ONLY_CONDITION_EFFECT_SOURCE_TYPES: tuple[_Definition, ...] = (
    fighter.ActionSurge,
    fighter.ExtraAttackFeature,
    monster_traits.MartialAdvantageFeature,
    monster_traits.SneakAttackFeature,
    monster_traits.BruteFeature,
    monster_traits.SurpriseAttackFeature,
    monster_traits.DivineEminenceActive,
    abjuration.AntimagicFieldZone,
)


def _profile_for(
    source_type: _Definition,
    branches: tuple[_Branch, ...],
) -> AuthoredConditionEffectProfile:
    source_ref = get_content_declaration(source_type).ref
    authored_branches = []
    for branch in branches:
        authored_effects = []
        for effect in branch.effects:
            if isinstance(effect, _ExactMutation):
                authored_effects.append(AuthoredConditionEffect(
                    effect_id=effect.effect_id,
                    source_ref=source_ref,
                    operation=effect.operation,
                    condition_ref=get_content_declaration(
                        effect.condition_type,
                    ).ref,
                    target=effect.target,
                ))
            else:
                authored_effects.append(AuthoredConditionEffect(
                    effect_id=effect.effect_id,
                    source_ref=source_ref,
                    operation=effect.operation,
                    selector=ConditionEffectSelector(
                        required_tags=effect.required_tags,
                        required_removal_triggers=(
                            effect.required_removal_triggers
                        ),
                    ),
                    target=effect.target,
                ))
        authored_branches.append(AuthoredConditionEffectBranch(
            branch_id=branch.branch_id,
            disposition=branch.disposition,
            included_creature_types=branch.included_creature_types,
            excluded_creature_types=branch.excluded_creature_types,
            gates=branch.gates,
            effects=tuple(authored_effects),
        ))
    return AuthoredConditionEffectProfile(
        branches=tuple(authored_branches),
    )


def _with_concentration(
    branches: tuple[_Branch, ...],
) -> tuple[_Branch, ...]:
    return (
        *branches,
        _branch(
            "concentration",
            ConditionEffectDisposition.NEUTRAL,
            (
                _apply(
                    "condition.concentrating",
                    conditions.Concentrating,
                    ConditionEffectTarget.ACTOR,
                ),
            ),
        ),
    )


def _condition_dependencies(
    profile: AuthoredConditionEffectProfile,
) -> tuple[ContentDependency, ...]:
    ordered_refs: dict[str, ContentRef] = {}
    for effect in profile.effects:
        if (
            effect.operation is ConditionEffectOperation.APPLY
            and effect.condition_ref is not None
        ):
            ordered_refs.setdefault(
                effect.condition_ref.identity_key,
                effect.condition_ref,
            )
    return tuple(
        ContentDependency(
            relation=ContentDependencyRelation.APPLIES_CONDITION,
            target_ref=ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes=(
                "Exact ordered authored condition application; operation and "
                "branch semantics are authenticated by the effect profile."
            ),
        )
        for ref in ordered_refs.values()
    )


def _source_types() -> tuple[_Definition, ...]:
    """Return every known behavior declaration source exactly once."""
    candidates = (
        *(spec.spell_type for spec in SPELL_CONTENT_IDENTITY_SPECS),
        *(spec.action_type for spec in ACTION_BEHAVIOR_IDENTITY_SPECS),
        *(spec.condition_type for spec in CONDITION_BEHAVIOR_IDENTITY_SPECS),
        *(spec.handler_type for spec in REACTION_BEHAVIOR_IDENTITY_SPECS),
        *tuple(_ACTION_AND_REACTION_BRANCHES),
        *INTERNAL_ONLY_CONDITION_EFFECT_SOURCE_TYPES,
    )
    by_ref: dict[str, _Definition] = {}
    for candidate in candidates:
        try:
            ref = get_content_declaration(candidate).ref
        except ValueError:
            continue
        existing = by_ref.get(ref.identity_key)
        if existing is not None and existing is not candidate:
            raise ValueError(
                f"Multiple runtime sources claim {ref.identity_key}",
            )
        by_ref[ref.identity_key] = candidate
    return tuple(by_ref[key] for key in sorted(by_ref))


def builtin_condition_effect_source_types() -> tuple[_Definition, ...]:
    """Return the exact built-in runtime sources audited by this inventory."""
    return _source_types()


def populate_builtin_condition_effects(
    declarations: tuple[ContentDeclaration, ...],
) -> tuple[ContentDeclaration, ...]:
    """Attach the closed built-in effect inventory before registry freeze."""
    all_spell_types = tuple(
        spec.spell_type
        for spec in SPELL_CONTENT_IDENTITY_SPECS
    )
    classified_spell_types = {
        *_SPELL_BRANCHES,
        *NO_CONDITION_EFFECT_SPELL_TYPES,
        *INDIRECT_CONDITION_EFFECT_SPELL_TYPES,
    }
    if classified_spell_types != set(all_spell_types):
        missing = sorted(
            spell_type.__name__
            for spell_type in set(all_spell_types) - classified_spell_types
        )
        unexpected = sorted(
            spell_type.__name__
            for spell_type in classified_spell_types - set(all_spell_types)
        )
        raise ValueError(
            "Spell condition-effect disposition inventory is not exhaustive: "
            f"missing={missing}, unexpected={unexpected}",
        )
    overlapping = (
        set(_SPELL_BRANCHES)
        & set(NO_CONDITION_EFFECT_SPELL_TYPES)
        | set(_SPELL_BRANCHES)
        & set(INDIRECT_CONDITION_EFFECT_SPELL_TYPES)
        | set(NO_CONDITION_EFFECT_SPELL_TYPES)
        & set(INDIRECT_CONDITION_EFFECT_SPELL_TYPES)
    )
    if overlapping:
        raise ValueError(
            "Spell condition-effect dispositions overlap: "
            + ", ".join(sorted(
                spell_type.__name__
                for spell_type in overlapping
            )),
        )

    profiles_by_source: dict[_Definition, AuthoredConditionEffectProfile] = {}
    for spell_type in all_spell_types:
        branches = _SPELL_BRANCHES.get(spell_type, ())
        metadata = SPELL_CATALOG_METADATA_BY_CLASS[spell_type]
        if metadata.concentration:
            branches = _with_concentration(branches)
        if branches:
            profiles_by_source[spell_type] = _profile_for(
                spell_type,
                branches,
            )
    for source_type, branches in _ACTION_AND_REACTION_BRANCHES.items():
        profiles_by_source[source_type] = _profile_for(
            source_type,
            branches,
        )

    replacements: dict[str, ContentDeclaration] = {}
    source_types_by_ref = {
        get_content_declaration(source_type).ref.identity_key: source_type
        for source_type in _source_types()
    }
    for declaration in declarations:
        source_type = source_types_by_ref.get(declaration.ref.identity_key)
        profile = (
            profiles_by_source.get(source_type)
            if source_type is not None
            else None
        )
        retained_dependencies = tuple(
            dependency
            for dependency in declaration.dependencies
            if dependency.relation
            is not ContentDependencyRelation.APPLIES_CONDITION
        )
        dependencies = (
            retained_dependencies
            if profile is None
            else (
                *retained_dependencies,
                *_condition_dependencies(profile),
            )
        )
        coverage = (
            ConditionEffectCoverage.PROFILED
            if profile is not None
            else (
                ConditionEffectCoverage.INDIRECT
                if source_type in INDIRECT_CONDITION_EFFECT_SPELL_TYPES
                else (
                    ConditionEffectCoverage.INTERNAL_ONLY
                    if source_type
                    in INTERNAL_ONLY_CONDITION_EFFECT_SOURCE_TYPES
                    else (
                        ConditionEffectCoverage.LIFECYCLE_ONLY
                        if declaration.runtime_behavior_kind
                        is RuntimeBehaviorKind.CONDITION
                        else ConditionEffectCoverage.NONE
                    )
                )
            )
        )
        if (
            declaration.dependencies == dependencies
            and declaration.condition_effect_coverage is coverage
            and declaration.condition_effect_profile == profile
        ):
            updated = declaration
        else:
            updated = declaration.model_copy(update={
                "dependencies": dependencies,
                "condition_effect_coverage": coverage,
                "condition_effect_profile": profile,
            })
            # Revalidate model-copy updates before the registry sees them.
            updated = ContentDeclaration.model_validate(
                dict(updated.__dict__),
            )
        if source_type is not None and updated is not declaration:
            replace_content_declaration_at_cold_startup(
                source_type,
                updated,
            )
        replacements[updated.ref.identity_key] = updated

    if len(replacements) != len(declarations):
        raise ValueError(
            "Built-in declaration inventory contains duplicate refs",
        )
    return tuple(
        replacements[declaration.ref.identity_key]
        for declaration in declarations
    )


__all__ = [
    "INDIRECT_CONDITION_EFFECT_SPELL_TYPES",
    "INTERNAL_CONDITION_PRODUCER_TYPES",
    "INTERNAL_ONLY_CONDITION_EFFECT_SOURCE_TYPES",
    "NO_CONDITION_EFFECT_SPELL_TYPES",
    "builtin_condition_effect_source_types",
    "populate_builtin_condition_effects",
]
