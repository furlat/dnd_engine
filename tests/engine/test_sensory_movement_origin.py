"""Every emitted movement observation uses its committed observer position."""

from dataclasses import replace

import pytest

from dnd.blocks.sensory import capture_senses_snapshot
from dnd.conditions import Invisible
from dnd.core.base_block import LightLevel, SenseMode, SensesType
from dnd.core.events import EventPhase, EventQueue, EventType, SpatialChangeEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.player.event_record import decode_event, encode_event
from dnd.types.senses import reduce_senses_snapshot
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state
from tests.engine.test_sensory_initial_replay import sensory_since


@pytest.mark.parametrize("sense", [SensesType.DARKVISION, SensesType.TRUESIGHT])
@pytest.mark.parametrize("attached_light", [False, True])
def test_movement_range_is_correct_at_every_sensory_completion(sense, attached_light):
    # The target crosses the 15-foot sense boundary, outside the small torch's
    # reach. Truesight separately tests bypassing an invisible creature on an
    # otherwise visible tile. No explicit refresh follows either movement.
    reset_senses_state(width=7, height=1, default_light=(
        LightLevel.DARKNESS if sense is SensesType.DARKVISION else LightLevel.DIM_LIGHT))
    mover = create_skeleton(name="Moving observer", position=(0, 0), darkvision=False)
    target = create_skeleton(name="Range boundary target", position=(4, 0), darkvision=False)
    if sense is SensesType.TRUESIGHT:
        target.add_condition(Invisible(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    mover.senses.sense_modes = [SenseMode(sense_type=sense, range_feet=15)]
    if attached_light:
        get_map().add_light_source(mover.position, bright_radius_feet=5,
            dim_radius_feet=10, anchor_uuid=mover.uuid)
    mover.update_entity_senses(max_distance=6)
    target_id = target.uuid
    initial_contact = target_id in mover.senses.entities
    assert not initial_contact

    replayed = None
    for event in sensory_since(mover.uuid):
        replayed = reduce_senses_snapshot(mover.uuid, replayed, decode_event(encode_event(event)))
    assert replayed is not None
    for destination, expected_contact in [((1, 0), True), ((0, 0), False)]:
        cursor = EventQueue.event_cursor()
        Entity.update_entity_position(mover, destination)
        observations = sensory_since(mover.uuid, cursor)
        assert observations
        for event in observations:
            replayed = reduce_senses_snapshot(mover.uuid, replayed, decode_event(encode_event(event)))
            if replayed.position == destination:
                present = target_id in replayed.entities
                assert present == expected_contact, (
                    "A committed sensory prefix measured range from the previous cell",
                    event.update_reason, destination, replayed.entities)
                if sense is SensesType.DARKVISION:
                    assert (target.position in replayed.visible) == expected_contact
            assert event.cause_event_uuid == event.parent_event
            assert EventQueue.get_event_by_uuid(event.cause_event_uuid) is not None
        assert replayed.position == destination
        final_contact = target_id in mover.senses.entities
        assert final_contact == expected_contact
        assert mover.senses._paths_dirty
        assert replace(replayed, paths_dirty=False) == replace(
            capture_senses_snapshot(mover.senses), paths_dirty=False)
        light_completions = [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, SpatialChangeEvent)
            and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
            and event.phase is EventPhase.COMPLETION]
        assert len(light_completions) == int(attached_light)
        if attached_light:
            assert any(EventQueue.get_event_by_uuid(event.cause_event_uuid).event_type
                is EventType.SPATIAL_LIGHT_CHANGED for event in observations)
        # The public full refresh is a reference for retained-field reuse. It
        # may materialize navigation but must not correct perception or emit
        # another sensory delta after the committed movement boundary.
        refresh_cursor = EventQueue.event_cursor()
        mover.update_entity_senses(max_distance=6)
        refreshed = capture_senses_snapshot(mover.senses)
        assert replace(replayed, paths_dirty=False) == replace(refreshed, paths_dirty=False)
        assert sensory_since(mover.uuid, refresh_cursor) == ()
