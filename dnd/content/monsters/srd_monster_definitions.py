"""Cold renderer-independent definitions for the migrated SRD roster."""

from types import MappingProxyType
from typing import Mapping

from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.content.monsters.monster_definitions import (
    MonsterDefinition,
    MonsterHitDice,
    MonsterMultiattack,
    MonsterSense,
    MonsterSkillTraining,
)
from dnd.types.abilities import AbilityName, SkillName
from dnd.types.creatures import CreatureType, Size
from dnd.types.damage import DamageType
from dnd.types.equipment import BodyPart, WeaponSlot
from dnd.types.senses import SensesType


def _abilities(
    strength: int,
    dexterity: int,
    constitution: int,
    intelligence: int,
    wisdom: int,
    charisma: int,
) -> tuple[tuple[AbilityName, int], ...]:
    return tuple(zip(
        tuple(AbilityName),
        (
            strength,
            dexterity,
            constitution,
            intelligence,
            wisdom,
            charisma,
        ),
        strict=True,
    ))


def _skills(*skills: SkillName) -> tuple[MonsterSkillTraining, ...]:
    return tuple(MonsterSkillTraining(skill) for skill in skills)


def _body(
    anatomy: str,
    *,
    lineage: str,
    role: str,
    state: str = "living",
) -> tuple[tuple[str, str], ...]:
    return (
        ("anatomy", anatomy),
        ("lineage", lineage),
        ("role", role),
        ("state", state),
    )


def _equipped(
    item_id: str,
    slot: BodyPart | WeaponSlot,
) -> ItemLoadoutEntry:
    return ItemLoadoutEntry(item_id, equipment_slot=slot)


_DARKVISION = (MonsterSense(SensesType.DARKVISION, 60),)

_LEATHER_BOOTS = (
    _equipped("apparel.leather_boots", BodyPart.FEET),
)
_DARK_BOOTS = (
    _equipped("apparel.leather_boots.dark", BodyPart.FEET),
)
_ARMORED_BOOTS = (
    _equipped("apparel.armored_boots", BodyPart.FEET),
)

SRD_CONFIGURED_WARDROBE_LOADOUTS: Mapping[
    str,
    tuple[ItemLoadoutEntry, ...],
] = MappingProxyType({
    "creature.commoner.configured": (
        _equipped("apparel.common_clothes.farmhand_tunic", BodyPart.BODY),
        _equipped("apparel.leather_shoes.brown", BodyPart.FEET),
    ),
    "creature.bandit.configured": _DARK_BOOTS,
    "creature.cultist.configured": _DARK_BOOTS,
    "creature.guard.configured": _LEATHER_BOOTS,
    "creature.tribal_warrior.configured": _LEATHER_BOOTS,
    "creature.kobold.configured": (
        _equipped("apparel.common_clothes.peasant_rags", BodyPart.BODY),
        _equipped("apparel.sandals.rope", BodyPart.FEET),
    ),
    "creature.acolyte.configured": (
        _equipped("apparel.robes.acolyte_vestments", BodyPart.BODY),
        _equipped("apparel.sandals.rope", BodyPart.FEET),
    ),
    "creature.scout.configured": (
        _equipped("apparel.leather_boots.brown", BodyPart.FEET),
    ),
    "creature.thug.configured": _LEATHER_BOOTS,
    "creature.spy.configured": (
        _equipped("apparel.travelers_clothes.thief_garb", BodyPart.BODY),
        _equipped("apparel.leather_boots.dark", BodyPart.FEET),
    ),
    "creature.berserker.configured": _LEATHER_BOOTS,
    "creature.bandit_captain.configured": _DARK_BOOTS,
    "creature.priest.configured": _LEATHER_BOOTS,
    "creature.cult_fanatic.configured": _DARK_BOOTS,
    "creature.knight.configured": _ARMORED_BOOTS,
    "creature.veteran.configured": _ARMORED_BOOTS,
    "creature.mage.configured": (
        _equipped("apparel.robes.wizard", BodyPart.BODY),
        _equipped("apparel.cloth_shoes.blue", BodyPart.FEET),
    ),
    "creature.orc.configured": _LEATHER_BOOTS,
    "creature.hobgoblin.configured": _ARMORED_BOOTS,
    "creature.bugbear.configured": _DARK_BOOTS,
    "creature.gnoll.configured": _LEATHER_BOOTS,
})


_DEFINITIONS = (
    MonsterDefinition(
        monster_id="creature.commoner",
        name="Commoner",
        description="A noncombatant pressed into danger.",
        abilities=_abilities(10, 10, 10, 10, 10, 10),
        hit_dice=(MonsterHitDice(8, 1),),
        proficiency_bonus=2,
        challenge_rating="0",
        role_tags=("civilian", "melee"),
        body_semantics=_body("humanoid", lineage="unspecified", role="civilian"),
        default_loadout=(
            _equipped("weapon.club", WeaponSlot.MELEE_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.bandit",
        name="Bandit",
        description="A lightly armored raider with melee and crossbow pressure.",
        abilities=_abilities(11, 12, 12, 10, 10, 10),
        hit_dice=(MonsterHitDice(8, 2),),
        proficiency_bonus=2,
        challenge_rating="1/8",
        role_tags=("humanoid", "melee", "ranged"),
        body_semantics=_body("humanoid", lineage="unspecified", role="raider"),
        default_loadout=(
            _equipped("armor.leather", BodyPart.BODY),
            _equipped("weapon.scimitar", WeaponSlot.MELEE_MAIN),
            _equipped("weapon.light_crossbow", WeaponSlot.RANGED_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.cultist",
        name="Cultist",
        description="A zealot with a scimitar and social skill pressure.",
        abilities=_abilities(11, 12, 10, 10, 11, 10),
        hit_dice=(MonsterHitDice(8, 2),),
        proficiency_bonus=2,
        challenge_rating="1/8",
        role_tags=("humanoid", "melee", "social"),
        skills=_skills(SkillName.DECEPTION, SkillName.RELIGION),
        trait_ids=("trait.srd.dark_devotion",),
        body_semantics=_body("humanoid", lineage="unspecified", role="cultist"),
        default_loadout=(
            _equipped("armor.leather", BodyPart.BODY),
            _equipped("weapon.scimitar", WeaponSlot.MELEE_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.guard",
        name="Guard",
        description="A defensive sentry with shielded spear pressure.",
        abilities=_abilities(13, 12, 12, 10, 11, 10),
        hit_dice=(MonsterHitDice(8, 2),),
        proficiency_bonus=2,
        challenge_rating="1/8",
        role_tags=("defender", "humanoid", "shield"),
        skills=_skills(SkillName.PERCEPTION),
        body_semantics=_body("humanoid", lineage="unspecified", role="guard"),
        default_loadout=(
            _equipped("armor.chain_shirt", BodyPart.BODY),
            _equipped("weapon.spear", WeaponSlot.MELEE_MAIN),
            _equipped("shield.shield", WeaponSlot.MELEE_OFF),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.tribal_warrior",
        name="Tribal Warrior",
        description="A light skirmisher that pressures pack-melee scenarios.",
        abilities=_abilities(13, 11, 12, 8, 11, 8),
        hit_dice=(MonsterHitDice(8, 2),),
        proficiency_bonus=2,
        challenge_rating="1/8",
        role_tags=("humanoid", "melee", "pack"),
        trait_ids=("trait.srd.pack_tactics",),
        body_semantics=_body(
            "humanoid",
            lineage="unspecified",
            role="tribal_warrior",
        ),
        default_loadout=(
            _equipped("armor.hide", BodyPart.BODY),
            _equipped("weapon.spear", WeaponSlot.MELEE_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.kobold",
        name="Kobold",
        description="A fragile darkvision skirmisher.",
        abilities=_abilities(7, 15, 9, 8, 7, 8),
        hit_dice=(MonsterHitDice(6, 2),),
        proficiency_bonus=2,
        challenge_rating="1/8",
        role_tags=("darkvision", "humanoid", "ranged", "small"),
        size=Size.SMALL,
        weight=35,
        senses=_DARKVISION,
        trait_ids=(
            "trait.srd.pack_tactics",
            "trait.srd.sunlight_sensitivity",
        ),
        body_semantics=_body("humanoid", lineage="kobold", role="skirmisher"),
        default_loadout=(
            _equipped("weapon.dagger", WeaponSlot.MELEE_MAIN),
            _equipped(
                "weapon.creature.kobold_sling",
                WeaponSlot.RANGED_MAIN,
            ),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.acolyte",
        name="Acolyte",
        description="A junior divine caster useful for low-CR support tests.",
        abilities=_abilities(10, 10, 10, 10, 14, 11),
        hit_dice=(MonsterHitDice(8, 2),),
        proficiency_bonus=2,
        challenge_rating="1/4",
        role_tags=("caster", "humanoid", "support"),
        skills=_skills(SkillName.MEDICINE, SkillName.RELIGION),
        spellcasting_ability=AbilityName.WISDOM,
        spellcaster_level=1,
        spell_slots=((1, 3),),
        spell_ids=(
            "spell.sacred_flame",
            "spell.bless",
            "spell.cure_wounds",
        ),
        body_semantics=_body("humanoid", lineage="unspecified", role="acolyte"),
        default_loadout=(
            _equipped("weapon.club", WeaponSlot.MELEE_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.scout",
        name="Scout",
        description="A perception-heavy ranged scout.",
        abilities=_abilities(11, 14, 12, 11, 13, 11),
        hit_dice=(MonsterHitDice(8, 3),),
        proficiency_bonus=2,
        challenge_rating="1/2",
        role_tags=("humanoid", "perception", "ranged"),
        skills=_skills(
            SkillName.NATURE,
            SkillName.PERCEPTION,
            SkillName.STEALTH,
            SkillName.SURVIVAL,
        ),
        trait_ids=("trait.srd.keen_hearing_and_sight",),
        multiattacks=(
            MonsterMultiattack(
                "action.monster.multiattack.scout.shortsword",
                "Scout Multiattack: Shortsword",
                ((WeaponSlot.MELEE_MAIN, 2),),
            ),
            MonsterMultiattack(
                "action.monster.multiattack.scout.longbow",
                "Scout Multiattack: Longbow",
                ((WeaponSlot.RANGED_MAIN, 2),),
            ),
        ),
        body_semantics=_body("humanoid", lineage="unspecified", role="scout"),
        default_loadout=(
            _equipped("armor.leather", BodyPart.BODY),
            _equipped("weapon.shortsword", WeaponSlot.MELEE_MAIN),
            _equipped("weapon.longbow", WeaponSlot.RANGED_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.thug",
        name="Thug",
        description="A durable low-CR bruiser with crossbow fallback.",
        abilities=_abilities(15, 11, 14, 10, 10, 11),
        hit_dice=(MonsterHitDice(8, 5),),
        proficiency_bonus=2,
        challenge_rating="1/2",
        role_tags=("bruiser", "humanoid", "ranged"),
        skills=_skills(SkillName.INTIMIDATION),
        trait_ids=("trait.srd.pack_tactics",),
        multiattacks=(
            MonsterMultiattack(
                "action.monster.multiattack.thug",
                "Thug Multiattack",
                ((WeaponSlot.MELEE_MAIN, 2),),
            ),
        ),
        body_semantics=_body("humanoid", lineage="unspecified", role="thug"),
        default_loadout=(
            _equipped("armor.leather", BodyPart.BODY),
            _equipped("weapon.mace", WeaponSlot.MELEE_MAIN),
            _equipped("weapon.heavy_crossbow", WeaponSlot.RANGED_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.spy",
        name="Spy",
        description="A mobile infiltrator with shortsword and hand-crossbow pressure.",
        abilities=_abilities(10, 15, 10, 12, 14, 16),
        hit_dice=(MonsterHitDice(8, 6),),
        proficiency_bonus=2,
        challenge_rating="1",
        role_tags=("humanoid", "ranged", "skirmisher"),
        skills=_skills(
            SkillName.DECEPTION,
            SkillName.INSIGHT,
            SkillName.INVESTIGATION,
            SkillName.PERCEPTION,
            SkillName.PERSUASION,
            SkillName.SLEIGHT_OF_HAND,
            SkillName.STEALTH,
        ),
        trait_ids=(
            "trait.srd.cunning_action",
            "trait.srd.sneak_attack",
        ),
        multiattacks=(
            MonsterMultiattack(
                "action.monster.multiattack.spy",
                "Spy Multiattack",
                ((WeaponSlot.MELEE_MAIN, 2),),
            ),
        ),
        body_semantics=_body("humanoid", lineage="unspecified", role="spy"),
        default_loadout=(
            _equipped("weapon.shortsword", WeaponSlot.MELEE_MAIN),
            _equipped(
                "weapon.creature.spy_hand_crossbow",
                WeaponSlot.RANGED_MAIN,
            ),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.berserker",
        name="Berserker",
        description="A high-HP axe charger for melee pressure tests.",
        abilities=_abilities(16, 12, 17, 9, 11, 9),
        hit_dice=(MonsterHitDice(8, 9),),
        proficiency_bonus=2,
        challenge_rating="2",
        role_tags=("bruiser", "humanoid", "melee"),
        trait_ids=("trait.srd.reckless",),
        body_semantics=_body(
            "humanoid",
            lineage="unspecified",
            role="berserker",
        ),
        default_loadout=(
            _equipped("armor.hide", BodyPart.BODY),
            _equipped("weapon.greataxe", WeaponSlot.MELEE_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.bandit_captain",
        name="Bandit Captain",
        description="A durable duelist leader with melee and thrown-dagger pressure.",
        abilities=_abilities(15, 16, 14, 14, 11, 14),
        hit_dice=(MonsterHitDice(8, 10),),
        proficiency_bonus=2,
        challenge_rating="2",
        role_tags=("duelist", "humanoid", "leader"),
        skills=_skills(SkillName.ATHLETICS, SkillName.DECEPTION),
        trait_ids=("trait.srd.parry",),
        multiattacks=(
            MonsterMultiattack(
                "action.monster.multiattack.bandit_captain.melee",
                "Bandit Captain Multiattack: Melee",
                (
                    (WeaponSlot.MELEE_MAIN, 2),
                    (WeaponSlot.MELEE_OFF, 1),
                ),
            ),
            MonsterMultiattack(
                "action.monster.multiattack.bandit_captain.ranged",
                "Bandit Captain Multiattack: Ranged",
                ((WeaponSlot.RANGED_MAIN, 2),),
            ),
        ),
        body_semantics=_body(
            "humanoid",
            lineage="unspecified",
            role="bandit_captain",
        ),
        default_loadout=(
            _equipped("armor.studded_leather", BodyPart.BODY),
            _equipped("weapon.scimitar", WeaponSlot.MELEE_MAIN),
            _equipped("weapon.dagger", WeaponSlot.MELEE_OFF),
            _equipped(
                "weapon.creature.bandit_captain_thrown_dagger",
                WeaponSlot.RANGED_MAIN,
            ),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.priest",
        name="Priest",
        description="A divine support caster with healing, radiant pressure, and aura options.",
        abilities=_abilities(10, 10, 12, 13, 16, 13),
        hit_dice=(MonsterHitDice(8, 5),),
        proficiency_bonus=2,
        challenge_rating="2",
        role_tags=("caster", "healing", "humanoid", "support"),
        skills=_skills(
            SkillName.MEDICINE,
            SkillName.PERSUASION,
            SkillName.RELIGION,
        ),
        spellcasting_ability=AbilityName.WISDOM,
        spellcaster_level=5,
        spell_slots=((1, 4), (2, 3), (3, 2)),
        spell_ids=(
            "spell.sacred_flame",
            "spell.cure_wounds",
            "spell.guiding_bolt",
            "spell.sanctuary",
            "spell.lesser_restoration",
            "spell.spirit_guardians",
        ),
        trait_ids=("trait.srd.divine_eminence",),
        body_semantics=_body("humanoid", lineage="unspecified", role="priest"),
        default_loadout=(
            _equipped("armor.chain_shirt", BodyPart.BODY),
            _equipped("weapon.mace", WeaponSlot.MELEE_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.cult_fanatic",
        name="Cult Fanatic",
        description="A low-mid control caster with dagger fallback.",
        abilities=_abilities(11, 14, 12, 10, 13, 14),
        hit_dice=(MonsterHitDice(8, 6),),
        proficiency_bonus=2,
        challenge_rating="2",
        role_tags=("caster", "control", "humanoid"),
        skills=_skills(
            SkillName.DECEPTION,
            SkillName.PERSUASION,
            SkillName.RELIGION,
        ),
        spellcasting_ability=AbilityName.WISDOM,
        spellcaster_level=4,
        spell_slots=((1, 4), (2, 3)),
        spell_ids=(
            "spell.sacred_flame",
            "spell.command",
            "spell.inflict_wounds",
            "spell.shield_of_faith",
            "spell.hold_person",
        ),
        trait_ids=("trait.srd.dark_devotion",),
        multiattacks=(
            MonsterMultiattack(
                "action.monster.multiattack.cult_fanatic",
                "Cult Fanatic Multiattack",
                ((WeaponSlot.MELEE_MAIN, 2),),
            ),
        ),
        body_semantics=_body(
            "humanoid",
            lineage="unspecified",
            role="cult_fanatic",
        ),
        default_loadout=(
            _equipped("armor.leather", BodyPart.BODY),
            _equipped("weapon.dagger", WeaponSlot.MELEE_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.knight",
        name="Knight",
        description="A plate-armored heavy melee combatant.",
        abilities=_abilities(16, 11, 14, 11, 11, 15),
        hit_dice=(MonsterHitDice(8, 8),),
        proficiency_bonus=2,
        challenge_rating="3",
        role_tags=("elite", "heavy-armor", "humanoid"),
        trait_ids=(
            "trait.srd.brave",
            "trait.srd.leadership",
            "trait.srd.parry",
        ),
        multiattacks=(
            MonsterMultiattack(
                "action.monster.multiattack.knight",
                "Knight Multiattack",
                ((WeaponSlot.MELEE_MAIN, 2),),
            ),
        ),
        body_semantics=_body("humanoid", lineage="unspecified", role="knight"),
        default_loadout=(
            _equipped("armor.plate", BodyPart.BODY),
            _equipped("weapon.greatsword", WeaponSlot.MELEE_MAIN),
            _equipped("weapon.heavy_crossbow", WeaponSlot.RANGED_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.veteran",
        name="Veteran",
        description="A disciplined martial enemy with melee and heavy-crossbow modes.",
        abilities=_abilities(16, 13, 14, 10, 11, 10),
        hit_dice=(MonsterHitDice(8, 9),),
        proficiency_bonus=2,
        challenge_rating="3",
        role_tags=("elite", "humanoid", "weapon-modes"),
        skills=_skills(SkillName.ATHLETICS, SkillName.PERCEPTION),
        multiattacks=(
            MonsterMultiattack(
                "action.monster.multiattack.veteran.melee",
                "Veteran Multiattack: Melee",
                (
                    (WeaponSlot.MELEE_MAIN, 2),
                    (WeaponSlot.MELEE_OFF, 1),
                ),
            ),
            MonsterMultiattack(
                "action.monster.multiattack.veteran.ranged",
                "Veteran Multiattack: Ranged",
                ((WeaponSlot.RANGED_MAIN, 2),),
            ),
        ),
        body_semantics=_body(
            "humanoid",
            lineage="unspecified",
            role="veteran",
        ),
        default_loadout=(
            _equipped("armor.splint", BodyPart.BODY),
            _equipped("weapon.longsword", WeaponSlot.MELEE_MAIN),
            _equipped("weapon.shortsword", WeaponSlot.MELEE_OFF),
            _equipped("weapon.heavy_crossbow", WeaponSlot.RANGED_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.mage",
        name="Mage",
        description="A high-slot arcane caster for resource and counterspell pressure.",
        abilities=_abilities(9, 14, 11, 17, 12, 11),
        hit_dice=(MonsterHitDice(8, 9),),
        proficiency_bonus=3,
        challenge_rating="6",
        role_tags=("arcane", "caster", "counterspell", "humanoid"),
        skills=_skills(SkillName.ARCANA, SkillName.HISTORY),
        spellcasting_ability=AbilityName.INTELLIGENCE,
        spellcaster_level=9,
        spell_slots=((1, 4), (2, 3), (3, 3), (4, 3), (5, 1)),
        spell_ids=(
            "spell.fire_bolt",
            "spell.magic_missile",
            "spell.mage_armor",
            "spell.misty_step",
            "spell.fireball",
            "spell.greater_invisibility",
            "spell.ice_storm",
            "spell.cone_of_cold",
        ),
        reaction_ids=("spell.shield", "spell.counterspell"),
        body_semantics=_body("humanoid", lineage="unspecified", role="mage"),
        default_loadout=(
            _equipped("weapon.dagger", WeaponSlot.MELEE_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.orc",
        name="Orc",
        description="A strong darkvision charger with axe and javelin pressure.",
        abilities=_abilities(16, 12, 16, 7, 11, 10),
        hit_dice=(MonsterHitDice(8, 2),),
        proficiency_bonus=2,
        challenge_rating="1/2",
        role_tags=("charger", "darkvision", "humanoid"),
        skills=_skills(SkillName.INTIMIDATION),
        senses=_DARKVISION,
        trait_ids=("trait.srd.aggressive",),
        body_semantics=_body("humanoid", lineage="orc", role="warrior"),
        default_loadout=(
            _equipped("armor.hide", BodyPart.BODY),
            _equipped("weapon.greataxe", WeaponSlot.MELEE_MAIN),
            _equipped(
                "weapon.creature.thrown_javelin",
                WeaponSlot.RANGED_MAIN,
            ),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.hobgoblin",
        name="Hobgoblin",
        description="A heavily armored goblinoid soldier with sword and bow.",
        abilities=_abilities(13, 12, 12, 10, 10, 9),
        hit_dice=(MonsterHitDice(8, 2),),
        proficiency_bonus=2,
        challenge_rating="1/2",
        role_tags=("darkvision", "humanoid", "ranged", "shield"),
        senses=_DARKVISION,
        trait_ids=("trait.srd.martial_advantage",),
        body_semantics=_body("humanoid", lineage="hobgoblin", role="soldier"),
        default_loadout=(
            _equipped("armor.chain_mail", BodyPart.BODY),
            _equipped("weapon.longsword", WeaponSlot.MELEE_MAIN),
            _equipped("shield.shield", WeaponSlot.MELEE_OFF),
            _equipped("weapon.longbow", WeaponSlot.RANGED_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.bugbear",
        name="Bugbear",
        description="A stealthy goblinoid bruiser.",
        abilities=_abilities(15, 14, 13, 8, 11, 9),
        hit_dice=(MonsterHitDice(8, 5),),
        proficiency_bonus=2,
        challenge_rating="1",
        role_tags=("bruiser", "darkvision", "humanoid", "stealth"),
        skills=_skills(SkillName.STEALTH, SkillName.SURVIVAL),
        senses=_DARKVISION,
        trait_ids=(
            "trait.srd.brute",
            "trait.srd.surprise_attack",
        ),
        body_semantics=_body("humanoid", lineage="bugbear", role="bruiser"),
        default_loadout=(
            _equipped("armor.hide", BodyPart.BODY),
            _equipped(
                "weapon.creature.bugbear_morningstar",
                WeaponSlot.MELEE_MAIN,
            ),
            _equipped("shield.shield", WeaponSlot.MELEE_OFF),
            _equipped(
                "weapon.creature.thrown_javelin",
                WeaponSlot.RANGED_MAIN,
            ),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.gnoll",
        name="Gnoll",
        description="A shielded savage with spear and longbow choices.",
        abilities=_abilities(14, 12, 11, 6, 10, 7),
        hit_dice=(MonsterHitDice(8, 5),),
        proficiency_bonus=2,
        challenge_rating="1/2",
        role_tags=("darkvision", "humanoid", "ranged", "shield"),
        senses=_DARKVISION,
        trait_ids=(
            "trait.srd.natural_bite",
            "trait.srd.rampage",
        ),
        body_semantics=_body("humanoid", lineage="gnoll", role="raider"),
        default_loadout=(
            _equipped("armor.hide", BodyPart.BODY),
            _equipped("weapon.spear", WeaponSlot.MELEE_MAIN),
            _equipped("shield.shield", WeaponSlot.MELEE_OFF),
            _equipped("weapon.longbow", WeaponSlot.RANGED_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.ogre",
        name="Ogre",
        description="A large giant with high HP and heavy bludgeoning pressure.",
        abilities=_abilities(19, 8, 16, 5, 7, 7),
        hit_dice=(MonsterHitDice(10, 7),),
        proficiency_bonus=2,
        challenge_rating="2",
        role_tags=("bruiser", "darkvision", "giant", "large"),
        creature_type=CreatureType.GIANT,
        size=Size.LARGE,
        weight=600,
        movement_feet=40,
        senses=_DARKVISION,
        body_semantics=_body("humanoid", lineage="ogre", role="bruiser"),
        default_loadout=(
            _equipped("armor.hide", BodyPart.BODY),
            _equipped(
                "weapon.creature.ogre_greatclub",
                WeaponSlot.MELEE_MAIN,
            ),
            _equipped(
                "weapon.creature.ogre_thrown_javelin",
                WeaponSlot.RANGED_MAIN,
            ),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.wolf",
        name="Wolf",
        description="A fast beast with natural bite pressure.",
        abilities=_abilities(12, 15, 12, 3, 12, 6),
        hit_dice=(MonsterHitDice(8, 2),),
        proficiency_bonus=2,
        challenge_rating="1/4",
        role_tags=("beast", "fast", "pack"),
        creature_type=CreatureType.BEAST,
        movement_feet=40,
        skills=_skills(SkillName.PERCEPTION, SkillName.STEALTH),
        trait_ids=(
            "trait.srd.keen_hearing_and_smell",
            "trait.srd.pack_tactics",
            "trait.srd.wolf_bite_prone_rider",
        ),
        body_semantics=_body("quadruped", lineage="wolf", role="predator"),
        intrinsic_loadout=(
            _equipped("armor.creature.wolf_natural", BodyPart.BODY),
            _equipped("weapon.creature.wolf_bite", WeaponSlot.MELEE_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.dire_wolf",
        name="Dire Wolf",
        description="A large fast beast for melee-pack and pursuit tests.",
        abilities=_abilities(17, 15, 15, 3, 12, 7),
        hit_dice=(MonsterHitDice(10, 5),),
        proficiency_bonus=2,
        challenge_rating="1",
        role_tags=("beast", "fast", "large", "pack"),
        creature_type=CreatureType.BEAST,
        size=Size.LARGE,
        weight=250,
        movement_feet=50,
        skills=_skills(SkillName.PERCEPTION, SkillName.STEALTH),
        trait_ids=(
            "trait.srd.keen_hearing_and_smell",
            "trait.srd.pack_tactics",
            "trait.srd.dire_wolf_bite_prone_rider",
        ),
        body_semantics=_body(
            "quadruped",
            lineage="dire_wolf",
            role="predator",
        ),
        intrinsic_loadout=(
            _equipped("armor.creature.dire_wolf_natural", BodyPart.BODY),
            _equipped(
                "weapon.creature.dire_wolf_bite",
                WeaponSlot.MELEE_MAIN,
            ),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.zombie",
        name="Zombie",
        description="A slow undead body that stresses pursuit and poison immunity.",
        abilities=_abilities(13, 6, 16, 3, 6, 5),
        hit_dice=(MonsterHitDice(8, 3),),
        proficiency_bonus=2,
        challenge_rating="1/4",
        role_tags=("melee", "slow", "undead"),
        creature_type=CreatureType.UNDEAD,
        movement_feet=20,
        damage_immunities=(DamageType.POISON,),
        condition_immunities=("Poisoned",),
        senses=_DARKVISION,
        trait_ids=("trait.srd.undead_fortitude",),
        body_semantics=_body(
            "humanoid",
            lineage="zombie",
            role="bruiser",
            state="undead",
        ),
        intrinsic_loadout=(
            _equipped("weapon.creature.zombie_slam", WeaponSlot.MELEE_MAIN),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.ogre_zombie",
        name="Ogre Zombie",
        description="A large undead bruiser with huge HP and slow cognition.",
        abilities=_abilities(19, 6, 18, 3, 6, 5),
        hit_dice=(MonsterHitDice(10, 9),),
        proficiency_bonus=2,
        challenge_rating="2",
        role_tags=("bruiser", "large", "undead"),
        creature_type=CreatureType.UNDEAD,
        size=Size.LARGE,
        weight=650,
        damage_immunities=(DamageType.POISON,),
        condition_immunities=("Poisoned",),
        senses=_DARKVISION,
        trait_ids=("trait.srd.undead_fortitude",),
        body_semantics=_body(
            "humanoid",
            lineage="ogre",
            role="bruiser",
            state="undead",
        ),
        default_loadout=(
            _equipped(
                "weapon.creature.ogre_zombie_morningstar",
                WeaponSlot.MELEE_MAIN,
            ),
        ),
    ),
    MonsterDefinition(
        monster_id="creature.ghoul",
        name="Ghoul",
        description="A fast undead attacker with bite and claw modes.",
        abilities=_abilities(13, 15, 10, 7, 10, 6),
        hit_dice=(MonsterHitDice(8, 5),),
        proficiency_bonus=2,
        challenge_rating="1",
        role_tags=("condition-threat", "melee", "undead"),
        creature_type=CreatureType.UNDEAD,
        damage_immunities=(DamageType.POISON,),
        condition_immunities=("Charmed", "Exhaustion", "Poisoned"),
        senses=_DARKVISION,
        trait_ids=("trait.srd.ghoul_claws_paralysis",),
        body_semantics=_body(
            "humanoid",
            lineage="ghoul",
            role="predator",
            state="undead",
        ),
        intrinsic_loadout=(
            _equipped("weapon.creature.ghoul_claws", WeaponSlot.MELEE_MAIN),
            _equipped("weapon.creature.ghoul_bite", WeaponSlot.MELEE_OFF),
        ),
    ),
)


SRD_MONSTER_DEFINITIONS: Mapping[str, MonsterDefinition] = MappingProxyType({
    definition.monster_id: definition
    for definition in _DEFINITIONS
})


__all__ = [
    "SRD_CONFIGURED_WARDROBE_LOADOUTS",
    "SRD_MONSTER_DEFINITIONS",
]
