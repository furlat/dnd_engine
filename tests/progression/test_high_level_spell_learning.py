"""New spells use the existing exact source-owned Sorcerer learning surface."""

from dataclasses import replace

import pytest

from dnd.content.characters.sorcerer_grants import apply_sorcerer_level
from dnd.spells.enchantment import CharmMonster
from dnd.spells.evocation import DelayedBlastFireball, VitriolicSphere
from dnd.types.character_progression import ClassChoiceSelection
from tests.progression.test_direct_sorcerer_progression import (
    _entity,
    _level,
    _reset_engine,
)


@pytest.mark.parametrize(
    "spell,identity,learn_level",
    [
        (CharmMonster, "spell.charm_monster", 7),
        (VitriolicSphere, "spell.vitriolic_sphere", 7),
        (DelayedBlastFireball, "spell.delayed_blast_fireball", 13),
    ],
)
def test_high_level_spell_learned_from_real_class_choice(spell, identity, learn_level):
    actor = _entity()
    for level in range(1, learn_level + 1):
        selection = _level(level)
        if level == learn_level:
            selection = replace(
                selection,
                choices=tuple(
                    ClassChoiceSelection(choice.choice_id, (identity,))
                    if choice.choice_id == f"class.sorcerer.level_{level}.spell_known"
                    else choice
                    for choice in selection.choices
                ),
            )
        apply_sorcerer_level(actor, selection)
    action = next(
        action for action in actor.registered_actions if isinstance(action, spell)
    )
    assert action.spellcasting_source_id in actor.spellcasting.sources
    assert (
        actor.spellcasting.sources[action.spellcasting_source_id].provider_id
        == "class.sorcerer"
    )
