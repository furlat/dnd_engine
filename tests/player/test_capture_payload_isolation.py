"""A captured lineage keeps its value while later native history is stored.

Stored event versions are frozen values (P7b): capture holds them by reference, and a late
child of a captured version is linked through the queue, not written into the version.
"""

from copy import deepcopy
from uuid import uuid4

from dnd.core.effect_types import EventResolutionRef, ObservedChangeRef
from dnd.core.events import (Event, EventPhase, EventQueue, EventType, SensoryUpdateEvent,
    SpatialChangeEvent, SpatialChangeType, SensesUpdateHint, StepMovementEvent)
from dnd.player.capture import capture_lineage
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.senses import PerceivedContact, SenseMode, SensesType


def _step_with_provenance(observer):
    source = StepMovementEvent(source_entity_uuid=observer,
        from_position=(0, 0), to_position=(1, 0)).phase_to(EventPhase.COMPLETION)
    resolution = EventResolutionRef(lineage_uuid=source.lineage_uuid)
    return SensoryUpdateEvent(source_entity_uuid=observer, observer_uuid=observer, resolution_ref=resolution,
        observed_changes=(ObservedChangeRef(source_event_uuid=source.uuid,
            source_index=EventQueue.get_event_index(source.uuid), resolution_ref=resolution,
            field='position', owner_uuid=observer),),
    ).phase_to(EventPhase.COMPLETION)


def _sensory_containers(observer):
    subject = uuid4()
    return SensoryUpdateEvent(source_entity_uuid=observer, observer_uuid=observer,
        visible_cells_added=[(1, 2)], seen_cells_added=[(1, 2)],
        entity_contacts_changed={subject: PerceivedContact(position=(1, 2), visual=True)},
        effective_light_levels_changed={'1,2': 3}, hazardous_cells_changed={'1,2': False},
        sense_modes=[SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)],
    ).phase_to(EventPhase.COMPLETION)


def _light_change(observer):
    return SpatialChangeEvent(source_entity_uuid=observer,
        change_type=SpatialChangeType.LIGHT_CHANGED, position=(1, 2),
        light_level_map={'1,2': 3},
        senses_hint=SensesUpdateHint(light_changed_positions={(1, 2)}),
    ).phase_to(EventPhase.COMPLETION)


def check_capture_is_stable(build) -> None:
    reset_engine_runtime()
    try:
        observer = uuid4()
        event = build(observer)
        retained = capture_lineage(event, observer_uuid=observer).root
        expected = deepcopy(retained)

        late_child = Event(source_entity_uuid=observer, event_type=EventType.TRIGGER_EVENT,
            phase=EventPhase.DECLARATION, parent_event=event.uuid).phase_to(EventPhase.COMPLETION)
        build(observer)

        assert retained == expected, build.__name__
        assert late_child.uuid not in retained.children_events, build.__name__
        assert late_child.uuid in EventQueue.child_links(event)[0], build.__name__
    finally:
        reset_engine_runtime()


def test_captured_lineage_is_unchanged_by_later_history():
    for build in (_step_with_provenance, _sensory_containers, _light_change):
        check_capture_is_stable(build)
