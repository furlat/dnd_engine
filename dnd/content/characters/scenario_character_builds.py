"""Direct character roots used by the authored in-process scenarios.

These functions translate a small authored parameter vocabulary into ordinary
origin and class-level values.  They do not own mutation: ``create_character``
and the entity progression transaction remain the only mutation boundary.
"""

import re
from types import MappingProxyType
from typing import Literal, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.content.characters.character_builds import create_character
from dnd.content.characters.class_definitions import (
    ClassLevelRequest,
    SORCERER_DEFINITION,
)
from dnd.content.characters.class_level_content import resolve_initial_level_steps
from dnd.entities.entity import Entity
from dnd.types.abilities import AbilityName
from dnd.types.creatures import Background, Species
from dnd.types.languages import SrdLanguageId
from dnd.types.progression import (
    AppliedOriginState,
    CharacterClass,
    ClassChoiceSelection,
    OriginChoiceSelection,
)


AbilityIncrease = tuple[AbilityName, Literal[1, 2]]


class BarbarianCharacterParameters(BaseModel):
    """Authored Barbarian scenario inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=1, ge=1, le=5)
    equipment_preset: Literal[
        "greataxe",
        "dual_axes",
        "sword_shield",
    ] = "greataxe"
    asi_4: tuple[AbilityIncrease, ...] = ()
    asi_8: tuple[AbilityIncrease, ...] = ()


class FighterCharacterParameters(BaseModel):
    """Authored Fighter scenario inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=1, ge=1, le=5)
    fighting_style: Literal[
        "archery",
        "defense",
        "dueling",
        "great_weapon",
        "protection",
        "two_weapon",
    ] = "defense"
    equipment_preset: Literal[
        "sword_shield",
        "greatsword",
        "dual_wield",
        "archery",
    ] = "sword_shield"
    asi_4: tuple[AbilityIncrease, ...] = ()
    asi_6: tuple[AbilityIncrease, ...] = ()
    asi_8: tuple[AbilityIncrease, ...] = ()


class SorcererCharacterParameters(BaseModel):
    """Authored Sorcerer scenario inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int = Field(default=1, ge=1, le=9)
    equipment_preset: Literal["dagger", "quarterstaff"] = "dagger"
    metamagic_choices: tuple[
        Literal["distant", "quickened", "twinned"],
        ...,
    ] = ()
    spell_names: tuple[str, ...] = ()
    asi_4: tuple[AbilityIncrease, ...] = ()
    asi_8: tuple[AbilityIncrease, ...] = ()


_FIGHTER_STYLE_IDS: Mapping[str, str] = MappingProxyType({
    "archery": "class_feature.fighter.fighting_style.archery",
    "defense": "class_feature.fighter.fighting_style.defense",
    "dueling": "class_feature.fighter.fighting_style.dueling",
    "great_weapon": "class_feature.fighter.fighting_style.great_weapon_fighting",
    "protection": "class_feature.fighter.fighting_style.protection",
    "two_weapon": "class_feature.fighter.fighting_style.two_weapon_fighting",
})

_SORCERER_SPELL_RANKS: Mapping[str, int] = MappingProxyType(
    dict(SORCERER_DEFINITION.spell_entitlements),
)
_SORCERER_LEARN_COUNTS = MappingProxyType({
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
})
_SORCERER_CANTRIP_COUNTS = MappingProxyType({1: 4, 4: 1, 10: 1})


def _choice(choice_id: str, *values: str) -> ClassChoiceSelection:
    return ClassChoiceSelection(choice_id=choice_id, values=values)


def _human_origin_state(class_id: CharacterClass) -> AppliedOriginState:
    if class_id is CharacterClass.FIGHTER:
        scores = (15, 14, 13, 10, 12, 8)
        bonuses = ((AbilityName.STRENGTH, 2), (AbilityName.CONSTITUTION, 1))
    elif class_id is CharacterClass.BARBARIAN:
        scores = (15, 13, 14, 8, 12, 10)
        bonuses = ((AbilityName.STRENGTH, 2), (AbilityName.CONSTITUTION, 1))
    else:
        scores = (8, 14, 13, 10, 12, 15)
        bonuses = ((AbilityName.CONSTITUTION, 1), (AbilityName.CHARISMA, 2))
    return AppliedOriginState(
        base_ability_scores=tuple(zip(AbilityName, scores, strict=True)),
        flexible_ability_bonuses=bonuses,
        choices=(OriginChoiceSelection(
            choice_id="species.human.additional_language",
            values=(SrdLanguageId.DRACONIC.value,),
        ),),
    )


def _asi_choice(
    class_id: CharacterClass,
    level: int,
    increases: tuple[AbilityIncrease, ...],
) -> ClassChoiceSelection:
    if not increases:
        default = (
            AbilityName.CHARISMA
            if class_id is CharacterClass.SORCERER
            else AbilityName.STRENGTH
        )
        increases = ((default, 2),)
    if sum(amount for _ability, amount in increases) != 2:
        raise ValueError("an ability score improvement must grant exactly two points")
    if len({ability for ability, _amount in increases}) != len(increases):
        raise ValueError("an ability score improvement cannot repeat an ability")
    return _choice(
        f"class.{class_id.value}.level_{level}.asi_or_feat",
        *(f"ability.{ability.value}:+{amount}" for ability, amount in increases),
    )


def _fighter_levels(
    parameters: FighterCharacterParameters,
) -> tuple[ClassLevelRequest, ...]:
    asi = {4: parameters.asi_4, 6: parameters.asi_6, 8: parameters.asi_8}
    rows: list[ClassLevelRequest] = []
    for level in range(1, parameters.level + 1):
        choices: list[ClassChoiceSelection] = []
        if level == 1:
            choices.extend((
                _choice(
                    "class.fighter.first_class.starting_equipment",
                    f"starting_equipment.fighter.{parameters.equipment_preset}",
                ),
                _choice(
                    "class.fighter.proficiencies.skills",
                    "skill.athletics",
                    "skill.perception",
                ),
                _choice(
                    "class.fighter.level_1.fighting_style",
                    _FIGHTER_STYLE_IDS[parameters.fighting_style],
                ),
            ))
        if level == 3:
            choices.append(_choice(
                "class.fighter.level_3.subclass",
                "subclass.fighter.champion",
            ))
        if level in {4, 6, 8}:
            choices.append(_asi_choice(CharacterClass.FIGHTER, level, asi[level]))
        rows.append(ClassLevelRequest(CharacterClass.FIGHTER, choices=tuple(choices)))
    return tuple(rows)


def _barbarian_levels(
    parameters: BarbarianCharacterParameters,
) -> tuple[ClassLevelRequest, ...]:
    asi = {4: parameters.asi_4, 8: parameters.asi_8}
    rows: list[ClassLevelRequest] = []
    for level in range(1, parameters.level + 1):
        choices: list[ClassChoiceSelection] = []
        if level == 1:
            choices.extend((
                _choice(
                    "class.barbarian.first_class.starting_equipment",
                    f"starting_equipment.barbarian.{parameters.equipment_preset}",
                ),
                _choice(
                    "class.barbarian.proficiencies.skills",
                    "skill.athletics",
                    "skill.perception",
                ),
            ))
        if level == 3:
            choices.append(_choice(
                "class.barbarian.level_3.subclass",
                "subclass.barbarian.berserker",
            ))
        if level in {4, 8}:
            choices.append(_asi_choice(CharacterClass.BARBARIAN, level, asi[level]))
        rows.append(ClassLevelRequest(CharacterClass.BARBARIAN, choices=tuple(choices)))
    return tuple(rows)


def _spell_id_from_name(name: str) -> str:
    spell_id = "spell." + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if spell_id not in _SORCERER_SPELL_RANKS:
        raise ValueError(f"unknown or non-Sorcerer spell {name!r}")
    return spell_id


def _sorcerer_spell_choices(
    parameters: SorcererCharacterParameters,
) -> dict[int, tuple[ClassChoiceSelection, ...]]:
    requested = tuple(_spell_id_from_name(name) for name in parameters.spell_names)
    if len(requested) != len(set(requested)):
        raise ValueError("Sorcerer spell names must be unique")
    entitlements = tuple(sorted(_SORCERER_SPELL_RANKS))
    requested_cantrips = [
        spell_id for spell_id in requested if _SORCERER_SPELL_RANKS[spell_id] == 0
    ]
    requested_cantrips.extend(
        spell_id
        for spell_id in entitlements
        if _SORCERER_SPELL_RANKS[spell_id] == 0
        and spell_id not in requested_cantrips
    )
    selected_cantrips = sorted(requested_cantrips[:4])
    requested_ranked = [
        spell_id for spell_id in requested if _SORCERER_SPELL_RANKS[spell_id] > 0
    ]
    selected_ranked: set[str] = set()
    choices: dict[int, tuple[ClassChoiceSelection, ...]] = {}
    for level in range(1, parameters.level + 1):
        rows: list[ClassChoiceSelection] = []
        cantrip_count = _SORCERER_CANTRIP_COUNTS.get(level)
        if cantrip_count is not None:
            if level == 1:
                selected = tuple(selected_cantrips)
            else:
                available = tuple(
                    spell_id
                    for spell_id in entitlements
                    if _SORCERER_SPELL_RANKS[spell_id] == 0
                    and spell_id not in selected_cantrips
                )
                selected = available[:cantrip_count]
                selected_cantrips.extend(selected)
            rows.append(_choice(
                f"class.sorcerer.level_{level}.cantrips",
                *selected,
            ))
        learn_count = _SORCERER_LEARN_COUNTS.get(level)
        if learn_count is not None:
            maximum_rank = min(9, (level + 1) // 2)
            requested_eligible = [
                spell_id
                for spell_id in requested_ranked
                if _SORCERER_SPELL_RANKS[spell_id] <= maximum_rank
                and spell_id not in selected_ranked
            ]
            requested_eligible.sort(key=lambda spell_id: (
                -_SORCERER_SPELL_RANKS[spell_id],
                requested_ranked.index(spell_id),
            ))
            fallback = [
                spell_id
                for spell_id in entitlements
                if 0 < _SORCERER_SPELL_RANKS[spell_id] <= maximum_rank
                and spell_id not in selected_ranked
                and spell_id not in requested_eligible
            ]
            selected_spells = tuple(sorted(
                (requested_eligible + fallback)[:learn_count],
            ))
            if len(selected_spells) != learn_count:
                raise ValueError("insufficient authored Sorcerer spells")
            selected_ranked.update(selected_spells)
            rows.append(_choice(
                f"class.sorcerer.level_{level}.spell_known",
                *selected_spells,
            ))
        choices[level] = tuple(rows)
    return choices


def _sorcerer_levels(
    parameters: SorcererCharacterParameters,
) -> tuple[ClassLevelRequest, ...]:
    metamagic = parameters.metamagic_choices or ("quickened", "twinned")
    if len(metamagic) != len(set(metamagic)):
        raise ValueError("Sorcerer Metamagic choices must be unique")
    spell_choices = _sorcerer_spell_choices(parameters)
    asi = {4: parameters.asi_4, 8: parameters.asi_8}
    rows: list[ClassLevelRequest] = []
    for level in range(1, parameters.level + 1):
        if level == 1:
            choices = [
                _choice(
                    "class.sorcerer.first_class.starting_equipment",
                    f"starting_equipment.sorcerer.{parameters.equipment_preset}",
                ),
                _choice(
                    "class.sorcerer.proficiencies.skills",
                    "skill.arcana",
                    "skill.deception",
                ),
                _choice(
                    "class.sorcerer.level_1.subclass",
                    "subclass.sorcerer.draconic_bloodline",
                ),
                *spell_choices[level],
                _choice(
                    "subclass.sorcerer.draconic_bloodline.level_1.ancestry",
                    "class_feature.sorcerer.draconic_ancestry.red",
                ),
            ]
        else:
            choices = list(spell_choices[level])
        if level == 3:
            choices.append(_choice(
                "class.sorcerer.level_3.metamagic",
                *(f"class_feature.sorcerer.metamagic.{name}_spell" for name in metamagic),
            ))
        if level in {4, 8}:
            choices.append(_asi_choice(CharacterClass.SORCERER, level, asi[level]))
        rows.append(ClassLevelRequest(CharacterClass.SORCERER, choices=tuple(choices)))
    return tuple(rows)


def create_scenario_character(
    entity_id: str,
    entity_uuid: UUID,
    *,
    name: str,
    faction: str,
    parameters: Mapping[str, object],
) -> Entity:
    """Create one direct authored class root without content infrastructure."""
    if entity_id == "character.fighter":
        parsed = FighterCharacterParameters.model_validate(parameters)
        class_id = CharacterClass.FIGHTER
        requests = _fighter_levels(parsed)
    elif entity_id == "character.barbarian":
        parsed = BarbarianCharacterParameters.model_validate(parameters)
        class_id = CharacterClass.BARBARIAN
        requests = _barbarian_levels(parsed)
    elif entity_id == "character.sorcerer":
        parsed = SorcererCharacterParameters.model_validate(parameters)
        class_id = CharacterClass.SORCERER
        requests = _sorcerer_levels(parsed)
    else:
        raise ValueError(f"unknown direct character root {entity_id!r}")
    origin_state = _human_origin_state(class_id)
    initial_levels = resolve_initial_level_steps(origin_state, requests)
    return create_character(
        entity_uuid,
        name=name,
        species=Species.HUMAN,
        background=Background.ADVENTURER,
        origin_state=origin_state,
        faction=faction,
        initial_levels=initial_levels,
    )


__all__ = [
    "BarbarianCharacterParameters",
    "FighterCharacterParameters",
    "SorcererCharacterParameters",
    "create_scenario_character",
]
