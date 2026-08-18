"""Cold direct-ID definitions for the authored class progressions.

This module is deliberately data-only.  It imports dependency-leaf enums and
dataclasses, never Entity, actions, blocks, builders, or the retired generic
content registry.
"""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional

from dnd.types.abilities import AbilityName, SkillName
from dnd.types.progression import (
    CasterProgression,
    CharacterClass,
    CharacterSubclass,
    ClassChoiceSelection,
    RitualPreparationPolicy,
)


@dataclass(frozen=True, slots=True)
class ClassLevelRequest:
    """One cold authored request to append a class level."""

    class_id: CharacterClass
    choices: tuple[ClassChoiceSelection, ...] = ()
    subclass_id: Optional[CharacterSubclass] = None
    step_id: Optional[str] = None


class ClassChoiceKind(str, Enum):
    """Closed authored choice families understood by level resolution."""

    STARTING_EQUIPMENT = "starting_equipment"
    CLASS_SKILL = "class_skill"
    FIGHTING_STYLE = "fighting_style"
    SUBCLASS = "subclass"
    ASI_OR_FEAT = "asi_or_feat"
    CANTRIP = "cantrip"
    SPELL_KNOWN = "spell_known"
    SPELL_REPLACEMENT = "spell_replacement"
    METAMAGIC = "metamagic"
    ELEMENTAL_ANCESTRY = "elemental_ancestry"


@dataclass(frozen=True, slots=True)
class AbilityPrerequisite:
    """One ability threshold used by multiclass validation."""

    ability: AbilityName
    minimum: int


@dataclass(frozen=True, slots=True)
class ClassChoiceDefinition:
    """Cardinality and direct semantic vocabulary for one level choice."""

    choice_id: str
    choice_kind: ClassChoiceKind
    minimum_selections: int
    maximum_selections: int
    allowed_values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClassLevelDefinition:
    """The authored grants and choices gained at one class level."""

    class_level: int
    automatic_grant_ids: tuple[str, ...] = ()
    choices: tuple[ClassChoiceDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class ClassDefinition:
    """Cold rules data for one complete class progression."""

    class_id: CharacterClass
    display_name: str
    description: str
    hit_die: int
    caster_progression: CasterProgression
    multiclass_prerequisites: tuple[AbilityPrerequisite, ...]
    multiclass_prerequisite_any: bool
    first_class_proficiencies: tuple[str, ...]
    multiclass_proficiencies: tuple[str, ...]
    saving_throw_proficiencies: tuple[AbilityName, ...]
    first_class_choices: tuple[ClassChoiceDefinition, ...]
    levels: tuple[ClassLevelDefinition, ...]
    subclass_ids: tuple[CharacterSubclass, ...]
    spellcasting_source_id: Optional[str] = None
    spellcasting_ability: Optional[AbilityName] = None
    ritual_policy: RitualPreparationPolicy = RitualPreparationPolicy.NONE
    spell_entitlements: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class SubclassDefinition:
    """Cold rules data for one authored subclass progression."""

    subclass_id: CharacterSubclass
    parent_class_id: CharacterClass
    display_name: str
    description: str
    levels: tuple[ClassLevelDefinition, ...]


_ASI_VALUES = tuple(
    f"ability.{ability.value}:+{amount}"
    for ability in AbilityName
    for amount in (1, 2)
) + ("feat.lucky",)

_FIGHTER_STYLES = (
    "class_feature.fighter.fighting_style.archery",
    "class_feature.fighter.fighting_style.defense",
    "class_feature.fighter.fighting_style.dueling",
    "class_feature.fighter.fighting_style.great_weapon_fighting",
    "class_feature.fighter.fighting_style.protection",
    "class_feature.fighter.fighting_style.two_weapon_fighting",
)

_FIGHTER_SKILLS = tuple(
    f"skill.{skill.value}"
    for skill in (
        SkillName.ACROBATICS,
        SkillName.ANIMAL_HANDLING,
        SkillName.ATHLETICS,
        SkillName.HISTORY,
        SkillName.INSIGHT,
        SkillName.INTIMIDATION,
        SkillName.PERCEPTION,
        SkillName.SURVIVAL,
    )
)

_BARBARIAN_SKILLS = tuple(
    f"skill.{skill.value}"
    for skill in (
        SkillName.ANIMAL_HANDLING,
        SkillName.ATHLETICS,
        SkillName.INTIMIDATION,
        SkillName.NATURE,
        SkillName.PERCEPTION,
        SkillName.SURVIVAL,
    )
)

_SORCERER_SKILLS = tuple(
    f"skill.{skill.value}"
    for skill in (
        SkillName.ARCANA,
        SkillName.DECEPTION,
        SkillName.INSIGHT,
        SkillName.INTIMIDATION,
        SkillName.PERSUASION,
        SkillName.RELIGION,
    )
)

_SORCERER_SPELL_RANKS: Mapping[str, int] = MappingProxyType({
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


def _choice(
    choice_id: str,
    kind: ClassChoiceKind,
    allowed_values: tuple[str, ...],
    *,
    count: int = 1,
    minimum: Optional[int] = None,
) -> ClassChoiceDefinition:
    return ClassChoiceDefinition(
        choice_id=choice_id,
        choice_kind=kind,
        minimum_selections=count if minimum is None else minimum,
        maximum_selections=count,
        allowed_values=allowed_values,
    )


def _asi_choice(class_id: CharacterClass, level: int) -> ClassChoiceDefinition:
    return _choice(
        f"class.{class_id.value}.level_{level}.asi_or_feat",
        ClassChoiceKind.ASI_OR_FEAT,
        _ASI_VALUES,
        count=2,
        minimum=1,
    )


_FIGHTER_GRANTS: Mapping[int, tuple[str, ...]] = {
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
}


def _fighter_level(level: int) -> ClassLevelDefinition:
    choices: list[ClassChoiceDefinition] = []
    if level == 1:
        choices.append(_choice(
            "class.fighter.level_1.fighting_style",
            ClassChoiceKind.FIGHTING_STYLE,
            _FIGHTER_STYLES,
        ))
    if level == 3:
        choices.append(_choice(
            "class.fighter.level_3.subclass",
            ClassChoiceKind.SUBCLASS,
            ("subclass.fighter.champion",),
        ))
    if level in {4, 6, 8, 12, 14, 16, 19}:
        choices.append(_asi_choice(CharacterClass.FIGHTER, level))
    return ClassLevelDefinition(
        class_level=level,
        automatic_grant_ids=_FIGHTER_GRANTS.get(level, ()),
        choices=tuple(choices),
    )


_BARBARIAN_GRANTS: Mapping[int, tuple[str, ...]] = {
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
}


def _barbarian_level(level: int) -> ClassLevelDefinition:
    choices: list[ClassChoiceDefinition] = []
    if level == 3:
        choices.append(_choice(
            "class.barbarian.level_3.subclass",
            ClassChoiceKind.SUBCLASS,
            ("subclass.barbarian.berserker",),
        ))
    if level in {4, 8, 12, 16, 19}:
        choices.append(_asi_choice(CharacterClass.BARBARIAN, level))
    return ClassLevelDefinition(
        class_level=level,
        automatic_grant_ids=_BARBARIAN_GRANTS.get(level, ()),
        choices=tuple(choices),
    )


_CANTRIP_COUNTS = {1: 4, 4: 1, 10: 1}
_SPELL_COUNTS = {
    1: 2, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1,
    10: 1, 11: 1, 13: 1, 15: 1, 17: 1,
}
_METAMAGIC_COUNTS = {3: 2, 10: 1}
_METAMAGIC_IDS = (
    "class_feature.sorcerer.metamagic.distant_spell",
    "class_feature.sorcerer.metamagic.quickened_spell",
    "class_feature.sorcerer.metamagic.twinned_spell",
)


def _maximum_sorcerer_rank(level: int) -> int:
    return min(9, (level + 1) // 2)


def _sorcerer_level(level: int) -> ClassLevelDefinition:
    choices: list[ClassChoiceDefinition] = []
    if level == 1:
        choices.append(_choice(
            "class.sorcerer.level_1.subclass",
            ClassChoiceKind.SUBCLASS,
            ("subclass.sorcerer.draconic_bloodline",),
        ))
    if level in _CANTRIP_COUNTS:
        choices.append(_choice(
            f"class.sorcerer.level_{level}.cantrips",
            ClassChoiceKind.CANTRIP,
            tuple(
                spell_id for spell_id, rank in _SORCERER_SPELL_RANKS.items()
                if rank == 0
            ),
            count=_CANTRIP_COUNTS[level],
        ))
    if level in _SPELL_COUNTS:
        choices.append(_choice(
            f"class.sorcerer.level_{level}.spell_known",
            ClassChoiceKind.SPELL_KNOWN,
            tuple(
                spell_id for spell_id, rank in _SORCERER_SPELL_RANKS.items()
                if 0 < rank <= _maximum_sorcerer_rank(level)
            ),
            count=_SPELL_COUNTS[level],
        ))
    if level > 1:
        choices.append(ClassChoiceDefinition(
            choice_id=f"class.sorcerer.level_{level}.spell_replacement",
            choice_kind=ClassChoiceKind.SPELL_REPLACEMENT,
            minimum_selections=0,
            maximum_selections=1,
        ))
    if level in _METAMAGIC_COUNTS:
        choices.append(_choice(
            f"class.sorcerer.level_{level}.metamagic",
            ClassChoiceKind.METAMAGIC,
            _METAMAGIC_IDS,
            count=_METAMAGIC_COUNTS[level],
        ))
    if level in {4, 8, 12, 16, 19}:
        choices.append(_asi_choice(CharacterClass.SORCERER, level))
    grants = (
        ("class_feature.sorcerer.sorcery_points",) if level >= 2 else ()
    ) + (
        ("class_feature.sorcerer.sorcerous_restoration",)
        if level == 20 else ()
    )
    return ClassLevelDefinition(
        class_level=level,
        automatic_grant_ids=grants,
        choices=tuple(choices),
    )


FIGHTER_DEFINITION = ClassDefinition(
    class_id=CharacterClass.FIGHTER,
    display_name="Fighter",
    description=(
        "A martial class built around Fighting Style, Second Wind, Action "
        "Surge, and progressively stronger Attack actions."
    ),
    hit_die=10,
    caster_progression=CasterProgression.NON_CASTER,
    multiclass_prerequisites=(
        AbilityPrerequisite(AbilityName.DEXTERITY, 13),
        AbilityPrerequisite(AbilityName.STRENGTH, 13),
    ),
    multiclass_prerequisite_any=True,
    first_class_proficiencies=(
        "armor.heavy", "armor.light", "armor.medium", "shield.shield",
        "weapon.martial", "weapon.simple",
    ),
    multiclass_proficiencies=(
        "armor.light", "armor.medium", "shield.shield",
        "weapon.martial", "weapon.simple",
    ),
    saving_throw_proficiencies=(AbilityName.CONSTITUTION, AbilityName.STRENGTH),
    first_class_choices=(
        _choice(
            "class.fighter.first_class.starting_equipment",
            ClassChoiceKind.STARTING_EQUIPMENT,
            tuple(f"starting_equipment.fighter.{value}" for value in (
                "archery", "dual_wield", "greatsword", "sword_shield",
            )),
        ),
        _choice(
            "class.fighter.proficiencies.skills",
            ClassChoiceKind.CLASS_SKILL,
            _FIGHTER_SKILLS,
            count=2,
        ),
    ),
    levels=tuple(_fighter_level(level) for level in range(1, 21)),
    subclass_ids=(CharacterSubclass.CHAMPION,),
)

BARBARIAN_DEFINITION = ClassDefinition(
    class_id=CharacterClass.BARBARIAN,
    display_name="Barbarian",
    description=(
        "A martial class built around Rage, resilience, mobility, and brutal "
        "weapon criticals."
    ),
    hit_die=12,
    caster_progression=CasterProgression.NON_CASTER,
    multiclass_prerequisites=(AbilityPrerequisite(AbilityName.STRENGTH, 13),),
    multiclass_prerequisite_any=False,
    first_class_proficiencies=(
        "armor.light", "armor.medium", "shield.shield",
        "weapon.martial", "weapon.simple",
    ),
    multiclass_proficiencies=(
        "shield.shield", "weapon.martial", "weapon.simple",
    ),
    saving_throw_proficiencies=(AbilityName.CONSTITUTION, AbilityName.STRENGTH),
    first_class_choices=(
        _choice(
            "class.barbarian.first_class.starting_equipment",
            ClassChoiceKind.STARTING_EQUIPMENT,
            tuple(f"starting_equipment.barbarian.{value}" for value in (
                "dual_axes", "greataxe", "sword_shield",
            )),
        ),
        _choice(
            "class.barbarian.proficiencies.skills",
            ClassChoiceKind.CLASS_SKILL,
            _BARBARIAN_SKILLS,
            count=2,
        ),
    ),
    levels=tuple(_barbarian_level(level) for level in range(1, 21)),
    subclass_ids=(CharacterSubclass.BERSERKER,),
)

SORCERER_DEFINITION = ClassDefinition(
    class_id=CharacterClass.SORCERER,
    display_name="Sorcerer",
    description=(
        "A Charisma-based full caster with Sorcery Points and selected "
        "Metamagic."
    ),
    hit_die=6,
    caster_progression=CasterProgression.FULL_CASTER,
    multiclass_prerequisites=(AbilityPrerequisite(AbilityName.CHARISMA, 13),),
    multiclass_prerequisite_any=False,
    first_class_proficiencies=(
        "weapon.dagger", "weapon.dart", "weapon.light_crossbow",
        "weapon.quarterstaff", "weapon.sling",
    ),
    multiclass_proficiencies=(),
    saving_throw_proficiencies=(AbilityName.CHARISMA, AbilityName.CONSTITUTION),
    first_class_choices=(
        _choice(
            "class.sorcerer.first_class.starting_equipment",
            ClassChoiceKind.STARTING_EQUIPMENT,
            (
                "starting_equipment.sorcerer.dagger",
                "starting_equipment.sorcerer.quarterstaff",
            ),
        ),
        _choice(
            "class.sorcerer.proficiencies.skills",
            ClassChoiceKind.CLASS_SKILL,
            _SORCERER_SKILLS,
            count=2,
        ),
    ),
    levels=tuple(_sorcerer_level(level) for level in range(1, 21)),
    subclass_ids=(CharacterSubclass.DRACONIC_BLOODLINE,),
    spellcasting_source_id="class.sorcerer.spellcasting",
    spellcasting_ability=AbilityName.CHARISMA,
    ritual_policy=RitualPreparationPolicy.NONE,
    spell_entitlements=tuple(_SORCERER_SPELL_RANKS.items()),
)

CHAMPION_DEFINITION = SubclassDefinition(
    subclass_id=CharacterSubclass.CHAMPION,
    parent_class_id=CharacterClass.FIGHTER,
    display_name="Champion",
    description=(
        "A Fighter archetype with expanded criticals, athletic talent, an "
        "additional Fighting Style, and Survivor."
    ),
    levels=tuple(
        ClassLevelDefinition(
            class_level=level,
            automatic_grant_ids={
                3: ("class_feature.fighter.improved_critical",),
                7: ("class_feature.fighter.remarkable_athlete",),
                15: ("class_feature.fighter.superior_critical",),
                18: ("class_feature.fighter.survivor",),
            }.get(level, ()),
            choices=(
                _choice(
                    "subclass.fighter.champion.level_10.fighting_style",
                    ClassChoiceKind.FIGHTING_STYLE,
                    _FIGHTER_STYLES,
                ),
            ) if level == 10 else (),
        )
        for level in range(1, 21)
    ),
)

BERSERKER_DEFINITION = SubclassDefinition(
    subclass_id=CharacterSubclass.BERSERKER,
    parent_class_id=CharacterClass.BARBARIAN,
    display_name="Berserker",
    description=(
        "A Barbarian path granting Frenzy, Mindless Rage, Intimidating "
        "Presence, and Retaliation."
    ),
    levels=tuple(
        ClassLevelDefinition(
            class_level=level,
            automatic_grant_ids={
                3: ("class_feature.barbarian.frenzy",),
                6: ("class_feature.barbarian.mindless_rage",),
                10: ("class_feature.barbarian.intimidating_presence",),
                14: ("class_feature.barbarian.retaliation",),
            }.get(level, ()),
        )
        for level in range(1, 21)
    ),
)

_DRACONIC_ANCESTRY_IDS = tuple(
    f"class_feature.sorcerer.draconic_ancestry.{ancestry}"
    for ancestry in (
        "black", "blue", "brass", "bronze", "copper", "gold", "green",
        "red", "silver", "white",
    )
)

DRACONIC_BLOODLINE_DEFINITION = SubclassDefinition(
    subclass_id=CharacterSubclass.DRACONIC_BLOODLINE,
    parent_class_id=CharacterClass.SORCERER,
    display_name="Draconic Bloodline",
    description=(
        "A Sorcerous Origin with a selected dragon ancestry, resilient "
        "scales, elemental affinity, wings, and draconic presence."
    ),
    levels=tuple(
        ClassLevelDefinition(
            class_level=level,
            automatic_grant_ids={
                1: ("class_feature.sorcerer.draconic_resilience",),
                6: ("class_feature.sorcerer.elemental_affinity",),
                14: ("class_feature.sorcerer.dragon_wings",),
                18: ("class_feature.sorcerer.draconic_presence",),
            }.get(level, ()),
            choices=(
                _choice(
                    "subclass.sorcerer.draconic_bloodline.level_1.ancestry",
                    ClassChoiceKind.ELEMENTAL_ANCESTRY,
                    _DRACONIC_ANCESTRY_IDS,
                ),
            ) if level == 1 else (),
        )
        for level in range(1, 21)
    ),
)

CLASS_DEFINITIONS: Mapping[CharacterClass, ClassDefinition] = MappingProxyType({
    CharacterClass.BARBARIAN: BARBARIAN_DEFINITION,
    CharacterClass.FIGHTER: FIGHTER_DEFINITION,
    CharacterClass.SORCERER: SORCERER_DEFINITION,
})

SUBCLASS_DEFINITIONS: Mapping[CharacterSubclass, SubclassDefinition] = (
    MappingProxyType({
        CharacterSubclass.BERSERKER: BERSERKER_DEFINITION,
        CharacterSubclass.CHAMPION: CHAMPION_DEFINITION,
        CharacterSubclass.DRACONIC_BLOODLINE: DRACONIC_BLOODLINE_DEFINITION,
    })
)


__all__ = [
    "BARBARIAN_DEFINITION",
    "BERSERKER_DEFINITION",
    "CHAMPION_DEFINITION",
    "CLASS_DEFINITIONS",
    "DRACONIC_BLOODLINE_DEFINITION",
    "FIGHTER_DEFINITION",
    "SORCERER_DEFINITION",
    "SUBCLASS_DEFINITIONS",
    "AbilityPrerequisite",
    "ClassChoiceDefinition",
    "ClassChoiceKind",
    "ClassDefinition",
    "ClassLevelDefinition",
    "ClassLevelRequest",
    "SubclassDefinition",
]
