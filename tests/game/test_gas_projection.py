"""A native release keeps its own observation before its gas obscures it."""

from uuid import uuid4

import pytest

from dnd.conditions import Blinded
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.gas_traps import GasCloudSpec, materialize_gas_vent
from dnd.types.senses import OpticalObscurement
from game.player_facts import MechanismActivationFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence
from game.presentation import capture_interval, reduce_interval
from game.replay import ObserverCapture, RecordedSequence, capture_history


def record_release(*, hidden_origin: bool = False, blinded_child: bool = False):
    reset_engine_runtime()
    built = build_battlefield("battlefield.visibility_open_range")
    game = Game()
    try:
        if hidden_origin:
            # An optical screen hides the apparatus without blocking the gas.
            # These are independent existing map channels, not a hidden-link grant.
            for y in range(built.definition.height):
                get_map().set_tile(3, y, name="Opaque screen", walking_cost=1,
                                  blocks_optics=True, blocks_propagation=False)
        observer = Entity.create(uuid4(), "Observer", config=EntityConfig(position=(2, 2)))
        observer.compose_entity()
        game.deploy_entity(observer, observer.position)
        vent = materialize_gas_vent((4, 2), gas=GasCloudSpec(
            radius_feet=5, optical_obscurement=OpticalObscurement.HEAVY))
        Entity.update_all_entities_senses()
        assert (vent.uuid in observer.senses.spatial_effects) is not hidden_origin
        cursor = EventQueue.event_cursor()
        initial = capture_interval(name="Gas release", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        command = EventQueue.publish_declaration(Event(name="Release gas",
            source_entity_uuid=vent.uuid, event_type=EventType.BASE_ACTION, use_register=False))
        command = command.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
        if blinded_child:
            observer.add_condition(Blinded(source_entity_uuid=observer.uuid,
                target_entity_uuid=observer.uuid), parent_event=command)
        result = vent.fire(parent_event=command)
        assert result.committed
        command.phase_to(EventPhase.COMPLETION)
        history = capture_history(before, (), observers=(ObserverCapture("observer", observer.uuid, cursor),))
        return history.views["observer"].model_dump_json(), vent.uuid
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("hidden_origin", (False, True))
def test_saved_obscuring_release_preserves_only_its_actual_initial_observation(hidden_origin):
    encoded, vent_uuid = record_release(hidden_origin=hidden_origin)
    native = RecordedSequence.model_validate_json(encoded, context=PASSIVE_EVENT_REPLAY)
    public = encode_player_sequence(project_sequence(native))
    before, roots = decode_player_sequence(public)
    activations = [node.fact for root in roots for node in root.events
                   if isinstance(node.fact, MechanismActivationFact)]
    fact, = activations
    assert fact.committed and fact.affected_positions
    if hidden_origin:
        assert fact.mechanism_uuid is None and fact.origin_position is None
        assert before.senses is not None and vent_uuid not in before.senses.spatial_effects
    else:
        assert fact.mechanism_uuid == vent_uuid and fact.origin_position == (4, 2)
    assert b"target_condition_uuid" not in public and b"target_item_uuid" not in public
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_release_after_blinding_cannot_borrow_its_outer_roots_earlier_sight():
    encoded, _ = record_release(blinded_child=True)
    native = RecordedSequence.model_validate_json(encoded, context=PASSIVE_EVENT_REPLAY)
    _, roots = decode_player_sequence(encode_player_sequence(project_sequence(native)))
    assert not any(isinstance(node.fact, MechanismActivationFact) for root in roots for node in root.events)
