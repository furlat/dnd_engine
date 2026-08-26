"""Dnd-only wire contracts for movement evidence and perception facts."""
from dnd.types.materials import Material, TileSurface

from uuid import UUID, uuid4

import pytest

from dnd.actions.standard import Move
from dnd.blocks.base_item import BaseItem
from dnd.blocks.sensory import spatial_senses_system
from dnd.core.events.events_registry import EventPhase, EventQueue, EventType
from dnd.core.events.world_events import (
    SensoryUpdateEvent,
    SpatialChangeEvent,
    StepMovementEvent,
    WorldObjectState,
    WorldTileState,
)
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.types.world import LightLevel
from dnd.types.senses import SenseMode, SensesType
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementKind
from pydantic import ValidationError
from tests.engine.support import create_test_monster, reset_combat_state


def reset_wire_scene() -> None:
    """Build a small event-silent world before entity deployment."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 5, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)


def completed_sensory_updates(observer_uuid: UUID) -> list[SensoryUpdateEvent]:
    """Return stored sensory completion facts for one observer."""
    return [
        event
        for event in EventQueue.get_events_by_type(EventType.SENSORY_UPDATE)
        if isinstance(event, SensoryUpdateEvent)
        and event.phase is EventPhase.COMPLETION
        and event.observer_uuid == observer_uuid
    ]


def test_movement_completion_freezes_both_endpoint_observer_grants() -> None:
    """Each committed edge records who perceived its origin and destination."""
    reset_wire_scene()
    origin_witness = create_test_monster(
        "monster.skeleton", name="Origin witness", position=(0, 0), darkvision=False,
    )
    destination_witness = create_test_monster(
        "monster.skeleton", name="Destination witness", position=(3, 0), darkvision=False,
    )
    mover = create_test_monster(
        "monster.skeleton", name="Mover", position=(1, 0), darkvision=False,
    )
    for witness in (origin_witness, destination_witness):
        witness.has_ordinary_sight = False
        witness.senses.sense_modes = [
            SenseMode(sense_type=SensesType.BLINDSIGHT, range_feet=5)
        ]
        spatial_senses_system.recompute_observer(witness.uuid)

    assert mover.uuid in origin_witness.senses.entities
    assert mover.uuid not in destination_witness.senses.entities
    mover.materialize_navigation(max_distance=4)
    cursor = EventQueue.event_cursor()

    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(2, 0),
        use_movement_cost=False,
    ).apply()

    assert result is not None and not result.canceled
    steps = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, StepMovementEvent)
        and event.phase is EventPhase.COMPLETION
        and event.committed
    ]
    assert len(steps) == 1
    evidence = steps[0].located_position_observer_uuids
    assert mover.uuid not in origin_witness.senses.entities
    assert mover.uuid in destination_witness.senses.entities
    assert str(origin_witness.uuid) in evidence["1,0"]
    assert str(origin_witness.uuid) not in evidence["2,0"]
    assert str(destination_witness.uuid) not in evidence["1,0"]
    assert str(destination_witness.uuid) in evidence["2,0"]
    assert str(mover.uuid) in evidence["1,0"]
    assert str(mover.uuid) in evidence["2,0"]


def test_sensory_update_round_trips_without_generic_observer_grants() -> None:
    """The typed subjective delta is complete without leaking internal grants."""
    reset_wire_scene()
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    update = completed_sensory_updates(observer.uuid)[0]

    restored = SensoryUpdateEvent.model_validate_json(update.model_dump_json())
    wire = update.model_dump(mode="json")
    assert restored.model_dump(mode="json") == wire
    assert "identified_entity_observer_uuids" not in wire
    assert "located_entity_observer_uuids" not in wire
    assert "located_position_observer_uuids" not in wire


def test_bootstrap_tile_and_object_carry_final_optical_channels() -> None:
    """Cold world rows preserve separate optical and propagation policies."""
    tile = WorldTileState(
        tile_uuid=uuid4(),
        position=(1, 0),
        surface=TileSurface(base_material=Material.STONE),
        name="Opaque grate",
        blocks_optics=True,
        blocks_propagation=False,
        walking_cost=1,
        flying_cost=1,
        swimming_cost=1,
        burrowing_cost=1,
        elevation_steps=0,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        default_light=LightLevel.DIM_LIGHT,
        resolved_light=LightLevel.DIM_LIGHT,
    )
    assert WorldTileState.model_validate_json(tile.model_dump_json()) == tile
    assert tile.blocks_optics is True
    assert tile.blocks_propagation is False


def test_slice_6_2_tile_facts_have_strict_four_costs_and_no_walkable_field() -> None:
    """Cold and incremental Tile facts expose the same strict cost authority."""
    tile = WorldTileState(
        tile_uuid=uuid4(),
        position=(1, 0),
        surface=TileSurface(base_material=Material.STONE),
        name="Strict cost tile",
        blocks_optics=False,
        blocks_propagation=False,
        walking_cost=0,
        flying_cost=1,
        swimming_cost=0,
        burrowing_cost=0,
        elevation_steps=0,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        default_light=LightLevel.BRIGHT_LIGHT,
        resolved_light=LightLevel.BRIGHT_LIGHT,
    )
    assert "walkable" not in type(tile).model_fields
    assert tile.model_dump(mode="json")["walking_cost"] == 0
    for invalid in (True, 1.5, "1", -1):
        with pytest.raises(ValidationError):
            WorldTileState.model_validate({**tile.model_dump(), "walking_cost": invalid})

    change = SpatialChangeEvent.tile_changed(
        (1, 0),
        tile_walking_cost=0,
        tile_flying_cost=1,
        tile_swimming_cost=0,
        tile_burrowing_cost=0,
    )
    assert change.tile_walking_cost == 0
    assert change.tile_burrowing_cost == 0
    for invalid in (True, 1.5, "1", -1):
        with pytest.raises(ValidationError):
            SpatialChangeEvent.tile_changed(
                (1, 0),
                tile_walking_cost=invalid,
                tile_flying_cost=1,
                tile_swimming_cost=0,
                tile_burrowing_cost=0,
            )
    with pytest.raises(ValidationError):
        SpatialChangeEvent.model_validate(
            {**change.model_dump(), "tile_walkable": True},
        )

    item = BaseItem(
        source_entity_uuid=uuid4(),
        semantic_key="test.opaque_permeable_object",
        name="Opaque permeable object",
        blocks_optics_field=True,
        blocks_propagation_field=False,
    )
    world_object = WorldObjectState(
        placement=WorldObjectPlacement(
            object_uuid=item.uuid,
            tile_uuid=tile.tile_uuid,
            position=(1, 0),
            kind=WorldPlacementKind.CENTER,
            occupies_bands=False,
            base_height_steps=0,
            top_height_steps=1,
        ),
        item=item.to_item_state(),
    )
    assert WorldObjectState.model_validate_json(world_object.model_dump_json()) == world_object
    assert world_object.item.blocks_optics is True
    assert world_object.item.blocks_propagation is False
