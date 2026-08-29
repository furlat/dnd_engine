"""Authored scenarios through the in-process Game and event boundary."""

from collections import Counter
from uuid import uuid4

import pytest

from dnd.content.scenarios.scenario_catalog import (
    AUTHORED_DEPLOYMENTS,
    AUTHORED_ENCOUNTERS,
    AUTHORED_ROSTERS,
    encounter_definition,
)
from dnd.blocks.base_item import BaseItem
from dnd.blocks.sensory import Senses, capture_senses_snapshot
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, ConditionApplicationEvent
from dnd.core.base_tiles import Tile
from dnd.content.scenarios.battlefield_builders import build_battlefield
from dnd.content.scenarios.scenario_deployment import prepare_scenario
from dnd.content.scenarios.scenario_definitions import FixedRosterOpeningPolicy
from dnd.core.events.events_registry import (
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.events.item_events import ItemLocationStateEvent
from dnd.core.events.world_events import (
    SensoryUpdateEvent,
    SensoryUpdateReason,
    SpatialChangeEvent,
    SpatialEffectChangeEvent,
    SpatialEffectInteractionEvent,
    WorldInitializedEvent,
)
from dnd.core.gridmap import get_map
from dnd.game import Game
from dnd.items.environment_interactables import PullLeverAction
from dnd.items.torches import Torch, WallTorch
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.materials import Material, TileSurface
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.types.spatial_effects import SpatialEffectChangeOperation
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

    world_start_index = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.WORLD_INITIALIZED
        and event.phase is EventPhase.DECLARATION
    )
    world_index = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.WORLD_INITIALIZED
        and event.phase is EventPhase.COMPLETION
    )
    first_birth = event_types.index(EventType.ENTITY_CREATED)
    first_deployment = event_types.index(EventType.SPATIAL_ENTITY_ENTERED)
    world = events[world_index]

    assert world.phase is EventPhase.COMPLETION
    assert len(world.tiles) == 225
    assert world_start_index < world_index < first_birth < first_deployment
    assert event_types.count(EventType.ENTITY_CREATED) == len(assembled.entities)
    assert event_types.count(EventType.SPATIAL_ENTITY_ENTERED) == (
        4 * len(assembled.entities)
    )

    authored_spike_uuid = assembled.battlefield.environment.spike_condition_uuid
    authored_torch_uuids = {
        row.placement.object_uuid
        for row in world.objects
        if row.item.semantic_key == "environment.wall_torch"
    }
    authored_setup = [
        (index, event)
        for index, event in enumerate(events)
        if (
            (
                isinstance(event, ConditionApplicationEvent)
                and event.condition.uuid == authored_spike_uuid
            )
            or (
                isinstance(event, SpatialEffectChangeEvent)
                and event.spatial_effect_uuid == authored_spike_uuid
            )
            or (
                isinstance(event, SpatialChangeEvent)
                and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
                and event.phase is EventPhase.COMPLETION
                and index < first_birth
            )
            or (
                isinstance(event, SpatialEffectInteractionEvent)
                and event.operation.value == "ignite"
                and event.source_object_uuid in authored_torch_uuids
            )
            or (
                isinstance(event, ItemLocationStateEvent)
                and event.item_state.item_uuid in authored_torch_uuids
            )
        )
        and event.phase is EventPhase.COMPLETION
    ]
    assert authored_setup
    assert all(
        world_start_index < index < world_index
        for index, _event in authored_setup
    )
    assert {
        event.spatial_effect_uuid
        for _index, event in authored_setup
        if isinstance(event, SpatialEffectChangeEvent)
    } == {authored_spike_uuid}
    assert {
        event.source_object_uuid
        for _index, event in authored_setup
        if isinstance(event, SpatialEffectInteractionEvent)
    } == authored_torch_uuids
    assert {
        event.item_state.item_uuid
        for _index, event in authored_setup
        if isinstance(event, ItemLocationStateEvent)
    } == authored_torch_uuids

    def perception_projection(senses: Senses) -> tuple[object, ...]:
        snapshot = capture_senses_snapshot(senses)
        return (
            snapshot.position,
            snapshot.visible,
            snapshot.seen,
            snapshot.entities,
            snapshot.objects,
            snapshot.effective_light_levels,
            tuple(senses.get_sense_modes()),
            snapshot.passive_perception,
            snapshot.visual_access,
        )

    for entity in assembled.entities:
        birth_index = next(
            index
            for index, event in enumerate(events)
            if event.event_type is EventType.ENTITY_CREATED
            and event.entity_uuid == entity.uuid
        )
        entered = [
            (index, event)
            for index, event in enumerate(events)
            if isinstance(event, SpatialChangeEvent)
            and event.event_type is EventType.SPATIAL_ENTITY_ENTERED
            and event.entity_uuid == entity.uuid
        ]
        assert birth_index < entered[0][0]
        assert len({event.lineage_uuid for _index, event in entered}) == 1
        entered_effect_index, entered_effect = next(
            (index, event)
            for index, event in entered
            if event.phase is EventPhase.EFFECT
        )
        entered_completion_index = next(
            index
            for index, event in entered
            if event.phase is EventPhase.COMPLETION
        )
        assert birth_index < entered_effect_index < entered_completion_index
        self_updates = [
            (index, event)
            for index, event in enumerate(events)
            if isinstance(event, SensoryUpdateEvent)
            and event.phase is EventPhase.COMPLETION
            and event.observer_uuid == entity.uuid
            and event.update_reason is SensoryUpdateReason.SELF_MOVEMENT
            and event.cause_event_uuid == entered_effect.uuid
        ]
        assert len(self_updates) == 1
        update_index, self_update = self_updates[0]
        assert update_index < entered_completion_index
        assert self_update.parent_event == entered_effect.uuid
        assert (
            self_update.observer_position_changed
            or self_update.visible_cells_added
            or self_update.visible_cells_removed
            or self_update.seen_cells_added
            or self_update.entity_contacts_changed
            or self_update.entity_contacts_removed
            or self_update.object_contacts_changed
            or self_update.object_contacts_removed
            or self_update.effective_light_levels_changed
            or self_update.sense_modes_changed
            or self_update.passive_perception_changed
            or self_update.visual_access_changed
        )

        replay = Senses.create(source_entity_uuid=entity.uuid)
        for event in events:
            if (
                isinstance(event, SensoryUpdateEvent)
                and event.phase is EventPhase.COMPLETION
                and event.observer_uuid == entity.uuid
            ):
                replay.apply_sensory_update(event)
        assert perception_projection(replay) == perception_projection(entity.senses)


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

    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    open_grid = get_map()
    open_events_before = tuple(EventQueue.get_events_chronological())
    open_tiles_before = open_grid.get_all_tiles()
    open_registered_before = {
        block_uuid: block
        for block_uuid, block in BaseBlock._registry.items()
        if isinstance(block, Tile)
    }
    open_world_before = next(
        event for event in open_events_before
        if isinstance(event, WorldInitializedEvent)
    )
    with pytest.raises(ValueError, match="empty"):
        build_battlefield("battlefield.open_floor_dark")
    assert tuple(EventQueue.get_events_chronological()) == open_events_before
    assert open_grid.get_all_object_placements() == ()
    assert open_grid.get_all_connectors() == ()
    assert open_grid.get_spatial_conditions() == []
    open_tiles_after = open_grid.get_all_tiles()
    assert set(open_tiles_after) == set(open_tiles_before)
    assert all(
        open_tiles_after[position] is tile
        for position, tile in open_tiles_before.items()
    )
    open_registered_after = {
        block_uuid: block
        for block_uuid, block in BaseBlock._registry.items()
        if isinstance(block, Tile)
    }
    assert set(open_registered_after) == set(open_registered_before)
    assert all(
        open_registered_after[tile_uuid] is tile
        for tile_uuid, tile in open_registered_before.items()
    )
    assert open_world_before == next(
        event for event in EventQueue.get_events_chronological()
        if isinstance(event, WorldInitializedEvent)
    )


@pytest.mark.parametrize(
    "canceled_event_type",
    (
        EventType.SPATIAL_LIGHT_CHANGED,
        EventType.SPATIAL_EFFECT_INTERACTION,
    ),
    ids=("light-change", "ignite"),
)
def test_authored_dynamic_setup_rejects_public_lifecycle_cancellation(
    canceled_event_type: EventType,
) -> None:
    """Post-world authored setup records cancellation and does not claim success."""
    reset_engine_runtime()
    canceled = []

    def cancel(event, _source_uuid):
        canceled.append(event.event_type)
        return event.cancel(status_message="authored setup canceled")

    handler = EventHandler(
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=canceled_event_type,
                event_phase=EventPhase.DECLARATION,
            ),
        ],
        event_processor=cancel,
    )
    EventQueue.add_event_handler(handler)
    try:
        with pytest.raises(RuntimeError, match="WallTorch"):
            build_battlefield("battlefield.standard_hazards_closed")
    finally:
        handler.remove()

    events = EventQueue.get_events_chronological()
    world = next(
        event
        for event in events
        if event.event_type is EventType.WORLD_INITIALIZED
        and event.phase is EventPhase.EFFECT
    )
    assert isinstance(world, WorldInitializedEvent)
    assert not any(
        event.event_type is EventType.WORLD_INITIALIZED
        and event.phase is EventPhase.COMPLETION
        for event in events
    )
    assert canceled == [canceled_event_type]
    canceled_facts = [
        event
        for event in events
        if event.event_type is canceled_event_type
        and event.phase is EventPhase.CANCEL
        and event.canceled
    ]
    assert len(canceled_facts) == 1
    first_torch_uuid = next(
        placement.object_uuid
        for placement in sorted(
            get_map().get_all_object_placements(),
            key=lambda row: (row.position, str(row.object_uuid)),
        )
        if isinstance(BaseItem.get(placement.object_uuid), WallTorch)
    )
    assert not any(
        isinstance(event, ItemLocationStateEvent)
        and event.item_state.item_uuid == first_torch_uuid
        for event in events
    )


@pytest.mark.parametrize(
    "phase",
    (EventPhase.EXECUTION, EventPhase.EFFECT),
    ids=("execution", "effect"),
)
@pytest.mark.parametrize(
    "attempt",
    ("cancel", "rewrite"),
    ids=("cancel", "rewrite"),
)
def test_world_initialized_lifecycle_ignores_handler_attempts(
    phase: EventPhase,
    attempt: str,
) -> None:
    """World bootstrap stores every phase without a handler veto or rewrite."""
    reset_engine_runtime()
    handler_calls = []

    def attempt_mutation(event, _source_uuid):
        handler_calls.append(event)
        if attempt == "cancel":
            return event.cancel(status_message="world lifecycle veto")
        return event.model_copy(update={"battlefield_name": "tampered"})

    handler = EventHandler(
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.WORLD_INITIALIZED,
                event_phase=phase,
            )
        ],
        event_processor=attempt_mutation,
    )
    EventQueue.add_event_handler(handler)
    try:
        built = build_battlefield("battlefield.standard_hazards_closed")
    finally:
        handler.remove()

    world_events = [
        event
        for event in EventQueue.get_events_chronological()
        if isinstance(event, WorldInitializedEvent)
    ]
    assert handler_calls == []
    assert [event.phase for event in world_events] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert all(
        event.battlefield_id == built.definition.battlefield_id
        and event.battlefield_name == built.definition.title
        for event in world_events
    )


def test_cold_world_plus_dynamic_facts_reproduces_live_authored_state() -> None:
    """Detached public facts settle the same condition, light, and item state."""
    reset_engine_runtime()
    built = build_battlefield("battlefield.standard_hazards_closed")
    events = EventQueue.get_events_chronological()
    world = next(
        event
        for event in events
        if isinstance(event, WorldInitializedEvent)
        and event.phase is EventPhase.COMPLETION
    )

    detached_items = {
        row.item.item_uuid: row.item
        for row in world.objects
    }
    detached_light = {
        state.position: state.resolved_light.value
        for state in world.tiles
    }
    detached_condition = None
    for event in events[1:]:
        if (
            isinstance(event, SpatialEffectChangeEvent)
            and event.phase is EventPhase.COMPLETION
            and event.operation is SpatialEffectChangeOperation.CREATED
        ):
            detached_condition = (
                event.spatial_effect_uuid,
                set(event.affected_positions),
                event.spatial_effect_content_ref,
            )
        elif (
            isinstance(event, SpatialChangeEvent)
            and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
            and event.phase is EventPhase.COMPLETION
        ):
            for key, level in (event.light_level_map or {}).items():
                x, y = (int(value) for value in key.split(","))
                detached_light[(x, y)] = level
        elif isinstance(event, ItemLocationStateEvent):
            detached_items[event.item_state.item_uuid] = event.item_state

    live_items = {
        placement.object_uuid: BaseItem.get(placement.object_uuid).to_item_state()
        for placement in get_map().get_all_object_placements()
        if BaseItem.get(placement.object_uuid) is not None
    }
    assert detached_items == live_items
    assert detached_light == {
        position: tile.resolved_light_level.value
        for position, tile in get_map().get_all_tiles().items()
    }
    assert detached_condition is not None
    live_condition = BaseCondition.get(built.environment.spike_condition_uuid)
    assert live_condition is not None
    assert detached_condition[:2] == (
        live_condition.uuid,
        set(live_condition.affected_positions),
    )
    assert detached_condition[2] == live_condition.content_ref


def test_world_initialized_round_trip_preserves_cliff_and_wall_torch_boundary_state() -> None:
    """Cold world facts precede settled authored condition and light state."""
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
    assert all(torch.is_lit for torch in standard.environment.wall_torches)
    assert all(
        torch.get_attached_light_sources()
        for torch in standard.environment.wall_torches
    )
    assert (
        BaseItem.get(standard.environment.trap_lever.uuid)
        is standard.environment.trap_lever
    )
    standard_condition = BaseCondition.get(standard.environment.spike_condition_uuid)
    assert standard_condition is not None
    assert standard_condition.applied
    assert set(standard_condition.affected_positions) == {
        (x, y) for x in range(5) for y in range(11, 15)
    }
    standard_torch_state = next(
        state
        for state in standard_world.objects
        if state.placement.object_uuid == standard_torch.uuid
    )
    assert standard_torch_state.item.light_source is not None
    assert standard_torch_state.item.light_source.is_lit is False
    assert standard_torch.to_item_state().light_source is not None
    assert standard_torch.to_item_state().light_source.is_lit is True
    assert standard_torch_state.item.boundary_structure is None
    lever_state = next(
        state
        for state in standard_world.objects
        if state.placement.object_uuid == standard.environment.trap_lever.uuid
    )
    assert (
        lever_state.item.linked_spatial_condition_uuid
        == standard.environment.spike_condition_uuid
    )
    lever_actions = [
        action
        for action in standard.environment.trap_lever.use_action_templates
        if isinstance(action, PullLeverAction)
    ]
    assert len(lever_actions) == 1
    assert (
        lever_state.item.linked_spatial_condition_uuid
        == lever_actions[0].trap_condition_uuid
        == standard.environment.spike_condition_uuid
        == standard_condition.uuid
    )
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
    torch_item_facts = [
        event
        for event in EventQueue.get_events_chronological()
        if isinstance(event, ItemLocationStateEvent)
        and event.item_state.item_uuid == standard_torch.uuid
    ]
    assert len(torch_item_facts) == 1
    torch_item_fact = torch_item_facts[0]
    assert torch_item_fact.item_state == standard_torch.to_item_state()
    assert torch_item_fact.world_placement == standard_torch_state.placement
    ignite = [
        event
        for event in EventQueue.get_events_chronological()
        if isinstance(event, SpatialEffectInteractionEvent)
        and event.source_object_uuid == standard_torch.uuid
        and event.operation.value == "ignite"
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(ignite) == 1
    world_effects = [
        event
        for event in EventQueue.get_events_chronological()
        if isinstance(event, WorldInitializedEvent)
        and event.phase is EventPhase.EFFECT
    ]
    assert len(world_effects) == 1
    world_completion = next(
        event
        for event in EventQueue.get_events_chronological()
        if isinstance(event, WorldInitializedEvent)
        and event.phase is EventPhase.COMPLETION
    )
    assert torch_item_fact.parent_event == world_effects[0].uuid
    chronological_indices = {
        event.uuid: index
        for index, event in enumerate(EventQueue.get_events_chronological())
    }
    assert chronological_indices[ignite[0].uuid] < chronological_indices[torch_item_fact.uuid]
    assert chronological_indices[torch_item_fact.uuid] < chronological_indices[world_completion.uuid]
    EventQueue.reset()
    detached_standard_world = standard_world.model_copy(update={"use_register": False})
    restored_standard = WorldInitializedEvent.model_validate_json(
        detached_standard_world.model_dump_json(),
    )
    assert restored_standard == detached_standard_world
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
    detached_proving_world = proving_world.model_copy(update={"use_register": False})
    restored_proving = WorldInitializedEvent.model_validate_json(
        detached_proving_world.model_dump_json(),
    )
    assert restored_proving == detached_proving_world
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
