"""The remaining authored Devil kits, composed from native rules and real items.

C01–C05 and C27 retain their existing canonical creature declarations.  The
source keys below deliberately preserve the vendor's literal capitalization.
"""

from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS, SpellAction
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.classes.fighter import create_protection_handler, twf_off_hand_melee_ability_bonus
from dnd.content_system.action_definitions import ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.condition_definitions import CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.creature_possessions import (
    CreaturePossessionDisposition, CreaturePossessionGrant, apply_creature_possessions,
)
from dnd.content_system.reaction_definitions import PROTECTION_REACTION_DECLARATION
from dnd.core.base_block import SenseMode, SensesType
from dnd.core.content.dependencies import ContentDependency, ContentDependencyRelation
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentPresentation, ContentVisibility
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration, creature_factory, get_content_declaration
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.core.equipment_types import BodyPart, EquipmentSlot, WeaponSlot
from dnd.core.modifiers import ContextualNumericalModifier
from dnd.core.values import Channel, Kind, add_modifier
from dnd.entity import Entity
from dnd.monsters.multiattack_definitions import declare_multiattack_configuration
from dnd.monsters.roster_casting import grant_innate_reaction, grant_innate_spell
from dnd.monsters.srd_roster import HitDieValue, create_creature_entity
from dnd.monsters.traits import (
    InnateFlight, InnateInvisibility, MagicResistance, MultiattackAction, ParryFeature,
    register_multiattack, register_parry,
)
from dnd.spells.abjuration import COUNTERSPELL_REACTION_DECLARATION, SHIELD_REACTION_DECLARATION
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS_BY_CLASS
from dnd.spells.conjuration import Darkness, Grease, Web
from dnd.spells.enchantment import Bane, Bless, Command
from dnd.spells.evocation import EldritchBlast, Thunderwave
from dnd.spells.reaction_spell_content import COUNTERSPELL_SPELL_DECLARATION, SHIELD_SPELL_DECLARATION
from dnd.spells.transmutation import Slow


class RemainingFiendParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True, slots=True)
class InnateSpellSelection:
    spell_type: type[SpellAction]
    rank: int
    daily_uses: int | None = None
    caster_level: int = 1


@dataclass(frozen=True, slots=True)
class RemainingFiendDefinition:
    key: str
    name: str
    source_id: str
    source_variant: str
    abilities: tuple[int, int, int, int, int, int]
    hit_points: int
    hit_dice: int
    possessions: tuple[CreaturePossessionGrant, ...]
    size: Size = Size.MEDIUM
    hit_die: HitDieValue = 8
    proficiency: int = 2
    speed: int = 30
    attacks: tuple[tuple[WeaponSlot, int], ...] = ()
    parry: int = 0
    protection: bool = False
    magic_resistance: bool = False
    devils_sight: bool = False
    flying_speed: int | None = None
    imp: bool = False
    paired_weapon_training: bool = False
    one_handed_offhand: bool = False
    athletic: bool = False
    spells: tuple[InnateSpellSelection, ...] = ()
    reactions: tuple[tuple[str, int, int], ...] = ()


def _equipped(item_id: str, slot: EquipmentSlot) -> CreaturePossessionGrant:
    return CreaturePossessionGrant(item_id=item_id,
        disposition=CreaturePossessionDisposition.EQUIPPED, equipment_slot=slot)


def _body(item_id: str) -> CreaturePossessionGrant:
    return CreaturePossessionGrant(item_id=item_id,
        disposition=CreaturePossessionDisposition.INTRINSIC, equipment_slot=WeaponSlot.MELEE_MAIN)


def _kit(main: str, armor: str | None = None, off: str | None = None,
         *, ranged: bool = False) -> tuple[CreaturePossessionGrant, ...]:
    """Plain possession data; no inferred attacks, item riders or extra gear."""
    grants = [_equipped(main, WeaponSlot.RANGED_MAIN if ranged else WeaponSlot.MELEE_MAIN)]
    if armor is not None:
        grants.append(_equipped(armor, BodyPart.BODY))
    if off is not None:
        grants.append(_equipped(off, WeaponSlot.MELEE_OFF))
    if ranged:
        grants.append(_equipped("gear.quiver", BodyPart.BACKPACK))
    return tuple(grants)


MAIN = WeaponSlot.MELEE_MAIN
OFF = WeaponSlot.MELEE_OFF
BOW = WeaponSlot.RANGED_MAIN
REMAINING_FIEND_DEFINITIONS = (
    RemainingFiendDefinition("oathblade_devil", "Oathblade Devil", "C06", "Demon Elite 1",
        (18,18,18,14,14,16),119,14,
        _kit("weapon.roster.psychic_scimitar","armor.half_plate","weapon.roster.psychic_scimitar"),
        proficiency=3,attacks=((MAIN,2),(OFF,1)),parry=3,magic_resistance=True,paired_weapon_training=True),
    RemainingFiendDefinition("blade_marshal_devil", "Blade Marshal Devil", "C07", "Demon Elite 2",
        (20,12,20,14,14,16),142,15,_kit("weapon.roster.psychic_greataxe","armor.plate"),
        proficiency=3,attacks=((MAIN,3),),parry=3,magic_resistance=True,spells=(InnateSpellSelection(Command,1,3),)),
    RemainingFiendDefinition("wing_regent_devil", "Wing Regent Devil", "C08", "Demon Elite 3",
        (22,14,22,18,16,20),207,18,
        (_body("weapon.creature.wing_regent_devil_claws"),_equipped("armor.half_plate",BodyPart.BODY)),
        size=Size.LARGE,hit_die=10,proficiency=4,attacks=((MAIN,3),),magic_resistance=True,
        devils_sight=True,flying_speed=60,spells=(InnateSpellSelection(Slow,3,1),),reactions=(("spell.counterspell",3,3),)),
    RemainingFiendDefinition("glaive_warden_devil", "Glaive Warden Devil", "C09", "Demon Elite 4",
        (18,14,18,12,14,14),110,13,_kit("weapon.roster.psychic_trident","armor.half_plate"),
        proficiency=3,attacks=((MAIN,2),),magic_resistance=True),
    RemainingFiendDefinition("oath_captain_devil", "Oath Captain Devil", "C10", "Demon Elite 5",
        (20,12,20,16,16,18),152,16,_kit("weapon.longsword","armor.plate","shield.shield"),
        proficiency=3,attacks=((MAIN,3),),protection=True,magic_resistance=True,spells=(InnateSpellSelection(Bless,1,3),)),
    RemainingFiendDefinition("gate_tyrant_devil", "Gate Tyrant Devil", "C11", "Demon Elite 6",
        (22,12,22,12,14,18),199,19,_kit("weapon.battleaxe","armor.plate","shield.shield"),
        proficiency=4,attacks=((MAIN,3),),parry=3,magic_resistance=True,athletic=True,
        spells=(InnateSpellSelection(Thunderwave,3,3),)),
    RemainingFiendDefinition("ash_scribe_devil", "Ash Scribe Devil", "C12", "Demon spawn 1",
        (8,14,14,14,12,16),45,7,_kit("focus.wand"),
        spells=(InnateSpellSelection(EldritchBlast,0,caster_level=5),InnateSpellSelection(Web,2,3),InnateSpellSelection(Grease,1,3),InnateSpellSelection(Bless,1,1))),
    RemainingFiendDefinition("debt_collector_devil", "Debt Collector Devil", "C13", "Demon Spawn 2",
        (14,14,14,10,10,10),39,6,_kit("weapon.mace","armor.studded_leather"),attacks=((MAIN,2),)),
    RemainingFiendDefinition("reaping_imp", "Reaping Imp", "I02", "Demon Spawn 3",
        (6,17,13,11,12,14),10,3,_kit("weapon.sickle"),size=Size.TINY,hit_die=4,speed=20,
        magic_resistance=True,devils_sight=True,flying_speed=40,imp=True),
    RemainingFiendDefinition("wardblade_devil", "Wardblade Devil", "C14", "Demon Spawn 4",
        (16,12,14,10,12,10),52,8,_kit("weapon.roster.psychic_longsword","armor.scale_mail","shield.shield"),
        attacks=((MAIN,2),),protection=True),
    RemainingFiendDefinition("contract_cutter_devil", "Contract Cutter Devil", "C15", "Demon Spawn 5",
        (12,16,14,12,12,12),45,7,_kit("weapon.scimitar","armor.studded_leather","weapon.scimitar"),
        attacks=((MAIN,1),(OFF,1)),parry=2,paired_weapon_training=True),
    RemainingFiendDefinition("bow_harrier_devil", "Bow Harrier Devil", "C16", "Demon Spawn 6",
        (12,16,12,10,12,10),27,5,_kit("weapon.shortbow","armor.leather",ranged=True),attacks=((BOW,2),)),
    RemainingFiendDefinition("night_archer_devil", "Night Archer Devil", "C17", "Demon Spawn 7",
        (12,18,14,12,14,12),52,8,_kit("weapon.shortbow","armor.studded_leather",ranged=True),
        attacks=((BOW,2),),devils_sight=True),
    RemainingFiendDefinition("night_notary_devil", "Night Notary Devil", "C18", "Demon Spawn 8",
        (10,14,16,16,14,18),90,12,_kit("weapon.quarterstaff"),magic_resistance=True,devils_sight=True,
        spells=(InnateSpellSelection(EldritchBlast,0,caster_level=11),InnateSpellSelection(Darkness,2,3),InnateSpellSelection(Web,2,3),InnateSpellSelection(Slow,3,1)),
        reactions=(("spell.counterspell",3,1),)),
    RemainingFiendDefinition("gate_guard_devil", "Gate Guard Devil", "C19", "Demon Spawn 9",
        (12,16,16,10,12,10),75,10,_kit("weapon.scimitar","armor.studded_leather","shield.shield"),
        attacks=((MAIN,2),),protection=True),
    RemainingFiendDefinition("ivory_marksman_devil", "Ivory Marksman Devil", "C20", "Demon Spawn 10",
        (12,18,16,12,14,12),90,12,_kit("weapon.longbow","armor.half_plate",ranged=True),attacks=((BOW,2),)),
    RemainingFiendDefinition("bastion_magus_devil", "Bastion Magus Devil", "C21", "Demon Spawn 11",
        (12,14,16,14,12,16),75,10,_kit("focus.wand","armor.half_plate"),
        spells=(InnateSpellSelection(EldritchBlast,0,caster_level=5),InnateSpellSelection(Bless,1,3),InnateSpellSelection(Web,2,3)),reactions=(("spell.shield",1,3),)),
    RemainingFiendDefinition("bulwark_devil", "Bulwark Devil", "C22", "Demon Spawn 12",
        (18,12,18,10,12,12),85,10,_kit("weapon.shortsword","armor.half_plate","shield.shield"),
        attacks=((MAIN,2),),protection=True),
    RemainingFiendDefinition("tollbreaker_devil", "Tollbreaker Devil", "C23", "Demon Spawn 13",
        (18,14,16,10,12,10),90,12,_kit("weapon.handaxe","armor.studded_leather","weapon.longsword"),
        attacks=((MAIN,1),(OFF,1)),paired_weapon_training=True,one_handed_offhand=True,athletic=True),
    RemainingFiendDefinition("shieldwing_imp", "Shieldwing Imp", "I01", "Imp 1",
        (6,17,13,11,12,14),10,3,_kit("weapon.handaxe",off="shield.shield"),
        size=Size.TINY,hit_die=4,speed=20,magic_resistance=True,devils_sight=True,flying_speed=40,imp=True),
    RemainingFiendDefinition("club_mote_devil", "Club Mote Devil", "C24", "Imp 2",
        (10,14,10,8,10,8),7,2,_kit("weapon.club"),size=Size.SMALL,hit_die=6,speed=25),
    RemainingFiendDefinition("standard_mote_devil", "Standard Mote Devil", "C25", "Imp 3",
        (10,14,12,10,10,12),13,3,_kit("weapon.scimitar","armor.leather") +
        (CreaturePossessionGrant(item_id="tool.banner",disposition=CreaturePossessionDisposition.INVENTORY),),
        size=Size.SMALL,hit_die=6,speed=25),
    RemainingFiendDefinition("needle_mote_devil", "Needle Mote Devil", "C26", "Imp 4",
        (10,14,10,8,10,8),7,2,_kit("weapon.dagger"),size=Size.SMALL,hit_die=6,speed=25),
    RemainingFiendDefinition("spear_mote_devil", "Spear Mote Devil", "C28", "Imp 6",
        (12,12,12,8,10,8),9,2,_kit("weapon.spear","armor.leather"),size=Size.SMALL,hit_die=6,speed=25),
    RemainingFiendDefinition("bow_mote_devil", "Bow Mote Devil", "C29", "Imp 7",
        (10,14,12,10,12,10),18,4,_kit("weapon.shortbow","armor.leather",ranged=True),
        size=Size.SMALL,hit_die=6,speed=25),
    RemainingFiendDefinition("buckler_mote_devil", "Buckler Mote Devil", "C30", "Imp 8",
        (12,14,14,10,10,10),27,5,_kit("weapon.scimitar","armor.leather","shield.shield"),
        size=Size.SMALL,hit_die=6,speed=25,protection=True),
    RemainingFiendDefinition("rod_mote_devil", "Rod Mote Devil", "C31", "Imp 9",
        (8,14,12,12,10,14),18,4,_kit("weapon.quarterstaff",off="weapon.dagger"),
        size=Size.SMALL,hit_die=6,speed=25,
        spells=(InnateSpellSelection(EldritchBlast,0),InnateSpellSelection(Grease,1,3),InnateSpellSelection(Bane,1,1))),
    RemainingFiendDefinition("twinhaft_mote_devil", "Twinhaft Mote Devil", "C32", "Imp 10",
        (12,14,14,10,10,10),27,5,_kit("weapon.shortsword","armor.scale_mail","weapon.dagger"),
        size=Size.SMALL,hit_die=6,speed=25,attacks=((MAIN,1),(OFF,1)),paired_weapon_training=True),
)


def _provenance(definition: RemainingFiendDefinition) -> ContentProvenance:
    notes = "Authored stats and accepted real-item kits; CR is provisional. No humanoid stat-block foundation."
    if definition.imp:
        notes += " Armed Imp Sting/Shapechanger and nonsilvered physical resistance omitted by disposition."
    if definition.source_id == "C08":
        notes += " Legendary actions and Legendary Resistance deferred."
    if definition.paired_weapon_training:
        notes += " Exact Multiattack count; separately paid native bonus offhand attack retained as an explicit adaptation."
    return ContentProvenance(primary_source_id="neurodragon.original_b2b3930",
        source_anchor=f"Authored Devils study 2026-10-01 {definition.source_id}; dispositions 2026-10-02; authoring plan 2026-10-18",
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.PARTIAL if definition.imp or definition.source_id == "C08" or definition.paired_weapon_training else ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=notes)


REMAINING_FIEND_MULTIATTACK_DECLARATIONS = tuple(
    declare_multiattack_configuration(content_id=f"action.monster.multiattack.{row.key}",
        display_name=f"{row.name} Multiattack",icon_key="ui.filter-attacks",
        source_anchor=f"Authored Devils {row.source_id}",steps=row.attacks,sort_order=100+index,
        pack_id="content.neurodragon",provenance=_provenance(row))
    for index,row in enumerate(REMAINING_FIEND_DEFINITIONS) if row.attacks)
_MULTIATTACKS = {row.ref.content_id.removeprefix("action.monster.multiattack."): row
    for row in REMAINING_FIEND_MULTIATTACK_DECLARATIONS}
_REACTION_SPELLS = {"spell.counterspell": (COUNTERSPELL_SPELL_DECLARATION,COUNTERSPELL_REACTION_DECLARATION),
    "spell.shield": (SHIELD_SPELL_DECLARATION,SHIELD_REACTION_DECLARATION)}


def _declare(definition: RemainingFiendDefinition) -> ContentDeclaration:
    multiattack = _MULTIATTACKS.get(definition.key)

    def factory(raw_context: object, parameters: RemainingFiendParameters) -> Entity:
        context = CreatureBuildContext.model_validate(raw_context)
        skills = {skill:True for skill in ("deception","insight","persuasion","stealth")} if definition.imp else {}
        if definition.athletic:
            skills["athletics"] = True
        entity = create_creature_entity(context=context,
            description=f"{definition.name}; authored Devil {definition.source_id} ({definition.source_variant}).",
            abilities=definition.abilities,hit_die_value=definition.hit_die,hit_die_count=definition.hit_dice,
            hit_points=definition.hit_points,proficiency_bonus=definition.proficiency,
            creature_type=CreatureType.FIEND,size=definition.size,movement=definition.speed,
            immunities=(DamageType.FIRE,DamageType.POISON),
            resistances=(DamageType.COLD,) if definition.imp else (),skills=skills,
            languages=("language.infernal","language.common"))
        entity.appearance.visual_scale = 1.0
        install_body_response(entity,BLOOD_BODY_RESPONSE)
        entity.add_condition_immunity("Poisoned",immunity_name=definition.name)
        entity.senses.sense_modes.append(SenseMode(sense_type=SensesType.DARKVISION,
            range_feet=120 if definition.devils_sight else 60))
        if definition.devils_sight:
            entity.senses.sense_modes.append(SenseMode(sense_type=SensesType.DEVILS_SIGHT,range_feet=120))
        if definition.one_handed_offhand:
            entity.grant_one_handed_offhand(entity.uuid)
        apply_creature_possessions(entity,definition.possessions,possession_mode=context.possession_mode)
        if definition.paired_weapon_training:
            add_modifier(entity.equipment.off_hand_melee_ability_bonus, Channel.SELF_CONTEXTUAL, Kind.VALUE,
                ContextualNumericalModifier(name="Authored paired weapon training",
                    source_entity_uuid=entity.uuid,target_entity_uuid=entity.uuid,
                    callable=twf_off_hand_melee_ability_bonus))
        if definition.magic_resistance:
            entity.add_condition(MagicResistance(source_entity_uuid=entity.uuid,target_entity_uuid=entity.uuid))
        if definition.flying_speed is not None:
            entity.add_condition(InnateFlight(source_entity_uuid=entity.uuid,target_entity_uuid=entity.uuid,
                flying_speed=definition.flying_speed))
        if definition.imp:
            entity.register_action(InnateInvisibility(source_entity_uuid=entity.uuid,template=True))
        if definition.parry:
            register_parry(entity,definition.parry)
        if definition.protection:
            handler = create_protection_handler(entity.uuid)
            handler.behavior_binding = BehaviorBinding(behavior_id="reaction.class_feature.fighter.protection",
                provided_by_id=context.requested_ref.content_id,origin_root_id=context.requested_ref.content_id,
                runtime_owner_uuid=entity.uuid)
            entity.add_event_handler(handler)
        if multiattack is not None:
            register_multiattack(entity,multiattack.descriptor.display_name,definition.attacks,
                configured_action_ref=multiattack.ref)
        for selection in definition.spells:
            grant_innate_spell(entity,selection.spell_type,caster_level=selection.caster_level,
                cast_rank=selection.rank,daily_uses=selection.daily_uses)
        for spell_id,rank,uses in definition.reactions:
            grant_innate_reaction(entity,spell_id,cast_rank=rank,daily_uses=uses)
        return entity

    factory.__name__ = f"build_{definition.key}"
    factory.__qualname__ = factory.__name__
    dependencies = [ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,target_ref=row.ref)
        for row in CORE_STANDARD_ACTION_DECLARATIONS]
    for enabled,feature in ((definition.magic_resistance,MagicResistance),(definition.flying_speed is not None,InnateFlight),
            (bool(definition.parry),ParryFeature)):
        if enabled:
            dependencies.append(ContentDependency(relation=ContentDependencyRelation.GRANTS_FEATURE,
                target_ref=CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[feature].ref))
    if definition.imp:
        dependencies.append(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[InnateInvisibility].ref))
    if definition.protection:
        dependencies.append(ContentDependency(relation=ContentDependencyRelation.INSTALLS_HANDLER,
            target_ref=PROTECTION_REACTION_DECLARATION.ref))
    if multiattack is not None:
        dependencies.extend(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,target_ref=row.ref)
            for row in (ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[MultiattackAction],multiattack))
    dependencies.extend(ContentDependency(relation=ContentDependencyRelation.GRANTS_SPELL,
        target_ref=SPELL_CONTENT_DECLARATIONS_BY_CLASS[selection.spell_type].ref) for selection in definition.spells)
    for spell_id,_,_ in definition.reactions:
        spell,handler = _REACTION_SPELLS[spell_id]
        dependencies.extend((ContentDependency(relation=ContentDependencyRelation.GRANTS_SPELL,target_ref=spell.ref),
            ContentDependency(relation=ContentDependencyRelation.INSTALLS_HANDLER,target_ref=handler.ref)))
    declared = creature_factory(pack_id="content.neurodragon",content_id=f"creature.{definition.key}",version=1,
        parameters=RemainingFiendParameters,
        descriptor=ContentDescriptorSpec(display_name=definition.name,
            description=f"Authored Devil {definition.source_id}; {definition.source_variant}.",
            tags=("creature","fiend","devil"),visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(portrait_key=f"creature.{definition.key}",
                visual_variant_key=definition.key,ui_group="creatures.neurodragon")),
        provenance=_provenance(definition),dependencies=tuple(dependencies))(factory)
    return get_content_declaration(declared)


REMAINING_FIEND_DECLARATIONS = tuple(_declare(row) for row in REMAINING_FIEND_DEFINITIONS)
REMAINING_FIEND_RECIPES_BY_ID = MappingProxyType({row.ref.content_id.removeprefix("creature."):
    ContentRecipe.create(ref=row.ref,parameters={}) for row in REMAINING_FIEND_DECLARATIONS})
