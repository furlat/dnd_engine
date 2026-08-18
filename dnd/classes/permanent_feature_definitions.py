"""Authored identities for permanent class and feat structure.

Permanent character features are not runtime conditions.  Character
composition installs their exact actions, handlers, resources, modifiers, and
formulae through reversible grant receipts.  This module owns only the cold
content identities and their explicit runtime dependencies.
"""

from dataclasses import dataclass

from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
    resolve_content_icon_key,
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
    behavior_content_ref,
    behavior_identity,
    get_content_declaration,
)
from dnd.types.behaviors import RuntimeBehaviorKind


_PACK_ID = "content.srd_5_1_cc"
_VERSION = 1


@dataclass(frozen=True, slots=True)
class _PermanentFeatureSpec:
    content_id: str
    display_name: str
    description: str
    owner_group: str
    sort_order: int
    definition_kind: ContentDefinitionKind = ContentDefinitionKind.CLASS_FEATURE
    granted_action_ids: tuple[str, ...] = ()
    granted_spell_ids: tuple[str, ...] = ()
    installed_reaction_ids: tuple[str, ...] = ()
    pack_id: str = _PACK_ID
    version: int = _VERSION
    visibility: ContentVisibility = ContentVisibility.PUBLIC


class _PermanentFeatureMarker:
    """Private attachment point for one non-constructible declaration."""


def _runtime_dependency(
    *,
    relation: ContentDependencyRelation,
    definition_kind: ContentDefinitionKind,
    runtime_behavior_kind: RuntimeBehaviorKind,
    content_id: str,
    pack_id: str = _PACK_ID,
    version: int = _VERSION,
) -> ContentDependency:
    return ContentDependency(
        relation=relation,
        target_ref=behavior_content_ref(
            definition_kind=definition_kind,
            runtime_behavior_kind=runtime_behavior_kind,
            pack_id=pack_id,
            content_id=content_id,
            version=version,
        ),
        phase=ContentDependencyPhase.RUNTIME_REFERENCE,
        notes=(
            "Installed by the reversible character-grant applier while this "
            "permanent feature is owned."
        ),
    )


def _declare(spec: _PermanentFeatureSpec) -> ContentDeclaration:
    ref = behavior_content_ref(
        definition_kind=spec.definition_kind,
        runtime_behavior_kind=RuntimeBehaviorKind.CLASS_FEATURE,
        pack_id=spec.pack_id,
        content_id=spec.content_id,
        version=spec.version,
    )
    icon_key, _asset_digest = resolve_content_icon_key(ref, spec.content_id)
    marker = _PermanentFeatureMarker()
    behavior_identity(
        definition_kind=spec.definition_kind,
        runtime_behavior_kind=RuntimeBehaviorKind.CLASS_FEATURE,
        pack_id=spec.pack_id,
        content_id=spec.content_id,
        version=spec.version,
        descriptor=ContentDescriptorSpec(
            display_name=spec.display_name,
            description=spec.description,
            tags=(
                spec.owner_group,
                "class_feature",
                "permanent",
                "structural_grant",
            ),
            visibility=spec.visibility,
            presentation=ContentPresentation(
                icon_key=icon_key,
                visual_variant_key=spec.content_id,
                ui_group=f"class_features.{spec.owner_group}",
            ),
            ordering=ContentOrdering(
                sort_group=f"class_features.{spec.owner_group}",
                sort_order=spec.sort_order,
            ),
        ),
        provenance=ContentProvenance(
            primary_source_id=(
                "wotc.srd_5_1_cc"
                if spec.pack_id == _PACK_ID
                else "neurodragon.original_b2b3930"
            ),
            source_anchor=(
                f"SRD 5.1: {spec.display_name}"
                if spec.pack_id == _PACK_ID
                else f"Neurodragon original content: {spec.display_name}"
            ),
            relation=(
                ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION
                if spec.pack_id == _PACK_ID
                else ContentProvenanceRelation.ORIGINAL_CONTENT
            ),
            fidelity=ContentFidelity.COMPLETE,
            review_status=ContentReviewStatus.REVIEWED,
            notes=(
                "Permanent character structure is installed through an exact "
                "source-owned grant receipt, not a persistent condition."
            ),
        ),
        dependencies=(
            *(
                _runtime_dependency(
                    relation=ContentDependencyRelation.GRANTS_ACTION,
                    definition_kind=ContentDefinitionKind.ACTION,
                    runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
                    content_id=content_id,
                    pack_id=spec.pack_id,
                    version=spec.version,
                )
                for content_id in spec.granted_action_ids
            ),
            *(
                _runtime_dependency(
                    relation=ContentDependencyRelation.GRANTS_ACTION,
                    definition_kind=ContentDefinitionKind.SPELL,
                    runtime_behavior_kind=RuntimeBehaviorKind.SPELL,
                    content_id=content_id,
                    pack_id=spec.pack_id,
                    version=spec.version,
                )
                for content_id in spec.granted_spell_ids
            ),
            *(
                _runtime_dependency(
                    relation=ContentDependencyRelation.INSTALLS_HANDLER,
                    definition_kind=ContentDefinitionKind.REACTION,
                    runtime_behavior_kind=RuntimeBehaviorKind.REACTION,
                    content_id=content_id,
                    pack_id=spec.pack_id,
                    version=spec.version,
                )
                for content_id in spec.installed_reaction_ids
            ),
        ),
    )(marker)
    return get_content_declaration(marker)


BARBARIAN_BRUTAL_CRITICAL_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.brutal_critical",
    "Brutal Critical",
    "Extra damage dice on critical melee hits",
    "barbarian",
    90,
))
BARBARIAN_DANGER_SENSE_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.danger_sense",
    "Danger Sense",
    "Advantage on DEX saves against effects you can see",
    "barbarian",
    20,
))
BARBARIAN_FAST_MOVEMENT_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.fast_movement",
    "Fast Movement",
    "+10 ft speed when not in heavy armor",
    "barbarian",
    50,
))
BARBARIAN_FERAL_INSTINCT_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.feral_instinct",
    "Feral Instinct",
    "Advantage on initiative rolls",
    "barbarian",
    70,
))
BARBARIAN_INDOMITABLE_MIGHT_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.indomitable_might",
    "Indomitable Might",
    "Strength checks cannot be lower than your Strength score",
    "barbarian",
    180,
))
BARBARIAN_INTIMIDATING_PRESENCE_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.intimidating_presence",
    "Intimidating Presence",
    "Use an action to frighten creatures within 30 feet",
    "barbarian",
    100,
    granted_action_ids=(
        "action.class.barbarian.intimidating_presence",
        "action.class.barbarian.extend_intimidating_presence",
    ),
))
BARBARIAN_MINDLESS_RAGE_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.mindless_rage",
    "Mindless Rage",
    "You cannot be charmed or frightened while raging",
    "barbarian",
    60,
))
BARBARIAN_PERSISTENT_RAGE_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.persistent_rage",
    "Persistent Rage",
    "Rage ends early only if you fall unconscious or choose to end it",
    "barbarian",
    150,
))
BARBARIAN_PRIMAL_CHAMPION_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.primal_champion",
    "Primal Champion",
    "+4 Strength and Constitution, to a maximum of 24",
    "barbarian",
    200,
))
BARBARIAN_RECKLESS_ATTACK_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.reckless_attack",
    "Reckless Attack",
    "Attack recklessly for advantage at the cost of being easier to hit",
    "barbarian",
    21,
    granted_action_ids=("action.class.barbarian.reckless_attack",),
))
BARBARIAN_RELENTLESS_RAGE_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.relentless_rage",
    "Relentless Rage",
    "Make a Constitution save to drop to 1 HP instead of 0 while raging",
    "barbarian",
    110,
))
BARBARIAN_RETALIATION_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.retaliation",
    "Retaliation",
    "Make a reaction melee attack when hit by an adjacent creature",
    "barbarian",
    140,
    installed_reaction_ids=(
        "reaction.class_feature.barbarian.retaliation",
    ),
))
BARBARIAN_RAGE_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.rage",
    "Rage",
    "Enter a primal rage as a bonus action",
    "barbarian",
    10,
    granted_action_ids=(
        "action.class.barbarian.rage",
        "action.class.barbarian.end_rage",
    ),
))
BARBARIAN_FRENZY_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.barbarian.frenzy",
    "Frenzy",
    "Enter a frenzied rage for bonus-action attacks",
    "barbarian",
    30,
    granted_action_ids=("action.class.barbarian.frenzy",),
))

FIGHTER_ACTION_SURGE_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.action_surge",
    "Action Surge",
    "Take one additional action on your turn",
    "fighter",
    20,
    granted_action_ids=("action.class.fighter.action_surge",),
))
FIGHTER_EXTRA_ATTACK_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.extra_attack",
    "Extra Attack",
    "Make additional attacks when taking the Attack action",
    "fighter",
    50,
    granted_action_ids=("action.feature.extra_attack",),
))
FIGHTER_ARCHERY_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.fighting_style.archery",
    "Fighting Style: Archery",
    "+2 bonus to attack rolls with ranged weapons",
    "fighter",
    10,
))
FIGHTER_DEFENSE_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.fighting_style.defense",
    "Fighting Style: Defense",
    "+1 AC while wearing armor",
    "fighter",
    11,
))
FIGHTER_DUELING_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.fighting_style.dueling",
    "Fighting Style: Dueling",
    "+2 damage while wielding a melee weapon in one hand",
    "fighter",
    12,
))
FIGHTER_GREAT_WEAPON_FIGHTING_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.fighting_style.great_weapon_fighting",
    "Fighting Style: Great Weapon Fighting",
    "Reroll a 1 or 2 on a two-handed melee weapon damage die",
    "fighter",
    13,
))
FIGHTER_PROTECTION_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.fighting_style.protection",
    "Fighting Style: Protection",
    "Use your reaction to protect a nearby ally from an attack",
    "fighter",
    14,
    installed_reaction_ids=(
        "reaction.class_feature.fighter.protection",
    ),
))
FIGHTER_TWO_WEAPON_FIGHTING_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.fighting_style.two_weapon_fighting",
    "Fighting Style: Two-Weapon Fighting",
    "Add your ability modifier to off-hand attack damage",
    "fighter",
    15,
))
FIGHTER_IMPROVED_CRITICAL_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.improved_critical",
    "Improved Critical",
    "Weapon attacks score a critical hit on a roll of 19 or 20",
    "fighter",
    30,
))
FIGHTER_INDOMITABLE_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.indomitable",
    "Indomitable",
    "Reroll a failed saving throw and use the new roll",
    "fighter",
    90,
))
FIGHTER_SECOND_WIND_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.second_wind",
    "Second Wind",
    "Heal 1d10 plus fighter level as a bonus action once per short rest",
    "fighter",
    16,
    granted_action_ids=("action.class.fighter.second_wind",),
))
FIGHTER_SUPERIOR_CRITICAL_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.superior_critical",
    "Superior Critical",
    "Weapon attacks score a critical hit on a roll of 18, 19, or 20",
    "fighter",
    150,
))
FIGHTER_SURVIVOR_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.fighter.survivor",
    "Survivor",
    "Regain 5 plus Constitution modifier HP at turn start while at half HP",
    "fighter",
    180,
))

LUCKY_FEAT_DECLARATION = _declare(_PermanentFeatureSpec(
    "feat.lucky",
    "Lucky",
    (
        "Spend one of three luck points to reroll an attack roll, ability "
        "check, or saving throw"
    ),
    "feat",
    10,
    definition_kind=ContentDefinitionKind.FEAT,
))

SORCERER_DRACONIC_RESILIENCE_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.sorcerer.draconic_resilience",
    "Draconic Resilience",
    "AC equals 13 plus Dexterity while unarmored, with +1 HP per sorcerer level",
    "sorcerer",
    10,
))
SORCERER_SORCERY_POINTS_DECLARATION = _declare(_PermanentFeatureSpec(
    "class_feature.sorcerer.sorcery_points",
    "Sorcery Points",
    "Sorcery points power Metamagic and Font of Magic",
    "sorcerer",
    20,
    granted_action_ids=(
        "action.class.sorcerer.convert_sorcery_points_to_slot",
        "action.class.sorcerer.convert_slot_to_sorcery_points",
        "action.class.sorcerer.distant_spell",
        "action.class.sorcerer.quickened_spell",
        "action.class.sorcerer.twinned_spell",
    ),
))

PERMANENT_CLASS_FEATURE_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    BARBARIAN_BRUTAL_CRITICAL_DECLARATION,
    BARBARIAN_DANGER_SENSE_DECLARATION,
    BARBARIAN_FAST_MOVEMENT_DECLARATION,
    BARBARIAN_FERAL_INSTINCT_DECLARATION,
    BARBARIAN_FRENZY_DECLARATION,
    BARBARIAN_INDOMITABLE_MIGHT_DECLARATION,
    BARBARIAN_INTIMIDATING_PRESENCE_DECLARATION,
    BARBARIAN_MINDLESS_RAGE_DECLARATION,
    BARBARIAN_PERSISTENT_RAGE_DECLARATION,
    BARBARIAN_PRIMAL_CHAMPION_DECLARATION,
    BARBARIAN_RAGE_DECLARATION,
    BARBARIAN_RECKLESS_ATTACK_DECLARATION,
    BARBARIAN_RELENTLESS_RAGE_DECLARATION,
    BARBARIAN_RETALIATION_DECLARATION,
    FIGHTER_ACTION_SURGE_DECLARATION,
    FIGHTER_ARCHERY_DECLARATION,
    FIGHTER_DEFENSE_DECLARATION,
    FIGHTER_DUELING_DECLARATION,
    FIGHTER_EXTRA_ATTACK_DECLARATION,
    FIGHTER_GREAT_WEAPON_FIGHTING_DECLARATION,
    FIGHTER_IMPROVED_CRITICAL_DECLARATION,
    FIGHTER_INDOMITABLE_DECLARATION,
    FIGHTER_PROTECTION_DECLARATION,
    FIGHTER_SECOND_WIND_DECLARATION,
    FIGHTER_SUPERIOR_CRITICAL_DECLARATION,
    FIGHTER_SURVIVOR_DECLARATION,
    FIGHTER_TWO_WEAPON_FIGHTING_DECLARATION,
    LUCKY_FEAT_DECLARATION,
    SORCERER_DRACONIC_RESILIENCE_DECLARATION,
    SORCERER_SORCERY_POINTS_DECLARATION,
)
PERMANENT_CLASS_FEATURE_DECLARATIONS_BY_CONTENT_ID = {
    declaration.ref.content_id: declaration
    for declaration in PERMANENT_CLASS_FEATURE_DECLARATIONS
}
