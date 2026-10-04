"""Ordinary Goblin kits composed from existing items, actions and creature traits."""

from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS
from dnd.actions_functional import register_spell
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.classes.fighter import create_protection_handler
from dnd.content_system.action_definitions import ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.condition_definitions import CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.creature_possessions import (
    CreaturePossessionDisposition, CreaturePossessionGrant, apply_creature_possessions,
)
from dnd.core.content.dependencies import ContentDependency, ContentDependencyRelation
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentPresentation, ContentVisibility
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import (
    ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.content.registration import ContentDeclaration, creature_factory, get_content_declaration
from dnd.core.creature_types import Size
from dnd.core.equipment_types import BodyPart, EquipmentSlot, WeaponSlot
from dnd.entity import Entity
from dnd.monsters.bestiary import register_goblin_nimble_escape
from dnd.monsters.multiattack_definitions import GOBLIN_MULTIATTACK_CONFIGURATIONS_BY_ID, MultiattackConfigurationDefinition
from dnd.monsters.srd_roster import HitDieValue, create_creature_entity
from dnd.monsters.traits import (
    BruteFeature, MultiattackAction, SurpriseAttackFeature,
    register_brute, register_multiattack, register_surprise_attack,
)
from dnd.spells.abjuration import (
    MageArmor, register_shield_reaction, register_counterspell_reaction,
    SHIELD_REACTION_DECLARATION, COUNTERSPELL_REACTION_DECLARATION,
)
from dnd.spells.conjuration import Web
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS_BY_CLASS
from dnd.spells.evocation import FireBolt, MagicMissile, Fireball, IceStorm, ConeOfCold
from dnd.spells.illusion import GreaterInvisibility


class GoblinRosterParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class GoblinProfile:
    abilities: tuple[int, int, int, int, int, int]
    hit_points: int
    hit_die: HitDieValue
    hit_dice: int
    proficiency: int = 2
    size: Size = Size.SMALL
    speed: int = 30
    caster: bool = False
    brute: bool = False
    nimble: bool = True


SKIRMISHER = GoblinProfile((8,14,10,10,8,8), 7,6,2)
CASTER = GoblinProfile((9,14,11,17,12,11), 40,8,9, proficiency=3, caster=True, nimble=False)
BRUISER = GoblinProfile((15,14,13,8,11,9), 27,8,5, size=Size.MEDIUM, brute=True, nimble=False)
RIDER = GoblinProfile((8,14,10,10,8,8), 7,6,2, size=Size.MEDIUM, speed=40, nimble=False)
CASTER_SPELLS = (FireBolt, MagicMissile, MageArmor, Web, Fireball, GreaterInvisibility, IceStorm, ConeOfCold)


@dataclass(frozen=True)
class GoblinDefinition:
    key: str
    name: str
    profile: GoblinProfile
    possessions: tuple[CreaturePossessionGrant, ...]
    protection: bool = False
    multiattack: str | None = None


def _equipped(item_id: str, slot: EquipmentSlot) -> CreaturePossessionGrant:
    return CreaturePossessionGrant(item_id=item_id,
        disposition=CreaturePossessionDisposition.EQUIPPED, equipment_slot=slot)


GOBLIN_DEFINITIONS = (
    GoblinDefinition("goblin", "Ashhook", SKIRMISHER, (
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("weapon.handaxe", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.common_clothes_21ae119f8607", BodyPart.BODY),
    )),
    GoblinDefinition("goblin_wispbinder", "Wispbinder", CASTER, (
        _equipped("apparel.roster.robes_ac36c74adec6", BodyPart.BODY),
        _equipped("apparel.leather_shoes.brown", BodyPart.FEET),
    )),
    GoblinDefinition("goblin_reedshot", "Reedshot", SKIRMISHER, (
        _equipped("gear.roster.quiver_6c39094102d0", BodyPart.BACKPACK),
        _equipped("apparel.roster.cloth_hood_44e704af2cf6", BodyPart.HEAD),
        _equipped("apparel.leather_boots.brown", BodyPart.FEET),
        _equipped("weapon.roster.shortbow_a0000007", WeaponSlot.RANGED_MAIN),
        _equipped("apparel.roster.common_clothes_21ae119f8607", BodyPart.BODY),
    )),
    GoblinDefinition("goblin_buckler_rat", "Buckler Rat", SKIRMISHER, (
        _equipped("shield.roster.wooden_90000006", WeaponSlot.MELEE_OFF),
        _equipped("weapon.scimitar", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("apparel.roster.iron_helmet_6b64ee00bd15", BodyPart.HEAD),
        _equipped("armor.roster.armor_scraps_8ab959786f2a", BodyPart.BODY),
    )),
    GoblinDefinition("goblin_longpoint", "Longpoint", SKIRMISHER, (
        _equipped("apparel.leather_boots.brown", BodyPart.FEET),
        _equipped("weapon.spear", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.common_clothes_16dea1f65105", BodyPart.BODY),
        _equipped("apparel.roster.cloth_hood_828192008429", BodyPart.HEAD),
    )),
    GoblinDefinition("goblin_ironhide", "Ironhide", SKIRMISHER, (
        _equipped("shield.roster.shield_a000000a", WeaponSlot.MELEE_OFF),
        _equipped("armor.roster.armor_scraps_f8d0f71d39aa", BodyPart.BODY),
        _equipped("weapon.shortsword", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.iron_helmet_6b64ee00bd15", BodyPart.HEAD),
        _equipped("apparel.roster.gauntlets_g0000009", BodyPart.HANDS),
        _equipped("apparel.roster.armored_boots_b000000d", BodyPart.FEET),
    ), protection=True),
    GoblinDefinition("goblin_briarling", "Briarling", SKIRMISHER, (
        _equipped("apparel.leather_boots.brown", BodyPart.FEET),
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("armor.roster.armor_scraps_f8d0f71d39aa", BodyPart.BODY),
        _equipped("weapon.dagger", WeaponSlot.MELEE_OFF),
        _equipped("weapon.shortsword", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.cloth_hood_7d8178761a23", BodyPart.HEAD),
    ), multiattack="goblin_briarling"),
    GoblinDefinition("goblin_redcap", "Redcap", CASTER, (
        _equipped("apparel.leather_shoes.brown", BodyPart.FEET),
        _equipped("apparel.roster.robes_51a81ec5104c", BodyPart.BODY),
        _equipped("weapon.roster.quarterstaff_a0000005", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.cloth_hood_828192008429", BodyPart.HEAD),
    )),
    GoblinDefinition("goblin_quicktail", "Quicktail", SKIRMISHER, (
        _equipped("weapon.roster.shortbow_20000002", WeaponSlot.RANGED_MAIN),
        _equipped("gear.roster.quiver_6c39094102d0", BodyPart.BACKPACK),
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("armor.roster.armor_scraps_f8d0f71d39aa", BodyPart.BODY),
        _equipped("apparel.roster.cloth_hood_7d8178761a23", BodyPart.HEAD),
        _equipped("apparel.leather_boots.dark", BodyPart.FEET),
    )),
    GoblinDefinition("goblin_spearline", "Spearline", SKIRMISHER, (
        _equipped("weapon.trident", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("armor.roster.armor_scraps_5b5b6ba7ea35", BodyPart.BODY),
        _equipped("apparel.roster.cloth_hood_7d8178761a23", BodyPart.HEAD),
        _equipped("apparel.leather_boots.dark", BodyPart.FEET),
    )),
    GoblinDefinition("goblin_packtrail", "Packtrail", RIDER, (
        CreaturePossessionGrant(item_id="gear.saddle", disposition=CreaturePossessionDisposition.INVENTORY),
        _equipped("shield.roster.wooden_90000006", WeaponSlot.MELEE_OFF),
        _equipped("weapon.handaxe", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.common_clothes_16dea1f65105", BodyPart.BODY),
    ), protection=True),
    GoblinDefinition("goblin_ashhide", "Ashhide", RIDER, (
        CreaturePossessionGrant(item_id="gear.saddle", disposition=CreaturePossessionDisposition.INVENTORY),
        _equipped("shield.roster.shield_a000000a", WeaponSlot.MELEE_OFF),
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("armor.roster.armor_scraps_f8d0f71d39aa", BodyPart.BODY),
        _equipped("weapon.handaxe", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.cloth_hood_7d8178761a23", BodyPart.HEAD),
    ), protection=True),
    GoblinDefinition("goblin_thornrunner", "Thornrunner", SKIRMISHER, (
        _equipped("apparel.roster.cloth_hood_44e704af2cf6", BodyPart.HEAD),
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("weapon.club", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.common_clothes_3b03cd4905fa", BodyPart.BODY),
    )),
    GoblinDefinition("goblin_buckler_hex", "Buckler Hex", SKIRMISHER, (
        _equipped("shield.roster.wooden_90000006", WeaponSlot.MELEE_OFF),
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("weapon.morningstar", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.iron_helmet_6b64ee00bd15", BodyPart.HEAD),
        _equipped("apparel.roster.armored_boots_b000000d", BodyPart.FEET),
        _equipped("armor.roster.armor_scraps_8ab959786f2a", BodyPart.BODY),
    ), protection=True),
    GoblinDefinition("goblin_gloomplate", "Gloomplate", BRUISER, (
        _equipped("apparel.roster.iron_helmet_h000000a", BodyPart.HEAD),
        _equipped("weapon.handaxe", WeaponSlot.MELEE_OFF),
        _equipped("apparel.leather_boots.brown", BodyPart.FEET),
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("weapon.handaxe", WeaponSlot.MELEE_MAIN),
        _equipped("armor.roster.armor_scraps_d6b6c79a6d59", BodyPart.BODY),
    ), multiattack="goblin_gloomplate"),
    GoblinDefinition("goblin_mossbreaker", "Mossbreaker", SKIRMISHER, (
        _equipped("shield.roster.wooden_90000006", WeaponSlot.MELEE_OFF),
        _equipped("apparel.leather_boots.brown", BodyPart.FEET),
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("weapon.shortsword", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.common_clothes_21ae119f8607", BodyPart.BODY),
    )),
    GoblinDefinition("goblin_gutterknife", "Gutterknife", SKIRMISHER, (
        _equipped("apparel.roster.cloth_hood_44e704af2cf6", BodyPart.HEAD),
        _equipped("apparel.leather_boots.brown", BodyPart.FEET),
        _equipped("weapon.scimitar", WeaponSlot.MELEE_MAIN),
        _equipped("apparel.roster.bracers_g0000003", BodyPart.HANDS),
        _equipped("weapon.pistol", WeaponSlot.RANGED_MAIN),
        _equipped("apparel.roster.common_clothes_21ae119f8607", BodyPart.BODY),
    )),
)


def build_goblin(context: CreatureBuildContext, definition: GoblinDefinition, *, weight: int = 40) -> Entity:
    profile = definition.profile
    skills = ({"arcana": True, "history": True} if profile.caster else
              {"stealth": True, "survival": True} if profile.brute else {"stealth": True})
    entity = create_creature_entity(context=context, description=f"{definition.name}, a goblinoid combatant.",
        abilities=profile.abilities, hit_die_value=profile.hit_die, hit_die_count=profile.hit_dice,
        hit_points=profile.hit_points, proficiency_bonus=profile.proficiency, size=profile.size,
        weight=weight, movement=profile.speed, darkvision=True, skills=skills,
        spellcasting_ability="intelligence" if profile.caster else None,
        spell_slots={1:4, 2:3, 3:3, 4:3, 5:1} if profile.caster else None)
    entity.appearance.visual_scale = 1.0
    install_body_response(entity, BLOOD_BODY_RESPONSE)
    if not profile.caster and not profile.brute:
        entity.skill_set.stealth.set_expertise(True)
    apply_creature_possessions(entity, definition.possessions, possession_mode=context.possession_mode)
    if profile.nimble:
        register_goblin_nimble_escape(entity)
    if profile.brute:
        register_brute(entity)
        register_surprise_attack(entity)
    if definition.protection:
        handler = create_protection_handler(entity.uuid)
        handler.behavior_binding = BehaviorBinding(behavior_id="reaction.class_feature.fighter.protection",
            provided_by_id=context.requested_ref.content_id, origin_root_id=context.requested_ref.content_id,
            runtime_owner_uuid=entity.uuid)
        entity.add_event_handler(handler)
    if profile.caster:
        for spell_type in CASTER_SPELLS:
            register_spell(entity, spell_type, caster_level=9)
        register_shield_reaction(entity)
        register_counterspell_reaction(entity)
    if definition.multiattack is not None:
        declaration = GOBLIN_MULTIATTACK_CONFIGURATIONS_BY_ID[definition.multiattack]
        config = MultiattackConfigurationDefinition.model_validate(declaration.definition_payload)
        register_multiattack(entity, declaration.descriptor.display_name,
            tuple((step.weapon_slot, step.count) for step in config.steps), configured_action_ref=declaration.ref)
    return entity


def _declare_goblin(definition: GoblinDefinition) -> ContentDeclaration:
    def factory(raw_context: object, parameters: GoblinRosterParameters) -> Entity:
        return build_goblin(CreatureBuildContext.model_validate(raw_context), definition)

    factory.__name__ = f"build_{definition.key}"
    factory.__qualname__ = factory.__name__
    dependencies = tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION, target_ref=row.ref)
        for row in CORE_STANDARD_ACTION_DECLARATIONS)
    dependencies += tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_FEATURE,
        target_ref=CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[feature].ref)
        for enabled, feature in ((definition.profile.brute, BruteFeature),
            (definition.profile.brute, SurpriseAttackFeature)) if enabled)
    if definition.profile.caster:
        dependencies += tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_SPELL,
            target_ref=SPELL_CONTENT_DECLARATIONS_BY_CLASS[spell].ref) for spell in CASTER_SPELLS)
        dependencies += tuple(ContentDependency(relation=ContentDependencyRelation.INSTALLS_HANDLER, target_ref=row.ref)
            for row in (SHIELD_REACTION_DECLARATION, COUNTERSPELL_REACTION_DECLARATION))
    if definition.multiattack is not None:
        dependencies += tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION, target_ref=row.ref)
            for row in (ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[MultiattackAction],
                GOBLIN_MULTIATTACK_CONFIGURATIONS_BY_ID[definition.multiattack]))
    declared = creature_factory(pack_id="content.neurodragon", content_id=f"creature.{definition.key}", version=1,
        parameters=GoblinRosterParameters,
        descriptor=ContentDescriptorSpec(display_name=definition.name,
            description="Authored goblinoid kit using ordinary equipment and existing creature abilities.",
            tags=("creature", "goblinoid", "humanoid", "adapted"), visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(visual_variant_key=definition.key, ui_group="creatures.neurodragon")),
        provenance=ContentProvenance(primary_source_id="neurodragon.original_b2b3930",
            source_anchor="SRD 5.1 Goblin, Mage and Bugbear numerical benchmarks; authored kits 2026-10-03",
            relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION, adapted_from_source_id="wotc.srd_5_1_cc",
            fidelity=ContentFidelity.PARTIAL, review_status=ContentReviewStatus.REVIEWED,
            notes="Art-led ordinary equipment; encounter CR uncalibrated. Baked riders are single combatants."),
        dependencies=dependencies,
    )(factory)
    return get_content_declaration(declared)


# Canonical creature.goblin remains declared once in bestiary_content.
ASHHOOK = GOBLIN_DEFINITIONS[0]
GOBLIN_DECLARATIONS = tuple(_declare_goblin(row) for row in GOBLIN_DEFINITIONS[1:])
GOBLIN_RECIPES_BY_ID = MappingProxyType({row.ref.content_id.removeprefix("creature."):
    ContentRecipe.create(ref=row.ref, parameters={}) for row in GOBLIN_DECLARATIONS})
