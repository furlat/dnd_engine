"""The E0 seat tooling (EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §5): Gallery Crowd seat layouts and O1.

O1 compares a seat's client fold with a reference read from the live engine. These cases plant a known fault
in an otherwise folded client and require O1 to name it: a body or an object drawn where nothing stands
(a ghost), a body value that drifted, a body or a tile the client lost, an ended effect or a removed connector
still shown. Other differences the head has are not asserted here; the gallery oracle runs list them.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
import random
from uuid import uuid4

import pytest

from devtools.performance import gallery_crowd, seat_oracle
from dnd.core.events import WorldConnectorState
from dnd.core.traversal_connectors import ConnectorProvocationPolicy, TraversalConnectorKind
from dnd.player.application import initialize_audiences
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import PlayerState
from dnd.player.reduction import reduce_initialization
from dnd.player.session import Session, close_session, create_session
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.senses import PerceivedSpatialEffect


@pytest.mark.parametrize('layout,expected', [
    ('faction', {'amber': 4, 'blue': 26}),
    ('character', {**{f'amber.{member}': 1 for member in ('unit_1', 'ally_1', 'ally_2', 'ally_3')},
                   **{f'blue.crowd_{index}': 1 for index in range(1, 27)}}),
    ('batch:5', {'amber': 4, 'blue.1': 5, 'blue.2': 5, 'blue.3': 5, 'blue.4': 5, 'blue.5': 5, 'blue.6': 1}),
])
def test_gallery_seat_layouts_give_every_member_one_seat(layout, expected):
    request, slots = gallery_crowd.start_request(False, {}, layout)
    assert request.assignments is not None
    seats = {row.seat_id: len(row.controlled) for row in request.assignments}
    assert seats == expected
    assert set(request.audience_ids) == set(slots) == set(expected)
    assert {slots[row.seat_id] for row in request.assignments if row.seat_id.startswith('blue')} <= {'blue'}


@pytest.fixture
def session():
    state = random.getstate()
    random.seed(0)
    # A bright room split by a wall with an open door: placed objects (wall faces, the door) are in view.
    value = create_session(battlefield_id='battlefield.visibility_doorway_open')
    try:
        yield value
    finally:
        close_session(value)
        reset_engine_runtime()
        random.setstate(state)


def senses(client: PlayerState):
    assert client.senses is not None
    return client.senses


def enemy(session: Session, client: PlayerState):
    """A body the seat sees that it does not control."""
    return next(actor for identity, actor in client.actors.items()
        if identity in senses(client).entities and not client.viewing_audience.controls(identity))


def ghost(session: Session, client: PlayerState) -> tuple[str, str, str | None]:
    body = enemy(session, client)
    identity = uuid4()
    client.actors[identity] = replace(body, uuid=identity)
    return 'actors', str(identity), None


def drifted_hit_points(session: Session, client: PlayerState) -> tuple[str, str, str | None]:
    body = enemy(session, client)
    client.actors[body.uuid] = replace(body, normal_hp=body.normal_hp - 1)
    return 'actors', str(body.uuid), 'body.normal_hp'


def lost_body(session: Session, client: PlayerState) -> tuple[str, str, str | None]:
    body = enemy(session, client)
    del client.actors[body.uuid]
    return 'actors', str(body.uuid), ''


def lost_tile(session: Session, client: PlayerState) -> tuple[str, str, str | None]:
    position = next(iter(seat_oracle.mask_positions(senses(client).visible)))
    del client.tiles[position]
    return 'tiles', seat_oracle.key(position), ''


def ghost_object(session: Session, client: PlayerState) -> tuple[str, str, str | None]:
    """A copy of a held object in view, under an identity nothing in the world has."""
    held = next(obj for identity, obj in client.objects.items() if seat_oracle.support_cells(obj.placement)
                & set(seat_oracle.mask_positions(senses(client).visible)))
    identity = uuid4()
    client.objects[identity] = replace(held, item=replace(held.item, item_uuid=identity),
                                       placement=held.placement.model_copy(update={'object_uuid': identity}))
    return 'objects', str(identity), None


def stale_effect(session: Session, client: PlayerState) -> tuple[str, str, str | None]:
    """An effect the client still shows on a visible cell after it ended."""
    position = next(iter(seat_oracle.mask_positions(senses(client).visible)))
    identity = uuid4()
    effect = PerceivedSpatialEffect(content_ref=client.content[0].ref, name='Ended zone', description='',
                                    positions=(position,))
    client.senses = replace(senses(client), spatial_effects={**senses(client).spatial_effects, identity: effect})
    return 'effects', str(identity), None


def stale_connector(session: Session, client: PlayerState) -> tuple[str, str, str | None]:
    """A connector the client holds between two visible cells, which the world does not have."""
    first, second = sorted(seat_oracle.mask_positions(senses(client).visible))[:2]
    identity = uuid4()
    client.connectors = (*client.connectors, WorldConnectorState(connector_uuid=identity, authored_id='ladder.gone',
        kind=TraversalConnectorKind.LADDER, presentation_key='ladder', endpoints=(first, second),
        support_tile_uuids=(client.tiles[first].tile_uuid, client.tiles[second].tile_uuid),
        endpoint_elevations_feet=(0, 0), movement_cost_feet=5, bidirectional=True, enabled=True,
        provocation_policy=ConnectorProvocationPolicy.DOES_NOT_PROVOKE))
    return 'connectors', str(identity), None


@dataclass(frozen=True)
class Fault:
    name: str
    plant: Callable[[Session, PlayerState], tuple[str, str, str | None]]


FAULTS = (Fault('ghost body', ghost), Fault('drifted hit points', drifted_hit_points),
          Fault('lost body', lost_body), Fault('lost tile', lost_tile), Fault('ghost object', ghost_object),
          Fault('stale effect', stale_effect), Fault('stale connector', stale_connector))


@pytest.mark.parametrize('fault', FAULTS, ids=lambda fault: fault.name)
def test_o1_names_a_fault_planted_in_the_client_fold(session, fault):
    runtimes, initializations = initialize_audiences(session, ui_content_manifest())
    seat, initial = next(iter(initializations.items()))
    audience = session.seats[seat]

    def o1(client: PlayerState) -> set[tuple[str, str, str | None]]:
        rows = seat_oracle.differences(seat_oracle.live_view(seat_oracle.live_world(session), audience, client),
                                       seat_oracle.client_view(client))
        return {(row['category'], row['key'], row.get('field')) for row in rows}

    client = reduce_initialization(initial, content_additions=runtimes[seat].projection.remembered.content)
    before = o1(client)
    planted = fault.plant(session, client)
    assert planted not in before, fault.name
    assert planted in o1(client), fault.name
