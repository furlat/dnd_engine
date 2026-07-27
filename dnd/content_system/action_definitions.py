"""Explicit authored identities for every concrete non-catalog action.

Spell catalog roots and the standard action set keep their co-located
declarations.  This module is the checked-in composition inventory for the
remaining concrete actions: identity is never derived from a Python path,
class name, or display label.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

import dnd.actions as actions
import dnd.classes.barbarian as barbarian
import dnd.classes.fighter as fighter
import dnd.classes.rage as rage
import dnd.classes.sorcerer as sorcerer
import dnd.extensions.aegis_spark as aegis_spark
import dnd.extensions.field_focus as field_focus
import dnd.items.consumables as consumables
import dnd.items.environment as environment
import dnd.items.test_items as test_items
import dnd.items.test_reactions as test_reactions
import dnd.items.torches as torches
import dnd.monsters.skeleton_abilities as skeleton_abilities
import dnd.monsters.traits as monster_traits
import dnd.spells.abjuration as abjuration
import dnd.spells.conjuration as conjuration
import dnd.spells.enchantment as enchantment
import dnd.spells.evocation as evocation
import dnd.spells.necromancy as necromancy
import dnd.spells.transmutation as transmutation
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


SRD_5_1_PACK_ID = "content.srd_5_1_cc"
NEURODRAGON_PACK_ID = "content.neurodragon"


@dataclass(frozen=True, slots=True)
class ActionBehaviorIdentitySpec:
    """One exact concrete action-to-content association."""

    action_type: type[BaseAction]
    pack_id: str
    content_id: str
    display_name: str
    description: str
    definition_kind: ContentDefinitionKind = ContentDefinitionKind.ACTION
    runtime_behavior_kind: RuntimeBehaviorKind = RuntimeBehaviorKind.ACTION
    visibility: ContentVisibility = ContentVisibility.PUBLIC
    granted_action_types: tuple[type[BaseAction], ...] = ()
    root_owned: bool = False
    icon_key: str | None = None


def _srd(
    action_type: type[BaseAction],
    content_id: str,
    display_name: str,
    description: str,
    *,
    visibility: ContentVisibility = ContentVisibility.PUBLIC,
    granted_action_types: tuple[type[BaseAction], ...] = (),
    root_owned: bool = False,
    icon_key: str | None = None,
) -> ActionBehaviorIdentitySpec:
    return ActionBehaviorIdentitySpec(
        action_type=action_type,
        pack_id=SRD_5_1_PACK_ID,
        content_id=content_id,
        display_name=display_name,
        description=description,
        visibility=visibility,
        granted_action_types=granted_action_types,
        root_owned=root_owned,
        icon_key=icon_key,
    )


def _original(
    action_type: type[BaseAction],
    content_id: str,
    display_name: str,
    description: str,
    *,
    visibility: ContentVisibility = ContentVisibility.PUBLIC,
    definition_kind: ContentDefinitionKind = ContentDefinitionKind.ACTION,
    runtime_behavior_kind: RuntimeBehaviorKind = RuntimeBehaviorKind.ACTION,
    root_owned: bool = False,
    icon_key: str | None = None,
) -> ActionBehaviorIdentitySpec:
    return ActionBehaviorIdentitySpec(
        action_type=action_type,
        pack_id=NEURODRAGON_PACK_ID,
        content_id=content_id,
        display_name=display_name,
        description=description,
        definition_kind=definition_kind,
        runtime_behavior_kind=runtime_behavior_kind,
        visibility=visibility,
        root_owned=root_owned,
        icon_key=icon_key,
    )


ACTION_BEHAVIOR_IDENTITY_SPECS: tuple[ActionBehaviorIdentitySpec, ...] = (
    # SRD-compatible standard and class actions not in the core starter set.
    _srd(actions.Drop, "action.core.drop", "Drop", "Drop one carried item onto the current tile."),
    _srd(actions.DropProne, "action.core.drop_prone", "Drop Prone", "Voluntarily become prone without spending movement."),
    _srd(actions.StandUp, "action.core.stand_up", "Stand Up", "Spend movement to stand from prone."),
    _srd(barbarian.ExtendIntimidatingPresence, "action.class.barbarian.extend_intimidating_presence", "Extend Intimidating Presence", "Extend an existing Intimidating Presence effect.", root_owned=True),
    _srd(barbarian.IntimidatingPresence, "action.class.barbarian.intimidating_presence", "Intimidating Presence", "Attempt to frighten a nearby creature.", root_owned=True),
    _srd(barbarian.RecklessAttack, "action.class.barbarian.reckless_attack", "Reckless Attack", "Gain advantage on Strength melee attacks while exposing yourself to attacks.", root_owned=True),
    _srd(fighter.ActionSurge, "action.class.fighter.action_surge", "Action Surge", "Spend an Action Surge use to take one additional action.", root_owned=True),
    _srd(fighter.ExtraAttack, "action.feature.extra_attack", "Extra Attack", "Spend one granted extra-attack use with the selected weapon.", root_owned=True),
    _srd(fighter.SecondWind, "action.class.fighter.second_wind", "Second Wind", "Spend a bonus action to recover hit points.", root_owned=True),
    _srd(rage.EndRage, "action.class.barbarian.end_rage", "End Rage", "Voluntarily end the active rage.", root_owned=True),
    _srd(rage.FrenziedStrike, "action.class.barbarian.frenzied_strike", "Frenzied Strike", "Make the bonus-action melee attack granted by Frenzy.", root_owned=True),
    _srd(rage.Frenzy, "action.class.barbarian.frenzy", "Frenzy", "Enter a frenzied rage.", root_owned=True),
    _srd(rage.Rage, "action.class.barbarian.rage", "Rage", "Spend a rage use to enter a primal rage.", root_owned=True),
    _srd(
        sorcerer.ConvertSPToSlot,
        "action.class.sorcerer.convert_sorcery_points_to_slot",
        "Convert Sorcery Points to Slot",
        "Spend sorcery points to create a spell slot.",
        root_owned=True,
        icon_key="action.convert-sorcery-points-to-slot",
    ),
    _srd(
        sorcerer.ConvertSlotToSP,
        "action.class.sorcerer.convert_slot_to_sorcery_points",
        "Convert Slot to Sorcery Points",
        "Spend a spell slot to recover sorcery points.",
        root_owned=True,
        icon_key="action.convert-slot-to-sorcery-points",
    ),
    _srd(sorcerer.DistantSpell, "action.class.sorcerer.distant_spell", "Distant Spell", "Empower the next eligible spell with increased range.", root_owned=True),
    _srd(
        sorcerer.ElementalAffinityResistanceAction,
        "action.class.sorcerer.elemental_affinity.resistance",
        "Elemental Affinity Resistance",
        "Spend one sorcery point for 1 hour of ancestry resistance.",
        root_owned=True,
        icon_key="condition.dnd-classes-sorcerer-elementalaffinity",
    ),
    _srd(
        sorcerer.Fly,
        "action.class.sorcerer.dragon_wings.fly",
        "Fly",
        "Move using manifested dragon wings.",
        root_owned=True,
        icon_key="action.move",
    ),
    _srd(
        sorcerer.DragonWings,
        "action.class.sorcerer.dragon_wings.toggle",
        "Dragon Wings",
        "Manifest or dismiss dragon wings as a bonus action.",
        granted_action_types=(sorcerer.Fly,),
        root_owned=True,
        icon_key="spell.haste",
    ),
    _srd(
        sorcerer.DraconicPresence,
        "action.class.sorcerer.draconic_presence",
        "Draconic Presence",
        "Concentrate on a 60-foot aura of awe or fear for up to 1 minute.",
        root_owned=True,
        icon_key="spell.fear",
    ),
    _srd(
        sorcerer.QuickenedSpell,
        "action.class.sorcerer.quickened_spell",
        "Quickened Spell",
        "Empower the next eligible spell to use a bonus action.",
        root_owned=True,
        icon_key="action.quickened-spell",
    ),
    _srd(
        sorcerer.TwinnedSpell,
        "action.class.sorcerer.twinned_spell",
        "Twinned Spell",
        "Empower the next eligible spell with a second target.",
        root_owned=True,
        icon_key="action.twinned-spell",
    ),

    # Original extension, item, environment, and maintained fixture actions.
    _original(
        aegis_spark.AegisSpark,
        "spell.aegis_spark",
        "Aegis Spark",
        "Project a short-lived defensive ward onto self or an ally.",
        definition_kind=ContentDefinitionKind.SPELL,
        runtime_behavior_kind=RuntimeBehaviorKind.SPELL,
    ),
    _original(field_focus.DeployFieldFocus, "action.item.field_kit.deploy", "Deploy Field Focus", "Deploy the carried field focus at a selected position."),
    _original(consumables._ApplyWeaponCoatAction, "action.item.weapon_coat.apply", "Coat Main Hand", "Apply the carried weapon coating to the active main-hand weapon."),
    _original(consumables._DrinkGreaterInvisibilityPotionAction, "action.item.potion_greater_invisibility.drink", "Drink Greater Invisibility Potion", "Drink the potion to gain its greater-invisibility effect."),
    _original(consumables._DrinkHastePotionAction, "action.item.potion_haste.drink", "Drink Haste Potion", "Drink the potion to gain its haste effect."),
    _original(consumables._DrinkHealingPotionAction, "action.item.potion_healing.drink", "Drink Healing Potion", "Drink the potion to recover hit points."),
    _original(environment.CloseDirectionalDoorAction, "action.environment.directional_door.close", "Close Directional Door", "Close the directional door from an adjacent tile."),
    _original(environment.OpenDirectionalDoorAction, "action.environment.directional_door.open", "Open Directional Door", "Open the directional door from an adjacent tile."),
    _original(test_items.ActivateDeviceAction, "action.environment.arcane_device.activate", "Activate Device", "Activate the selected arcane device."),
    _original(test_items.CloseDoorAction, "action.environment.door.close", "Close Door", "Close the adjacent door."),
    _original(test_items.CookAction, "action.environment.campfire.cook", "Cook", "Use the campfire to prepare a restorative meal."),
    _original(
        test_items.InteractDoorAction,
        "action.fixture.interact_door",
        "Interact Door",
        "Maintained developer interaction used to exercise generic door actions.",
        visibility=ContentVisibility.DEVELOPER,
    ),
    _original(test_items.LootAllAction, "action.environment.storage_chest.loot_all", "Loot All", "Transfer every accessible item from the container."),
    _original(test_items.OpenDoorAction, "action.environment.door.open", "Open Door", "Open the adjacent door."),
    _original(test_items.PullLeverAction, "action.environment.trap_lever.pull", "Pull Lever", "Pull the linked lever to alter its encounter mechanism."),
    _original(test_items.RestAction, "action.environment.campfire.rest", "Rest", "Rest beside the campfire."),
    _original(
        test_reactions.PrepareIntercept,
        "action.fixture.prepare_intercept",
        "Prepare Intercept",
        "Maintained developer action that prepares a movement interception.",
        visibility=ContentVisibility.DEVELOPER,
    ),
    _original(torches.ExtinguishTorchAction, "action.item.torch.extinguish", "Extinguish Torch", "Extinguish a carried torch."),
    _original(torches.ExtinguishWallTorchAction, "action.environment.wall_torch.extinguish", "Extinguish Wall Torch", "Extinguish an adjacent wall torch."),
    _original(torches.IgniteTorchAction, "action.item.torch.ignite", "Ignite Torch", "Ignite a carried torch."),
    _original(torches.IgniteWallTorchAction, "action.environment.wall_torch.ignite", "Ignite Wall Torch", "Ignite an adjacent wall torch."),
    _original(skeleton_abilities.MarkTargetAction, "action.creature.skeleton_archer.mark_target", "Mark Target", "Mark a visible enemy for allied attacks.", root_owned=True),

    # Reusable SRD monster actions. Natural Attack and Multiattack are genuine
    # parameterized rules definitions; creature data supplies their variants.
    _srd(monster_traits.AggressiveMoveAction, "action.trait.aggressive", "Aggressive", "Move toward a visible hostile as a bonus action.", root_owned=True),
    _srd(monster_traits.DivineEminenceAction, "action.trait.divine_eminence", "Divine Eminence", "Spend a spell slot to empower melee attacks with radiant damage.", root_owned=True),
    _srd(monster_traits.LeadershipAction, "action.trait.leadership", "Leadership", "Inspire nearby allies with a temporary attack and saving-throw bonus.", root_owned=True),
    _srd(
        monster_traits.MultiattackAction,
        "action.monster.multiattack",
        "Multiattack Runtime",
        (
            "Internal reusable engine behavior specialized by exact public "
            "stat-block action configurations."
        ),
        visibility=ContentVisibility.INTERNAL,
        root_owned=True,
    ),
    _srd(monster_traits.NaturalAttack, "action.monster.natural_attack", "Natural Attack", "Resolve a data-authored natural weapon attack.", root_owned=True),

    # Helper actions granted by persistent spell effects or active casts.
    _srd(abjuration.FreedomOfMovementEscape, "action.spell.freedom_of_movement.escape", "Freedom of Movement Escape", "Spend movement to escape an eligible nonmagical restraint."),
    _srd(conjuration.CallLightningStrike, "action.spell.call_lightning.strike", "Call Lightning Strike", "Call another bolt from an active Call Lightning spell."),
    _srd(conjuration.EatFromFeast, "action.environment.heroes_feast.eat", "Eat from Feast", "Consume one serving from a Heroes' Feast."),
    _srd(conjuration.EscapeWebAction, "action.spell.web.escape", "Escape Web", "Attempt to escape the restraint imposed by Web."),
    _original(
        enchantment.TestBless,
        "spell.fixture.test_bless",
        "Test Bless",
        "Maintained developer spell used to exercise ordered multi-target application.",
        visibility=ContentVisibility.DEVELOPER,
        definition_kind=ContentDefinitionKind.SPELL,
        runtime_behavior_kind=RuntimeBehaviorKind.SPELL,
    ),
    _srd(evocation.SunbeamStrike, "action.spell.sunbeam.strike", "Sunbeam Strike", "Fire another beam from an active Sunbeam spell."),
    _srd(necromancy.EyebiteStrike, "action.spell.eyebite.strike", "Eyebite Strike", "Apply another selected gaze effect from an active Eyebite spell."),
    _srd(transmutation.BonusDash, "action.spell.expeditious_retreat.dash", "Dash (Bonus)", "Take the Dash action as a bonus action."),
    _srd(transmutation.TelekinesisMove, "action.spell.telekinesis.move", "Telekinesis: Move", "Move the creature currently held by Telekinesis."),
    _srd(transmutation.TelekinesisRestrain, "action.spell.telekinesis.restrain", "Telekinesis: Restrain", "Restrain the creature currently held by Telekinesis."),
    _srd(
        transmutation.TelekinesisGrab,
        "action.spell.telekinesis.grab",
        "Telekinesis",
        "Attempt to grab a creature with an active Telekinesis spell.",
        granted_action_types=(
            transmutation.TelekinesisMove,
            transmutation.TelekinesisRestrain,
        ),
    ),
)


def _provenance(spec: ActionBehaviorIdentitySpec) -> ContentProvenance:
    if spec.pack_id == SRD_5_1_PACK_ID:
        return ContentProvenance(
            primary_source_id="wotc.srd_5_1_cc",
            source_anchor=(
                "SRD 5.1 (CC-BY-4.0), existing playable behavior: "
                f"{spec.display_name}"
            ),
            relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.UNREVIEWED,
            notes=(
                "Exact identity preserves an existing playable action; "
                "source-parity review remains tracked separately."
            ),
        )
    if spec.pack_id == NEURODRAGON_PACK_ID:
        return ContentProvenance(
            primary_source_id="neurodragon.original_b2b3930",
            source_anchor=(
                "Neurodragon original content baseline: "
                f"{spec.display_name}"
            ),
            relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
            fidelity=ContentFidelity.COMPLETE,
            review_status=ContentReviewStatus.REVIEWED,
            notes="Existing runtime action preserved as authored content.",
        )
    raise ValueError(f"Unsupported action behavior pack {spec.pack_id}")


def _declare_action_behavior(
    spec: ActionBehaviorIdentitySpec,
    sort_order: int,
) -> ContentDeclaration:
    try:
        declaration = get_content_declaration(spec.action_type)
    except ValueError:
        declaration = None
    else:
        if declaration.descriptor.display_name != spec.display_name:
            raise ValueError(
                f"Co-located declaration for {spec.action_type!r} has "
                "unexpected display identity",
            )

    if declaration is None:
        dependencies = tuple(
            ContentDependency(
                relation=ContentDependencyRelation.GRANTS_ACTION,
                target_ref=get_content_declaration(action_type).ref,
                phase=ContentDependencyPhase.RUNTIME_REFERENCE,
                notes="Registered while this action is the active provider.",
            )
            for action_type in spec.granted_action_types
        )
        decorator = behavior_identity(
            definition_kind=spec.definition_kind,
            runtime_behavior_kind=spec.runtime_behavior_kind,
            pack_id=spec.pack_id,
            content_id=spec.content_id,
            version=1,
            descriptor=ContentDescriptorSpec(
                display_name=spec.display_name,
                description=spec.description,
                tags=(
                    "action",
                    spec.runtime_behavior_kind.value,
                    *(("root_owned",) if spec.root_owned else ()),
                ),
                visibility=spec.visibility,
                presentation=ContentPresentation(
                    icon_key=spec.icon_key or spec.content_id,
                    visual_variant_key=spec.content_id,
                    vfx_profile=spec.content_id,
                    ui_group=f"actions.{spec.runtime_behavior_kind.value}",
                ),
                ordering=ContentOrdering(
                    sort_group=f"actions.{spec.runtime_behavior_kind.value}",
                    sort_order=sort_order,
                ),
            ),
            provenance=_provenance(spec),
            dependencies=dependencies,
        )
        decorator(spec.action_type)
        declaration = get_content_declaration(spec.action_type)
    if (
        declaration.ref.pack_id != spec.pack_id
        or declaration.ref.definition_kind is not spec.definition_kind
        or declaration.ref.content_id != spec.content_id
        or declaration.runtime_behavior_kind is not spec.runtime_behavior_kind
        or declaration.descriptor.visibility is not spec.visibility
        or declaration.descriptor.presentation.icon_key
        != resolve_content_icon_key(
            declaration.ref,
            spec.icon_key or spec.content_id,
        )[0]
    ):
        raise ValueError(
            "Action behavior declaration disagrees with its explicit spec "
            f"for {spec.action_type!r}",
        )
    return declaration


ACTION_BEHAVIOR_DECLARATIONS: tuple[ContentDeclaration, ...] = tuple(
    _declare_action_behavior(spec, sort_order)
    for sort_order, spec in enumerate(
        ACTION_BEHAVIOR_IDENTITY_SPECS,
        start=1,
    )
)
ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS = MappingProxyType({
    spec.action_type: declaration
    for spec, declaration in zip(
        ACTION_BEHAVIOR_IDENTITY_SPECS,
        ACTION_BEHAVIOR_DECLARATIONS,
        strict=True,
    )
})

if (
    len(ACTION_BEHAVIOR_DECLARATIONS)
    != len(ACTION_BEHAVIOR_IDENTITY_SPECS)
    or len(ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS)
    != len(ACTION_BEHAVIOR_DECLARATIONS)
    or len({
        declaration.ref.identity_key
        for declaration in ACTION_BEHAVIOR_DECLARATIONS
    }) != len(ACTION_BEHAVIOR_DECLARATIONS)
):
    raise ValueError("Action behavior identity inventory is not one-to-one")


__all__ = [
    "ACTION_BEHAVIOR_DECLARATIONS",
    "ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS",
    "ACTION_BEHAVIOR_IDENTITY_SPECS",
    "ActionBehaviorIdentitySpec",
]
