"""Recorded lineage payloads remain detached from later native mutations."""

from copy import deepcopy
from uuid import uuid4

from pydantic import Field

from dnd.core.effect_types import EventResolutionRef, ObservedChangeRef
from dnd.core.events import (EventPhase, EventQueue, SensoryUpdateEvent,
    SpatialChangeEvent, SpatialChangeType, SensesUpdateHint, StepMovementEvent)
from dnd.player.capture import capture_lineage
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.senses import PerceivedContact, SenseMode, SensesType
from tests.sensory_cells import packed_cells


class ExtendedContact(PerceivedContact):
    notes: list[str] = Field(default_factory=list)


class ExtendedSensoryEvent(SensoryUpdateEvent):
    notes: list[str] = Field(default_factory=list)


class ExtendedResolutionRef(EventResolutionRef):
    notes: list[str] = Field(default_factory=list)


def test_captured_native_event_and_provenance_extensions_remain_detached():
    reset_engine_runtime()
    try:
        observer = uuid4()
        source = StepMovementEvent(source_entity_uuid=observer,
            from_position=(0, 0), to_position=(1, 0)).phase_to(EventPhase.COMPLETION)
        resolution = ExtendedResolutionRef(lineage_uuid=source.lineage_uuid, notes=['observed'])
        event = ExtendedSensoryEvent(source_entity_uuid=observer, observer_uuid=observer,
            notes=['original'], resolution_ref=resolution,
            observed_changes=(ObservedChangeRef(source_event_uuid=source.uuid,
                source_index=EventQueue.get_event_index(source.uuid), resolution_ref=resolution,
                field='position', owner_uuid=observer),),
        ).phase_to(EventPhase.COMPLETION)
        retained = capture_lineage(event, observer_uuid=observer).root
        expected = deepcopy(retained)

        event.notes.append('later')
        event.resolution_ref.notes.append('later event provenance')
        event.observed_changes[0].resolution_ref.notes.append('later observation provenance')

        assert retained == expected
    finally:
        reset_engine_runtime()


def test_captured_sensory_lineage_detaches_containers_and_mutable_extensions():
    reset_engine_runtime()
    try:
        observer, subject, extension = uuid4(), uuid4(), uuid4()
        # Packed cell values are immutable; the containers beside them are detached.
        event = SensoryUpdateEvent(source_entity_uuid=observer, observer_uuid=observer,
            **packed_cells(dict(visible_cells_added=[(1, 2)], seen_cells_added=[(1, 2)],
                effective_light_levels_changed={(1, 2): 3}, hazardous_cells_changed={(1, 2): False})),
            entity_contacts_changed={subject: PerceivedContact(position=(1, 2), visual=True),
                extension: ExtendedContact(position=(2, 2), visual=True, notes=['observed'])},
            sense_modes=[SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)],
        ).phase_to(EventPhase.COMPLETION)
        event.identified_entity_observer_uuids[str(subject)] = {str(observer)}
        event.located_entity_observer_uuids[str(subject)] = {str(observer)}
        event.located_position_observer_uuids['1,2'] = {str(observer)}
        cursor = EventQueue.event_cursor()
        retained = capture_lineage(event, observer_uuid=observer).root
        expected = deepcopy(retained)

        event.children_events.append(uuid4())
        event.children_lineages.append(uuid4())
        event.lineage_children_events.append(uuid4())
        event.identified_entity_observer_uuids[str(subject)].clear()
        event.located_entity_observer_uuids[str(subject)].clear()
        event.located_position_observer_uuids['1,2'].clear()
        event.entity_contacts_changed[extension].notes.append('later')
        event.entity_contacts_changed.clear()
        event.entity_contacts_removed.add(subject)
        event.object_contacts_removed.add(subject)
        event.spatial_effects_removed.add(subject)
        event.sense_modes[0].range_feet = 120

        assert retained == expected
        assert EventQueue.event_cursor() == cursor
    finally:
        reset_engine_runtime()


def test_captured_light_lineage_detaches_light_map_and_hint_sets():
    reset_engine_runtime()
    try:
        observer = uuid4()
        event = SpatialChangeEvent(source_entity_uuid=observer,
            change_type=SpatialChangeType.LIGHT_CHANGED, position=(1, 2),
            light_level_map={'1,2': 3},
            senses_hint=SensesUpdateHint(light_changed_positions={(1, 2)}),
        ).phase_to(EventPhase.COMPLETION)
        retained = capture_lineage(event, observer_uuid=observer).root
        expected = deepcopy(retained)
        event.light_level_map['1,2'] = 0
        event.senses_hint.light_changed_positions.clear()
        assert retained == expected
    finally:
        reset_engine_runtime()
