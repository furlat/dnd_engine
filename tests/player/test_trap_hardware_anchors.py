"""Observed traps identify their own perceived hardware in detached player updates.

Real ground-hardware installation, discovery and destruction cross capture,
JSON transport and the client fold. Spatial-only traps and unseen housings must
not acquire an anchor from another nearby trap with the same content.
"""

import random
from uuid import uuid4

import pytest

from dnd.conditions import Blinded
from dnd.content.items.environment_item_builders import build_authored_door
from dnd.content.items.ground_hardware_builders import materialize_ground_hardware
from dnd.core.concealment_types import concealment
from dnd.core.creature_types import DamageType
from dnd.core.events import EventPhase, EventQueue, MechanismInstallEvent
from dnd.player.application import initialize_audiences, seat_content
from dnd.player.audience import PlayerAudience
from dnd.player.content_composition import ui_content_manifest
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import close_session, create_session
from dnd.spatial.environmental_conditions import (
    POISON_DAMAGE_SPIKE_CONTENT_REF, POISON_DAMAGE_SPIKE_PAYLOAD,
    SICKENING_SPIKE_CONTENT_REF, SICKENING_SPIKE_PAYLOAD, SpikeTrap,
)
from dnd.types.traps import TrapState
from dnd.types.world import CardinalDirection
from tests.engine.test_ground_hardware import owner
from tests.player.test_emitted_update_replica import INITIALIZATION
from tests.player.test_holy_nimbus_attribution import capture


@pytest.fixture
def trap_session():
    previous_random = random.getstate()
    random.seed(6)
    session = create_session()
    actors = tuple(session.game.entities[identity] for identity in session.player_uuids)
    session.seats.clear()
    session.seats.update({name: PlayerAudience((actor.uuid,), (actor.uuid,))
        for name, actor in zip(("first", "second"), actors, strict=True)})
    try:
        yield session, actors
    finally:
        close_session(session)
        random.setstate(previous_random)


def mechanism(kind, position, *, stealth_dc=None):
    if kind in ("spikes_poisoned", "spikes_poison_damage"):
        content, payload = ((SICKENING_SPIKE_CONTENT_REF, SICKENING_SPIKE_PAYLOAD)
            if kind == "spikes_poisoned" else (POISON_DAMAGE_SPIKE_CONTENT_REF, POISON_DAMAGE_SPIKE_PAYLOAD))
        return SpikeTrap(source_entity_uuid=uuid4(), position=position, affected_positions={position},
            content_ref=content, payload=payload, concealment=concealment(stealth_dc))
    result = owner(kind, position, uuid4())
    result.concealment = concealment(stealth_dc)
    return result


def clients_for(session):
    catalog = ui_content_manifest()
    audiences, initializations = initialize_audiences(session, catalog)
    clients = {seat: reduce_initialization(INITIALIZATION.validate_json(INITIALIZATION.dump_json(initial)),
        content_additions=seat_content(audiences[seat])) for seat, initial in initializations.items()}
    return catalog, audiences, clients


def install(trap, item_id=None):
    cause = EventQueue.publish_declaration(MechanismInstallEvent(name="Install trap",
        source_entity_uuid=trap.source_entity_uuid, use_register=False))
    cause = cause.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    body = None
    if item_id is not None:
        body = materialize_ground_hardware(trap, item_id=item_id, parent_event=cause)
    else:
        admitted = trap.activate(parent_event=cause)
        assert admitted is not None and not admitted.canceled
    cause.phase_to(EventPhase.COMPLETION)
    return body


def fold_since(session, audiences, catalog, clients, cursor):
    updates = capture(session, audiences, catalog, cursor)
    for seat, update in updates.items():
        clients[seat] = reduce_operation(clients[seat], update)
    return updates


@pytest.mark.parametrize("kind", ("gas_vent", "jaw", "pressure_plate", "tripwire", "spikes",
    "spikes_poisoned", "spikes_poison_damage"))
def test_trap_anchors_survive_transport_without_borrowing_hidden_or_spatial_only_owners(trap_session, kind):
    session, actors = trap_session
    blinded = actors[1].add_condition(Blinded(source_entity_uuid=actors[1].uuid,
        target_entity_uuid=actors[1].uuid))
    assert blinded is not None and not blinded.canceled
    catalog, audiences, clients = clients_for(session)
    item_id = "environment.trap." + ("spikes" if kind.startswith("spikes") else kind)
    first, second, spatial, hidden = (mechanism(kind, position, stealth_dc=stealth)
        for position, stealth in (((11, 10), None), ((11, 12), None), ((12, 13), None), ((12, 14), 1000)))

    cursor = EventQueue.event_cursor()
    first_body = install(first, item_id)
    second_body = install(second, item_id)
    install(spatial)
    hidden_body = install(hidden, item_id)
    updates = fold_since(session, audiences, catalog, clients, cursor)
    assert set(updates) == {"first", "second"}
    assert first.uuid != second.uuid and first_body.uuid != second_body.uuid

    def check_observed(client):
        assert client.senses is not None
        for trap, body in ((first, first_body), (second, second_body)):
            observed = client.senses.spatial_effects[trap.uuid]
            assert body.uuid in client.senses.objects
            assert observed.anchor_item_uuid == body.uuid
            assert observed.content_ref == trap.content_ref
            assert not observed.apparent_presence
            if kind == "pressure_plate":
                assert observed.pressed is False
            elif kind == "tripwire":
                assert observed.direction == (1, 0)
            else:
                assert observed.trap_state is TrapState.READY
        assert client.senses.spatial_effects[spatial.uuid].anchor_item_uuid is None
        assert hidden.uuid not in client.senses.spatial_effects
        assert hidden_body.uuid not in client.senses.objects

    check_observed(clients["first"])
    blind_senses = clients["second"].senses
    assert blind_senses is not None
    assert not {first.uuid, second.uuid, spatial.uuid, hidden.uuid} & blind_senses.spatial_effects.keys()
    blind_wire = updates["second"].model_dump_json()
    assert all(str(body.uuid) not in blind_wire for body in (first_body, second_body, hidden_body))

    cursor = EventQueue.event_cursor()
    assert actors[1].remove_condition("Blinded")
    fold_since(session, audiences, catalog, clients, cursor)
    for client in clients.values():
        check_observed(client)

    cursor = EventQueue.event_cursor()
    assert first_body.receive_damage(100, DamageType.BLUDGEONING, actors[0].uuid) > 0
    fold_since(session, audiences, catalog, clients, cursor)
    for client in clients.values():
        assert first.uuid not in client.senses.spatial_effects
        assert first_body.uuid in client.senses.objects
        assert client.senses.spatial_effects[second.uuid].anchor_item_uuid == second_body.uuid
        assert client.senses.spatial_effects[spatial.uuid].anchor_item_uuid is None


def test_visible_spike_cells_do_not_reveal_housing_behind_closed_doors(trap_session):
    session, _ = trap_session
    doors = {}
    for direction in CardinalDirection:
        door = build_authored_door("environment.door.fantasy_a1")
        door.place_on_grid((13, 11), boundary_direction=direction)
        doors[direction] = door
    catalog, audiences, clients = clients_for(session)
    spikes = SpikeTrap(source_entity_uuid=uuid4(), position=(13, 11),
        affected_positions={(13, 11), (11, 11)})
    cursor = EventQueue.event_cursor()
    body = install(spikes, "environment.trap.spikes")
    fold_since(session, audiences, catalog, clients, cursor)
    for client in clients.values():
        assert body.uuid not in client.senses.objects
        observed = client.senses.spatial_effects[spikes.uuid]
        assert observed.positions == ((11, 11),)
        assert observed.anchor_item_uuid is None

    cursor = EventQueue.event_cursor()
    doors[CardinalDirection.WEST].open()
    fold_since(session, audiences, catalog, clients, cursor)
    for client in clients.values():
        assert body.uuid in client.senses.objects
        assert client.senses.spatial_effects[spikes.uuid].anchor_item_uuid == body.uuid

    cursor = EventQueue.event_cursor()
    doors[CardinalDirection.WEST].close()
    fold_since(session, audiences, catalog, clients, cursor)
    for client in clients.values():
        assert body.uuid not in client.senses.objects
        observed = client.senses.spatial_effects[spikes.uuid]
        assert observed.positions == ((11, 11),)
        assert observed.anchor_item_uuid is None
