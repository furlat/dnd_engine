"""Explicit authored identities for every concrete non-catalog action.

Spell catalog roots and the standard action set keep their co-located
declarations.  This module is the checked-in composition inventory for the
remaining concrete actions: identity is never derived from a Python path,
class name, or display label.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

import dnd.items.spell_items as spell_items
from dnd.items.scroll_learning import LearnSpellFromScroll
import dnd.actions as actions
import dnd.classes.barbarian as barbarian
import dnd.classes.fighter as fighter
import dnd.classes.cleric as cleric
import dnd.classes.divine_intervention as intervention
import dnd.items.divine_rewards as divine_rewards
import dnd.classes.paladin as paladin
import dnd.classes.wizard as wizard
import dnd.classes.rage as rage
import dnd.extensions.aegis_spark as aegis_spark
import dnd.extensions.field_focus as field_focus
import dnd.items.consumables as consumables
import dnd.items.container_traps as container_traps
import dnd.items.locks as locks
import dnd.items.searchables as searchables
import dnd.items.environment as environment
import dnd.items.environment_interactables as environment_interactables
import dnd.items.torches as torches
import dnd.monsters.skeleton_abilities as skeleton_abilities
import dnd.monsters.traits as monster_traits
import dnd.spells.abjuration as abjuration
import dnd.spells.conjuration as conjuration
import dnd.spatial.jaws as jaws
import dnd.spells.enchantment as enchantment
import dnd.spells.divination as divination
import dnd.spells.evocation as evocation
import dnd.items.created_items as created_items
import dnd.monsters.spell_summons as spell_summons
import dnd.monsters.spell_summon_actions as summon_actions
import dnd.items.spell_payloads as payloads
import dnd.spells.necromancy as necromancy
import dnd.spells.transmutation as transmutation
import dnd.summoning.actions as summoning
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
    srd_version: str = "5.1",
) -> ActionBehaviorIdentitySpec:
    return ActionBehaviorIdentitySpec(
        action_type=action_type,
        pack_id=f"content.srd_{srd_version.replace('.','_')}_cc",
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
    _srd(intervention.SunderHeretical,"action.class.cleric.divine_intervention.sunder_heretical","Divine Intervention: Sunder the Heretical","Once per character, a50ft enemy radiant burst.",root_owned=True),
    _srd(intervention.OpulentRevival,"action.class.cleric.divine_intervention.opulent_revival","Divine Intervention: Opulent Revival","Once per character, bounded allied recovery and half-HP companion revival.",root_owned=True),
    _srd(intervention.ArmThyServant,"action.class.cleric.divine_intervention.arm_thy_servant","Divine Intervention: Arm Thy Servant","Once per character, a permanent Devotee mace.",root_owned=True),
    _srd(intervention.GoldenGenerosity,"action.class.cleric.divine_intervention.golden_generosity","Divine Intervention: Golden Generosity","Once per character, a permanent native chest containing seven potions.",root_owned=True),
    _original(divine_rewards.HealingIncense,"action.item.devotees_mace.healing_incense","Healing Incense Aura","The equipped mace grants a ten-turn healing aura once per long rest."),
    _srd(paladin.DivineSense, "action.class.paladin.divine_sense", "Divine Sense", "Gain two-turn attack advantage against celestial, fiend and undead.", root_owned=True),
    _srd(paladin.LayOnHands, "action.class.paladin.lay_on_hands", "Lay on Hands", "Spend native healing charges to heal or cure a touched ally.", root_owned=True),
    _srd(paladin.TurnUnholy, "action.class.paladin.turn_unholy", "Turn the Unholy", "Turn visible fiends and undead using Paladin CHA.", root_owned=True),
    _srd(paladin.SacredWeapon, "action.class.paladin.sacred_weapon", "Sacred Weapon", "Enchant an exact held weapon for ten turns.", root_owned=True),
    _srd(paladin.CleansingTouch, "action.class.paladin.cleansing_touch", "Cleansing Touch", "End one exact eligible spell on a willing touched recipient.", root_owned=True),
    _srd(paladin.HolyNimbus, "action.class.paladin.holy_nimbus", "Holy Nimbus", "Shine for ten turns and damage nearby enemies at their turn start.", root_owned=True),
    _srd(wizard.ArcaneRecovery, "action.class.wizard.arcane_recovery", "Arcane Recovery", "Recover a spent shared slot outside combat using Wizard recovery points.", root_owned=True),
    _srd(cleric.TurnUndead, "action.class.cleric.turn_undead", "Turn Undead", "Turn visible undead within30 feet for three turns.", root_owned=True),
    _srd(cleric.PreserveLife, "action.class.cleric.preserve_life", "Preserve Life", "Heal nearby living allies with Channel Divinity.", root_owned=True),
    _srd(LearnSpellFromScroll, "action.wizard.learn_scroll", "Learn Spell", "Transcribe an eligible scroll into the Wizard book without gold cost."),
    *tuple(_srd(kind,identity,kind.model_fields["name"].default,"Approved summon creature technique using native actions.")
        for kind,identity in summon_actions.SUMMON_ACTION_IDENTITIES),
    _srd(payloads.ThrowSpellPayload,"action.spell.payload.throw","Throw Spell Sphere","Throw a retained sphere, retiring the item before its explosion."),
    _srd(payloads.TouchDelayedFireball,"action.spell.delayed_blast_fireball.touch","Touch Delayed Fireball","Touch the bead: DEX failure detonates; success permits pickup or a same-action throw."),
    _srd(spell_summons.FlamingSphereRam,"action.spell.flaming_sphere.ram","Flaming Sphere Ram","Bonus-action saved fire contact from the autonomous sphere."),
    _srd(spell_summons.SpiritualWeaponStrike,"action.spell.spiritual_weapon.strike","Spiritual Weapon Strike","Bonus-action force attack from the autonomous weapon."),
    _srd(created_items.EatGoodberry,"action.spell.goodberry.eat","Eat Goodberry","Consume one berry as a bonus action to heal 1d4."),
    _srd(transmutation.ExhaleDragonsBreath,"action.spell.dragons_breath.exhale","Exhale Dragon's Breath","Use the retained elemental cone.",srd_version="5.2"),
    _srd(necromancy.VampiricTouchStrike,"action.spell.vampiric_touch.strike","Vampiric Touch Strike","Repeat a melee necrotic attack and own-component healing."),
    _srd(evocation.MoveMoonbeam,"action.spell.moonbeam.move","Move Moonbeam","Relocate the retained beam within sixty feet."),
    _srd(abjuration.BreakEnchantment,"action.spell.dispel_evil_and_good.break_enchantment","Break Enchantment","Touch to cure an eligible control and end the ward."),
    _srd(evocation.ArcaneSwordStrike,"action.spell.arcane_sword.strike","Arcane Sword Strike","Move the sword anchor and make its melee spell attack."),
    _srd(evocation.MoveArcaneSword,"action.spell.arcane_sword.move","Move Arcane Sword","Relocate the sword without attacking."),
    _srd(evocation.MoveDancingLights,"action.spell.dancing_lights.move","Move Dancing Lights","Relocate the retained light within 60 feet."),
    _srd(divination.ReapplyHuntersMark,"action.spell.hunters_mark.reapply","Reapply Hunter's Mark","Choose a new quarry after the previous quarry is defeated."),
    _srd(enchantment.ReapplyHex,"action.spell.hex.reapply","Reapply Hex","Choose a new quarry after the previous quarry is defeated."),
    _original(actions.TraverseConnector, "action.traverse_connector", "Traverse Connector", "Traverse an admitted existing passage using its native costs and endpoints."),
    _original(summoning.DismissSummon, "action.summon.dismiss", "Dismiss Summon", "Spend one action to dismiss a temporary creature whose control is retained."),
    _srd(monster_traits.InnateInvisibility,"action.monster.innate_invisibility","Innate Invisibility","Concentrate on indefinite innate invisibility.",root_owned=True),
    _srd(monster_traits.ShieldBash, "action.monster.shield_bash", "Shield Bash", "Bash with a held shield; eligible targets save against falling Prone.", root_owned=True),
    _srd(monster_traits.WightLifeDrain,"action.monster.wight.life_drain","Life Drain","Intrinsic necrotic contact with saved maximum HP reduction.",root_owned=True),
    _original(spell_items.EmberQuiverActivation,"action.item.ember_quiver","Ember Quiver","Apply a ten-round fire coating to an equipped bow or crossbow."),
    _srd(evocation.DismissFireShield, "action.spell.fire_shield.dismiss", "Dismiss Fire Shield", "Dismiss the retained fire or cold shield."),
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
    _original(consumables._DrinkTrueSeeingPotionAction, "action.item.potion_true_seeing.drink", "Drink True Seeing Potion", "Drink the potion to gain truesight for ten rounds."),
    _original(consumables._DrinkHastePotionAction, "action.item.potion_haste.drink", "Drink Haste Potion", "Drink the potion to gain its haste effect."),
    _original(consumables._DrinkHealingPotionAction, "action.item.potion_healing.drink", "Drink Healing Potion", "Drink the potion to recover hit points."),
    _original(environment.CloseDirectionalDoorAction, "action.environment.directional_door.close", "Close Directional Door", "Close the directional door from an adjacent tile."),
    _original(environment.OpenDirectionalDoorAction, "action.environment.directional_door.open", "Open Directional Door", "Open the directional door from an adjacent tile."),
    _original(environment_interactables.ActivateDeviceAction, "action.environment.arcane_device.activate", "Activate Device", "Activate the selected arcane device."),
    _original(environment_interactables.CloseDoorAction, "action.environment.door.close", "Close Door", "Close the adjacent door."),
    _original(environment_interactables.CookAction, "action.environment.campfire.cook", "Cook", "Use the campfire to prepare a restorative meal."),
    _original(environment_interactables.OpenChestAction, "action.environment.storage_chest.open", "Open Chest", "Open the adjacent chest without transferring its contents."),
    _original(environment_interactables.CloseChestAction, "action.environment.storage_chest.close", "Close Chest", "Close the adjacent chest independently of its contents."),
    _original(environment_interactables.ToggleLeverAction, "action.environment.control_lever.toggle", "Toggle Lever", "Move a reusable lever and request its linked light or door state."),
    _original(environment_interactables.LootAllAction, "action.environment.storage_chest.loot_all", "Loot All", "Transfer every accessible item from the container."),
    _original(environment_interactables.LootItemAction, "action.environment.storage_chest.loot", "Loot", "Transfer one selected accessible item from the container."),
    _original(environment_interactables.OpenDoorAction, "action.environment.door.open", "Open Door", "Open the adjacent door."),
    _original(environment_interactables.PullLeverAction, "action.environment.trap_lever.pull", "Pull Lever", "Set the linked trap's mechanical state through its placed lever."),
    _original(environment_interactables.RestAction, "action.environment.campfire.rest", "Rest", "Rest beside the campfire."),
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
        "Multiattack",
        (
            "Make a creature's stat-block sequence of weapon attacks for one "
            "action; each creature's recipe supplies its steps. The engine "
            "resolves the whole sequence against one selected target, although "
            "the general attack rules let each attack choose its own unless a "
            "stat block says otherwise."
        ),
        root_owned=True,
        icon_key="ui.filter-attacks",
    ),
    _srd(monster_traits.NaturalAttack, "action.monster.natural_attack", "Natural Attack", "Resolve a data-authored natural weapon attack.", root_owned=True),

    # Helper actions granted by persistent spell effects or active casts.
    _srd(abjuration.FreedomOfMovementEscape, "action.spell.freedom_of_movement.escape", "Freedom of Movement Escape", "Spend movement to escape an eligible nonmagical restraint."),
    _srd(conjuration.CallLightningStrike, "action.spell.call_lightning.strike", "Call Lightning Strike", "Call another bolt from an active Call Lightning spell."),
    _srd(conjuration.EatFromFeast, "action.environment.heroes_feast.eat", "Eat from Feast", "Consume one serving from a Heroes' Feast."),
    _original(jaws.ForceJawOpen, "action.environment.escape_jaw.athletics", "Force jaws open", "Use an action and Athletics to escape one jaw."),
    _original(container_traps.DisarmTrap, "action.environment.trap.disarm", "Disarm Trap", "Use a Trap Disarm Toolkit and Sleight of Hand on a trap you have found."),
    _original(locks.Unlock, "action.environment.lock.unlock", "Unlock", "Unlock with the right key, or lift a bar from its side."),
    _original(locks.LockShut, "action.environment.lock.lock", "Lock", "Lock with the right key, or set a bar from its side."),
    _original(locks.PickLock, "action.environment.lock.pick", "Pick Lock", "Pick a lock with Thieves' Tools and Sleight of Hand."),
    _original(locks.ForceLock, "action.environment.lock.force", "Force Lock", "Force a lock or bar open with Athletics."),
    _original(searchables.SearchBody, "action.environment.search", "Search", "Search one desk, cabinet, board or body for anything tucked away."),
    _original(jaws.SlipFreeOfJaw, "action.environment.escape_jaw.acrobatics", "Slip free of jaws", "Use an action and Acrobatics to escape one jaw."),
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
    _srd(transmutation.TelekinesisMove, "action.spell.telekinesis.move", "Telekinesis: Move", "Spend an action to move one creature to a supported destination."),
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
