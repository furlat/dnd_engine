"""Exact geometry coverage retained from the displaced AoE shape matrix."""

from typing import Optional
from uuid import uuid4

from dnd.core.aoe import Cone, Cube, Line, Sphere
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialChangeEvent,
    SpatialChangeType,
    SpatialHandler,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    reset_spell_regression_arena,
)


def test_aoe_shapes_preserve_extent_width_entities_and_wall_occlusion() -> None:
    """Sphere, cone, line, and both cube anchors retain their runtime geometry."""
    reset_spell_regression_arena(20, 15)
    grid = get_map()
    source_uuid = uuid4()
    center_target = create_spell_regression_actor(
        "Sphere Center",
        (5, 5),
        "monsters",
    )
    edge_target = create_spell_regression_actor(
        "Sphere Edge",
        (7, 5),
        "monsters",
    )
    outside_target = create_spell_regression_actor(
        "Sphere Outside",
        (10, 5),
        "monsters",
    )
    Entity.update_all_entities_senses(max_distance=100)

    sphere = Sphere(
        source_entity_uuid=source_uuid,
        target=(5, 5),
        radius_feet=10,
    )
    sphere.compute_objective(caster_pos=(0, 0))

    assert (5, 5) in sphere.affected_positions
    assert (3, 5) in sphere.affected_positions
    assert (7, 5) in sphere.affected_positions
    assert (8, 5) not in sphere.affected_positions
    assert center_target.uuid in sphere.affected_entity_uuids
    assert edge_target.uuid in sphere.affected_entity_uuids
    assert outside_target.uuid not in sphere.affected_entity_uuids

    cone = Cone(
        source_entity_uuid=source_uuid,
        target=(10, 8),
        length_feet=15,
        angle_degrees=90,
    )
    cone.compute_objective(caster_pos=(5, 8))

    assert (6, 8) in cone.affected_positions
    assert (7, 8) in cone.affected_positions
    assert (4, 8) not in cone.affected_positions

    narrow_line = Line(
        source_entity_uuid=source_uuid,
        target=(12, 11),
        length_feet=30,
        width_feet=5,
    )
    narrow_line.compute_objective(caster_pos=(0, 11))
    wide_line = Line(
        source_entity_uuid=source_uuid,
        target=(12, 8),
        length_feet=20,
        width_feet=15,
    )
    wide_line.compute_objective(caster_pos=(0, 8))

    assert {(0, 11), (3, 11), (6, 11)} <= narrow_line.affected_positions
    assert (3, 13) not in narrow_line.affected_positions
    assert {(0, 7), (0, 8), (0, 9), (2, 8)} <= wide_line.affected_positions

    centered_cube = Cube(
        source_entity_uuid=source_uuid,
        target=(14, 4),
        size_feet=15,
        centered=True,
    )
    centered_cube.compute_objective(caster_pos=(0, 0))
    directional_cube = Cube(
        source_entity_uuid=source_uuid,
        target=(12, 2),
        size_feet=15,
        centered=False,
    )
    directional_cube.compute_objective(caster_pos=(7, 2))

    assert centered_cube.affected_positions == {
        (x, y)
        for x in range(13, 16)
        for y in range(3, 6)
    }
    assert {(7, 1), (7, 2), (7, 3), (8, 2), (9, 2)} <= (
        directional_cube.affected_positions
    )

    even_centered_cube = Cube(
        source_entity_uuid=source_uuid,
        target=(14, 4),
        size_feet=20,
        centered=True,
    )
    even_centered_cube.compute_objective(caster_pos=(0, 0))
    assert even_centered_cube.affected_positions == {
        (x, y)
        for x in range(12, 16)
        for y in range(2, 6)
    }

    grid.set_tile(5, 11, walkable=False, visible=False, name="Line Wall")
    blocked_line = Line(
        source_entity_uuid=source_uuid,
        target=(15, 11),
        length_feet=50,
        width_feet=5,
    )
    blocked_line.compute_objective(caster_pos=(0, 11))
    assert (4, 11) in blocked_line.affected_positions
    assert (6, 11) not in blocked_line.affected_positions

    grid.set_tile(7, 5, walkable=False, visible=False, name="Sphere Wall")
    blocked_sphere = Sphere(
        source_entity_uuid=source_uuid,
        target=(5, 5),
        radius_feet=20,
    )
    blocked_sphere.compute_objective(caster_pos=(0, 0))
    assert (6, 5) in blocked_sphere.affected_positions
    assert (8, 5) not in blocked_sphere.affected_positions


def test_spatial_registry_dispatches_multiple_indexed_and_global_handlers() -> None:
    """Add, move, remove, coexistence, compatibility, and reset stay explicit."""
    reset_spell_regression_arena(4, 4)
    source_uuid = uuid4()
    mover_uuid = uuid4()
    indexed_calls: list[str] = []
    global_calls: list[str] = []

    def indexed_processor(
        event: SpatialChangeEvent,
        _handler_source_uuid,
    ) -> Optional[SpatialChangeEvent]:
        indexed_calls.append(event.name)
        return event

    first = SpatialHandler(
        name="First indexed handler",
        source_entity_uuid=source_uuid,
        positions={(1, 1)},
        event_type=EventType.SPATIAL_ENTITY_ENTERED,
        event_phase=EventPhase.EFFECT,
        event_processor=indexed_processor,
    )
    second = SpatialHandler(
        name="Second indexed handler",
        source_entity_uuid=source_uuid,
        positions={(1, 1)},
        event_type=EventType.SPATIAL_ENTITY_ENTERED,
        event_phase=EventPhase.EFFECT,
        event_processor=indexed_processor,
    )
    EventQueue.add_spatial_handler(first)
    EventQueue.add_spatial_handler(second)

    def global_processor(
        event: Event,
        _handler_source_uuid,
    ) -> Optional[Event]:
        global_calls.append(event.name)
        return event

    global_handler = EventHandler(
        name="Global spatial event handler",
        source_entity_uuid=source_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
            )
        ],
        event_processor=global_processor,
    )
    EventQueue.add_event_handler(global_handler)

    def entered(position: tuple[int, int]) -> SpatialChangeEvent:
        return SpatialChangeEvent(
            name=f"entered {position}",
            source_entity_uuid=mover_uuid,
            entity_uuid=mover_uuid,
            position=position,
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            change_type=SpatialChangeType.ENTITY_ENTERED,
            phase=EventPhase.EFFECT,
            use_register=False,
        )

    EventQueue.register(entered((1, 1)))

    assert indexed_calls == ["entered (1, 1)", "entered (1, 1)"]
    assert global_calls == ["entered (1, 1)"]
    assert EventQueue.get_spatial_handlers_at((1, 1)) == [first, second]

    assert EventQueue.update_spatial_handler_positions(first.uuid, {(2, 2)})
    assert EventQueue.remove_spatial_handler(second.uuid)
    assert EventQueue.get_spatial_handlers_at((1, 1)) == []
    assert EventQueue.get_spatial_handlers_at((2, 2)) == [first]

    EventQueue.register(entered((2, 2)))

    assert indexed_calls[-1] == "entered (2, 2)"
    assert global_calls[-1] == "entered (2, 2)"

    EventQueue.reset()

    assert EventQueue._spatial_handlers == {}
    assert EventQueue._spatial_handlers_by_position == {}
    assert EventQueue.get_spatial_handlers_at((2, 2)) == []
    assert all(
        not handlers_by_position
        for handlers_by_position in EventQueue._spatial_handlers_by_position.values()
    )
