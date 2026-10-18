"""Real authored build inputs shared by prepared-class gameplay tests."""

from dataclasses import replace

from dnd.content.characters.build_types import CharacterAppearance, CharacterBuild
from dnd.content.characters.class_definitions import (
    class_level_choices,
    next_class_level,
)
from dnd.types.character_progression import (
    ClassChoiceSelection,
    OriginChoiceSelection,
    Background,
    Species,
)


def prepared_level(class_id, previous=()):
    row = next_class_level(class_id, previous)
    learned = {
        spell
        for level in previous
        if level.class_id is class_id
        for choice in level.choices
        if choice.choice_id.endswith((".cantrips", ".spellbook"))
        for spell in choice.values
    }
    choices = []
    for choice in class_level_choices(row, first_class=not previous):
        if choice.choice_id.endswith(".asi_or_feat"):
            ability = {
                4: "constitution",
                8: "intelligence",
                12: "wisdom",
                16: "charisma",
                19: "strength",
            }[row.resulting_class_level]
            values = (f"ability_score.{ability}.2",)
        elif choice.choice_id.endswith((".mastery_1", ".mastery_2", ".signature")):
            values = tuple(
                spell for spell in choice.allowed_values if spell in learned
            )[: choice.selections[0]]
        else:
            values = tuple(
                spell for spell in choice.allowed_values if spell not in learned
            )[: choice.selections[0]]
        choices.append(ClassChoiceSelection(choice.choice_id, values))
        if choice.choice_id.endswith((".cantrips", ".spellbook")):
            learned.update(values)
    return replace(row, choices=tuple(choices))


def prepared_build(class_id, level=1):
    levels = ()
    for _ in range(level):
        levels = (*levels, prepared_level(class_id, levels))
    return CharacterBuild(
        name=class_id.value,
        species=Species.HUMAN,
        background=Background.ADVENTURER,
        base_ability_scores=(
            ("strength", 13),
            ("dexterity", 8),
            ("constitution", 14),
            ("intelligence", 13),
            ("wisdom", 13),
            ("charisma", 13),
        ),
        flexible_ability_bonuses=(("intelligence", 2), ("wisdom", 1)),
        origin_choices=(
            OriginChoiceSelection(
                "species.human.additional_language", ("language.draconic",)
            ),
        ),
        class_levels=levels,
        item_loadout=(),
        appearance=CharacterAppearance(),
    )
