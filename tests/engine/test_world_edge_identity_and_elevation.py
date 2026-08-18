"""Canonical world-edge identity and elevation authoring contracts."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.base_tiles import Tile
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.events.world_events import (
    TileElevationChangeEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.values import BaseValue
from dnd.core.world_edges import AdjacentEdgeKey, ElevationSurfaceKind, SlopeAxis
from dnd.types.world import WorldEdgeChannel
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.entities.entity import Entity
from tests.engine.support import reset_combat_state
from tests.engine.test_combat_actions import reset_core_action_state, strong_entity
from server.api_models import (
    MapEditorGridBounds,
    MapEditorMapSnapshot,
    MapEditorSavedMapDocument,
    MapEditorSavedMapMetadata,
    MapEditorTilePatch,
)
from server.mapeditor_support import (
    _preflight_saved_editor_map,
    apply_tile_patches,
)
from server.world_contracts import APITile
from server.world_projection import project_grid


def reset_grid() -> None:
    reset_combat_state()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(0, 0, 3, 2)


def test_adjacent_edge_key_is_cardinal_canonical_and_strict() -> None:
    expected = AdjacentEdgeKey(first=(1, 2), second=(2, 2))
    assert AdjacentEdgeKey.between((2, 2), (1, 2)) == expected
    assert AdjacentEdgeKey.between((1, 2), (2, 2)) == expected
    with pytest.raises(ValueError):
        AdjacentEdgeKey.between((1, 1), (2, 2))
    with pytest.raises(TypeError):
        AdjacentEdgeKey.between((True, 1), (1, 1))


def test_tile_elevation_tuple_is_exact_and_internally_coherent() -> None:
    with pytest.raises(ValidationError):
        Tile.create((0, 0), height=True)
    with pytest.raises(ValidationError):
        Tile.create((0, 0), height=1, slope_axis=SlopeAxis.EAST_WEST)
    with pytest.raises(ValidationError):
        Tile.create((0, 0), height=1, elevation_surface_kind=ElevationSurfaceKind.RAMP)

    tile = Tile.create(
        (0, 0),
        height=-2,
        elevation_surface_kind=ElevationSurfaceKind.STAIRS,
        slope_axis=SlopeAxis.NORTH_SOUTH,
    )
    assert tile.height == -2


def test_world_edge_is_one_reciprocal_objective_structural_fact() -> None:
    reset_grid()
    grid = get_map()
    first = grid.get_tile(0, 0)
    second = grid.get_tile(1, 0)
    assert first is not None and second is not None
    grid.set_tile_elevation(
        (1, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.RAMP,
        slope_axis=SlopeAxis.EAST_WEST,
    )
    grid.set_tile_directional_border((0, 0), "movement", "east", False)

    forward = grid.get_world_edge((0, 0), (1, 0))
    reverse = grid.get_world_edge((1, 0), (0, 0))

    assert forward == reverse
    assert forward.key == AdjacentEdgeKey(first=(0, 0), second=(1, 0))
    assert forward.elevation_delta_steps == 1
    assert forward.first_tile_uuid == first.uuid
    assert forward.second_tile_uuid == second.uuid
    assert any(
        contribution.provider_uuid == first.uuid
        and contribution.blocked_channels == (WorldEdgeChannel.MOVEMENT,)
        for contribution in forward.structural_contributions
    )


def test_world_edge_structural_provider_identity_survives_door_state() -> None:
    reset_grid()
    grid = get_map()
    wall = DirectionalWall(source_entity_uuid=uuid4())
    door = DirectionalDoor(source_entity_uuid=uuid4())
    grid.place_object(wall.uuid, (0, 0))
    grid.place_object(door.uuid, (0, 0))

    closed = grid.get_world_edge((0, 0), (1, 0))
    closed_by_provider = {
        row.provider_uuid: row.blocked_channels
        for row in closed.structural_contributions
    }
    assert closed_by_provider[wall.uuid] == tuple(WorldEdgeChannel)
    assert closed_by_provider[door.uuid] == tuple(WorldEdgeChannel)

    door.open()
    opened = grid.get_world_edge((1, 0), (0, 0))
    opened_by_provider = {
        row.provider_uuid: row.blocked_channels
        for row in opened.structural_contributions
    }
    assert opened_by_provider[wall.uuid] == tuple(WorldEdgeChannel)
    assert opened_by_provider[door.uuid] == ()


def test_elevation_mutation_noop_cancel_and_completion_are_exact() -> None:
    reset_grid()
    grid = get_map()
    before_revision = grid.movement_revision

    assert not grid.set_tile_elevation(
        (0, 0),
        height=0,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )
    assert grid.movement_revision == before_revision

    source_uuid = uuid4()
    handler = EventHandler(
        name="Veto elevation",
        source_entity_uuid=source_uuid,
        trigger_conditions=[
            Trigger(
                name="Veto elevation declaration",
                event_type=EventType.SPATIAL_TILE_CHANGED,
                event_phase=EventPhase.DECLARATION,
            )
        ],
        event_processor=lambda event, _source: event.cancel("No elevation change"),
    )
    EventQueue.add_event_handler(handler)
    try:
        assert not grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.STAIRS,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)

    tile = grid.get_tile(0, 0)
    assert tile is not None
    assert tile.height == 0

    assert grid.set_tile_elevation(
        (0, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.STAIRS,
        slope_axis=SlopeAxis.EAST_WEST,
    )
    assert tile.height == 1
    completion_events = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if event.phase is EventPhase.COMPLETION
        and getattr(event, "new_height_steps", None) == 1
    ]
    assert len(completion_events) == 1


def test_elevation_handler_cannot_forge_queue_or_observer_evidence() -> None:
    reset_grid()
    grid = get_map()
    forged_child = uuid4()
    forged_turn = uuid4()
    handler = EventHandler(
        name="Forge elevation evidence",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Forge declaration",
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=lambda event, _source: event.post(
            turn_execution_id=forged_turn,
            children_events=[forged_child],
            located_position_observer_uuids={"0,0": {str(uuid4())}},
        ),
    )
    EventQueue.add_event_handler(handler)
    try:
        assert not grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)

    tile = grid.get_tile(0, 0)
    assert tile is not None and tile.height == 0
    elevation_versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if getattr(event, "new_height_steps", None) == 1
    ]
    assert [event.phase for event in elevation_versions] == [
        EventPhase.DECLARATION,
        EventPhase.CANCEL,
    ]
    assert all(event.turn_execution_id is None for event in elevation_versions)
    assert all(forged_child not in event.children_events for event in elevation_versions)
    assert all(not event.located_position_observer_uuids for event in elevation_versions)


def test_elevation_handler_forged_child_evidence_vetoes_mutation() -> None:
    reset_grid()
    grid = get_map()
    forged_child = uuid4()
    handler = EventHandler(
        name="Forge only elevation child evidence",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=lambda event, _source: event.model_copy(update={
            "children_events": [forged_child],
        }),
    )
    EventQueue.add_event_handler(handler)
    try:
        assert not grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)

    tile = grid.get_tile(0, 0)
    assert tile is not None and tile.height == 0
    versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if type(event) is TileElevationChangeEvent
    ]
    assert [event.phase for event in versions] == [
        EventPhase.DECLARATION,
        EventPhase.CANCEL,
    ]
    assert all(forged_child not in event.children_events for event in versions)


def test_elevation_commit_rejects_global_tile_registry_replacement() -> None:
    reset_grid()
    grid = get_map()
    tile = grid.get_tile(0, 0)
    assert tile is not None

    def replace_registry_owner(event: Event, _source_uuid: UUID) -> Event:
        impostor = Tile.model_validate(tile.model_dump())
        assert impostor is not tile
        assert BaseBlock.get(tile.uuid) is impostor
        return event

    handler = EventHandler(
        name="Replace elevation support registry owner",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=replace_registry_owner,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert not grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)

    assert grid.get_tile(0, 0) is tile
    assert grid.get_tile_by_uuid(tile.uuid) is tile
    assert tile.height == 0
    versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if type(event) is TileElevationChangeEvent
    ]
    assert [event.phase for event in versions] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.CANCEL,
    ]


def test_elevation_handler_cannot_substitute_a_stored_other_lineage() -> None:
    reset_grid()
    grid = get_map()
    other_tile = grid.get_tile(1, 0)
    assert other_tile is not None
    prestored = TileElevationChangeEvent(
        source_entity_uuid=other_tile.uuid,
        target_entity_uuid=other_tile.uuid,
        position=(1, 0),
        tile_uuid=other_tile.uuid,
        old_height_steps=0,
        new_height_steps=9,
        old_surface_kind=ElevationSurfaceKind.ORDINARY,
        new_surface_kind=ElevationSurfaceKind.ORDINARY,
        modified=True,
        phase=EventPhase.DECLARATION,
        use_register=True,
    )
    handler = EventHandler(
        name="Substitute stored elevation",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Substitute declaration",
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=lambda _event, _source: prestored,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert not grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)

    original = grid.get_tile(0, 0)
    assert original is not None and original.height == 0
    original_versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if getattr(event, "tile_uuid", None) == original.uuid
    ]
    assert [event.phase for event in original_versions] == [
        EventPhase.DECLARATION,
        EventPhase.CANCEL,
    ]
    assert all(event.lineage_uuid != prestored.lineage_uuid for event in original_versions)


def test_elevation_handler_cannot_mutate_the_stored_validation_baseline() -> None:
    reset_grid()
    grid = get_map()
    forged_child = uuid4()
    forged_turn = uuid4()

    def mutate_stored(event, _source):
        stored = EventQueue.get_event_by_uuid(event.uuid)
        assert isinstance(stored, TileElevationChangeEvent)
        stored.new_height_steps = 9
        stored.turn_execution_id = forged_turn
        stored.children_events.append(forged_child)
        stored.located_position_observer_uuids = {"0,0": {str(uuid4())}}
        return stored

    handler = EventHandler(
        name="Mutate stored elevation baseline",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Mutate stored declaration",
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=mutate_stored,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert not grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)

    tile = grid.get_tile(0, 0)
    assert tile is not None and tile.height == 0
    versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if isinstance(event, TileElevationChangeEvent)
        and event.tile_uuid == tile.uuid
    ]
    assert [event.phase for event in versions] == [
        EventPhase.DECLARATION,
        EventPhase.CANCEL,
    ]
    assert all(event.new_height_steps == 1 for event in versions)
    assert all(event.turn_execution_id is None for event in versions)
    assert all(forged_child not in event.children_events for event in versions)
    assert all(not event.located_position_observer_uuids for event in versions)


def test_elevation_handler_cannot_forge_mutable_queue_field_types() -> None:
    reset_grid()
    grid = get_map()
    handler = EventHandler(
        name="Forge elevation queue types",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Forge declaration queue types",
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=lambda event, _source: event.model_copy(update={
            "uuid": "bad-uuid",
            "timestamp": "bad-time",
            "modified": "yes",
            "status_message": 123,
        }),
    )
    EventQueue.add_event_handler(handler)
    try:
        assert not grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)

    tile = grid.get_tile(0, 0)
    assert tile is not None and tile.height == 0
    versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if isinstance(event, TileElevationChangeEvent)
        and event.tile_uuid == tile.uuid
    ]
    assert [event.phase for event in versions] == [
        EventPhase.DECLARATION,
        EventPhase.CANCEL,
    ]
    assert all(type(event.uuid) is UUID for event in versions)
    assert all(type(event.timestamp) is datetime for event in versions)
    assert all(type(event.modified) is bool for event in versions)
    assert all(
        event.status_message is None or type(event.status_message) is str
        for event in versions
    )


@pytest.mark.parametrize(
    "forged_update",
    [
        {"new_height_steps": True},
        {"position": (False, 0)},
        {"new_surface_kind": "ramp"},
        {"new_slope_axis": "east_west"},
    ],
)
def test_elevation_handler_rejects_equal_valued_wrong_runtime_shapes(
    forged_update: dict[str, object],
) -> None:
    reset_grid()
    grid = get_map()
    handler = EventHandler(
        name="Forge elevation authored type",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Forge elevation authored type declaration",
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=lambda event, _source: event.model_copy(
            update=forged_update,
        ),
    )
    EventQueue.add_event_handler(handler)
    try:
        assert not grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)

    tile = grid.get_tile(0, 0)
    assert tile is not None and tile.height == 0
    versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if isinstance(event, TileElevationChangeEvent)
        and event.tile_uuid == tile.uuid
    ]
    assert [event.phase for event in versions] == [
        EventPhase.DECLARATION,
        EventPhase.CANCEL,
    ]
    assert all(type(event.new_height_steps) is int for event in versions)
    assert all(
        type(event.position) is tuple
        and all(type(coordinate) is int for coordinate in event.position)
        for event in versions
    )
    assert all(
        type(event.new_surface_kind) is ElevationSurfaceKind
        and type(event.new_slope_axis) is SlopeAxis
        for event in versions
    )


def test_elevation_noop_effect_handler_publishes_exactly_four_versions() -> None:
    """A guarded no-op does not manufacture a second authoritative EFFECT."""
    reset_grid()
    grid = get_map()
    tile = grid.get_tile(0, 0)
    assert tile is not None
    immediate = []
    sequences = []
    batches = []

    def capture_event(event) -> None:
        immediate.append(event)

    def capture_sequence(events) -> None:
        sequences.append(tuple(events))

    def capture_batch(events) -> None:
        batches.append(tuple(events))

    handler = EventHandler(
        name="No-op elevation effect",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Observe elevation effect",
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=lambda event, _source: event,
    )
    EventQueue.add_event_handler(handler)
    EventQueue.add_on_event_callback(capture_event)
    EventQueue.add_on_event_sequence_callback(capture_sequence)
    EventQueue.add_on_event_batch_callback(capture_batch)
    try:
        assert grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)
        EventQueue.remove_on_event_callback(capture_event)
        EventQueue.remove_on_event_sequence_callback(capture_sequence)
        EventQueue.remove_on_event_batch_callback(capture_batch)

    versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if type(event) is TileElevationChangeEvent
        and event.tile_uuid == tile.uuid
    ]
    expected_phases = [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert [event.phase for event in versions] == expected_phases
    lineage = versions[0].lineage_uuid
    assert [
        event.phase
        for event in immediate
        if type(event) is TileElevationChangeEvent
        and event.lineage_uuid == lineage
    ] == expected_phases
    assert [
        event.phase
        for sequence in sequences
        for event in sequence
        if type(event) is TileElevationChangeEvent
        and event.lineage_uuid == lineage
    ] == expected_phases
    assert [
        event.phase
        for batch in batches
        for event in batch
        if type(event) is TileElevationChangeEvent
        and event.lineage_uuid == lineage
    ] == expected_phases


def test_elevation_child_emission_preserves_noop_parent_lifecycle() -> None:
    """Queue-authored child linkage does not make an unchanged proposal forged."""
    reset_grid()
    grid = get_map()
    emitted_children: list[Event] = []

    def emit_child(event: Event, _source_uuid: UUID) -> Event:
        child = EventQueue.register(Event(
            source_entity_uuid=event.source_entity_uuid,
            event_type=EventType.BASE_ACTION,
            phase=EventPhase.COMPLETION,
            parent_event=event.uuid,
            use_register=True,
        ))
        emitted_children.append(child)
        return event

    handler = EventHandler(
        name="Elevation effect emits a child",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=emit_child,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)

    assert len(emitted_children) == 1
    versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if type(event) is TileElevationChangeEvent
        and event.position == (0, 0)
    ]
    assert [event.phase for event in versions] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    effect = versions[2]
    assert emitted_children[0].uuid in effect.children_events


def test_elevation_mutation_and_replacement_dirty_materialized_actor_paths() -> None:
    reset_core_action_state()
    actor = strong_entity("Path Owner", (0, 0), "heroes")
    Entity.update_all_entities_senses(max_distance=20)
    assert actor.senses._paths_dirty is False

    grid = get_map()
    grid.set_tile_elevation(
        (1, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.RAMP,
        slope_axis=SlopeAxis.EAST_WEST,
    )
    assert actor.senses._paths_dirty is True

    Entity.update_all_entities_senses(max_distance=20)
    assert actor.senses._paths_dirty is False
    replacement = Tile.create(
        (1, 0),
        height=2,
        elevation_surface_kind=ElevationSurfaceKind.RAMP,
        slope_axis=SlopeAxis.EAST_WEST,
    )
    veto = EventHandler(
        name="Cannot veto committed replacement invalidation",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Veto tile declaration",
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=lambda event, _source: event.cancel("Too late"),
    )
    EventQueue.add_event_handler(veto)
    try:
        grid.set_tile(1, 0, tile=replacement)
        assert actor.senses._paths_dirty is True
    finally:
        EventQueue.remove_event_handler(veto)


def test_removing_ordinary_support_dirties_paths_and_recomputes_fov() -> None:
    reset_core_action_state()
    actor = strong_entity("Removal Observer", (0, 0), "heroes")
    Entity.update_all_entities_senses(max_distance=20)
    assert actor.senses._paths_dirty is False
    assert (1, 0) in actor.senses.visible
    assert (1, 0) in actor.senses.paths

    get_map().remove_tile(1, 0)

    assert actor.senses._paths_dirty is True
    assert (1, 0) not in actor.senses.visible


def test_clear_remove_replace_and_missing_edge_do_not_leave_duplicate_authority() -> None:
    reset_grid()
    grid = get_map()
    edge = grid.get_world_edge((0, 0), (1, 0))
    assert edge.first_tile_uuid != edge.second_tile_uuid

    grid.remove_tile(1, 0)
    with pytest.raises(ValueError):
        grid.get_world_edge((0, 0), (1, 0))


def test_tile_replacement_with_new_elevation_invalidates_movement_topology() -> None:
    reset_grid()
    grid = get_map()
    elevated = Tile.create(
        (1, 0),
        height=3,
        elevation_surface_kind=ElevationSurfaceKind.RAMP,
        slope_axis=SlopeAxis.EAST_WEST,
    )
    grid.set_tile(1, 0, tile=elevated)
    before_revision = grid.movement_revision
    assert grid.get_world_edge((0, 0), (1, 0)).elevation_delta_steps == 3

    replacement = grid.set_tile(1, 0)

    assert replacement.height == 0
    assert grid.movement_revision == before_revision + 1
    assert grid.get_world_edge((0, 0), (1, 0)).elevation_delta_steps == 0

    replacement = grid.set_tile(1, 0)
    assert grid.get_world_edge((0, 0), (1, 0)).second_tile_uuid == replacement.uuid

    grid.clear()
    with pytest.raises(ValueError):
        grid.get_world_edge((0, 0), (1, 0))


def test_invalid_elevated_replacement_preserves_old_tile_and_uuid_index() -> None:
    reset_grid()
    grid = get_map()
    original = grid.get_tile(0, 0)
    assert original is not None
    registry_counts = (
        len(BaseObject._registry),
        len(BaseBlock._registry),
        len(BaseValue._registry),
    )

    with pytest.raises(ValueError, match="require a slope axis"):
        grid.set_tile(
            0,
            0,
            height=1,
            elevation_surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=None,
        )

    assert grid.get_tile(0, 0) is original
    assert grid.get_tile_by_uuid(original.uuid) is original
    assert (
        len(BaseObject._registry),
        len(BaseBlock._registry),
        len(BaseValue._registry),
    ) == registry_counts


def test_mutated_prebuilt_tile_cannot_install_a_malformed_elevation_tuple() -> None:
    reset_grid()
    grid = get_map()
    original = grid.get_tile(0, 0)
    assert original is not None
    candidate = Tile.create((2, 1))
    candidate.height = 1
    candidate.elevation_surface_kind = ElevationSurfaceKind.RAMP
    candidate.slope_axis = None
    registry_counts = (
        len(BaseObject._registry),
        len(BaseBlock._registry),
        len(BaseValue._registry),
    )

    with pytest.raises(ValueError, match="require a slope axis"):
        grid.set_tile(0, 0, tile=candidate)

    assert grid.get_tile(0, 0) is original
    assert grid.get_tile_by_uuid(original.uuid) is original
    assert grid.get_tile_by_uuid(candidate.uuid) is None
    assert (
        len(BaseObject._registry),
        len(BaseBlock._registry),
        len(BaseValue._registry),
    ) == registry_counts


def test_projection_and_editor_patch_carry_one_exact_elevation_tuple() -> None:
    reset_grid()
    snapshot = apply_tile_patches(
        [
            MapEditorTilePatch(
                x=1,
                y=0,
                elevation_steps=-2,
                elevation_surface_kind=ElevationSurfaceKind.RAMP,
                slope_axis=SlopeAxis.EAST_WEST,
            )
        ]
    )
    tile = next(row for row in snapshot.tiles if (row.x, row.y) == (1, 0))
    assert tile.elevation_steps == -2
    assert tile.elevation_steps * 5 == -10
    assert "elevation_feet" not in tile.model_dump()
    assert tile.elevation_surface_kind is ElevationSurfaceKind.RAMP
    assert tile.slope_axis is SlopeAxis.EAST_WEST

    round_trip = APITile.model_validate_json(tile.model_dump_json())
    assert round_trip == tile
    objective = next(
        row for row in project_grid(get_map()).tiles if (row.x, row.y) == (1, 0)
    )
    assert objective == tile

    with pytest.raises(ValidationError):
        MapEditorTilePatch(x=0, y=0, elevation_steps=True)

    payload = tile.model_dump()
    payload.update(elevation_steps=True)
    with pytest.raises(ValidationError):
        APITile.model_validate(payload)
    payload.update(elevation_steps="1")
    with pytest.raises(ValidationError):
        APITile.model_validate(payload)
    payload = tile.model_dump()
    payload["elevation_feet"] = 999
    with pytest.raises(ValidationError):
        APITile.model_validate(payload)

    with pytest.raises(ValidationError):
        MapEditorTilePatch.model_validate({
            "x": 0,
            "y": 0,
            "elevation_feet": 999,
        })


def test_invalid_mixed_editor_elevation_patch_mutates_nothing() -> None:
    reset_grid()
    grid = get_map()
    tile = grid.get_tile(0, 0)
    assert tile is not None
    before_uuid = tile.uuid
    before_light = tile.default_light
    before_border = tile.border_east

    with pytest.raises(ValueError, match="require a slope axis"):
        apply_tile_patches([
            MapEditorTilePatch(
                x=0,
                y=0,
                type="wall",
                light_level=0,
                directional_channel="movement",
                direction="east",
                passable=False,
                elevation_surface_kind=ElevationSurfaceKind.RAMP,
            )
        ])

    after = grid.get_tile(0, 0)
    assert after is not None
    assert after is tile
    assert after.uuid == before_uuid
    assert after.name == "Floor"
    assert after.default_light is before_light
    assert after.border_east is before_border
    assert after.height == 0
    assert after.elevation_surface_kind is ElevationSurfaceKind.ORDINARY


def test_elevation_veto_aborts_mixed_editor_patch_before_other_mutation() -> None:
    reset_grid()
    grid = get_map()
    original = grid.get_tile(0, 0)
    assert original is not None
    before = (
        original.uuid,
        original.name,
        original.default_light,
        original.border_east,
        original.height,
        original.elevation_surface_kind,
        original.slope_axis,
    )
    handler = EventHandler(
        name="Veto editor elevation",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            name="Veto editor elevation declaration",
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=lambda event, _source: event.cancel("Anchored tile"),
    )
    EventQueue.add_event_handler(handler)
    try:
        with pytest.raises(ValueError, match="elevation change was rejected"):
            apply_tile_patches([
                MapEditorTilePatch(
                    x=0,
                    y=0,
                    type="wall",
                    light_level=0,
                    directional_channel="movement",
                    direction="east",
                    passable=False,
                    elevation_steps=1,
                    elevation_surface_kind=ElevationSurfaceKind.RAMP,
                    slope_axis=SlopeAxis.EAST_WEST,
                )
            ])
    finally:
        EventQueue.remove_event_handler(handler)

    after = grid.get_tile(0, 0)
    assert after is original
    assert after is not None
    assert (
        after.uuid,
        after.name,
        after.default_light,
        after.border_east,
        after.height,
        after.elevation_surface_kind,
        after.slope_axis,
    ) == before


def test_saved_map_preflight_rejects_contradictory_progressive_edge() -> None:
    reset_grid()
    projected = project_grid(get_map())
    first = next(tile for tile in projected.tiles if (tile.x, tile.y) == (0, 0))
    second = next(tile for tile in projected.tiles if (tile.x, tile.y) == (1, 0))
    bad_snapshot = MapEditorMapSnapshot(
        grid_bounds=MapEditorGridBounds(min_x=0, min_y=0, max_x=1, max_y=0),
        tiles=[
            first.model_copy(update={
                "elevation_steps": 0,
                "elevation_surface_kind": ElevationSurfaceKind.RAMP,
                "slope_axis": SlopeAxis.EAST_WEST,
            }),
            second.model_copy(update={
                "elevation_steps": 2,
                "elevation_surface_kind": ElevationSurfaceKind.RAMP,
                "slope_axis": SlopeAxis.EAST_WEST,
            }),
        ],
    )
    document = MapEditorSavedMapDocument(
        content_set_digest="0" * 64,
        metadata=MapEditorSavedMapMetadata(
            id="bad-progressive-run",
            name="Bad Progressive Run",
            created_at="2026-08-08T00:00:00Z",
            updated_at="2026-08-08T00:00:00Z",
            grid_bounds=bad_snapshot.grid_bounds,
            tile_count=2,
            floor_object_count=0,
        ),
        snapshot=bad_snapshot,
    )

    with pytest.raises(ValueError, match="contradictory progressive elevation"):
        _preflight_saved_editor_map(document, validate_runtime_state=False)
