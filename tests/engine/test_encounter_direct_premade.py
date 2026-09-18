"""Authored encounters compose direct heroes and native creatures together."""

import pytest

from dnd.core.content.encounters import (
    EncounterRecipe,
    EncounterRosterRecipe,
    PremadeCharacterRosterSource,
)
from dnd.core.events import EventQueue, EventType
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.scenarios.encounter_catalog import encounter_recipe
from dnd.types.character_progression import CharacterClass


def test_warband_recipe_builds_a_complete_direct_barbarian_once() -> None:
    reset_engine_runtime()
    authored = encounter_recipe("encounter.srd_goblinoid_warband")
    recipe = EncounterRecipe.model_validate_json(authored.model_dump_json())

    assembled = prepare_encounter_recipe(recipe, game=Game())

    hero = assembled.entities_by_member_address[("roster_1", "hero")]
    births = EventQueue.get_events_by_type(EventType.ENTITY_CREATED)
    assert len(births) == len(assembled.entities) == 5
    birth, = (event for event in births if event.entity_uuid == hero.uuid)
    assert hero.name == birth.entity_name == "Validation Warband Barbarian"
    assert hero.character_body_id == "creature.player.humanoid_body"
    assert hero.content_ref is None
    assert len(hero.applied_class_levels) == 5
    assert all(
        level.class_id is CharacterClass.BARBARIAN
        for level in hero.applied_class_levels
    )
    torch, = (
        item for item in birth.items
        if item.item_id == "equipment.portable_torch"
    )
    assert torch.is_lit
    assert sum(
        item.item_id == "equipment.portable_torch"
        for item in hero.inventory.items.values()
    ) == 1
    assert all(
        entity.content_ref is not None
        for entity in assembled.entities_by_roster_slot["roster_2"]
    )


def test_rejected_encounter_discards_prepared_direct_hero_without_birth() -> None:
    reset_engine_runtime()
    authored = encounter_recipe("encounter.srd_goblinoid_warband")
    opponents = authored.roster_slots[1]
    members = opponents.roster.members
    unavailable = members[0].model_copy(update={
        "source": PremadeCharacterRosterSource(premade_id="hero.missing"),
    })
    roster = EncounterRosterRecipe.create(
        roster_id=opponents.roster.roster_id,
        title=opponents.roster.title,
        members=(unavailable, *members[1:]),
        tags=opponents.roster.tags,
        required_battlefield_capabilities=(
            opponents.roster.required_battlefield_capabilities
        ),
        forbidden_battlefield_capabilities=(
            opponents.roster.forbidden_battlefield_capabilities
        ),
    )
    recipe = EncounterRecipe.create(
        encounter_id=authored.encounter_id,
        title=authored.title,
        roster_slots=(
            authored.roster_slots[0],
            opponents.model_copy(update={"roster": roster}),
        ),
        battlefield_id=authored.battlefield_id,
        deployment=authored.deployment,
        opening_policy=authored.opening_policy,
        notable_positions=authored.notable_positions,
        tags=authored.tags,
    )
    game = Game()

    with pytest.raises(KeyError, match="hero.missing"):
        prepare_encounter_recipe(recipe, game=game)

    assert Entity.get_all_entities() == []
    assert not game.entities
    assert EventQueue.get_events_by_type(EventType.ENTITY_CREATED) == []
