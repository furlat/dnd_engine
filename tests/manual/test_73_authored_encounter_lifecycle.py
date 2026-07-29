"""Census and lifecycle gates for canonical authored encounters."""

import pytest

from dnd.core.content.encounters import (
    EncounterRecipe,
    FixedRosterOpeningPolicy,
)
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.items.torches import Torch
from dnd.scenarios.encounter_assembler import assemble_encounter_recipe
from dnd.scenarios.encounter_catalog import (
    AUTHORED_ENCOUNTER_RECIPES,
    encounter_recipe,
)


ENCOUNTER_IDS = tuple(
    recipe.encounter_id for recipe in AUTHORED_ENCOUNTER_RECIPES
)


def _with_opening_roster(
    recipe: EncounterRecipe,
    roster_slot_id: str,
) -> EncounterRecipe:
    return EncounterRecipe.create(
        encounter_id=recipe.encounter_id,
        title=recipe.title,
        roster_slots=recipe.roster_slots,
        battlefield_id=recipe.battlefield_id,
        deployment=recipe.deployment,
        opening_policy=FixedRosterOpeningPolicy(
            roster_slot_id=roster_slot_id,
        ),
        notable_positions=recipe.notable_positions,
        tags=recipe.tags,
    )


def test_all_38_authored_encounters_have_complete_canonical_recipes() -> None:
    assert len(AUTHORED_ENCOUNTER_RECIPES) == 38
    assert len(set(ENCOUNTER_IDS)) == 38
    for recipe in AUTHORED_ENCOUNTER_RECIPES:
        assert len(recipe.roster_slots) == 2
        assert all(slot.roster.members for slot in recipe.roster_slots)
        assert recipe.deployment.battlefield_id == recipe.battlefield_id
        assert recipe.tags == ("authored",)


@pytest.mark.parametrize("encounter_id", ENCOUNTER_IDS)
def test_every_active_recipe_constructs_one_complete_encounter(
    encounter_id: str,
) -> None:
    recipe = encounter_recipe(encounter_id)
    assembled = assemble_encounter_recipe(recipe)

    assert assembled.recipe.encounter_id == encounter_id
    assert [
        len(assembled.entities_by_roster_slot[slot.roster_slot_id])
        for slot in recipe.roster_slots
    ] == [len(slot.roster.members) for slot in recipe.roster_slots]
    assert {
        entity.uuid for entity in assembled.entities
    } == set(assembled.encounter.combatants)
    assert all(
        entity.content_ref is not None for entity in assembled.entities
    )


@pytest.mark.parametrize("roster_slot_id", ("roster_1", "roster_2"))
def test_fixed_opening_preserves_rolled_initiative_and_forces_roster(
    roster_slot_id: str,
) -> None:
    base = encounter_recipe("encounter.standard_skeleton_doors")
    recipe = _with_opening_roster(base, roster_slot_id)
    assembled = assemble_encounter_recipe(recipe)
    current = assembled.encounter.get_current_entity()

    assert current is not None
    assert current in assembled.entities_by_roster_slot[roster_slot_id]
    assert all(
        state.initiative_roll > 0
        for state in assembled.encounter.combatants.values()
    )


def test_starting_damage_and_conditions_flow_through_events() -> None:
    assembled = assemble_encounter_recipe(
        encounter_recipe("encounter.cleanse_support_triage"),
    )
    poisoned_guard, blinded_archer, _ = (
        assembled.entities_by_roster_slot["roster_2"]
    )

    damage_events = EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
    condition_events = EventQueue.get_events_by_type(
        EventType.CONDITION_APPLICATION,
    )
    assert any(event.phase == EventPhase.EFFECT for event in damage_events)
    assert any(event.phase == EventPhase.EFFECT for event in condition_events)
    assert set(poisoned_guard.active_conditions) == {"Poisoned"}
    assert set(blinded_archer.active_conditions) == {"Blinded"}


def test_typed_post_grant_behavior_ignites_the_authored_portable_torch() -> None:
    assembled = assemble_encounter_recipe(
        encounter_recipe("encounter.standard_skeleton_doors"),
    )
    hero = assembled.entities_by_roster_slot["roster_1"][0]
    torches = [
        item
        for item in hero.inventory.items.values()
        if isinstance(item, Torch)
    ]

    assert len(torches) == 1
    assert torches[0].is_lit
