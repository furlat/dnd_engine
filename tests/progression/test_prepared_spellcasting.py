"""Real preparation, source ownership and finite-charge spellbook learning."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.actions import SpellAction
from dnd.characters.spellbook import wizard_book
from dnd.content.characters.builds import create_character
from dnd.content.characters.progression import add_class_level, remove_last_class_level
from dnd.content.characters.spellcasting_grants import (
    change_prepared_spells,
    class_casting_source,
)
from dnd.core.base_block import BaseBlock
from dnd.items.spell_items import (
    build_fire_bolt_scroll,
    build_fireball_scroll,
    build_magic_missile_scroll,
    build_spike_growth_scroll,
)
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.character_progression import (
    CharacterClass,
    PreparedSpellSelection,
)
from tests.progression.prepared_class_support import prepared_build, prepared_level


@pytest.fixture(autouse=True)
def clean_runtime():
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def spells(actor, class_id):
    source = class_casting_source(actor, class_id)
    return {
        action.semantic_key: action
        for action in actor.registered_actions
        if isinstance(action, SpellAction) and action.spellcasting_source_id == source
    }


def selection(class_id, *ids):
    return PreparedSpellSelection(class_id.value + ".spellcasting", ids)


def give_scroll(actor, builder):
    scroll = builder(actor.uuid)
    actor.inventory.add_item(scroll)
    return scroll


def test_preparation_replaces_only_one_source_and_retains_domain_spells():
    actor = create_character(prepared_build(CharacterClass.CLERIC, 3))
    change_prepared_spells(
        actor, selection(CharacterClass.CLERIC, "spell.healing_word", "spell.command")
    )
    old = spells(actor, CharacterClass.CLERIC)
    assert {
        "spell.bless",
        "spell.cure_wounds",
        "spell.aid",
        "spell.lesser_restoration",
        "spell.healing_word",
        "spell.command",
    } <= set(old)
    add_class_level(
        actor, prepared_level(CharacterClass.PALADIN, actor.applied_class_levels)
    )
    add_class_level(
        actor, prepared_level(CharacterClass.PALADIN, actor.applied_class_levels)
    )
    change_prepared_spells(
        actor, selection(CharacterClass.PALADIN, "spell.cure_wounds")
    )
    paladin_cure = spells(actor, CharacterClass.PALADIN)["spell.cure_wounds"]
    assert paladin_cure.uuid != old["spell.cure_wounds"].uuid
    change_prepared_spells(
        actor, selection(CharacterClass.CLERIC, "spell.guiding_bolt")
    )
    assert "spell.healing_word" not in spells(actor, CharacterClass.CLERIC)
    assert spells(actor, CharacterClass.PALADIN)["spell.cure_wounds"] is paladin_cure
    assert "spell.cure_wounds" in spells(actor, CharacterClass.CLERIC)
    before = tuple(actor.registered_actions)
    with pytest.raises(ValueError):
        change_prepared_spells(
            actor, selection(CharacterClass.CLERIC, "spell.fireball")
        )
    assert tuple(actor.registered_actions) == before

    actor.active_encounter_uuid = uuid4()
    with pytest.raises(ValueError, match="encounter"):
        change_prepared_spells(actor, selection(CharacterClass.CLERIC, "spell.command"))
    assert tuple(actor.registered_actions) == before


@pytest.mark.parametrize(
    "spell_id,level", [("spell.shield", 1), ("spell.counterspell", 5)]
)
def test_last_prepared_reaction_remembers_disabled_preference(spell_id, level):
    actor = create_character(
        replace(
            prepared_build(CharacterClass.WIZARD, level), scribed_spell_ids=(spell_id,)
        )
    )
    change_prepared_spells(actor, selection(CharacterClass.WIZARD, spell_id))
    identity = actor.spellcasting.learned_reaction_spell_handler_uuid(spell_id)
    assert identity is not None and actor.set_handler_enabled_by_uuid(identity, False)
    change_prepared_spells(actor, selection(CharacterClass.WIZARD))
    assert actor.spellcasting.learned_reaction_spell_handler_uuid(spell_id) is None
    change_prepared_spells(actor, selection(CharacterClass.WIZARD, spell_id))
    identity = actor.spellcasting.learned_reaction_spell_handler_uuid(spell_id)
    assert identity is not None and not actor.event_handlers[identity].enabled


def test_scroll_teaches_once_retires_last_charge_and_fire_bolt_installs_immediately():
    actor = create_character(prepared_build(CharacterClass.WIZARD))
    scroll = give_scroll(actor, build_fire_bolt_scroll)
    actions = scroll.get_use_actions(actor.uuid)
    assert [action.name for action in actions] == ["Fire Bolt", "Learn Spell"]
    learn = actions[1].instantiate()
    result = learn.apply()
    assert result is not None and not result.canceled
    assert "spell.fire_bolt" in wizard_book(actor)
    assert "spell.fire_bolt" in spells(actor, CharacterClass.WIZARD)
    assert BaseBlock.get(scroll.uuid) is None
    assert actor.action_economy.actions.normalized_score == 1
    stale = learn.apply()
    assert stale is not None and stale.canceled
    second = give_scroll(actor, build_fire_bolt_scroll)
    assert [action.name for action in second.get_use_actions(actor.uuid)] == [
        "Fire Bolt"
    ]
    assert second.charges == 1


def test_shared_slot_capacity_allows_fireball_scribing_without_changing_wizard_source_rank():
    actor = create_character(prepared_build(CharacterClass.CLERIC, 4))
    add_class_level(
        actor, prepared_level(CharacterClass.WIZARD, actor.applied_class_levels)
    )
    actor.action_economy.consume("spell_slot_3", 2)
    scroll = give_scroll(actor, build_fireball_scroll)
    result = scroll.get_use_actions(actor.uuid)[1].instantiate().apply()
    assert result is not None and not result.canceled
    assert "spell.fireball" in actor.scribed_spell_ids
    change_prepared_spells(actor, selection(CharacterClass.WIZARD, "spell.fireball"))
    assert "spell.fireball" in spells(actor, CharacterClass.WIZARD)
    source = actor.spellcasting.sources[
        class_casting_source(actor, CharacterClass.WIZARD)
    ]
    assert source.provider_level == 1 and source.maximum_spell_rank == 1
    foreign = give_scroll(actor, build_spike_growth_scroll)
    assert [action.name for action in foreign.get_use_actions(actor.uuid)] == [
        "Spike Growth"
    ]
    assert foreign.charges == 1


def test_removing_level_book_knowledge_retires_entitlement_but_scribed_knowledge_survives():
    build = prepared_build(CharacterClass.WIZARD, 2)
    row = build.class_levels[1]
    choices = tuple(
        replace(choice, values=("spell.magic_missile", "spell.mage_armor"))
        if choice.choice_id.endswith(".spellbook")
        else choice
        for choice in row.choices
    )
    build = replace(
        build, class_levels=(build.class_levels[0], replace(row, choices=choices))
    )
    actor = create_character(build)
    change_prepared_spells(
        actor, selection(CharacterClass.WIZARD, "spell.magic_missile")
    )
    assert "spell.magic_missile" in spells(actor, CharacterClass.WIZARD)
    remove_last_class_level(actor)
    assert "spell.magic_missile" not in wizard_book(actor)
    assert "spell.magic_missile" not in spells(actor, CharacterClass.WIZARD)
    rebuilt_without_learned = create_character(
        replace(
            build,
            class_levels=build.class_levels[:1],
            prepared_spells=actor.prepared_spell_selections,
            position=(4, 4),
        )
    )
    assert "spell.magic_missile" not in spells(
        rebuilt_without_learned, CharacterClass.WIZARD
    )
    scroll = give_scroll(actor, build_magic_missile_scroll)
    assert not scroll.get_use_actions(actor.uuid)[1].instantiate().apply().canceled
    assert "spell.magic_missile" not in spells(actor, CharacterClass.WIZARD)
    change_prepared_spells(
        actor, selection(CharacterClass.WIZARD, "spell.magic_missile")
    )
    captured = replace(
        build,
        class_levels=build.class_levels[:1],
        scribed_spell_ids=actor.scribed_spell_ids,
        prepared_spells=actor.prepared_spell_selections,
    )
    rebuilt = create_character(replace(captured, position=(2, 2)))
    assert "spell.magic_missile" in wizard_book(rebuilt)
    assert "spell.magic_missile" in spells(rebuilt, CharacterClass.WIZARD)
