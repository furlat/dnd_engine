"""Exact geometry coverage retained from the displaced AoE shape matrix."""

from typing import Optional
from uuid import uuid4

from dnd.core.aoe import Cone, Cube, Line, Sphere, objective_footprint
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

    sphere = objective_footprint(Sphere(radius_feet=10), (5, 5), (0, 0))
    occupants = {identity for cell in sphere for identity in grid.get_entities_at(cell)}

    assert (5, 5) in sphere
    assert (3, 5) in sphere
    assert (7, 5) in sphere
    assert (8, 5) not in sphere
    assert center_target.uuid in occupants
    assert edge_target.uuid in occupants
    assert outside_target.uuid not in occupants

    cone = objective_footprint(Cone(length_feet=15, angle_degrees=90), (10, 8), (5, 8))

    assert (6, 8) in cone
    assert (7, 8) in cone
    assert (4, 8) not in cone

    narrow_line = objective_footprint(Line(length_feet=30, width_feet=5), (12, 11), (0, 11))
    wide_line = objective_footprint(Line(length_feet=20, width_feet=15), (12, 8), (0, 8))

    assert {(0, 11), (3, 11), (6, 11)} <= narrow_line
    assert (3, 13) not in narrow_line
    assert {(0, 7), (0, 8), (0, 9), (2, 8)} <= wide_line

    centered_cube = objective_footprint(Cube(size_feet=15, centered=True), (14, 4), (0, 0))
    directional_cube = objective_footprint(Cube(size_feet=15, centered=False), (12, 2), (7, 2))

    assert centered_cube == {
        (x, y)
        for x in range(13, 16)
        for y in range(3, 6)
    }
    assert {(7, 1), (7, 2), (7, 3), (8, 2), (9, 2)} <= directional_cube

    grid.set_tile(5, 11, walking_cost=0, blocks_optics=True, blocks_propagation=True, name="Line Wall")
    blocked_line = objective_footprint(Line(length_feet=50, width_feet=5), (15, 11), (0, 11))
    assert (4, 11) in blocked_line
    assert (6, 11) not in blocked_line

    Entity.update_entity_position(edge_target, (7, 4))
    grid.set_tile(7, 5, walking_cost=0, blocks_optics=True, blocks_propagation=True, name="Sphere Wall")
    blocked_sphere = objective_footprint(Sphere(radius_feet=20), (5, 5), (0, 0))
    assert (6, 5) in blocked_sphere
    assert (8, 5) not in blocked_sphere


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
