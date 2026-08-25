"""Authored scenarios through the in-process Game and event boundary."""

from collections import Counter

import pytest

from dnd.content.scenarios.scenario_catalog import (
    AUTHORED_DEPLOYMENTS,
    AUTHORED_ENCOUNTERS,
    AUTHORED_ROSTERS,
    encounter_definition,
)
from dnd.blocks.base_item import BaseItem
from dnd.content.scenarios.battlefield_builders import build_battlefield
from dnd.content.scenarios.scenario_deployment import prepare_scenario
from dnd.content.scenarios.scenario_definitions import FixedRosterOpeningPolicy
from dnd.core.events.events_registry import EventPhase, EventQueue, EventType
from dnd.core.events.world_events import WorldInitializedEvent
from dnd.core.gridmap import get_map
from dnd.game import Game
from dnd.items.torches import Torch
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.materials import Material, TileSurface
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.types.world_placement import (
    BoundaryStructureKind,
    WorldObjectPlacement,
    WorldPlacementKind,
)


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


def test_real_world_initialized_fact_keeps_surface_and_object_identity() -> None:
    """Cold battlefield bootstrap carries exact semantic Tiles and placements."""
    reset_engine_runtime()
    built = build_battlefield("battlefield.field_cache_bright")
    world = next(
        event
        for event in EventQueue.get_events_chronological()
        if isinstance(event, WorldInitializedEvent)
    )
    tile_state = next(state for state in world.tiles if state.position == (0, 0))
    tile = get_map().get_tile(0, 0)
    assert tile is not None
    assert tile_state.surface == TileSurface(base_material=Material.STONE)
    assert tile_state.surface == tile.surface
    assert world.objects
    object_state = next(
        state
        for state in world.objects
        if state.placement.object_uuid == built.object_uuids["field_cache"]
    )
    runtime_item = BaseItem.get(object_state.item.item_uuid)
    assert runtime_item is not None
    assert object_state.item == runtime_item.to_item_state()
    assert object_state.contained_items == tuple(
        child.to_item_state()
        for child in sorted(
            runtime_item.get_storage_block().items.values(),
            key=lambda child: str(child.uuid),
        )
    )
    assert object_state.placement.object_uuid == object_state.item.item_uuid
    assert object_state.placement == get_map().get_object_placement(
        object_state.item.item_uuid,
    )
    assert object_state.item.item_uuid in set(built.object_uuids.values())


def test_world_initialized_round_trip_preserves_cliff_and_wall_torch_boundary_state() -> None:
    """Cold world facts retain concrete boundary placement and light state."""
    reset_engine_runtime()
    standard = build_battlefield("battlefield.standard_hazards_closed")
    standard_worlds = [
        event
        for event in EventQueue.get_events_chronological()
        if isinstance(event, WorldInitializedEvent)
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(standard_worlds) == 1
    standard_world = standard_worlds[0]
    standard_torch = standard.environment.wall_torches[0]
    standard_torch_state = next(
        state
        for state in standard_world.objects
        if state.placement.object_uuid == standard_torch.uuid
    )
    assert standard_torch_state.item == standard_torch.to_item_state()
    assert standard_torch_state.item.light_source is not None
    assert standard_torch_state.item.light_source.is_lit is True
    assert standard_torch_state.item.boundary_structure is None
    assert standard_torch_state.placement == WorldObjectPlacement(
        object_uuid=standard_torch.uuid,
        tile_uuid=get_map().get_tile(14, 1).uuid,
        position=(14, 1),
        kind=WorldPlacementKind.BOUNDARY,
        occupies_bands=False,
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=1,
        top_height_steps=2,
        orientation=CardinalDirection.WEST,
    )
    exit_layer, entry_layer = get_map().get_boundary_route_layers(
        (14, 1),
        CardinalDirection.EAST,
        WorldEdgeChannel.OPTICAL,
    )
    assert standard_torch.uuid in exit_layer
    assert entry_layer == ()
    EventQueue.reset()
    restored_standard = WorldInitializedEvent.model_validate_json(
        standard_world.model_dump_json(),
    )
    assert restored_standard == standard_world
    standard_light_before = get_map().get_tile(14, 1).resolved_light_level
    standard_placements = tuple(
        row.placement for row in restored_standard.objects
    )
    rebuild_cursor = EventQueue.event_cursor()
    standard_rebuilt = get_map().rebuild_object_placements(standard_placements)
    assert set(standard_rebuilt) == set(standard_placements)
    assert set(get_map().get_all_object_placements()) == set(standard_placements)
    assert list(EventQueue.iter_events_since(rebuild_cursor)) == []
    assert get_map().get_tile(14, 1).resolved_light_level is standard_light_before

    reset_engine_runtime()
    proving = build_battlefield("battlefield.elevation_proving_ground")
    proving_worlds = [
        event
        for event in EventQueue.get_events_chronological()
        if isinstance(event, WorldInitializedEvent)
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(proving_worlds) == 1
    proving_world = proving_worlds[0]
    cliff_uuid = proving.object_uuids["cliff"]
    cliff_state = next(
        state
        for state in proving_world.objects
        if state.placement.object_uuid == cliff_uuid
    )
    assert cliff_state.item == BaseItem.get(cliff_uuid).to_item_state()
    assert cliff_state.placement.kind is WorldPlacementKind.BOUNDARY
    assert cliff_state.placement.occupies_bands is True
    assert cliff_state.placement.boundary_direction is CardinalDirection.WEST
    assert (
        cliff_state.placement.base_height_steps,
        cliff_state.placement.top_height_steps,
    ) == (0, 2)
    assert cliff_state.placement.orientation is None
    assert cliff_state.item.boundary_structure is not None
    assert cliff_state.item.boundary_structure.structure is BoundaryStructureKind.CLIFF
    assert cliff_state.item.boundary_structure.material is Material.STONE
    assert cliff_state.item.boundary_structure.blocked_channels == (
        WorldEdgeChannel.MOVEMENT,
    )
    EventQueue.reset()
    restored_proving = WorldInitializedEvent.model_validate_json(
        proving_world.model_dump_json(),
    )
    assert restored_proving == proving_world
    complete_placements = tuple(
        row.placement for row in restored_proving.objects
    )
    get_map().remove_object(cliff_uuid)
    rebuild_cursor = EventQueue.event_cursor()
    rebuilt = get_map().rebuild_object_placements(complete_placements)
    assert set(rebuilt) == set(complete_placements)
    assert get_map().get_object_placement(cliff_uuid) == cliff_state.placement
    assert list(EventQueue.iter_events_since(rebuild_cursor)) == []
    assert set(get_map().get_all_object_placements()) == set(complete_placements)


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
