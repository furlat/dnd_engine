"""Cold direct class definitions and pure class-line resolution."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from dnd.types.abilities import AbilityName, SkillName
from dnd.types.character_progression import (
    AppliedClassLevel,
    CharacterClass,
    CharacterSubclass,
)
from dnd.core.progression import FULL_CASTER_SPELL_SLOTS


FIGHTER_FIGHTING_STYLES = (
    "class_feature.fighter.fighting_style.archery",
    "class_feature.fighter.fighting_style.defense",
    "class_feature.fighter.fighting_style.dueling",
    "class_feature.fighter.fighting_style.great_weapon_fighting",
    "class_feature.fighter.fighting_style.protection",
    "class_feature.fighter.fighting_style.two_weapon_fighting",
)
FIGHTER_CLASS_SKILLS: tuple[SkillName, ...] = (
    "acrobatics",
    "animal_handling",
    "athletics",
    "history",
    "insight",
    "intimidation",
    "perception",
    "survival",
)
FIGHTER_STARTING_EQUIPMENT = (
    "starting_equipment.fighter.archery",
    "starting_equipment.fighter.dual_wield",
    "starting_equipment.fighter.greatsword",
    "starting_equipment.fighter.sword_shield",
)
FIGHTER_FIRST_CLASS_PROFICIENCIES = (
    "armor.heavy",
    "armor.light",
    "armor.medium",
    "shield.shield",
    "weapon.martial",
    "weapon.simple",
)
FIGHTER_MULTICLASS_PROFICIENCIES = (
    "armor.light",
    "armor.medium",
    "shield.shield",
    "weapon.martial",
    "weapon.simple",
)
FIGHTER_SAVING_THROWS = ("constitution", "strength")
FIGHTER_ASI_LEVELS = (4, 6, 8, 12, 14, 16, 19)
FIGHTER_ASI_VALUES = tuple(
    f"ability_score.{ability}.{amount}"
    for ability in (
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    )
    for amount in (1, 2)
) + ("feat.lucky",)

# Exact legacy declarations displaced by the direct Fighter/Champion owner.
# Shared Extra Attack and Lucky identities remain admitted until their other
# class families move off the legacy path.
FIGHTER_RETIRED_DECLARATION_IDS = frozenset({
    "class.fighter",
    "subclass.fighter.champion",
    "action.class.fighter.action_surge",
    "action.class.fighter.second_wind",
    "reaction.class_feature.fighter.protection",
    *FIGHTER_FIGHTING_STYLES,
    "class_feature.fighter.action_surge",
    "class_feature.fighter.improved_critical",
    "class_feature.fighter.indomitable",
    "class_feature.fighter.remarkable_athlete",
    "class_feature.fighter.second_wind",
    "class_feature.fighter.superior_critical",
    "class_feature.fighter.survivor",
})

BARBARIAN_CLASS_SKILLS: tuple[SkillName, ...] = (
    "animal_handling",
    "athletics",
    "intimidation",
    "nature",
    "perception",
    "survival",
)
BARBARIAN_STARTING_EQUIPMENT = (
    "starting_equipment.barbarian.dual_axes",
    "starting_equipment.barbarian.greataxe",
    "starting_equipment.barbarian.sword_shield",
)
BARBARIAN_FIRST_CLASS_PROFICIENCIES = (
    "armor.light",
    "armor.medium",
    "shield.shield",
    "weapon.martial",
    "weapon.simple",
)
BARBARIAN_MULTICLASS_PROFICIENCIES = (
    "shield.shield",
    "weapon.martial",
    "weapon.simple",
)
BARBARIAN_SAVING_THROWS = ("constitution", "strength")
BARBARIAN_ASI_LEVELS = (4, 8, 12, 16, 19)
BARBARIAN_ASI_VALUES = tuple(
    f"ability_score.{ability}.{amount}"
    for ability in (
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    )
    for amount in (1, 2)
) + ("feat.lucky",)

SORCERER_CLASS_SKILLS: tuple[SkillName, ...] = (
    "arcana",
    "deception",
    "insight",
    "intimidation",
    "persuasion",
    "religion",
)
SORCERER_STARTING_EQUIPMENT = (
    "starting_equipment.sorcerer.dagger",
    "starting_equipment.sorcerer.quarterstaff",
)
SORCERER_FIRST_CLASS_PROFICIENCIES = (
    "weapon.dagger",
    "weapon.dart",
    "weapon.light_crossbow",
    "weapon.quarterstaff",
    "weapon.sling",
)
SORCERER_SAVING_THROWS = ("charisma", "constitution")
SORCERER_ASI_LEVELS = (4, 8, 12, 16, 19)
SORCERER_ASI_VALUES = tuple(
    f"ability_score.{ability}.{amount}"
    for ability in (
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    )
    for amount in (1, 2)
) + ("feat.lucky",)
SORCERER_METAMAGIC_OPTIONS = (
    "class_feature.sorcerer.metamagic.distant_spell",
    "class_feature.sorcerer.metamagic.quickened_spell",
    "class_feature.sorcerer.metamagic.twinned_spell",
)

# Exact legacy declarations displaced by the direct Sorcerer/Draconic owner.
# Spell behaviors and Lucky remain admitted because they are shared authored
# mechanics; only the obsolete class-line declarations are retired here.
SORCERER_RETIRED_DECLARATION_IDS = frozenset({
    "class.sorcerer",
    "subclass.sorcerer.draconic_bloodline",
    "action.class.sorcerer.convert_sorcery_points_to_slot",
    "action.class.sorcerer.convert_slot_to_sorcery_points",
    "action.class.sorcerer.distant_spell",
    "action.class.sorcerer.draconic_presence",
    "action.class.sorcerer.dragon_wings.fly",
    "action.class.sorcerer.dragon_wings.toggle",
    "action.class.sorcerer.elemental_affinity.resistance",
    "action.class.sorcerer.quickened_spell",
    "action.class.sorcerer.twinned_spell",
    "class_feature.sorcerer.draconic_ancestry.black",
    "class_feature.sorcerer.draconic_ancestry.blue",
    "class_feature.sorcerer.draconic_ancestry.brass",
    "class_feature.sorcerer.draconic_ancestry.bronze",
    "class_feature.sorcerer.draconic_ancestry.copper",
    "class_feature.sorcerer.draconic_ancestry.gold",
    "class_feature.sorcerer.draconic_ancestry.green",
    "class_feature.sorcerer.draconic_ancestry.red",
    "class_feature.sorcerer.draconic_ancestry.silver",
    "class_feature.sorcerer.draconic_ancestry.white",
    "class_feature.sorcerer.draconic_presence",
    "class_feature.sorcerer.draconic_presence.aura",
    "class_feature.sorcerer.draconic_presence.immunity",
    "class_feature.sorcerer.draconic_resilience",
    "class_feature.sorcerer.dragon_wings",
    "class_feature.sorcerer.dragon_wings.active",
    "class_feature.sorcerer.elemental_affinity",
    "class_feature.sorcerer.elemental_affinity.resistance",
    "class_feature.sorcerer.metamagic.careful_spell",
    "class_feature.sorcerer.metamagic.distant_spell",
    "class_feature.sorcerer.metamagic.empowered_spell",
    "class_feature.sorcerer.metamagic.extended_spell",
    "class_feature.sorcerer.metamagic.heightened_spell",
    "class_feature.sorcerer.metamagic.quickened_spell",
    "class_feature.sorcerer.metamagic.subtle_spell",
    "class_feature.sorcerer.metamagic.twinned_spell",
    "class_feature.sorcerer.metamagic_active",
    "class_feature.sorcerer.sorcerous_restoration",
    "class_feature.sorcerer.sorcery_points",
})
SORCERER_ANCESTRY_DAMAGE_TYPES: Mapping[str, str] = MappingProxyType({
    "class_feature.sorcerer.draconic_ancestry.black": "acid",
    "class_feature.sorcerer.draconic_ancestry.blue": "lightning",
    "class_feature.sorcerer.draconic_ancestry.brass": "fire",
    "class_feature.sorcerer.draconic_ancestry.bronze": "lightning",
    "class_feature.sorcerer.draconic_ancestry.copper": "acid",
    "class_feature.sorcerer.draconic_ancestry.gold": "fire",
    "class_feature.sorcerer.draconic_ancestry.green": "poison",
    "class_feature.sorcerer.draconic_ancestry.red": "fire",
    "class_feature.sorcerer.draconic_ancestry.silver": "cold",
    "class_feature.sorcerer.draconic_ancestry.white": "cold",
})
SORCERER_SPELL_RANKS: Mapping[str, int] = MappingProxyType({
    "spell.acid_splash": 0,
    "spell.chill_touch": 0,
    "spell.fire_bolt": 0,
    "spell.light": 0,
    "spell.poison_spray": 0,
    "spell.ray_of_frost": 0,
    "spell.shocking_grasp": 0,
    "spell.true_strike": 0,
    "spell.burning_hands": 1,
    "spell.charm_person": 1,
    "spell.color_spray": 1,
    "spell.expeditious_retreat": 1,
    "spell.false_life": 1,
    "spell.fog_cloud": 1,
    "spell.jump": 1,
    "spell.mage_armor": 1,
    "spell.magic_missile": 1,
    "spell.shield": 1,
    "spell.sleep": 1,
    "spell.thunderwave": 1,
    "spell.blindness_deafness": 2,
    "spell.blur": 2,
    "spell.darkness": 2,
    "spell.darkvision": 2,
    "spell.enhance_ability": 2,
    "spell.enlarge_reduce": 2,
    "spell.gust_of_wind": 2,
    "spell.hold_person": 2,
    "spell.invisibility": 2,
    "spell.mirror_image": 2,
    "spell.misty_step": 2,
    "spell.scorching_ray": 2,
    "spell.see_invisibility": 2,
    "spell.shatter": 2,
    "spell.web": 2,
    "spell.counterspell": 3,
    "spell.daylight": 3,
    "spell.fear": 3,
    "spell.fireball": 3,
    "spell.haste": 3,
    "spell.hypnotic_pattern": 3,
    "spell.lightning_bolt": 3,
    "spell.protection_from_energy": 3,
    "spell.sleet_storm": 3,
    "spell.slow": 3,
    "spell.stinking_cloud": 3,
    "spell.banishment": 4,
    "spell.blight": 4,
    "spell.dimension_door": 4,
    "spell.greater_invisibility": 4,
    "spell.ice_storm": 4,
    "spell.stoneskin": 4,
    "spell.cloudkill": 5,
    "spell.cone_of_cold": 5,
    "spell.hold_monster": 5,
    "spell.insect_plague": 5,
    "spell.telekinesis": 5,
    "spell.chain_lightning": 6,
    "spell.circle_of_death": 6,
    "spell.disintegrate": 6,
    "spell.eyebite": 6,
    "spell.globe_of_invulnerability": 6,
    "spell.sunbeam": 6,
    "spell.true_seeing": 6,
    "spell.finger_of_death": 7,
    "spell.prismatic_spray": 7,
    "spell.incendiary_cloud": 8,
    "spell.power_word_stun": 8,
    "spell.sunburst": 8,
    "spell.power_word_kill": 9,
})

# Exact legacy declarations displaced by the direct Barbarian/Berserker
# owner. Lucky remains shared with the not-yet-migrated Sorcerer line. The
# Reckless Attack action and its runtime condition remain admitted because the
# SRD Berserker monster independently owns that same behavior pair.
BARBARIAN_RETIRED_DECLARATION_IDS = frozenset({
    "class.barbarian",
    "subclass.barbarian.berserker",
    "action.class.barbarian.end_rage",
    "action.class.barbarian.extend_intimidating_presence",
    "action.class.barbarian.frenzied_strike",
    "action.class.barbarian.frenzy",
    "action.class.barbarian.intimidating_presence",
    "action.class.barbarian.rage",
    "action.feature.extra_attack",
    "reaction.class_feature.barbarian.retaliation",
    "class_feature.extra_attack",
    "class_feature.barbarian.brutal_critical",
    "class_feature.barbarian.danger_sense",
    "class_feature.barbarian.fast_movement",
    "class_feature.barbarian.feral_instinct",
    "class_feature.barbarian.frenzied",
    "class_feature.barbarian.frenzy",
    "class_feature.barbarian.indomitable_might",
    "class_feature.barbarian.intimidating_presence",
    "class_feature.barbarian.intimidating_presence_immunity",
    "class_feature.barbarian.mindless_rage",
    "class_feature.barbarian.persistent_rage",
    "class_feature.barbarian.primal_champion",
    "class_feature.barbarian.rage",
    "class_feature.barbarian.raging",
    "class_feature.barbarian.reckless_attack",
    "class_feature.barbarian.relentless_rage",
    "class_feature.barbarian.retaliation",
    "class_feature.barbarian.unarmored_defense",
})
CHARACTER_RETIRED_DECLARATION_IDS = (
    FIGHTER_RETIRED_DECLARATION_IDS
    | BARBARIAN_RETIRED_DECLARATION_IDS
    | SORCERER_RETIRED_DECLARATION_IDS
)


@dataclass(frozen=True, slots=True)
class ClassChoiceDefinition:
    """One exact ordered direct class choice."""

    choice_id: str
    selections: tuple[int, ...]
    allowed_values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClassLevelDefinition:
    """Cold automatic features and choices for one class level."""

    class_level: int
    feature_ids: tuple[str, ...] = ()
    choices: tuple[ClassChoiceDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class FighterDefinition:
    """Complete direct Fighter/Champion authored table."""

    hit_die: int
    first_class_proficiencies: tuple[str, ...]
    multiclass_proficiencies: tuple[str, ...]
    saving_throws: tuple[AbilityName, ...]
    class_skills: tuple[SkillName, ...]
    starting_equipment: tuple[str, ...]
    levels: tuple[ClassLevelDefinition, ...]
    champion_levels: tuple[ClassLevelDefinition, ...]


@dataclass(frozen=True, slots=True)
class ResolvedFighterLevel:
    """Validated values consumed directly by the Fighter grant owner."""

    level: AppliedClassLevel
    first_class_entry: bool
    proficiencies: tuple[str, ...]
    saving_throws: tuple[AbilityName, ...]
    skills: tuple[SkillName, ...]
    starting_equipment_id: str | None
    fighting_style_id: str | None
    ability_increases: tuple[tuple[AbilityName, int], ...]
    feat_id: str | None
    feature_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BarbarianDefinition:
    """Complete direct Barbarian/Berserker authored table."""

    hit_die: int
    first_class_proficiencies: tuple[str, ...]
    multiclass_proficiencies: tuple[str, ...]
    saving_throws: tuple[AbilityName, ...]
    class_skills: tuple[SkillName, ...]
    starting_equipment: tuple[str, ...]
    levels: tuple[ClassLevelDefinition, ...]
    berserker_levels: tuple[ClassLevelDefinition, ...]


@dataclass(frozen=True, slots=True)
class ResolvedBarbarianLevel:
    """Validated values consumed directly by the Barbarian grant owner."""

    level: AppliedClassLevel
    first_class_entry: bool
    proficiencies: tuple[str, ...]
    saving_throws: tuple[AbilityName, ...]
    skills: tuple[SkillName, ...]
    starting_equipment_id: str | None
    ability_increases: tuple[tuple[AbilityName, int], ...]
    feat_id: str | None
    feature_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SorcererDefinition:
    """Complete direct Sorcerer/Draconic Bloodline authored table."""

    hit_die: int
    first_class_proficiencies: tuple[str, ...]
    multiclass_proficiencies: tuple[str, ...]
    saving_throws: tuple[AbilityName, ...]
    class_skills: tuple[SkillName, ...]
    starting_equipment: tuple[str, ...]
    spellcasting_source_id: str
    spellcasting_ability: AbilityName
    spell_ranks: Mapping[str, int]
    levels: tuple[ClassLevelDefinition, ...]
    draconic_levels: tuple[ClassLevelDefinition, ...]


@dataclass(frozen=True, slots=True)
class ResolvedSorcererLevel:
    """Validated values consumed directly by the Sorcerer grant owner."""

    level: AppliedClassLevel
    first_class_entry: bool
    proficiencies: tuple[str, ...]
    saving_throws: tuple[AbilityName, ...]
    skills: tuple[SkillName, ...]
    starting_equipment_id: str | None
    cantrip_ids: tuple[str, ...]
    spell_ids: tuple[str, ...]
    replacement: tuple[str, str] | None
    metamagic_ids: tuple[str, ...]
    ancestry_id: str | None
    ancestry_damage_type: str | None
    ability_increases: tuple[tuple[AbilityName, int], ...]
    feat_id: str | None
    feature_ids: tuple[str, ...]
    normal_spell_slots: tuple[tuple[int, int], ...]
    maximum_spell_rank: int


_FIGHTER_FEATURES: Mapping[int, tuple[str, ...]] = MappingProxyType({
    1: ("class_feature.fighter.second_wind",),
    2: ("class_feature.fighter.action_surge",),
    5: ("class_feature.extra_attack",),
    9: ("class_feature.fighter.indomitable",),
    11: ("class_feature.extra_attack",),
    13: ("class_feature.fighter.indomitable",),
    17: (
        "class_feature.fighter.action_surge",
        "class_feature.fighter.indomitable",
    ),
    20: ("class_feature.extra_attack",),
})
_CHAMPION_FEATURES: Mapping[int, tuple[str, ...]] = MappingProxyType({
    3: ("class_feature.fighter.improved_critical",),
    7: ("class_feature.fighter.remarkable_athlete",),
    15: ("class_feature.fighter.superior_critical",),
    18: ("class_feature.fighter.survivor",),
})


def _asi_choice(level: int) -> ClassChoiceDefinition:
    return ClassChoiceDefinition(
        choice_id=f"class.fighter.level_{level}.asi_or_feat",
        selections=(1, 2),
        allowed_values=FIGHTER_ASI_VALUES,
    )


def _fighter_choices(level: int) -> tuple[ClassChoiceDefinition, ...]:
    rows: list[ClassChoiceDefinition] = []
    if level == 1:
        rows.append(ClassChoiceDefinition(
            "class.fighter.level_1.fighting_style",
            (1,),
            FIGHTER_FIGHTING_STYLES,
        ))
    if level == 3:
        rows.append(ClassChoiceDefinition(
            "class.fighter.level_3.subclass",
            (1,),
            (CharacterSubclass.CHAMPION.value,),
        ))
    if level in FIGHTER_ASI_LEVELS:
        rows.append(_asi_choice(level))
    return tuple(rows)


def _champion_choices(level: int) -> tuple[ClassChoiceDefinition, ...]:
    if level != 10:
        return ()
    return (ClassChoiceDefinition(
        "subclass.fighter.champion.level_10.fighting_style",
        (1,),
        FIGHTER_FIGHTING_STYLES,
    ),)


FIGHTER_DEFINITION = FighterDefinition(
    hit_die=10,
    first_class_proficiencies=FIGHTER_FIRST_CLASS_PROFICIENCIES,
    multiclass_proficiencies=FIGHTER_MULTICLASS_PROFICIENCIES,
    saving_throws=FIGHTER_SAVING_THROWS,
    class_skills=FIGHTER_CLASS_SKILLS,
    starting_equipment=FIGHTER_STARTING_EQUIPMENT,
    levels=tuple(
        ClassLevelDefinition(
            level,
            _FIGHTER_FEATURES.get(level, ()),
            _fighter_choices(level),
        )
        for level in range(1, 21)
    ),
    champion_levels=tuple(
        ClassLevelDefinition(
            level,
            _CHAMPION_FEATURES.get(level, ()),
            _champion_choices(level),
        )
        for level in range(1, 21)
    ),
)


_BARBARIAN_FEATURES: Mapping[int, tuple[str, ...]] = MappingProxyType({
    1: (
        "class_feature.barbarian.rage",
        "class_feature.barbarian.unarmored_defense",
    ),
    2: (
        "class_feature.barbarian.reckless_attack",
        "class_feature.barbarian.danger_sense",
    ),
    3: ("class_feature.barbarian.rage",),
    5: ("class_feature.extra_attack", "class_feature.barbarian.fast_movement"),
    6: ("class_feature.barbarian.rage",),
    7: ("class_feature.barbarian.feral_instinct",),
    9: (
        "class_feature.barbarian.rage",
        "class_feature.barbarian.brutal_critical",
    ),
    11: ("class_feature.barbarian.relentless_rage",),
    12: ("class_feature.barbarian.rage",),
    13: ("class_feature.barbarian.brutal_critical",),
    15: ("class_feature.barbarian.persistent_rage",),
    16: ("class_feature.barbarian.rage",),
    17: (
        "class_feature.barbarian.rage",
        "class_feature.barbarian.brutal_critical",
    ),
    18: ("class_feature.barbarian.indomitable_might",),
    20: (
        "class_feature.barbarian.rage",
        "class_feature.barbarian.primal_champion",
    ),
})
_BERSERKER_FEATURES: Mapping[int, tuple[str, ...]] = MappingProxyType({
    3: ("class_feature.barbarian.frenzy",),
    6: ("class_feature.barbarian.mindless_rage",),
    10: ("class_feature.barbarian.intimidating_presence",),
    14: ("class_feature.barbarian.retaliation",),
})


def _barbarian_choices(level: int) -> tuple[ClassChoiceDefinition, ...]:
    rows: list[ClassChoiceDefinition] = []
    if level == 3:
        rows.append(ClassChoiceDefinition(
            "class.barbarian.level_3.subclass",
            (1,),
            (CharacterSubclass.BERSERKER.value,),
        ))
    if level in BARBARIAN_ASI_LEVELS:
        rows.append(ClassChoiceDefinition(
            f"class.barbarian.level_{level}.asi_or_feat",
            (1, 2),
            BARBARIAN_ASI_VALUES,
        ))
    return tuple(rows)


BARBARIAN_DEFINITION = BarbarianDefinition(
    hit_die=12,
    first_class_proficiencies=BARBARIAN_FIRST_CLASS_PROFICIENCIES,
    multiclass_proficiencies=BARBARIAN_MULTICLASS_PROFICIENCIES,
    saving_throws=BARBARIAN_SAVING_THROWS,
    class_skills=BARBARIAN_CLASS_SKILLS,
    starting_equipment=BARBARIAN_STARTING_EQUIPMENT,
    levels=tuple(
        ClassLevelDefinition(
            level,
            _BARBARIAN_FEATURES.get(level, ()),
            _barbarian_choices(level),
        )
        for level in range(1, 21)
    ),
    berserker_levels=tuple(
        ClassLevelDefinition(level, _BERSERKER_FEATURES.get(level, ()))
        for level in range(1, 21)
    ),
)


_SORCERER_FEATURES: Mapping[int, tuple[str, ...]] = MappingProxyType({
    2: ("class_feature.sorcerer.sorcery_points",),
    20: ("class_feature.sorcerer.sorcerous_restoration",),
})
_DRACONIC_FEATURES: Mapping[int, tuple[str, ...]] = MappingProxyType({
    1: ("class_feature.sorcerer.draconic_resilience",),
    6: ("class_feature.sorcerer.elemental_affinity",),
    14: ("class_feature.sorcerer.dragon_wings",),
    18: ("class_feature.sorcerer.draconic_presence",),
})
_SORCERER_CANTRIP_LEARN_COUNTS = {1: 4, 4: 1, 10: 1}
_SORCERER_SPELL_LEARN_COUNTS = {
    1: 2,
    2: 1,
    3: 1,
    4: 1,
    5: 1,
    6: 1,
    7: 1,
    8: 1,
    9: 1,
    10: 1,
    11: 1,
    13: 1,
    15: 1,
    17: 1,
}
_SORCERER_METAMAGIC_LEARN_COUNTS = {3: 2, 10: 1}


def _sorcerer_maximum_spell_rank(level: int) -> int:
    return max(FULL_CASTER_SPELL_SLOTS[level], default=0)


def _sorcerer_ranked_spells(level: int) -> tuple[str, ...]:
    maximum_rank = _sorcerer_maximum_spell_rank(level)
    return tuple(
        spell_id
        for spell_id, rank in SORCERER_SPELL_RANKS.items()
        if 0 < rank <= maximum_rank
    )


def _sorcerer_choices(level: int) -> tuple[ClassChoiceDefinition, ...]:
    rows: list[ClassChoiceDefinition] = []
    if level == 1:
        rows.append(ClassChoiceDefinition(
            "class.sorcerer.level_1.subclass",
            (1,),
            (CharacterSubclass.DRACONIC_BLOODLINE.value,),
        ))
    cantrip_count = _SORCERER_CANTRIP_LEARN_COUNTS.get(level)
    if cantrip_count is not None:
        rows.append(ClassChoiceDefinition(
            f"class.sorcerer.level_{level}.cantrips",
            (cantrip_count,),
            tuple(
                spell_id
                for spell_id, rank in SORCERER_SPELL_RANKS.items()
                if rank == 0
            ),
        ))
    spell_count = _SORCERER_SPELL_LEARN_COUNTS.get(level)
    if spell_count is not None:
        rows.append(ClassChoiceDefinition(
            f"class.sorcerer.level_{level}.spell_known",
            (spell_count,),
            _sorcerer_ranked_spells(level),
        ))
    if level > 1:
        rows.append(ClassChoiceDefinition(
            f"class.sorcerer.level_{level}.spell_replacement",
            (2,),
            _sorcerer_ranked_spells(level),
        ))
    metamagic_count = _SORCERER_METAMAGIC_LEARN_COUNTS.get(level)
    if metamagic_count is not None:
        rows.append(ClassChoiceDefinition(
            f"class.sorcerer.level_{level}.metamagic",
            (metamagic_count,),
            SORCERER_METAMAGIC_OPTIONS,
        ))
    if level in SORCERER_ASI_LEVELS:
        rows.append(ClassChoiceDefinition(
            f"class.sorcerer.level_{level}.asi_or_feat",
            (1, 2),
            SORCERER_ASI_VALUES,
        ))
    return tuple(rows)


def _draconic_choices(level: int) -> tuple[ClassChoiceDefinition, ...]:
    if level != 1:
        return ()
    return (ClassChoiceDefinition(
        "subclass.sorcerer.draconic_bloodline.level_1.ancestry",
        (1,),
        tuple(SORCERER_ANCESTRY_DAMAGE_TYPES),
    ),)


SORCERER_DEFINITION = SorcererDefinition(
    hit_die=6,
    first_class_proficiencies=SORCERER_FIRST_CLASS_PROFICIENCIES,
    multiclass_proficiencies=(),
    saving_throws=SORCERER_SAVING_THROWS,
    class_skills=SORCERER_CLASS_SKILLS,
    starting_equipment=SORCERER_STARTING_EQUIPMENT,
    spellcasting_source_id="class.sorcerer.spellcasting",
    spellcasting_ability="charisma",
    spell_ranks=SORCERER_SPELL_RANKS,
    levels=tuple(
        ClassLevelDefinition(
            level,
            _SORCERER_FEATURES.get(level, ()),
            _sorcerer_choices(level),
        )
        for level in range(1, 21)
    ),
    draconic_levels=tuple(
        ClassLevelDefinition(
            level,
            _DRACONIC_FEATURES.get(level, ()),
            _draconic_choices(level),
        )
        for level in range(1, 21)
    ),
)


def _choice_values(level: AppliedClassLevel) -> dict[str, tuple[str, ...]]:
    choice_ids = tuple(choice.choice_id for choice in level.choices)
    if len(choice_ids) != len(set(choice_ids)):
        raise ValueError("class level choices contain duplicate IDs")
    return {choice.choice_id: choice.values for choice in level.choices}


def _parse_asi(values: tuple[str, ...]) -> tuple[
    tuple[tuple[AbilityName, int], ...],
    str | None,
]:
    if values == ("feat.lucky",):
        return (), "feat.lucky"
    parsed: list[tuple[AbilityName, int]] = []
    for value in values:
        parts = value.split(".")
        if len(parts) != 3 or parts[0] != "ability_score":
            raise ValueError("ASI choice must contain direct ability-score values")
        ability = parts[1]
        if ability not in {
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        }:
            raise ValueError(f"unsupported ASI ability {ability!r}")
        amount = int(parts[2])
        parsed.append((ability, amount))
    if len(parsed) == 1 and parsed[0][1] == 2:
        return tuple(parsed), None
    if (
        len(parsed) == 2
        and all(amount == 1 for _, amount in parsed)
        and parsed[0][0] != parsed[1][0]
    ):
        return tuple(parsed), None
    raise ValueError("ASI must be one +2, two distinct +1 values, or feat.lucky")


def resolve_fighter_level(
    level: AppliedClassLevel,
    applied_levels: tuple[AppliedClassLevel, ...],
    *,
    initial_first_class: bool | None = None,
) -> ResolvedFighterLevel:
    """Validate one next Fighter/Champion row without touching engine state."""
    if level.class_id is not CharacterClass.FIGHTER:
        raise ValueError("Fighter resolver received another class")
    if level.character_level != len(applied_levels) + 1:
        raise ValueError("character levels must be applied in exact order")
    fighter_levels = tuple(
        row for row in applied_levels if row.class_id is CharacterClass.FIGHTER
    )
    expected_class_level = len(fighter_levels) + 1
    if level.resulting_class_level != expected_class_level:
        raise ValueError("Fighter levels must be applied in exact order")
    if level.step_id != f"class.fighter.level_{expected_class_level}":
        raise ValueError("Fighter step_id does not match its resulting level")

    if expected_class_level < 3:
        if level.subclass_id is not None:
            raise ValueError("Champion cannot be selected before Fighter level 3")
    elif level.subclass_id is not CharacterSubclass.CHAMPION:
        raise ValueError("the implemented Fighter line requires Champion at level 3")

    inferred_first_class = expected_class_level == 1 and level.character_level == 1
    first_class_entry = (
        inferred_first_class
        if initial_first_class is None
        else initial_first_class
    )
    if first_class_entry and not inferred_first_class:
        raise ValueError("first-class Fighter entry must be character level one")
    expected_choices: list[ClassChoiceDefinition] = []
    if expected_class_level == 1 and first_class_entry:
        expected_choices.extend((
            ClassChoiceDefinition(
                "class.fighter.first_class.starting_equipment",
                (1,),
                FIGHTER_STARTING_EQUIPMENT,
            ),
            ClassChoiceDefinition(
                "class.fighter.proficiencies.skills",
                (2,),
                tuple(FIGHTER_CLASS_SKILLS),
            ),
        ))
    expected_choices.extend(FIGHTER_DEFINITION.levels[expected_class_level - 1].choices)
    if level.subclass_id is CharacterSubclass.CHAMPION:
        expected_choices.extend(
            FIGHTER_DEFINITION.champion_levels[expected_class_level - 1].choices,
        )

    choices = _choice_values(level)
    expected_ids = tuple(row.choice_id for row in expected_choices)
    if tuple(choices) != expected_ids:
        raise ValueError(
            "Fighter level choices must match the exact authored order: "
            f"{expected_ids!r}",
        )
    for requirement in expected_choices:
        values = choices[requirement.choice_id]
        if len(values) not in requirement.selections:
            raise ValueError(
                f"{requirement.choice_id} requires {requirement.selections!r} selections",
            )
        if any(value not in requirement.allowed_values for value in values):
            raise ValueError(f"{requirement.choice_id} contains an illegal value")

    skills = tuple(choices.get("class.fighter.proficiencies.skills", ()))
    equipment = choices.get("class.fighter.first_class.starting_equipment", ())
    style_choice_id = (
        "class.fighter.level_1.fighting_style"
        if expected_class_level == 1
        else "subclass.fighter.champion.level_10.fighting_style"
        if expected_class_level == 10
        else None
    )
    style = choices[style_choice_id][0] if style_choice_id is not None else None
    if style is not None:
        prior_styles = {
            value
            for row in fighter_levels
            for choice in row.choices
            if choice.choice_id.endswith("fighting_style")
            for value in choice.values
        }
        if style in prior_styles:
            raise ValueError("a Fighter cannot select the same fighting style twice")

    ability_increases: tuple[tuple[AbilityName, int], ...] = ()
    feat_id: str | None = None
    if expected_class_level in FIGHTER_ASI_LEVELS:
        ability_increases, feat_id = _parse_asi(
            choices[f"class.fighter.level_{expected_class_level}.asi_or_feat"],
        )
        if feat_id is not None and any(
            feat_id in choice.values
            for row in applied_levels
            for choice in row.choices
        ):
            raise ValueError("feat.lucky cannot be selected more than once")

    feature_ids = (
        *FIGHTER_DEFINITION.levels[expected_class_level - 1].feature_ids,
        *(
            FIGHTER_DEFINITION.champion_levels[
                expected_class_level - 1
            ].feature_ids
            if level.subclass_id is CharacterSubclass.CHAMPION
            else ()
        ),
        *((style,) if style is not None else ()),
        *((feat_id,) if feat_id is not None else ()),
    )
    return ResolvedFighterLevel(
        level=level,
        first_class_entry=first_class_entry,
        proficiencies=(
            FIGHTER_FIRST_CLASS_PROFICIENCIES
            if first_class_entry
            else FIGHTER_MULTICLASS_PROFICIENCIES
            if expected_class_level == 1
            else ()
        ),
        saving_throws=FIGHTER_SAVING_THROWS if first_class_entry else (),
        skills=skills,
        starting_equipment_id=equipment[0] if equipment else None,
        fighting_style_id=style,
        ability_increases=ability_increases,
        feat_id=feat_id,
        feature_ids=feature_ids,
    )


def resolve_barbarian_level(
    level: AppliedClassLevel,
    applied_levels: tuple[AppliedClassLevel, ...],
    *,
    initial_first_class: bool | None = None,
) -> ResolvedBarbarianLevel:
    """Validate one next Barbarian/Berserker row without engine mutation."""
    if level.class_id is not CharacterClass.BARBARIAN:
        raise ValueError("Barbarian resolver received another class")
    if level.character_level != len(applied_levels) + 1:
        raise ValueError("character levels must be applied in exact order")
    barbarian_levels = tuple(
        row
        for row in applied_levels
        if row.class_id is CharacterClass.BARBARIAN
    )
    expected_class_level = len(barbarian_levels) + 1
    if level.resulting_class_level != expected_class_level:
        raise ValueError("Barbarian levels must be applied in exact order")
    if level.step_id != f"class.barbarian.level_{expected_class_level}":
        raise ValueError("Barbarian step_id does not match its resulting level")

    if expected_class_level < 3:
        if level.subclass_id is not None:
            raise ValueError("Berserker cannot be selected before Barbarian level 3")
    elif level.subclass_id is not CharacterSubclass.BERSERKER:
        raise ValueError("the implemented Barbarian line requires Berserker at level 3")

    inferred_first_class = expected_class_level == 1 and level.character_level == 1
    first_class_entry = (
        inferred_first_class
        if initial_first_class is None
        else initial_first_class
    )
    if first_class_entry and not inferred_first_class:
        raise ValueError("first-class Barbarian entry must be character level one")
    expected_choices: list[ClassChoiceDefinition] = []
    if first_class_entry:
        expected_choices.extend((
            ClassChoiceDefinition(
                "class.barbarian.first_class.starting_equipment",
                (1,),
                BARBARIAN_STARTING_EQUIPMENT,
            ),
            ClassChoiceDefinition(
                "class.barbarian.proficiencies.skills",
                (2,),
                tuple(BARBARIAN_CLASS_SKILLS),
            ),
        ))
    expected_choices.extend(
        BARBARIAN_DEFINITION.levels[expected_class_level - 1].choices,
    )

    choices = _choice_values(level)
    expected_ids = tuple(row.choice_id for row in expected_choices)
    if tuple(choices) != expected_ids:
        raise ValueError(
            "Barbarian level choices must match the exact authored order: "
            f"{expected_ids!r}",
        )
    for requirement in expected_choices:
        values = choices[requirement.choice_id]
        if len(values) not in requirement.selections:
            raise ValueError(
                f"{requirement.choice_id} requires "
                f"{requirement.selections!r} selections",
            )
        if any(value not in requirement.allowed_values for value in values):
            raise ValueError(f"{requirement.choice_id} contains an illegal value")

    ability_increases: tuple[tuple[AbilityName, int], ...] = ()
    feat_id: str | None = None
    if expected_class_level in BARBARIAN_ASI_LEVELS:
        ability_increases, feat_id = _parse_asi(
            choices[f"class.barbarian.level_{expected_class_level}.asi_or_feat"],
        )
        if feat_id is not None and any(
            feat_id in choice.values
            for row in applied_levels
            for choice in row.choices
        ):
            raise ValueError("feat.lucky cannot be selected more than once")

    skills = tuple(choices.get("class.barbarian.proficiencies.skills", ()))
    equipment = choices.get(
        "class.barbarian.first_class.starting_equipment",
        (),
    )
    feature_ids = (
        *BARBARIAN_DEFINITION.levels[
            expected_class_level - 1
        ].feature_ids,
        *(
            BARBARIAN_DEFINITION.berserker_levels[
                expected_class_level - 1
            ].feature_ids
            if level.subclass_id is CharacterSubclass.BERSERKER
            else ()
        ),
        *((feat_id,) if feat_id is not None else ()),
    )
    return ResolvedBarbarianLevel(
        level=level,
        first_class_entry=first_class_entry,
        proficiencies=(
            BARBARIAN_FIRST_CLASS_PROFICIENCIES
            if first_class_entry
            else BARBARIAN_MULTICLASS_PROFICIENCIES
            if expected_class_level == 1
            else ()
        ),
        saving_throws=BARBARIAN_SAVING_THROWS if first_class_entry else (),
        skills=skills,
        starting_equipment_id=equipment[0] if equipment else None,
        ability_increases=ability_increases,
        feat_id=feat_id,
        feature_ids=feature_ids,
    )


def _known_sorcerer_spells(
    levels: tuple[AppliedClassLevel, ...],
) -> tuple[set[str], set[str]]:
    cantrips: set[str] = set()
    spells: set[str] = set()
    for row in levels:
        if row.class_id is not CharacterClass.SORCERER:
            continue
        for choice in row.choices:
            if choice.choice_id.endswith(".cantrips"):
                cantrips.update(choice.values)
            elif choice.choice_id.endswith(".spell_known"):
                spells.update(choice.values)
            elif choice.choice_id.endswith(".spell_replacement"):
                old_spell, new_spell = choice.values
                spells.remove(old_spell)
                spells.add(new_spell)
    return cantrips, spells


def resolve_sorcerer_level(
    level: AppliedClassLevel,
    applied_levels: tuple[AppliedClassLevel, ...],
    *,
    initial_first_class: bool | None = None,
) -> ResolvedSorcererLevel:
    """Validate one next Sorcerer/Draconic row without engine mutation."""
    if level.class_id is not CharacterClass.SORCERER:
        raise ValueError("Sorcerer resolver received another class")
    if level.character_level != len(applied_levels) + 1:
        raise ValueError("character levels must be applied in exact order")
    sorcerer_levels = tuple(
        row for row in applied_levels if row.class_id is CharacterClass.SORCERER
    )
    expected_class_level = len(sorcerer_levels) + 1
    if level.resulting_class_level != expected_class_level:
        raise ValueError("Sorcerer levels must be applied in exact order")
    if level.step_id != f"class.sorcerer.level_{expected_class_level}":
        raise ValueError("Sorcerer step_id does not match its resulting level")
    if level.subclass_id is not CharacterSubclass.DRACONIC_BLOODLINE:
        raise ValueError("the implemented Sorcerer line requires Draconic Bloodline")

    inferred_first_class = expected_class_level == 1 and level.character_level == 1
    first_class_entry = (
        inferred_first_class
        if initial_first_class is None
        else initial_first_class
    )
    if first_class_entry and not inferred_first_class:
        raise ValueError("first-class Sorcerer entry must be character level one")
    expected_choices: list[ClassChoiceDefinition] = []
    if first_class_entry:
        expected_choices.extend((
            ClassChoiceDefinition(
                "class.sorcerer.first_class.starting_equipment",
                (1,),
                SORCERER_STARTING_EQUIPMENT,
            ),
            ClassChoiceDefinition(
                "class.sorcerer.proficiencies.skills",
                (2,),
                tuple(SORCERER_CLASS_SKILLS),
            ),
        ))
    expected_choices.extend(
        SORCERER_DEFINITION.levels[expected_class_level - 1].choices,
    )
    expected_choices.extend(
        SORCERER_DEFINITION.draconic_levels[expected_class_level - 1].choices,
    )

    choices = _choice_values(level)
    required_ids = tuple(
        row.choice_id
        for row in expected_choices
        if not row.choice_id.endswith(".spell_replacement")
    )
    replacement_id = f"class.sorcerer.level_{expected_class_level}.spell_replacement"
    accepted_ids = tuple(row.choice_id for row in expected_choices)
    if tuple(choices) not in (
        required_ids,
        accepted_ids,
    ):
        raise ValueError(
            "Sorcerer level choices must match the exact authored order, with "
            f"only {replacement_id!r} optional: {accepted_ids!r}",
        )
    for requirement in expected_choices:
        values = choices.get(requirement.choice_id)
        if values is None:
            if requirement.choice_id.endswith(".spell_replacement"):
                continue
            raise ValueError(f"missing Sorcerer choice {requirement.choice_id}")
        if len(values) not in requirement.selections:
            raise ValueError(
                f"{requirement.choice_id} requires "
                f"{requirement.selections!r} selections",
            )
        if any(value not in requirement.allowed_values for value in values):
            raise ValueError(f"{requirement.choice_id} contains an illegal value")

    prior_cantrips, prior_spells = _known_sorcerer_spells(applied_levels)
    cantrip_ids = choices.get(
        f"class.sorcerer.level_{expected_class_level}.cantrips",
        (),
    )
    spell_ids = choices.get(
        f"class.sorcerer.level_{expected_class_level}.spell_known",
        (),
    )
    if prior_cantrips.intersection(cantrip_ids):
        raise ValueError("Sorcerer cannot learn the same cantrip twice")
    if prior_spells.intersection(spell_ids):
        raise ValueError("Sorcerer cannot learn the same spell twice")

    replacement_values = choices.get(replacement_id)
    replacement: tuple[str, str] | None = None
    if replacement_values is not None:
        old_spell, new_spell = replacement_values
        if old_spell not in prior_spells:
            raise ValueError("Sorcerer replacement must name a currently known spell")
        if new_spell in prior_spells or new_spell in spell_ids:
            raise ValueError("Sorcerer replacement must learn a different spell")
        replacement = (old_spell, new_spell)

    metamagic_ids = choices.get(
        f"class.sorcerer.level_{expected_class_level}.metamagic",
        (),
    )
    prior_metamagic = {
        value
        for row in sorcerer_levels
        for choice in row.choices
        if choice.choice_id.endswith(".metamagic")
        for value in choice.values
    }
    if prior_metamagic.intersection(metamagic_ids):
        raise ValueError("Sorcerer cannot select the same Metamagic twice")

    ability_increases: tuple[tuple[AbilityName, int], ...] = ()
    feat_id: str | None = None
    if expected_class_level in SORCERER_ASI_LEVELS:
        ability_increases, feat_id = _parse_asi(
            choices[f"class.sorcerer.level_{expected_class_level}.asi_or_feat"],
        )
        if feat_id is not None and any(
            feat_id in choice.values
            for row in applied_levels
            for choice in row.choices
        ):
            raise ValueError("feat.lucky cannot be selected more than once")

    ancestry_id = next(
        (
            value
            for row in (*sorcerer_levels, level)
            for choice in row.choices
            if choice.choice_id.endswith(".ancestry")
            for value in choice.values
        ),
        None,
    )
    ancestry_damage_type = (
        SORCERER_ANCESTRY_DAMAGE_TYPES[ancestry_id]
        if ancestry_id is not None
        else None
    )
    skills = tuple(choices.get("class.sorcerer.proficiencies.skills", ()))
    equipment = choices.get(
        "class.sorcerer.first_class.starting_equipment",
        (),
    )
    feature_ids = (
        *SORCERER_DEFINITION.levels[expected_class_level - 1].feature_ids,
        *SORCERER_DEFINITION.draconic_levels[expected_class_level - 1].feature_ids,
        *metamagic_ids,
        *((ancestry_id,) if expected_class_level == 1 else ()),
        *((feat_id,) if feat_id is not None else ()),
    )
    slots = FULL_CASTER_SPELL_SLOTS[expected_class_level]
    return ResolvedSorcererLevel(
        level=level,
        first_class_entry=first_class_entry,
        proficiencies=(
            SORCERER_FIRST_CLASS_PROFICIENCIES if first_class_entry else ()
        ),
        saving_throws=SORCERER_SAVING_THROWS if first_class_entry else (),
        skills=skills,
        starting_equipment_id=equipment[0] if equipment else None,
        cantrip_ids=cantrip_ids,
        spell_ids=spell_ids,
        replacement=replacement,
        metamagic_ids=metamagic_ids,
        ancestry_id=ancestry_id,
        ancestry_damage_type=ancestry_damage_type,
        ability_increases=ability_increases,
        feat_id=feat_id,
        feature_ids=feature_ids,
        normal_spell_slots=tuple(sorted(slots.items())),
        maximum_spell_rank=max(slots, default=0),
    )


__all__ = [
    "BARBARIAN_ASI_LEVELS",
    "BARBARIAN_ASI_VALUES",
    "BARBARIAN_CLASS_SKILLS",
    "BARBARIAN_DEFINITION",
    "BARBARIAN_RETIRED_DECLARATION_IDS",
    "BARBARIAN_STARTING_EQUIPMENT",
    "BarbarianDefinition",
    "CHARACTER_RETIRED_DECLARATION_IDS",
    "ClassChoiceDefinition",
    "ClassLevelDefinition",
    "FIGHTER_ASI_LEVELS",
    "FIGHTER_ASI_VALUES",
    "FIGHTER_CLASS_SKILLS",
    "FIGHTER_DEFINITION",
    "FIGHTER_FIGHTING_STYLES",
    "FIGHTER_RETIRED_DECLARATION_IDS",
    "FIGHTER_STARTING_EQUIPMENT",
    "FighterDefinition",
    "ResolvedBarbarianLevel",
    "ResolvedFighterLevel",
    "ResolvedSorcererLevel",
    "SORCERER_ANCESTRY_DAMAGE_TYPES",
    "SORCERER_ASI_LEVELS",
    "SORCERER_ASI_VALUES",
    "SORCERER_CLASS_SKILLS",
    "SORCERER_DEFINITION",
    "SORCERER_METAMAGIC_OPTIONS",
    "SORCERER_RETIRED_DECLARATION_IDS",
    "SORCERER_SPELL_RANKS",
    "SORCERER_STARTING_EQUIPMENT",
    "SorcererDefinition",
    "resolve_barbarian_level",
    "resolve_fighter_level",
    "resolve_sorcerer_level",
]
