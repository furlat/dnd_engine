"""Pure preparation rules; shared by cold builds and native composition."""

from dnd.types.character_progression import AppliedClassLevel, CharacterClass
from dnd.types.class_spells import (
    CLERIC_SPELL_RANKS,
    PALADIN_SPELL_RANKS,
    WIZARD_SPELL_RANKS,
    LIFE_DOMAIN_SPELLS,
    DEVOTION_OATH_SPELLS,
)


def always_prepared_spells(
    class_id: CharacterClass, levels: tuple[AppliedClassLevel, ...]
) -> tuple[str, ...]:
    own = tuple(row for row in levels if row.class_id is class_id)
    table = (
        LIFE_DOMAIN_SPELLS
        if class_id is CharacterClass.CLERIC
        else DEVOTION_OATH_SPELLS
        if class_id is CharacterClass.PALADIN
        else {}
    )
    domain = tuple(
        spell
        for level, spells in table.items()
        if len(own) >= level
        for spell in spells
    )
    signature = tuple(
        spell
        for row in own
        for choice in row.choices
        if choice.choice_id.endswith(".signature")
        for spell in choice.values
    )
    return tuple(dict.fromkeys((*domain, *signature)))


def preparation_error(
    class_id: CharacterClass,
    levels: tuple[AppliedClassLevel, ...],
    scribed: tuple[str, ...],
    selected: tuple[str, ...],
    ability_modifier: int,
    shared_max_rank: int,
) -> str | None:
    own = tuple(row for row in levels if row.class_id is class_id)
    level = len(own)
    if not level or class_id is CharacterClass.PALADIN and level < 2:
        return "The prepared casting source is not available"
    if len(set(selected)) != len(selected):
        return "Prepared spell identities must be unique"
    capacity = max(
        1,
        (level // 2 if class_id is CharacterClass.PALADIN else level)
        + ability_modifier,
    )
    if len(set(selected) - set(always_prepared_spells(class_id, levels))) > capacity:
        return "Selected spells exceed preparation capacity"
    ranks = {
        CharacterClass.CLERIC: CLERIC_SPELL_RANKS,
        CharacterClass.PALADIN: PALADIN_SPELL_RANKS,
        CharacterClass.WIZARD: WIZARD_SPELL_RANKS,
    }[class_id]
    own_rank = (
        (level + 3) // 4 if class_id is CharacterClass.PALADIN else (level + 1) // 2
    )
    maximum = shared_max_rank if class_id is CharacterClass.WIZARD else own_rank
    book = {
        spell
        for row in own
        for choice in row.choices
        if choice.choice_id.endswith(".spellbook")
        for spell in choice.values
    } | set(scribed)
    for spell in selected:
        if spell not in ranks or not 1 <= ranks[spell] <= maximum:
            return "Prepared spell is outside this source's accessible spell list/rank"
        if class_id is CharacterClass.WIZARD and spell not in book:
            return "Prepared Wizard spell is not in this Wizard book"
    return None
