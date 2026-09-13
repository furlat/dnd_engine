"""Native world/sensory after-values preserve AI knowledge after runtime reset."""

from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter

from dnd.actor_projection import condition_fact
from dnd.ai.contracts.observation import ObservationTileFact
from dnd.ai.runtime.subjective_projection import project_visible_tile_fact
from dnd.ai.runtime.world_projection import project_object, project_tile
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import HazardFilter
from dnd.core.events import Event, EventPhase, EventQueue, EventType, SensoryUpdateEvent, WorldInitializedEvent
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entity import Entity, EntityConfig
from dnd.items.environment import DirectionalDoor
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.transmutation import SpikeGrowthZone
from dnd.types.actor_facts import ConditionFact
from dnd.types.senses import SensesSnapshot, reduce_senses_snapshot
from dnd.types.world import CardinalDirection
from dnd.world_authoring import set_world_tile
from dnd.world_facts import WorldFacts, apply_world_fact
from game.event_record import RecordedEvent
from game.presentation import _retained_event
from tests.engine.support import create_test_entity


ROWS = TypeAdapter(list[tuple[RecordedEvent, ConditionFact | None]])


def recorded(observer_uuid: UUID) -> bytes:
    return ROWS.dump_json([
        (_retained_event(event, observer_uuid), condition_fact(event, source_index=index))
        for index, event in EventQueue.iter_events_since(0)
    ])


def replay(blob: bytes, observer_uuid: UUID) -> tuple[WorldFacts, SensesSnapshot | None]:
    world = WorldFacts()
    senses = None
    for event, condition in ROWS.validate_json(blob):
        if event.phase is not EventPhase.COMPLETION or event.canceled:
            continue
        apply_world_fact(world, event, condition)
        if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == observer_uuid:
            senses = reduce_senses_snapshot(observer_uuid, senses, event)
    return world, senses


def tile_checkpoint(observer_uuid: UUID) -> tuple[bytes, list[ObservationTileFact]]:
    from_observer = [str(observer_uuid)]
    # The independent live projector is the existing behavior being preserved.
    observer = Entity.get(observer_uuid)
    assert observer is not None
    expected = [project_visible_tile_fact(position, from_observer)
                for position in sorted(observer.senses.visible)]
    return recorded(observer_uuid), expected


def check_saved_tiles(checkpoints: list[tuple[bytes, list[ObservationTileFact]]], observer_uuid: UUID) -> None:
    reset_engine_runtime()
    for blob, expected in checkpoints:
        world, senses = replay(blob, observer_uuid)
        assert senses is not None
        actual = [project_tile(world, row.position, [str(observer_uuid)], {observer_uuid: senses})
                  for row in expected]
        assert actual == expected
    assert EventQueue.event_cursor() == 0
    assert not get_map().get_all_tiles()


def test_raw_rectangle_and_live_edits_replay_complete_support_without_a_catalog_seed() -> None:
    reset_engine_runtime(grid_size=(3, 2))
    grid = get_map()
    assert not any(isinstance(event, WorldInitializedEvent) for _, event in EventQueue.iter_events_since(0))
    assert grid.set_tile_elevation((1, 0), height=2, surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    assert set_world_tile((2, 0), author_uuid=uuid4(), name="Water", walking_cost=0, swimming_cost=3)
    assert grid.remove_tile(2, 1)
    expected = {position: tile.to_world_tile_state() for position, tile in grid.get_all_tiles().items()}
    observer = uuid4()
    blob = recorded(observer)
    reset_engine_runtime()
    world, senses = replay(blob, observer)
    assert senses is None
    assert world.tiles == expected
    assert world.tiles[(1, 0)].elevation_steps == 2
    assert world.tiles[(2, 0)].swimming_cost == 3
    assert (2, 1) not in world.tiles
    assert EventQueue.event_cursor() == 0


def test_catalog_rectangle_stays_inside_its_existing_world_initialization() -> None:
    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    completed = [event for _, event in EventQueue.iter_events_since(0) if event.phase is EventPhase.COMPLETION]
    assert len(completed) == 1 and isinstance(completed[0], WorldInitializedEvent)
    observer = uuid4()
    expected = {position: tile.to_world_tile_state() for position, tile in get_map().get_all_tiles().items()}
    blob = recorded(observer)
    reset_engine_runtime()
    assert replay(blob, observer)[0].tiles == expected


@pytest.mark.parametrize("base_height", (0, 3))
def test_recorded_door_sides_preserve_height_contacts_and_open_close_state(base_height: int) -> None:
    reset_engine_runtime(grid_size=(5, 3))
    observer = create_test_entity(name="Observer", config=EntityConfig(position=(0, 1)))
    door = DirectionalDoor(source_entity_uuid=uuid4(), item_id="test.recorded_world.door")
    door.place_on_grid((1, 1), boundary_direction=CardinalDirection.EAST, base_height_steps=base_height)
    checkpoints = [tile_checkpoint(observer.uuid)]
    door.open()
    checkpoints.append(tile_checkpoint(observer.uuid))
    opened = recorded(observer.uuid)
    door.close()
    checkpoints.append(tile_checkpoint(observer.uuid))
    assert get_map().remove_object(door.uuid)
    checkpoints.append(tile_checkpoint(observer.uuid))
    identity, observer_uuid = door.uuid, observer.uuid
    check_saved_tiles(checkpoints, observer_uuid)
    world, _ = replay(opened, observer_uuid)
    fact = project_object(world, identity, (1, 1), [str(observer_uuid)])
    assert fact is not None
    assert fact.state["is_open"] is True
    assert identity not in replay(checkpoints[-1][0], observer_uuid)[0].objects


def test_tile_condition_and_independent_area_hazards_publish_without_contact_changes() -> None:
    reset_engine_runtime(grid_size=(5, 3))
    observer = create_test_entity(name="Observer", config=EntityConfig(position=(0, 1)))
    tile = get_map().get_tile(2, 1)
    assert tile is not None
    initial = tile_checkpoint(observer.uuid)
    cursor = EventQueue.event_cursor()
    applied = tile.add_condition(BaseCondition(
        name="Exposed trap", source_entity_uuid=uuid4(), target_entity_uuid=tile.uuid,
        hazard_filter=HazardFilter.ALL,
    ))
    assert applied is not None and not applied.canceled
    updates = [event for _, event in EventQueue.iter_events_since(cursor)
               if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == observer.uuid
               and event.hazardous_cells_changed.get("2,1") is True]
    assert updates and all(not event.visible_cells_added and not event.visible_cells_removed
                           and not event.entity_contacts_changed and not event.object_contacts_changed
                           for event in updates)
    trapped = tile_checkpoint(observer.uuid)
    assert tile.remove_condition("Exposed trap")
    cleared = tile_checkpoint(observer.uuid)
    cause = Event(source_entity_uuid=observer.uuid, event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT)
    zone = SpikeGrowthZone(source_entity_uuid=uuid4(), position=(2, 1), zone_radius_feet=0, spell_dc=0)
    assert zone.activate(parent_event=cause) is not None
    area = tile_checkpoint(observer.uuid)
    assert tile.active_conditions == {}
    assert observer.senses.hazardous_cells[(2, 1)] is True
    assert zone.remove_from_runtime_owner(parent_event=cause)
    ended = tile_checkpoint(observer.uuid)
    assert observer.senses.hazardous_cells[(2, 1)] is False
    observer_uuid = observer.uuid
    check_saved_tiles([initial, trapped, cleared, area, ended], observer_uuid)
    area_world, _ = replay(area[0], observer_uuid)
    assert area_world.tiles[(2, 1)].condition_names == ()
    assert area_world.tiles[(2, 1)].walking_cost == 2
