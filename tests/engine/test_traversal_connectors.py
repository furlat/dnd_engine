"""Public contracts for exact support-anchored traversal connectors."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.core.base_tiles import Tile
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    TraversalConnectorChangeEvent,
    StepMovementEvent,
    MovementTrajectory,
    Trigger,
)
from dnd.core.action_execution import MovementProvocationPolicy
from dnd.core.gridmap import GridMap
from dnd.core.traversal_connectors import (
    ConnectorProvocationPolicy,
    TraversalConnectorChangeOperation,
    TraversalConnectorDefinition,
    TraversalConnectorKind,
)
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.types.materials import Material, TileSurface
from tests.engine.support import reset_combat_state
from tests.engine.test_combat_actions import strong_entity
from dnd.actions import TraverseConnector, TraverseConnectorEvent


def _connector_grid() -> GridMap:
    reset_combat_state()
    grid = GridMap.get_instance()
    for position, height in (((0, 0), 0), ((1, 0), 1)):
        grid.set_tile(
            *position,
            tile=Tile.create(
                position,
                surface=TileSurface(base_material=Material.STONE),
                height=height,
            ),
        )
    return grid


def _ladder(*, enabled: bool = True) -> TraversalConnectorDefinition:
    return TraversalConnectorDefinition(
        authored_id="connector.test.ladder",
        kind=TraversalConnectorKind.LADDER,
        presentation_key="ladder",
        endpoint_positions=((0, 0), (1, 0)),
        movement_cost_feet=10,
        bidirectional=True,
        enabled=enabled,
        provocation_policy=(
            ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT
        ),
    )


def test_connector_registration_state_changes_and_removal_are_exact() -> None:
    grid = _connector_grid()

    connector = grid.register_connector(_ladder())
    assert connector is not None
    assert grid.get_connector(connector.uuid) == connector
    assert grid.get_connector_by_authored_id(connector.authored_id) == connector
    assert grid.get_connectors_at((0, 0)) == (connector,)
    assert grid.get_connectors_at((1, 0)) == (connector,)
    assert connector.endpoints[0].elevation_feet == 0
    assert connector.endpoints[1].elevation_feet == 5

    disabled = grid.set_connector_enabled(connector.uuid, False)
    assert disabled is not None
    assert disabled.uuid == connector.uuid
    assert disabled.revision == connector.revision + 1
    assert disabled.enabled is False

    assert grid.remove_connector(connector.uuid)
    assert grid.get_connector(connector.uuid) is None
    assert grid.get_connectors_at((0, 0)) == ()
    assert grid.get_connectors_at((1, 0)) == ()

    completions = [
        event
        for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, TraversalConnectorChangeEvent)
        and event.phase is EventPhase.COMPLETION
    ]
    assert [event.operation for event in completions] == [
        TraversalConnectorChangeOperation.REGISTER,
        TraversalConnectorChangeOperation.DISABLE,
        TraversalConnectorChangeOperation.REMOVE,
    ]
    assert completions[0].new_connector == connector
    assert completions[-1].old_connector == disabled


def test_connector_veto_and_support_guard_leave_no_partial_index() -> None:
    grid = _connector_grid()
    starting_revision = grid.connector_revision

    def reject_registration(event: Event, _source_uuid) -> Event:
        return event.cancel("connector rejected")

    handler = EventHandler(
        name="Reject connector registration",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
                event_phase=EventPhase.DECLARATION,
            )
        ],
        event_processor=reject_registration,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert grid.register_connector(_ladder()) is None
    finally:
        EventQueue.remove_event_handler(handler)

    assert grid.connector_revision == starting_revision
    assert grid.get_all_connectors() == ()

    connector = grid.register_connector(_ladder())
    assert connector is not None
    with pytest.raises(ValueError, match="connector is anchored"):
        grid.set_tile_elevation(
            (1, 0),
            height=2,
            surface_kind=ElevationSurfaceKind.ORDINARY,
            slope_axis=None,
        )
    assert grid.get_connector(connector.uuid) == connector


def test_connector_definitions_reject_coercion_and_invalid_vertical_shape() -> None:
    with pytest.raises(ValidationError):
        TraversalConnectorDefinition.model_validate(
            {
                **_ladder().model_dump(),
                "bidirectional": 1,
            }
        )


def test_connector_variant_commits_one_exact_transfer_and_cost() -> None:
    grid = _connector_grid()
    connector = grid.register_connector(_ladder())
    assert connector is not None
    actor = strong_entity(
        "Climber",
        (0, 0),
        "heroes",
        setup_actions=False,
    )
    template = TraverseConnector(
        source_entity_uuid=actor.uuid,
        template=True,
    )
    variants = template.get_discovery_variants(actor)
    assert len(variants) == 1
    variant = variants[0]
    assert isinstance(variant, TraverseConnector)
    assert variant.connector_traversal is not None
    assert variant.connector_traversal.command.connector_uuid == connector.uuid

    movement_before = actor.action_economy.movement.normalized_score
    result = variant.apply()

    assert isinstance(result, TraverseConnectorEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.end_position == (1, 0)
    assert result.objective_end_position == (1, 0)
    assert result.start_elevation_feet == 0
    assert result.end_elevation_feet == 5
    assert actor.position == (1, 0)
    assert actor.action_economy.movement.normalized_score == movement_before - 10
    completed_steps = [
        event
        for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, StepMovementEvent)
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(completed_steps) == 1
    step = completed_steps[0]
    assert step.committed
    assert step.trajectory is MovementTrajectory.CONNECTOR_TRANSFER
    assert step.disclosed_path == ((0, 0), (1, 0))
    assert step.from_elevation_feet == 0
    assert step.to_elevation_feet == 5
    assert step.provocation_policy is MovementProvocationPolicy.ORDINARY_EXIT


def test_connector_step_veto_spends_nothing_and_leaves_actor_at_source() -> None:
    grid = _connector_grid()
    assert grid.register_connector(_ladder()) is not None
    actor = strong_entity(
        "Stopped climber",
        (0, 0),
        "heroes",
        setup_actions=False,
    )
    variant = TraverseConnector(
        source_entity_uuid=actor.uuid,
        template=True,
    ).get_discovery_variants(actor)[0]
    movement_before = actor.action_economy.movement.normalized_score

    def stop_step(event: Event, _source_uuid) -> Event:
        return event.cancel("connector step vetoed")

    handler = EventHandler(
        name="Stop connector Step",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=stop_step,
    )
    EventQueue.add_event_handler(handler)
    try:
        result = variant.apply()
    finally:
        EventQueue.remove_event_handler(handler)

    assert isinstance(result, TraverseConnectorEvent)
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason.value == "step_canceled"
    assert actor.position == (0, 0)
    assert actor.action_economy.movement.normalized_score == movement_before
    with pytest.raises(ValidationError):
        TraversalConnectorDefinition(
            authored_id="connector.test.bad",
            kind=TraversalConnectorKind.LADDER,
            presentation_key="ladder",
            endpoint_positions=((0, 0), (2, 0)),
            movement_cost_feet=5,
            bidirectional=True,
            enabled=True,
            provocation_policy=(
                ConnectorProvocationPolicy.DOES_NOT_PROVOKE
            ),
        )
