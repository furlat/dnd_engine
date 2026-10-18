"""Selected undead champions and casters composed from existing native rules."""

from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS, SpellAction
from dnd.actions_functional import register_spell
from dnd.body_responses import BONE_BODY_RESPONSE, install_body_response
from dnd.classes.barbarian import RecklessAttack
from dnd.classes.fighter import create_protection_handler
from dnd.content_system.action_definitions import ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.condition_definitions import CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.creature_possessions import CreaturePossessionDisposition, CreaturePossessionGrant, apply_creature_possessions
from dnd.content_system.reaction_definitions import PROTECTION_REACTION_DECLARATION
from dnd.core.content.dependencies import ContentDependency, ContentDependencyRelation
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentPresentation, ContentVisibility
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration, creature_factory, get_content_declaration
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.equipment_types import BodyPart, EquipmentSlot, WeaponKind, WeaponSlot
from dnd.core.proficiency_types import ProficiencyMode
from dnd.entity import Entity
from dnd.monsters.multiattack_definitions import declare_multiattack_configuration
from dnd.monsters.roster_casting import ARCHMAGE_SPELLS, MAGE_SPELLS, grant_innate_spell
from dnd.monsters.srd_roster import HitDieValue, create_creature_entity
from dnd.monsters.traits import (
    BraveFeature, BruteFeature, MagicResistance, MultiattackAction, ParryFeature,
    SpellDamageResistance, SunlightSensitivityFeature, WightLifeDrain,
    register_brave, register_brute, register_multiattack, register_parry,
    register_reckless, register_sunlight_sensitivity, AttackReplacement,
)
from dnd.spells.abjuration import COUNTERSPELL_REACTION_DECLARATION, SHIELD_REACTION_DECLARATION, register_counterspell_reaction, register_shield_reaction
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS_BY_CLASS
from dnd.spells.evocation import BurningHands
from dnd.spells.illusion import Invisibility
from dnd.types.abilities import AbilityName


class UndeadRosterParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class UndeadProfile:
    abilities: tuple[int, int, int, int, int, int]
    hp: int
    hit_die: HitDieValue
    hit_dice: int
    proficiency: int
    saves: tuple[AbilityName, ...] = ()
    skills: tuple[str, ...] = ()
    brute: bool = False
    brave: bool = False
    reckless: bool = False
    wight: bool = False
    caster_level: int = 0
    spells: tuple[type[SpellAction], ...] = ()
    slots: tuple[tuple[int, int], ...] = ()
    archmage: bool = False


GLADIATOR = UndeadProfile((18,15,16,10,12,15),112,8,15,3,
    saves=("strength","dexterity","constitution"),skills=("athletics","intimidation"),brute=True,brave=True)
WIGHT = UndeadProfile((15,14,16,10,13,15),45,8,6,2,skills=("perception","stealth"),wight=True)
BERSERKER = UndeadProfile((16,12,17,9,11,9),67,8,9,2,reckless=True)
ARCHMAGE = UndeadProfile((10,14,12,20,15,16),99,8,18,4,
    saves=("intelligence","wisdom"),skills=("arcana","history"),caster_level=18,
    spells=ARCHMAGE_SPELLS,slots=((1,4),(2,3),(3,3),(4,3),(5,3),(6,1),(7,1),(8,1),(9,1)),archmage=True)
MAGE = UndeadProfile((9,14,11,17,12,11),40,8,9,3,
    saves=("intelligence","wisdom"),skills=("arcana","history"),caster_level=9,
    spells=MAGE_SPELLS,slots=((1,4),(2,3),(3,3),(4,3),(5,1)))


@dataclass(frozen=True)
class UndeadDefinition:
    key: str
    name: str
    source_variant: str
    profile: UndeadProfile
    possessions: tuple[CreaturePossessionGrant, ...]
    attacks: tuple[tuple[WeaponSlot, int], ...] = ()
    parry: int = 0
    protection: bool = False
    burning_hands: bool = False
    life_drain_weapon: WeaponKind | None = None


def _equipped(item_id: str, slot: EquipmentSlot) -> CreaturePossessionGrant:
    return CreaturePossessionGrant(item_id=item_id,
        disposition=CreaturePossessionDisposition.EQUIPPED, equipment_slot=slot)


UNDEAD_DEFINITIONS = (
    UndeadDefinition("undead_bonewheel", "Bone-wheel Cleaver", "1Brute", GLADIATOR,
        (_equipped("weapon.greatsword",WeaponSlot.MELEE_MAIN),), attacks=((WeaponSlot.MELEE_MAIN,3),),parry=3),
    UndeadDefinition("undead_ash_crown", "Ash-crown Revenant", "2DeathLord", WIGHT,
        (_equipped("weapon.roster.ember_longsword",WeaponSlot.MELEE_MAIN),
         _equipped("shield.shield",WeaponSlot.MELEE_OFF),_equipped("armor.plate",BodyPart.BODY)),
        attacks=((WeaponSlot.MELEE_MAIN,2),),life_drain_weapon=WeaponKind.LONGSWORD),
    UndeadDefinition("undead_flareblade", "Flareblade Grave Sentinel", "3DarkKnight", WIGHT,
        (_equipped("weapon.roster.ember_longsword",WeaponSlot.MELEE_MAIN),
         _equipped("shield.shield",WeaponSlot.MELEE_OFF),_equipped("armor.half_plate",BodyPart.BODY)),
        attacks=((WeaponSlot.MELEE_MAIN,2),),parry=2,life_drain_weapon=WeaponKind.LONGSWORD),
    UndeadDefinition("undead_red_crescent", "Red-crescent Ravager", "4Berserker", BERSERKER,
        (_equipped("weapon.greataxe",WeaponSlot.MELEE_MAIN),),burning_hands=True),
    UndeadDefinition("undead_pikeward", "Pikeward", "6Warrior", WIGHT,
        (_equipped("weapon.spear",WeaponSlot.MELEE_MAIN),_equipped("shield.shield",WeaponSlot.MELEE_OFF)),
        attacks=((WeaponSlot.MELEE_MAIN,2),),protection=True,life_drain_weapon=WeaponKind.SPEAR),
    UndeadDefinition("undead_black_fletch", "The Black Fletch", "7DarkArcher", WIGHT,
        (_equipped("weapon.shortbow",WeaponSlot.RANGED_MAIN),_equipped("gear.quiver",BodyPart.BACKPACK)),
        attacks=((WeaponSlot.RANGED_MAIN,2),)),
    UndeadDefinition("undead_ossuary_hierophant", "Violet Ossuary Hierophant", "8Necromancer", ARCHMAGE, ()),
    UndeadDefinition("undead_ember_oracle", "Antlered Ember Oracle", "9Wizard", MAGE, ()),
)

UNDEAD_MULTIATTACK_DECLARATIONS = tuple(declare_multiattack_configuration(
    content_id=f"action.monster.multiattack.{row.key}",display_name=f"{row.name} Multiattack",
    icon_key="ui.filter-attacks",source_anchor=f"Accepted undead roster {row.source_variant}",
    steps=row.attacks,sort_order=index,pack_id="content.neurodragon")
    for index,row in enumerate(UNDEAD_DEFINITIONS) if row.attacks)
_MULTIATTACKS = MappingProxyType({row.ref.content_id.removeprefix("action.monster.multiattack."):row
                                for row in UNDEAD_MULTIATTACK_DECLARATIONS})


def _declare_undead(definition: UndeadDefinition) -> ContentDeclaration:
    profile = definition.profile
    configuration = _MULTIATTACKS.get(definition.key)

    def factory(raw_context: object, parameters: UndeadRosterParameters) -> Entity:
        context = CreatureBuildContext.model_validate(raw_context)
        entity = create_creature_entity(context=context,
            description=f"{definition.name}; selected undead/{definition.source_variant} adaptation.",
            abilities=profile.abilities,hit_points=profile.hp,hit_die_value=profile.hit_die,
            hit_die_count=profile.hit_dice,proficiency_bonus=profile.proficiency,
            creature_type=CreatureType.UNDEAD,darkvision=profile.wight,
            immunities=(DamageType.POISON,),resistances=(DamageType.NECROTIC,) if profile.wight else (),
            skills={skill:True for skill in profile.skills},save_proficiencies=profile.saves,
            spellcasting_ability="intelligence" if profile.caster_level else None,
            spell_slots=dict(profile.slots),languages=("language.common","language.elvish","language.dwarvish",
                "language.draconic","language.infernal","language.celestial") if profile.archmage else
                ("language.common","language.elvish","language.draconic","language.dwarvish") if profile.caster_level else
                ("language.common",))
        entity.appearance.visual_scale = 1.0
        install_body_response(entity,BONE_BODY_RESPONSE)
        for condition in ("Poisoned","Exhaustion"):
            entity.add_condition_immunity(condition,immunity_name=definition.name)
        apply_creature_possessions(entity,definition.possessions,possession_mode=context.possession_mode)
        if profile.brute:
            register_brute(entity)
            entity.skill_set.athletics.add_proficiency_source(entity.uuid,ProficiencyMode.EXPERTISE)
        if profile.brave:
            register_brave(entity)
        if profile.reckless:
            register_reckless(entity)
        if profile.wight:
            register_sunlight_sensitivity(entity)
            entity.register_action(WightLifeDrain(source_entity_uuid=entity.uuid,template=True))
        if definition.parry:
            register_parry(entity,definition.parry)
        if definition.protection:
            handler=create_protection_handler(entity.uuid)
            handler.behavior_binding=BehaviorBinding(behavior_id=PROTECTION_REACTION_DECLARATION.ref.content_id,
                provided_by_id=context.requested_ref.content_id,origin_root_id=context.requested_ref.content_id,
                runtime_owner_uuid=entity.uuid)
            entity.add_event_handler(handler)
        if configuration is not None:
            if definition.life_drain_weapon is not None:
                action=MultiattackAction(source_entity_uuid=entity.uuid,template=True,
                    attack_sequence=definition.attacks,configured_action_ref=configuration.ref,
                    attack_replacement=AttackReplacement(sequence_index=0,weapon_kind=definition.life_drain_weapon,
                        action=WightLifeDrain(source_entity_uuid=entity.uuid)))
                entity.register_action(action)
            else:
                register_multiattack(entity,"Multiattack",definition.attacks,configured_action_ref=configuration.ref)
        if definition.burning_hands:
            grant_innate_spell(entity,BurningHands,caster_level=1,cast_rank=1,daily_uses=1)
        for spell_type in profile.spells:
            register_spell(entity,spell_type,caster_level=profile.caster_level)
        if profile.caster_level:
            register_counterspell_reaction(entity)
            if profile.archmage:
                for skill in (entity.skill_set.arcana,entity.skill_set.history):
                    skill.add_proficiency_source(entity.uuid,ProficiencyMode.EXPERTISE)
                entity.add_condition(MagicResistance(source_entity_uuid=entity.uuid,target_entity_uuid=entity.uuid))
                entity.add_condition(SpellDamageResistance(source_entity_uuid=entity.uuid,target_entity_uuid=entity.uuid))
                grant_innate_spell(entity,Invisibility,caster_level=18,ability="intelligence")
            else:
                register_shield_reaction(entity)
        return entity

    factory.__name__=f"build_{definition.key}"
    factory.__qualname__=factory.__name__
    dependencies=[ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,target_ref=row.ref)
                  for row in CORE_STANDARD_ACTION_DECLARATIONS]
    for enabled,feature in ((profile.brute,BruteFeature),(profile.brave,BraveFeature),
            (profile.wight,SunlightSensitivityFeature),(profile.archmage,MagicResistance),
            (profile.archmage,SpellDamageResistance),(bool(definition.parry),ParryFeature)):
        if enabled:
            dependencies.append(ContentDependency(relation=ContentDependencyRelation.GRANTS_FEATURE,
                target_ref=CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[feature].ref))
    if configuration is not None:
        dependencies.extend(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,target_ref=row.ref)
            for row in (configuration,ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[MultiattackAction]))
    if profile.wight:
        dependencies.append(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[WightLifeDrain].ref))
    if definition.protection:
        dependencies.append(ContentDependency(relation=ContentDependencyRelation.INSTALLS_HANDLER,
            target_ref=PROTECTION_REACTION_DECLARATION.ref))
    if profile.reckless:
        dependencies.append(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[RecklessAttack].ref))
    spells=(*profile.spells,*((BurningHands,) if definition.burning_hands else ()),
            *((Invisibility,) if profile.archmage else ()))
    dependencies.extend(ContentDependency(relation=ContentDependencyRelation.GRANTS_SPELL,
        target_ref=SPELL_CONTENT_DECLARATIONS_BY_CLASS[spell].ref) for spell in spells)
    if profile.caster_level:
        dependencies.append(ContentDependency(relation=ContentDependencyRelation.INSTALLS_HANDLER,
            target_ref=COUNTERSPELL_REACTION_DECLARATION.ref))
        if not profile.archmage:
            dependencies.append(ContentDependency(relation=ContentDependencyRelation.INSTALLS_HANDLER,
                target_ref=SHIELD_REACTION_DECLARATION.ref))
    declared=creature_factory(pack_id="content.neurodragon",content_id=f"creature.{definition.key}",
        version=1,parameters=UndeadRosterParameters,
        descriptor=ContentDescriptorSpec(display_name=definition.name,
            description=f"undead/{definition.source_variant}; authored adaptation, threat uncalibrated.",
            tags=("creature","undead","roster","uncalibrated"),visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(portrait_key=f"creature.{definition.key}",visual_variant_key=definition.key,
                ui_group="creatures.neurodragon")),
        provenance=ContentProvenance(primary_source_id="neurodragon.original_b2b3930",
            source_anchor=f"Nonanimal roster2026-10-18 undead/{definition.source_variant}",
            relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,adapted_from_source_id="wotc.srd_5_1_cc",
            fidelity=ContentFidelity.PARTIAL,review_status=ContentReviewStatus.REVIEWED,
            notes="Explicit undead adaptation and real gear. Omitted deferred signatures, controlled zombie creation, unsupported utility spells and silver-qualified physical resistance; source CR uncalibrated. Canonical Skeleton Archer remains a separate retained identity."),
        dependencies=tuple(dependencies))(factory)
    return get_content_declaration(declared)


UNDEAD_ROSTER_DECLARATIONS=tuple(_declare_undead(row) for row in UNDEAD_DEFINITIONS)
UNDEAD_ROSTER_RECIPES_BY_ID=MappingProxyType({row.ref.content_id.removeprefix("creature."):
    ContentRecipe.create(ref=row.ref,parameters={}) for row in UNDEAD_ROSTER_DECLARATIONS})
