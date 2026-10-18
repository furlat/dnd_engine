"""The selected Orc, HD Enemy, Barbarian and Character NPC kits.

Vendor family names identify source cards, never PC classes or creature types.
These are passive stat/possession selections over the existing native owners.
"""

from dataclasses import dataclass, replace
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS, SpellAction
from dnd.actions_functional import register_spell
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.classes.barbarian import RecklessAttack
from dnd.classes.fighter import create_protection_handler, twf_off_hand_melee_ability_bonus
from dnd.content_system.action_definitions import ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.condition_definitions import CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.reaction_definitions import PROTECTION_REACTION_DECLARATION
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
from dnd.core.content.registration import ContentDeclaration, creature_factory, get_content_declaration
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.core.equipment_types import BodyPart, EquipmentSlot, WeaponKind, WeaponSlot
from dnd.core.modifiers import ContextualNumericalModifier
from dnd.core.values import Channel, Kind, add_modifier
from dnd.entity import Entity
from dnd.monsters.multiattack_definitions import declare_multiattack_configuration
from dnd.monsters.roster_casting import (
    ARCHMAGE_SPELLS, MAGE_SPELLS, grant_innate_spell,
)
from dnd.monsters.srd_roster import HitDieValue, create_creature_entity
from dnd.monsters.traits import (
    AggressiveMoveAction, AssassinateFeature, BraveFeature, BruteFeature,
    DivineEminenceAction, EvasionFeature, HitSaveRiderFeature, LeadershipAction,
    MagicResistance, MultiattackAction, ParryFeature, ShieldBash, SneakAttackFeature,
    SpellDamageResistance, register_aggressive, register_assassinate, register_brave,
    register_brute, register_divine_eminence, register_leadership, register_multiattack,
    register_parry, register_reckless, register_shield_bash, register_sneak_attack,
    shield_bash_multiattack,
)
from dnd.spells.abjuration import (
    COUNTERSPELL_REACTION_DECLARATION, SHIELD_REACTION_DECLARATION,
    register_counterspell_reaction, register_shield_reaction,
)
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS_BY_CLASS
from dnd.spells.conjuration import ProduceFlame, Web
from dnd.spells.evocation import BurningHands, Thunderwave
from dnd.spells.illusion import Invisibility
from dnd.spells.transmutation import Barkskin, Fly, Longstrider, Shillelagh, Slow
from dnd.types.abilities import AbilityName, SkillName


class HumanoidRosterParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class NpcFoundation:
    source: str
    abilities: tuple[int, int, int, int, int, int]
    hp: int
    hit_dice: int
    proficiency: int = 2
    hit_die: HitDieValue = 8
    size: Size = Size.MEDIUM
    creature_type: CreatureType = CreatureType.HUMANOID
    speed: int = 30
    skills: tuple[SkillName, ...] = ()
    expertise: tuple[SkillName, ...] = ()
    saves: tuple[AbilityName, ...] = ()
    languages: tuple[str, ...] = ("language.common",)
    darkvision: bool = False
    parry: int = 0
    brave: bool = False
    brute: bool = False
    leadership: bool = False
    aggressive: bool = False
    assassin: bool = False
    reckless: bool = False
    caster_level: int = 0
    casting_ability: AbilityName | None = None
    slots: tuple[tuple[int, int], ...] = ()
    spells: tuple[type[SpellAction], ...] = ()
    shield_spell: bool = False
    counterspell: bool = False


ORC = NpcFoundation("Orc", (16,12,16,7,11,10), 15,2,
    skills=("intimidation",), languages=("language.common","language.orc"),
    darkvision=True, aggressive=True)
MAGE = NpcFoundation("Mage", (9,14,11,17,12,11), 40,9,proficiency=3,
    skills=("arcana","history"), saves=("intelligence","wisdom"),
    languages=("language.common","language.elvish","language.draconic","language.dwarvish"),
    caster_level=9,casting_ability="intelligence", slots=((1,4),(2,3),(3,3),(4,3),(5,1)),
    spells=MAGE_SPELLS,shield_spell=True,counterspell=True)
ORC_MAGE = replace(MAGE, languages=(*MAGE.languages[:-1],"language.orc"),darkvision=True)
GLADIATOR = NpcFoundation("Gladiator", (18,15,16,10,12,15),112,15,proficiency=3,
    skills=("athletics","intimidation"),expertise=("athletics",),
    saves=("strength","dexterity","constitution"),parry=3,brave=True,brute=True)
TRAINED = replace(GLADIATOR, source="Gladiator; authored level11 martial-die reference",parry=0,brute=False)
ASSASSIN = NpcFoundation("Assassin", (11,16,14,13,11,10),78,12,proficiency=3,
    skills=("acrobatics","deception","perception","stealth"),expertise=("stealth",),
    saves=("dexterity","intelligence"),
    languages=("language.common","language.elvish","language.thieves_cant"),assassin=True)
KNIGHT = NpcFoundation("Knight",(16,11,14,11,11,15),52,8,
    saves=("constitution","wisdom"),parry=2,brave=True,leadership=True)
VETERAN = NpcFoundation("Veteran",(16,13,14,10,11,10),58,9,
    skills=("athletics","perception"))
CAPTAIN = NpcFoundation("Bandit Captain",(15,16,14,14,11,14),65,10,
    skills=("athletics","deception"),saves=("strength","dexterity","wisdom"),
    languages=("language.common","language.goblin"),parry=2)
BERSERKER = NpcFoundation("Berserker",(16,12,17,9,11,9),67,9,reckless=True)
OGRE = NpcFoundation("Ogre",(19,8,16,5,7,7),59,7,hit_die=10,
    size=Size.LARGE,creature_type=CreatureType.GIANT,speed=40,darkvision=True,
    languages=("language.common","language.giant"))
DRUID_SPELLS = (ProduceFlame,Shillelagh,Longstrider,Thunderwave,Barkskin)
DRUID = NpcFoundation("Druid",(10,12,13,12,15,11),27,5,
    skills=("medicine","nature","perception"),
    languages=("language.common","language.elvish","language.druidic"),
    caster_level=4,casting_ability="wisdom",slots=((1,4),(2,3)),spells=DRUID_SPELLS)
ARCHMAGE = NpcFoundation("Archmage",(10,14,12,20,15,16),99,18,proficiency=4,
    skills=("arcana","history"),expertise=("arcana","history"),saves=("intelligence","wisdom"),
    languages=("language.common","language.elvish","language.draconic","language.dwarvish",
               "language.infernal","language.celestial"),
    caster_level=18,casting_ability="intelligence",
    slots=((1,4),(2,3),(3,3),(4,3),(5,3),(6,1),(7,1),(8,1),(9,1)),
    spells=ARCHMAGE_SPELLS,counterspell=True)
SENTINEL = NpcFoundation("Authored Arcane Sentinel E01",(16,14,18,10,12,8),119,14,
    proficiency=3,creature_type=CreatureType.ELEMENTAL,skills=("perception",),
    saves=("constitution","wisdom"),darkvision=True)


@dataclass(frozen=True)
class HumanoidRosterDefinition:
    key: str
    name: str
    pack: str
    source_variant: str
    foundation: NpcFoundation
    possessions: tuple[CreaturePossessionGrant, ...]
    attacks: tuple[tuple[WeaponSlot,int], ...] = ()
    protection: bool = False
    web: bool = False
    burning_hands: bool = False
    innate_burning_hands: bool = False
    slow: bool = False
    divine_eminence: bool = False
    shield_bash: bool = False
    trained_die: HitDieValue | None = None


def _equipped(item_id: str, slot: EquipmentSlot) -> CreaturePossessionGrant:
    return CreaturePossessionGrant(item_id,CreaturePossessionDisposition.EQUIPPED,slot)


def _inventory(item_id: str,stack_count: int = 1) -> CreaturePossessionGrant:
    return CreaturePossessionGrant(item_id,CreaturePossessionDisposition.INVENTORY,stack_count=stack_count)


MAIN = WeaponSlot.MELEE_MAIN
OFF = WeaponSlot.MELEE_OFF
BOW = WeaponSlot.RANGED_MAIN
BODY = BodyPart.BODY
BACK = BodyPart.BACKPACK
_POISON = (_inventory("consumable.weapon_coat.assassin_poison",3),)

# Core source armor is deliberately replaced only where the accepted art-led kit
# chooses another grade. Optional old enhancement proposals are not selected.
HUMANOID_ROSTER_DEFINITIONS = (
    HumanoidRosterDefinition("orc_rededge","Rededge","orcs_goblins","Orc 02",ORC,(
        _equipped("weapon.battleaxe",MAIN),_equipped("apparel.common_clothes",BODY))),
    HumanoidRosterDefinition("orc_yellowtusk","Yellowtusk","orcs_goblins","Orc 03",ORC,(
        _equipped("weapon.battleaxe",MAIN),_equipped("apparel.common_clothes",BODY),
        _equipped("apparel.iron_helmet",BodyPart.HEAD))),
    HumanoidRosterDefinition("orc_redblade","Redblade","orcs_goblins","Orc 09",ORC,(
        _equipped("weapon.shortsword",MAIN),_equipped("apparel.common_clothes",BODY))),
    HumanoidRosterDefinition("orc_greenfang","Greenfang","orcs_goblins","Orc 11",ORC,(
        _equipped("weapon.battleaxe",MAIN),_equipped("shield.wooden",OFF),
        _equipped("apparel.common_clothes",BODY)),protection=True),
    HumanoidRosterDefinition("orc_bristlejaw","Bristlejaw","orcs_goblins","Orc 04",ORC,(
        _equipped("weapon.club",MAIN),_equipped("apparel.common_clothes",BODY))),
    HumanoidRosterDefinition("orc_longspike","Longspike","orcs_goblins","Orc 05",ORC,(
        _equipped("weapon.shortbow",BOW),_equipped("gear.quiver",BACK),
        _equipped("apparel.common_clothes",BODY))),
    HumanoidRosterDefinition("orc_frostmane","Frostmane","orcs_goblins","Orc 06",ORC_MAGE,(
        _equipped("weapon.quarterstaff",MAIN),_equipped("apparel.robes",BODY)),web=True),
    HumanoidRosterDefinition("orc_brassbrow","Brassbrow","orcs_goblins","Orc 07",ORC_MAGE,(
        _equipped("apparel.robes",BODY),),web=True),
    HumanoidRosterDefinition("orc_blackplate","Blackplate","orcs_goblins","Orc 08",ORC,(
        _equipped("weapon.scimitar",MAIN),_equipped("shield.shield",OFF),
        _equipped("apparel.common_clothes",BODY)),protection=True),
    HumanoidRosterDefinition("orc_mudrunner","Mudrunner","orcs_goblins","Orc 10",ORC,(
        _equipped("weapon.mace",MAIN),_equipped("weapon.handaxe",OFF),
        _equipped("apparel.common_clothes",BODY)),attacks=((MAIN,1),(OFF,1))),
    HumanoidRosterDefinition("orc_ironjaw","Ironjaw","orcs_goblins","Orc 12",ORC,(
        _equipped("weapon.scimitar",MAIN),_equipped("weapon.scimitar",OFF),
        _equipped("apparel.common_clothes",BODY))),
    HumanoidRosterDefinition("enemy_bellringer","The Bellringer","enemy","1Hammer",GLADIATOR,(
        _equipped("weapon.maul",MAIN),_equipped("armor.half_plate",BODY),
        _equipped("apparel.iron_helmet",BodyPart.HEAD),_equipped("apparel.gauntlets",BodyPart.HANDS)),
        attacks=((MAIN,3),)),
    HumanoidRosterDefinition("enemy_blue_quarrel","Blue Quarrel","enemy","2Shooter",ASSASSIN,(
        _equipped("weapon.musket",BOW),_equipped("armor.half_plate",BODY),
        _equipped("gear.warden_pack",BACK),_equipped("apparel.iron_helmet",BodyPart.HEAD),*_POISON)),
    HumanoidRosterDefinition("enemy_gateplate","Gateplate","enemy","3Footsoldier",GLADIATOR,(
        _equipped("weapon.longsword",MAIN),_equipped("shield.shield",OFF),
        _equipped("armor.plate",BODY),_equipped("apparel.iron_helmet",BodyPart.HEAD)),
        attacks=((MAIN,3),),shield_bash=True,protection=True),
    HumanoidRosterDefinition("enemy_blue_twinblade","Blue Twinblade Poisoner","enemy","4Assassin",ASSASSIN,(
        _equipped("weapon.shortsword",MAIN),_equipped("weapon.shortsword",OFF),
        _equipped("armor.studded_leather",BODY),_equipped("apparel.cloth_hood",BodyPart.HEAD),*_POISON),
        attacks=((MAIN,1),(OFF,1))),
    HumanoidRosterDefinition("enemy_gold_knuckle","Gold-knuckle Breaker","enemy","5Bruiser",TRAINED,(
        _equipped("armor.half_plate",BODY),_equipped("apparel.gauntlets",BodyPart.HANDS)),
        attacks=((MAIN,3),),trained_die=8),
    HumanoidRosterDefinition("enemy_reliquary","Reliquary","enemy","6Crusader",KNIGHT,(
        _equipped("weapon.greatsword",MAIN),_equipped("armor.plate",BODY),
        _equipped("apparel.cloak",BodyPart.CLOAK)),attacks=((MAIN,2),)),
    HumanoidRosterDefinition("enemy_far_eye","Far-Eye","enemy","7Sniper",ASSASSIN,(
        _equipped("weapon.musket",BOW),_equipped("armor.studded_leather",BODY),
        _equipped("apparel.cloth_hood",BodyPart.HEAD),*_POISON)),
    HumanoidRosterDefinition("enemy_dockwall","The Dockwall","enemy","8Brawler",TRAINED,(
        _equipped("apparel.common_clothes",BODY),),attacks=((MAIN,3),),trained_die=8),
    HumanoidRosterDefinition("enemy_magister_nine","Magister Nine","enemy","9Commander",ARCHMAGE,(
        _equipped("apparel.common_clothes",BODY),_equipped("apparel.cloth_hood",BodyPart.HEAD))),
    HumanoidRosterDefinition("enemy_pale_ember","Pale Ember","enemy","10Caster",MAGE,(
        _equipped("weapon.quarterstaff",MAIN),_equipped("apparel.robes",BODY))),
    HumanoidRosterDefinition("enemy_arcane_sentinel","Violet Static","enemy","11Arcane elemental",SENTINEL,(
        CreaturePossessionGrant("weapon.creature.arcane_sentinel_slam",CreaturePossessionDisposition.INTRINSIC,MAIN),
        CreaturePossessionGrant("armor.creature.arcane_sentinel_natural",CreaturePossessionDisposition.INTRINSIC,BODY)),
        attacks=((MAIN,2),)),
    HumanoidRosterDefinition("enemy_bronze_watch","Bronze Watch","enemy","12Guard",GLADIATOR,(
        _equipped("weapon.spear",MAIN),_equipped("armor.half_plate",BODY),
        _equipped("apparel.iron_helmet",BodyPart.HEAD)),attacks=((MAIN,3),)),
    HumanoidRosterDefinition("barbarian_gatebreaker","Cleaver Gatebreaker","barbarian","1Ogre",OGRE,(
        _equipped("weapon.maul",MAIN),_equipped("apparel.common_clothes",BODY))),
    HumanoidRosterDefinition("barbarian_cinderplate","Cinderplate Executioner","barbarian","2Golem",GLADIATOR,(
        _equipped("weapon.roster.ember_greatsword",MAIN),_equipped("armor.plate",BODY),
        _equipped("apparel.iron_helmet",BodyPart.HEAD)),attacks=((MAIN,3),),innate_burning_hands=True),
    HumanoidRosterDefinition("barbarian_saffron_ward","Saffron Axe Ward","barbarian","3Nomad",CAPTAIN,(
        _equipped("weapon.battleaxe",MAIN),_equipped("shield.shield",OFF),
        _equipped("armor.scale_mail",BODY)),attacks=((MAIN,2),)),
    HumanoidRosterDefinition("barbarian_red_rage","Red-Rage Twinblade","barbarian","4Berserker",VETERAN,(
        _equipped("weapon.longsword",MAIN),_equipped("weapon.shortsword",OFF),
        _equipped("apparel.common_clothes",BODY)),attacks=((MAIN,2),(OFF,1))),
    HumanoidRosterDefinition("barbarian_farshot","Farshot Pathfinder","barbarian","5BarbArcher",VETERAN,(
        _equipped("weapon.longbow",BOW),_equipped("gear.wayfarer_pack",BACK),
        _equipped("apparel.common_clothes",BODY)),attacks=((BOW,2),)),
    HumanoidRosterDefinition("barbarian_stonejaw","Stonejaw Reaver","barbarian","6Barbarian",BERSERKER,(
        _equipped("weapon.greataxe",MAIN),_equipped("apparel.common_clothes",BODY))),
    HumanoidRosterDefinition("barbarian_windmark","Windmark Bowman","barbarian","7BowMan",VETERAN,(
        _equipped("weapon.longbow",BOW),_equipped("gear.ember_quiver",BACK),
        _equipped("armor.half_plate",BODY),_equipped("apparel.iron_helmet",BodyPart.HEAD)),attacks=((BOW,2),)),
    HumanoidRosterDefinition("barbarian_venom_ritualist","Venom Sword Ritualist","barbarian","8Witchdoctor",CAPTAIN,(
        _equipped("weapon.roster.silver_longsword",MAIN),_equipped("shield.shield",OFF),
        _equipped("armor.leather",BODY),_equipped("apparel.cloth_hood",BodyPart.HEAD),
        _inventory("consumable.weapon_coat.basic_poison",2)),
        attacks=((MAIN,2),)),
    HumanoidRosterDefinition("barbarian_sun_ring","Sun-ring Ember Shaman","barbarian","9Shaman",DRUID,(
        _equipped("weapon.quarterstaff",MAIN),_equipped("apparel.common_clothes",BODY))),
    HumanoidRosterDefinition("character_whiteplate","Whiteplate Dueling Officer","character","1Knight",KNIGHT,(
        _equipped("weapon.longsword",MAIN),_equipped("shield.shield",OFF),_equipped("armor.plate",BODY),
        _equipped("apparel.iron_helmet",BodyPart.HEAD)),attacks=((MAIN,2),)),
    HumanoidRosterDefinition("character_briarline","Briarline Archer","character","2Archer",VETERAN,(
        _equipped("weapon.longbow",BOW),_equipped("gear.quiver",BACK),
        _equipped("apparel.common_clothes",BODY)),attacks=((BOW,2),)),
    HumanoidRosterDefinition("character_golden_orbit","Golden-orbit Pyromancer","character","3Wizard",MAGE,(
        _equipped("apparel.robes",BODY),),burning_hands=True),
    HumanoidRosterDefinition("character_gilded_ward","Gilded Ward Champion","character","4Paladin",KNIGHT,(
        _equipped("weapon.mace",MAIN),_equipped("shield.shield",OFF),_equipped("armor.plate",BODY)),
        attacks=((MAIN,2),),protection=True,divine_eminence=True),
    HumanoidRosterDefinition("character_white_streak","White-streak Ambusher","character","5CamoArcher",ASSASSIN,(
        _equipped("weapon.longbow",BOW),_equipped("gear.quiver",BACK),
        _equipped("armor.studded_leather",BODY),_equipped("apparel.cloth_hood",BodyPart.HEAD),*_POISON),
        attacks=((BOW,2),)),
    HumanoidRosterDefinition("character_azure_current","Azure Currentbinder","character","6Mage",MAGE,(
        _equipped("apparel.robes",BODY),),web=True),
    HumanoidRosterDefinition("character_violet_oathbreaker","Violet Oathbreaker","character","7DeathKnight",GLADIATOR,(
        _equipped("weapon.roster.psychic_longsword_greater",MAIN),_equipped("shield.shield",OFF),
        _equipped("armor.plate",BODY),_equipped("apparel.iron_helmet",BodyPart.HEAD)),
        attacks=((MAIN,3),),shield_bash=True),
    HumanoidRosterDefinition("character_hex_sovereign","Magenta Hex Sovereign","character","8DarkLord",MAGE,(
        _equipped("apparel.robes",BODY),),slow=True),
    HumanoidRosterDefinition("character_blue_spark","Blue-spark Arc Marksman","character","9Longbow",VETERAN,(
        _equipped("weapon.longbow",BOW),_equipped("gear.quiver",BACK),
        _equipped("armor.half_plate",BODY)),attacks=((BOW,2),)),
)


HUMANOID_MULTIATTACK_DECLARATIONS = tuple(
    declare_multiattack_configuration(content_id=f"action.monster.multiattack.{row.key}",
        display_name=f"{row.name} Multiattack",icon_key="ui.filter-attacks",
        source_anchor=f"Accepted roster {row.pack}/{row.source_variant}; {row.foundation.source}",
        steps=row.attacks,sort_order=index,pack_id="content.neurodragon")
    for index,row in enumerate(HUMANOID_ROSTER_DEFINITIONS) if row.attacks
)
_MULTIATTACK_BY_KEY = MappingProxyType({
    row.ref.content_id.removeprefix("action.monster.multiattack."):row
    for row in HUMANOID_MULTIATTACK_DECLARATIONS
})


def _selected_spells(row: HumanoidRosterDefinition) -> tuple[type[SpellAction], ...]:
    # Web replaces unsupported source Suggestion; Burning Hands replaces
    # unsupported Detect Magic. Slow replaces the source Fly selection.
    spells = row.foundation.spells
    if row.web:
        spells = (*spells,Web)
    if row.burning_hands:
        spells = (*spells,BurningHands)
    if row.slow:
        spells = (*(spell for spell in spells if spell is not Fly),Slow)
    return spells


def build_roster_humanoid(context: CreatureBuildContext, row: HumanoidRosterDefinition) -> Entity:
    profile = row.foundation
    slots = dict(profile.slots)
    if row.divine_eminence:
        slots = {1:1}
    entity = create_creature_entity(context=context,description=f"{row.name}; {profile.source} adaptation.",
        abilities=profile.abilities,hit_die_value=profile.hit_die,hit_die_count=profile.hit_dice,
        hit_points=profile.hp,proficiency_bonus=profile.proficiency,skills={skill:True for skill in profile.skills},
        creature_type=profile.creature_type,size=profile.size,movement=profile.speed,
        darkvision=profile.darkvision,save_proficiencies=profile.saves,languages=profile.languages,
        spellcasting_ability=profile.casting_ability,spell_slots=slots,
        resistances=(DamageType.POISON,) if profile.assassin else (),
        immunities=(DamageType.POISON,) if profile is SENTINEL else (),
        nonmagical_attack_resistances=(DamageType.BLUDGEONING,DamageType.PIERCING,DamageType.SLASHING)
            if profile is SENTINEL else ())
    entity.appearance.visual_scale = 1.0
    if profile is not SENTINEL:
        install_body_response(entity,BLOOD_BODY_RESPONSE)
    for skill in profile.expertise:
        entity.skill_set.get_skill(skill).set_expertise(True)
    apply_creature_possessions(entity,row.possessions,possession_mode=context.possession_mode)
    if profile.aggressive:
        register_aggressive(entity)
    if profile.brave:
        register_brave(entity)
    if profile.brute:
        register_brute(entity)
    if profile.parry:
        register_parry(entity,ac_bonus=profile.parry)
    if profile.leadership:
        register_leadership(entity)
    if profile.reckless:
        register_reckless(entity)
    if row.protection:
        handler = create_protection_handler(entity.uuid)
        handler.behavior_binding = BehaviorBinding(behavior_id=PROTECTION_REACTION_DECLARATION.ref.content_id,
            provided_by_id=context.requested_ref.content_id,origin_root_id=context.requested_ref.content_id,
            runtime_owner_uuid=entity.uuid)
        entity.add_event_handler(handler)
    if any(slot is OFF for slot,count in row.attacks):
        add_modifier(entity.equipment.off_hand_melee_ability_bonus,Channel.SELF_CONTEXTUAL,Kind.VALUE,
            ContextualNumericalModifier(name="Two-Weapon Fighting",source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,callable=twf_off_hand_melee_ability_bonus))
    if profile.assassin:
        register_assassinate(entity)
        register_sneak_attack(entity,dice_numbers=4)
        entity.add_condition(EvasionFeature(source_entity_uuid=entity.uuid,target_entity_uuid=entity.uuid))
    if row.divine_eminence:
        register_divine_eminence(entity)
    if row.trained_die is not None:
        entity.equipment.unarmed_damage_dice = row.trained_die
        entity.equipment.unarmed_dice_numbers = 1
        entity.equipment.unarmed_damage_type = DamageType.BLUDGEONING
    if row.attacks:
        declaration = _MULTIATTACK_BY_KEY[row.key]
        if row.shield_bash:
            register_shield_bash(entity)
            action = shield_bash_multiattack(entity.uuid,WeaponKind.LONGSWORD)
            action.template = True
            action.name = declaration.descriptor.display_name
            action.configured_action_ref = declaration.ref
            entity.register_action(action)
        else:
            register_multiattack(entity,declaration.descriptor.display_name,row.attacks,
                configured_action_ref=declaration.ref)
    for spell in _selected_spells(row):
        register_spell(entity,spell,caster_level=profile.caster_level)
    if profile.shield_spell:
        register_shield_reaction(entity)
    if profile.counterspell:
        register_counterspell_reaction(entity)
    if row.innate_burning_hands:
        grant_innate_spell(entity,BurningHands,cast_rank=1,daily_uses=1)
    if profile is ARCHMAGE:
        grant_innate_spell(entity,Invisibility,caster_level=18,cast_rank=2,ability="intelligence")
        entity.add_condition(MagicResistance(source_entity_uuid=entity.uuid,target_entity_uuid=entity.uuid))
        entity.add_condition(SpellDamageResistance(source_entity_uuid=entity.uuid,target_entity_uuid=entity.uuid))
    if profile is SENTINEL:
        entity.add_condition_immunity("Poisoned",immunity_name="Elemental body")
        entity.add_condition_immunity("Exhaustion",immunity_name="Elemental body")
    return entity


def _declare(row: HumanoidRosterDefinition) -> ContentDeclaration:
    profile = row.foundation
    def factory(raw_context: object,parameters: HumanoidRosterParameters) -> Entity:
        return build_roster_humanoid(CreatureBuildContext.model_validate(raw_context),row)
    factory.__name__ = factory.__qualname__ = f"build_{row.key}"
    dependencies = [ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,target_ref=item.ref)
        for item in CORE_STANDARD_ACTION_DECLARATIONS]
    features = (
        (profile.brave,BraveFeature),(profile.brute,BruteFeature),(bool(profile.parry),ParryFeature),
        (profile.assassin,AssassinateFeature),(profile.assassin,SneakAttackFeature),
        (profile.assassin,EvasionFeature),
        (row.shield_bash,HitSaveRiderFeature),(profile is ARCHMAGE,MagicResistance),
        (profile is ARCHMAGE,SpellDamageResistance),
    )
    dependencies.extend(ContentDependency(relation=ContentDependencyRelation.GRANTS_FEATURE,
        target_ref=CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[feature].ref)
        for enabled,feature in features if enabled)
    actions = ((profile.aggressive,AggressiveMoveAction),(profile.leadership,LeadershipAction),
        (profile.reckless,RecklessAttack),(bool(row.attacks),MultiattackAction),
        (row.divine_eminence,DivineEminenceAction),(row.shield_bash,ShieldBash))
    dependencies.extend(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,
        target_ref=ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[action].ref)
        for enabled,action in actions if enabled)
    if row.attacks:
        dependencies.append(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=_MULTIATTACK_BY_KEY[row.key].ref))
    spells = (*_selected_spells(row), *((BurningHands,) if row.innate_burning_hands else ()),
        *((Invisibility,) if profile is ARCHMAGE else ()))
    dependencies.extend(ContentDependency(relation=ContentDependencyRelation.GRANTS_SPELL,
        target_ref=SPELL_CONTENT_DECLARATIONS_BY_CLASS[spell].ref) for spell in spells)
    for enabled,reaction in ((profile.shield_spell,SHIELD_REACTION_DECLARATION),
                              (profile.counterspell,COUNTERSPELL_REACTION_DECLARATION),
                              (row.protection,PROTECTION_REACTION_DECLARATION)):
        if enabled:
            dependencies.append(ContentDependency(relation=ContentDependencyRelation.INSTALLS_HANDLER,
                target_ref=reaction.ref))
    declared = creature_factory(pack_id="content.neurodragon",content_id=f"creature.{row.key}",version=1,
        parameters=HumanoidRosterParameters,
        descriptor=ContentDescriptorSpec(display_name=row.name,
            description=f"{row.pack}/{row.source_variant}; adapted {profile.source}. CR uncalibrated.",
            tags=("creature","npc","roster",profile.creature_type.value.lower()),
            visibility=ContentVisibility.PUBLIC,presentation=ContentPresentation(
                portrait_key=f"creature.{row.key}",visual_variant_key=row.key,ui_group="creatures.neurodragon")),
        provenance=ContentProvenance(primary_source_id="neurodragon.original_b2b3930",
            source_anchor=f"Accepted roster {row.pack}/{row.source_variant}; {profile.source}; 2026-10-18",
            relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,adapted_from_source_id="wotc.srd_5_1_cc",
            fidelity=ContentFidelity.PARTIAL,review_status=ContentReviewStatus.REVIEWED,
            notes="Native NPC composition; finite supplies; unsupported spells and retained kit changes in family evidence. CR uncalibrated."),
        dependencies=tuple(dependencies))(factory)
    return get_content_declaration(declared)


HUMANOID_ROSTER_DECLARATIONS = tuple(_declare(row) for row in HUMANOID_ROSTER_DEFINITIONS)
HUMANOID_ROSTER_RECIPES_BY_ID = MappingProxyType({
    row.ref.content_id.removeprefix("creature."):ContentRecipe.create(ref=row.ref,parameters={})
    for row in HUMANOID_ROSTER_DECLARATIONS
})
