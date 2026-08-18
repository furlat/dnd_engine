"""Cold renderer-independent definitions for the hand-authored bestiary."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.types.abilities import AbilityName, SkillName
from dnd.types.creatures import CreatureType, Size
from dnd.types.damage import DamageType
from dnd.types.equipment import BodyPart, WeaponSlot
from dnd.types.senses import SensesType


@dataclass(frozen=True, slots=True)
class MonsterHitDice:
    """Cold hit-die facts for a monster body."""

    die: int
    count: int
    mode: str = "average"
    ignore_first_level: bool = False


@dataclass(frozen=True, slots=True)
class MonsterSkillTraining:
    """One intrinsic monster skill proficiency or expertise."""

    skill: SkillName
    expertise: bool = False


@dataclass(frozen=True, slots=True)
class MonsterSense:
    """One intrinsic special sense."""

    sense_type: SensesType
    range_feet: int


@dataclass(frozen=True, slots=True)
class MonsterMultiattack:
    """One exact ordered stat-block attack sequence."""

    action_id: str
    name: str
    attacks: tuple[tuple[WeaponSlot, int], ...]


@dataclass(frozen=True, slots=True)
class MonsterDefinition:
    """Static authored facts resolved by the separate monster builder."""

    monster_id: str
    name: str
    description: str
    abilities: tuple[tuple[AbilityName, int], ...]
    hit_dice: tuple[MonsterHitDice, ...]
    proficiency_bonus: int
    challenge_rating: str = "0"
    role_tags: tuple[str, ...] = ()
    creature_type: CreatureType = CreatureType.HUMANOID
    size: Size = Size.MEDIUM
    weight: int = 150
    movement_feet: int = 30
    skills: tuple[MonsterSkillTraining, ...] = ()
    saving_throw_proficiencies: tuple[AbilityName, ...] = ()
    ability_modifier_bonuses: tuple[tuple[AbilityName, int], ...] = ()
    damage_reduction: int = 0
    temporary_hit_points: int = 0
    unarmed_damage_type: DamageType = DamageType.BLUDGEONING
    damage_vulnerabilities: tuple[DamageType, ...] = ()
    damage_immunities: tuple[DamageType, ...] = ()
    condition_immunities: tuple[str, ...] = ()
    senses: tuple[MonsterSense, ...] = ()
    spellcasting_ability: Optional[AbilityName] = None
    spellcaster_level: Optional[int] = None
    spell_slots: tuple[tuple[int, int], ...] = ()
    uses_full_caster_slots: bool = False
    spell_ids: tuple[str, ...] = ()
    reaction_ids: tuple[str, ...] = ()
    intrinsic_action_ids: tuple[str, ...] = ()
    intrinsic_feature_ids: tuple[str, ...] = ()
    trait_ids: tuple[str, ...] = ()
    multiattacks: tuple[MonsterMultiattack, ...] = ()
    body_semantics: tuple[tuple[str, str], ...] = ()
    intrinsic_loadout: tuple[ItemLoadoutEntry, ...] = ()
    default_loadout: tuple[ItemLoadoutEntry, ...] = ()

    def __post_init__(self) -> None:
        if not self.monster_id or "." not in self.monster_id:
            raise ValueError("monster_id must be a namespaced semantic ID")
        if tuple(name for name, _ in self.abilities) != tuple(AbilityName):
            raise ValueError("monster abilities must contain all six abilities in order")
        if self.proficiency_bonus < 0:
            raise ValueError("monster proficiency bonus cannot be negative")
        if self.movement_feet < 0:
            raise ValueError("monster movement cannot be negative")


_GOBLIN_ABILITIES = (
    (AbilityName.STRENGTH, 8),
    (AbilityName.DEXTERITY, 14),
    (AbilityName.CONSTITUTION, 10),
    (AbilityName.INTELLIGENCE, 10),
    (AbilityName.WISDOM, 8),
    (AbilityName.CHARISMA, 8),
)
_SKELETON_ABILITIES = (
    (AbilityName.STRENGTH, 10),
    (AbilityName.DEXTERITY, 14),
    (AbilityName.CONSTITUTION, 15),
    (AbilityName.INTELLIGENCE, 6),
    (AbilityName.WISDOM, 8),
    (AbilityName.CHARISMA, 5),
)
_SKELETON_ARCHER_ABILITIES = tuple(
    (ability, 16 if ability is AbilityName.DEXTERITY else score)
    for ability, score in _SKELETON_ABILITIES
)
_SKELETON_WARLOCK_ABILITIES = tuple(
    (ability, 14 if ability is AbilityName.CHARISMA else score)
    for ability, score in _SKELETON_ABILITIES
)
_CASTER_ABILITIES = (
    (AbilityName.STRENGTH, 8),
    (AbilityName.DEXTERITY, 14),
    (AbilityName.CONSTITUTION, 14),
    (AbilityName.INTELLIGENCE, 10),
    (AbilityName.WISDOM, 10),
    (AbilityName.CHARISMA, 18),
)

_DARKVISION = (MonsterSense(SensesType.DARKVISION, 60),)
_GOBLIN_BODY = (
    ("anatomy", "humanoid"),
    ("lineage", "goblinoid"),
    ("skin_palette", "green"),
    ("stature", "small"),
)
_SKELETON_BODY = (
    ("anatomy", "humanoid_skeleton"),
    ("material", "bone"),
    ("state", "undead"),
)
_CASTER_BODY = (
    ("anatomy", "humanoid"),
    ("role", "arcane_caster"),
)

_GOBLIN_LOADOUT = (
    ItemLoadoutEntry("armor.leather", equipment_slot=BodyPart.BODY),
    ItemLoadoutEntry("weapon.scimitar", equipment_slot=WeaponSlot.MELEE_MAIN),
    ItemLoadoutEntry("weapon.shortbow", equipment_slot=WeaponSlot.RANGED_MAIN),
    ItemLoadoutEntry("shield.shield", equipment_slot=WeaponSlot.MELEE_OFF),
)
_SKELETON_LOADOUT = (
    ItemLoadoutEntry("armor.armor_scraps", equipment_slot=BodyPart.BODY),
    ItemLoadoutEntry("weapon.shortsword", equipment_slot=WeaponSlot.MELEE_MAIN),
    ItemLoadoutEntry("weapon.shortbow", equipment_slot=WeaponSlot.RANGED_MAIN),
)
_CASTER_LOADOUT = (
    ItemLoadoutEntry("weapon.dagger", equipment_slot=WeaponSlot.MELEE_MAIN),
    ItemLoadoutEntry("consumable.potion_greater_invisibility"),
    ItemLoadoutEntry("consumable.potion_haste"),
)

MONSTER_WARDROBE_LOADOUTS: Mapping[str, tuple[ItemLoadoutEntry, ...]] = (
    MappingProxyType({
        "monster.goblin": (
            ItemLoadoutEntry(
                "apparel.leather_boots.dark",
                equipment_slot=BodyPart.FEET,
            ),
        ),
        "monster.goblin_archer": (
            ItemLoadoutEntry(
                "apparel.leather_boots.dark",
                equipment_slot=BodyPart.FEET,
            ),
        ),
        "monster.generic_caster.arcane": (
            ItemLoadoutEntry(
                "apparel.robes.hedge_wizard",
                equipment_slot=BodyPart.BODY,
            ),
            ItemLoadoutEntry(
                "apparel.cloth_shoes",
                equipment_slot=BodyPart.FEET,
            ),
        ),
        "monster.generic_caster.dark": (
            ItemLoadoutEntry(
                "apparel.robes.dark_cultist",
                equipment_slot=BodyPart.BODY,
            ),
            ItemLoadoutEntry(
                "apparel.cloth_shoes.dark",
                equipment_slot=BodyPart.FEET,
            ),
        ),
        "monster.generic_caster.divine": (
            ItemLoadoutEntry(
                "apparel.robes.priest_vestments",
                equipment_slot=BodyPart.BODY,
            ),
            ItemLoadoutEntry(
                "apparel.sandals.rope",
                equipment_slot=BodyPart.FEET,
            ),
        ),
        "monster.generic_caster.necromancer": (
            ItemLoadoutEntry(
                "apparel.robes.necromancer",
                equipment_slot=BodyPart.BODY,
            ),
            ItemLoadoutEntry(
                "apparel.cloth_shoes.dark",
                equipment_slot=BodyPart.FEET,
            ),
        ),
        "monster.goblin_caster": (
            ItemLoadoutEntry(
                "apparel.robes.hedge_wizard",
                equipment_slot=BodyPart.BODY,
            ),
            ItemLoadoutEntry(
                "apparel.cloth_shoes.dark",
                equipment_slot=BodyPart.FEET,
            ),
        ),
    })
)

_DEFINITIONS = (
    MonsterDefinition(
        monster_id="monster.goblin",
        name="Goblin",
        description="A small, green-skinned creature with pointed ears and sharp teeth.",
        abilities=_GOBLIN_ABILITIES,
        hit_dice=(MonsterHitDice(6, 2),),
        proficiency_bonus=2,
        size=Size.SMALL,
        weight=40,
        skills=(MonsterSkillTraining(SkillName.STEALTH, expertise=True),),
        senses=_DARKVISION,
        intrinsic_action_ids=("trait.goblin.nimble_escape",),
        body_semantics=_GOBLIN_BODY,
        default_loadout=_GOBLIN_LOADOUT,
    ),
    MonsterDefinition(
        monster_id="monster.skeleton",
        name="Skeleton",
        description="An animated skeleton wielding rusted weapons.",
        abilities=_SKELETON_ABILITIES,
        hit_dice=(MonsterHitDice(8, 2),),
        proficiency_bonus=2,
        creature_type=CreatureType.UNDEAD,
        weight=120,
        damage_vulnerabilities=(DamageType.BLUDGEONING,),
        damage_immunities=(DamageType.POISON,),
        condition_immunities=("Poisoned", "Exhaustion"),
        senses=_DARKVISION,
        body_semantics=_SKELETON_BODY,
        default_loadout=_SKELETON_LOADOUT,
    ),
    MonsterDefinition(
        monster_id="monster.goblin_archer",
        name="Goblin Archer",
        description="A goblin skirmisher that prefers to attack from range.",
        abilities=_GOBLIN_ABILITIES,
        hit_dice=(MonsterHitDice(6, 2),),
        proficiency_bonus=2,
        size=Size.SMALL,
        weight=40,
        skills=(MonsterSkillTraining(SkillName.STEALTH, expertise=True),),
        senses=_DARKVISION,
        body_semantics=_GOBLIN_BODY + (("role", "archer"),),
        default_loadout=(
            ItemLoadoutEntry("armor.leather", equipment_slot=BodyPart.BODY),
            ItemLoadoutEntry("weapon.shortbow", equipment_slot=WeaponSlot.RANGED_MAIN),
            ItemLoadoutEntry("weapon.scimitar", equipment_slot=WeaponSlot.MELEE_MAIN),
            ItemLoadoutEntry("weapon.dagger", equipment_slot=WeaponSlot.MELEE_OFF),
        ),
    ),
    MonsterDefinition(
        monster_id="monster.generic_caster",
        name="Caster",
        description="A classless spellcaster with innate magical abilities.",
        abilities=_CASTER_ABILITIES,
        hit_dice=(MonsterHitDice(6, 5, mode="maximums"),),
        proficiency_bonus=3,
        spellcasting_ability=AbilityName.CHARISMA,
        uses_full_caster_slots=True,
        spell_ids=(
            "spell.fire_bolt", "spell.magic_missile", "spell.fireball",
            "spell.burning_hands", "spell.lightning_bolt", "spell.shatter",
            "spell.thunderwave", "spell.invisibility",
            "spell.greater_invisibility",
        ),
        reaction_ids=("reaction.spell.shield",),
        body_semantics=_CASTER_BODY,
        default_loadout=_CASTER_LOADOUT,
    ),
    MonsterDefinition(
        monster_id="monster.goblin_caster",
        name="Goblin Caster",
        description="A goblin hedge caster combining arcane power with goblinoid mobility.",
        abilities=_CASTER_ABILITIES,
        hit_dice=(MonsterHitDice(6, 5, mode="maximums"),),
        proficiency_bonus=3,
        size=Size.SMALL,
        weight=40,
        senses=_DARKVISION,
        spellcasting_ability=AbilityName.CHARISMA,
        uses_full_caster_slots=True,
        spell_ids=(
            "spell.fire_bolt", "spell.magic_missile", "spell.fireball",
            "spell.burning_hands", "spell.lightning_bolt", "spell.shatter",
            "spell.thunderwave", "spell.invisibility",
            "spell.greater_invisibility",
        ),
        reaction_ids=("reaction.spell.shield",),
        intrinsic_action_ids=("trait.goblin.nimble_escape",),
        body_semantics=_GOBLIN_BODY + (("role", "arcane_caster"),),
        default_loadout=_CASTER_LOADOUT,
    ),
    MonsterDefinition(
        monster_id="monster.skeleton_warrior",
        name="Skeleton Warrior",
        description="A heavily armored skeleton wielding a longsword and shield.",
        abilities=_SKELETON_ABILITIES,
        hit_dice=(MonsterHitDice(8, 4),),
        proficiency_bonus=2,
        creature_type=CreatureType.UNDEAD,
        weight=120,
        damage_vulnerabilities=(DamageType.BLUDGEONING,),
        damage_immunities=(DamageType.POISON,),
        condition_immunities=("Poisoned", "Exhaustion"),
        body_semantics=_SKELETON_BODY + (("role", "warrior"),),
        default_loadout=(
            ItemLoadoutEntry("armor.armor_scraps", equipment_slot=BodyPart.BODY),
            ItemLoadoutEntry("weapon.longsword", equipment_slot=WeaponSlot.MELEE_MAIN),
            ItemLoadoutEntry("shield.shield", equipment_slot=WeaponSlot.MELEE_OFF),
            ItemLoadoutEntry("consumable.acid_flask"),
        ),
    ),
    MonsterDefinition(
        monster_id="monster.skeleton_archer",
        name="Skeleton Archer",
        description="A skeleton archer that can mark targets for its allies.",
        abilities=_SKELETON_ARCHER_ABILITIES,
        hit_dice=(MonsterHitDice(8, 3),),
        proficiency_bonus=2,
        creature_type=CreatureType.UNDEAD,
        weight=120,
        damage_vulnerabilities=(DamageType.BLUDGEONING,),
        damage_immunities=(DamageType.POISON,),
        condition_immunities=("Poisoned", "Exhaustion"),
        intrinsic_action_ids=("trait.skeleton.mark_target",),
        body_semantics=_SKELETON_BODY + (("role", "archer"),),
        default_loadout=(
            ItemLoadoutEntry("armor.armor_scraps", equipment_slot=BodyPart.BODY),
            ItemLoadoutEntry("weapon.shortbow", equipment_slot=WeaponSlot.RANGED_MAIN),
            ItemLoadoutEntry("weapon.dagger", equipment_slot=WeaponSlot.MELEE_MAIN),
            ItemLoadoutEntry("weapon.dagger", equipment_slot=WeaponSlot.MELEE_OFF),
        ),
    ),
    MonsterDefinition(
        monster_id="monster.skeleton_warlock",
        name="Skeleton Warlock",
        description="A skeleton crackling with dark arcane energy.",
        abilities=_SKELETON_WARLOCK_ABILITIES,
        hit_dice=(MonsterHitDice(8, 2),),
        proficiency_bonus=2,
        creature_type=CreatureType.UNDEAD,
        weight=120,
        damage_vulnerabilities=(DamageType.BLUDGEONING,),
        damage_immunities=(DamageType.POISON,),
        condition_immunities=("Poisoned", "Exhaustion"),
        spellcasting_ability=AbilityName.CHARISMA,
        spell_slots=((1, 2), (2, 1)),
        spell_ids=(
            "spell.eldritch_blast", "spell.burning_hands",
            "spell.thunderwave", "spell.necrotic_bless",
        ),
        reaction_ids=("reaction.spell.shield",),
        body_semantics=_SKELETON_BODY + (("role", "warlock"),),
        default_loadout=(
            ItemLoadoutEntry("armor.armor_scraps", equipment_slot=BodyPart.BODY),
            ItemLoadoutEntry("apparel.crown", equipment_slot=BodyPart.HEAD),
            ItemLoadoutEntry("weapon.arcane_staff", equipment_slot=WeaponSlot.MELEE_MAIN),
            ItemLoadoutEntry("spell_item.scroll_invisibility"),
        ),
    ),
    MonsterDefinition(
        monster_id="monster.circus_fighter",
        name="Circus Fighter",
        description=(
            "A veteran circus fighter trained to duel with elemental weapons."
        ),
        abilities=(
            (AbilityName.STRENGTH, 16),
            (AbilityName.DEXTERITY, 12),
            (AbilityName.CONSTITUTION, 16),
            (AbilityName.INTELLIGENCE, 10),
            (AbilityName.WISDOM, 10),
            (AbilityName.CHARISMA, 10),
        ),
        hit_dice=(
            MonsterHitDice(10, 4),
            MonsterHitDice(8, 1, ignore_first_level=True),
        ),
        proficiency_bonus=0,
        skills=(MonsterSkillTraining(SkillName.ACROBATICS, expertise=True),),
        saving_throw_proficiencies=(AbilityName.STRENGTH,),
        ability_modifier_bonuses=((AbilityName.STRENGTH, 1),),
        damage_reduction=1,
        temporary_hit_points=10,
        unarmed_damage_type=DamageType.PIERCING,
        intrinsic_feature_ids=(
            "trait.circus.dual_wielder",
            "trait.circus.elemental_weapon_mastery",
            "trait.circus.elemental_affinity",
            "trait.circus.performer",
        ),
        body_semantics=(
            ("anatomy", "humanoid"),
            ("role", "circus_fighter"),
            ("hands", "spiked_claws"),
        ),
        default_loadout=(
            ItemLoadoutEntry(
                "armor.circus.performer_leather",
                equipment_slot=BodyPart.BODY,
            ),
            ItemLoadoutEntry(
                "weapon.circus.flaming_scimitar",
                equipment_slot=WeaponSlot.MELEE_MAIN,
            ),
            ItemLoadoutEntry(
                "weapon.circus.rusty_dagger",
                equipment_slot=WeaponSlot.MELEE_OFF,
            ),
        ),
    ),
)

MONSTER_DEFINITIONS: Mapping[str, MonsterDefinition] = MappingProxyType({
    definition.monster_id: definition
    for definition in _DEFINITIONS
})


__all__ = [
    "MONSTER_DEFINITIONS",
    "MONSTER_WARDROBE_LOADOUTS",
    "MonsterDefinition",
    "MonsterHitDice",
    "MonsterMultiattack",
    "MonsterSense",
    "MonsterSkillTraining",
]
