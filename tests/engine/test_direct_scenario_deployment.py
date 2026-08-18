"""Authored scenarios through the in-process Game and event boundary."""

from collections import Counter

import pytest

from dnd.content.scenarios.scenario_catalog import (
    AUTHORED_DEPLOYMENTS,
    AUTHORED_ENCOUNTERS,
    AUTHORED_ROSTERS,
    encounter_definition,
)
from dnd.content.scenarios.scenario_deployment import prepare_scenario
from dnd.content.scenarios.scenario_definitions import FixedRosterOpeningPolicy
from dnd.core.events.events_registry import EventPhase, EventQueue, EventType
from dnd.game import Game
from dnd.items.torches import Torch
from dnd.runtime_reset import reset_engine_runtime


def test_cold_scenario_catalog_preserves_the_audited_authored_surface() -> None:
    effect_counts = Counter(
        type(effect).__name__
        for roster in AUTHORED_ROSTERS
        for member in roster.members
        for effect in member.scenario_setup_effects
    )
    item_ids = {
        effect.item_id
        for roster in AUTHORED_ROSTERS
        for member in roster.members
        for effect in member.scenario_setup_effects
        if hasattr(effect, "item_id")
    }
    spell_ids = {
        spell_id
        for roster in AUTHORED_ROSTERS
        for member in roster.members
        for effect in member.scenario_setup_effects
        if hasattr(effect, "spell_ids")
        for spell_id in effect.spell_ids
    }

    assert len(AUTHORED_ROSTERS) == 58
    assert sum(len(roster.members) for roster in AUTHORED_ROSTERS) == 141
    assert len(AUTHORED_DEPLOYMENTS) == 10
    assert len(AUTHORED_ENCOUNTERS) == 39
    assert sum(len(row.roster_slots) for row in AUTHORED_ENCOUNTERS) == 78
    assert effect_counts == {
        "RosterItemGrant": 43,
        "RosterSpellGrant": 23,
        "RosterBehaviorGrant": 19,
        "RosterStartingDamage": 10,
        "RosterDamageAffinity": 2,
        "RosterStartingCondition": 2,
    }
    assert len(item_ids) == 16
    assert len(spell_ids) == 51


@pytest.mark.parametrize(
    "definition",
    AUTHORED_ENCOUNTERS,
    ids=lambda row: row.encounter_id,
)
def test_every_authored_scenario_prepares_through_one_direct_path(
    definition,
) -> None:
    reset_engine_runtime()
    assembled = prepare_scenario(Game(), definition)

    assert assembled.definition is definition
    assert len(assembled.entities) == sum(
        len(slot.roster.members) for slot in definition.roster_slots
    )
    assert set(assembled.game.entities) == {
        entity.uuid for entity in assembled.entities
    }
    assert set(assembled.encounter.combatants) == {
        entity.uuid for entity in assembled.entities
    }
    assert assembled.compatibility.admitted
    assert all(
        "content_ref" not in type(entity).model_fields
        for entity in assembled.entities
    )


@pytest.mark.parametrize("roster_slot_id", ("roster_1", "roster_2"))
def test_fixed_opening_preserves_initiative_and_forces_the_authored_roster(
    roster_slot_id: str,
) -> None:
    reset_engine_runtime()
    base = encounter_definition("encounter.standard_skeleton_doors")
    definition = base.model_copy(update={
        "opening_policy": FixedRosterOpeningPolicy(
            roster_slot_id=roster_slot_id,
        ),
    })
    assembled = prepare_scenario(Game(), definition)
    assembled.encounter.start_encounter()
    current = assembled.encounter.get_current_entity()

    assert current is not None
    assert current in assembled.entities_by_roster_slot[roster_slot_id]
    assert all(
        state.initiative_roll > 0
        for state in assembled.encounter.combatants.values()
    )


def test_world_birth_and_deployment_are_ordered_event_facts() -> None:
    reset_engine_runtime()
    assembled = prepare_scenario(
        Game(),
        encounter_definition("encounter.standard_skeleton_doors"),
    )
    events = EventQueue.get_events_chronological()
    event_types = [event.event_type for event in events]

    world_index = event_types.index(EventType.WORLD_INITIALIZED)
    first_birth = event_types.index(EventType.ENTITY_CREATED)
    first_deployment = event_types.index(EventType.SPATIAL_ENTITY_ENTERED)
    world = events[world_index]

    assert world.phase is EventPhase.COMPLETION
    assert len(world.tiles) == 225
    assert world_index < first_birth < first_deployment
    assert event_types.count(EventType.ENTITY_CREATED) == len(assembled.entities)
    assert event_types.count(EventType.SPATIAL_ENTITY_ENTERED) == (
        4 * len(assembled.entities)
    )


def test_scenario_setup_uses_real_item_condition_and_reaction_mechanics() -> None:
    reset_engine_runtime()
    standard = prepare_scenario(
        Game(),
        encounter_definition("encounter.standard_skeleton_doors"),
    )
    hero = standard.entities_by_roster_slot["roster_1"][0]
    torches = [
        item for item in hero.inventory.items.values()
        if isinstance(item, Torch)
    ]
    assert len(torches) == 1
    assert torches[0].is_lit

    reset_engine_runtime()
    triage = prepare_scenario(
        Game(),
        encounter_definition("encounter.cleanse_support_triage"),
    )
    poisoned_guard, blinded_archer, _ = (
        triage.entities_by_roster_slot["roster_2"]
    )
    assert tuple(
        condition.name for condition in poisoned_guard.active_conditions.values()
    ) == ("Poisoned",)
    assert {
        condition.name for condition in blinded_archer.active_conditions.values()
    } == {"Blinded"}
    assert any(
        event.phase is EventPhase.EFFECT
        for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
    )
    assert any(
        event.phase is EventPhase.EFFECT
        for event in EventQueue.get_events_by_type(EventType.CONDITION_APPLICATION)
    )
    assert any(
        event.phase is EventPhase.COMPLETION
        and event.condition_behavior_id == "condition.poisoned"
        for event in EventQueue.get_events_by_type(EventType.CONDITION_APPLICATION)
    )

    reset_engine_runtime()
    reactions = prepare_scenario(
        Game(),
        encounter_definition("encounter.reaction_counterspell_lab"),
    )
    handler_ids = {
        handler.behavior_id
        for entity in reactions.entities
        for handler in entity.event_handlers.values()
    }
    assert "reaction.spell.shield" in handler_ids
    assert "reaction.spell.counterspell" in handler_ids
