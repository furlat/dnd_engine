"""Cold direct definitions for the four authored premade characters."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from dnd.content.characters.class_definitions import ClassLevelRequest
from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.types.abilities import AbilityName
from dnd.types.creatures import Background, Species
from dnd.types.equipment import BodyPart, WeaponSlot
from dnd.types.languages import SrdLanguageId
from dnd.types.progression import (
    AppliedOriginState,
    CharacterClass,
    ClassChoiceSelection,
    OriginChoiceSelection,
)


@dataclass(frozen=True, slots=True)
class PremadeCharacterDefinition:
    """Complete server/DB-independent authored character build."""

    premade_id: str
    display_name: str
    species: Species
    background: Background
    origin_state: AppliedOriginState
    level_requests: tuple[ClassLevelRequest, ...]
    body_semantics: tuple[tuple[str, str], ...]
    supplemental_loadout: tuple[ItemLoadoutEntry, ...]

    def __post_init__(self) -> None:
        if not self.premade_id.startswith("hero."):
            raise ValueError("premade_id must be a hero semantic ID")
        if not self.level_requests:
            raise ValueError("premade character requires at least one level")
        keys = tuple(key for key, _value in self.body_semantics)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("body semantics must have unique ordered keys")


def _human_state(
    scores: tuple[int, int, int, int, int, int],
    bonuses: tuple[tuple[AbilityName, int], ...],
) -> AppliedOriginState:
    return AppliedOriginState(
        base_ability_scores=tuple(zip(AbilityName, scores, strict=True)),
        flexible_ability_bonuses=bonuses,
        choices=(OriginChoiceSelection(
            "species.human.additional_language",
            (SrdLanguageId.DRACONIC.value,),
        ),),
    )


def _body_semantics(
    *,
    skin: str,
    hair: str,
    head: str,
    build: str,
    stature: str,
    beard: bool,
) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((
        ("body.form", "humanoid"),
        ("body.build", build),
        ("body.stature", stature),
        ("head.hair_style", head),
        ("palette.skin", skin),
        ("palette.hair", hair),
        ("beard.presence", "present" if beard else "absent"),
        ("palette.beard", hair if beard else "none"),
    )))


def _choice(choice_id: str, *values: str) -> ClassChoiceSelection:
    return ClassChoiceSelection(choice_id, values)


def _fighter_levels(level: int = 5) -> tuple[ClassLevelRequest, ...]:
    rows = [
        ClassLevelRequest(CharacterClass.FIGHTER, choices=(
            _choice(
                "class.fighter.first_class.starting_equipment",
                "starting_equipment.fighter.sword_shield",
            ),
            _choice(
                "class.fighter.proficiencies.skills",
                "skill.athletics",
                "skill.perception",
            ),
            _choice(
                "class.fighter.level_1.fighting_style",
                "class_feature.fighter.fighting_style.dueling",
            ),
        )),
        ClassLevelRequest(CharacterClass.FIGHTER),
        ClassLevelRequest(CharacterClass.FIGHTER, choices=(
            _choice(
                "class.fighter.level_3.subclass",
                "subclass.fighter.champion",
            ),
        )),
        ClassLevelRequest(CharacterClass.FIGHTER, choices=(
            _choice(
                "class.fighter.level_4.asi_or_feat",
                "ability.strength:+2",
            ),
        )),
        ClassLevelRequest(CharacterClass.FIGHTER),
    ]
    return tuple(rows[:level])


def _barbarian_levels() -> tuple[ClassLevelRequest, ...]:
    return (
        ClassLevelRequest(CharacterClass.BARBARIAN, choices=(
            _choice(
                "class.barbarian.first_class.starting_equipment",
                "starting_equipment.barbarian.greataxe",
            ),
            _choice(
                "class.barbarian.proficiencies.skills",
                "skill.athletics",
                "skill.perception",
            ),
        )),
        ClassLevelRequest(CharacterClass.BARBARIAN),
        ClassLevelRequest(CharacterClass.BARBARIAN, choices=(
            _choice(
                "class.barbarian.level_3.subclass",
                "subclass.barbarian.berserker",
            ),
        )),
        ClassLevelRequest(CharacterClass.BARBARIAN, choices=(
            _choice(
                "class.barbarian.level_4.asi_or_feat",
                "ability.strength:+2",
            ),
        )),
        ClassLevelRequest(CharacterClass.BARBARIAN),
    )


def _sorcerer_levels(*, first_class: bool) -> tuple[ClassLevelRequest, ...]:
    first_choices = []
    if first_class:
        first_choices.extend((
            _choice(
                "class.sorcerer.first_class.starting_equipment",
                "starting_equipment.sorcerer.dagger",
            ),
            _choice(
                "class.sorcerer.proficiencies.skills",
                "skill.arcana",
                "skill.deception",
            ),
        ))
    first_choices.extend((
        _choice(
            "class.sorcerer.level_1.subclass",
            "subclass.sorcerer.draconic_bloodline",
        ),
        _choice(
            "class.sorcerer.level_1.cantrips",
            *(
                (
                    "spell.acid_splash",
                    "spell.chill_touch",
                    "spell.fire_bolt",
                    "spell.ray_of_frost",
                )
                if first_class
                else (
                    "spell.fire_bolt",
                    "spell.light",
                    "spell.ray_of_frost",
                    "spell.shocking_grasp",
                )
            ),
        ),
        _choice(
            "class.sorcerer.level_1.spell_known",
            *(
                ("spell.burning_hands", "spell.magic_missile")
                if first_class
                else ("spell.magic_missile", "spell.shield")
            ),
        ),
        _choice(
            "subclass.sorcerer.draconic_bloodline.level_1.ancestry",
            "class_feature.sorcerer.draconic_ancestry.red",
        ),
    ))
    return (
        ClassLevelRequest(CharacterClass.SORCERER, choices=tuple(first_choices)),
        ClassLevelRequest(CharacterClass.SORCERER, choices=(
            _choice(
                "class.sorcerer.level_2.spell_known",
                "spell.charm_person" if first_class else "spell.burning_hands",
            ),
        )),
        ClassLevelRequest(CharacterClass.SORCERER, choices=(
            _choice(
                "class.sorcerer.level_3.spell_known",
                "spell.scorching_ray",
            ),
            _choice(
                "class.sorcerer.level_3.metamagic",
                "class_feature.sorcerer.metamagic.quickened_spell",
                "class_feature.sorcerer.metamagic.twinned_spell",
            ),
        )),
        ClassLevelRequest(CharacterClass.SORCERER, choices=(
            _choice(
                "class.sorcerer.level_4.cantrips",
                "spell.light",
            ),
            _choice(
                "class.sorcerer.level_4.spell_known",
                "spell.hold_person",
            ),
            _choice(
                "class.sorcerer.level_4.asi_or_feat",
                "ability.charisma:+2",
            ),
        )),
        ClassLevelRequest(CharacterClass.SORCERER, choices=(
            _choice(
                "class.sorcerer.level_5.spell_known",
                "spell.fireball",
            ),
        )),
    )


_COMMON_SUPPLEMENT = (
    ItemLoadoutEntry("consumable.potion_haste"),
    ItemLoadoutEntry("consumable.healing_potion", quantity=2),
)

_FIGHTER_SUPPLEMENT = (
    ItemLoadoutEntry("apparel.leather_boots.brown", equipment_slot=BodyPart.FEET),
    *_COMMON_SUPPLEMENT,
    ItemLoadoutEntry("apparel.cloth_shoes"),
    ItemLoadoutEntry("apparel.iron_helmet.steel", equipment_slot=BodyPart.HEAD),
    ItemLoadoutEntry("weapon.handaxe"),
    ItemLoadoutEntry("weapon.javelin"),
    ItemLoadoutEntry("weapon.dagger"),
    ItemLoadoutEntry("armor.leather"),
)

_BARBARIAN_SUPPLEMENT = (
    *_COMMON_SUPPLEMENT,
    ItemLoadoutEntry("weapon.handaxe"),
    ItemLoadoutEntry("weapon.javelin"),
    ItemLoadoutEntry("weapon.dagger"),
    ItemLoadoutEntry("weapon.longsword"),
    ItemLoadoutEntry("shield.shield"),
    ItemLoadoutEntry("apparel.costume.pit_fighter_wrap", equipment_slot=BodyPart.BODY),
    ItemLoadoutEntry("apparel.leather_boots", equipment_slot=BodyPart.FEET),
    ItemLoadoutEntry("equipment.portable_torch"),
)

_SORCERER_SUPPLEMENT = (
    ItemLoadoutEntry("apparel.robes.red_mage", equipment_slot=BodyPart.BODY),
    ItemLoadoutEntry("apparel.cloth_shoes.red", equipment_slot=BodyPart.FEET),
    *_COMMON_SUPPLEMENT,
    ItemLoadoutEntry("apparel.robes.wizard"),
    ItemLoadoutEntry("apparel.cloth_shoes.blue"),
    ItemLoadoutEntry("apparel.wizard_hat.red", equipment_slot=BodyPart.HEAD),
    ItemLoadoutEntry("weapon.quarterstaff"),
    ItemLoadoutEntry("equipment.portable_torch"),
)


BARBARIAN_PREMADE = PremadeCharacterDefinition(
    premade_id="hero.barbarian_l5_berserker_torch",
    display_name="Berserker",
    species=Species.HUMAN,
    background=Background.ADVENTURER,
    origin_state=_human_state(
        (15, 13, 14, 8, 12, 10),
        ((AbilityName.STRENGTH, 2), (AbilityName.CONSTITUTION, 1)),
    ),
    level_requests=_barbarian_levels(),
    body_semantics=_body_semantics(
        skin="warm_tan", hair="sand", head="hair_17",
        build="broad", stature="tall", beard=False,
    ),
    supplemental_loadout=_BARBARIAN_SUPPLEMENT,
)

FIGHTER_PREMADE = PremadeCharacterDefinition(
    premade_id="hero.fighter_l5_shield_torch",
    display_name="Shield Fighter",
    species=Species.HUMAN,
    background=Background.ADVENTURER,
    origin_state=_human_state(
        (15, 14, 13, 10, 12, 8),
        ((AbilityName.STRENGTH, 2), (AbilityName.CONSTITUTION, 1)),
    ),
    level_requests=_fighter_levels(),
    body_semantics=_body_semantics(
        skin="light_tan", hair="auburn", head="hair_10",
        build="average", stature="average", beard=True,
    ),
    supplemental_loadout=(
        *_FIGHTER_SUPPLEMENT,
        ItemLoadoutEntry("weapon.longbow", equipment_slot=WeaponSlot.RANGED_MAIN),
        ItemLoadoutEntry("equipment.portable_torch"),
    ),
)

SORCERER_PREMADE = PremadeCharacterDefinition(
    premade_id="hero.sorcerer_l5_standard_torch",
    display_name="Draconic Sorcerer",
    species=Species.HUMAN,
    background=Background.ADVENTURER,
    origin_state=_human_state(
        (8, 14, 13, 10, 12, 15),
        ((AbilityName.CONSTITUTION, 1), (AbilityName.CHARISMA, 2)),
    ),
    level_requests=_sorcerer_levels(first_class=True),
    body_semantics=_body_semantics(
        skin="light_tan", hair="auburn", head="hair_22",
        build="slender", stature="short", beard=False,
    ),
    supplemental_loadout=_SORCERER_SUPPLEMENT,
)

SPELLBLADE_PREMADE = PremadeCharacterDefinition(
    premade_id="hero.fighter_2_sorcerer_3_spellblade",
    display_name="Draconic Spellblade",
    species=Species.HUMAN,
    background=Background.ADVENTURER,
    origin_state=_human_state(
        (15, 13, 13, 8, 9, 14),
        ((AbilityName.STRENGTH, 2), (AbilityName.CHARISMA, 1)),
    ),
    level_requests=(*_fighter_levels(2), *_sorcerer_levels(first_class=False)[:3]),
    body_semantics=FIGHTER_PREMADE.body_semantics,
    supplemental_loadout=(
        *(
            ItemLoadoutEntry(entry.item_id, entry.quantity)
            if entry.equipment_slot is BodyPart.HEAD
            else entry
            for entry in _FIGHTER_SUPPLEMENT
        ),
        ItemLoadoutEntry("apparel.spellblade_crown", equipment_slot=BodyPart.HEAD),
        ItemLoadoutEntry("equipment.portable_torch"),
    ),
)

PREMADE_CHARACTER_DEFINITIONS: Mapping[
    str,
    PremadeCharacterDefinition,
] = MappingProxyType({
    definition.premade_id: definition
    for definition in (
        BARBARIAN_PREMADE,
        FIGHTER_PREMADE,
        SORCERER_PREMADE,
        SPELLBLADE_PREMADE,
    )
})


__all__ = [
    "BARBARIAN_PREMADE",
    "FIGHTER_PREMADE",
    "PREMADE_CHARACTER_DEFINITIONS",
    "PremadeCharacterDefinition",
    "SORCERER_PREMADE",
    "SPELLBLADE_PREMADE",
]
