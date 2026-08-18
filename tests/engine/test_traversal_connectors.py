"""Typed vertical-connector ownership, execution, and privacy regressions."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.core.traversal_connectors import (
    ConnectorActionCostType,
    ConnectorProvocationPolicy,
    TraversalConnectorChangeOperation,
    TraversalConnectorDefinition,
    TraversalConnectorKind,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_tiles import Tile
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.types.life import LifeState
from dnd.core.positioning import PositionCommitError, PositionPublicationError
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.core.action_execution import MovementTerminationReason
from dnd.core.events.world_events import (
    MovementTrajectory,
    StepMovementEvent,
)
from dnd.core.combat_log import CombatLogEntryType
from dnd.actions.standard import (
    TraverseConnector,
)
from dnd.core.events.action_events import (
    TraverseConnectorEvent,
)
from dnd.actions.operations import execute_available_action
from tests.engine.support import create_test_monster
from dnd.entities.entity import Entity
from dnd.actions.reactions import add_opportunity_attack_handler
from tests.engine.support import (
    force_attack_hit,
    remove_attack_modifier,
    reset_combat_state,
    set_hp,
)


def connector_definition(
    *,
    kind: TraversalConnectorKind = TraversalConnectorKind.LADDER,
    endpoint_positions: tuple[tuple[int, int], tuple[int, int]] = ((0, 0), (1, 0)),
    action_cost_type: ConnectorActionCostType | None = ConnectorActionCostType.ACTIONS,
    action_cost_amount: int = 1,
    movement_cost_feet: int = 10,
    bidirectional: bool = True,
    enabled: bool = True,
    provocation_policy: ConnectorProvocationPolicy = (
        ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT
    ),
) -> TraversalConnectorDefinition:
    return TraversalConnectorDefinition(
        authored_id="connector.test.ladder",
        kind=kind,
        presentation_key="traversal.ladder",
        endpoint_positions=endpoint_positions,
        movement_cost_feet=movement_cost_feet,
        action_cost_type=action_cost_type,
        action_cost_amount=action_cost_amount,
        bidirectional=bidirectional,
        enabled=enabled,
        provocation_policy=provocation_policy,
    )


def test_connector_definition_is_strict_and_kind_geometry_is_closed() -> None:
    assert connector_definition().endpoint_positions == ((0, 0), (1, 0))
    passage = connector_definition(
        kind=TraversalConnectorKind.PASSAGE,
        endpoint_positions=((0, 0), (4, 4)),
        action_cost_type=None,
        action_cost_amount=0,
    )
    assert passage.kind is TraversalConnectorKind.PASSAGE

    with pytest.raises(ValidationError):
        connector_definition(endpoint_positions=((0, 0), (2, 0)))
    with pytest.raises(ValidationError):
        connector_definition(action_cost_type=None, action_cost_amount=1)
    with pytest.raises(ValidationError):
        connector_definition(action_cost_type=ConnectorActionCostType.ACTIONS, action_cost_amount=0)
    with pytest.raises(ValidationError):
        TraversalConnectorDefinition.model_validate({
            **connector_definition().model_dump(),
            "movement_cost_feet": True,
        })


def test_connector_runtime_uuid_is_not_cold_authored_identity() -> None:
    definition = connector_definition()
    assert not isinstance(definition.authored_id, UUID)


def _connector_grid() -> None:
    reset_combat_state()
    grid = get_map()
    grid.set_tile(0, 0, height=0)
    grid.set_tile(1, 0, height=1)
    grid.set_tile(0, 1, height=2)


def _connector_row(actor: Entity):
    rows = [
        row
        for row in actor.get_available_actions().self_actions
        if row.connector_traversal is not None
    ]
    assert len(rows) == 1
    return rows[0]


def test_gridmap_connector_registry_indexes_lifecycle_and_clear() -> None:
    _connector_grid()
    grid = get_map()
    second = connector_definition().model_copy(update={
        "authored_id": "connector.test.alpha",
        "endpoint_positions": ((0, 0), (0, 1)),
    })
    first = grid.register_connector(connector_definition())
    alpha = grid.register_connector(second)
    assert first is not None
    assert alpha is not None
    assert grid.get_connector(first.uuid) is first
    assert grid.get_connector_by_authored_id(first.authored_id) is first
    assert grid.get_connectors_at((0, 0)) == (alpha, first)
    assert grid.connector_revision == 2
    assert EventQueue.get_events_by_type(
        EventType.TRAVERSAL_CONNECTOR_CHANGED
    )[-1].phase is EventPhase.COMPLETION

    with pytest.raises(ValueError, match="duplicate connector authored_id"):
        grid.register_connector(connector_definition())

    disabled = grid.set_connector_enabled(first.uuid, False)
    assert disabled is not None and disabled.enabled is False
    assert disabled.uuid == first.uuid
    assert disabled.revision == first.revision + 1
    assert disabled.objective_digest != first.objective_digest
    replacement = grid.replace_connector(
        first.uuid,
        disabled.definition().model_copy(update={"movement_cost_feet": 15}),
    )
    assert replacement is not None
    assert replacement.movement_cost_feet == 15
    assert grid.remove_connector(first.uuid) is True
    assert grid.get_connector(first.uuid) is None
    assert grid.get_connectors_at((1, 0)) == ()

    grid.clear()
    assert grid.get_all_connectors() == ()
    assert grid.connector_revision == 0


def test_live_tile_cannot_alias_positions_during_connector_registration() -> None:
    """Connector supports retain reciprocal tile-position identity under handlers."""
    _connector_grid()
    grid = get_map()
    other = grid.set_tile(2, 0, height=0)
    destination = grid.get_tile(1, 0)
    assert destination is not None

    with pytest.raises(ValueError, match="second position"):
        grid.set_tile(2, 0, tile=destination)
    assert grid.get_tile(1, 0) is destination
    assert grid.get_tile(2, 0) is other
    assert grid.get_tile_by_uuid(destination.uuid) is destination
    assert destination.position == (1, 0)

    def attempt_alias(event: Event, _source_uuid: UUID) -> Event:
        with pytest.raises(ValueError, match="second position"):
            grid.set_tile(2, 0, tile=destination)
        return event

    handler = EventHandler(
        name="Attempt connector support alias",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=attempt_alias,
    )
    EventQueue.add_event_handler(handler)
    try:
        connector = grid.register_connector(connector_definition())
    finally:
        EventQueue.remove_event_handler(handler)

    assert connector is not None
    assert grid.connector_supports_are_current(connector)
    grid.remove_tile(2, 0)
    assert grid.get_tile(1, 0) is destination
    assert grid.get_tile_by_uuid(destination.uuid) is destination
    assert grid.get_connector(connector.uuid) is connector
    assert grid.connector_supports_are_current(connector)


def test_tile_uuid_impostor_cannot_become_a_connector_support() -> None:
    """Grid and connector support identity agree with the global registry."""
    _connector_grid()
    grid = get_map()
    canonical = Tile.create((9, 9))
    impostor = canonical.model_copy(deep=True)

    with pytest.raises(ValueError, match="exact global Tile"):
        grid.set_tile(2, 0, tile=impostor)
    assert BaseBlock.get(canonical.uuid) is canonical
    assert grid.get_tile(2, 0) is None

    def attempt_impostor_install(event: Event, _source_uuid: UUID) -> Event:
        with pytest.raises(ValueError, match="exact global Tile"):
            grid.set_tile(1, 0, tile=impostor)
        return event

    handler = EventHandler(
        name="Attempt connector support UUID impostor",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=attempt_impostor_install,
    )
    EventQueue.add_event_handler(handler)
    try:
        connector = grid.register_connector(connector_definition())
    finally:
        EventQueue.remove_event_handler(handler)

    assert connector is not None
    assert grid.connector_supports_are_current(connector)
    support = grid.get_tile(1, 0)
    assert support is not None
    support_impostor = support.model_copy(deep=True)
    BaseBlock._registry[support.uuid] = support_impostor
    assert not grid.connector_supports_are_current(connector)
    BaseBlock._registry[support.uuid] = support
    assert grid.connector_supports_are_current(connector)


def test_connector_change_veto_mutates_no_index_or_revision() -> None:
    _connector_grid()
    grid = get_map()
    veto = EventHandler(
        name="Veto connector registration",
        source_entity_uuid=UUID("00000000-0000-0000-0000-000000000123"),
        trigger_conditions=[Trigger(
            event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=lambda event, _source: event.cancel(
            status_message="connector change vetoed"
        ),
    )
    EventQueue.add_event_handler(veto)

    assert grid.register_connector(connector_definition()) is None
    assert grid.get_all_connectors() == ()
    assert grid.connector_revision == 0
    phases = [
        event.phase
        for event in EventQueue.get_events_by_type(
            EventType.TRAVERSAL_CONNECTOR_CHANGED
        )
    ]
    assert phases == [EventPhase.DECLARATION, EventPhase.CANCEL]


def test_connector_change_effect_forgery_mutates_no_index_or_history_fact() -> None:
    _connector_grid()
    grid = get_map()

    def forge_change(event: Event, _source_uuid: UUID) -> Event:
        if event.event_type is not EventType.TRAVERSAL_CONNECTOR_CHANGED:
            return event
        return event.model_copy(update={
            "connector_uuid": uuid4(),
            "authored_id": "connector.forged.identity",
        })

    handler = EventHandler(
        name="Forge connector change EFFECT",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=forge_change,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert grid.register_connector(connector_definition()) is None
    finally:
        EventQueue.remove_event_handler(handler)

    assert grid.get_all_connectors() == ()
    assert grid.connector_revision == 0
    stored = EventQueue.get_events_by_type(EventType.TRAVERSAL_CONNECTOR_CHANGED)
    assert [event.phase for event in stored] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.CANCEL,
    ]
    assert all(
        getattr(event, "authored_id", None) == "connector.test.ladder"
        for event in stored
    )


def test_connector_register_revalidates_support_after_effect_handlers() -> None:
    """A support removed during EFFECT cannot leave a stale connector index."""
    _connector_grid()
    grid = get_map()

    def remove_destination(event: Event, _source_uuid: UUID) -> Event:
        grid.remove_tile(1, 0)
        return event

    handler = EventHandler(
        name="Remove connector support during registration",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=remove_destination,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert grid.register_connector(connector_definition()) is None
    finally:
        EventQueue.remove_event_handler(handler)

    assert grid.get_all_connectors() == ()
    assert grid.get_connectors_at((1, 0)) == ()
    assert grid.connector_revision == 0
    assert grid.get_tile(1, 0) is None


def test_nested_same_authored_connector_registration_is_serialized() -> None:
    """A nested accepted registration wins; the stale outer proposal cancels."""
    _connector_grid()
    grid = get_map()
    definition = connector_definition()
    nested: list[object] = []
    inside_nested = False

    def register_nested(event: Event, _source_uuid: UUID) -> Event:
        nonlocal inside_nested
        if not inside_nested:
            inside_nested = True
            try:
                nested.append(grid.register_connector(definition))
            finally:
                inside_nested = False
        return event

    handler = EventHandler(
        name="Nested connector registration",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=register_nested,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert grid.register_connector(definition) is None
    finally:
        EventQueue.remove_event_handler(handler)

    assert len(nested) == 1 and nested[0] is not None
    assert len(grid.get_all_connectors()) == 1
    assert grid.get_connector_by_authored_id(definition.authored_id) is nested[0]
    assert grid.connector_revision == 1


@pytest.mark.parametrize("mutation", ["remove", "replace", "elevate"])
def test_connector_replace_revalidates_new_support_after_effect_handlers(
    mutation: str,
) -> None:
    """A replacement never indexes supports changed inside its EFFECT."""
    _connector_grid()
    grid = get_map()
    old = grid.register_connector(connector_definition())
    assert old is not None
    replacement_definition = connector_definition(
        endpoint_positions=((0, 0), (0, 1)),
    )

    def mutate_new_support(event: Event, _source_uuid: UUID) -> Event:
        if getattr(event, "operation", None) is not TraversalConnectorChangeOperation.REPLACE:
            return event
        if mutation == "remove":
            grid.remove_tile(0, 1)
        elif mutation == "replace":
            grid.set_tile(0, 1, height=2)
        else:
            assert grid.set_tile_elevation(
                (0, 1),
                height=3,
                surface_kind=ElevationSurfaceKind.ORDINARY,
                slope_axis=None,
            )
        return event

    handler = EventHandler(
        name=f"Mutate replacement support: {mutation}",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=mutate_new_support,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert grid.replace_connector(old.uuid, replacement_definition) is None
    finally:
        EventQueue.remove_event_handler(handler)

    assert grid.get_connector(old.uuid) is old
    assert grid.get_connectors_at((1, 0)) == (old,)
    assert grid.get_connectors_at((0, 1)) == ()
    assert grid.connector_revision == 1


def test_elevation_commit_rejects_connector_registered_during_effect() -> None:
    """Elevation and connector support commits serialize at the existing boundary."""
    _connector_grid()
    grid = get_map()
    registered: list[object] = []

    def register_on_old_support(event: Event, _source_uuid: UUID) -> Event:
        registered.append(grid.register_connector(connector_definition(
            endpoint_positions=((0, 0), (0, 1)),
        )))
        return event

    handler = EventHandler(
        name="Register connector during elevation EFFECT",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=register_on_old_support,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert grid.set_tile_elevation(
            (0, 1),
            height=3,
            surface_kind=ElevationSurfaceKind.ORDINARY,
            slope_axis=None,
        ) is False
    finally:
        EventQueue.remove_event_handler(handler)

    assert len(registered) == 1 and registered[0] is not None
    tile = grid.get_tile(0, 1)
    assert tile is not None and tile.height == 2
    assert grid.get_all_connectors() == (registered[0],)
    assert grid.connector_revision == 1


def test_connector_remove_revalidates_record_after_nested_replace() -> None:
    """A stale outer removal cannot unindex a replacement committed in EFFECT."""
    _connector_grid()
    grid = get_map()
    old = grid.register_connector(connector_definition())
    assert old is not None
    nested_replacement: list[object] = []
    inside_nested = False

    def replace_during_remove(event: Event, _source_uuid: UUID) -> Event:
        nonlocal inside_nested
        if (
            getattr(event, "operation", None)
            is TraversalConnectorChangeOperation.REMOVE
            and not inside_nested
        ):
            inside_nested = True
            try:
                nested_replacement.append(grid.replace_connector(
                    old.uuid,
                    old.definition().model_copy(update={
                        "movement_cost_feet": 15,
                    }),
                ))
            finally:
                inside_nested = False
        return event

    handler = EventHandler(
        name="Replace connector during outer removal",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
            event_phase=EventPhase.EFFECT,
        )],
        event_processor=replace_during_remove,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert grid.remove_connector(old.uuid) is False
    finally:
        EventQueue.remove_event_handler(handler)

    assert len(nested_replacement) == 1
    replacement = nested_replacement[0]
    assert replacement is not None
    assert grid.get_connector(old.uuid) is replacement
    assert grid.get_connector_by_authored_id(old.authored_id) is replacement
    assert grid.get_connectors_at((0, 0)) == (replacement,)
    assert grid.get_connectors_at((1, 0)) == (replacement,)
    assert grid.connector_revision == 2


def test_connector_support_is_anchored_until_connector_removal() -> None:
    _connector_grid()
    grid = get_map()
    connector = grid.register_connector(connector_definition())
    assert connector is not None

    with pytest.raises(ValueError, match="support height"):
        grid.set_tile_elevation(
            (0, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.ORDINARY,
            slope_axis=None,
        )
    with pytest.raises(ValueError, match="replace a support tile"):
        grid.set_tile(0, 0, height=0)
    with pytest.raises(ValueError, match="remove a support tile"):
        grid.remove_tile(0, 0)

    assert grid.set_tile_elevation(
        (0, 0),
        height=0,
        surface_kind=ElevationSurfaceKind.STAIRS,
        slope_axis=SlopeAxis.EAST_WEST,
    ) is True


def test_connector_discovery_and_atomic_execution_share_one_typed_variant() -> None:
    _connector_grid()
    grid = get_map()
    connector = grid.register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="Connector User",
        position=(0, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)

    available = actor.get_available_actions(legal_only=True)
    rows = [
        row for row in available.self_actions
        if row.connector_traversal is not None
    ]
    assert len(rows) == 1
    row = rows[0]
    discovery = row.connector_traversal
    assert discovery is not None
    assert discovery.command.connector_uuid == connector.uuid
    assert discovery.command.source_position == (0, 0)
    assert discovery.command.destination_position == (1, 0)
    assert str(connector.uuid) in row.template_name
    assert row.can_afford is True

    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.COMPLETED
    assert result.end_position == (1, 0)
    assert result.objective_end_position == (1, 0)
    assert actor.position == (1, 0)
    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.movement.normalized_score == 20
    steps = [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if type(event) is StepMovementEvent
        and event.source_entity_uuid == actor.uuid
    ]
    assert [event.phase for event in steps] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert steps[-1].trajectory is MovementTrajectory.CONNECTOR_TRANSFER
    assert steps[-1].committed is True
    assert result.combat_log is not None
    assert result.combat_log.data["movement_type"] == "connector"
    assert result.combat_log.data["connector_authored_id"] == connector.authored_id


def test_one_way_reverse_and_disabled_connector_have_no_discovery_variant() -> None:
    _connector_grid()
    grid = get_map()
    definition = connector_definition().model_copy(update={"bidirectional": False})
    connector = grid.register_connector(definition)
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="Reverse User",
        position=(1, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)
    assert not any(
        row.connector_traversal is not None
        for row in actor.get_available_actions().self_actions
    )

    Entity.update_entity_position(actor, (0, 0))
    disabled = grid.set_connector_enabled(connector.uuid, False)
    assert disabled is not None
    assert not any(
        row.connector_traversal is not None
        for row in actor.get_available_actions().self_actions
    )
    disabled_connector = grid.get_connector(connector.uuid)
    assert disabled_connector is not None
    assert disabled_connector.uuid == connector.uuid
    assert disabled_connector.authored_id == connector.authored_id
    assert disabled_connector.revision == connector.revision + 1
    assert disabled_connector.enabled is False
    assert grid.remove_connector(connector.uuid) is True
    assert grid.set_tile_elevation(
        (0, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    ) is True


@pytest.mark.parametrize(
    ("policy", "expects_attack"),
    [
        (ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT, True),
        (ConnectorProvocationPolicy.DOES_NOT_PROVOKE, False),
    ],
)
def test_connector_provocation_is_authored_not_inferred_from_kind(
    policy: ConnectorProvocationPolicy,
    expects_attack: bool,
) -> None:
    _connector_grid()
    grid = get_map()
    grid.set_tile(-1, 0, height=0)
    connector = grid.register_connector(connector_definition(
        kind=TraversalConnectorKind.LIFT,
        action_cost_type=None,
        action_cost_amount=0,
        provocation_policy=policy,
    ))
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Connector Mover", position=(0, 0), faction="heroes")
    reactor = create_test_monster("monster.skeleton", name="Connector Watcher", position=(-1, 0), faction="monsters")
    add_opportunity_attack_handler(reactor)
    Entity.update_all_entities_senses(max_distance=20)
    hp_before = actor.get_hp()
    hit = force_attack_hit(reactor)
    try:
        row = _connector_row(actor)
        result = execute_available_action(actor, row, row.valid_targets[0])
    finally:
        remove_attack_modifier(reactor, hit)

    assert type(result) is TraverseConnectorEvent
    assert result.termination_reason is MovementTerminationReason.COMPLETED
    assert actor.position == (1, 0)
    assert (actor.get_hp() < hp_before) is expects_attack
    assert reactor.action_economy.reactions.normalized_score == (0 if expects_attack else 1)
    assert result.combat_log is not None
    nested_types = {
        nested.entry_type
        for step_log in result.combat_log.sub_entries
        for nested in step_log.sub_entries
    }
    assert (CombatLogEntryType.ATTACK in nested_types) is expects_attack


def test_lethal_connector_reaction_stops_before_cost_or_arrival() -> None:
    _connector_grid()
    grid = get_map()
    grid.set_tile(-1, 0, height=0)
    connector = grid.register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Fragile Connector User", position=(0, 0), faction="heroes")
    set_hp(actor, 1)
    Entity.update_all_entities_senses(max_distance=20)

    def lethal_step_reaction(event: Event, _source_uuid: UUID) -> Event:
        set_hp(actor, 0)
        return event

    actor.add_event_handler(EventHandler(
        name="Lethal connector Step reaction",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=actor.uuid,
        )],
        event_processor=lethal_step_reaction,
    ))
    action_costs_before = {
        modifier.uuid
        for modifier in actor.action_economy.get_cost_modifiers("actions")
    }
    movement_costs_before = {
        modifier.uuid
        for modifier in actor.action_economy.get_cost_modifiers("movement")
    }
    row = _connector_row(actor)
    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.DEAD
    assert actor.position == (0, 0)
    assert {
        modifier.uuid
        for modifier in actor.action_economy.get_cost_modifiers("actions")
    } == action_costs_before
    assert {
        modifier.uuid
        for modifier in actor.action_economy.get_cost_modifiers("movement")
    } == movement_costs_before
    completed_steps = [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if type(event) is StepMovementEvent
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(completed_steps) == 1
    assert completed_steps[0].committed is False


def test_stale_or_unaffordable_connector_variant_mutates_nothing() -> None:
    _connector_grid()
    grid = get_map()
    connector = grid.register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Stale Connector User", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)
    stale_row = _connector_row(actor)
    replacement = grid.replace_connector(
        connector.uuid,
        connector.definition().model_copy(update={"movement_cost_feet": 15}),
    )
    assert replacement is not None

    stale_result = execute_available_action(actor, stale_row, stale_row.valid_targets[0])

    assert type(stale_result) is TraverseConnectorEvent
    assert stale_result.phase is EventPhase.CANCEL
    assert actor.position == (0, 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.movement.normalized_score == 30

    costly = grid.replace_connector(
        connector.uuid,
        replacement.definition().model_copy(update={"movement_cost_feet": 35}),
    )
    assert costly is not None
    unaffordable_row = _connector_row(actor)
    assert unaffordable_row.can_afford is False
    result = execute_available_action(
        actor,
        unaffordable_row,
        stale_row.valid_targets[0],
    )

    assert result is None
    assert actor.position == (0, 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.movement.normalized_score == 30


def test_hidden_destination_occupancy_does_not_change_unknown_discovery() -> None:
    _connector_grid()
    connector = get_map().register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Uninformed Connector User", position=(0, 0), faction="heroes")
    empty_row = _connector_row(actor)
    empty_discovery = empty_row.connector_traversal
    assert empty_discovery is not None
    assert empty_discovery.destination_status.value == "unknown"

    create_test_monster("monster.skeleton", name="Secret Occupant", position=(1, 0), faction="monsters")
    actor.senses.visible[(1, 0)] = False
    occupied_row = _connector_row(actor)
    occupied_discovery = occupied_row.connector_traversal
    assert occupied_discovery is not None
    assert occupied_discovery == empty_discovery

    result = execute_available_action(actor, occupied_row, occupied_row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.termination_reason is MovementTerminationReason.COLLISION
    assert result.status_message is not None
    assert "Secret Occupant" not in result.status_message
    assert actor.position == (0, 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.movement.normalized_score == 30


def test_occupied_connector_destination_stops_before_step_or_oa() -> None:
    """Initial collision admission cannot create a source-exit reaction."""
    _connector_grid()
    grid = get_map()
    grid.set_tile(-1, 0, height=0)
    connector = grid.register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="Blocked Connector User",
        position=(0, 0),
        faction="heroes",
    )
    create_test_monster("monster.skeleton", 
        name="Connector Destination Occupant",
        position=(1, 0),
        faction="monsters",
    )
    reactor = create_test_monster("monster.skeleton", 
        name="Connector Source Reactor",
        position=(-1, 0),
        faction="monsters",
    )
    add_opportunity_attack_handler(reactor)
    Entity.update_all_entities_senses(max_distance=20)
    hp_before = actor.get_hp()
    hit = force_attack_hit(reactor)
    row = _connector_row(actor)
    try:
        result = execute_available_action(actor, row, row.valid_targets[0])
    finally:
        remove_attack_modifier(reactor, hit)

    assert type(result) is TraverseConnectorEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.COLLISION
    assert actor.position == (0, 0)
    assert actor.get_hp() == hp_before
    assert reactor.action_economy.reactions.normalized_score == 1
    assert not any(
        type(event) is StepMovementEvent
        and event.source_entity_uuid == actor.uuid
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
    )
    assert not any(
        event.name == "Opportunity Attack"
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
    )


def test_connector_arrival_fires_once_and_preserves_objective_displacement() -> None:
    _connector_grid()
    connector = get_map().register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Displaced Connector User", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)
    arrivals: list[tuple[int, int]] = []

    def displace_after_connector_arrival(event: Event, _source: UUID) -> Event:
        position = getattr(event, "position", None)
        if position == (1, 0):
            arrivals.append((1, 0))
            Entity.update_entity_position(actor, (0, 1), parent_event=event.uuid)
        return event

    actor.add_event_handler(EventHandler(
        name="Connector arrival displacement",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=actor.uuid,
        )],
        event_processor=displace_after_connector_arrival,
    ))

    row = _connector_row(actor)
    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.termination_reason is MovementTerminationReason.COMPLETED
    assert result.end_position == (1, 0)
    assert result.objective_end_position == (0, 1)
    assert actor.position == (0, 1)
    assert arrivals == [(1, 0)]
    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.movement.normalized_score == 20


def test_connector_arrival_handler_cannot_mutate_stored_step_or_root() -> None:
    _connector_grid()
    connector = get_map().register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Arrival Guarded Connector", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)

    def mutate_stored_effects(event: Event, _source_uuid: UUID) -> Event:
        if event.parent_event is None:
            return event
        stored_step = EventQueue.get_event_by_uuid(event.parent_event)
        if type(stored_step) is not StepMovementEvent:
            return event
        stored_root = (
            EventQueue.get_event_by_uuid(stored_step.parent_event)
            if stored_step.parent_event is not None
            else None
        )
        stored_step.to_position = (99, 99)
        stored_step.to_elevation_feet = 999
        stored_step.movement_cost = 999
        if type(stored_root) is TraverseConnectorEvent:
            stored_root.requested_end_position = (99, 99)
            stored_root.requested_end_elevation_feet = 999
            stored_root.movement_cost_feet = 999
            stored_root.connector_digest = "f" * 64
        return event

    actor.add_event_handler(EventHandler(
        name="Mutate connector effects during arrival",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=actor.uuid,
        )],
        event_processor=mutate_stored_effects,
    ))
    row = _connector_row(actor)

    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.requested_end_position == (1, 0)
    assert result.end_position == (1, 0)
    assert result.requested_end_elevation_feet == 5
    assert result.end_elevation_feet == 5
    assert result.movement_cost_feet == 10
    assert result.connector_digest == connector.objective_digest
    assert result.combat_log is not None
    assert result.combat_log.data["end_position"] == (1, 0)
    assert result.combat_log.data["movement_cost"] == 10
    stored_steps = EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
    assert stored_steps
    assert all(getattr(event, "to_position", None) == (1, 0) for event in stored_steps)
    assert all(getattr(event, "to_elevation_feet", None) == 5 for event in stored_steps)
    assert all(getattr(event, "movement_cost", None) == 10 for event in stored_steps)


def test_connector_arrival_mutation_is_restored_before_publication_error_escapes() -> None:
    """A committed connector failure cannot retain forged Step/root history."""
    _connector_grid()
    connector = get_map().register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="Failing Arrival Connector",
        position=(0, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)

    def mutate_effects_then_raise(event: Event, _source_uuid: UUID) -> Event:
        if event.parent_event is None:
            return event
        stored_step = EventQueue.get_event_by_uuid(event.parent_event)
        if type(stored_step) is not StepMovementEvent:
            return event
        stored_root = (
            EventQueue.get_event_by_uuid(stored_step.parent_event)
            if stored_step.parent_event is not None
            else None
        )
        stored_step.uuid = uuid4()
        stored_step.to_position = (99, 99)
        stored_step.to_elevation_feet = 999
        stored_step.movement_cost = 999
        if type(stored_root) is TraverseConnectorEvent:
            stored_root.uuid = uuid4()
            stored_root.requested_end_position = (99, 99)
            stored_root.requested_end_elevation_feet = 999
            stored_root.movement_cost_feet = 999
            stored_root.connector_digest = "f" * 64
        raise RuntimeError("injected connector arrival publication failure")

    actor.add_event_handler(EventHandler(
        name="Mutate and fail connector arrival publication",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=actor.uuid,
        )],
        event_processor=mutate_effects_then_raise,
    ))
    row = _connector_row(actor)

    with pytest.raises(PositionPublicationError):
        execute_available_action(actor, row, row.valid_targets[0])

    assert actor.position == (1, 0)
    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.movement.normalized_score == 20
    roots = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is TraverseConnectorEvent
        and event.source_entity_uuid == actor.uuid
        and event.phase is EventPhase.EFFECT
    ]
    steps = [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if type(event) is StepMovementEvent
        and event.source_entity_uuid == actor.uuid
        and event.phase is EventPhase.EFFECT
    ]
    assert len(roots) == 1
    assert len(steps) == 1
    assert EventQueue.get_event_by_uuid(roots[0].uuid) is roots[0]
    assert EventQueue.get_event_by_uuid(steps[0].uuid) is steps[0]
    assert roots[0].requested_end_position == (1, 0)
    assert roots[0].requested_end_elevation_feet == 5
    assert roots[0].movement_cost_feet == 10
    assert roots[0].connector_digest == connector.objective_digest
    assert steps[0].to_position == (1, 0)
    assert steps[0].to_elevation_feet == 5
    assert steps[0].movement_cost == 10
    assert not any(
        type(event) is StepMovementEvent
        and event.source_entity_uuid == actor.uuid
        and event.phase is EventPhase.COMPLETION
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
    )


def test_connector_restores_parent_between_step_handlers_and_on_later_failure() -> None:
    """A Step handler cannot lend forged connector facts to the next handler."""
    _connector_grid()
    connector = get_map().register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="Step Guarded Connector",
        position=(0, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)
    seen_costs: list[int] = []

    def forge_parent(event: Event, _source_uuid: UUID) -> Event:
        if type(event) is StepMovementEvent and event.parent_event is not None:
            parent = EventQueue.get_event_by_uuid(event.parent_event)
            if type(parent) is TraverseConnectorEvent:
                parent.uuid = uuid4()
                parent.requested_end_position = (99, 99)
                parent.movement_cost_feet = 999
        return event

    def observe_reforge_and_raise(event: Event, _source_uuid: UUID) -> Event:
        if type(event) is StepMovementEvent and event.parent_event is not None:
            parent = EventQueue.get_event_by_uuid(event.parent_event)
            if type(parent) is TraverseConnectorEvent:
                seen_costs.append(parent.movement_cost_feet)
                if parent.movement_cost_feet == 999:
                    set_hp(actor, 0)
                parent.uuid = uuid4()
                parent.requested_end_position = (88, 88)
                parent.movement_cost_feet = 888
        raise RuntimeError("injected connector Step handler failure")

    for name, processor in (
        ("Forge connector parent in first Step handler", forge_parent),
        ("Observe connector parent in second Step handler", observe_reforge_and_raise),
    ):
        actor.add_event_handler(EventHandler(
            name=name,
            source_entity_uuid=actor.uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.STEP_MOVEMENT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=actor.uuid,
            )],
            event_processor=processor,
        ))
    row = _connector_row(actor)

    with pytest.raises(RuntimeError, match="injected connector Step handler failure"):
        execute_available_action(actor, row, row.valid_targets[0])

    assert seen_costs == [10]
    assert actor.health.life_state is LifeState.ALIVE
    assert actor.position == (0, 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.movement.normalized_score == 30
    roots = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is TraverseConnectorEvent
        and event.source_entity_uuid == actor.uuid
        and event.phase is EventPhase.EFFECT
    ]
    assert len(roots) == 1
    assert EventQueue.get_event_by_uuid(roots[0].uuid) is roots[0]
    assert roots[0].requested_end_position == (1, 0)
    assert roots[0].movement_cost_feet == 10
    assert roots[0].connector_digest == connector.objective_digest


def test_connector_and_step_noop_effect_handlers_publish_one_version_per_phase() -> None:
    """Guarded no-ops do not duplicate root or Step EFFECT evidence."""
    _connector_grid()
    connector = get_map().register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="No-op Guarded Connector",
        position=(0, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)
    immediate = []
    sequences = []
    batches = []

    def capture_event(event: Event) -> None:
        immediate.append(event)

    def capture_sequence(events) -> None:
        sequences.append(tuple(events))

    def capture_batch(events) -> None:
        batches.append(tuple(events))

    for name, event_type in (
        ("No-op connector root EFFECT", EventType.MOVEMENT),
        ("No-op connector Step EFFECT", EventType.STEP_MOVEMENT),
    ):
        actor.add_event_handler(EventHandler(
            name=name,
            source_entity_uuid=actor.uuid,
            trigger_conditions=[Trigger(
                event_type=event_type,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=actor.uuid,
            )],
            event_processor=lambda event, _source: event,
        ))

    EventQueue.add_on_event_callback(capture_event)
    EventQueue.add_on_event_sequence_callback(capture_sequence)
    EventQueue.add_on_event_batch_callback(capture_batch)
    row = _connector_row(actor)
    try:
        result = execute_available_action(actor, row, row.valid_targets[0])
    finally:
        EventQueue.remove_on_event_callback(capture_event)
        EventQueue.remove_on_event_sequence_callback(capture_sequence)
        EventQueue.remove_on_event_batch_callback(capture_batch)

    assert type(result) is TraverseConnectorEvent
    expected_phases = [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    root_versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is TraverseConnectorEvent
        and event.lineage_uuid == result.lineage_uuid
    ]
    step_versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if type(event) is StepMovementEvent
        and event.source_entity_uuid == actor.uuid
    ]
    assert [event.phase for event in root_versions] == expected_phases
    assert len({event.lineage_uuid for event in step_versions}) == 1
    step_lineage = step_versions[0].lineage_uuid
    assert [event.phase for event in step_versions] == expected_phases

    for observed in (
        immediate,
        [event for sequence in sequences for event in sequence],
        [event for batch in batches for event in batch],
    ):
        assert [
            event.phase
            for event in observed
            if type(event) is TraverseConnectorEvent
            and event.lineage_uuid == result.lineage_uuid
        ] == expected_phases
        assert [
            event.phase
            for event in observed
            if type(event) is StepMovementEvent
            and event.lineage_uuid == step_lineage
        ] == expected_phases


def test_connector_and_step_child_emission_preserve_noop_parent_lifecycles() -> None:
    """Real child linkage remains authoritative without duplicating or vetoing parents."""
    _connector_grid()
    grid = get_map()
    connector = grid.register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="Child Emitting Connector",
        position=(0, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)
    emitted_by_parent: dict[UUID, UUID] = {}

    def emit_child(event: Event, _source_uuid: UUID) -> Event:
        child = EventQueue.register(Event(
            source_entity_uuid=event.source_entity_uuid,
            event_type=EventType.BASE_ACTION,
            phase=EventPhase.COMPLETION,
            parent_event=event.uuid,
            use_register=True,
        ))
        emitted_by_parent[event.uuid] = child.uuid
        return event

    for name, event_type in (
        ("Connector root emits a child", EventType.MOVEMENT),
        ("Connector Step emits a child", EventType.STEP_MOVEMENT),
    ):
        actor.add_event_handler(EventHandler(
            name=name,
            source_entity_uuid=actor.uuid,
            trigger_conditions=[Trigger(
                event_type=event_type,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=actor.uuid,
            )],
            event_processor=emit_child,
        ))

    row = _connector_row(actor)
    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.COMPLETED
    assert actor.position == (1, 0)
    assert grid.connector_revision == 1
    root_versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is TraverseConnectorEvent
        and event.lineage_uuid == result.lineage_uuid
    ]
    step_versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if type(event) is StepMovementEvent
        and event.source_entity_uuid == actor.uuid
    ]
    expected_phases = [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert [event.phase for event in root_versions] == expected_phases
    assert [event.phase for event in step_versions] == expected_phases
    root_effect = root_versions[2]
    step_effect = step_versions[2]
    assert emitted_by_parent[root_effect.uuid] in root_effect.children_events
    assert emitted_by_parent[step_effect.uuid] in step_effect.children_events


def test_connector_change_forged_child_evidence_vetoes_registration() -> None:
    _connector_grid()
    grid = get_map()
    forged_child = uuid4()
    handler = EventHandler(
        name="Forge connector change child evidence",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.TRAVERSAL_CONNECTOR_CHANGED,
            event_phase=EventPhase.DECLARATION,
        )],
        event_processor=lambda event, _source: event.model_copy(update={
            "children_events": [forged_child],
        }),
    )
    EventQueue.add_event_handler(handler)
    try:
        connector = grid.register_connector(connector_definition())
    finally:
        EventQueue.remove_event_handler(handler)

    assert connector is None
    assert grid.connector_revision == 0
    assert grid.get_all_connectors() == ()
    versions = EventQueue.get_events_by_type(
        EventType.TRAVERSAL_CONNECTOR_CHANGED
    )
    assert [event.phase for event in versions] == [
        EventPhase.DECLARATION,
        EventPhase.CANCEL,
    ]
    assert all(forged_child not in event.children_events for event in versions)


def test_connector_step_forged_child_evidence_stops_before_commit() -> None:
    _connector_grid()
    grid = get_map()
    connector = grid.register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="Forged Step Child Connector",
        position=(0, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)
    forged_child = uuid4()
    actor.add_event_handler(EventHandler(
        name="Forge connector Step child evidence",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=actor.uuid,
        )],
        event_processor=lambda event, _source: event.model_copy(update={
            "children_events": [forged_child],
        }),
    ))
    row = _connector_row(actor)

    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.STEP_CANCELED
    assert actor.position == (0, 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.movement.normalized_score == 30
    steps = [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if type(event) is StepMovementEvent
    ]
    assert [event.phase for event in steps] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert steps[-1].committed is False
    assert all(forged_child not in event.children_events for event in steps)


def test_connector_root_forged_child_evidence_cancels_before_step() -> None:
    _connector_grid()
    grid = get_map()
    connector = grid.register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="Forged Root Child Connector",
        position=(0, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)
    forged_child = uuid4()
    actor.add_event_handler(EventHandler(
        name="Forge connector root child evidence",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=actor.uuid,
        )],
        event_processor=lambda event, _source: event.model_copy(update={
            "children_events": [forged_child],
        }),
    ))
    row = _connector_row(actor)

    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.phase is EventPhase.CANCEL
    assert actor.position == (0, 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.movement.normalized_score == 30
    assert not [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if type(event) is StepMovementEvent
        and event.source_entity_uuid == actor.uuid
    ]
    root_versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is TraverseConnectorEvent
    ]
    assert [event.phase for event in root_versions] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.CANCEL,
    ]
    assert all(forged_child not in event.children_events for event in root_versions)


def test_connector_execution_rejects_replaced_global_support_owner() -> None:
    _connector_grid()
    grid = get_map()
    connector = grid.register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="Registry Stale Connector",
        position=(0, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)
    row = _connector_row(actor)
    support = grid.get_tile(1, 0)
    assert support is not None
    impostor = Tile.model_validate(support.model_dump())
    assert impostor is not support
    assert BaseBlock.get(support.uuid) is impostor
    assert grid.get_tile(1, 0) is support
    assert not grid.connector_supports_are_current(connector)

    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.phase is EventPhase.CANCEL
    assert actor.position == (0, 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.movement.normalized_score == 30
    assert not [
        event
        for event in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
        if type(event) is StepMovementEvent
        and event.source_entity_uuid == actor.uuid
    ]


def test_connector_step_handler_cannot_mutate_parent_root_before_stop() -> None:
    """A pre-cost Step stop completes only the accepted connector evidence."""
    _connector_grid()
    connector = get_map().register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", 
        name="Step Parent Guarded Connector",
        position=(0, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)

    def mutate_parent_and_kill(event: Event, _source_uuid: UUID) -> Event:
        if type(event) is not StepMovementEvent or event.parent_event is None:
            return event
        stored_root = EventQueue.get_event_by_uuid(event.parent_event)
        if type(stored_root) is TraverseConnectorEvent:
            stored_root.requested_end_position = (99, 99)
            stored_root.requested_end_elevation_feet = 999
            stored_root.movement_cost_feet = 999
            stored_root.connector_digest = "f" * 64
        set_hp(actor, 0)
        return event

    actor.add_event_handler(EventHandler(
        name="Mutate connector root during Step EFFECT",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=actor.uuid,
        )],
        event_processor=mutate_parent_and_kill,
    ))
    row = _connector_row(actor)

    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.termination_reason is MovementTerminationReason.DEAD
    assert result.requested_end_position == (1, 0)
    assert result.end_position == (0, 0)
    assert result.requested_end_elevation_feet == 5
    assert result.end_elevation_feet == 0
    assert result.movement_cost_feet == 10
    assert result.connector_digest == connector.objective_digest
    assert actor.position == (0, 0)
    assert all(
        modifier.name != "Connector Action Cost_cost"
        for modifier in actor.action_economy.actions.self_static.value_modifiers.values()
    )
    assert all(
        modifier.name != "Connector Movement Cost_cost"
        for modifier in actor.action_economy.movement.self_static.value_modifiers.values()
    )
    roots = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is TraverseConnectorEvent
    ]
    assert roots
    assert all(event.requested_end_position == (1, 0) for event in roots)
    assert all(event.requested_end_elevation_feet == 5 for event in roots)
    assert all(event.movement_cost_feet == 10 for event in roots)
    assert all(event.connector_digest == connector.objective_digest for event in roots)


def test_connector_position_staging_failure_undoes_exact_debit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _connector_grid()
    grid = get_map()
    connector = grid.register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Staging Connector User", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)
    row = _connector_row(actor)
    original = grid.recompute_tile_directional_blocking

    def fail_destination(position: tuple[int, int]):
        if position == (1, 0):
            raise RuntimeError("injected connector staging failure")
        return original(position)

    monkeypatch.setattr(grid, "recompute_tile_directional_blocking", fail_destination)
    with pytest.raises(PositionCommitError):
        execute_available_action(actor, row, row.valid_targets[0])

    assert actor.position == (0, 0)
    assert actor.senses.position == (0, 0)
    assert grid.get_entity_position(actor.uuid) == (0, 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.movement.normalized_score == 30
    assert not any(
        type(event) is TraverseConnectorEvent
        and event.phase is EventPhase.COMPLETION
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
    )


def test_connector_spatial_publication_failure_keeps_position_and_cost() -> None:
    _connector_grid()
    connector = get_map().register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Publishing Connector User", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)
    handler = EventHandler(
        name="Fail connector spatial publication",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_LEFT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=actor.uuid,
        )],
        event_processor=lambda _event, _source: (_ for _ in ()).throw(
            RuntimeError("injected connector publication failure")
        ),
    )
    EventQueue.add_event_handler(handler)
    row = _connector_row(actor)
    try:
        with pytest.raises(PositionPublicationError):
            execute_available_action(actor, row, row.valid_targets[0])
    finally:
        EventQueue.remove_event_handler(handler)

    assert actor.position == (1, 0)
    assert actor.senses.position == (1, 0)
    assert get_map().get_entity_position(actor.uuid) == (1, 0)
    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.movement.normalized_score == 20
    assert not any(
        type(event) is TraverseConnectorEvent
        and event.phase is EventPhase.COMPLETION
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
    )


def test_connector_root_and_step_forgery_store_no_forged_geometry() -> None:
    _connector_grid()
    connector = get_map().register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Guarded Connector User", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)

    def forge_step(event: Event, _source: UUID) -> Event:
        if type(event) is StepMovementEvent:
            return event.model_copy(update={
                "to_position": (99, 99),
                "to_elevation_feet": 999,
                "movement_cost": 999,
            })
        return event

    actor.add_event_handler(EventHandler(
        name="Forge connector transfer Step",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=actor.uuid,
        )],
        event_processor=forge_step,
    ))

    row = _connector_row(actor)
    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.termination_reason is MovementTerminationReason.STEP_CANCELED
    assert actor.position == (0, 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.movement.normalized_score == 30
    stored_steps = EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
    assert stored_steps
    assert all(getattr(event, "to_position", None) == (1, 0) for event in stored_steps)
    assert all(getattr(event, "movement_cost", None) == 10 for event in stored_steps)


def test_connector_root_effect_forgery_cancels_before_step_or_cost() -> None:
    _connector_grid()
    connector = get_map().register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Guarded Connector Root", position=(0, 0), faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)

    def forge_root(event: Event, _source: UUID) -> Event:
        if type(event) is TraverseConnectorEvent:
            return event.model_copy(update={
                "requested_end_position": (99, 99),
                "requested_end_elevation_feet": 999,
                "movement_cost_feet": 999,
                "connector_digest": "f" * 64,
            })
        return event

    actor.add_event_handler(EventHandler(
        name="Forge connector root EFFECT",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=actor.uuid,
        )],
        event_processor=forge_root,
    ))
    row = _connector_row(actor)

    result = execute_available_action(actor, row, row.valid_targets[0])

    assert type(result) is TraverseConnectorEvent
    assert result.phase is EventPhase.CANCEL
    assert result.canceled_from_phase is EventPhase.EFFECT
    assert actor.position == (0, 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.movement.normalized_score == 30
    assert EventQueue.get_events_by_type(EventType.STEP_MOVEMENT) == []
    roots = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if type(event) is TraverseConnectorEvent
    ]
    assert roots
    assert all(event.requested_end_position == (1, 0) for event in roots)
    assert all(event.requested_end_elevation_feet == 5 for event in roots)
    assert all(event.movement_cost_feet == 10 for event in roots)
    assert all(event.connector_digest == connector.objective_digest for event in roots)


def test_connector_discovery_uses_only_endpoint_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _connector_grid()
    grid = get_map()
    connector = grid.register_connector(connector_definition())
    assert connector is not None
    actor = create_test_monster("monster.skeleton", name="Indexed Connector User", position=(0, 0), faction="heroes")
    template = TraverseConnector(source_entity_uuid=actor.uuid)

    monkeypatch.setattr(
        grid,
        "get_all_connectors",
        lambda: (_ for _ in ()).throw(AssertionError("global connector scan")),
    )
    assert len(template.get_discovery_variants(actor)) == 1
    Entity.update_entity_position(actor, (0, 1))
    assert template.get_discovery_variants(actor) == []
