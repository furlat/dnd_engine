import random

import pytest

from ai.evaluation.arena_manifest import build_arena_manifest
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.scenarios.ai_validation_arenas import (
    create_ai_validation_arena,
    list_ai_validation_arena_specs,
)
from dnd.scenarios.evaluation.assembler import assemble_legacy_scenario
from dnd.scenarios.evaluation.battlefield_catalog import get_battlefield
from dnd.scenarios.evaluation.combatant_catalog import get_combatant_configuration
from dnd.scenarios.evaluation.deployment_catalog import get_deployment
from dnd.scenarios.evaluation.legacy_recipes import LEGACY_RECIPES


LEGACY_ARENA_IDS = tuple(recipe.arena_id for recipe in LEGACY_RECIPES)


def test_all_38_legacy_specs_have_complete_composition_recipes() -> None:
    assert len(LEGACY_RECIPES) == 38
    assert set(LEGACY_ARENA_IDS) == {
        spec.arena_id for spec in list_ai_validation_arena_specs()
    }
    for recipe in LEGACY_RECIPES:
        assert get_combatant_configuration(recipe.hero_configuration_id).side_kind == "hero"
        assert get_combatant_configuration(recipe.monster_configuration_id).side_kind == "monster_party"
        assert get_battlefield(recipe.battlefield_id).battlefield_id == recipe.battlefield_id
        assert get_deployment(recipe.deployment_id).source_arena_id == recipe.arena_id


@pytest.mark.parametrize("arena_id", LEGACY_ARENA_IDS)
def test_composed_recipe_matches_seeded_legacy_manifest(arena_id: str) -> None:
    random.seed(20260717)
    legacy_manifest = build_arena_manifest(create_ai_validation_arena(arena_id))
    random.seed(20260717)
    composed_manifest = build_arena_manifest(assemble_legacy_scenario(arena_id))

    assert composed_manifest == legacy_manifest


@pytest.mark.parametrize("opening_faction", ("heroes", "monsters"))
def test_composed_opening_treatment_preserves_rolled_initiative_and_forces_side(
    opening_faction: str,
) -> None:
    random.seed(91)
    arena = assemble_legacy_scenario("standard_skeleton_doors", opening_faction=opening_faction)

    assert arena.encounter.get_current_entity().faction == opening_faction
    assert all(state.initiative_roll > 0 for state in arena.encounter.combatants.values())


def test_starting_damage_and_conditions_flow_through_events_without_extra_start_state() -> None:
    arena = assemble_legacy_scenario("cleanse_support_triage")
    poisoned_guard, blinded_archer, _ = arena.monsters

    damage_events = EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
    condition_events = EventQueue.get_events_by_type(EventType.CONDITION_APPLICATION)
    assert any(event.phase == EventPhase.EFFECT for event in damage_events)
    assert any(event.phase == EventPhase.EFFECT for event in condition_events)
    assert set(poisoned_guard.active_conditions) == {"Poisoned"}
    assert set(blinded_archer.active_conditions) == {"Blinded"}
