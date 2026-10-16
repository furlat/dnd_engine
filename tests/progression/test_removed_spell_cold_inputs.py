"""Removed spell identities fail through supported cold character inputs."""
from dataclasses import replace

import pytest

from dnd.content.characters.builds import create_character
from dnd.types.character_progression import CharacterClass, PreparedSpellSelection
from tests.progression.prepared_class_support import prepared_build


@pytest.mark.parametrize("class_id", [CharacterClass.CLERIC, CharacterClass.WIZARD])
def test_removed_spell_is_rejected_in_cold_preparation_or_spellbook(class_id):
    build = prepared_build(class_id,15)
    selection = PreparedSpellSelection(f"{class_id.value}.spellcasting", ("spell.antimagic_field",))
    changes = {"prepared_spells": (selection,)}
    if class_id is CharacterClass.WIZARD:
        changes["scribed_spell_ids"] = ("spell.antimagic_field",)
    with pytest.raises(ValueError, match="(?i)(prepared spell|implemented Wizard spells)"):
        create_character(replace(build, **changes))
