"""A seat's world holds the engine's current after-values.

Light settled between the actor-free world snapshot and the seat's
initialization, and connector edits made after it, reach a seat that
perceives the cells: the client fold of the projected recording equals the
live map.
"""

from dataclasses import dataclass
import random
from typing import Callable
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter

from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.core.traversal_connectors import TraversalConnectorDefinition
from dnd.player.application import capture_application_operation, initialize_audiences, seat_content
from dnd.player.audience import PlayerAudience
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import PlayerInitialization, PlayerLineage, PlayerState, PlayerUpdate
from dnd.player.projection import ProjectionState, SessionProjection, begin_projection, project_lineage
from dnd.player.reduction import reduce_initialization, reduce_lineage, reduce_operation
from dnd.player.session import Operation, Session, close_session, create_session
from dnd.spatial.gas_traps import materialize_gas_vent
from dnd.spatial.portals import materialize_portal
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.types.controls import ActivationLink
from dnd.types.traps import TrapState
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.cells import cell_in
from dnd.types.event_facts import WorldConnectorState
from dnd.types.world import LightLevel
from dnd.world_authoring import (project_world_connector, register_world_connector, remove_world_connector,
    replace_world_connector, set_world_connector_enabled)


INITIALIZATION = TypeAdapter(PlayerInitialization)
LINEAGE = TypeAdapter(PlayerLineage)


@dataclass
class Seat:
    """One seat's projection and the client fold of everything it was sent."""

    audience: PlayerAudience
    session: SessionProjection
    projection: ProjectionState
    client: PlayerState


def initialize(session: Session) -> Seat:
    """Record the session's startup for the party seat, project it and fold it as the client does."""
    audience = session.seats['party']
    startup = capture_interval(name='startup', start_cursor=0, end_cursor=EventQueue.event_cursor(),
        observer_uuid=audience.observers[0], audience=audience,
        battlefield_id=session.battlefield.definition.battlefield_id)
    projected = SessionProjection()
    projection, initial = begin_projection(projected, startup)
    return Seat(audience, projected, projection, reduce_initialization(INITIALIZATION.validate_json(
        INITIALIZATION.dump_json(initial))))


def advance(seat: Seat, act: Callable[[], object]) -> None:
    """Run one engine operation; record, project and fold its roots."""
    begin = EventQueue.event_cursor()
    act()
    roots = tuple(event for _, event in EventQueue.iter_events_since(begin)
        if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
    for native in capture_lineages(roots, observer_uuid=seat.audience.observers[0], audience=seat.audience):
        packet = project_lineage(seat.session, seat.projection, native)
        if packet is not None:
            seat.client = reduce_lineage(seat.client, LINEAGE.validate_json(LINEAGE.dump_json(packet)))


@pytest.fixture
def sessions():
    state = random.getstate()
    random.seed(0)
    opened: list[Session] = []

    def open_session(**options) -> Session:
        opened.append(create_session(**options))
        return opened[-1]
    try:
        yield open_session
    finally:
        for session in opened:
            close_session(session)
        reset_engine_runtime()
        random.setstate(state)


def test_initial_tiles_carry_the_light_settled_after_the_world_snapshot(sessions):
    # The Lantern Crypt lights its wall torches after its actor-free world snapshot.
    session = sessions(battlefield_id='battlefield.lantern_crypt', player_positions=((3, 5), (4, 5)),
        enemy_positions=((14, 6), (15, 6)))
    client = initialize(session).client
    tiles = get_map().get_all_tiles()
    engine = {position: tiles[position].to_world_tile_state().resolved_light for position in client.tiles}
    assert set(engine.values()) - {LightLevel.DARKNESS}, 'the torches light cells the party sees'
    assert {position: tile.resolved_light for position, tile in client.tiles.items()} == engine


@dataclass(frozen=True)
class ConnectorCase:
    name: str
    edit: Callable[[UUID, UUID], object]


def _replaced(ladder: UUID, author: UUID) -> object:
    connector = get_map().get_connector(ladder)
    assert connector is not None
    return replace_world_connector(ladder, connector.definition().model_copy(update={'movement_cost_feet': 20}),
        author_uuid=author)


def _registered(ladder: UUID, author: UUID) -> object:
    connector = get_map().get_connector(ladder)
    assert connector is not None
    return register_world_connector(TraversalConnectorDefinition.model_validate({
        **connector.definition().model_dump(), 'authored_id': 'connector.test.second_ladder',
        'endpoint_positions': ((2, 11), (2, 12))}), author_uuid=author)


CONNECTOR_CASES = (
    ConnectorCase('disabled', lambda ladder, author: set_world_connector_enabled(ladder, False, author_uuid=author)),
    ConnectorCase('replaced', _replaced),
    ConnectorCase('removed', lambda ladder, author: remove_world_connector(ladder, author_uuid=author)),
    ConnectorCase('registered', _registered),
)


def visible_connectors(client: PlayerState) -> dict[UUID, WorldConnectorState]:
    """The live map's connectors with both endpoints in the seat's view."""
    assert client.senses is not None
    return {connector.uuid: project_world_connector(connector) for connector in get_map().get_all_connectors()
            if all(cell_in(client.senses.visible, endpoint.position) for endpoint in connector.endpoints)}


@pytest.mark.parametrize('case', CONNECTOR_CASES, ids=lambda case: case.name)
def test_connector_edits_after_initialization_reach_a_seat_that_sees_them(sessions, case):
    session = sessions(battlefield_id='battlefield.elevation_proving_ground', player_positions=((2, 9), (3, 9)),
        enemy_positions=((12, 4), (13, 4)))
    seat = initialize(session)
    ladder = session.battlefield.object_uuids['connector.proving.ladder']
    held = dict(seat.client.connectors)
    assert ladder in held and held == visible_connectors(seat.client), case.name
    advance(seat, lambda: case.edit(ladder, uuid4()))
    assert seat.client.connectors == visible_connectors(seat.client), case.name


def test_live_connector_edits_and_mechanism_installs_publish_to_every_seat(sessions):
    """A connector edit and a mechanism installed mid-game are supported roots: the operation projector publishes
    them (no unprojected committed state), and each seat's client keeps the connectors its view holds."""
    session = sessions(battlefield_id='battlefield.elevation_proving_ground', player_positions=((2, 9), (3, 9)),
        enemy_positions=((12, 4), (13, 4)))
    catalog = ui_content_manifest()
    runtimes, initializations = initialize_audiences(session, catalog)
    clients = {seat: reduce_initialization(INITIALIZATION.validate_json(INITIALIZATION.dump_json(initial)),
        content_additions=seat_content(runtimes[seat])) for seat, initial in initializations.items()}
    ladder = session.battlefield.object_uuids['connector.proving.ladder']
    author = uuid4()
    vent = []
    edits = (
        lambda: set_world_connector_enabled(ladder, False, author_uuid=author),
        lambda: materialize_portal({(2, 11)}, (2, 12), trap_state=TrapState.READY),
        lambda: vent.append(materialize_gas_vent((3, 11))),
        lambda: materialize_pressure_plate({(4, 11)}, ActivationLink(target_condition_uuid=vent[0].uuid)),
        lambda: remove_world_connector(ladder, author_uuid=author),
    )
    for edit in edits:
        start = EventQueue.event_cursor()
        edit()
        operation = Operation(start_cursor=start, end_cursor=EventQueue.event_cursor(),
            roots=tuple(event for _, event in EventQueue.iter_events_since(start)
                if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)))
        for seat, update in capture_application_operation(runtimes, operation, catalog).items():
            clients[seat] = reduce_operation(clients[seat], PlayerUpdate.model_validate_json(update.model_dump_json()))
    for client in clients.values():
        assert ladder not in client.connectors
        assert client.connectors == visible_connectors(client)
